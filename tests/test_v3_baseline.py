"""
A lezárt v3 alapfutás kapujának tesztjei.

A teszthalmazhoz csak jóváhagyott, hiánytalan, a kóddal egyező és COMMITOLT
protokollal lehet nyúlni — és csak egyszer: a második futás csak kifejezett
kérésre indul, és az eredményben ez látszik. Az ujjlenyomat nem függ attól,
hogy a fájl Windowson (CRLF) vagy Linuxon (LF) van kicsekkolva.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from data.build_warehouse import build
from data.make_synthetic import generate
from pipeline import train
from pipeline import v3_baseline as vb

PROTO = Path(__file__).resolve().parent.parent / "docs" / "v3_protokoll.json"


@pytest.fixture(autouse=True)
def _git_ne_keressen_felfele(tmp_path_factory, monkeypatch):
    """
    A tesztek ideiglenes mappái „nem git-tárolók" — akkor is, ha egy felsőbb mappa az
    (pl. a felhasználói mappában is van egy .git: Windowson a Temp a felhasználói mappa
    alatt van, így a git azt a tárolót találná meg). A git a pytest ideiglenes gyökerénél
    feljebb nem keres (GIT_CEILING_DIRECTORIES; a git-hívások öröklik a környezetet).
    """
    base = tmp_path_factory.getbasetemp()
    # Windowson mindkét írásmóddal (C:/… és C:\…), az elválasztó ott „;" — Linuxon a kettő ugyanaz
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", os.pathsep.join(dict.fromkeys([base.as_posix(), str(base)])))


def _jovahagyott(forras="szintetikus", B=100) -> dict:
    p = json.loads(PROTO.read_text(encoding="utf-8"))
    p.update(allapot="jovahagyva", cimke_tisztitas=True)
    p["jovahagyas"] = {"ki": "teszt", "mikor": "2026-10-08", "megjegyzes": None}
    p["adat"]["forras"] = forras
    p["bizonytalansag"]["B"] = B
    p["tanitasi_veletlen"]["magok"] = [1, 2]
    return p


def test_tervezet_protokollal_nem_fut():
    p, _ = vb.load_protocol(PROTO)
    p["allapot"] = "tervezet"
    with pytest.raises(vb.ProtocolError, match="jovahagyva"):
        vb.check_protocol(p, "valós")


def test_a_jovahagyott_protokoll_hianytalan_es_egyezik_a_koddal():
    """
    A tárolt protokoll jóvá van hagyva, minden döntése ki van töltve, és pontosan
    azt írja le, amit a kód csinál. Ha valaki a kódban utólag átírja pl. az alsó
    korlátot vagy a magokat, ez a teszt elbukik — a jóváhagyott protokoll védett.
    """
    p, _ = vb.load_protocol(PROTO)
    assert p["allapot"] == "jovahagyva" and p["cimke_tisztitas"] is True
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


def test_az_ujjlenyomat_nem_fugg_a_sorvegtol(tmp_path):
    szoveg = json.dumps(_jovahagyott(), ensure_ascii=False, indent=2)
    (tmp_path / "lf.json").write_bytes(szoveg.encode("utf-8"))
    (tmp_path / "crlf.json").write_bytes(szoveg.replace("\n", "\r\n").encode("utf-8"))
    p1, h1 = vb.load_protocol(tmp_path / "lf.json")
    p2, h2 = vb.load_protocol(tmp_path / "crlf.json")
    assert p1 == p2 and h1 == h2


@pytest.mark.skipif(shutil.which("git") is None, reason="nincs git")
def test_git_allapot(tmp_path):
    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                       cwd=tmp_path, check=True, capture_output=True)
    f = tmp_path / "protokoll.json"
    assert vb.git_state(f)["git"] is False                  # még nincs tároló
    git("init", "-q")
    f.write_text("{}", encoding="utf-8")
    assert vb.git_state(f)["protokoll_commitolva"] is False  # követetlen
    git("add", "protokoll.json")
    git("commit", "-q", "-m", "jovahagyva")
    s = vb.git_state(f)
    assert s["protokoll_commitolva"] and s["munkapeldany_tiszta"] and s["commit"]
    f.write_text('{"x": 1}', encoding="utf-8")
    s = vb.git_state(f)
    assert not s["protokoll_commitolva"] and not s["munkapeldany_tiszta"]


@pytest.fixture(scope="module")
def synth_db(tmp_path_factory):
    d = tmp_path_factory.mktemp("v3")
    generate(n_orders=3000, seed=5, out_dir=d / "raw", verbose=False)
    build(d / "raw", d / "w.duckdb", verbose=False)
    return d / "w.duckdb"


def test_commitolatlan_protokollal_nem_fut(synth_db, tmp_path):
    proto = tmp_path / "protokoll.json"            # a tmp_path nem git-tároló (lásd fent)
    proto.write_text(json.dumps(_jovahagyott(), ensure_ascii=False), encoding="utf-8")
    with pytest.raises(vb.ProtocolError, match="commitolni"):
        vb.run_locked(synth_db, proto, tmp_path / "e.json", tmp_path / "e.md")
    assert not (tmp_path / "e.json").exists()


def test_lezart_futas_egyszer_fut_es_ujjlenyomatot_ment(synth_db, tmp_path, monkeypatch):
    monkeypatch.setattr(train, "ARTIFACTS", tmp_path / "artifacts")
    proto = tmp_path / "protokoll.json"
    proto.write_text(json.dumps(_jovahagyott(), ensure_ascii=False), encoding="utf-8")
    out, md = tmp_path / "eredmeny.json", tmp_path / "eredmeny.md"

    r = vb.run_locked(synth_db, proto, out, md, require_committed=False)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["protokoll_sha256"] == hashlib.sha256(proto.read_bytes()).hexdigest()
    assert saved["futas"]["ismetles"] is False
    assert saved["futas"]["commit_nelkul_engedve"] is True
    assert saved["vegso_modell"]["fak_szama"] == saved["modellvalasztas"]["n_fix"] >= 50
    assert saved["cimke_tisztitas"]["be"] is True
    b = saved["teszt"]["bootstrap"]["pr_auc"]
    assert b["ci95"][0] <= b["ertek"] <= b["ci95"][1]
    assert len(saved["tanitasi_veletlen"]["futasok"]) == 2
    assert "Lezárt v3 alapfutás" in md.read_text(encoding="utf-8")

    with pytest.raises(vb.LockedRunExists):
        vb.run_locked(synth_db, proto, out, md, require_committed=False)
    r2 = vb.run_locked(synth_db, proto, out, md, ismetles=True, require_committed=False)
    assert r2["futas"]["ismetles"] is True
    assert r2["teszt"]["bootstrap"]["pr_auc"] == r["teszt"]["bootstrap"]["pr_auc"]
