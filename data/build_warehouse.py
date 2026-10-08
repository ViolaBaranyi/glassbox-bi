"""
M0 — Adattárház: 9 Olist CSV  ->  csillagséma DuckDB-ben.

KÉT TÉNYTÁBLA, KÉT SZEMCSÉZETTSÉG
---------------------------------
* fact_order_items — egy sor = egy rendelési tétel (az Olistban egy tétel egy
  darab: két egyforma termék két sor). Ez a forrás minden rendelésszintű
  összegzéshez.
* fact_orders      — egy sor = egy rendelés. A döntés (késik-e a szállítmány)
  rendelésszinten értelmes, ezért a modell és a késési arány itt számol.

Számlálási szabály: minden arány és darabszám RENDELÉST számol (fact_orders),
soha nem tételt. A tételszintű tábla csak az összegzés forrása.

A rendelés FŐ TÉTELE a legnagyobb értékű tétel (egyezésnél a legkisebb
tételsorszámú); ebből jön a rendelés terméke, kategóriája és eladója. A súly
és a térfogat az összes tétel összege; ha egy tétel mérete hiányzik, az
összeg is hiányzó (NaN), nem alulbecsült.

TÁVOLSÁG — közelítés
--------------------
Az Olist irányítószám-előtagonként sok koordinátát ad. Előtagonként a
MEDIÁNT vesszük (a kiugró pontok nem húzzák el), a Brazílián kívüli pontokat
pedig karanténba tesszük. Az eladó–vevő távolság e két előtag-pont légvonalbeli
távolsága — közelítés, nem úthossz. Ha valamelyik előtaghoz nincs koordináta,
a távolság hiányzó (NaN); a LightGBM ezt natívan kezeli, a darabszám a
meta_build táblába kerül.

MEGFIGYELÉSI ZÁRÓNAP ÉS KIZÁRT RENDELÉSEK
----------------------------------------
A zárónap a nyers adat utolsó eseménye. Csak a kézbesített rendelésnek van
címkéje; a többi (feladva, számlázva, lemondva…) a kizart_rendelesek táblába
kerül, azzal együtt, hogy a vállalt határidő lejárt-e a zárónapig. A fő elemzés
ezeket kizárja (v2, a témavezetővel egyeztetve); az érzékenységi jelentés
(python -m pipeline.cohort_report) megmutatja, mi változna, ha a lejárt
határidejű, még úton lévőket késésnek tekintenénk.

V-1 VALIDÁCIÓS RÉTEG — két szigorúsági szint
--------------------------------------------
* SZERKEZETI HIBA  -> azonnali leállás. Az adat használhatatlan
  (pl. duplikált rendelésazonosító, hiányzó fájl, vegyes forrású adat).
* SORSZINTŰ HIBA   -> karantén TŰRÉSHATÁRRAL. Ha a hibás sorok aránya
  legfeljebb 0,1%, a sorok kikerülnek és a karantén-jelentésbe kerülnek;
  ha több, az már rendszerszintű probléma -> leállás.

  Ez a valódi adathoz kell: a nyilvános Olist adathalmazban is vannak
  elszórt adatminőségi hibák, és egy tucat hibás sor miatt nem szabad
  az egész tárháznak elbuknia — de ezer miatt igen.

EREDET (provenance)
-------------------
A tárház rögzíti, miből épült: forrásfájlonként SHA256 és sorszám, valamint
hogy szintetikus vagy valós adatról van-e szó (meta_* táblák).

Futtatás:
    python -m data.build_warehouse
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from data.db import WarehouseUnavailable, connect, use_utf8_console

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "warehouse.duckdb"

TOLERANCE = 0.001  # a sorszintű hibák megengedett aránya (0,1%)

# Brazília szélső pontjai kis pufferrel (fok): Monte Caburaí É 5,27°; Arroio Chuí
# D 33,75°; Serra do Divisor Ny kb. 73,99°; Martim Vaz-szigetek K 28,85°.
# A keret a szigeteket (pl. Fernando de Noronha) is tartalmazza.
BRAZIL_LAT = (-33.85, 5.37)
BRAZIL_LNG = (-74.10, -28.75)

# Ezek a státuszok még úton lévő (vagy elakadt) rendelést jelentenek; ha a vállalt
# határidő a zárónapig lejárt, az érzékenységi változatban késésnek számítanak.
# A lemondott / nem elérhető rendelés más kimenet, ezt egyik változat sem számolja.
IN_PROGRESS_STATUSES = ("shipped", "invoiced", "processing", "approved", "created")

SOURCES = {
    "orders": "olist_orders_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "geo": "olist_geolocation_dataset.csv",
    "translation": "product_category_name_translation.csv",
}
SYNTHETIC_MARKER = "_synthetic.json"


class ValidationError(RuntimeError):
    """V-1 réteg: az adat nem felel meg egy kötelező feltételnek."""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


class Quarantine:
    """Sorszintű hibák gyűjtője tűréshatárral."""

    def __init__(self, tolerance: float = TOLERANCE):
        self.tolerance = tolerance
        self.log: list[tuple[str, int]] = []

    def apply(self, df: pd.DataFrame, bad: pd.Series, reason: str) -> pd.DataFrame:
        n_bad = int(bad.sum())
        if n_bad == 0:
            return df
        frac = n_bad / max(len(df), 1)
        if frac > self.tolerance:
            raise ValidationError(
                f"{reason}: {n_bad:,} sor ({frac:.2%}) — ez meghaladja a "
                f"{self.tolerance:.1%}-os tűréshatárt, rendszerszintű hibára utal."
            )
        self.log.append((reason, n_bad))
        return df.loc[~bad].copy()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = np.radians(np.asarray(lat2) - np.asarray(lat1))
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def detect_source(raw_dir: Path, hashes: dict[str, str]) -> str:
    """Szintetikus vagy valós? A generátor kiírja a fájlok ujjlenyomatát."""
    marker = raw_dir / SYNTHETIC_MARKER
    if not marker.exists():
        return "valós"
    recorded = json.loads(marker.read_text(encoding="utf-8")).get("files", {})
    match = [recorded.get(f) == h for f, h in hashes.items()]
    if all(match):
        return "szintetikus"
    if not any(match):
        return "valós"
    mixed = [f for f, ok in zip(hashes, match) if ok]
    raise ValidationError(
        "Vegyes forrású adat: ezek a fájlok még a szintetikus generátortól "
        f"származnak, a többi nem: {', '.join(mixed)}. Másold be mind a 9 "
        "valódi CSV-t, vagy generáld újra a szintetikus adatot."
    )


def read_raw(raw_dir: Path) -> dict[str, pd.DataFrame]:
    missing = [f for f in SOURCES.values() if not (raw_dir / f).exists()]
    if missing:
        raise ValidationError(
            f"Hiányzó forrásfájlok itt: {raw_dir}\n  "
            + "\n  ".join(missing)
            + "\n\nHa még nincs meg a valódi adat, futtasd ezt:\n"
              "  python -m data.make_synthetic"
        )
    return {k: pd.read_csv(raw_dir / v) for k, v in SOURCES.items()}


def build(raw_dir: Path = RAW, db_path: Path = DB_PATH, verbose: bool = True) -> dict:
    raw_dir, db_path = Path(raw_dir), Path(db_path)
    raw = read_raw(raw_dir)
    hashes = {f: sha256(raw_dir / f) for f in SOURCES.values()}
    source = detect_source(raw_dir, hashes)
    q = Quarantine()

    orders = raw["orders"].copy()
    # Dátumok értelmezése — CSENDES ADATVESZTÉS NÉLKÜL.
    # A pandas alapból az első sor formátumából következtet; ha egy oszlopban
    # vegyes a formátum (pl. "2017-11-17" és "2017-11-07 10:56:00"), az
    # errors="coerce" a többit szó nélkül NaT-ra alakítaná, és a sorok eltűnnének.
    # Ezért ISO 8601 szerint értelmezünk, és minden meghiúsult értelmezést
    # megszámolunk: ritka hiba -> jelentés, tömeges hiba -> leállás.
    for c in ["order_purchase_timestamp", "order_approved_at",
              "order_delivered_carrier_date", "order_delivered_customer_date",
              "order_estimated_delivery_date"]:
        had_value = orders[c].notna() & orders[c].astype(str).str.strip().ne("")
        orders[c] = pd.to_datetime(orders[c], format="ISO8601", errors="coerce")
        failed = int((had_value & orders[c].isna()).sum())
        if failed:
            frac = failed / max(int(had_value.sum()), 1)
            if frac > TOLERANCE:
                raise ValidationError(
                    f"Dátumértelmezési hiba a(z) {c} oszlopban: {failed:,} érték "
                    f"({frac:.2%}) nem ISO 8601 formátumú.")
            q.log.append((f"értelmezhetetlen dátum ({c})", failed))

    # ---------------------------------------------------- V-1: szerkezeti
    check(len(orders) > 0, "Az orders tábla üres.")
    check(orders["order_id"].is_unique, "Duplikált order_id az orders táblában.")

    # Megfigyelési zárónap: a nyers adat utolsó tényleges eseménye. (A vállalt
    # határidő ígéret a jövőre, ezért nem számít eseménynek.)
    zarnap = max(orders[c].max() for c in [
        "order_purchase_timestamp", "order_approved_at",
        "order_delivered_carrier_date", "order_delivered_customer_date"])
    check(pd.notna(zarnap), "Egyetlen értelmezhető időpont sincs az orders táblában.")

    # Csak a ténylegesen kézbesített rendelésekkel dolgozunk: máshol nincs címke.
    is_delivered = (
        orders["order_status"].eq("delivered")
        & orders["order_delivered_customer_date"].notna()
        & orders["order_estimated_delivery_date"].notna()
    )
    delivered = orders[is_delivered].copy()
    check(len(delivered) > 0, "Nincs egyetlen kézbesített rendelés sem.")
    n_delivered_raw = len(delivered)

    # A többi rendelés nem tűnik el nyomtalanul: külön táblába kerül, hogy az
    # érzékenységi jelentés megmutathassa, mi változna nélkülük / velük.
    excl = orders[~is_delivered]
    vallalt_excl = excl["order_estimated_delivery_date"].dt.normalize()
    lejart = (vallalt_excl < zarnap.normalize()).fillna(False).astype(bool)
    folyamatban = excl["order_status"].isin(IN_PROGRESS_STATUSES)
    kizart_rendelesek = pd.DataFrame({
        "order_key": excl["order_id"],
        "statusz": excl["order_status"],
        "rendeles_idopont": excl["order_purchase_timestamp"],
        "vallalt_hatarido": vallalt_excl,
        "lejart_a_zarnapig": lejart,
        # érzékenységi változat: lejárt határidejű, de még úton lévő -> késett
        "kesett_erzekenysegi": (folyamatban & lejart),
    })

    # ---------------------------------------------------- V-1: sorszintű
    delivered = q.apply(delivered, delivered["order_purchase_timestamp"].isna(),
                        "hiányzó rendelési időpont")
    delivered = q.apply(
        delivered,
        delivered["order_delivered_customer_date"] < delivered["order_purchase_timestamp"],
        "kézbesítés a rendelés előtt")
    delivered = q.apply(
        delivered,
        delivered["order_estimated_delivery_date"].dt.normalize()
        < delivered["order_purchase_timestamp"].dt.normalize(),
        "vállalt határidő a rendelés előtt")

    # -------------------------------------------------------- dimenziók
    # Geolokáció: a Brazílián kívüli pontok karanténba kerülnek (az Olistban
    # néhány tucat ilyen van, pl. európai koordináta brazil irányítószámmal),
    # előtagonként pedig a MEDIÁN számít — egy kiugró pont nem húzza el.
    geo_raw = raw["geo"]
    in_box = (geo_raw["geolocation_lat"].between(*BRAZIL_LAT)
              & geo_raw["geolocation_lng"].between(*BRAZIL_LNG))
    geo_raw = q.apply(geo_raw, ~in_box, "Brazílián kívüli koordináta")
    geo = (geo_raw
           .groupby("geolocation_zip_code_prefix", as_index=False)
           .agg(lat=("geolocation_lat", "median"), lng=("geolocation_lng", "median")))

    cust = raw["customers"].merge(
        geo, left_on="customer_zip_code_prefix",
        right_on="geolocation_zip_code_prefix", how="left")
    dim_customer = pd.DataFrame({
        "customer_key": cust["customer_id"],
        "customer_unique_key": cust["customer_unique_id"],
        "allam": cust["customer_state"],
        "varos": cust["customer_city"],
        "iranyitoszam": cust["customer_zip_code_prefix"].astype(str),
        "szelesseg": cust["lat"],
        "hosszusag": cust["lng"],
    }).drop_duplicates("customer_key")

    sell = raw["sellers"].merge(
        geo, left_on="seller_zip_code_prefix",
        right_on="geolocation_zip_code_prefix", how="left")
    dim_seller = pd.DataFrame({
        "seller_key": sell["seller_id"],
        "allam": sell["seller_state"],
        "varos": sell["seller_city"],
        "szelesseg": sell["lat"],
        "hosszusag": sell["lng"],
    }).drop_duplicates("seller_key")

    prod = raw["products"].merge(raw["translation"], on="product_category_name", how="left")
    dim_product = pd.DataFrame({
        "product_key": prod["product_id"],
        "kategoria": prod["product_category_name_english"].fillna("ismeretlen"),
        "suly_g": prod["product_weight_g"],
        "hossz_cm": prod["product_length_cm"],
        "magassag_cm": prod["product_height_cm"],
        "szelesseg_cm": prod["product_width_cm"],
    }).drop_duplicates("product_key")

    # -------------------------------------------------------- tételek
    items = raw["items"].copy()
    check(not items.duplicated(["order_id", "order_item_id"]).any(),
          "Duplikált tétel (order_id + order_item_id) az items táblában.")
    # A pénzösszegek két tizedesre kerekítve: így a rendelésszintű összeg pontosan
    # a tételek DECIMAL összege lesz (ezt teszt ellenőrzi).
    items["price"] = items["price"].round(2)
    items["freight_value"] = items["freight_value"].round(2)
    items = items.merge(
        dim_product[["product_key", "kategoria", "suly_g",
                     "hossz_cm", "magassag_cm", "szelesseg_cm"]],
        left_on="product_id", right_on="product_key", how="left")
    items["terfogat_cm3"] = items["hossz_cm"] * items["magassag_cm"] * items["szelesseg_cm"]

    # A rendelés FŐ TÉTELE: a legnagyobb értékű; egyezésnél a legkisebb sorszámú.
    main = (items
            .sort_values(["order_id", "price", "order_item_id"],
                         ascending=[True, False, True], kind="mergesort")
            .drop_duplicates("order_id")
            [["order_id", "order_item_id", "product_id", "seller_id"]]
            .rename(columns={"order_item_id": "fo_tetel_sorszam",
                             "product_id": "product_key", "seller_id": "seller_key"}))

    g = items.groupby("order_id")
    agg = g.agg(
        tetel_szam=("order_item_id", "count"),
        kosar_ertek=("price", "sum"),
        szallitasi_dij=("freight_value", "sum"),
        elado_szam=("seller_id", "nunique"),
        kategoria_szam=("kategoria", "nunique"),
        suly_g=("suly_g", "sum"),
        terfogat_cm3=("terfogat_cm3", "sum"),
    )
    # Ha egy tétel mérete hiányzik, az összeg se legyen csendben alulbecsült.
    hiany = items.assign(_s=items["suly_g"].isna(), _v=items["terfogat_cm3"].isna()) \
                 .groupby("order_id")[["_s", "_v"]].any()
    agg.loc[hiany["_s"], "suly_g"] = np.nan
    agg.loc[hiany["_v"], "terfogat_cm3"] = np.nan
    agg = agg.reset_index().merge(main, on="order_id", how="left")

    fact = delivered.merge(agg, on="order_id", how="inner")
    check(len(fact) > 0, "A rendelés–tétel összekapcsolás üres eredményt adott.")

    fact = q.apply(fact, fact["kosar_ertek"] <= 0, "nempozitív kosárérték")
    fact = q.apply(fact, fact["szallitasi_dij"] < 0, "negatív szállítási díj")
    fact = q.apply(fact, ~fact["customer_id"].isin(set(dim_customer["customer_key"])),
                   "ismeretlen vevőre hivatkozik")
    fact = q.apply(fact, ~fact["seller_key"].isin(set(dim_seller["seller_key"])),
                   "ismeretlen eladóra hivatkozik")
    fact = q.apply(fact, ~fact["product_key"].isin(set(dim_product["product_key"])),
                   "ismeretlen termékre hivatkozik")

    # -------------------------------------------------------- fact_orders
    fact_orders = pd.DataFrame({
        "order_key": fact["order_id"],
        "date_key": fact["order_purchase_timestamp"].dt.normalize(),
        "customer_key": fact["customer_id"],
        "seller_key": fact["seller_key"],
        "product_key": fact["product_key"],

        # leadáskor ismert mértékek
        "rendeles_idopont": fact["order_purchase_timestamp"],
        "tetel_szam": fact["tetel_szam"].astype("int32"),
        "kosar_ertek": fact["kosar_ertek"].round(2),
        "szallitasi_dij": fact["szallitasi_dij"].round(2),
        "elado_szam": fact["elado_szam"].astype("int32"),
        "kategoria_szam": fact["kategoria_szam"].astype("int32"),
        "suly_g": fact["suly_g"],                 # az összes tétel összege
        "terfogat_cm3": fact["terfogat_cm3"],     # az összes tétel összege
        "fo_tetel_sorszam": fact["fo_tetel_sorszam"].astype("int32"),
        "vallalt_hatarido": fact["order_estimated_delivery_date"].dt.normalize(),

        # utólag ismert — CSAK a címkéhez és az as-of előzményhez, jellemzőnek tilos
        "feladas_datuma": fact["order_delivered_carrier_date"],
        "kezbesites_datuma": fact["order_delivered_customer_date"],
    })
    fact_orders["kesett"] = (
        fact_orders["kezbesites_datuma"].dt.normalize() > fact_orders["vallalt_hatarido"]
    )

    check(fact_orders["order_key"].is_unique, "Duplikált order_key a ténytáblában.")
    late_rate = float(fact_orders["kesett"].mean())
    check(0.001 < late_rate < 0.5,
          f"Gyanús késési arány: {late_rate:.1%}. Ellenőrizd a címkedefiníciót.")

    # -------------------------------------------------------- eladó–vevő távolság
    f = fact_orders.merge(
        dim_seller[["seller_key", "szelesseg", "hosszusag"]]
        .rename(columns={"szelesseg": "s_lat", "hosszusag": "s_lon"}),
        on="seller_key", how="left")
    f = f.merge(
        dim_customer[["customer_key", "szelesseg", "hosszusag"]]
        .rename(columns={"szelesseg": "c_lat", "hosszusag": "c_lon"}),
        on="customer_key", how="left")
    fact_orders["tavolsag_km"] = haversine_km(
        f["s_lat"], f["s_lon"], f["c_lat"], f["c_lon"]).round(2)
    tavolsag_hianyzik = int(fact_orders["tavolsag_km"].isna().sum())

    # -------------------------------------------------------- fact_order_items
    # Csak a ténytáblába bekerült rendelések tételei; a fő tétel megjelölve.
    foi = items[items["order_id"].isin(set(fact_orders["order_key"]))]
    fo_kulcs = set(zip(fact_orders["order_key"], fact_orders["fo_tetel_sorszam"]))
    fact_order_items = pd.DataFrame({
        "order_key": foi["order_id"],
        "tetel_sorszam": foi["order_item_id"].astype("int32"),
        "product_key": foi["product_id"],
        "seller_key": foi["seller_id"],
        "ar": foi["price"],
        "szallitasi_dij": foi["freight_value"],
        "fo_tetel": [k in fo_kulcs for k in zip(foi["order_id"], foi["order_item_id"])],
    })

    # -------------------------------------------------------- dim_date
    days = pd.date_range(fact_orders["date_key"].min(), fact_orders["date_key"].max(), freq="D")
    dim_date = pd.DataFrame({"date_key": days})
    dim_date["ev"] = dim_date["date_key"].dt.year.astype("int16")
    dim_date["honap"] = dim_date["date_key"].dt.month.astype("int16")
    dim_date["negyedev"] = dim_date["date_key"].dt.quarter.astype("int16")
    dim_date["het_napja"] = dim_date["date_key"].dt.dayofweek.astype("int16")
    dim_date["unnep_kozeli"] = (
        ((dim_date["honap"] == 11) & (dim_date["date_key"].dt.day >= 20))
        | (dim_date["honap"] == 12)
    )

    # A dátum-dimenzió kulcsa DATE típus legyen, ne TIMESTAMP (rendszerterv 06.).
    dim_date["date_key"] = dim_date["date_key"].dt.date
    fact_orders["date_key"] = fact_orders["date_key"].dt.date
    fact_orders["vallalt_hatarido"] = fact_orders["vallalt_hatarido"].dt.date
    kizart_rendelesek["vallalt_hatarido"] = kizart_rendelesek["vallalt_hatarido"].dt.date

    # -------------------------------------------------------- eredet
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    meta_build = pd.DataFrame([{
        "epitve": built_at,
        "adatforras": source,
        "rendelesek_nyers": len(orders),
        "kezbesitett": n_delivered_raw,
        "fact_sorok": len(fact_orders),
        "tetel_sorok": len(fact_order_items),
        "kesesi_arany": round(late_rate, 4),
        "karanten_osszes": sum(n for _, n in q.log),
        "turehatar": TOLERANCE,
        "megfigyelesi_zarnap": zarnap,
        "kizart_rendelesek": len(kizart_rendelesek),
        "kizart_lejart_uton": int(kizart_rendelesek["kesett_erzekenysegi"].sum()),
        "tavolsag_hianyzik": tavolsag_hianyzik,
    }])
    meta_sources = pd.DataFrame(
        [{"fajl": f, "sha256": h, "sorok": len(raw[k])}
         for (k, f), h in zip(SOURCES.items(), hashes.values())])
    meta_quarantine = pd.DataFrame(q.log, columns=["ok", "sorok"]) if q.log else \
        pd.DataFrame({"ok": pd.Series(dtype=str), "sorok": pd.Series(dtype="int64")})

    # -------------------------------------------------------- kiírás
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError as exc:
            raise WarehouseUnavailable(
                f"A régi tárházfájl nem törölhető, mert egy másik program nyitva "
                f"tartja: {db_path}\nZárd be a DBeaverben / a PyCharm "
                "adatbázis-paneljén, majd futtasd újra."
            ) from exc

    # Pénzösszeg DECIMAL, nem lebegőpontos: BI-összegzésnél a kerekítési hiba
    # nem megengedett (0,1 + 0,2 != 0,3 lebegőpontosan).
    select_override = {
        "fact_orders": (
            "SELECT * REPLACE ("
            "CAST(kosar_ertek AS DECIMAL(12,2)) AS kosar_ertek, "
            "CAST(szallitasi_dij AS DECIMAL(12,2)) AS szallitasi_dij) FROM tmp_df"),
        "fact_order_items": (
            "SELECT * REPLACE ("
            "CAST(ar AS DECIMAL(12,2)) AS ar, "
            "CAST(szallitasi_dij AS DECIMAL(12,2)) AS szallitasi_dij) FROM tmp_df"),
    }
    con = connect(db_path, read_only=False)
    for name, df in [
        ("dim_date", dim_date),
        ("dim_customer", dim_customer),
        ("dim_seller", dim_seller),
        ("dim_product", dim_product),
        ("fact_orders", fact_orders.sort_values(["date_key", "order_key"])),
        ("fact_order_items", fact_order_items.sort_values(["order_key", "tetel_sorszam"])),
        ("kizart_rendelesek", kizart_rendelesek.sort_values(["rendeles_idopont", "order_key"])),
        ("meta_build", meta_build),
        ("meta_sources", meta_sources),
        ("meta_quarantine", meta_quarantine),
    ]:
        con.register("tmp_df", df)
        sql = select_override.get(name, "SELECT * FROM tmp_df")
        con.execute(f"CREATE TABLE {name} AS {sql}")
        con.unregister("tmp_df")
    con.close()

    summary = {
        "db": str(db_path),
        "adatforras": source,
        "fact_sorok": len(fact_orders),
        "tetel_sorok": len(fact_order_items),
        "kesesi_arany": late_rate,
        "karanten": q.log,
        "idoszak": (str(fact_orders["date_key"].min()), str(fact_orders["date_key"].max())),
        "zarnap": str(zarnap),
        "kizart": len(kizart_rendelesek),
        "kizart_lejart_uton": int(kizart_rendelesek["kesett_erzekenysegi"].sum()),
        "tavolsag_hianyzik": tavolsag_hianyzik,
        "dimenziok": {"date": len(dim_date), "customer": len(dim_customer),
                      "seller": len(dim_seller), "product": len(dim_product)},
    }
    if verbose:
        print(f"Tárház felépítve: {db_path}")
        print(f"  adatforrás:   {source.upper()}")
        print(f"  fact_orders:  {len(fact_orders):,} rendelés "
              f"({len(fact_order_items):,} tétel a fact_order_items táblában)")
        print(f"  időszak:      {summary['idoszak'][0]} .. {summary['idoszak'][1]}"
              f"   (megfigyelési zárónap: {zarnap:%Y-%m-%d %H:%M})")
        print(f"  késési arány: {late_rate:.1%}")
        print(f"  kizárt (nem kézbesített) rendelés: {len(kizart_rendelesek):,}, ebből "
              f"lejárt határidejű és még úton: {summary['kizart_lejart_uton']:,}")
        print(f"  távolság hiányzik (nincs koordináta): {tavolsag_hianyzik:,} rendelés")
        d = summary["dimenziok"]
        print(f"  dimenziók:    date={d['date']:,}  customer={d['customer']:,}  "
              f"seller={d['seller']:,}  product={d['product']:,}")
        if q.log:
            print(f"  karantén ({TOLERANCE:.1%} tűréshatáron belül):")
            for reason, n in q.log:
                print(f"    - {reason}: {n:,} sor")
        else:
            print("  karantén:     üres")
        print("  V-1 validáció: rendben.")
    return summary


def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="Olist CSV -> DuckDB csillagséma")
    ap.add_argument("--raw", type=Path, default=RAW)
    ap.add_argument("--db", type=Path, default=DB_PATH)
    args = ap.parse_args()
    try:
        build(args.raw, args.db)
    except (ValidationError, WarehouseUnavailable) as exc:
        print(f"\nHIBA — a tárház nem épült fel:\n{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
