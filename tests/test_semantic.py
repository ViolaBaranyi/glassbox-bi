"""
A szemantikus réteg tesztjei (semantic/ — metrikakatalógus, KAPU ①, SQL-építő, MetricResult,
sablonos válasz) és a Kérdezz oldal — szintetikus tárházon.

  * a katalógus betölthető, és a hibás katalógust a betöltés elutasítja;
  * a fehérlista az adatból készül; az írásmódok („Sao Paulo”, „délkelet”, „hétfő”) a
    kanonikus kódra fordulnak;
  * a KAPU ① minden elutasítási kódja előáll, és elutasításnál nincs szám;
  * a kész SQL egyetlen SELECT, a guard minden mást elutasít, az értékek idézése helyes;
  * a MetricResult számai egyeznek egy független pandas-számolással;
  * a sablonos válasz minden száma visszavezethető a payloadra (a KAPU ② előfutára);
  * az ábrák minden rétegének magyar súgója van; az oldal hiba nélkül végigkattintható.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
import sqlglot

from data.db import connect
from pipeline.cohort_report import wilson
from semantic import answer as ans
from semantic import builder, catalog, engine
from semantic import spec as sp
from semantic.catalog import CatalogError
from ui import backend as be
from ui import charts
from xai import labels

APP = Path(__file__).resolve().parent.parent / "ui" / "app.py"


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


def _run(raw, cat, wl, con) -> engine.MetricResult:
    gate = sp.check(raw, cat, wl)
    assert gate.ok, gate.elutasitas
    return engine.run(gate.spec, cat, wl, con, gate.megjegyzesek)


def _grid(cat):
    """Minden mérőszám bontás nélkül és minden megengedett bontással."""
    for m in cat.metrics.values():
        yield {"metrika": m.id}
        for d in cat.dimensions.values():
            if d.id not in m.tiltott_dimenzio:
                yield {"metrika": m.id, "bontas": [d.id]}


# ---------------------------------------------------------------- katalógus
def test_a_katalogus_betoltheto_es_teljes(cat):
    assert len(cat.metrics) >= 10 and len(cat.dimensions) >= 8
    assert re.fullmatch(r"[0-9a-f]{64}", cat.sha256)
    for m in cat.metrics.values():
        assert m.nev and m.leiras and m.egyseg in catalog.UNITS
        if m.is_rate:
            assert m.szamlalo
    for d in cat.dimensions.values():
        assert d.szerint and d.rovid and d.nev
    assert {u for x in cat.unavailable for u in x.helyette} <= set(cat.metrics)
    assert not cat.dimensions["kategoria"].termeszetes_sorrend


def test_a_regiok_egyeznek_az_allamtablaval(cat, con):
    """A katalógus régió-CASE-e ugyanazt adja, mint a felület államtáblája (xai.labels)."""
    codes = sorted(labels.STATES)
    sql = cat.dimensions["vevo_regio"].sql
    rows = con.execute(f"SELECT c.allam, {sql} FROM (SELECT unnest(?) AS allam) AS c", [codes]).fetchall()
    assert len(rows) == 27
    for code, region in rows:
        assert region == labels.STATES[code][1], code


BROKEN = [
    ('egyseg = "arany"', 'egyseg = "szazalek"', "ismeretlen egység"),
    ('szamlalo = "sum(CASE WHEN f.kesett THEN 1 ELSE 0 END)"', "", "kötelező a „szamlalo”"),
    ('sql = "avg(f.kosar_ertek)"', 'sql = "avg(f.kosar_ertek"', "nem értelmezhető"),
    ('tiltott_dimenzio = ["kesett"]', 'tiltott_dimenzio = ["kesve"]', "ismeretlen tiltott dimenzió"),
    ('helyette = ["rendelesek_szama"]', 'helyette = ["keszlet"]', "nincs a katalógusban"),
    ('id = "ev"', 'id = "honap"', "már foglalt"),
    ('ertekek = "ido"\nszurheto = false\ntipus = "egesz"', 'ertekek = "ido"\nszurheto = true\ntipus = "egesz"',
     "nem szűrhető"),
    ('kapcsolat = "dim_seller"', 'kapcsolat = "dim_elado"', "ismeretlen kapcsolat"),
]


@pytest.mark.parametrize("old,new,msg", BROKEN)
def test_a_hibas_katalogust_a_betoltes_elutasitja(tmp_path, old, new, msg):
    text = catalog.KATALOGUS.read_text(encoding="utf-8")
    assert old in text, old
    p = tmp_path / "k.toml"
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(CatalogError, match=msg):
        catalog.load(p)


# ---------------------------------------------------------------- fehérlista
def test_a_feherlista_az_adatbol_keszul(cat, con, wl):
    states = [r[0] for r in con.execute(
        "SELECT DISTINCT c.allam FROM fact_orders f JOIN dim_customer c USING (customer_key) ORDER BY 1"
    ).fetchall()]
    assert list(wl.values["vevo_allam"]) == states
    lo, hi = con.execute("SELECT min(date_key), max(date_key) FROM fact_orders").fetchone()
    assert (wl.date_min, wl.date_max) == (lo, hi)
    assert wl.values["vevo_regio"] == ("N", "NE", "CO", "SE", "S")          # rögzített lista
    assert "honap" not in wl.values and "ev" not in wl.values               # időbeli: időablak szűr
    assert wl.source == "szintetikus"


@pytest.mark.parametrize("dim,raw,key", [
    ("vevo_allam", "SP", "SP"), ("vevo_allam", "sp", "SP"), ("vevo_allam", "Sao Paulo", "SP"),
    ("vevo_allam", "São Paulo (SP)", "SP"), ("vevo_allam", "  são   paulo ", "SP"),
    ("vevo_regio", "délkelet", "SE"), ("vevo_regio", "Delkelet", "SE"), ("vevo_regio", "N", "N"),
    ("het_napja", "hétfő", "1"), ("het_napja", 7, "7"), ("het_napja", "Vasarnap", "7"),
    ("kesett", "késett", "kesett"), ("kesett", "időben érkezett", "idoben"),
    ("vevo_allam", "Sao Pablo", None), ("vevo_allam", "AC", None),        # AC nincs a szintetikus adatban
])
def test_az_irasmodok_a_kanonikus_kodra_fordulnak(cat, wl, dim, raw, key):
    assert catalog.normalize_value(cat, wl, dim, raw) == key


def test_a_kategoria_magyar_neve_is_elfogadott(cat, wl):
    key = wl.values["kategoria"][0]
    assert catalog.normalize_value(cat, wl, "kategoria", labels.category_name(key)) == key


# -------------------------------------------------------------------- KAPU ①
def test_a_kapu_normalizal_es_kitolti_az_alapertekeket(cat, wl):
    raw = json.dumps({"metrika": "kesesi_arany", "bontas": "vevo_allam",
                      "szuro": {"vevo_regio": ["Dél", "délkelet", "SE"], "het_napja": [2, "hétfő"]},
                      "idoablak": {"tol": "2010-01-01", "ig": "2018-03-31"}}, ensure_ascii=False)
    gate = sp.check(raw, cat, wl)
    assert gate.ok and gate.status == "elfogadva"
    s = gate.spec
    assert s.bontas == ("vevo_allam",)
    assert s.szuro == (("het_napja", ("1", "2")), ("vevo_regio", ("SE", "S")))   # fehérlista-sorrend
    assert s.tol is None and s.ig == date(2018, 3, 31)          # az eleje az adat elejére szűkült
    assert gate.megjegyzesek == ("idoablak_szukitve",)
    assert (s.rendezes, s.limit) == ("ertek_csokkeno", cat.settings["alap_limit"])
    assert sp.check(s.to_dict(), cat, wl).spec == s            # a normalizált alak fixpont


def test_idobeli_bontasnal_idorend_es_minden_csoport(cat, wl):
    for dim in ("honap", "ev", "het_napja"):
        s = sp.check({"metrika": "forgalom", "bontas": [dim]}, cat, wl).spec
        assert (s.rendezes, s.limit) == ("bontas", cat.settings["max_limit"])


REJECTIONS = [
    ({}, "hianyzo_metrika"),
    ({"metrika": 5}, "formatum"),
    ("ez nem JSON", "formatum"),
    ([1, 2], "formatum"),
    ({"metrika": "kesesi_arany", "sql": "DROP TABLE fact_orders"}, "ismeretlen_mezo"),
    ({"metrika": "haszonkulcs", "bontas": ["elado_allam"]}, "nem_elerheto"),
    ({"metrika": "vásárlói elégedettség"}, "nem_elerheto"),
    ({"metrika": "kesesi_arani"}, "ismeretlen_metrika"),
    ({"metrika": "kesesi_arany", "bontas": ["varos"]}, "ismeretlen_bontas"),
    ({"metrika": "kesesi_arany", "bontas": ["vevo_allam", "kategoria"]}, "tul_sok_bontas"),
    ({"metrika": "kesesi_arany", "bontas": ["kesett"]}, "tiltott_kombinacio"),
    ({"metrika": "atlagos_keses", "szuro": {"kesett": ["kesett"]}}, "tiltott_kombinacio"),
    ({"metrika": "kesesi_arany", "szuro": {"honap": ["2018-01"]}}, "nem_szurheto"),
    ({"metrika": "kesesi_arany", "szuro": {"varos": ["x"]}}, "ismeretlen_szuro"),
    ({"metrika": "kesesi_arany", "szuro": {"vevo_allam": []}}, "ures_szuro"),
    ({"metrika": "kesesi_arany", "szuro": {"vevo_allam": ["SP"] * 31}}, "tul_sok_ertek"),
    ({"metrika": "kesesi_arany", "szuro": {"vevo_allam": ["Sao Pablo"]}}, "ismeretlen_ertek"),
    ({"metrika": "kesesi_arany", "szuro": "SP"}, "formatum"),
    ({"metrika": "kesesi_arany", "idoablak": {"tol": "2018-13-01"}}, "ervenytelen_datum"),
    ({"metrika": "kesesi_arany", "idoablak": {"tol": "2018-05-01", "ig": "2018-01-01"}}, "forditott_idoablak"),
    ({"metrika": "kesesi_arany", "idoablak": {"tol": "2019-01-01"}}, "adaton_kivuli_idoablak"),
    ({"metrika": "kesesi_arany", "idoablak": {"from": "2018-01-01"}}, "formatum"),
    ({"metrika": "kesesi_arany", "rendezes": "veletlen"}, "ervenytelen_rendezes"),
    ({"metrika": "kesesi_arany", "bontas": ["kategoria"], "rendezes": "bontas"}, "ervenytelen_rendezes"),
    ({"metrika": "kesesi_arany", "limit": 0}, "ervenytelen_limit"),
    ({"metrika": "kesesi_arany", "limit": 101}, "ervenytelen_limit"),
    ({"metrika": "kesesi_arany", "limit": True}, "ervenytelen_limit"),
    ({"metrika": "kesesi_arany", "limit": "5"}, "ervenytelen_limit"),
]


@pytest.mark.parametrize("raw,kod", REJECTIONS)
def test_a_kapu_indokolt_elutasitasai(cat, wl, raw, kod):
    gate = sp.check(raw, cat, wl)
    assert not gate.ok and gate.spec is None
    assert gate.elutasitas.kod == kod, gate.elutasitas
    assert len(gate.elutasitas.uzenet) > 20 and gate.status == f"elutasítva ({kod})"


def test_az_elutasitas_javasol_es_nem_mond_szamot(cat, wl, synth_db):
    gate = sp.check({"metrika": "haszonkulcs"}, cat, wl)
    assert gate.elutasitas.javaslatok == ("atlagos_kosarertek", "atlagos_szallitasi_dij")
    assert "beszerzési ár" in gate.elutasitas.uzenet
    assert sp.check({"metrika": "kesesi_arani"}, cat, wl).elutasitas.javaslatok[0] == "kesesi_arany"
    typo = sp.check({"metrika": "kesesi_arany", "szuro": {"vevo_allam": ["Sao Pablo"]}}, cat, wl)
    assert typo.elutasitas.javaslatok[0] == "SP" and "São Paulo (SP)" in typo.elutasitas.uzenet
    g, result, answer = be.ask({"metrika": "haszonkulcs"}, synth_db)
    assert not g.ok and result is None and answer is None


# -------------------------------------------------------- SQL-építő és guard
def test_minden_kerdesbol_egyetlen_ellenorzott_select_lesz(cat, wl):
    n = 0
    for raw in _grid(cat):
        built = builder.build(sp.check(raw, cat, wl).spec, cat)
        for sql, dialect in ((built.total, "duckdb"), (built.groups, "duckdb"),
                             (built.total_pg, "postgres"), (built.groups_pg, "postgres")):
            if sql is None:
                continue
            trees = sqlglot.parse(sql, read=dialect)
            assert len(trees) == 1 and isinstance(trees[0], sqlglot.exp.Select)
            n += 1
    assert n > 150


@pytest.mark.parametrize("sql", [
    "DROP TABLE fact_orders",
    "SELECT count(*) AS ertek FROM fact_orders AS f; DROP TABLE fact_orders",
    "DELETE FROM fact_orders",
    "INSERT INTO fact_orders SELECT * FROM fact_orders",
    "UPDATE fact_orders SET kesett = true",
    "COPY fact_orders TO 'ki.csv'",
    "ATTACH 'masik.duckdb' AS m",
    "PRAGMA database_list",
    "SET threads = 1",
    "CREATE TABLE x AS SELECT 1",
    "SELECT count(*) AS ertek FROM read_csv('olist_customers_dataset.csv')",
    "SELECT count(*) AS ertek FROM information_schema.tables",
    "SELECT count(*) AS ertek FROM fact_orders AS f WHERE f.order_key IN (SELECT order_key FROM fact_orders)",
    "SELECT f.allam AS bontas FROM fact_orders AS f UNION SELECT s.allam FROM dim_seller AS s",
    "SELECT x.order_key AS ertek FROM fact_orders AS f",
    "SELECT order_key AS ertek FROM fact_orders AS f",
    "SELECT count(*) AS ertek INTO uj FROM fact_orders AS f",
])
def test_a_guard_mindent_elutasit_ami_nem_a_katalogusbol_jon(cat, sql):
    with pytest.raises(builder.UnsafeSQL):
        builder.guard(sql, cat)


def test_az_ertekek_idezese_helyes(cat, con):
    """Ha egy érték valahogy átjutna a kapun, akkor is csak szöveg-literál lesz belőle."""
    evil = "x' OR '1'='1"
    spec = sp.QuerySpec(metrika="rendelesek_szama", szuro=(("vevo_allam", (evil,)),))
    built = builder.build(spec, cat)
    assert "'x'' OR ''1''=''1'" in built.total
    assert con.execute(built.total).fetchone()[1] == 0          # nincs találat — nem „mind igaz”


def test_rogzitett_listanal_a_katalogus_sorrendje(cat, wl, con):
    r = _run({"metrika": "rendelesek_szama", "bontas": ["vevo_regio"], "rendezes": "bontas"}, cat, wl, con)
    order = list(cat.dimensions["vevo_regio"].ertekek)
    keys = [row["kulcs"] for row in r.sorok]
    assert keys == sorted(keys, key=order.index)
    assert "CASE" in r.sql["bontas"].split("ORDER BY")[1] and "CASE" in r.sql_postgres["bontas"].split("ORDER BY")[1]


# ---------------------------------------------------------------- eredmény
@pytest.fixture(scope="module")
def facts(con):
    """Független viszonyítás: a tények a dimenziókkal, pandasban (nem a katalógus SQL-jéből)."""
    d = con.execute("""
        SELECT f.*, c.allam AS vevo_allam, s.allam AS elado_allam, p.kategoria
        FROM fact_orders f
        LEFT JOIN dim_customer c ON f.customer_key = c.customer_key
        LEFT JOIN dim_seller s ON f.seller_key = s.seller_key
        LEFT JOIN dim_product p ON f.product_key = p.product_key""").df()
    d["szallitas_nap"] = (d["kezbesites_datuma"] - d["rendeles_idopont"]).dt.total_seconds() / 86400
    d["keses_nap"] = (d["kezbesites_datuma"].dt.normalize() - pd.to_datetime(d["vallalt_hatarido"])).dt.days
    d["vallalt_nap"] = (pd.to_datetime(d["vallalt_hatarido"]) - pd.to_datetime(d["date_key"])).dt.days
    d["vevo_regio"] = d["vevo_allam"].map(lambda c: labels.STATES[c][1])
    d["ev"] = pd.to_datetime(d["date_key"]).dt.year.astype(str)
    d["het_napja"] = (pd.to_datetime(d["date_key"]).dt.dayofweek + 1).astype(str)
    d["honap"] = pd.to_datetime(d["date_key"]).dt.to_period("M").dt.start_time.dt.date.astype(str)
    return d


REFERENCE = {
    "rendelesek_szama": lambda g: len(g),
    "kesett_rendelesek": lambda g: int(g["kesett"].sum()),
    "kesesi_arany": lambda g: g["kesett"].mean(),
    "atlagos_szallitasi_ido": lambda g: g["szallitas_nap"].mean(),
    "median_szallitasi_ido": lambda g: g["szallitas_nap"].median(),
    "atlagos_vallalt_ido": lambda g: g["vallalt_nap"].mean(),
    "atlagos_keses": lambda g: g.loc[g["kesett"], "keses_nap"].mean() if g["kesett"].any() else None,
    "atlagos_kosarertek": lambda g: g["kosar_ertek"].astype(float).mean(),
    "forgalom": lambda g: g["kosar_ertek"].astype(float).sum(),
    "atlagos_szallitasi_dij": lambda g: g["szallitasi_dij"].astype(float).mean(),
    "atlagos_tavolsag": lambda g: g["tavolsag_km"].mean(),
}


def _close(a, b) -> bool:
    if a is None or b is None or (isinstance(b, float) and pd.isna(b)):
        return a is None and (b is None or pd.isna(b))
    return a == pytest.approx(b, rel=1e-9, abs=1e-12)


def test_minden_szam_egyezik_a_fuggetlen_pandas_szamolassal(cat, wl, con, facts):
    assert set(REFERENCE) == set(cat.metrics)
    checked = 0
    for raw in _grid(cat):
        r = _run(raw, cat, wl, con)
        ref = REFERENCE[raw["metrika"]]
        assert _close(r.osszesen["ertek"], ref(facts)), raw
        assert r.osszesen["rendelesek"] == len(facts)
        if not raw.get("bontas"):
            continue
        dim = raw["bontas"][0]
        col = {"kesett": facts["kesett"].map({True: "kesett", False: "idoben"})}.get(dim, facts[dim])
        expected = {str(k): g for k, g in facts.groupby(col)}
        assert {row["kulcs"] for row in r.sorok} == set(expected), raw
        for row in r.sorok:
            g = expected[row["kulcs"]]
            assert _close(row["ertek"], ref(g)), (raw, row)
            assert row["rendelesek"] == len(g)
            checked += 1
    assert checked > 300


def test_szurt_es_idoablakos_kerdes(cat, wl, con, facts):
    states = list(wl.values["vevo_allam"][-3:])
    r = _run({"metrika": "atlagos_szallitasi_ido", "bontas": ["kategoria"],
              "szuro": {"vevo_allam": states}, "idoablak": {"tol": "2017-06-01", "ig": "2017-12-31"}},
             cat, wl, con)
    dk = pd.to_datetime(facts["date_key"])
    sub = facts[facts["vevo_allam"].isin(states) & (dk >= "2017-06-01") & (dk <= "2017-12-31")]
    assert r.osszesen["rendelesek"] == len(sub) > 0
    assert _close(r.osszesen["ertek"], sub["szallitas_nap"].mean())
    for row in r.sorok:
        g = sub[sub["kategoria"] == row["kulcs"]]
        assert _close(row["ertek"], g["szallitas_nap"].mean()) and row["rendelesek"] == len(g)
    assert r.idoablak == {"tol": "2017-06-01", "ig": "2017-12-31", "teljes": False}
    assert [f["dimenzio"] for f in r.szurok] == ["vevo_allam"]


def test_wilson_tartomany_kis_csoport_es_viszonyszamok(cat, wl, con):
    r = _run({"metrika": "kesesi_arany", "bontas": ["vevo_allam"], "limit": 3}, cat, wl, con)
    tot = r.osszesen
    assert tuple(tot["ci"]) == wilson(tot["szamlalo"], tot["rendelesek"])
    assert tot["ci"][0] <= tot["ertek"] <= tot["ci"][1]
    for row in r.sorok:
        assert tuple(row["ci"]) == wilson(row["szamlalo"], row["rendelesek"])
        assert row["keves_adat"] == (row["rendelesek"] < 100)
        assert row["relativ"] == pytest.approx(row["ertek"] / tot["ertek"])
    values = [row["ertek"] for row in r.sorok]
    assert values == sorted(values, reverse=True)
    shown = r.shown_rows()
    assert len(shown) == 3 and not any(row["keves_adat"] for row in shown)

    f = _run({"metrika": "forgalom", "bontas": ["vevo_allam"]}, cat, wl, con)
    assert sum(row["reszesedes"] for row in f.sorok) == pytest.approx(1.0)
    assert not any(row["keves_adat"] for row in f.sorok)          # összegnél nincs minimum

    k = _run({"metrika": "atlagos_keses", "bontas": ["vevo_regio"]}, cat, wl, con)
    for row in k.sorok:                       # a késés átlaga a KÉSETT rendelésekből számolódik
        assert row["keves_adat"] == (row["alap"] < 30) and row["alap"] <= row["rendelesek"]

    up = _run({"metrika": "kesesi_arany", "bontas": ["elado_allam"], "rendezes": "ertek_novekvo"}, cat, wl, con)
    vals = [row["ertek"] for row in up.sorok]
    assert vals == sorted(vals)


def test_ugyanarra_a_kerdesre_bitre_azonos_eredmeny(cat, wl, con):
    raw = {"metrika": "median_szallitasi_ido", "bontas": ["honap"], "szuro": {"vevo_regio": ["SE"]}}
    a, b = _run(raw, cat, wl, con), _run(raw, cat, wl, con)
    assert a == b                                         # az időmérés nem része az összevetésnek
    assert json.dumps(a.to_payload(), default=str) == json.dumps(b.to_payload(), default=str)
    assert ans.answer(a).text == ans.answer(b).text


# ------------------------------------------------------------ sablonos válasz
def test_a_valasz_minden_szama_a_payloadbol_jon(cat, wl, con):
    n = 0
    raws = list(_grid(cat)) + [
        {"metrika": "kesesi_arany", "bontas": ["vevo_allam"], "szuro": {"vevo_regio": ["SE", "S"]},
         "idoablak": {"tol": "2016-01-01", "ig": "2018-02-28"}},
        {"metrika": "forgalom", "bontas": ["kategoria"], "rendezes": "ertek_novekvo", "limit": 3},
        {"metrika": "atlagos_keses", "bontas": ["vevo_regio"], "rendezes": "bontas"},
    ]
    for raw in raws:
        a = ans.answer(_run(raw, cat, wl, con))
        assert a.fedetlen_szamok() == [], (raw, a.text)
        assert all(shown in a.text for shown, _ in a.hivatkozasok)
        assert a.text.startswith("A kérdés ") and "  " not in a.text
        n += 1
    assert n > 90


def test_a_szamellenor_eszreveszi_a_kitalalt_szamot():
    refs = [("6,8%", "osszesen.ertek"), ("12 350", "osszesen.rendelesek")]
    text = "A késési arány 6,8%, 12 350 rendelésből; tavaly 7,1% volt, 2017-ben 3 hónapig."
    assert ans.uncovered_numbers(text, refs) == ["7,1", "2017", "3"]
    assert ans.uncovered_numbers("A késési arány 6,8%.", refs) == []


def test_a_valasz_szerkezete(cat, wl, con):
    a = ans.answer(_run({"metrika": "kesesi_arany", "bontas": ["vevo_allam"], "limit": 2}, cat, wl, con))
    assert "95%-os tartomány" in a.text and "A vevő állama szerint a legmagasabb" in a.text
    assert "együttjárást jeleznek, nem okot" in a.text
    clamp = ans.answer(_run({"metrika": "forgalom", "idoablak": {"tol": "2010-01-01", "ig": "2017-12-31"}},
                            cat, wl, con))
    assert "a kérdés időablakát erre szűkítettem" in clamp.text and clamp.fedetlen_szamok() == []
    honap = ans.answer(_run({"metrika": "kesesi_arany", "bontas": ["honap"]}, cat, wl, con))
    assert "Havi bontásban a legmagasabb" in honap.text


def test_ures_eredmenyre_nincs_szam(cat, wl, con):
    rare = wl.values["vevo_allam"][0]
    days = {r[0] for r in con.execute("SELECT DISTINCT f.date_key FROM fact_orders f JOIN dim_customer c "
                                      "USING (customer_key) WHERE c.allam = ?", [rare]).fetchall()}
    day = next(wl.date_min + timedelta(i) for i in range(400) if wl.date_min + timedelta(i) not in days)
    r = _run({"metrika": "kesesi_arany", "bontas": ["kategoria"], "szuro": {"vevo_allam": [rare]},
              "idoablak": {"tol": day.isoformat(), "ig": day.isoformat()}}, cat, wl, con)
    assert r.empty and r.sorok == [] and r.osszesen["ertek"] is None
    a = ans.answer(r)
    assert "nincs egyetlen kézbesített rendelés sem" in a.text and a.fedetlen_szamok() == []
    # van rendelés, de egy sem késett: az átlagos késés nem számolható (nem 0 nap)
    on_time = con.execute("SELECT date_key FROM fact_orders GROUP BY 1 HAVING NOT bool_or(kesett) "
                          "ORDER BY count(*) DESC LIMIT 1").fetchone()[0]
    k = _run({"metrika": "atlagos_keses", "idoablak": {"tol": on_time.isoformat(), "ig": on_time.isoformat()}},
             cat, wl, con)
    assert k.osszesen["rendelesek"] > 0 and k.osszesen["ertek"] is None
    text = ans.answer(k).text
    assert "nincs késett rendelés, ezért az átlagos késés nem számolható" in text


# ----------------------------------------------------------- ábra és táblázat
def _marks(spec: dict):
    if "layer" in spec:
        for layer in spec["layer"]:
            yield from _marks(layer)
    elif "mark" in spec:
        yield spec


@pytest.mark.parametrize("raw", [
    {"metrika": "kesesi_arany", "bontas": ["honap"]},
    {"metrika": "kesesi_arany", "bontas": ["vevo_allam"], "limit": 5},
    {"metrika": "forgalom", "bontas": ["ev"]},
    {"metrika": "atlagos_keses", "bontas": ["vevo_regio"]},
    {"metrika": "rendelesek_szama", "bontas": ["het_napja"]},
    {"metrika": "atlagos_szallitasi_ido", "bontas": ["kesett"], "rendezes": "bontas"},
])
def test_az_abra_minden_jelenek_magyar_sugoja_van(cat, wl, con, raw):
    r = _run(raw, cat, wl, con)
    for ink in (charts.LIGHT, charts.DARK):
        spec = charts.answer_chart(r, ink).to_dict()
        layers = list(_marks(spec))
        assert layers
        for layer in layers:
            mark = layer["mark"] if isinstance(layer["mark"], dict) else {"type": layer["mark"]}
            assert "tooltip" in layer.get("encoding", {}) or mark.get("tooltip") is False, mark
    assert charts.answer_chart(_run({"metrika": "forgalom"}, cat, wl, con)) is None


def test_a_valasz_tablazata(cat, wl, con):
    t = be.answer_table(_run({"metrika": "kesesi_arany", "bontas": ["vevo_allam"]}, cat, wl, con))
    assert list(t.columns) == ["megnevezes", "ertek", "rendelesek", "tartomany", "viszony", "keves_adat"]
    assert t["viszony"].str.fullmatch(r"\d+,\d×").all()
    k = be.answer_table(_run({"metrika": "atlagos_keses", "bontas": ["vevo_regio"]}, cat, wl, con))
    assert "alap" in k.columns and "tartomany" not in k.columns


# ------------------------------------------------------------- a Kérdezz oldal
@pytest.fixture
def app_env(synth_db, synth_cache, monkeypatch):
    monkeypatch.setenv("GLASSBOX_DB", str(synth_db))
    monkeypatch.setenv("GLASSBOX_CACHE", str(synth_cache))


def _no_exception(at):
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_a_kerdezz_oldal_vegigkattinthato(app_env):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP), default_timeout=180).run()
    at.switch_page("oldalak/kerdezz.py").run()
    _no_exception(at)
    assert not at.error
    assert any(m.value.startswith("**Válasz.**") for m in at.markdown)
    for i in range(6):                                            # a példakérdések
        at.button(key=f"kerdezz_pelda_{i}").click().run()
        _no_exception(at)
        assert not at.error
        assert any(m.value.startswith("**Válasz.**") for m in at.markdown)
        assert len(at.dataframe) == 1
    at.selectbox(key="kerdezz_bontas").select("kategoria").run()
    _no_exception(at)
    assert len(at.radio(key="kerdezz_rendezes").options) == 2    # kategóriánál nincs „bontás sorrendje”
    at.selectbox(key="kerdezz_metrika").select("atlagos_keses").run()
    at.multiselect(key="kerdezz_szuro_vevo_regio").select("SE").run()
    _no_exception(at)
    assert not at.error and any("Délkelet" in m.value for m in at.markdown)

    at.button(key="kerdezz_kapu_0").click().run()                 # „nem létező mérőszám”
    _no_exception(at)
    assert any("nem_elerheto" in e.value for e in at.error)
    at.text_area(key="kerdezz_kapu_json").input('{"metrika": "forgalom", "bontas": "ev"}').run()
    _no_exception(at)
    assert any("Elfogadva" in s.value for s in at.success)


# ------------------------------------------------ a PostgreSQL-változat ellenőrzése
def test_a_katalogus_ujjlenyomata_sorvegfuggetlen(tmp_path, cat):
    """Windowson a git CRLF-fel írhatja ki a katalógust — az ujjlenyomat ettől nem változhat."""
    crlf = tmp_path / "k.toml"
    crlf.write_bytes(catalog.KATALOGUS.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert catalog.load(crlf).sha256 == cat.sha256


def test_a_postgresql_ellenorzes_lezart_eredmenye(cat):
    pg = be.pg_check()
    assert pg is not None, "hiányzik: uv run python -m semantic.pg_ellenorzes"
    assert pg["adat"] == "valós" and pg["elteres"] == 0 and pg["eltero_esetek"] == []
    assert pg["lekerdezesek"] > 300 and pg["cellak"] > 5000
    assert pg["katalogus_sha256"] == cat.sha256, \
        "a metrikakatalógus változott — futtasd újra: uv run python -m semantic.pg_ellenorzes"
    assert "PostgreSQL" in pg["postgresql"] and pg["pg_collation"] == "C"


def test_az_ellenorzes_kerdesei_es_kiirasa(cat, wl, con, tmp_path):
    from semantic import pg_ellenorzes as pgc
    qs = pgc.questions(cat, wl)
    assert {q["metrika"] for q in qs} == set(cat.metrics)
    assert all(sp.check(q, cat, wl).ok for q in qs)
    assert {q["rendezes"] for q in qs if "rendezes" in q} == set(catalog.SORT_ORDERS)
    counts = pgc.export(con, cat, wl, tmp_path)
    assert counts["esetek"] == len(qs)
    ddl = json.loads((tmp_path / "ddl.json").read_text(encoding="utf-8"))
    assert len(ddl) == 4 and "kosar_ertek numeric(12,2)" in ddl[0]
    assert (tmp_path / "fact_orders.csv").read_text(encoding="utf-8").count("\n") == 1 + len(
        con.execute("SELECT * FROM fact_orders").fetchall())


def test_az_osszevetes_eszreveszi_az_elterest(tmp_path):
    from semantic import pg_ellenorzes as pgc
    cases = [{"kerdes": {"metrika": "x"}, "pg": {"osszesen": "…", "bontas": "…"},
              "duckdb": {"osszesen": {"oszlopok": ["ertek", "rendelesek"], "sorok": [[0.25, 4]]},
                         "bontas": {"oszlopok": ["bontas", "ertek"],
                                    "sorok": [["2018-01-01", 1.0], [2018, 2.0], ["SP", None]]}}}]
    same = [{"osszesen": {"oszlopok": ["ertek", "rendelesek"], "sorok": [["0.25000000000000000001", 4]]},
             "bontas": {"oszlopok": ["bontas", "ertek"],
                        "sorok": [["2018-01-01T00:00:00.000Z", "1.0"], ["2018", 2], ["SP", None]]}}]
    (tmp_path / "esetek.json").write_text(json.dumps(cases), encoding="utf-8")
    (tmp_path / "pg_eredmeny.json").write_text(json.dumps(same), encoding="utf-8")
    r = pgc.compare(tmp_path)
    assert (r["elteres"], r["sorok"], r["cellak"]) == (0, 4, 8)
    same[0]["bontas"]["sorok"][1] = ["2017", 2]                   # más kulcs
    same[0]["osszesen"]["sorok"][0][0] = 0.2500001                 # tűrésen kívül
    (tmp_path / "pg_eredmeny.json").write_text(json.dumps(same), encoding="utf-8")
    r = pgc.compare(tmp_path)
    assert r["elteres"] == 2 and {d["oszlop"] for d in r["eltero_esetek"]} == {"ertek", "bontas"}
    same[0]["bontas"] = {"hiba": "syntax error"}
    (tmp_path / "pg_eredmeny.json").write_text(json.dumps(same), encoding="utf-8")
    assert pgc.compare(tmp_path)["eltero_esetek"][-1]["hiba"] == "syntax error"


def _pglite_ready() -> bool:
    import shutil
    from semantic import pg_ellenorzes as pgc
    return bool(shutil.which("node")) and (pgc.RUNNER / "node_modules" / "@electric-sql" / "pglite").exists()


@pytest.mark.skipif(not _pglite_ready(), reason="Node.js és a PGlite (tools/pg: npm ci) nélkül nem futtatható")
def test_postgresqlben_is_ugyanaz_a_szintetikus_adaton(cat, wl, con, tmp_path):
    from semantic import pg_ellenorzes as pgc
    pgc.export(con, cat, wl, tmp_path)
    pgc.run_postgres(tmp_path)
    r = pgc.compare(tmp_path)
    assert r["elteres"] == 0, r["eltero_esetek"][:3]
    assert r["lekerdezesek"] > 300
