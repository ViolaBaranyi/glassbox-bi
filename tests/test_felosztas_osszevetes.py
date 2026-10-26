"""
Időbeli vagy véletlen felosztás (tools/felosztas_osszevetes.py) — szintetikus adaton.

  * a felső 10% és a mérőszámok kézzel számolt példán;
  * a felosztások mérete, diszjunktsága és determinizmusa; az időrendi belső ellenőrzés csak a
    vágásig eldőlt címkéken tanul;
  * egy kis futás: minden változat és modell megvan, a sejtések számlálói 0 és R közöttiek, a
    jelentés elkészül; próbafutás nem írhat a docs/ mappába.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def fo():
    spec = importlib.util.spec_from_file_location("felosztas_osszevetes", ROOT / "tools" / "felosztas_osszevetes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_meroszamok_kezzel(fo):
    y = np.array([1, 0, 0, 1, 0, 0, 0, 0, 0, 1] * 2, dtype=float)       # 20 sor, 6 késés
    p = np.linspace(1, 0, 20)                                             # az első kettő a felső 10%
    assert fo.top_share_capture(y, p) == pytest.approx(1 / 6)             # a 2 sorból 1 késett
    m = fo.metrics(y, np.full(20, 0.3))
    assert m["bazis"] == pytest.approx(0.3) and m["kalibracio_pp"] == pytest.approx(0.0)
    assert m["roc_auc"] == pytest.approx(0.5) and m["emeles"] == pytest.approx(1.0)
    assert m["n"] == 20


def test_a_felosztasok(fo, synth_bundle):
    b = synth_bundle
    tr, ev = fo.random_full_split(b, 0)
    tr2, ev2 = fo.random_full_split(b, 0)
    assert (tr == tr2).all() and (ev == ev2).all()
    assert len(tr) == len(b.train_idx) and len(ev) == len(b.split.test)
    assert not set(tr) & set(ev) and set(tr) | set(ev) <= set(b.X.index)
    assert not (fo.random_full_split(b, 1)[0] == tr).all()
    itr, iev = fo.random_inner_split(b, 0)
    assert not set(itr) & set(iev) and set(itr) | set(iev) == set(b.train_idx)
    assert len(iev) == round(fo.INNER_FRAC * len(b.train_idx))
    ctr, cev, cut = fo.chrono_inner_split(b)
    ts = pd.to_datetime(b.meta["rendeles_idopont"])
    assert (ts.loc[ctr] < cut).all() and (ts.loc[cev] >= cut).all()
    promised = pd.to_datetime(b.meta["vallalt_hatarido"]).loc[ctr]
    assert ((promised + pd.Timedelta(days=1)) <= cut).all()               # csak eldőlt címke
    assert set(cev) <= set(b.train_idx)


def test_kis_futas_es_jelentes(fo, synth_bundle, tmp_path):
    res = fo.run(synth_bundle, kinds=("lightgbm", "logreg"), r=2, verbose=False)
    out = res["eredmenyek"]
    for v in ("II", "III_ben", "III_kivul"):
        assert all(len(out[v][k]) == 2 for k in ("lightgbm", "logreg"))
    assert set(out["I"]) == set(out["IIIb"]) == {"lightgbm", "logreg"}
    e = res["osszegzes"]["sejtesek"]
    assert all(0 <= n <= 2 for n in list(e["E1_II"].values()) + list(e["E1_III"].values()))
    assert 0 <= e["E2"]["nagyobb"] <= 2
    md = fo.report(res)
    assert "## LightGBM" in md and "## Az előre rögzített sejtések" in md and "E3" in md
    with pytest.raises(SystemExit):
        fo.main(["--ismetlesek", "2"])                                    # próbafutás a docs/-ba: tilos
