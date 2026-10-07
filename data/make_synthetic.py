"""
Szintetikus, Olist-alakú adat generálása.

Mire kell: a valódi Olist-adat nem kerülhet a tárolóba, ezért a CI (GitHub
Actions) és a tesztek ezen futnak — így a teljes pipeline (ETL -> jellemzők ->
betanítás) valódi adat nélkül is végigfuttatható és ellenőrizhető. A fájlnevek
és oszlopnevek szándékosan azonosak a valódi Olist adathalmazéval.

A demó alapból a valódi adaton fut (data/fetch_olist.py tölti le); szintetikus
adatot csak a `python demo.py --synthetic` vagy ez a modul állít elő.

FONTOS: ez NEM a valódi adat. Az itt kapott számok semmit nem mondanak a valóságról.
A generátor szándékosan visz be ismert összefüggéseket, hogy a modellnek legyen mit
megtanulnia, és hogy a szivárgásteszt is tudjon mibe beleakadni.

Futtatás:
    python -m data.make_synthetic --orders 40000 --seed 42
    (valódi adatot tartalmazó mappát nem ír felül; másik mappába: --out <mappa>)
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(__file__).resolve().parent / "raw"

# Brazil államok KÖZELÍTŐ központi koordinátái. Csak a szintetikus adathoz,
# a valódi Olistban a geolocation tábla adja az irányítószám szintű pozíciót.
STATES = {
    "SP": (-23.55, -46.63, 0.42),
    "RJ": (-22.91, -43.20, 0.13),
    "MG": (-19.92, -43.94, 0.12),
    "RS": (-30.03, -51.23, 0.06),
    "PR": (-25.43, -49.27, 0.05),
    "SC": (-27.59, -48.55, 0.04),
    "BA": (-12.97, -38.50, 0.05),
    "PE": (-8.05, -34.88, 0.03),
    "CE": (-3.73, -38.53, 0.03),
    "GO": (-16.69, -49.26, 0.03),
    "DF": (-15.79, -47.88, 0.02),
    "AM": (-3.10, -60.02, 0.02),
}

CATEGORIES = [
    ("cama_mesa_banho", "bed_bath_table"),
    ("beleza_saude", "health_beauty"),
    ("esporte_lazer", "sports_leisure"),
    ("informatica_acessorios", "computers_accessories"),
    ("moveis_decoracao", "furniture_decor"),
    ("utilidades_domesticas", "housewares"),
    ("relogios_presentes", "watches_gifts"),
    ("telefonia", "telephony"),
    ("automotivo", "auto"),
    ("brinquedos", "toys"),
    ("ferramentas_jardim", "garden_tools"),
    ("perfumaria", "perfumery"),
]

START = pd.Timestamp("2017-01-01")
END = pd.Timestamp("2018-08-31")
TARGET_LATE_RATE = 0.08


def haversine_km(lat1, lon1, lat2, lon2):
    """Két pont távolsága km-ben."""
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = np.radians(lat2 - lat1)
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def zscore(x):
    x = np.asarray(x, dtype=float)
    return (x - x.mean()) / (x.std() + 1e-9)


def pick_states(rng, n):
    names = list(STATES.keys())
    probs = np.array([STATES[s][2] for s in names])
    probs = probs / probs.sum()
    return rng.choice(names, size=n, p=probs)


def jitter_coords(rng, states):
    lat = np.array([STATES[s][0] for s in states]) + rng.normal(0, 0.8, len(states))
    lon = np.array([STATES[s][1] for s in states]) + rng.normal(0, 0.8, len(states))
    return lat, lon


def generate(n_orders: int = 40000, seed: int = 42,
             out_dir: Path = RAW, verbose: bool = True) -> dict:
    rng = np.random.default_rng(seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- eladók
    n_sellers = max(60, n_orders // 70)
    seller_ids = [f"s{i:05d}" for i in range(n_sellers)]
    seller_states = pick_states(rng, n_sellers)
    seller_lat, seller_lon = jitter_coords(rng, seller_states)
    # Latens megbízhatóság, kétmóduszú eloszlással: az eladók ~20%-a rendszeresen
    # problémás. Ez az egyik valódi jel, amit a modellnek meg kell találnia. Reálisabb,
    # mint egy sima unimodális eloszlás, és — ami itt fontos — az eladó MÚLTJÁBÓL
    # tényleg megtanulható, mert a két csoport késési aránya érdemben elválik.
    problemas = rng.random(n_sellers) < 0.20
    seller_unreliability = np.where(
        problemas, rng.beta(6, 3, n_sellers), rng.beta(2, 8, n_sellers))
    seller_zip = rng.integers(1000, 99999, n_sellers)

    sellers = pd.DataFrame({
        "seller_id": seller_ids,
        "seller_zip_code_prefix": seller_zip,
        "seller_city": [f"city_{s.lower()}" for s in seller_states],
        "seller_state": seller_states,
    })

    # ---------------------------------------------------------------- vevők
    n_customers = int(n_orders * 0.85)
    customer_unique = [f"cu{i:06d}" for i in range(n_customers)]
    cust_states = pick_states(rng, n_customers)
    cust_lat, cust_lon = jitter_coords(rng, cust_states)
    cust_zip = rng.integers(1000, 99999, n_customers)

    # ---------------------------------------------------------------- termékek
    n_products = max(120, n_orders // 25)
    product_ids = [f"p{i:05d}" for i in range(n_products)]
    prod_cat_idx = rng.integers(0, len(CATEGORIES), n_products)
    prod_weight = np.clip(rng.lognormal(6.6, 0.9, n_products), 50, 30000)  # gramm
    prod_len = rng.integers(8, 90, n_products)
    prod_hei = rng.integers(3, 70, n_products)
    prod_wid = rng.integers(5, 80, n_products)

    products = pd.DataFrame({
        "product_id": product_ids,
        "product_category_name": [CATEGORIES[i][0] for i in prod_cat_idx],
        "product_name_lenght": rng.integers(20, 70, n_products),
        "product_description_lenght": rng.integers(100, 3000, n_products),
        "product_photos_qty": rng.integers(1, 8, n_products),
        "product_weight_g": prod_weight.round().astype(int),
        "product_length_cm": prod_len,
        "product_height_cm": prod_hei,
        "product_width_cm": prod_wid,
    })

    # ---------------------------------------------------------------- rendelések
    order_ids = [f"o{i:07d}" for i in range(n_orders)]
    cust_idx = rng.integers(0, n_customers, n_orders)
    seller_idx = rng.integers(0, n_sellers, n_orders)
    prod_idx = rng.integers(0, n_products, n_orders)

    span_days = (END - START).days
    purchase_offset = rng.integers(0, span_days, n_orders)
    purchase = START + pd.to_timedelta(purchase_offset, unit="D")
    purchase = purchase + pd.to_timedelta(rng.integers(0, 24 * 60, n_orders), unit="m")

    distance = haversine_km(
        seller_lat[seller_idx], seller_lon[seller_idx],
        cust_lat[cust_idx], cust_lon[cust_idx],
    )
    weight_g = prod_weight[prod_idx]
    n_items = rng.choice([1, 2, 3], n_orders, p=[0.86, 0.11, 0.03])

    # Vállalt szállítási idő: a távolsággal nő, de csak gyengén és zajosan. Ha túl
    # szoros lenne a kapcsolat, a vállalt idő kioltaná a távolság hatását, és
    # egyik jellemző sem maradna informatív.
    promised_days = np.clip(
        (9 + distance / 420 + rng.normal(0, 4, n_orders)).round(), 4, 45
    ).astype(int)
    estimated = (purchase.normalize() + pd.to_timedelta(promised_days, unit="D"))

    # Ünnepi torlódás: november vége (Black Friday) és december.
    month = purchase.month.values
    day = purchase.day.values
    busy = ((month == 11) & (day >= 20)) | (month == 12)

    # --- A késés valódi generáló folyamata -------------------------------
    z = (
        0.55 * zscore(np.log1p(distance))
        + 2.60 * (seller_unreliability[seller_idx] - seller_unreliability.mean())
        + 0.35 * zscore(np.log1p(weight_g))
        - 0.70 * zscore(promised_days)
        + 0.50 * busy.astype(float)
        + 0.20 * (n_items - 1)
        + rng.normal(0, 0.45, n_orders)
    )
    # Eltoljuk az intercept-et, hogy a késési arány a célérték közelébe essen.
    lo, hi = -12.0, 6.0
    for _ in range(60):
        mid = (lo + hi) / 2
        rate = (1 / (1 + np.exp(-(z + mid)))).mean()
        if rate > TARGET_LATE_RATE:
            hi = mid
        else:
            lo = mid
    p_late = 1 / (1 + np.exp(-(z + (lo + hi) / 2)))
    late = rng.random(n_orders) < p_late

    # --- Dátumok, amelyek konzisztensek a címkével ------------------------
    delivered = np.empty(n_orders, dtype="datetime64[ns]")
    late_extra = rng.integers(1, 13, n_orders)
    early_frac = rng.uniform(0.35, 0.92, n_orders)
    for i in range(n_orders):
        if late[i]:
            delivered[i] = estimated[i] + pd.Timedelta(days=int(late_extra[i]))
        else:
            d = max(2, int(promised_days[i] * early_frac[i]))
            delivered[i] = purchase[i].normalize() + pd.Timedelta(days=d)
    delivered = pd.to_datetime(delivered)

    approved = purchase + pd.to_timedelta(rng.integers(1, 48, n_orders), unit="h")
    carrier = approved + pd.to_timedelta(rng.integers(4, 96, n_orders), unit="h")
    carrier = pd.Series(np.minimum(carrier.values, delivered.values))

    # Nem minden rendelés ér célba: ~3% más státusszal, hiányzó kézbesítéssel.
    status = np.full(n_orders, "delivered", dtype=object)
    broken = rng.random(n_orders) < 0.03
    status[broken] = rng.choice(["shipped", "canceled", "processing"], broken.sum())

    orders = pd.DataFrame({
        "order_id": order_ids,
        "customer_id": [f"c{i:07d}" for i in range(n_orders)],
        "order_status": status,
        "order_purchase_timestamp": purchase,
        "order_approved_at": approved,
        "order_delivered_carrier_date": carrier,
        "order_delivered_customer_date": delivered,
        "order_estimated_delivery_date": estimated,
    })
    for col in ["order_delivered_carrier_date", "order_delivered_customer_date"]:
        orders.loc[broken, col] = pd.NaT

    # A customers tábla: order-szintű customer_id -> személy szintű unique id.
    customers = pd.DataFrame({
        "customer_id": orders["customer_id"],
        "customer_unique_id": [customer_unique[i] for i in cust_idx],
        "customer_zip_code_prefix": cust_zip[cust_idx],
        "customer_city": [f"city_{s.lower()}" for s in cust_states[cust_idx]],
        "customer_state": cust_states[cust_idx],
    })

    # ---------------------------------------------------------------- tételek
    item_rows = []
    for i in range(n_orders):
        base_price = float(np.round(rng.lognormal(4.3, 0.75), 2))
        freight = float(np.round(6 + distance[i] / 90 + weight_g[i] / 2600, 2))
        for k in range(int(n_items[i])):
            item_rows.append((
                order_ids[i], k + 1,
                product_ids[prod_idx[i]] if k == 0 else product_ids[rng.integers(0, n_products)],
                seller_ids[seller_idx[i]],
                (purchase[i] + pd.Timedelta(days=3)),
                round(base_price * (1 + 0.1 * k), 2),
                round(freight, 2),
            ))
    items = pd.DataFrame(item_rows, columns=[
        "order_id", "order_item_id", "product_id", "seller_id",
        "shipping_limit_date", "price", "freight_value",
    ])

    # ---------------------------------------------------------------- fizetés
    pay = items.groupby("order_id", as_index=False)[["price", "freight_value"]].sum()
    payments = pd.DataFrame({
        "order_id": pay["order_id"],
        "payment_sequential": 1,
        "payment_type": rng.choice(
            ["credit_card", "boleto", "voucher", "debit_card"],
            len(pay), p=[0.74, 0.19, 0.05, 0.02]),
        "payment_installments": rng.integers(1, 11, len(pay)),
        "payment_value": (pay["price"] + pay["freight_value"]).round(2),
    })

    # ---------------------------------------------------------------- értékelés
    # A késés erősen rontja az értékelést -> ez a tábla SZÁNDÉKOSAN szivárgó.
    # Pont ezért kell, hogy a szivárgásteszt tudjon mit kiszűrni.
    score = np.where(late, rng.choice([1, 2, 3], n_orders, p=[0.55, 0.3, 0.15]),
                     rng.choice([4, 5, 3], n_orders, p=[0.35, 0.55, 0.10]))
    reviews = pd.DataFrame({
        "review_id": [f"r{i:07d}" for i in range(n_orders)],
        "order_id": order_ids,
        "review_score": score,
        "review_comment_title": "",
        "review_creation_date": delivered + pd.Timedelta(days=1),
        "review_answer_timestamp": delivered + pd.Timedelta(days=2),
    })

    # ---------------------------------------------------------------- geo
    geo_zip = np.concatenate([cust_zip, seller_zip])
    geo_lat = np.concatenate([cust_lat, seller_lat])
    geo_lon = np.concatenate([cust_lon, seller_lon])
    geo_st = np.concatenate([cust_states, seller_states])
    geolocation = pd.DataFrame({
        "geolocation_zip_code_prefix": geo_zip,
        "geolocation_lat": geo_lat.round(5),
        "geolocation_lng": geo_lon.round(5),
        "geolocation_city": [f"city_{s.lower()}" for s in geo_st],
        "geolocation_state": geo_st,
    }).drop_duplicates("geolocation_zip_code_prefix")

    translation = pd.DataFrame(CATEGORIES, columns=[
        "product_category_name", "product_category_name_english"])

    # ---------------------------------------------------------------- kiírás
    out = {
        "olist_orders_dataset.csv": orders,
        "olist_order_items_dataset.csv": items,
        "olist_customers_dataset.csv": customers,
        "olist_sellers_dataset.csv": sellers,
        "olist_products_dataset.csv": products,
        "olist_order_payments_dataset.csv": payments,
        "olist_order_reviews_dataset.csv": reviews,
        "olist_geolocation_dataset.csv": geolocation,
        "product_category_name_translation.csv": translation,
    }
    for name, df in out.items():
        df.to_csv(out_dir / name, index=False)

    # Ujjlenyomat: a build_warehouse ebből ismeri fel, hogy szintetikus adatból
    # épül-e a tárház — és hogy nem keveredett-e valódi fájlokkal.
    def _sha(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    marker = {
        "generator": "data.make_synthetic",
        "figyelem": "SZINTETIKUS ADAT — nem a valóság. A valódi Olist CSV-k "
                    "bemásolásakor ez a fájl törölhető.",
        "seed": seed,
        "orders": n_orders,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {name: _sha(out_dir / name) for name in out},
    }
    (out_dir / "_synthetic.json").write_text(
        json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")

    delivered_mask = orders["order_status"].eq("delivered")
    actual_rate = float(late[delivered_mask.values].mean())
    if verbose:
        print(f"Szintetikus adat kiírva ide: {out_dir}")
        print(f"  rendelések:        {n_orders:,}")
        print(f"  kézbesített:       {delivered_mask.sum():,}")
        print(f"  késési arány:      {actual_rate:.1%}  (cél: {TARGET_LATE_RATE:.0%})")
        print(f"  eladók / termékek: {n_sellers:,} / {n_products:,}")
        print(f"  időszak:           {START.date()} .. {END.date()}")
    return {"out_dir": str(out_dir), "orders": n_orders,
            "delivered": int(delivered_mask.sum()), "late_rate": actual_rate}

if __name__ == "__main__":
    from data.db import use_utf8_console
    use_utf8_console()
    ap = argparse.ArgumentParser(description="Olist-alakú szintetikus adat")
    ap.add_argument("--orders", type=int, default=40000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=RAW)
    args = ap.parse_args()
    from data.fetch_olist import data_state
    if data_state(args.out) == "valós":
        import sys
        print(f"A(z) {args.out} mappában valódi Olist-adat van — a szintetikus "
              "generálás felülírná.\nMásik mappába: --out <mappa>", file=sys.stderr)
        sys.exit(1)
    generate(n_orders=args.orders, seed=args.seed, out_dir=args.out)
