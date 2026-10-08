"""
A heti blokk-bootstrap tesztjei.

  * a hét hétfőn kezdődik (ISO);
  * egy újramintavétel EGÉSZ hetekből áll, és ugyanannyi hétből, mint az eredeti;
  * azonos maggal azonos eredmény; az intervallum tartalmazza a pontbecslést;
  * páros változat: azonos előrejelzésnél a különbség pontosan 0, a jobb
    előrejelzés pedig kimutathatóan nyer.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pipeline.bootstrap import (block_bootstrap, paired_block_bootstrap,
                                resample_indices, week_blocks)


def _adat(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2018-06-04", periods=n, freq="40min")    # kb. 12 hét
    p = rng.beta(1, 15, n)
    y = (rng.random(n) < p).astype(int)
    return ts, y, p


def test_iso_het_hetfon_kezdodik():
    b = week_blocks(pd.to_datetime(
        ["2018-06-03 23:59", "2018-06-04 00:00", "2018-06-10 23:59", "2018-06-11 00:00"]))
    assert list(b) == [201822, 201823, 201823, 201824]


def test_egesz_heteket_huz():
    ts, _, _ = _adat()
    bl = week_blocks(ts)
    teljes = pd.Series(bl).value_counts()
    for idx in resample_indices(bl, B=25, seed=1):
        db = pd.Series(bl[idx]).value_counts()
        assert all(db[k] % teljes[k] == 0 for k in db.index), "egy hetet csak részben húzott"
        assert sum(db[k] // teljes[k] for k in db.index) == len(teljes)


def test_reprodukalhato_es_a_pontbecslest_tartalmazza():
    ts, y, p = _adat()
    bl = week_blocks(ts)
    a = block_bootstrap(y, p, bl, B=300, seed=5)
    assert a == block_bootstrap(y, p, bl, B=300, seed=5)
    for k in ("pr_auc", "roc_auc", "brier"):
        lo, hi = a[k]["ci95"]
        assert lo <= a[k]["ertek"] <= hi
    assert a["_beallitas"]["blokkok"] == len(np.unique(bl))


def test_paros_azonos_elorejelzesnel_nulla():
    ts, y, p = _adat()
    r = paired_block_bootstrap(y, p, p.copy(), week_blocks(ts), B=200)
    for k in ("pr_auc", "roc_auc", "brier", "ece"):
        assert r[k]["kulonbseg"] == 0 and r[k]["ci95"] == [0.0, 0.0]


def test_paros_a_jobb_elorejelzes_nyer():
    ts, y, p = _adat(n=6000)
    r = paired_block_bootstrap(y, p, np.full(len(y), y.mean()), week_blocks(ts), B=300)
    assert r["brier"]["ci95"][1] < 0          # a modell Brier-értéke kisebb
    assert r["pr_auc"]["ci95"][0] > 0         # és jobban rangsorol


def test_egy_het_nem_eleg():
    ts = pd.date_range("2018-06-04", periods=50, freq="h")          # mind ugyanazon a héten
    y = np.r_[np.zeros(45, int), np.ones(5, int)]
    with pytest.raises(ValueError):
        block_bootstrap(y, np.linspace(0, 1, 50), week_blocks(ts), B=10)
