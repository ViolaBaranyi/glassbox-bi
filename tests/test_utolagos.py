"""
Az utólagos, leíró eszközök: a késés és az értékelés együttjárása (tools/ertekeles_osszevetes.py)
és a K1 kézi ellenőrzésének bizonytalansága (tools/k1_kezi_intervallum.py).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ev = _load("ertekeles_osszevetes")
ki = _load("k1_kezi_intervallum")


def _reviews():
    orders = pd.DataFrame({"order_key": ["a", "b", "c", "d"], "kesett": [True, True, False, False]})
    reviews = pd.DataFrame({
        "review_id": ["r1", "r2", "r3", "r4", "r5", "r6"],
        "order_id": ["a", "a", "b", "c", "d", "x"],          # az „x” nincs a tárházban
        "review_score": [1, 4, 2, 5, 3, 1],
        "review_creation_date": ["2018-01-01", "2018-01-05", "2018-01-02", "2018-01-03", "2018-01-04", "2018-01-01"],
    })
    return orders, reviews


def test_ertekeles_fo_szabaly_rendelesenkent_atlagol():
    res = ev.compare(*_reviews())
    assert res["ertekelt_rendelesek"] == 4 and res["tobb_ertekeles"] == 1
    k = res["szabalyok"]["atlag"]["kesett"]
    # a: átlag 2,5 (nem alacsony), b: 2 (alacsony)
    assert k["n"] == 2 and k["alacsony_k"] == 1 and k["atlag"] == pytest.approx(2.25)
    assert res["szabalyok"]["atlag"]["idoben"]["alacsony_k"] == 0


def test_ertekeles_erzekenysegi_szabalyok():
    s = ev.compare(*_reviews())["szabalyok"]
    assert s["ertekelesenkent"]["kesett"]["n"] == 3 and s["ertekelesenkent"]["kesett"]["alacsony_k"] == 2
    assert s["elso"]["kesett"]["alacsony_k"] == 2          # a: az első értékelés 1 csillag
    assert s["utolso"]["kesett"]["alacsony_k"] == 1        # a: az utolsó 4 csillag
    assert s["barmelyik"]["kesett"]["alacsony_k"] == 2
    lo, hi = s["atlag"]["kesett"]["ci95"]
    assert 0 <= lo <= 0.5 <= hi <= 1


def test_k1_intervallum_pontbecsles_a_kepletekkel():
    agak = {"jelolo": {"megjelolt_arany": 0.4, "pontossag": {"k": 8, "n": 10}, "kihagyas": {"k": 5, "n": 20}},
            "szabad": {"megjelolt_arany": 0.5, "pontossag": {"k": 9, "n": 10}, "kihagyas": {"k": 6, "n": 20}}}
    p = ki.point(agak)
    assert p["jelolo_eljut"] == pytest.approx(0.6 * 0.25)
    assert p["szabad_k1"] == pytest.approx(0.5 * 0.9 + 0.5 * 0.3)
    assert p["kulonbseg"] == pytest.approx(0.6 - 0.15) and p["hanyados"] == pytest.approx(0.25)
    d = ki.run_draws(agak, np.random.default_rng(1), 20_000)
    assert np.all((d["jelolo_eljut"] >= 0) & (d["jelolo_eljut"] <= 0.6))
    assert abs(np.median(d["szabad_k1"]) - p["szabad_k1"]) < 0.03


def test_k1_intervallum_a_tarolt_kezi_ellenorzesen():
    src = json.loads((ROOT / "docs" / "k1_kezi_ellenorzes.json").read_text(encoding="utf-8"))
    a, b = ki.analyze(src, draws=5000), ki.analyze(src, draws=5000)
    assert a == b                                           # rögzített mag: determinisztikus
    for r, s in zip(a["futasok"], src["futasok"]):
        assert r["jelolo_eljut"]["becsles"] == pytest.approx(s["agak"]["jelolo"]["eljut_fedetlen"]["becsles"])
        assert r["szabad_k1"]["becsles"] == pytest.approx(s["agak"]["szabad"]["k1_korrigalt"])
        for k in ki.KEYS:
            lo, hi = r[k]["ci95"]
            assert lo <= hi
    stored = ROOT / "docs" / "k1_kezi_intervallum.json"
    if stored.exists():                                     # a tárolt eredmény az eszköz kimenete
        old, new = json.loads(stored.read_text(encoding="utf-8")), ki.analyze(src)
        for r_old, r_new in zip(old["futasok"] + [old["osszevont"]], new["futasok"] + [new["osszevont"]]):
            for k in ki.KEYS:
                assert r_old[k]["becsles"] == pytest.approx(r_new[k]["becsles"], abs=1e-12)
                assert r_old[k]["ci95"] == pytest.approx(r_new[k]["ci95"], abs=1e-9)
