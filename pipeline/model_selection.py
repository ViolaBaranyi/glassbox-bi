"""
M2 — Modellválasztás bővülő ablakos keresztvalidációval (útiterv T5).

Miért nem a validációs ablak dönt a fák számáról?
  Eddig a korai leállítás a validációs ablakon (2018. márc.–máj.) figyelte a
  PR-AUC-t, és az döntötte el, hány fa legyen. Ebben az ablakban azonban éles
  rendszerváltás van (március 19,0% késés → április 4,5%), és egyetlen ablak
  alapján választani kockázatos: a 10. lelet szerint a validáció itt rossz
  modellt is választott volna. Ezért a fák számát a TANÍTÓ időszakon belül
  választjuk, a validációs és a teszt ablak érintése nélkül:

    1. bővülő ablakos CV — 4 hajtás; mindegyik a saját vágása előtti időszakon
       tanul, és a rákövetkező szakaszon értékel, korai leállítással (PR-AUC,
       150 kör türelem);
    2. 3 maggal megismételve → 12 „legjobb iteráció";
    3. a végső fa-szám:   N_fix = max(N_MIN, medián(legjobb iterációk))
       a medián a kiugró hajtásoktól véd, az alsó korlát az összeomló korai
       leállítástól (egy ablációs futásban egyszer 2 fánál állt meg);
    4. minden hajtás újra, PONTOSAN N_fix fával — ez a rögzített fa-szám
       teljesítménye a tanító időszakon belül (ezen lehet konfigurációk között
       választani, a teszt helyett);
    5. a végső modell a tanító ablakon tanul, pontosan N_fix fával: a
       validációs ablak semmit nem befolyásol, időn kívüli ellenőrzés lesz.

Címke-tisztítás (--purge; a lezárt futásnál a protokoll dönt):
  minden vágásnál csak azok a tanító sorok maradnak, amelyeknek a vállalt
  határideje a vágás előtt lejárt — ezeknek a kimenete akkor már biztosan
  eldőlt. Részletek: split.settled_before.

Futtatás (csak a tanító időszakot olvassa):
    python -m pipeline.model_selection
    python -m pipeline.model_selection --purge
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from data.db import DB_PATH, WarehouseUnavailable, connect, use_utf8_console
from pipeline.features import LeakageError, build_features, suspicious_features
from pipeline.split import expanding_cv_folds, settled_before, temporal_split
from pipeline.train import ARTIFACTS, EARLY_STOPPING_ROUNDS, PARAMS, evaluate

N_MIN = 50            # alsó korlát a fa-számra (útiterv T5; konzultáción megerősítendő)
CV_FOLDS = 4
CV_SEEDS = (1, 2, 3)


# ------------------------------------------------------------------ szabály
def fixed_tree_count(best_iters, n_min: int = N_MIN) -> int:
    """N_fix = max(n_min, a legjobb iterációk mediánja, felfelé kerekítve ,5-nél)."""
    vals = np.asarray(list(best_iters), dtype=float)
    if vals.size == 0:
        raise ValueError("Nincs legjobb iteráció: a keresztvalidáció egy hajtást sem futtatott.")
    med = float(np.median(vals))
    return max(int(n_min), int(np.floor(med + 0.5)))


# ------------------------------------------------------------- illesztések
def model_params(seed: int, balance: str = "none") -> dict:
    if balance not in ("none", "balanced"):
        raise ValueError(f"Ismeretlen balance érték: {balance!r}")
    params = dict(PARAMS, random_state=seed)
    params["class_weight"] = "balanced" if balance == "balanced" else None
    return params


def fit_early_stopping(params: dict, Xtr, ytr, Xva, yva):
    """Korai leállítás az értékelő halmazon (PR-AUC). Visszaad: (modell, legjobb iteráció)."""
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
    return model, int(model.best_iteration_ or params["n_estimators"])


def fit_fixed(params: dict, Xtr, ytr, n_trees: int):
    """Pontosan n_trees fa, értékelő halmaz és korai leállítás nélkül."""
    n_trees = int(n_trees)
    if n_trees < 1:
        raise ValueError(f"A fák száma legalább 1 kell legyen, nem {n_trees}.")
    model = lgb.LGBMClassifier(**dict(params, n_estimators=n_trees))
    model.fit(Xtr, ytr)
    return model


# ------------------------------------------------------- keresztvalidáció
def cross_validate(X: pd.DataFrame, y: pd.Series, meta: pd.DataFrame,
                   train_index: pd.Index, *, seeds=CV_SEEDS, n_folds: int = CV_FOLDS,
                   n_min: int = N_MIN, purge: bool = False, balance: str = "none",
                   verbose: bool = True) -> dict:
    """
    Bővülő ablakos CV a `train_index` sorain (a tanító ablakon) — más sort nem olvas.
    Visszaad: a hajtások adatai, a legjobb iterációk, a medián és az N_fix.
    """
    ts = pd.to_datetime(meta["rendeles_idopont"])
    folds = expanding_cv_folds(ts, train_index, n_folds)

    prepared = []
    for k, f in enumerate(folds, start=1):
        tr = settled_before(f.train, meta["vallalt_hatarido"], f.cut) if purge else f.train
        usable = y.loc[tr].nunique() == 2 and y.loc[f.valid].nunique() == 2
        prepared.append((k, f, tr, usable))

    best = []                      # (hajtás, mag, legjobb iteráció)
    for k, f, tr, usable in prepared:
        if not usable:
            continue
        for s in seeds:
            _, it = fit_early_stopping(model_params(s, balance),
                                       X.loc[tr], y.loc[tr], X.loc[f.valid], y.loc[f.valid])
            best.append((k, s, it))
    if not best:
        raise ValueError("A keresztvalidáció egyik hajtásban sem futhatott "
                         "(mindegyikben csak egy osztály volt).")

    iters = [it for _, _, it in best]
    n_fix = fixed_tree_count(iters, n_min)
    med = float(np.median(iters))

    hajtasok = []
    for k, f, tr, usable in prepared:
        entry = {
            "hajtas": k,
            "tanitas_vege": str(f.cut.date()),
            "ertekeles": [str(f.cut.date()), str((f.valid_end - pd.Timedelta(days=1)).date())],
            "tanito_sorok": int(len(tr)),
            "tanito_sorok_tisztitas_elott": int(len(f.train)),
            "ertekelo_sorok": int(len(f.valid)),
            "ertekelo_keses_arany": round(float(y.loc[f.valid].mean()), 4),
            "hasznalhato": bool(usable),
        }
        if usable:
            entry["legjobb_iteraciok"] = {str(s): it for kk, s, it in best if kk == k}
            mets = []
            for s in seeds:
                m = fit_fixed(model_params(s, balance), X.loc[tr], y.loc[tr], n_fix)
                mets.append(evaluate(y.loc[f.valid], m.predict_proba(X.loc[f.valid])[:, 1]))
            entry["rogzitett_fa_szammal"] = {
                key: round(float(np.mean([m[key] for m in mets])), 4) for key in mets[0]}
        hajtasok.append(entry)

    result = {
        "modszer": "bővülő ablakos keresztvalidáció a tanító időszakon belül",
        "hajtasok_szama": len(folds),
        "magok": [int(s) for s in seeds],
        "korai_leallitas_kor": EARLY_STOPPING_ROUNDS,
        "kiegyensulyozas": balance,
        "cimke_tisztitas": bool(purge),
        "legjobb_iteraciok": iters,
        "median": med,
        "n_min": int(n_min),
        "n_fix": int(n_fix),
        "also_korlat_dontott": bool(med < n_min),
        "hajtasok": hajtasok,
    }
    if verbose:
        print_cv(result)
    return result


def print_cv(res: dict) -> None:
    print(f"\nMODELLVÁLASZTÁS — bővülő ablakos CV a tanító időszakon belül "
          f"({res['hajtasok_szama']} hajtás × {len(res['magok'])} mag)")
    print("  címke-tisztítás: " + ("BE — csak a vágás előtt lezárult kimenetű tanító sorok"
                                   if res["cimke_tisztitas"] else "nincs"))
    seeds = "/".join(str(s) for s in res["magok"])
    print(f"  {'hajtás':<7}{'tanul -ig':<12}{'értékel':<26}{'tanító':>8}{'értékelő':>10}"
          f"{'késés':>8}   {'legjobb iter. (mag ' + seeds + ')':<30}{'PR-AUC':>8}{'ROC-AUC':>9}")
    for h in res["hajtasok"]:
        if not h["hasznalhato"]:
            print(f"  {h['hajtas']:<7}{h['tanitas_vege']:<12}— kihagyva (egy osztály)")
            continue
        its = " / ".join(str(v) for v in h["legjobb_iteraciok"].values())
        m = h["rogzitett_fa_szammal"]
        print(f"  {h['hajtas']:<7}{h['tanitas_vege']:<12}"
              f"{h['ertekeles'][0] + ' .. ' + h['ertekeles'][1]:<26}"
              f"{h['tanito_sorok']:>8,}{h['ertekelo_sorok']:>10,}{h['ertekelo_keses_arany']:>8.2%}"
              f"   {its:<30}{m['pr_auc']:>8.4f}{m['roc_auc']:>9.4f}")
    dontott = "  (az alsó korlát döntött)" if res["also_korlat_dontott"] else ""
    print(f"  medián: {res['median']:g} → N_fix = max({res['n_min']}, {res['median']:g}) "
          f"= {res['n_fix']} fa{dontott}")
    print(f"  (a PR-AUC / ROC-AUC oszlop: minden hajtás újratanítva pontosan {res['n_fix']} "
          "fával, a magok átlaga)")


# ---------------------------------------------------------------- parancssor
def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(
        description="Fa-szám választása bővülő ablakos keresztvalidációval "
                    "(csak a tanító időszakot olvassa)")
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--purge", action="store_true",
                    help="címke-tisztítás: csak a vágás előtt lezárult kimenetű tanító sorok")
    ap.add_argument("--balance", choices=["none", "balanced"], default="none")
    a = ap.parse_args()
    try:
        con = connect(a.db, read_only=True)
        X, y, meta = build_features(con)          # a névszűrő itt fut
        forras = str(con.execute("SELECT adatforras FROM meta_build").fetchone()[0])
        con.close()
        sp = temporal_split(meta["rendeles_idopont"])
        gyanus = suspicious_features(X.loc[sp.train], y.loc[sp.train])
        if gyanus:
            raise LeakageError("Gyanúsan jós jellemző(k): "
                               + ", ".join(f"{c} (AUC {v})" for c, v in gyanus))
        print(f"Adatforrás: {forras.upper()} · tanító ablak: {sp.train_end.date()} előtt, "
              f"{len(sp.train):,} rendelés")
        print("A validációs és a teszt ablakhoz ez a lépés nem nyúl.")
        res = cross_validate(X, y, meta, sp.train, purge=a.purge, balance=a.balance)
        res["adatforras"] = forras
        out = ARTIFACTS / ("modellvalasztas_tisztitott.json" if a.purge else "modellvalasztas.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nMentve: {out}")
    except (WarehouseUnavailable, LeakageError, ValueError) as exc:
        print(f"\nHIBA:\n{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
