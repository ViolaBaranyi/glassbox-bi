"""
M2 — Betanítás: LightGBM baseline, becsületes kiértékeléssel.

Ez még nem a 40 futásos sweep, hanem az az EGY modell, amire a többi épül.
A rendszerterv és a témavezetői egyeztetés (okt. 2.) szerinti döntések:

  * learning_rate = 0.05, RÖGZÍTETT (nem hangoljuk — rendszerterv 10.)
  * a korai leállítás KIZÁRÓLAG a PR-AUC-t figyeli (lásd PARAMS megjegyzés)
  * időbeli szétvágás, nem véletlen
  * PR-AUC a fő mérőszám, nem pontosság (a pozitív osztály kb. 6,8%)
  * SÚLYOZÁS NÉLKÜL tanítunk, és NINCS utólagos kalibrátor: a súlyozatlan
    modell nyers kimenete magától is jól kalibrált, az izotonikus leképezés
    az időbeli alapráta-eltolódás miatt rontott rajta (7. és 9. lelet). Így a
    SHAP pontosan a megjelenített számot bontja fel. A kalibráció csak
    DIAGNOSZTIKA: ECE két sávolással, CORP-felbontás, Brier-készség.
  * determinisztikus futás: azonos adat + mag -> azonos modell (NF-1)
  * a szivárgásteszt a betanítás ELŐTT fut, és megállítja a folyamatot

Az alapbeállítás a LEZÁRT v3 PROTOKOLL (docs/v3_protokoll.json, okt. 9.):
  --trees cv   bővülő ablakos keresztvalidáció a TANÍTÓ időszakon belül, N_fix =
               max(50, medián) — a validációs ablak semmit nem befolyásol (útiterv
               T5, lásd pipeline/model_selection.py)
  --purge      címke-tisztítás — csak azokon a tanító sorokon tanul, amelyeknek a
               kimenete a vágás pillanatában már eldőlt (split.settled_before)
Összehasonlításhoz: --trees korai (korai leállítás a validációs ablakon, a régi út),
--trees <szám> (pontosan ennyi fa), --no-purge (címke-tisztítás nélkül).

Futtatás:
    python -m pipeline.train                             # a lezárt protokoll szerint
    python -m pipeline.train --trees korai --no-purge    # a régi út, összehasonlításhoz
    python -m pipeline.train --balance balanced          # összehasonlításhoz
    python -m pipeline.train --drop honap                # abláció: hónap nélkül
    python -m pipeline.train --drop naptar               # hónap + ünnep nélkül

Az abláció csak a betanításból zár ki jellemzőket; a jellemzőszerződés
(features.FEATURES) és a szivárgásvédelem változatlan. A kizárt jellemzők a
metrics.json-ban, a model cardban és az artefaktummappa nevében is látszanak.
"""

from __future__ import annotations

import argparse
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
from pipeline.features import (
    LeakageError, build_features, resolve_drop, schema, suspicious_features)
from pipeline.split import settled_before, temporal_split

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"

# --- rögzített hiperparaméterek (a későbbi hangolás a fa SZERKEZETÉT érinti) --
PARAMS = dict(
    objective="binary",
    # A korai leállítás metrikája KIZÁRÓLAG az average_precision (PR-AUC).
    # Ha az alapértelmezett binary_logloss is futna, a class_weight="balanced"
    # (összehasonlító ág) mellett az azonnal romlani kezdene a validáción, és a
    # leállítás pár fa után megállítaná a tanítást (egyszer 7 fánál állt meg).
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
    class_weight=None,         # súlyozás nélkül (okt. 2-i döntés); --balance balanced: összevetés
    # NF-1 reprodukálhatóság: szálszámtól független, bitre azonos eredmény.
    deterministic=True,
    force_row_wise=True,
    n_jobs=-1,
    verbose=-1,
)
EARLY_STOPPING_ROUNDS = 150


# ----------------------------------------------------------------- mérőszámok
def _bins(p, n_bins, strategy="uniform"):
    """
    Sávhatárok és sávindexek.
      uniform  — 10 egyenlő szélességű sáv (0–0,1, 0,1–0,2, …)
      quantile — 10 egyenlő elemszámú sáv (tizedek). Ritka eseménynél ez a
                 beszédesebb: ha az előrejelzések 98%-a 10% alatt van, az
                 egyenlő szélességű sávolás szinte mindent egy sávba tesz, és az
                 ECE főleg az ÁTLAGOT méri.
    """
    p = np.asarray(p, dtype=float)
    if strategy == "uniform":
        edges = np.linspace(0.0, 1.0, n_bins + 1)
    elif strategy == "quantile":
        edges = np.unique(np.quantile(p, np.linspace(0.0, 1.0, n_bins + 1)))
        if len(edges) < 2:                      # minden előrejelzés azonos
            edges = np.array([p.min(), p.max()])
    else:
        raise ValueError(f"Ismeretlen sávolás: {strategy!r}")
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, len(edges) - 2)
    return edges, idx


def expected_calibration_error(y_true, p, n_bins: int = 10,
                               strategy: str = "uniform") -> float:
    """ECE: sávonként |átlagos becslés − tényleges arány|, elemszámmal súlyozva."""
    y_true = np.asarray(y_true, dtype=float)
    p = np.asarray(p, dtype=float)
    edges, idx = _bins(p, n_bins, strategy)
    ece = 0.0
    for b in range(len(edges) - 1):
        m = idx == b
        if m.any():
            ece += (m.sum() / len(p)) * abs(p[m].mean() - y_true[m].mean())
    return float(ece)


def reliability_table(y_true, p, n_bins: int = 10, strategy: str = "uniform") -> list[dict]:
    y_true = np.asarray(y_true, dtype=float)
    p = np.asarray(p, dtype=float)
    edges, idx = _bins(p, n_bins, strategy)
    rows = []
    for b in range(len(edges) - 1):
        m = idx == b
        if m.any():
            rows.append({
                "bin": f"{edges[b]:.3f}-{edges[b + 1]:.3f}",
                "n": int(m.sum()),
                "atlag_becsles": round(float(p[m].mean()), 4),
                "tenyleges_arany": round(float(y_true[m].mean()), 4),
            })
    return rows


def corp_decomposition(y_true, p) -> dict:
    """
    A Brier-pontszám CORP-felbontása (Dimitriadis, Gneiting & Jordan, PNAS 2021):
        Brier = MCB − DSC + UNC
      MCB  (miscalibration)  — mennyit javítana egy utólagos, monoton
            újrakalibrálás UGYANEZEN az adaton (PAV / izotonikus regresszió);
            0 = tökéletesen kalibrált
      DSC  (discrimination)  — mennyivel jobb az újrakalibrált előrejelzés a
            konstans átlagnál; ez a felbontás / megkülönböztető erő
      UNC  (uncertainty)     — a konstans átlag Brier-értéke, az adat nehézsége
    Ez diagnosztika (mintán belüli újrakalibrálás), nem javító lépés.
    """
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(p, dtype=float)
    iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    p_rc = iso.fit(p, y).predict(p)
    brier = float(np.mean((p - y) ** 2))
    s_rc = float(np.mean((p_rc - y) ** 2))
    unc = float(np.mean((y.mean() - y) ** 2))
    return {"brier": round(brier, 6), "mcb": round(brier - s_rc, 6),
            "dsc": round(unc - s_rc, 6), "unc": round(unc, 6)}


def brier_skill(y_true, p, reference_rate: float) -> float:
    """1 − Brier / Brier(konstans előrejelzés a megadott aránnyal)."""
    y = np.asarray(y_true, dtype=float)
    ref = float(np.mean((reference_rate - y) ** 2))
    return round(1.0 - float(np.mean((np.asarray(p, dtype=float) - y) ** 2)) / ref, 4)


def evaluate(y_true, p) -> dict:
    return {
        "pr_auc": round(float(average_precision_score(y_true, p)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, p)), 4),
        "brier": round(float(brier_score_loss(y_true, p)), 5),
        "ece": round(expected_calibration_error(y_true, p), 5),
        "ece_egyenlo_elemszam": round(expected_calibration_error(y_true, p, strategy="quantile"), 5),
    }


def git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
            stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return "nincs-git"


def _print_reliability(rows):
    print("\nMEGBÍZHATÓSÁG — ha a modell X%-ot mond, tényleg X% késik-e?")
    print("  (tizedek: mindegyik sávban a rendelések kb. tizede)")
    print(f"  {'becslési sáv':<16}{'n':>8}{'mond':>10}{'valóság':>10}")
    for r in rows:
        print(f"  {r['bin']:<16}{r['n']:>8}{r['atlag_becsles']:>10.3f}{r['tenyleges_arany']:>10.3f}")


# ----------------------------------------------------------------- betanítás
def _trees_mode(trees) -> tuple[str, int | None]:
    """'korai' | 'cv' | pozitív egész → (mód, fix fa-szám vagy None)."""
    if isinstance(trees, str) and trees.strip().lower() in ("korai", "cv"):
        return trees.strip().lower(), None
    try:
        n = int(trees)
    except (TypeError, ValueError):
        raise ValueError(f"Ismeretlen --trees érték: {trees!r} (korai, cv vagy pozitív egész)")
    if n < 1:
        raise ValueError(f"A fák száma legalább 1 kell legyen, nem {n}.")
    return "rogzitett", n


def run(db_path: Path = DB_PATH, seed: int = 42, tag: str = "baseline",
        balance: str = "none", write_artifacts: bool = True,
        drop=None, trees="cv", purge: bool = True,
        return_predictions: bool = False) -> dict:
    """
    balance: "none"     — súlyozás nélkül (alapértelmezés, okt. 2-i döntés)
             "balanced" — class_weight="balanced"; csak összehasonlításhoz: a
                          nyers valószínűségei erősen torzak (ECE kb. 0,28)
    drop:    abláció — kizárandó jellemzők vagy csoportok (features.FEATURE_GROUPS),
             pl. ["honap"]. Ismeretlen névre hibát ad, nem hallgat.
    trees:   "cv" (bővülő ablakos CV a tanító időszakon — a lezárt protokoll),
             "korai" (korai leállítás a validáción, a régi út), vagy egy pozitív
             egész (pontosan ennyi fa)
    purge:   címke-tisztítás — csak a vágás előtt lezárult kimenetű tanító sorok
             (a lezárt protokoll szerint be)
    return_predictions: a validációs és a teszt előrejelzéseket is visszaadja
             (a lezárt alapfutás bootstrapjához); a metrics.json-ba nem kerülnek
    """
    if balance not in ("balanced", "none"):
        raise ValueError(f"Ismeretlen balance érték: {balance!r}")
    mode, n_fixed = _trees_mode(trees)
    drop_names = [str(d).strip() for d in (drop or []) if str(d).strip()]
    drop_cols = resolve_drop(drop_names)   # elgépelésnél itt megáll, még a betöltés előtt
    con = connect(db_path, read_only=True)
    X, y, meta = build_features(con)   # a szivárgásteszt itt fut le
    prov = con.execute("SELECT * FROM meta_build").df().iloc[0].to_dict()
    con.close()
    if drop_cols:
        X = X.drop(columns=drop_cols)

    forras = str(prov["adatforras"])
    sp = temporal_split(meta["rendeles_idopont"])
    print(f"Adatforrás: {forras.upper()}")
    print(f"Jellemzők: {X.shape[1]} db, {len(X):,} sor, pozitív arány {y.mean():.1%}")
    if drop_cols:
        print(f"ABLÁCIÓ — kizárva ({', '.join(drop_names)}): {', '.join(drop_cols)}")
    print(f"Időbeli szétvágás ({sp.source}):")
    print(sp.describe(meta["rendeles_idopont"]))

    # Címke-tisztítás: csak azok a tanító sorok, amelyeknek a kimenete a vágáskor
    # már eldőlt (a vállalt határidejük napja a vágás előtt véget ért).
    train_idx = sp.train
    if purge:
        train_idx = settled_before(sp.train, meta["vallalt_hatarido"], sp.train_end)
        print(f"Címke-tisztítás: {len(sp.train) - len(train_idx):,} tanító sor kimarad "
              f"(a vállalt határidejük {sp.train_end.date()} vagy később) — "
              f"marad {len(train_idx):,}")

    Xtr, ytr = X.loc[train_idx], y.loc[train_idx]
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

    # (körkörös importot kerülünk: a model_selection a train konstansait használja)
    from pipeline.model_selection import (
        cross_validate, fit_early_stopping, fit_fixed, model_params)
    params = model_params(seed, balance)
    cv = None
    if mode == "korai":
        model, n_trees = fit_early_stopping(params, Xtr, ytr, Xva, yva)
        fa_indok = "korai leállítás a validációs ablakon, PR-AUC alapján"
    elif mode == "cv":
        cv = cross_validate(X, y, meta, sp.train, purge=purge, balance=balance)
        n_trees = cv["n_fix"]
        model = fit_fixed(params, Xtr, ytr, n_trees)
        fa_indok = (f"bővülő ablakos CV a tanító időszakon: medián {cv['median']:g}, "
                    f"alsó korlát {cv['n_min']}")
    else:
        n_trees = n_fixed
        model = fit_fixed(params, Xtr, ytr, n_trees)
        fa_indok = "rögzített fa-szám (parancssorból)"
    if mode != "korai":
        params = dict(params, n_estimators=n_trees)
    print(f"\nBetanítva: {n_trees} fa ({fa_indok})")

    p_va = model.predict_proba(Xva)[:, 1]
    p_te = model.predict_proba(Xte)[:, 1]

    # A megjelenített szám a NYERS modellkimenet — utólagos kalibrátor nincs.
    m_te = evaluate(yte, p_te)
    base_rate = float(yte.mean())
    train_rate = float(ytr.mean())
    rel = reliability_table(yte, p_te, strategy="quantile")
    rel_uniform = reliability_table(yte, p_te, strategy="uniform")

    # ---- kalibrációs DIAGNOSZTIKA (semmi nem módosítja a modell kimenetét)
    corp = corp_decomposition(yte, p_te)
    skill = {
        # a predikció idején is ismert referencia: a tanító időszak aránya
        "tanito_bazisratahoz": brier_skill(yte, p_te, train_rate),
        # „orákulum": a teszt saját aránya, amit előre nem tudhattunk
        "teszt_bazisratahoz": brier_skill(yte, p_te, base_rate),
    }
    # Mi történt volna egy validáción illesztett izotonikus kalibrátorral?
    # (Ezt NEM használjuk — a 7. és 9. lelet szerint az eltolódás miatt ront.)
    iso = IsotonicRegression(out_of_bounds="clip").fit(p_va, yva)
    m_iso = evaluate(yte, iso.predict(p_te))

    print("\nTESZT — érintetlen, legkésőbbi időszak (a modell nyers kimenete)")
    print(f"  bázisráta (a késések aránya):  {base_rate:.4f}  <- a PR-AUC ehhez viszonyítandó"
          f"   (tanító időszak: {train_rate:.4f})")
    print(f"  {'':<10}{'PR-AUC':>9}{'ROC-AUC':>9}{'Brier':>9}{'ECE':>9}")
    print(f"  {'modell':<10}{m_te['pr_auc']:>9.4f}{m_te['roc_auc']:>9.4f}"
          f"{m_te['brier']:>9.4f}{m_te['ece']:>9.4f}")
    print(f"  emelés a bázisrátához képest: {m_te['pr_auc'] / base_rate:.1f}x")

    print("\nKALIBRÁCIÓ — diagnosztika (a megjelenített szám nem változik)")
    print(f"  ECE, 10 egyenlő szélességű sáv:  {m_te['ece']:.4f}"
          f"   egyenlő elemszámú sáv: {m_te['ece_egyenlo_elemszam']:.4f}")
    print(f"  Brier-felbontás (CORP):  MCB {corp['mcb']:.5f} · DSC {corp['dsc']:.5f}"
          f" · UNC {corp['unc']:.5f}   (Brier = MCB − DSC + UNC)")
    print(f"  Brier-készség:  a tanító időszak arányához {skill['tanito_bazisratahoz']:.1%}"
          f" · a teszt saját arányához {skill['teszt_bazisratahoz']:.1%}")
    print(f"  validáción illesztett izotonikus kalibrátorral (NEM használjuk): "
          f"ECE {m_iso['ece']:.4f}, Brier {m_iso['brier']:.4f}")

    _print_reliability(rel)

    if m_te["roc_auc"] > 0.97:
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
        "fa_szam_mod": mode,                  # korai | cv | rogzitett
        "fa_szam_indoklas": fa_indok,
        "modellvalasztas": cv,                # a bővülő ablakos CV részletei (cv módban)
        "cimke_tisztitas": {
            "be": bool(purge),
            "tanito_sorok": int(len(train_idx)),
            "kizart_tanito_sorok": int(len(sp.train) - len(train_idx)),
        },
        "bazisrata": round(base_rate, 4),
        "tanito_bazisrata": round(train_rate, 4),
        "teszt": m_te,
        "teszt_diagnosztika": {
            "corp": corp,
            "brier_keszseg": skill,
            "izotonikus_validacion_illesztve": m_iso,
        },
        # korai módban optimista (a korai leállítás is ezt figyelte); cv és
        # rögzített módban tiszta, időn kívüli ellenőrzés. Konfigurációk között
        # a bővülő ablakos CV-n (modellvalasztas) választunk, nem a teszten.
        "validacio": evaluate(yva, p_va),
        "validacio_bazisrata": round(float(yva.mean()), 4),
        "jellemzok": int(X.shape[1]),
        "kizart_jellemzok": drop_cols,
        "ablacio": drop_names,
        # amit a modell ténylegesen látott — ebből ellenőrizhető az abláció
        "jellemzo_nevek": list(model.booster_.feature_name()),
        "sorok": int(len(X)),
    }
    preds = None
    if return_predictions:
        preds = {
            "tanito_arany": train_rate,
            "valid": {"y": yva.to_numpy(), "p": p_va,
                      "ido": meta.loc[sp.valid, "rendeles_idopont"].to_numpy()},
            "teszt": {"y": yte.to_numpy(), "p": p_te,
                      "ido": meta.loc[sp.test, "rendeles_idopont"].to_numpy()},
        }
    if not write_artifacts:
        if preds is not None:
            result["elorejelzesek"] = preds
        return result

    # ------------------------------------------------------------ artefaktum
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    minus = f"_minus-{'+'.join(drop_names)}" if drop_names else ""
    fa = {"korai": "", "cv": "_cv", "rogzitett": f"_n{n_trees}"}[mode]
    tiszt = "_tisztitott" if purge else ""
    out = ARTIFACTS / f"{stamp}_lgbm_{tag}_{balance}{minus}{fa}{tiszt}_seed{seed}"
    out.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, out / "model.joblib")
    # Kalibrátort SZÁNDÉKOSAN nem mentünk: a szállított kimenet a nyers modell.
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
            "megfigyelesi_zarnap": str(prov.get("megfigyelesi_zarnap", "")),
            "kizart_rendelesek": int(prov.get("kizart_rendelesek", 0) or 0),
        },
        "szetvagas": {
            "forras": sp.source,
            "train_vege": str(sp.train_end.date()),
            "valid_vege": str(sp.valid_end.date()),
            "meret": {"train": len(sp.train), "valid": len(sp.valid), "test": len(sp.test)},
        },
        "megbizhatosag_tizedek": rel,
        "megbizhatosag_egyenlo_szelesseg": rel_uniform,
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
    ablacio_sor = (
        f"\n**Ablációs futás** — kizárt jellemzők ({', '.join(drop_names)}): "
        f"{', '.join(drop_cols)}. Ez összehasonlító kísérlet, nem a szállított modell.\n"
        if drop_cols else "")
    drop_arg = f" --drop {','.join(drop_names)}" if drop_names else ""
    trees_arg = "" if mode == "cv" else f" --trees {'korai' if mode == 'korai' else n_trees}"
    purge_arg = "" if purge else " --no-purge"
    tisztitas_sor = (
        f"Címke-tisztítás: csak a vágás előtt lezárult kimenetű tanító sorok "
        f"({len(train_idx):,} tanító sor; {len(sp.train) - len(train_idx):,} kimaradt).\n"
        if purge else "")
    card = f"""# Model card — {stamp}
{figyelmeztetes}
## Mire tanítottuk
Bináris osztályozás: késik-e a rendelés a vállalt határidőhöz képest.
Adat: Olist-alakú tárház ({forras}), {len(X):,} kézbesített rendelés,
{sp.train_end.date()} előtti időszakon tanítva, {n_trees} fával
(a fák száma: {fa_indok}).
Osztálysúlyozás: {balance}.
{tisztitas_sor}{ablacio_sor}
## Jellemzők
{X.shape[1]} mező, mind a rendelés LEADÁSAKOR ismert információból.
Az eladói előzmény-jellemzők as-of illesztéssel készülnek: csak a rendelés
pillanatában már LEZÁRULT korábbi rendelések kimenetét látják.
Tiltólistán: tényleges kézbesítés, feladás dátuma, értékelés, a címke.
A szivárgásteszt minden betanítás előtt lefut.

## Teljesítmény (érintetlen teszthalmaz, {sp.valid_end.date()} utáni időszak)
A kimenet a NYERS modellvalószínűség — utólagos kalibrátor nincs.

| mérőszám | érték |
|---|---|
| PR-AUC | {m_te['pr_auc']} |
| ROC-AUC | {m_te['roc_auc']} |
| Brier | {m_te['brier']} |
| ECE (10 egyenlő szélességű sáv) | {m_te['ece']} |
| ECE (10 egyenlő elemszámú sáv) | {m_te['ece_egyenlo_elemszam']} |

Bázisráta (a késések aránya a teszten): {base_rate:.4f}; a tanító időszakban: {train_rate:.4f}.
Brier-felbontás (CORP): MCB {corp['mcb']}, DSC {corp['dsc']}, UNC {corp['unc']}.
Brier-készség a tanító időszak arányához: {skill['tanito_bazisratahoz']:.1%}.

## Mire NEM használható
* Más webáruházra, más országra, más időszakra — az eladói viselkedés adatfüggő.
* Egyedi rendelés sorsának garantálására: ez valószínűségi becslés.
* Oksági következtetésre: a modell együttjárást tanul, nem okot.

## Ismert korlátok
* Az előrejelzések szinte mind alacsonyak (ritka esemény, gyenge jel): a modell értéke a
  rangsorolásban van, a pontos százalék helyett a relatív kockázat a beszédesebb.
* A teszt időszak alaprátája eltér a tanítóétól (időbeli eltolódás); utólagos kalibrátor
  ezért nincs — egy validáción illesztett izotonikus leképezés rontana.
* Osztálysúlyozással (`--balance balanced`) a nyers valószínűségek erősen torzak; ez az ág
  csak összehasonlításra szolgál.
* Új eladónál az előzmény-jellemzők hiányoznak (NaN); a LightGBM ezt natívan kezeli.
* Egyetlen adathalmaz, egyetlen modellcsalád — az általánosíthatóság korlátozott.

## Reprodukálás
`python -m pipeline.train --seed {seed} --balance {balance}{drop_arg}{trees_arg}{purge_arg}` — determinisztikus beállítással
(`deterministic=True`, `force_row_wise=True`). Környezet: `metrics.json`.
"""
    (out / "model_card.md").write_text(card, encoding="utf-8")
    (ARTIFACTS / "LATEST.txt").write_text(out.name, encoding="utf-8")

    print(f"\nArtefaktumok: {out}")
    result["artifacts"] = str(out)
    if preds is not None:
        result["elorejelzesek"] = preds
    return result


def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="LightGBM baseline betanítása")
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--tag", type=str, default="baseline")
    ap.add_argument("--balance", choices=["none", "balanced"], default="none",
                    help="osztálysúlyozás: none (alapértelmezett) vagy balanced (összevetéshez)")
    # nargs="?": a Windows PowerShell 5.1 az üres ("") argumentumot elhagyja,
    # így egy ciklusban a --drop "" érték nélkül érkezik — az is teljes modell.
    ap.add_argument("--drop", type=str, nargs="?", const="", default="",
                    help="abláció: kizárandó csoportok vagy jellemzők vesszővel, "
                         "pl. honap vagy naptar vagy honap_sin,het_napja")
    ap.add_argument("--trees", type=str, default="cv",
                    help="a fák száma: cv (bővülő ablakos CV a tanító időszakon, "
                         "alapértelmezett — a lezárt protokoll), korai (korai leállítás "
                         "a validáción, a régi út) vagy egy pozitív egész")
    ap.add_argument("--purge", action=argparse.BooleanOptionalAction, default=True,
                    help="címke-tisztítás: csak a vágás előtt lezárult kimenetű tanító sorok "
                         "(alapértelmezett; --no-purge kikapcsolja)")
    a = ap.parse_args()
    try:
        run(a.db, a.seed, a.tag, a.balance, drop=a.drop.split(","),
            trees=a.trees, purge=a.purge)
    except (WarehouseUnavailable, LeakageError, ValueError) as exc:
        print(f"\nHIBA:\n{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
