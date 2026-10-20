"""A K1 v2 összevető eszköze (tools/k1_v2_osszevetes.py): két valódi mérőfutás a kis próbasoron
(hamis modellel, a szintetikus tárházon), majd az összevetés — a párosítás, az újraszámolt ítélet,
az újrapontozás önellenőrzése, és hogy a protokolltól eltérő futással nem számol."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from narrative import meres
from narrative.client import load_config
from semantic import catalog
from tests.test_meres import _responder, _small_set
from tests.test_nyelvi_reteg import _env, _is_spec_call, fake_client

ROOT = Path(__file__).resolve().parent.parent


def _tool():
    spec = importlib.util.spec_from_file_location("k1_v2_osszevetes", ROOT / "tools" / "k1_v2_osszevetes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _wrong_for(base, qid_text: str):
    """Ugyanaz a hamis modell, de egy kérdésre rossz mérőszámot ad (a „v3” futás)."""
    def respond(payload):
        out = base(payload)
        if payload.get("messages") and _is_spec_call(payload) and qid_text in payload["messages"][1]["content"]:
            out = {**out, "metrika": "rendelesek_szama"}
        return out
    return respond


@pytest.fixture(scope="module")
def cat():
    return catalog.load()


@pytest.fixture
def two_runs(cat, synth_db, tmp_path, monkeypatch):
    pfile, qfile = _small_set(tmp_path)
    protocol = json.loads(pfile.read_text(encoding="utf-8"))
    fp = meres.frozen_fingerprint(load_config(env=_env()))
    protocol["beallitasok"]["ismetles"] = 1
    protocol["modellek"][1]["nev"] = "probamodell:8b"
    protocol["kod"] = {"verzio": "v4", "ujjlenyomat": fp, "v3": {"ujjlenyomat": fp}}
    protocol["statisztika"]["bootstrap"] = {"B": 200, "mag": 7}
    pfile.write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    meres.lock(pfile)
    meres.approve("Teszt", pfile)
    questions = meres.proba.load_questions(qfile)
    monkeypatch.setattr(meres, "PROTOKOLL", pfile)
    monkeypatch.setattr(meres, "DB_PATH", synth_db)
    monkeypatch.setattr(meres, "load_config", lambda: load_config(env={**_env(), "LLM_MODEL": "qwen3.5:4b"}))
    base = _responder(cat, questions)
    dirs = {}
    for name, responder in (("v4", base), ("v3", _wrong_for(base, "Mennyi az összes forgalom?"))):
        monkeypatch.setattr(meres, "MERES", tmp_path / f"meres_{name}")
        monkeypatch.setattr(meres, "LlmClient", lambda cfg, r=responder: fake_client(r))
        meres.main([])
        dirs[name] = next((tmp_path / f"meres_{name}").iterdir())
    return pfile, dirs, synth_db, tmp_path


def test_az_osszevetes_parosit_es_onmagat_ellenorzi(two_runs):
    pfile, dirs, db, tmp = two_runs
    tool = _tool()
    out = tool.run(dirs["v4"], dirs["v3"], protokoll=pfile, kimenet=tmp / "eredmeny.md", db_path=db)
    checks, res = out["ellenorzes"], out["eredmeny"]
    assert checks["hibak"] == [] and checks["ujraszamolas"] == [] and checks["onellenorzes"] == []
    fo = res["fo"]
    assert fo["n"] == 3 and fo["v4"]["k"] == 3 and fo["v3"]["k"] == 2
    assert (fo["mindketto"], fo["csak_v4"], fo["csak_v3"], fo["egyik_sem"]) == (2, 1, 0, 0)
    assert fo["kulonbseg"] == pytest.approx(1 / 3)
    assert res["F2"]["v4"]["k"] == res["F2"]["v3"]["k"] == 1
    k = res["K1"]["szabad"]
    assert k["v4_szoveg_v4_kapu"]["k"] == 3 and k["v3_szoveg_v4_kapu"]["n"] == 3   # a kontroll szövege a hamis számmal
    assert res["K1"]["jelolo"]["v4_szoveg_v4_kapu"]["k"] == 0
    md = (tmp / "eredmeny.md").read_text(encoding="utf-8")
    assert "## Fő mutató" in md and "| k003 | osszesito |" in md and "✓ ↑" in md
    data = json.loads((tmp / "eredmeny.json").read_text(encoding="utf-8"))
    assert data["eredmeny"]["fo"]["n"] == 3


def test_protokolltol_eltero_futassal_nem_szamol(two_runs):
    pfile, dirs, db, tmp = two_runs
    tool = _tool()
    head_file = dirs["v3"] / "fej.json"
    head = json.loads(head_file.read_text(encoding="utf-8"))
    head["kod"]["ujjlenyomat"] = "masik_kod"
    head_file.write_text(json.dumps(head), encoding="utf-8")
    with pytest.raises(SystemExit, match="ujjlenyomata"):
        tool.run(dirs["v4"], dirs["v3"], protokoll=pfile, kimenet=tmp / "x.md", db_path=db)


def test_a_paros_tabla():
    tool = _tool()
    p = tool.paired({"a": True, "b": True, "c": False, "d": True}, {"a": True, "b": False, "c": False, "e": True},
                    {"B": 100, "mag": 1})
    assert p["n"] == 3 and (p["mindketto"], p["csak_v4"], p["csak_v3"], p["egyik_sem"]) == (1, 1, 0, 1)
    assert p["kulonbseg"] == pytest.approx(1 / 3)
