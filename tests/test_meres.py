"""
A K1 mérés tesztjei (narrative/meres.py, eval/meresi_kerdessor.toml, docs/k1_protokoll.json),
valódi nyelvi modell nélkül:

  * a mérési kérdéssor formailag érvényes, nem ismétli a fejlesztői próbasort és a prompt
    mintapéldáit, és Claude 80 kérdése megvan (64 megválaszolandó + 16 csapda);
  * az ítélet lista-elvárást (metrika, rendezés, elutasítás) és csonka idősort is kezel;
  * a 2. kapu a számjeggyel leírt csoportértéknél is nézi a kötést (a kontrollágon is);
  * lezárás és jóváhagyás nélkül nem lehet mérni, a sorvég nem változtat az ujjlenyomaton;
  * a mérés végigfut, folytatható, a jelentés és a kézi ellenőrzés mintája elkészül.
"""

from __future__ import annotations

import json
import shutil
import sys
import tomllib
from pathlib import Path

import pytest

from data.db import connect
from narrative import meres, proba
from narrative import to_spec as ts
from narrative import verifier as vf
from narrative.client import load_config
from semantic import catalog, engine
from semantic import spec as sp
from tests.test_nyelvi_reteg import _env, _is_spec_call, fake_client

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "eval" / "meresi_kerdessor.toml"
CLAUDE_80 = "39efd2463ee099f8e69448230b51f14ed0b031c7b467fcc175273ab850a4188e"
# A kérdéssor Viola kérdései előtt szándékosan nincs a gépén (hogy ne igazodjon hozzá) — addig ezek kimaradnak.
needs_gold = pytest.mark.skipif(not GOLD.exists(), reason="a mérési kérdéssor még nincs ezen a gépen")


@pytest.fixture(scope="module")
def cat():
    return catalog.load()


@pytest.fixture(scope="module")
def con(synth_db):
    c = connect(synth_db, read_only=True)
    yield c
    c.close()


@pytest.fixture(scope="module")
def wl(cat, con):
    return catalog.whitelist(cat, con)


def _fold(text: str) -> str:
    return " ".join(text.lower().split())


# ------------------------------------------------------------------ a kérdéssor
@needs_gold
def test_a_meresi_kerdessor_ervenyes(cat):
    questions = proba.load_questions(GOLD)
    assert meres.validate(questions, cat) == []
    mine = [q for q in questions if q["szerzo"] == "claude"]
    assert len(mine) == 80 and sum(bool(q.get("elutasitas")) for q in mine) == 16
    protocol, _ = meres.load_protocol()
    ks = protocol["kerdessor"]
    assert len(questions) == ks["kerdesek"] and sum(bool(q.get("elutasitas")) for q in questions) == ks["csapda"]
    assert {a: sum(q["szerzo"] == a for q in questions) for a in meres.SZERZOK} == ks["szerzok"]
    # minden mérőszám legalább háromszor, minden kérdéstípus és csapda-fajta szerepel
    metrics = [m for q in mine if not q.get("elutasitas") for m in proba._as_list(q["metrika"])]
    assert all(metrics.count(m) >= 3 for m in cat.metrics), {m: metrics.count(m) for m in cat.metrics}
    assert {q["tipus"] for q in mine} == set(meres.TIPUSOK)
    assert {q["csapda"] for q in questions if q.get("csapda")} == set(meres.CSAPDAK)


@needs_gold
def test_claude_kerdesei_nem_valtoztak():
    """Claude 80 kérdésének ujjlenyomata a megírásukkor (2026-10-16, Viola kérdései előtt) —
    a döntési naplóban is. Ha ez elbukik, a kérdések a megírás után megváltoztak."""
    questions = proba.load_questions(GOLD)
    assert meres.author_fingerprint(questions, "claude") == CLAUDE_80
    changed = [dict(q) for q in questions]
    changed.append({"id": "k081", "szerzo": "viola", "kerdes": "?"})
    assert meres.author_fingerprint(changed, "claude") == CLAUDE_80      # a másik szerző nem számít


@needs_gold
def test_a_lezart_kerdessor_nem_valtozott():
    """Ha a protokoll jóváhagyott, a kérdéssor ujjlenyomata a lezáráskorival egyezik (okt. 16.,
    14:25: ce87d85f…) — a lezárás után a kérdéssor nem változhat."""
    protocol, _ = meres.load_protocol()
    if protocol["allapot"] != "jovahagyva":
        pytest.skip("a protokoll még nincs jóváhagyva")
    questions = proba.load_questions(GOLD)
    assert meres.readiness(protocol, questions, meres.sha256_text(GOLD)) == []
    assert protocol["kerdessor"]["sha256"] == "ce87d85fd44038c96f107f6474b4c6cdf1a5978afb88b3bfa6629784a69bc01f"


@needs_gold
def test_a_meresi_kerdessor_nem_ismetli_a_hangolasra_hasznaltakat(cat):
    gold = {_fold(q["kerdes"]) for q in proba.load_questions(GOLD)}
    dev = {_fold(q["kerdes"]) for q in proba.load_questions()}
    examples = {_fold(question) for question, _ in ts.examples(cat)}
    ui = (ROOT / "ui" / "oldalak" / "kerdezz.py").read_text(encoding="utf-8")
    ui_questions = {_fold(m) for m in __import__("re").findall(r"\"([A-ZÁÉÍÓÖŐÚÜŰ][^\"]{8,}\?)\"", ui)}
    assert not gold & dev and not gold & examples and not gold & ui_questions


@needs_gold
def test_a_csapdak_elvart_indoka_a_kapuban(cat, wl):
    """Ha a modell jól tölti ki az űrlapot, a kapu a kérdéssorban várt indokkal utasít el."""
    by_id = {q["id"]: q for q in proba.load_questions(GOLD)}
    forms = {"k065": ts._form(cat, "nem_elerheto", "nyereség"),
             "k067": ts._form(cat, "nem_elerheto", "bankkártyás fizetések"),
             "k072": ts._form(cat, "atlagos_szallitasi_ido", "szállítási idő", tol="2016-03-01", ig="2016-03-31"),
             "k077": ts._form(cat, "atlagos_keses", "átlagos késés", szuro={"kesett": ["idoben"]}),
             "k078": ts._form(cat, "forgalom", "forgalom", ["vevo_regio", "kategoria"])}
    for qid, form in forms.items():
        gate = sp.check(ts.to_query_spec(form, cat), cat, wl)
        assert proba.judge(by_id[qid], gate, cat, wl)[0] == "helyes elutasítás", (qid, gate.elutasitas)


# ------------------------------------------------------------------ az ítélet
def test_ites_listaval_es_csonka_idosorral(cat, wl):
    q = {"id": "x", "kerdes": "?", "metrika": ["atlagos_szallitasi_ido", "median_szallitasi_ido"],
         "bontas": ["honap"], "szuro": {}, "tol": "", "ig": "", "rendezes": ["ertek_csokkeno", "bontas"],
         "teljes": True}
    full = sp.check({"metrika": "median_szallitasi_ido", "bontas": ["honap"], "rendezes": "bontas", "limit": 100}, cat, wl)
    assert proba.judge(q, full, cat, wl, groups=lambda s: 24) == ("helyes", [])
    cut = sp.check({"metrika": "median_szallitasi_ido", "bontas": ["honap"], "rendezes": "bontas", "limit": 10}, cat, wl)
    verdict, diffs = proba.judge(q, cut, cat, wl, groups=lambda s: 24)
    assert verdict == "hibás értelmezés" and diffs == ["csonka sor: 10 csoport látszik a 24-ból"]
    by_value = sp.check({"metrika": "atlagos_szallitasi_ido", "bontas": ["honap"], "rendezes": "ertek_csokkeno",
                         "limit": 1}, cat, wl)
    assert proba.judge(q, by_value, cat, wl, groups=lambda s: 24)[0] == "helyes"   # a csúcs elöl áll
    assert proba.core_ok(q, cut) is True and proba.core_ok({**q, "bontas": []}, cut) is False
    invented = sp.check({"metrika": "median_szallitasi_ido", "bontas": ["honap"], "rendezes": "bontas", "limit": 100,
                         "szuro": {"het_napja": ["1"]}}, cat, wl)
    assert any(d.startswith("szűrő") for d in proba.judge(q, invented, cat, wl)[1])   # a kitalált szűrő hiba
    trap = {"id": "y", "kerdes": "?", "elutasitas": ["nem_elerheto", "adaton_kivuli_idoablak"]}
    out = sp.check({"metrika": "forgalom", "idoablak": {"tol": "2030-01-01", "ig": "2030-12-31"}}, cat, wl)
    assert proba.judge(trap, out, cat, wl)[0] == "helyes elutasítás" and proba.core_ok(trap, out) is None


# ------------------------------------------------------------------ a kötés a leírt számnál
@pytest.fixture(scope="module")
def regions(cat, wl, con):
    g = sp.check({"metrika": "kesesi_arany", "bontas": ["vevo_regio"]}, cat, wl)
    return engine.run(g.spec, cat, wl, con)


def _view(r, placeholders):
    from narrative import to_text as tt
    return tt.build_view(r, placeholders=placeholders, minimal=True)


def test_a_leirt_szam_is_a_sajat_csoportja_mellett(regions):
    r = regions
    view = _view(r, placeholders=False)
    all_shown = [v for v, _ in view.values.values()]
    value_of = {int(path[6:-7]): v for v, path in view.values.values() if path.endswith("].ertek") and path.startswith("sorok[")}
    # két csoport, amelynek az értéke máshol nem szerepel (a 8,4% pl. az összesített tartomány felső határa is)
    i, j = [k for k, v in sorted(value_of.items()) if all_shown.count(v) == 1][:2]
    first, second = r.sorok[i], r.sorok[j]
    shown = {0: value_of[i], 1: value_of[j]}
    good = f"{first['megnevezes']}en a legmagasabb a késési arány ({shown[0]}), utána {second['megnevezes']} ({shown[1]})."
    v = vf.verify(good, good, view.values, [], r, mod="szabad")
    assert not any("értéke, de" in p for p in v.problemak), v.problemak
    swapped = f"{first['megnevezes']}en {shown[1]} a késési arány, {second['megnevezes']} értéke {shown[0]}."
    v = vf.verify(swapped, swapped, view.values, [], r, mod="szabad")
    assert sum("értéke, de" in p for p in v.problemak) == 2, v.problemak
    assert any(p.startswith(f"a(z) {shown[1].rstrip('%')}") for p in v.problemak)
    # a fő ágon a jelölő helyett leírt szám kötését is nézi
    mview = _view(r, placeholders=True)
    text = f"{first['megnevezes']}en {shown[1]} a késési arány."
    assert any("értéke, de" in p for p in vf.verify(text, text, mview.values, [], r).problemak)


def test_ketertelmu_szamot_nem_kot(regions):
    r = regions
    view = _view(r, placeholders=False)
    values = dict(view.values)
    a, b = [k for k, (_, path) in values.items() if path in ("sorok[0].ertek", "sorok[1].ertek")]
    values[b] = (values[a][0], values[b][1])                      # két csoportnak ugyanaz az értéke
    marked, rows, _ = vf.literal_marks(f"{r.sorok[1]['megnevezes']} {values[a][0]}", values, r)
    assert rows == {} and "{" not in marked
    marked, rows, labels = vf.literal_marks("{S1} és 2018 között", view.values, r)
    assert rows == {} and marked == "{S1} és 2018 között"          # a jelölő „1”-e és az évszám nem csoportérték


# ------------------------------------------------------------------ lezárás és jóváhagyás
def _small_set(tmp: Path) -> tuple[Path, Path]:
    """Egy kis, mérhető kérdéssor és protokoll a szintetikus tárházhoz."""
    (tmp / "eval").mkdir(parents=True)
    (tmp / "docs").mkdir()
    qfile = tmp / "eval" / "kis_kerdessor.toml"
    qfile.write_text("""
[[kerdes]]
id = "k001"
szerzo = "claude"
tipus = "rangsor"
kerdes = "Melyik régióban a legnagyobb a késési arány?"
metrika = "kesesi_arany"
bontas = ["vevo_regio"]
szuro = {}
tol = ""
ig = ""
rendezes = "ertek_csokkeno"

[[kerdes]]
id = "k002"
szerzo = "claude"
tipus = "idosor"
kerdes = "Havonta hány rendelés jött?"
metrika = "rendelesek_szama"
bontas = ["honap"]
szuro = {}
tol = ""
ig = ""
rendezes = "bontas"
teljes = true

[[kerdes]]
id = "k003"
szerzo = "viola"
tipus = "osszesito"
kerdes = "Mennyi az összes forgalom?"
metrika = "forgalom"
bontas = []
szuro = {}
tol = ""
ig = ""

[[kerdes]]
id = "k004"
szerzo = "viola"
tipus = "csapda"
csapda = "nincs_adat"
kerdes = "Mekkora a haszon?"
elutasitas = "nem_elerheto"
""", encoding="utf-8")
    protocol = json.loads((ROOT / "docs" / "k1_protokoll.json").read_text(encoding="utf-8"))
    # a valódi protokoll már lezárt és jóváhagyott lehet: a másolat tervezetként indul
    protocol.update({"allapot": "tervezet", "jovahagyas": None})
    protocol["kerdessor"].update({"fajl": str(qfile), "kerdesek": 4, "megvalaszolando": 3, "csapda": 1,
                                  "szerzok": {"claude": 2, "viola": 2}, "sha256": None, "lezarva": None})
    protocol["beallitasok"]["ismetles"] = 2
    protocol["modellek"][1]["nev"] = None                         # a megnevezést a teszt végzi
    pfile = tmp / "docs" / "k1_protokoll.json"
    pfile.write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    return pfile, qfile


def test_lezaras_es_jovahagyas(tmp_path):
    pfile, qfile = _small_set(tmp_path)
    protocol, _ = meres.load_protocol(pfile)
    questions = proba.load_questions(qfile)
    assert "a kérdéssor még nincs lezárva (--lezar)" in meres.readiness(protocol, questions, meres.sha256_text(qfile))
    with pytest.raises(SystemExit, match="lezárni"):
        meres.approve("Baranyi Viola", pfile)
    sha = meres.lock(pfile)
    assert sha == meres.sha256_text(qfile)
    # ugyanaz a tartalom LF és CRLF sorvéggel (Windowson a write_text eleve CRLF-et ír — ezért előbb LF-re)
    lf_bytes = qfile.read_bytes().replace(b"\r\n", b"\n")
    (tmp_path / "lf.toml").write_bytes(lf_bytes)
    (tmp_path / "crlf.toml").write_bytes(lf_bytes.replace(b"\n", b"\r\n"))
    assert meres.sha256_text(tmp_path / "lf.toml") == meres.sha256_text(tmp_path / "crlf.toml") == sha
    with pytest.raises(SystemExit, match="meg kell nevezni"):     # a második modell még nincs megnevezve
        meres.approve("Baranyi Viola", pfile)
    protocol, _ = meres.load_protocol(pfile)
    protocol["modellek"][1]["nev"] = "probamodell:8b"
    pfile.write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    meres.approve("Baranyi Viola", pfile)
    protocol, _ = meres.load_protocol(pfile)
    assert protocol["allapot"] == "jovahagyva" and protocol["jovahagyas"]["ki"] == "Baranyi Viola"
    assert meres.readiness(protocol, questions, sha) == []
    with pytest.raises(SystemExit, match="nem tervezet"):
        meres.lock(pfile)
    qfile.write_text(qfile.read_text(encoding="utf-8").replace("összes forgalom", "teljes forgalom"), encoding="utf-8")
    assert meres.readiness(protocol, proba.load_questions(qfile), meres.sha256_text(qfile)) == \
        ["a kérdéssor megváltozott a lezárás óta (az ujjlenyomat nem egyezik)"]


def test_a_lezaras_ellenorzi_az_osszetetelt(tmp_path):
    pfile, qfile = _small_set(tmp_path)
    protocol = json.loads(pfile.read_text(encoding="utf-8"))
    protocol["kerdessor"]["csapda"] = 2
    pfile.write_text(json.dumps(protocol, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit, match="összetétel"):
        meres.lock(pfile)


# ------------------------------------------------------------------ a mérés végig
def _responder(cat, questions):
    by_text = {q["kerdes"]: q for q in questions}

    def respond(payload):
        if not payload.get("messages"):
            return {}                                              # előtöltés
        system = payload["messages"][0]["content"]
        if not _is_spec_call(payload):
            if "Számjegyet NE írj" in system:
                return {"szoveg": "Az összesített érték {O}."}
            return {"szoveg": "Az összesített érték 999,9 egység, és ez a hétvégi akció hatására alakult így."}
        text = payload["messages"][1]["content"]
        q = next(q for t, q in by_text.items() if f"«{t}»" in text)
        if q.get("elutasitas"):
            return ts._form(cat, "nem_elerheto", "haszon")
        time_like = bool(q["bontas"]) and q["bontas"][0] in ("honap", "ev", "het_napja")
        return ts._form(cat, proba._as_list(q["metrika"])[0], q["kerdes"][:20], q["bontas"], q["szuro"],
                        q["tol"], q["ig"], proba._as_list(q.get("rendezes", "ertek_csokkeno"))[0],
                        q.get("limit", 100 if time_like else 10))
    return respond


def test_a_meres_vegig_es_folytatas(cat, synth_db, tmp_path, monkeypatch, capsys):
    pfile, qfile = _small_set(tmp_path)
    protocol = json.loads(pfile.read_text(encoding="utf-8"))
    protocol["modellek"][1]["nev"] = "probamodell:8b"
    pfile.write_text(json.dumps(protocol, ensure_ascii=False), encoding="utf-8")
    meres.lock(pfile)
    meres.approve("Teszt", pfile)
    questions = proba.load_questions(qfile)
    monkeypatch.setattr(meres, "PROTOKOLL", pfile)
    monkeypatch.setattr(meres, "MERES", tmp_path / "meres")
    monkeypatch.setattr(meres, "DB_PATH", synth_db)
    monkeypatch.setattr(meres, "load_config", lambda: load_config(env=_env()))
    monkeypatch.setattr(meres, "LlmClient", lambda cfg: fake_client(_responder(cat, questions)))
    with pytest.raises(SystemExit):                                # a protokollban nem szereplő modell
        meres.main(["--modell", "masik:1b"])
    assert "nem szerepel a protokollban" in capsys.readouterr().err
    monkeypatch.setattr(meres, "load_config",
                        lambda: load_config(env={**_env(), "LLM_MODEL": "qwen3.5:4b"}))
    meres.main([])
    out = capsys.readouterr().out
    assert "F-1: 100,0% · F-2: 100,0% · K1 fő ág: 0,0% · kontrollág: 100,0%" in out
    run = next((tmp_path / "meres").iterdir())
    rows = meres.read_rows(run)
    assert len(rows) == 8 and {r["ismetles"] for r in rows} == {1, 2}
    first = next(r for r in rows if r["id"] == "k001" and r["ismetles"] == 1)
    assert list(first["agak"]) == ["jelolo", "szabad"]
    assert list(next(r for r in rows if r["id"] == "k001" and r["ismetles"] == 2)["agak"]) == ["szabad", "jelolo"]
    control = first["agak"]["szabad"]
    assert control["fajtak"] == {"fedetlen_szam": 1, "oksag": 1} and control["allitasok"] == 2 and not control["sablon"]
    summary = json.loads((run / "osszegzes.json").read_text(encoding="utf-8"))["osszegzes"]
    assert summary["K1"]["jelolo"]["fo"]["k"] == 0 and summary["K1"]["szabad"]["fo"]["k"] == 6
    assert summary["K1"]["szabad"]["eljut"]["k"] == 6 and summary["K1_paros"]["kulonbseg"] == 1.0
    md = (run / "jelentes.md").read_text(encoding="utf-8")
    assert "| F-1 — helyes mérőszám és bontás | 6/6 = **100,0%**" in md and "## K1" in md
    assert (run / "kezi_ellenorzes.csv").exists() and (run / "kezi_ellenorzes_kulcs.csv").exists()
    sample = (run / "kezi_ellenorzes.csv").read_text(encoding="utf-8-sig")
    assert "jelolo" not in sample and "szabad" not in sample      # vak: az ág a kulcsban van
    # folytatás: nincs hátra semmi; a kód ujjlenyomata nélkül nem folytatható
    meres.main(["--folytat", str(run)])
    assert "hátra: 0" in capsys.readouterr().out and len(meres.read_rows(run)) == 8
    head = json.loads((run / "fej.json").read_text(encoding="utf-8"))
    head["kod"]["ujjlenyomat"] = "mas"
    (run / "fej.json").write_text(json.dumps(head), encoding="utf-8")
    with pytest.raises(SystemExit):
        meres.main(["--folytat", str(run)])
    assert "a nyelvi réteg kódja" in capsys.readouterr().err
    # a jelentés modell nélkül újra
    (run / "jelentes.md").unlink()
    meres.main(["--jelentes", str(run)])
    assert (run / "jelentes.md").exists()
    # a kézi minta újra, a hatókörrel: ugyanaz a kulcs; a kitöltött minta kiértékelése
    import csv
    import importlib.util
    spec = importlib.util.spec_from_file_location("kezi_minta", ROOT / "tools" / "kezi_minta.py")
    km = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(km)
    key_before = (run / "kezi_ellenorzes_kulcs.csv").read_bytes()
    assert km.sample(run) == 12 and (run / "kezi_ellenorzes_kulcs.csv").read_bytes() == key_before
    rows = list(csv.reader((run / "kezi_ellenorzes.csv").open(encoding="utf-8-sig", newline=""), delimiter=";"))
    assert all(r[2].startswith("HATÓKÖR") for r in rows[1:]) and (run / "kezi_ellenorzes_utmutato.txt").exists()
    key = {r[0]: r for r in csv.reader((run / "kezi_ellenorzes_kulcs.csv").open(encoding="utf-8-sig", newline=""), delimiter=";")}
    for r in rows[1:]:
        r[4] = "igen" if key[r[0]][4] == "igen" else "nem"         # a kapu itt mindig igazat mond
    with (run / "kezi_ellenorzes.csv").open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, delimiter=";").writerows(rows)
    with pytest.raises(SystemExit, match="ki van töltve"):
        km.sample(run)                                             # a kitöltöttet nem írja felül
    out = km.evaluate(run)
    assert out["kitoltetlen"] == [] and out["agak"]["szabad"]["pontossag"] == 1.0
    assert out["agak"]["szabad"]["k1_korrigalt"] == 1.0 and out["agak"]["jelolo"]["k1_korrigalt"] == 0.0


def test_lezaratlan_kerdessoron_nem_mer(tmp_path, monkeypatch, capsys):
    pfile, _ = _small_set(tmp_path)
    monkeypatch.setattr(meres, "PROTOKOLL", pfile)
    with pytest.raises(SystemExit) as exc:
        meres.main([])
    assert exc.value.code == 2 and "nincs lezárva" in capsys.readouterr().err


def test_osszegzes_szamai():
    """A statisztika kézzel ellenőrizhető számokon."""
    assert meres.wilson(0, 0) is None
    lo, hi = meres.wilson(8, 10)
    assert round(lo, 3) == 0.490 and round(hi, 3) == 0.943           # a Wilson-intervallum ismert értéke
    mean, lo, hi = meres.bootstrap_mean([1.0] * 5, 200, 1)
    assert mean == lo == hi == 1.0
    assert meres.classify("vissza nem vezethető szám: 3,6") == "fedetlen_szam"
    assert meres.classify("a(z) {S2} „Észak” értéke, de „Dél” mellett áll") == "kotes"
    assert meres.classify("„Dél” nem a legnagyobb érték (az: „Észak”)") == "felsofok"
    assert meres.classify("valami új") == "egyeb"


def test_ez_az_elozo_mondat_csoportjara_utal(regions):
    """A valódi modell szövege (okt. 16., f04): „A számítógépeknél a legnagyobb ({S1}). Ez az
    összesített érték ({O}) 9,0-szerese, utána következik a sütők …” — a 9,0 a számítógépeké."""
    r = regions
    view = _view(r, placeholders=True)
    a, b = r.sorok[0]["megnevezes"], r.sorok[1]["megnevezes"]
    good = f"{a}en a legmagasabb a késési arány ({{S1}}). Ez az összesített érték ({{O}}) {{S1_X}}-szerese, utána {b} ({{S2}}) következik."
    assert not [p for p in vf.verify(good, good, view.values, [], r).problemak if "értéke, de" in p]
    bad = good.replace("{S1_X}", "{S2_X}")
    problems = [p for p in vf.verify(bad, bad, view.values, [], r).problemak if "értéke, de" in p]
    assert problems == [f"a(z) {{S2_X}} „{b}” értéke, de „{a}” értékére utal („ez …”)"]
    alone = f"{a}en a legmagasabb a késési arány ({{S1}}). Ez az összesített érték {{S2_X}}-szerese."
    assert any("értékére utal" in p for p in vf.verify(alone, alone, view.values, [], r).problemak)


def test_elfogadhato_alternativak_es_barmely_idoablak(cat, wl):
    q = {"id": "x", "kerdes": "?", "metrika": "forgalom", "bontas": ["vevo_regio"], "szuro": {"vevo_allam": ["SP"]},
         "tol": "2017-01-01", "ig": "2017-03-31",
         "alternativak": [{"ig": "2017-01-31"}, {"szuro": {"elado_allam": ["SP"]}}]}

    def gate(szuro, ig):
        return sp.check({"metrika": "forgalom", "bontas": ["vevo_regio"], "szuro": szuro,
                         "idoablak": {"tol": "2017-01-01", "ig": ig}}, cat, wl)
    assert proba.judge(q, gate({"vevo_allam": ["SP"]}, "2017-03-31"), cat, wl)[0] == "helyes"
    assert proba.judge(q, gate({"vevo_allam": ["SP"]}, "2017-01-31"), cat, wl)[0] == "helyes"
    assert proba.judge(q, gate({"elado_allam": ["SP"]}, "2017-03-31"), cat, wl)[0] == "helyes"
    # az alternatíva csak a felsorolt mezőt írja felül: az eladói szűrő a januári időablakkal nem jó
    verdict, diffs = proba.judge(q, gate({"elado_allam": ["SP"]}, "2017-01-31"), cat, wl)
    assert verdict == "hibás értelmezés" and any(d.startswith("szűrő") for d in diffs)   # a fő elváráshoz mérve
    free = {k: v for k, v in q.items() if k not in ("tol", "ig", "alternativak")} | {"idoablak": "barmely"}
    assert proba.judge(free, gate({"vevo_allam": ["SP"]}, "2017-02-28"), cat, wl)[0] == "helyes"
    assert proba.core_ok({**q, "metrika": "rendelesek_szama", "alternativak": [{"metrika": "forgalom"}]},
                         gate({"vevo_allam": ["SP"]}, "2017-03-31")) is True
    assert meres.validate([{**q, "szerzo": "viola", "tipus": "kombinalt", "id": "k999",
                            "alternativak": [{"szuro": {"nincs_ilyen": ["x"]}}]}], cat) == \
        ["k999 (1. alternatíva): ismeretlen dimenzió: nincs_ilyen"]


@needs_gold
def test_az_olvashato_valtozat(cat):
    questions = proba.load_questions(GOLD)
    md = meres.readable_md(questions, cat, meres.sha256_text(GOLD))
    assert md.count("\n| k") == len(questions)
    by_id = {q["id"]: q for q in questions}
    assert "**vagy:**" in meres.describe(by_id["k087"], cat) and "bútorok és lakásdekoráció" in meres.describe(by_id["k087"], cat)
    assert meres.describe(by_id["k079"], cat).startswith("**elutasítás** (átverési kísérlet; bármilyen indokkal)")
    assert "időszak: bármely" in meres.describe(by_id["k122"], cat)


def test_a_rogzitett_kod_es_a_masik_protokoll(tmp_path, monkeypatch, capsys):
    """v2-től a protokoll a kód ujjlenyomatát is rögzíti: más kóddal a mérés nem indul; a
    --protokoll kapcsolóval másik protokoll (és kérdéssor) választható."""
    pfile, qfile = _small_set(tmp_path)
    meres.lock(pfile)
    protocol = json.loads(pfile.read_text(encoding="utf-8"))
    protocol["modellek"][1]["nev"] = "probamodell:8b"
    protocol["kod"] = {"verzio": "v4", "ujjlenyomat": "0" * 64}
    pfile.write_text(json.dumps(protocol, ensure_ascii=False), encoding="utf-8")
    meres.approve("Teszt", pfile)
    protocol, _ = meres.load_protocol(pfile)
    questions = proba.load_questions(qfile)
    real = meres.frozen_fingerprint(load_config(env=_env()))
    assert meres.readiness(protocol, questions, meres.sha256_text(qfile), real)[0].startswith("a nyelvi réteg kódja")
    protocol["kod"]["ujjlenyomat"] = real
    assert meres.readiness(protocol, questions, meres.sha256_text(qfile), real) == []
    monkeypatch.setattr(meres, "load_config", lambda: load_config(env=_env()))
    monkeypatch.setattr(meres, "PROTOKOLL", meres.PROTOKOLL)          # a main() átállítja; a teszt végén vissza
    with pytest.raises(SystemExit) as exc:
        meres.main(["--protokoll", str(pfile)])                         # a fájlban még a „0000…” áll
    assert exc.value.code == 2 and "nem a protokollban rögzített" in capsys.readouterr().err
