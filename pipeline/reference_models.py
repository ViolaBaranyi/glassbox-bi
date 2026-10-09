"""
Referencia-modellek a LightGBM mellé (rendszerterv: logisztikus regresszió,
döntési fa, random forest — lineáris regresszió nem, mert a feladat bináris).

Miért kellenek?
  1. Megéri-e a LightGBM bonyolultsága? Ha egy egyszerűbb modell ugyanannyit
     tud, az átláthatóbbat kell választani.
  2. A K4 kutatási kérdés (bonyolultság ↔ magyarázat) több bonyolultsági
     szintet kíván: lineáris → egyetlen fa → erdő → gradiens-boosting.
  3. A SHAP-réteg mindegyikre elkészül.

Tisztességes összevetés: ugyanaz az adat-protokoll, mint a lezárt LightGBM-nél
(22 jellemző, időbeli vágás, címke-tisztítás, súlyozás és utólagos kalibrátor
nélkül), és mindegyik modell EGY, a bonyolultságát szabályozó hiperparamétert
kap, amelyet ugyanaz a bővülő ablakos CV választ a tanító időszakon:

    LightGBM             a fák száma          (lezárt: 119)
    logisztikus regr.    C                    a regularizáció (kisebb C = erősebb)
    döntési fa           max_depth            a fa mélysége
    random forest        min_samples_leaf     a levelek legkisebb mérete

Választási szabály: a legnagyobb átlagos PR-AUC a hajtásokon; egyezésnél az
egyszerűbb (a rácsok egyszerűtől a bonyolult felé haladnak). A validációs és
a teszt ablak ebbe nem szól bele.

Az előfeldolgozás közös (a SHAP B-konfigurációjával összhangban): hiányzó
számértékek → medián + hiány-jelző oszlop; kategóriák → one-hot (a 20-nál
ritkább kategóriák összevonva); a logisztikus regressziónál standardizálás is.

Futtatás (csak a tanító időszakot olvassa):
    python -m pipeline.reference_models
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

from data.db import DB_PATH, WarehouseUnavailable, connect, use_utf8_console
from pipeline.features import (BOOLEAN_FEATURES, CATEGORICAL_FEATURES, NUMERIC_FEATURES,
                               LeakageError, build_features, suspicious_features)
from pipeline.split import expanding_cv_folds, settled_before, temporal_split
from pipeline.train import ARTIFACTS, evaluate

SEED = 42
CV_FOLDS = 4
RF_TREES = 300
DT_MIN_LEAF = 50          # a döntési fa leveleinek alsó mérete (rögzített)
RARE_CATEGORY = 20        # ennél ritkább kategóriák összevonva

# A rácsok az egyszerűtől a bonyolult felé haladnak — egyezésnél az első nyer.
MODELS = {
    "logreg": {"nev": "logisztikus regresszió", "param": "C",
               "racs": [0.001, 0.01, 0.1, 1.0]},
    "dontesi_fa": {"nev": "döntési fa", "param": "max_depth",
                   "racs": [3, 4, 5, 6, 8, 10, 12, 15, 20]},
    "random_forest": {"nev": "random forest", "param": "min_samples_leaf",
                      "racs": [100, 30, 10, 5, 2]},
}


# ---------------------------------------------------------------- modellek
def _bool_to_float(X: pd.DataFrame) -> pd.DataFrame:
    X = X.copy()
    for c in BOOLEAN_FEATURES:
        if c in X.columns:
            X[c] = X[c].astype(float)
    return X


def make_model(kind: str, value, seed: int = SEED) -> Pipeline:
    """Egy referencia-modell az előfeldolgozással együtt (sklearn Pipeline)."""
    if kind not in MODELS:
        raise ValueError(f"Ismeretlen referencia-modell: {kind!r} ({', '.join(MODELS)})")
    num_steps = [("hianyzo", SimpleImputer(strategy="median", add_indicator=True))]
    if kind == "logreg":
        num_steps.append(("skala", StandardScaler()))
    pre = ColumnTransformer([
        ("szam", Pipeline(num_steps), NUMERIC_FEATURES + BOOLEAN_FEATURES),
        ("kat", OneHotEncoder(handle_unknown="infrequent_if_exist",
                              min_frequency=RARE_CATEGORY, sparse_output=False),
         CATEGORICAL_FEATURES),
    ])
    if kind == "logreg":
        clf = LogisticRegression(C=float(value), max_iter=5000)
    elif kind == "dontesi_fa":
        clf = DecisionTreeClassifier(max_depth=int(value), min_samples_leaf=DT_MIN_LEAF,
                                     random_state=seed)
    else:
        clf = RandomForestClassifier(n_estimators=RF_TREES, min_samples_leaf=int(value),
                                     max_features="sqrt", n_jobs=-1, random_state=seed)
    return Pipeline([("logikai", FunctionTransformer(_bool_to_float)),
                     ("elofeldolgozas", pre), ("modell", clf)])


def _fold_data(meta, y, train_index, n_folds, purge):
    ts = pd.to_datetime(meta["rendeles_idopont"])
    out = []
    for f in expanding_cv_folds(ts, train_index, n_folds):
        tr = settled_before(f.train, meta["vallalt_hatarido"], f.cut) if purge else f.train
        if y.loc[tr].nunique() == 2 and y.loc[f.valid].nunique() == 2:
            out.append((f, tr))
    if not out:
        raise ValueError("Egyik hajtásban sincs mindkét osztály — a CV nem futtatható.")
    return out


def select(kind: str, X: pd.DataFrame, y: pd.Series, meta: pd.DataFrame,
           train_index: pd.Index, *, n_folds: int = CV_FOLDS, purge: bool = True,
           seed: int = SEED, folds=None) -> dict:
    """A rács minden pontja minden hajtáson; a legjobb átlagos PR-AUC nyer."""
    folds = folds or _fold_data(meta, y, train_index, n_folds, purge)
    spec = MODELS[kind]
    rows = []
    for value in spec["racs"]:
        mets = [evaluate(y.loc[f.valid],
                         make_model(kind, value, seed).fit(X.loc[tr], y.loc[tr])
                         .predict_proba(X.loc[f.valid])[:, 1])
                for f, tr in folds]
        rows.append({"ertek": value, "hajtasok": len(mets),
                     **{k: round(float(np.mean([m[k] for m in mets])), 4) for k in mets[0]}})
    best = max(range(len(rows)), key=lambda i: (rows[i]["pr_auc"], -i))
    return {"modell": kind, "nev": spec["nev"], "param": spec["param"],
            "racs": rows, "valasztott": spec["racs"][best], "cv": rows[best]}


def lightgbm_cv(X, y, meta, train_index, *, n_folds: int = CV_FOLDS, purge: bool = True,
                seed: int = SEED, folds=None) -> dict:
    """A lezárt LightGBM ugyanazokon a hajtásokon, ugyanazzal a maggal — az összevetéshez."""
    from pipeline.model_selection import cross_validate, fit_fixed, model_params
    cv = cross_validate(X, y, meta, train_index, purge=purge, verbose=False)
    folds = folds or _fold_data(meta, y, train_index, n_folds, purge)
    mets = [evaluate(y.loc[f.valid],
                     fit_fixed(model_params(seed), X.loc[tr], y.loc[tr], cv["n_fix"])
                     .predict_proba(X.loc[f.valid])[:, 1])
            for f, tr in folds]
    row = {"ertek": cv["n_fix"], "hajtasok": len(mets),
           **{k: round(float(np.mean([m[k] for m in mets])), 4) for k in mets[0]}}
    return {"modell": "lightgbm", "nev": "LightGBM", "param": "a fák száma",
            "racs": [row], "valasztott": cv["n_fix"], "cv": row}


def compare(X, y, meta, train_index, *, purge: bool = True, seed: int = SEED,
            verbose: bool = True) -> dict:
    """Mind a négy modell ugyanazokon a tisztított hajtásokon (csak a tanító ablak)."""
    folds = _fold_data(meta, y, train_index, CV_FOLDS, purge)
    out = {"lightgbm": lightgbm_cv(X, y, meta, train_index, purge=purge, seed=seed, folds=folds)}
    for kind in MODELS:
        out[kind] = select(kind, X, y, meta, train_index, purge=purge, seed=seed, folds=folds)
    res = {"modszer": "bővülő ablakos CV a tanító időszakon, ugyanazokon a hajtásokon",
           "hajtasok": len(folds), "cimke_tisztitas": bool(purge), "mag": seed,
           "modellek": out}
    if verbose:
        print_compare(res)
    return res


def print_compare(res: dict) -> None:
    print(f"\nREFERENCIA-MODELLEK — bővülő ablakos CV a tanító időszakon "
          f"({res['hajtasok']} hajtás, címke-tisztítás: {'be' if res['cimke_tisztitas'] else 'nincs'}, "
          f"mag {res['mag']})")
    for kind, r in res["modellek"].items():
        if kind == "lightgbm":
            continue
        print(f"\n  {r['nev']} — a rács ({r['param']}):")
        for row in r["racs"]:
            jel = "  ← választott" if row["ertek"] == r["valasztott"] else ""
            print(f"    {r['param']} = {row['ertek']!s:<8} PR-AUC {row['pr_auc']:.4f}   "
                  f"ROC-AUC {row['roc_auc']:.4f}   Brier {row['brier']:.4f}{jel}")
    print("\n  ÖSSZEVETÉS (a hajtások átlaga, a választott beállítással):")
    print(f"    {'modell':<26}{'beállítás':<26}{'PR-AUC':>8}{'ROC-AUC':>9}{'Brier':>9}{'ECE':>8}")
    for kind, r in res["modellek"].items():
        cv = r["cv"]
        beall = f"{r['param']} = {r['valasztott']}"
        print(f"    {r['nev']:<26}{beall:<26}{cv['pr_auc']:>8.4f}{cv['roc_auc']:>9.4f}"
              f"{cv['brier']:>9.4f}{cv['ece']:>8.4f}")


# ---------------------------------------------------------------- parancssor
def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(
        description="Referencia-modellek összevetése bővülő ablakos CV-n "
                    "(csak a tanító időszakot olvassa)")
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--no-purge", action="store_true",
                    help="címke-tisztítás nélkül (a lezárt protokoll szerint be van kapcsolva)")
    a = ap.parse_args()
    try:
        con = connect(a.db, read_only=True)
        X, y, meta = build_features(con)
        forras = str(con.execute("SELECT adatforras FROM meta_build").fetchone()[0])
        con.close()
        sp = temporal_split(meta["rendeles_idopont"])
        gyanus = suspicious_features(X.loc[sp.train], y.loc[sp.train])
        if gyanus:
            raise LeakageError("Gyanúsan jós jellemző(k): "
                               + ", ".join(f"{c} (AUC {v})" for c, v in gyanus))
        print(f"Adatforrás: {forras.upper()} · tanító ablak: {sp.train_end.date()} előtt")
        print("A validációs és a teszt ablakhoz ez a lépés nem nyúl.")
        res = compare(X, y, meta, sp.train, purge=not a.no_purge)
        res["adatforras"] = forras
        out = ARTIFACTS / "referencia_cv.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nMentve: {out}")
    except (WarehouseUnavailable, LeakageError, ValueError) as exc:
        print(f"\nHIBA:\n{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
