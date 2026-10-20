"""
A nyelvi réteg v4 szabályai (a v3 lezárt mérése után, 2026-10-20) — valódi nyelvi modell nélkül.
Minden szabály egy, a v3 mérésén látott hibafajtát javít; a v4-et új, előre nem látott
kérdéseken kell mérni (döntési napló).

  * időkifejezések: „félév”, viszonylagos év + negyedév / Q / hónap, ékezet nélkül; az „ideig”
    nem „idei”;
  * földelés: a kérdésben nem említett kategória, „késett / időben” szűrő és időablak elmarad;
    a késési mérőszámoknál a „késett” szűrő fölösleges (nem elutasítás);
  * idősor időrendben; „havonta / évente” → bontás; egyetlen megnevezett érték → szűrő, nem
    bontás; összehasonlításnál bontás; az állam szerepe a neve utáni szóból;
  * elutasítás, ha a kérdés vevőt számol, nem elérhető adatot kér, vagy két bontást egyszerre;
  * a 2. kapu: a szám mértékegység nélkül, a rövid kategórianév, a felsorolás „illetve” nélkül.
"""

from __future__ import annotations

from datetime import date

import pytest

from narrative import to_spec as ts
from narrative import to_text as tt
from narrative import verifier as vf
from narrative.idoszak import mentions_time, parse_window
from semantic import engine
from semantic import spec as sp
from tests.test_nyelvi_reteg import cat, con, form, wl  # noqa: F401  (pytest-kellékek)

MA = date(2018, 9, 1)


# ------------------------------------------------------------------ időkifejezések
@pytest.mark.parametrize("question,tol,ig", [
    ("tavaly negyedik negyedévben mennyi volt a bevétel?", "2017-10-01", "2017-12-31"),
    ("tavalyi év Q3-ban melyik eladói állam küldte a legtöbbet?", "2017-07-01", "2017-09-30"),
    ("tavaly augusztusban mennyi volt?", "2017-08-01", "2017-08-31"),
    ("az idei első negyedévben mennyi volt?", "2018-01-01", "2018-03-31"),
    ("2018 első félévében mennyi volt?", "2018-01-01", "2018-06-30"),
    ("2017 második félév legkisebb államai", "2017-07-01", "2017-12-31"),
    ("2017 Q4-ben mennyi volt?", "2017-10-01", "2017-12-31"),
    ("2017 utolsó negyedévében?", "2017-10-01", "2017-12-31"),
    ("mult évbe hányan késtek?", "2017-01-01", "2017-12-31"),
    ("az elmult 3 honapban?", "2018-06-01", "2018-08-31"),
    ("az elmúlt fél évben?", "2018-03-01", "2018-08-31"),
])
def test_v4_idokifejezesek(question, tol, ig):
    assert parse_window(question, MA).window() == {"tol": tol, "ig": ig}


def test_az_ideig_nem_idei_es_az_idoszo():
    assert parse_window("Szóval mennyi ideig tart, amíg megérkezik?", MA) is None
    assert not mentions_time("Szóval mennyi ideig tart, amíg megérkezik?")
    for q in ("Melyik hónapban volt a legtöbb rendelés?", "Hónapról hónapra hogyan változott?",
              "Mutasd évenkénti bontásban!", "A babatermékeknél hogyan oszlik meg?"):
        assert not mentions_time(q), q                                    # bontás, nem időablak
    for q in ("2018 elején", "17 nyarán", "mostanában", "augusztusban", "a következő hónapban", "jövő év"):
        assert mentions_time(q), q


# ------------------------------------------------------------------ az értelmezés javítása
def _gate(cat, wl, question, **kw):
    q = ts.to_query_spec(form(cat, **kw), cat)
    q, _ = ts.resolve_filters(q, cat, wl)
    fixed, fixes = ts.correct(q, question, cat, wl)
    return sp.check(fixed, cat, wl), fixes


def test_a_nem_emlitett_kategoria_kesettseg_es_idoablak_elmarad(cat, wl):
    g, fixes = _gate(cat, wl, "2017 márciusában hány csomag késett?", metrika="kesett_rendelesek",
                     szuro={"kategoria": ["játékok"]}, tol="2017-03-01", ig="2017-03-31")
    assert g.ok and g.spec.filters == {} and any("kategória" in f.ok for f in fixes)
    g, _ = _gate(cat, wl, "Hány késett rendelés volt a parfümöknél?", metrika="kesett_rendelesek",
                 szuro={"kategoria": ["parfümök"]})
    assert g.ok and g.spec.filters == {"kategoria": ("perfumery",)}               # említi: marad
    g, fixes = _gate(cat, wl, "Melyik régióban a legnagyobb a kosárérték?", metrika="atlagos_kosarertek",
                     bontas=["vevo_regio"], szuro={"kesett": ["időben"]}, tol="2017-09-01")
    assert g.ok and g.spec.filters == {} and g.spec.tol is None
    assert {f.mezo for f in fixes} == {"szuro", "idoablak"}


def test_a_kesett_szuro_a_kesesi_merosszamoknal(cat, wl):
    # fölösleges a késett rendelések számánál — elmarad, nem elutasítás
    g, fixes = _gate(cat, wl, "Hogyan alakult havonta a késett rendelések száma?", metrika="kesett_rendelesek",
                     bontas=["honap"], szuro={"kesett": ["késett"]}, rendezes="bontas", limit=100)
    assert g.ok and g.spec.filters == {} and any("eleve" in f.ok for f in fixes)
    # az időben érkezettekre szűrt késés továbbra is tiltott (a mérési kérdéssor csapdája)
    g, _ = _gate(cat, wl, "Mekkora az átlagos késés az időben kézbesített rendeléseknél?", metrika="atlagos_keses",
                 szuro={"kesett": ["időben"]})
    assert not g.ok and g.elutasitas.kod == "tiltott_kombinacio"
    # a késési arány a késve érkezettek között: értelmetlen — elutasítás marad
    g, _ = _gate(cat, wl, "Mi a késési arány a késve érkezett rendelések között?", metrika="kesesi_arany",
                 szuro={"kesett": ["késett"]})
    assert not g.ok and g.elutasitas.kod == "tiltott_kombinacio"


def test_idosor_idorendben_es_havonta_bontas(cat, wl):
    g, fixes = _gate(cat, wl, "Évről évre nőtt vagy csökkent a kosárérték?", metrika="atlagos_kosarertek",
                     bontas=["ev"], rendezes="ertek_csokkeno", limit=10)
    assert g.spec.rendezes == "bontas" and g.spec.limit == 100 and fixes
    g, _ = _gate(cat, wl, "Melyik hónapban volt a legtöbb rendelés?", metrika="rendelesek_szama", bontas=["honap"])
    assert g.spec.rendezes == "ertek_csokkeno"                                     # felsőfok: marad
    g, fixes = _gate(cat, wl, "Hogyan alakult havonta a forgalom?", metrika="forgalom")
    assert g.spec.bontas == ("honap",) and g.spec.rendezes == "bontas"


def test_egyetlen_megnevezett_ertek_szuro_nem_bontas(cat, wl):
    g, fixes = _gate(cat, wl, "mennyi az átlag kosárérték keddenként az északi régióban?", metrika="atlagos_kosarertek",
                     bontas=["vevo_regio"], szuro={"het_napja": ["kedd"]})
    assert g.spec.bontas == () and g.spec.filters == {"het_napja": ("2",), "vevo_regio": ("N",)}
    g, _ = _gate(cat, wl, "északkeleti régióba mennyi idő alatt érnek ki a csomagok?", metrika="atlagos_szallitasi_ido",
                 bontas=["vevo_regio"])
    assert g.spec.filters == {"vevo_regio": ("NE",)}                               # nem az „Észak”
    g, _ = _gate(cat, wl, "Melyik régióban késnek a legtöbbet északon kívül?", metrika="kesesi_arany",
                 bontas=["vevo_regio"])
    assert g.spec.bontas == ("vevo_regio",)                                        # „melyik”: rangsor


def test_osszehasonlitas_es_az_allam_szerepe(cat, wl):
    g, _ = _gate(cat, wl, "Hétfői napokon több a rendelés mint pénteken?", metrika="rendelesek_szama",
                 szuro={"het_napja": ["hétfő", "péntek"]})
    assert g.spec.bontas == ("het_napja",)
    g, fixes = _gate(cat, wl, "Milyen messze vannak a São Pauló-i eladók a vevőiktől?", metrika="atlagos_tavolsag",
                     szuro={"vevo_allam": ["SP"]})
    assert g.spec.filters == {"elado_allam": ("SP",)}
    g, _ = _gate(cat, wl, "Mekkora a vállalt idő átlaga Amazonasban?", metrika="atlagos_vallalt_ido",
                 szuro={"vevo_allam": ["AM"], "elado_allam": ["AM"]})
    assert g.spec.filters == {"vevo_allam": ("AM",)}


def test_elutasitas_vevoszam_nem_elerheto_adat_ket_bontas(cat, wl):
    g, fixes = _gate(cat, wl, "Melyik államban vannak a vevőink a legtöbben?", metrika="rendelesek_szama",
                     bontas=["vevo_allam"])
    assert not g.ok and fixes[-1].mezo == "elutasitas"
    g, _ = _gate(cat, wl, "Hány rendelést fizettek bankkártyával?", metrika="rendelesek_szama")
    assert not g.ok and g.elutasitas.kod == "nem_elerheto"
    g, _ = _gate(cat, wl, "Bontsd le a forgalmat egyszerre régiók és termékkategóriák szerint!", metrika="forgalom",
                 bontas=["vevo_regio"])
    assert not g.ok and g.elutasitas.kod == "tul_sok_bontas"
    g, _ = _gate(cat, wl, "Mutasd részletesen a forgalmat régiónként!", metrika="forgalom", bontas=["vevo_regio"])
    assert g.ok                                                     # a „részletesen” nem részletfizetés


def test_merosszam_a_nevebol_es_a_butor(cat, wl):
    g, fixes = _gate(cat, wl, "Hónapról hónapra hogyan változott az átlagos szállítási díj?",
                     metrika=ts.NOT_IN_CATALOG, kert="átlagos szállítási díj", bontas=["honap"])
    assert g.ok and g.spec.metrika == "atlagos_szallitasi_dij" and fixes[0].mezo == "metrika"
    assert ts.resolve_value(cat, wl, "kategoria", "bútor")[0] == "furniture_decor"


# ------------------------------------------------------------------ a 2. kapu
@pytest.fixture(scope="module")
def regions(cat, wl, con):
    return engine.run(sp.check({"metrika": "atlagos_tavolsag", "bontas": ["vevo_regio"]}, cat, wl).spec, cat, wl, con)


def test_a_szam_mertekegyseg_nelkul(regions):
    view = tt.build_view(regions, placeholders=False, minimal=True)
    o = next(v for v, path in view.values.values() if path == "osszesen.ertek")          # pl. „601 km”
    n = o.split()[0] if len(o.split()[0]) >= 3 else None
    if n is None:
        pytest.skip("túl rövid szám")
    text = f"Az átlagos távolság {n} kilométer."
    assert not vf.verify(text, text, view.values, [], regions, mod="szabad").fedetlen
    made_up = "Az átlagos távolság 987 kilométer."
    assert vf.verify(made_up, made_up, view.values, [], regions, mod="szabad").fedetlen == ["987"]


def test_rovid_kategorianev_es_felsorolas():
    assert vf.short_alias("lakástextil (ágy, fürdő, asztal)") == "lakástextil"
    assert vf.short_alias("háztartási gépek (2. csoport)") is None             # más kategória neve
    assert vf.short_alias("lakáskomfort (2. csoport)") is None                 # két ilyen rövid alak van
    assert vf.short_alias("São Paulo (SP)") is None


def test_felsorolas_illetve_nelkul(regions):
    r = regions
    view = tt.build_view(r, placeholders=True, minimal=True)
    a, b = r.sorok[0]["megnevezes"], r.sorok[1]["megnevezes"]
    good = f"Utána {a} és {b} következik, {{S1}} és {{S2}} értékkel."
    assert not [p for p in vf.verify(good, good, view.values, [], r).problemak if "sorrend" in p]
    bad = f"Utána {a} és {b} következik, {{S2}} és {{S1}} értékkel."
    assert [p for p in vf.verify(bad, bad, view.values, [], r).problemak if "sorrend" in p]
