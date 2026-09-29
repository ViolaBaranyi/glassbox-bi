"""
M2 — Betanítás: LightGBM baseline, kalibrációval és becsületes kiértékeléssel.

Ez még nem a 40 futásos sweep, hanem az az EGY modell, amire a többi épül.
A rendszerterv szerinti döntések itt már érvényesek:

  * learning_rate = 0.05, RÖGZÍTETT (nem hangoljuk — rendszerterv 10.)
  * a korai leállítás KIZÁRÓLAG a PR-AUC-t figyeli (lásd PARAMS megjegyzés)
  * időbeli szétvágás, nem véletlen
  * PR-AUC a fő mérőszám, nem pontosság (a pozitív osztály ~8%)
  * izotonikus kalibráció a validáción, mert a felületen valószínűséget mutatunk
  * determinisztikus futás: azonos adat + mag -> azonos modell (NF-1)
  * a szivárgásteszt a betanítás ELŐTT fut, és megállítja a folyamatot

Futtatás:
    python -m pipeline.train
"""

from __future__ import annotations

import argparse
import inspect
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import sklearn
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from data.db import DB_PATH, WarehouseUnavailable, connect, use_utf8_console
from pipeline.features import LeakageError, build_features, schema, suspicious_features
from pipeline.split import temporal_split

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"

# --- rögzített hiperparaméterek (a későbbi hangolás a fa SZERKEZETÉT érinti) --
PARAMS = dict(
    objective="binary",
    # A korai leállítás metrikája KIZÁRÓLAG az average_precision (PR-AUC).
    # Ha az alapértelmezett binary_logloss is futna, a class_weight="balanced"
    # miatt az azonnal romlani kezdene a validáción, és a leállítás pár fa
    # után megállítaná a tanítást (az első változatnál 7 fánál állt meg).
    metric="average_precision",
    first_metric_only=True,
    learning_rate=0.05,        # RÖGZÍTETT
    n_estimators=3000,         # felső korlát; a korai leállítás dönt
    num_leaves=31,
    min_child_samples=60,
    feature_fraction=0.85,
    bagging_fraction=0.85,
    bagging_freq=1,
    reg_lambda=1.0,
    class_weight="balanced",
    # NF-1 reprodukálhatóság: szálszámtól független, bitre azonos eredmény.
    deterministic=True,
    force_row_wise=True,
    n_jobs=-1,
    verbose=-1,
)
EARLY_STOPPING_ROUNDS = 150


# ----------------------------------------------------------------- mérőszámok
def _bins(p, n_bins):
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    return edges, np.clip(np.digitize(p, edges[1:-1], right=False), 0, n_bins - 1)


def expected_calibration_error(y_true, p, n_bins: int = 10) -> float:
    """ECE: binenként |átlagos becslés − tényleges arány|, mintaszámmal súlyozva."""
    y_true = np.asarray(y_true, dtype=float)
    p = np.asarray(p, dtype=float)
    _, idx = _bins(p, n_bins)
    ece = 0.0
    for b in range(n_bins):
        m = idx == b
        if m.any():
            ece += (m.sum() / len(p)) * abs(p[m].mean() - y_true[m].mean())
    return float(ece)


def reliability_table(y_true, p, n_bins: int = 10) -> list[dict]:
    y_true = np.asarray(y_true, dtype=float)
    p = np.asarray(p, dtype=float)
    edges, idx = _bins(p, n_bins)
    rows = []
    for b in range(n_bins):
        m = idx == b
        if m.any():
            rows.append({
                "bin": f"{edges[b]:.1f}-{edges[b + 1]:.1f}",
                "n": int(m.sum()),
                "atlag_becsles": round(float(p[m].mean()), 4),
                "tenyleges_arany": round(float(y_true[m].mean()), 4),
            })
    return rows


def evaluate(y_true, p) -> dict:
    return {
        "pr_auc": round(float(average_precision_score(y_true, p)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, p)), 4),
        "brier": round(float(brier_score_loss(y_true, p)), 5),
        "ece": round(expected_calibration_error(y_true, p), 5),
    }


def git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
            stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return "nincs-git"


def _print_reliability(raw_rows, cal_rows):
    print("\nMEGBÍZHATÓSÁG — ha a modell X%-ot mond, tényleg X% késik-e?")
    print(f"  {'becslés':<10}{'kalibrálatlan':>28}{'kalibrált':>28}")
    print(f"  {'sáv':<10}{'n':>8}{'mond':>10}{'valóság':>10}{'n':>8}{'mond':>10}{'valóság':>10}")
    raw_by = {r["bin"]: r for r in raw_rows}
    cal_by = {r["bin"]: r for r in cal_rows}

    def cell(r):
        if r is None:
            return f"{'':>8}{'':>10}{'':>10}"
        return f"{r['n']:>8}{r['atlag_becsles']:>10.2f}{r['tenyleges_arany']:>10.2f}"

    for b in sorted(set(raw_by) | set(cal_by)):
        print(f"  {b:<10}{cell(raw_by.get(b))}{cell(cal_by.get(b))}")
    print("  (kis mintájú sávokban — n < 100 — a becslés bizonytalan)")


# ----------------------------------------------------------------- betanítás
def run(db_path: Path = DB_PATH, seed: int = 42, tag: str = "baseline",
        balance: str = "balanced", write_artifacts: bool = True) -> dict:
    """
    balance: "balanced" — class_weight="balanced" (a rendszerterv jelenlegi alapja)
             "none"     — súlyozás nélkül (természetes eloszlás; lásd a
                          konzultációs kérdést a rendszerterv állapot-szakaszában)
    """
    if balance not in ("balanced", "none"):
        raise ValueError(f"Ismeretlen balance érték: {balance!r}")
    con = connect(db_path, read_only=True)
    X, y, meta = build_features(con)   # a szivárgásteszt itt fut le
    prov = con.execute("SELECT * FROM meta_build").df().iloc[0].to_dict()
    con.close()

    forras = str(prov["adatforras"])
    sp = temporal_split(meta["rendeles_idopont"])
    print(f"Adatforrás: {forras.upper()}")
    print(f"Jellemzők: {X.shape[1]} db, {len(X):,} sor, pozitív arány {y.mean():.1%}")
    print(f"Időbeli szétvágás ({sp.source}):")
    print(sp.describe(meta["rendeles_idopont"]))

    Xtr, ytr = X.loc[sp.train], y.loc[sp.train]
    Xva, yva = X.loc[sp.valid], y.loc[sp.valid]
    Xte, yte = X.loc[sp.test], y.loc[sp.test]

    # A szivárgásvédelem második szintje — CSAK a tanító részen, hogy a teszthez
    # semmilyen formában ne nyúljunk a végső kiértékelés előtt.
    gyanus = suspicious_features(Xtr, ytr)
    if gyanus:
        raise LeakageError(
            "Gyanúsan jós jellemző(k) — szivárgás valószínű, a betanítás leáll: "
            + ", ".join(f"{c} (AUC {a})" for c, a in gyanus))
    print("Szivárgásvédelem: névszűrő és AUC-őr rendben.")

    params = dict(PARAMS, random_state=seed)
    if balance == "none":
        params["class_weight"] = None
    model = lgb.LGBMClassifier(**params)
    callbacks = [
        lgb.early_stopping(EARLY_STOPPING_ROUNDS, first_metric_only=True, verbose=False),
        lgb.log_evaluation(0),
    ]
    # A LightGBM 4.7 óta az eval_set helyett eval_X / eval_y a javasolt forma.
    # Mindkettőt kezeljük, hogy a kód régebbi verzióval is fusson.
    if "eval_X" in inspect.signature(model.fit).parameters:
        model.fit(Xtr, ytr, eval_X=Xva, eval_y=yva,
                  eval_metric="average_precision", callbacks=callbacks)
    else:
        model.fit(Xtr, ytr, eval_set=[(Xva, yva)],
                  eval_metric="average_precision", callbacks=callbacks)
    n_trees = int(model.best_iteration_ or params["n_estimators"])
    print(f"\nBetanítva: {n_trees} fa (korai leállítás a validáción, PR-AUC alapján)")

    p_va_raw = model.predict_proba(Xva)[:, 1]
    p_te_raw = model.predict_proba(Xte)[:, 1]

    # Izotonikus kalibráció a VALIDÁCIÓN, alkalmazva a teszten.
    # Megjegyzés: a kalibrált PR-AUC / ROC-AUC kicsit alacsonyabb lehet, mert az
    # izotonikus regresszió lépcsős függvény, ami holtversenyeket hoz létre a
    # rangsorban. A RANGSOROLÓ képességet a kalibrálatlan, a VALÓSZÍNŰSÉG
    # hitelességét a kalibrált számok mutatják — mindkettőt közöljük.
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(p_va_raw, yva)
    p_te_cal = iso.predict(p_te_raw)

    m_raw = evaluate(yte, p_te_raw)
    m_cal = evaluate(yte, p_te_cal)
    base_rate = float(yte.mean())
    rel_raw = reliability_table(yte, p_te_raw)
    rel_cal = reliability_table(yte, p_te_cal)

    print("\nTESZT — érintetlen, legkésőbbi időszak")
    print(f"  bázisráta (a késések aránya):  {base_rate:.4f}  <- a PR-AUC ehhez viszonyítandó")
    print(f"  {'':<14}{'PR-AUC':>9}{'ROC-AUC':>9}{'Brier':>9}{'ECE':>9}")
    for label, m in [("kalibrálatlan", m_raw), ("kalibrált", m_cal)]:
        print(f"  {label:<14}{m['pr_auc']:>9.4f}{m['roc_auc']:>9.4f}"
              f"{m['brier']:>9.4f}{m['ece']:>9.4f}")
    print(f"  emelés a bázisrátához képest: {m_raw['pr_auc'] / base_rate:.1f}x")

    _print_reliability(rel_raw, rel_cal)

    if m_cal["roc_auc"] > 0.97:
        print("\n  FIGYELEM: 0.97 fölötti ROC-AUC. Tabuláris üzleti adaton ez "
              "szinte mindig adatszivárgásra utal, nem sikerre.")

    imp = (pd.Series(model.booster_.feature_importance(importance_type="gain"),
                     index=X.columns)
           .sort_values(ascending=False))
    imp = imp / imp.sum()
    print("\nJellemzőfontosság (LightGBM gain-arány, TOP 8)")
    print("  (tájékoztató — a valódi magyarázatot a következő lépésben a SHAP adja)")
    for name, val in imp.head(8).items():
        print(f"  {name:<28} {val:>6.1%}")

    result = {
        "modell": "LightGBM",
        "kiegyensulyozas": balance,
        "adatforras": forras,
        "seed": seed,
        "fak_szama": n_trees,
        "bazisrata": round(base_rate, 4),
        "teszt_kalibralatlan": m_raw,
        "teszt_kalibralt": m_cal,
        "jellemzok": int(X.shape[1]),
        "sorok": int(len(X)),
    }
    if not write_artifacts:
        return result

    # ------------------------------------------------------------ artefaktum
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = ARTIFACTS / f"{stamp}_lgbm_{tag}_{balance}_seed{seed}"
    out.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, out / "model.joblib")
    joblib.dump(iso, out / "calibrator.joblib")
    model.booster_.save_model(str(out / "model.txt"))
    (out / "feature_schema.json").write_text(
        json.dumps(schema(X), ensure_ascii=False, indent=2), encoding="utf-8")

    metrics = {
        "futas": stamp,
        **result,
        "params": {k: v for k, v in params.items() if k != "n_jobs"},
        "early_stopping_rounds": EARLY_STOPPING_ROUNDS,
        "adat": {
            "forras": forras,
            "tarhaz_epitve": str(prov["epitve"]),
            "sorok": int(len(X)),
            "jellemzok": int(X.shape[1]),
            "pozitiv_arany": round(float(y.mean()), 4),
            "karanten_sorok": int(prov["karanten_osszes"]),
        },
        "szetvagas": {
            "forras": sp.source,
            "train_vege": str(sp.train_end.date()),
            "valid_vege": str(sp.valid_end.date()),
            "meret": {"train": len(sp.train), "valid": len(sp.valid), "test": len(sp.test)},
        },
        "megbizhatosag_kalibralatlan": rel_raw,
        "megbizhatosag_kalibralt": rel_cal,
        "jellemzofontossag_gain": {k: round(float(v), 4) for k, v in imp.items()},
        "kornyezet": {
            "python": platform.python_version(),
            "lightgbm": lgb.__version__,
            "scikit_learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "os": platform.platform(),
            "git": git_hash(),
        },
    }
    (out / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    figyelmeztetes = (
        "\n> **SZINTETIKUS ADAT.** Ez a modell generált adaton tanult. A számok a\n"
        "> gépezet működését mutatják, a valóságról semmit nem mondanak.\n"
        if forras == "szintetikus" else "")
    card = f"""# Model card — {stamp}
{figyelmeztetes}
## Mire tanítottuk
Bináris osztályozás: késik-e a rendelés a vállalt határidőhöz képest.
Adat: Olist-alakú tárház ({forras}), {len(X):,} kézbesített rendelés,
{sp.train_end.date()} előtti időszakon tanítva, {n_trees} fával.
Osztálysúlyozás: {balance}.

## Jellemzők
{X.shape[1]} mező, mind a rendelés LEADÁSAKOR ismert információból.
Az eladói előzmény-jellemzők as-of illesztéssel készülnek: csak a rendelés
pillanatában már LEZÁRULT korábbi rendelések kimenetét látják.
Tiltólistán: tényleges kézbesítés, feladás dátuma, értékelés, a címke.
A szivárgásteszt minden betanítás előtt lefut.

## Teljesítmény (érintetlen teszthalmaz, {sp.valid_end.date()} utáni időszak)
| mérőszám | kalibrálatlan | kalibrált |
|---|---|---|
| PR-AUC | {m_raw['pr_auc']} | {m_cal['pr_auc']} |
| ROC-AUC | {m_raw['roc_auc']} | {m_cal['roc_auc']} |
| Brier | {m_raw['brier']} | {m_cal['brier']} |
| ECE | {m_raw['ece']} | {m_cal['ece']} |

Bázisráta (a késések aránya a teszten): {base_rate:.4f}.
A rangsoroló képességet a kalibrálatlan, a valószínűség hitelességét a
kalibrált oszlop mutatja.

## Mire NEM használható
* Más webáruházra, más országra, más időszakra — az eladói viselkedés adatfüggő.
* Egyedi rendelés sorsának garantálására: ez valószínűségi becslés.
* Oksági következtetésre: a modell együttjárást tanul, nem okot.

## Ismert korlátok
* Osztálysúlyozással (`balanced`) a nyers valószínűségek erősen torzak; ezért van kalibráció.
* Új eladónál az előzmény-jellemzők hiányoznak (NaN); a LightGBM ezt natívan kezeli.
* Egyetlen adathalmaz, egyetlen modellcsalád — az általánosíthatóság korlátozott.

## Reprodukálás
`python -m pipeline.train --seed {seed} --balance {balance}` — determinisztikus beállítással
(`deterministic=True`, `force_row_wise=True`). Környezet: `metrics.json`.
"""
    (out / "model_card.md").write_text(card, encoding="utf-8")
    (ARTIFACTS / "LATEST.txt").write_text(out.name, encoding="utf-8")

    print(f"\nArtefaktumok: {out}")
    result["artifacts"] = str(out)
    return result


def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="LightGBM baseline betanítása")
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--tag", type=str, default="baseline")
    ap.add_argument("--balance", choices=["balanced", "none"], default="balanced",
                    help="osztálysúlyozás: balanced (alapértelmezett) vagy none")
    a = ap.parse_args()
    try:
        run(a.db, a.seed, a.tag, a.balance)
    except (WarehouseUnavailable, LeakageError) as exc:
        print(f"\nHIBA:\n{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
