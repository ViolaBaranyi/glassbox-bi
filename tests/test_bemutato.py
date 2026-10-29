"""A Kérdezz oldal bemutató módja (ui/bemutato.py): a rögzített modellválaszok fájlja egyezik a
lezárt harmadik kérdéssorral, a visszajátszó kliens pontosan a rögzített kimenetet adja, és a
szabad szöveges út a rögzített válaszokkal hiba nélkül lefut. (Hogy a valódi adaton mind az 50
kérdés ugyanazt az ítéletet, lekérdezést és szöveget adja, mint a mérésben, azt a döntési napló
rögzíti — a valódi adat nem része a tárolónak.)"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

from data.db import connect
from semantic import catalog
from ui import bemutato

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def meta():
    return bemutato.load()


def test_a_rogzitett_valaszok_a_lezart_kerdessorbol(meta):
    recs = meta["valaszok"]
    assert len(recs) == 50 and len({r["id"] for r in recs}) == 50
    assert meta["modell"] == "qwen3.5:4b" and meta["kod"]["verzio"] == "v5"
    qset = tomllib.loads((ROOT / meta["kerdessor"]["fajl"]).read_text(encoding="utf-8"))
    by_id = {q["id"]: q for q in qset["kerdes"]}
    for r in recs:
        assert r["kerdes"] == by_id[r["id"]]["kerdes"]
        assert isinstance(r["urlap"], dict) and "metrika" in r["urlap"]
        assert r["rogzitett"]["kapu1"]


def test_a_bemutato_a_mert_nyelvi_reteggel_fut(meta):
    """Ha a nyelvi réteg (narrative/, semantic/, promptok) megváltozik, a visszajátszás már nem azt
    mutatja, amit a mérés látott: akkor új mérésből újra kell exportálni (tools/bemutato_export.py)."""
    from narrative.client import load_config
    from narrative.meres import frozen_fingerprint
    assert frozen_fingerprint(load_config()) == meta["kod"]["ujjlenyomat"]


def test_a_visszajatszo_kliens_a_rogzitett_kimenetet_adja(meta):
    rec = next(r for r in meta["valaszok"] if r["modell_szoveg"])
    client = bemutato.client_for(rec, meta)
    assert client.status()[0] and client.log_path is None and not client.preload()
    assert json.loads(client.chat("to_spec", [], {}, "x").text) == rec["urlap"]
    reply = client.chat("to_text", [], {}, "x")
    assert json.loads(reply.text) == {"szoveg": rec["modell_szoveg"]}
    assert "rögzített" in reply.model


def test_a_szabad_szoveges_ut_a_rogzitett_valaszokkal_lefut(meta, synth_db):
    cat = catalog.load()
    con = connect(synth_db, read_only=True)
    try:
        wl = catalog.whitelist(cat, con)
        for rec in meta["valaszok"]:
            fa = bemutato.ask(rec, meta, cat, wl, con)
            want = rec["rogzitett"]["kapu1"]
            if want in ("nem_elerheto", "ismeretlen_metrika", "tul_sok_bontas"):  # adattól független
                assert not fa.spec.gate.ok and fa.spec.gate.elutasitas.kod == want
            if fa.ok:
                assert fa.szoveg is not None and fa.szoveg.szoveg
    finally:
        con.close()
