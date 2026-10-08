"""
V-1 validációs réteg tesztjei.

Nem a "jó" adatot teszteljük — azt a betanítás úgyis kipróbálja —, hanem azt,
hogy a ROSSZ adatra a tárház a várt módon reagál-e:

  * szerkezeti hiba          -> azonnali leállás
  * elszórt, ritka sorhiba   -> karantén, a tárház felépül, a jelentés rögzíti
  * tömeges sorhiba          -> leállás (tűréshatár felett)
  * vegyes forrású adat      -> leállás

Minden teszt egy kicsi, ideiglenes mappában dolgozik; a projekt valódi
tárházához nem nyúl.
"""

from __future__ import annotations

import shutil

import duckdb
import pandas as pd
import pytest

from data.build_warehouse import ValidationError, build
from data.make_synthetic import generate

ORDERS = "olist_orders_dataset.csv"


@pytest.fixture(scope="module")
def clean_raw(tmp_path_factory):
    d = tmp_path_factory.mktemp("raw_clean")
    generate(n_orders=3000, seed=7, out_dir=d, verbose=False)
    return d


@pytest.fixture
def raw(clean_raw, tmp_path):
    """Friss másolat minden teszthez, hogy nyugodtan elronthassuk."""
    d = tmp_path / "raw"
    shutil.copytree(clean_raw, d)
    return d


def _corrupt(raw_dir, fn):
    """Módosítja az orders fájlt. A szintetikus jelölőt töröljük, mert egy
    kézzel módosított fájl már nem a generátoré — valós adatként kezelendő."""
    path = raw_dir / ORDERS
    df = pd.read_csv(path)
    df = fn(df)
    df.to_csv(path, index=False)
    (raw_dir / "_synthetic.json").unlink()


# ----------------------------------------------------------------------------
def test_tiszta_adat_felepul_es_szintetikusnak_ismeri(raw, tmp_path):
    s = build(raw, tmp_path / "w.duckdb", verbose=False)
    assert s["adatforras"] == "szintetikus"
    assert s["karanten"] == []
    con = duckdb.connect(str(tmp_path / "w.duckdb"), read_only=True)
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    types = dict(con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'fact_orders'").fetchall())
    con.close()
    assert {"fact_orders", "dim_date", "dim_customer", "dim_seller",
            "dim_product", "meta_build", "meta_sources", "meta_quarantine"} <= tables
    assert types["date_key"] == "DATE", "A dátumkulcs DATE típusú legyen."
    assert types["kosar_ertek"].startswith("DECIMAL"), "Pénzösszeg nem lehet lebegőpontos."
    assert types["szallitasi_dij"].startswith("DECIMAL"), "Pénzösszeg nem lehet lebegőpontos."


def test_duplikalt_rendeles_leallit(raw, tmp_path):
    _corrupt(raw, lambda df: pd.concat([df, df.iloc[[0]]], ignore_index=True))
    with pytest.raises(ValidationError, match="Duplikált order_id"):
        build(raw, tmp_path / "w.duckdb", verbose=False)


def test_elszort_sorhiba_karantenba_kerul(raw, tmp_path):
    """Egyetlen hibás sor (kézbesítés a rendelés előtt): karantén, nem leállás."""
    def one_bad(df):
        i = df.index[df["order_status"].eq("delivered")][0]
        t = pd.to_datetime(df.loc[i, "order_purchase_timestamp"])
        df.loc[i, "order_delivered_customer_date"] = str(t - pd.Timedelta(days=3))
        return df
    _corrupt(raw, one_bad)
    s = build(raw, tmp_path / "w.duckdb", verbose=False)
    assert s["adatforras"] == "valós"
    assert ("kézbesítés a rendelés előtt", 1) in s["karanten"]


def test_vegyes_datumformatum_nem_okoz_csendes_adatvesztest(raw, clean_raw, tmp_path):
    """
    Regressziós teszt egy valódi, a fejlesztés közben talált hibára: ha egy
    dátumoszlopban vegyes a formátum ("2017-11-17" és "2017-11-17 14:05:00"),
    a pandas az első sorból következtetett, és a többit csendben NaT-ra
    alakította — a sorok szinte mind eltűntek, hibaüzenet nélkül.
    """
    ref = build(clean_raw, tmp_path / "ref.duckdb", verbose=False)["fact_sorok"]

    def add_time_to_first(df):
        i = df.index[df["order_status"].eq("delivered")][0]
        d = pd.to_datetime(df.loc[i, "order_delivered_customer_date"])
        df.loc[i, "order_delivered_customer_date"] = str(d + pd.Timedelta(hours=14))
        return df
    _corrupt(raw, add_time_to_first)
    s = build(raw, tmp_path / "w.duckdb", verbose=False)
    assert s["fact_sorok"] == ref, (
        f"Sorvesztés vegyes dátumformátum miatt: {s['fact_sorok']} vs {ref}.")


def test_tomeges_sorhiba_leallit(raw, tmp_path):
    """5% hibás sor már rendszerszintű probléma — a tűréshatár 0,1%."""
    def many_bad(df):
        idx = df.index[df["order_status"].eq("delivered")]
        bad = idx[: int(len(idx) * 0.05)]
        t = pd.to_datetime(df.loc[bad, "order_purchase_timestamp"])
        df.loc[bad, "order_delivered_customer_date"] = (t - pd.Timedelta(days=3)).astype(str)
        return df
    _corrupt(raw, many_bad)
    with pytest.raises(ValidationError, match="tűréshatárt"):
        build(raw, tmp_path / "w.duckdb", verbose=False)


def test_vegyes_forras_leallit(raw, tmp_path):
    """Ha csak EGY fájlt cseréltek le, a többi még szintetikus: ez hibás tárházat adna."""
    path = raw / ORDERS
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="Vegyes forrású"):
        build(raw, tmp_path / "w.duckdb", verbose=False)


def test_hianyzo_fajl_leallit(raw, tmp_path):
    (raw / ORDERS).unlink()
    with pytest.raises(ValidationError, match="Hiányzó forrásfájlok"):
        build(raw, tmp_path / "w.duckdb", verbose=False)


# ---------------------------------------------------------------------------
# Két ténytábla, fő tétel, geolokáció, zárónap (okt. 8., témavezetői H2, H6, P2)
# ---------------------------------------------------------------------------
def _tables(db):
    con = duckdb.connect(str(db), read_only=True)
    fo = con.execute("SELECT * FROM fact_orders").df()
    foi = con.execute("SELECT * FROM fact_order_items").df()
    meta = con.execute("SELECT * FROM meta_build").df().iloc[0]
    kiz = con.execute("SELECT * FROM kizart_rendelesek").df()
    cust = con.execute("SELECT * FROM dim_customer").df()
    q = con.execute("SELECT * FROM meta_quarantine").df()
    con.close()
    return fo, foi, meta, kiz, cust, q


def test_ket_tenytabla_es_a_fo_tetel_szabalya(clean_raw, tmp_path):
    db = tmp_path / "w.duckdb"
    build(clean_raw, db, verbose=False)
    fo, foi, *_ = _tables(db)

    # minden rendelésnek pontosan egy fő tétele van, és az a megjelölt sorszám
    fotetel = foi[foi["fo_tetel"]]
    assert fotetel["order_key"].is_unique and len(fotetel) == len(fo)
    fo_map = fo.set_index("order_key")["fo_tetel_sorszam"]
    assert (fotetel.set_index("order_key")["tetel_sorszam"] == fo_map.loc[fotetel["order_key"]].values).all()

    # a fő tétel a legdrágább; egyezésnél a legkisebb sorszámú
    best = (foi.sort_values(["order_key", "ar", "tetel_sorszam"], ascending=[True, False, True])
               .drop_duplicates("order_key").set_index("order_key")["tetel_sorszam"])
    assert (best.loc[fo["order_key"]].values == fo["fo_tetel_sorszam"].values).all()

    # a rendelésszintű pénzösszeg PONTOSAN a tételek összege — DECIMAL
    # aritmetikával az adatbázisban (pandasban lebegőpontos lenne az összeadás)
    con = duckdb.connect(str(db), read_only=True)
    elteres = con.execute("""
        SELECT count(*) FROM fact_orders f
        JOIN (SELECT order_key, sum(ar) AS a, sum(szallitasi_dij) AS d
              FROM fact_order_items GROUP BY order_key) i USING (order_key)
        WHERE f.kosar_ertek <> i.a OR f.szallitasi_dij <> i.d""").fetchone()[0]
    con.close()
    assert elteres == 0

    # tételszám és eladószám a tételekből
    f = fo.set_index("order_key")
    cnt = foi.groupby("order_key").agg(n=("tetel_sorszam", "count"), s=("seller_key", "nunique"))
    assert (cnt.loc[f.index, "n"].values == f["tetel_szam"].values).all()
    assert (cnt.loc[f.index, "s"].values == f["elado_szam"].values).all()


def test_geolokacio_median_es_brazil_keret(raw, tmp_path):
    """Brazílián kívüli pont -> karantén; előtagonként a medián számít, nem az átlag."""
    geo_path = raw / "olist_geolocation_dataset.csv"
    cust = pd.read_csv(raw / "olist_customers_dataset.csv")
    geo = pd.read_csv(geo_path)
    prefix = int(cust["customer_zip_code_prefix"].iloc[0])
    row = geo[geo["geolocation_zip_code_prefix"] == prefix].iloc[0]
    extra = pd.DataFrame([
        # még két pont ugyanott + egy kiugró (Brazílián belül): a medián marad
        {**row.to_dict(), "geolocation_lat": row["geolocation_lat"]},
        {**row.to_dict(), "geolocation_lat": row["geolocation_lat"]},
        {**row.to_dict(), "geolocation_lat": 4.9},
        # két pont Európában, brazil irányítószámmal -> karantén
        {**row.to_dict(), "geolocation_lat": 41.6, "geolocation_lng": -8.4},
        {**row.to_dict(), "geolocation_lat": 38.4, "geolocation_lng": -6.3},
    ])
    pd.concat([geo, extra], ignore_index=True).to_csv(geo_path, index=False)
    (raw / "_synthetic.json").unlink()

    s = build(raw, tmp_path / "w.duckdb", verbose=False)
    assert ("Brazílián kívüli koordináta", 2) in s["karanten"]
    _, _, _, _, dim_c, _ = _tables(tmp_path / "w.duckdb")
    lat = dim_c.loc[dim_c["iranyitoszam"] == str(prefix), "szelesseg"].iloc[0]
    assert abs(lat - row["geolocation_lat"]) < 1e-9, "Nem a medián került a dimenzióba."


def test_zarnap_es_kizart_rendelesek(clean_raw, tmp_path):
    db = tmp_path / "w.duckdb"
    s = build(clean_raw, db, verbose=False)
    fo, _, meta, kiz, _, _ = _tables(db)
    orders = pd.read_csv(clean_raw / ORDERS)
    events = [pd.to_datetime(orders[c], format="ISO8601").max() for c in [
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date"]]
    assert pd.Timestamp(meta["megfigyelesi_zarnap"]) == max(events)
    # minden rendelés vagy a ténytáblában, vagy a kizártak között van (karantén nélkül)
    assert len(fo) + len(kiz) == len(orders)
    assert not set(fo["order_key"]) & set(kiz["order_key"])
    # érzékenységi késés csak úton lévő ÉS lejárt határidejű rendelés lehet
    jelolt = kiz[kiz["kesett_erzekenysegi"]]
    assert jelolt["lejart_a_zarnapig"].all()
    assert set(jelolt["statusz"]) <= {"shipped", "invoiced", "processing", "approved", "created"}
    assert s["kizart_lejart_uton"] == len(jelolt) > 0
