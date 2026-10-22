"""
A második kapu véletlen átcsúszásának mérőeszköze (tools/kapu_atcsuszas.py) — a szintetikus
tárházon, egy kis kérdéssorral.

  * a kitalált szám alakja a megjelenítésé (a), eggyel kevesebb tizedessel (b), „kb.” előtaggal
    (c); sosem az összesített érték alakja;
  * a kapu a nézet egy valódi értékét átengedi, a nagyon távoli számot nem — mindkét ágon;
  * egy kis futás determinisztikus, az arányok 0 és 1 közöttiek, a jelentés elkészül.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import numpy as np
import pytest

from data.db import connect
from semantic import catalog

ROOT = Path(__file__).resolve().parent.parent

SET = '''
[[kerdes]]
id = "k001"
szerzo = "viola"
tipus = "rangsor"
kerdes = "melyik államban a legnagyobb a késési arány?"
metrika = "kesesi_arany"
bontas = ["vevo_allam"]
szuro = {}
tol = ""
ig = ""

[[kerdes]]
id = "k002"
szerzo = "viola"
tipus = "osszesito"
kerdes = "mennyi az átlagos kosárérték?"
metrika = "atlagos_kosarertek"
bontas = []
szuro = {}
tol = ""
ig = ""

[[kerdes]]
id = "k003"
szerzo = "viola"
tipus = "osszesito"
kerdes = "hány rendelés volt?"
metrika = "rendelesek_szama"
bontas = []
szuro = {}
tol = ""
ig = ""

[[kerdes]]
id = "k004"
szerzo = "viola"
tipus = "csapda"
kerdes = "mennyi a haszon?"
elutasitas = "nem_elerheto"
csapda = "nincs_adat"
'''


def _tool():
    spec = importlib.util.spec_from_file_location("kapu_atcsuszas", ROOT / "tools" / "kapu_atcsuszas.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def env(synth_db, tmp_path_factory):
    d = tmp_path_factory.mktemp("atcsuszas")
    (d / "eval").mkdir()
    (d / "eval" / "kis.toml").write_text(SET, encoding="utf-8")
    con = connect(synth_db, read_only=True)
    cat = catalog.load()
    wl = catalog.whitelist(cat, con)
    yield {"ka": _tool(), "con": con, "cat": cat, "wl": wl, "root": d, "sets": ("eval/kis.toml",)}
    con.close()


def _items(env):
    return env["ka"].results(env["cat"], env["wl"], env["con"], env["sets"], env["root"])


def test_a_kitalalt_szam_alakja(env):
    ka = env["ka"]
    items = _items(env)
    assert [i["id"] for i in items] == ["k001", "k002", "k003"]           # a csapda kimarad
    rate, basket, count = (i["eredmeny"] for i in items)
    assert ka.forms_for(rate) == ["a", "b", "c"] and ka.forms_for(count) == ["a"]
    rng = np.random.default_rng(5)
    truth = ka.fmt(rate.metrika, float(rate.osszesen["ertek"]), 1)
    for _ in range(50):
        a, b, c = (ka.draw(rate, f, rng) for f in "abc")
        assert re.fullmatch(r"\d+,\d%", a) and a != truth
        assert re.fullmatch(r"\d+%", b) and c.startswith("kb. ") and re.fullmatch(r"\d+%", c[4:])
    assert re.fullmatch(r"\d+,\d BRL", ka.draw(basket, "b", rng))
    lo, hi = min(ka.metric_values(rate)), max(ka.metric_values(rate))
    vals = [float(ka.draw(rate, "a", rng).rstrip("%").replace(",", ".")) for _ in range(200)]
    assert min(vals) >= 100 * 0.5 * lo - 0.05 and max(vals) <= 100 * 1.5 * hi + 0.05


def test_a_kapu_a_valodi_erteket_atengedi_a_tavolit_nem(env):
    ka = env["ka"]
    from narrative.to_text import build_view
    rate = _items(env)[0]["eredmeny"]
    for mod in ("jelolo", "szabad"):
        view = build_view(rate, placeholders=(mod == "jelolo"), minimal=True)
        shown = next(s for s, path in view.values.values() if path.startswith("sorok[") and path.endswith(".ertek"))
        assert ka.slips(rate, f"Az érték {shown}.", mod)
        assert not ka.slips(rate, "Az érték 987,6%.", mod)


def test_kis_futas_determinisztikus_es_jelentes(env):
    ka = env["ka"]
    items = _items(env)
    r1, r2 = ka.measure(items, k=20), ka.measure(items, k=20)
    assert r1 == r2 and all(0.0 <= x["atcsuszas"] <= 1.0 for x in r1)
    # k001 és k002: 2 ág × 3 alak; k003: 2 ág × 1 alak
    assert len(r1) == 6 + 6 + 2
    s = ka.summarize(r1)
    assert "jelolo|a" in s["osszes"] and "szabad|c" in s["osszes"]
    res = {"letrehozva": "2026-10-22T00:00:00+00:00", "kod_ujjlenyomat": "0" * 64,
           "beallitas": {"K": 20, "mag": ka.SEED, "ci_mag": ka.CI_SEED, "tartomany": [ka.LO, ka.HI],
                         "kerdessorok": list(env["sets"]), "alakok": ka.FORM_NAMES},
           "eredmenyek": len(items), "sorok": r1, "osszegzes": s, "ido_mp": 0.0}
    md = ka.report(json.loads(json.dumps(res, ensure_ascii=False)))
    assert "## Összesen" in md and "## Mértékegység szerint" in md and "arány (%)" in md
