"""
A kohorsz-érzékenységi jelentés tesztje (okt. 8., témavezetői P2).

A B változat a lejárt határidejű, még úton lévő rendeléseket késettként
hozzáadja; a késési arány így egyik ablakban sem lehet kisebb, mint az A-ban.
"""

from __future__ import annotations

from data.build_warehouse import build
from data.make_synthetic import generate
from pipeline.cohort_report import report, wilson


def test_wilson_intervallum():
    lo, hi = wilson(12, 120)                 # 10% 120 esetből: kb. 5,8–16,7%
    assert 0.057 < lo < 0.059 and 0.166 < hi < 0.168
    lo, hi = wilson(0, 50)
    assert lo == 0.0 and hi > 0


def test_b_valtozat_csak_hozzaad(tmp_path):
    raw = tmp_path / "raw"
    generate(n_orders=3000, seed=7, out_dir=raw, verbose=False)
    db = tmp_path / "w.duckdb"
    s = build(raw, db, verbose=False)
    r = report(db, verbose=False, write=False)
    assert r["hozzaadott_rendelesek_B"] == s["kizart_lejart_uton"] > 0
    tobblet = 0
    for name, w in r["ablakok"].items():
        assert w["B"]["n"] >= w["A"]["n"]
        assert w["B"]["arany"] >= w["A"]["arany"], name
        tobblet += w["B"]["n"] - w["A"]["n"]
    assert tobblet == r["hozzaadott_rendelesek_B"]
