"""Két mérőfutás összevetése (tools/k1_futas_osszevetes.py) — a nagyobb modell és a gépváltás
összevetésének eszköze: párosítás, azonos értelmezés, K1 ugyanazzal a kapuval, és hogy a
protokolltól eltérő kóddal futott futással nem számol."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from tests.test_k1_v2_osszevetes import cat, two_runs  # noqa: F401  (a két hamis-modelles futás)

ROOT = Path(__file__).resolve().parent.parent


def _tool():
    spec = importlib.util.spec_from_file_location("k1_futas_osszevetes", ROOT / "tools" / "k1_futas_osszevetes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ket_futas_parositva(two_runs):  # noqa: F811
    pfile, dirs, db, tmp = two_runs
    out = _tool().run(dirs["v4"], dirs["v3"], "A modell", "B modell", pfile, tmp / "ab.md", db_path=db)
    res, checks = out["eredmeny"], out["ellenorzes"]
    assert checks["hibak"] == [] and checks["ujraszamolas"] == []
    fo = res["fo"]
    assert fo["n"] == 3 and fo["v4"]["k"] == 3 and fo["v3"]["k"] == 2 and fo["kulonbseg"] == pytest.approx(1 / 3)
    assert res["egyezes"] == {"kerdesek": 4, "azonos_ertelmezes": 3, "azonos_itelet": 3}
    assert res["K1"]["jelolo"]["a"]["k"] == 0 and res["K1"]["szabad"]["a"]["k"] == 3
    md = (tmp / "ab.md").read_text(encoding="utf-8")
    assert "A = A modell, B = B modell" in md and "| k003 | osszesito |" in md and "✓ ↑ | ≠ |" in md
    assert json.loads((tmp / "ab.json").read_text(encoding="utf-8"))["eredmeny"]["egyezes"]["kerdesek"] == 4


def test_mas_koddal_futott_futassal_nem_szamol(two_runs):  # noqa: F811
    pfile, dirs, db, tmp = two_runs
    head_file = dirs["v3"] / "fej.json"
    head = json.loads(head_file.read_text(encoding="utf-8"))
    head["kod"]["ujjlenyomat"] = "masik_kod"
    head_file.write_text(json.dumps(head), encoding="utf-8")
    with pytest.raises(SystemExit, match="ujjlenyomata"):
        _tool().run(dirs["v4"], dirs["v3"], "A", "B", pfile, tmp / "x.md", db_path=db)


def test_azonos_ertelmezes():
    tool = _tool()
    spec = {"metrika": "forgalom", "bontas": [], "szuro": {}, "rendezes": "ertek_csokkeno", "limit": 10}
    assert tool.same_reading({"spec": spec, "kapu1": "elfogadva"}, {"spec": dict(spec), "kapu1": "elfogadva"})
    assert not tool.same_reading({"spec": spec, "kapu1": "elfogadva"}, {"spec": None, "kapu1": "nem_elerheto"})
    assert tool.same_reading({"spec": None, "kapu1": "nem_elerheto"}, {"spec": None, "kapu1": "nem_elerheto"})
    assert not tool.same_reading({"spec": None, "kapu1": "nem_elerheto"}, {"spec": None, "kapu1": "tul_sok_bontas"})
