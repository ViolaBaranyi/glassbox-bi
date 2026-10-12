"""
A négy végső modell — pontosan a lezárt protokollok szerint.

    LightGBM            docs/v3_protokoll.json: a fák száma a lezárt eredményből
                        (docs/v3_lezart_eredmeny.json → 119), címke-tisztítás, mag 42
    logisztikus regr.,  docs/v3_referencia_protokoll.json: a CV-ben választott
    döntési fa,         beállítások (C = 0,1 · mélység 10 · levélméret 10), mag 42
    random forest

Mind a tisztított tanító ablakon tanul, determinisztikusan: ugyanaz az adat és a
kód bitre ugyanazt a modellt adja, mint a lezárt futások.

A betanítás pár tíz másodperc. Az eredményt az artifacts/ alá mentjük, a tárház
építési idejével és a protokollok ujjlenyomatával kulcsolva — ha bármelyik
változik, újratanít, különben betölti (a felület így gyorsan indul).

Szintetikus adaton (CI, tesztek) nincs lezárt eredmény: ott a fa-számot a
bővülő ablakos CV adja, a referencia-modellek a protokoll beállításaival tanulnak.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import pandas as pd

from data.db import DB_PATH, connect
from pipeline import reference_models as rm
from pipeline.features import build_features
from pipeline.split import Split, settled_before, temporal_split

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
CACHE = ROOT / "artifacts" / "v3_modellek.joblib"

KINDS = ("lightgbm", "logreg", "dontesi_fa", "random_forest")
NAMES = {"lightgbm": "LightGBM", "logreg": "logisztikus regresszió",
         "dontesi_fa": "döntési fa", "random_forest": "random forest"}


@dataclass
class Bundle:
    """A modellek és az adat, amin magyarázunk."""
    models: dict
    X: pd.DataFrame
    y: pd.Series
    meta: pd.DataFrame
    split: Split
    train_idx: pd.Index
    info: dict = field(default_factory=dict)

    def background(self, n: int = 500, seed: int = 0) -> pd.DataFrame:
        """Háttérminta a tisztított tanító ablakból (a lineáris SHAP várható értékéhez)."""
        idx = self.train_idx
        if len(idx) > n:
            idx = pd.Index(pd.Series(idx).sample(n, random_state=seed).sort_values())
        return self.X.loc[idx]


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def locked_settings(adatforras: str) -> dict:
    """A lezárt beállítások — valódi adaton a lezárt eredményekből."""
    proto = _read(DOCS / "v3_protokoll.json") or {}
    ref = _read(DOCS / "v3_referencia_protokoll.json") or {}
    locked = _read(DOCS / "v3_lezart_eredmeny.json")
    seed = int((proto.get("vegso_modell") or {}).get("mag", 42))
    purge = bool(proto.get("cimke_tisztitas", True))
    n_trees = None
    if adatforras == "valós" and locked:
        n_trees = int(locked["modellvalasztas"]["n_fix"])
    choices = ref.get("cv_valasztas_elvart") or {"logreg": 0.1, "dontesi_fa": 10,
                                                 "random_forest": 10}
    return {"mag": seed, "cimke_tisztitas": purge, "lightgbm_fak": n_trees,
            "referencia": {k: choices[k] for k in rm.MODELS}}


def _key(build_time: str, settings: dict) -> str:
    h = hashlib.sha256()
    h.update(build_time.encode())
    h.update(json.dumps(settings, sort_keys=True).encode())
    for f in ("v3_protokoll.json", "v3_referencia_protokoll.json"):
        p = DOCS / f
        if p.exists():
            h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def load_bundle(db_path: Path = DB_PATH, use_cache: bool = True,
                cache_path: Path = CACHE, verbose: bool = False) -> Bundle:
    from pipeline.model_selection import cross_validate, fit_fixed, model_params

    con = connect(db_path, read_only=True)
    X, y, meta = build_features(con)
    mb = con.execute("SELECT adatforras, epitve FROM meta_build").fetchone()
    con.close()
    adatforras, epitve = str(mb[0]), str(mb[1])
    sp = temporal_split(meta["rendeles_idopont"])
    settings = locked_settings(adatforras)
    tr = (settled_before(sp.train, meta["vallalt_hatarido"], sp.train_end)
          if settings["cimke_tisztitas"] else sp.train)
    key = _key(epitve, settings)

    if use_cache and Path(cache_path).exists():
        cached = joblib.load(cache_path)
        if cached.get("kulcs") == key:
            return Bundle(cached["modellek"], X, y, meta, sp, tr, cached["info"])

    if verbose:
        print("A négy modell betanítása a lezárt beállításokkal (első indításkor kb. fél perc)…")
    n_trees = settings["lightgbm_fak"]
    if n_trees is None:
        n_trees = cross_validate(X, y, meta, sp.train, purge=settings["cimke_tisztitas"],
                                 verbose=False)["n_fix"]
    models = {"lightgbm": fit_fixed(model_params(settings["mag"]), X.loc[tr], y.loc[tr], n_trees)}
    for kind, val in settings["referencia"].items():
        models[kind] = rm.make_model(kind, val, settings["mag"]).fit(X.loc[tr], y.loc[tr])
    info = {"adatforras": adatforras, "tarhaz_epitve": epitve, "lightgbm_fak": int(n_trees),
            **{k: v for k, v in settings.items() if k != "lightgbm_fak"},
            "tanito_sorok": int(len(tr))}
    if use_cache:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"kulcs": key, "modellek": models, "info": info}, cache_path)
    return Bundle(models, X, y, meta, sp, tr, info)
