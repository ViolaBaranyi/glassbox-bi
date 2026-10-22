"""A K1 v3 összevető eszköze (tools/k1_v3_osszevetes.py) és a v4 futás protokollja
(tools/v4_protokoll.py): két valódi mérőfutás a kis próbasoron (hamis modellel, a szintetikus
tárházon) — a „v5” a jóváhagyott protokollal, a „v4” a származtatott változattal —, majd az
összevetés: párosítás, a kód tiszta hatása, önellenőrzés, és hogy a protokolltól eltérő futással
nem számol."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from narrative import meres
from narrative.client import load_config
from semantic import catalog
from tests.test_k1_v2_osszevetes import _wrong_for
from tests.test_meres import _responder, _small_set
from tests.test_nyelvi_reteg import _env, fake_client

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cat():
    return catalog.load()


@pytest.fixture
def runs(cat, synth_db, tmp_path, monkeypatch):
    pfile, qfile = _small_set(tmp_path)
    protocol = json.loads(pfile.read_text(encoding="utf-8"))
    fp = meres.frozen_fingerprint(load_config(env=_env()))
    protocol["beallitasok"]["ismetles"] = 1
    protocol["modellek"][1]["nev"] = "probamodell:8b"
    protocol["kod"] = {"verzio": "v5", "ujjlenyomat": fp, "v4": {"ujjlenyomat": fp}}
    protocol["statisztika"]["bootstrap"] = {"B": 200, "mag": 7}
    pfile.write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    meres.lock(pfile)
    meres.approve("Teszt", pfile)
    v4file = pfile.with_name("k1_protokoll_v4.json")
    v4file.write_text(_load("v4_protokoll").text(json.loads(pfile.read_text(encoding="utf-8"))), encoding="utf-8")
    questions = meres.proba.load_questions(qfile)
    monkeypatch.setattr(meres, "DB_PATH", synth_db)
    monkeypatch.setattr(meres, "load_config", lambda: load_config(env={**_env(), "LLM_MODEL": "qwen3.5:4b"}))
    base = _responder(cat, questions)
    dirs = {}
    for name, responder, pf in (("v5", base, pfile), ("v4", _wrong_for(base, "Mennyi az összes forgalom?"), v4file),
                                ("v4_fo", base, pfile)):
        monkeypatch.setattr(meres, "PROTOKOLL", pf)
        monkeypatch.setattr(meres, "MERES", tmp_path / f"meres_{name}")
        monkeypatch.setattr(meres, "LlmClient", lambda cfg, r=responder: fake_client(r))
        meres.main([])
        dirs[name] = next((tmp_path / f"meres_{name}").iterdir())
    return pfile, dirs, synth_db, tmp_path


def test_az_osszevetes_parosit_es_a_kod_hatasat_kulon_mutatja(runs):
    pfile, dirs, db, tmp = runs
    tool = _load("k1_v3_osszevetes")
    out = tool.run(dirs["v5"], dirs["v4"], protokoll=pfile, kimenet=tmp / "eredmeny.md", db_path=db)
    checks, res = out["ellenorzes"], out["eredmeny"]
    assert checks["hibak"] == [] and checks["ujraszamolas"] == [] and checks["onellenorzes"] == []
    fo = res["fo"]
    assert fo["n"] == 3 and fo["v5"]["k"] == 3 and fo["v4"]["k"] == 2
    assert (fo["mindketto"], fo["csak_v5"], fo["csak_v4"], fo["egyik_sem"]) == (2, 1, 0, 0)
    c = res["kod_hatasa"]
    assert c["mas_urlap"] == 1 and c["mas_urlap_javult"] == 1 and c["azonos_urlap_javult"] == c["azonos_urlap_romlott"] == 0
    assert c["azonos_urlap"] == c["kerdes"] - 1
    assert set(res["szerep_szerint"]) == {"—"}                       # a kis sorban nincs szerep
    md = (tmp / "eredmeny.md").read_text(encoding="utf-8")
    assert "## Fő mutató" in md and "### A kód tiszta hatása" in md and "✓ ↑" in md
    assert json.loads((tmp / "eredmeny.json").read_text(encoding="utf-8"))["eredmeny"]["fo"]["n"] == 3


def test_a_v4_futas_csak_a_szarmaztatott_protokollal_szamit(runs):
    pfile, dirs, db, tmp = runs
    tool = _load("k1_v3_osszevetes")
    with pytest.raises(SystemExit, match="v4-es változatával"):
        tool.run(dirs["v5"], dirs["v4_fo"], protokoll=pfile, kimenet=tmp / "x.md", db_path=db)


def test_mas_kod_ujjlenyomattal_nem_szamol(runs):
    pfile, dirs, db, tmp = runs
    tool = _load("k1_v3_osszevetes")
    head_file = dirs["v4"] / "fej.json"
    head = json.loads(head_file.read_text(encoding="utf-8"))
    head["kod"]["ujjlenyomat"] = "masik_kod"
    head_file.write_text(json.dumps(head), encoding="utf-8")
    with pytest.raises(SystemExit, match="ujjlenyomata"):
        tool.run(dirs["v5"], dirs["v4"], protokoll=pfile, kimenet=tmp / "x.md", db_path=db)


def test_a_v4_protokoll(tmp_path):
    v4p = _load("v4_protokoll")
    p = {"allapot": "jovahagyva", "kod": {"ujjlenyomat": "v5fp", "v4": {"ujjlenyomat": "v4fp"}}, "kerdessor": {"sha256": "q"}}
    d = v4p.derive(p)
    assert d["kod"]["ujjlenyomat"] == "v4fp" and d["kerdessor"] == p["kerdessor"] and p["kod"]["ujjlenyomat"] == "v5fp"
    f = tmp_path / "p.json"
    f.write_bytes(v4p.text(p).replace("\n", "\r\n").encode("utf-8"))                 # Windowson CRLF-fel íródik
    assert meres.sha256_text(f) == v4p.sha256(p) == hashlib.sha256(v4p.text(p).encode()).hexdigest()
