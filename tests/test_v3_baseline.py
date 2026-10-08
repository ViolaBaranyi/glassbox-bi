"""
A lezárt v3 alapfutás kapujának tesztjei.

A teszthalmazhoz csak jóváhagyott, hiánytalan, a kóddal egyező protokollal
lehet nyúlni — és csak egyszer: a második futás csak kifejezett kérésre
indul, és az eredményben ez látszik.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from data.build_warehouse import build
from data.make_synthetic import generate
from pipeline import train
from pipeline import v3_baseline as vb

PROTO = Path(__file__).resolve().parent.parent / "docs" / "v3_protokoll.json"


def _jovahagyott(forras="szintetikus", B=100) -> dict:
    p = json.loads(PROTO.read_text(encoding="utf-8"))
    p.update(allapot="jovahagyva", cimke_tisztitas=True)
    p["jovahagyas"] = {"ki": "teszt", "mikor": "2026-10-08", "megjegyzes": None}
    p["adat"]["forras"] = forras
    p["bizonytalansag"]["B"] = B
    p["tanitasi_veletlen"]["magok"] = [1, 2]
    return p


def test_a_tarolt_protokoll_tervezet_ezert_nem_fut():
    p, _ = vb.load_protocol(PROTO)
    with pytest.raises(vb.ProtocolError, match="jovahagyva"):
        vb.check_protocol(p, "valós")


def test_a_tarolt_protokoll_minden_rogzitett_erteke_egyezik_a_koddal():
    """Csak a döntések (jóváhagyás, címke-tisztítás) hiányoznak belőle."""
    p, _ = vb.load_protocol(PROTO)
    p.update(allapot="jovahagyva", cimke_tisztitas=True,
             jovahagyas={"ki": "x", "mikor": "y"})
    vb.check_protocol(p, "valós")


@pytest.mark.parametrize("modositas, minta", [
    (lambda p: p.update(cimke_tisztitas=None), "címke-tisztítás"),
    (lambda p: p["modellvalasztas"].update(n_min=30), "n_min"),
    (lambda p: p["modellvalasztas"].update(magok=[1, 2]), "magok"),
    (lambda p: p["vegso_modell"].update(utolagos_kalibrator=True), "kalibrator"),
    (lambda p: p["ablakok"].update(tanito_vege="2018-04-01"), "tanito_vege"),
    (lambda p: p.update(jovahagyas={"ki": None, "mikor": None}), "jovahagyas.ki"),
    (lambda p: p["tanitasi_veletlen"].update(magok=[1]), "két mag"),
])
def test_hianyos_vagy_a_kodtol_eltero_protokoll(modositas, minta):
    p = _jovahagyott(forras="valós")
    modositas(p)
    with pytest.raises(vb.ProtocolError, match=minta):
        vb.check_protocol(p, "valós")


def test_mas_adatforrason_nem_fut():
    with pytest.raises(vb.ProtocolError, match="adat.forras"):
        vb.check_protocol(_jovahagyott(forras="valós"), "szintetikus")


def test_lezart_futas_egyszer_fut_es_ujjlenyomatot_ment(tmp_path, monkeypatch):
    generate(n_orders=3000, seed=5, out_dir=tmp_path / "raw", verbose=False)
    db = tmp_path / "w.duckdb"
    build(tmp_path / "raw", db, verbose=False)
    monkeypatch.setattr(train, "ARTIFACTS", tmp_path / "artifacts")

    proto = tmp_path / "protokoll.json"
    proto.write_text(json.dumps(_jovahagyott(), ensure_ascii=False), encoding="utf-8")
    out, md = tmp_path / "eredmeny.json", tmp_path / "eredmeny.md"

    r = vb.run_locked(db, proto, out, md)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["protokoll_sha256"] == hashlib.sha256(proto.read_bytes()).hexdigest()
    assert saved["futas"]["ismetles"] is False
    assert saved["vegso_modell"]["fak_szama"] == saved["modellvalasztas"]["n_fix"] >= 50
    assert saved["cimke_tisztitas"]["be"] is True
    b = saved["teszt"]["bootstrap"]["pr_auc"]
    assert b["ci95"][0] <= b["ertek"] <= b["ci95"][1]
    assert len(saved["tanitasi_veletlen"]["futasok"]) == 2
    assert "Lezárt v3 alapfutás" in md.read_text(encoding="utf-8")

    with pytest.raises(vb.LockedRunExists):
        vb.run_locked(db, proto, out, md)
    r2 = vb.run_locked(db, proto, out, md, ismetles=True)
    assert r2["futas"]["ismetles"] is True
    assert r2["teszt"]["bootstrap"]["pr_auc"] == r["teszt"]["bootstrap"]["pr_auc"]
