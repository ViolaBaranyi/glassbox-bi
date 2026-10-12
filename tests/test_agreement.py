"""
Az egyezési mértékek tesztjei (xai.agreement) — adat nélkül.

  * a rangsor |érték| szerint csökkenő, egyezésnél a megadott sorrend dönt;
  * az RBO azonos rangsorra 1, szimmetrikus, egyezik a definíció szerinti
    (nem inkrementális) számolással, és a rangsor ELEJÉN lévő csere többet számít;
  * top-k, előjel-egyezés, rel_L1, súlyozott tau és a bootstrap-összegzés.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import pytest

from xai import agreement as ag


def _rbo_definition(r1, r2, p):
    k = len(r1)
    x = [len(set(r1[:d]) & set(r2[:d])) for d in range(1, k + 1)]
    return (x[-1] / k) * p ** k + (1 - p) / p * sum((x[d - 1] / d) * p ** d for d in range(1, k + 1))


def test_rangsor():
    assert ag.ranking([0.1, -3.0, 2.0, 0.0], ["a", "b", "c", "d"]) == ["b", "c", "a", "d"]
    assert ag.ranking([1.0, -1.0, 1.0]) == [0, 1, 2]          # egyezésnél a megadott sorrend


def test_rbo_tulajdonsagai():
    items = list("abcdefghij")
    assert ag.rbo(items, items) == pytest.approx(1.0)
    rng = np.random.default_rng(0)
    for _ in range(50):
        r1, r2 = list(rng.permutation(items)), list(rng.permutation(items))
        v = ag.rbo(r1, r2, 0.9)
        assert v == pytest.approx(_rbo_definition(r1, r2, 0.9))
        assert v == pytest.approx(ag.rbo(r2, r1, 0.9))          # szimmetrikus
        assert 0.0 <= v <= 1.0
    top_swap = ["b", "a"] + items[2:]
    bottom_swap = items[:-2] + ["j", "i"]
    assert ag.rbo(items, top_swap) < ag.rbo(items, bottom_swap) < 1.0
    with pytest.raises(ValueError):
        ag.rbo(items, items[:-1])
    with pytest.raises(ValueError):
        ag.rbo(items, items, p=1.0)


def test_rbo_minden_permutacion_a_definicioval_egyezik():
    items = list("abcd")
    for perm in itertools.permutations(items):
        assert ag.rbo(items, list(perm), 0.9) == pytest.approx(_rbo_definition(items, list(perm), 0.9))


def test_egyszeru_mertekek():
    a = np.array([5.0, -4.0, 3.0, 0.1, 0.0])
    b = np.array([4.0, 3.0, -5.0, 0.0, 0.2])
    assert ag.top_k_overlap(a, a) == 1.0
    assert ag.top_k_overlap(a, b, 3) == 1.0                   # ugyanaz a 3 tényező, más sorrendben
    assert ag.top_k_overlap(a, b, 1) == 0.0                   # a legfontosabb más
    assert ag.sign_agreement(a, b, 3) == pytest.approx(1 / 3)  # csak az első iránya egyezik
    assert ag.rel_l1(a, a) == 0.0
    assert ag.rel_l1(a, b) == pytest.approx(np.abs(a - b).sum() / np.abs(b).sum())
    assert ag.weighted_tau(a, a) == pytest.approx(1.0)
    assert np.isnan(ag.weighted_tau(np.ones(5), a))
    assert ag.rbo_values(a, a) == pytest.approx(1.0)


def test_tablak_osszevetese_es_osszegzes():
    cols = ["x", "y", "z", "w"]
    a = pd.DataFrame([[3, 2, 1, 0], [0, 1, 2, 3]], columns=cols, dtype=float)
    b = pd.DataFrame([[3, 2, 1, 0], [3, 2, 1, 0]], columns=cols, dtype=float)
    t = ag.compare_frames(a, b)
    assert list(t.columns) == list(ag.METRICS)
    assert t.loc[0, "rbo"] == pytest.approx(1.0) and t.loc[1, "rbo"] < 1.0
    s = ag.summary(t, n_boot=200)
    assert s["top3"]["n"] == 2
    lo, hi = s["rbo"]["ci95"]
    assert lo <= s["rbo"]["atlag"] <= hi
    with pytest.raises(ValueError):
        ag.compare_frames(a, b[["y", "x", "z", "w"]])
    assert np.isnan(ag.mean_ci([np.nan])["atlag"])
