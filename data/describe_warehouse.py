"""
Belenézés a tárházba: eredet, táblák, séma, mintasorok és egy tipikus
üzleti lekérdezés.

Erre való: ellenőrizni, hogy a `build_warehouse` tényleg azt építette-e fel,
amit vártunk. A szemantikus réteg (KAPU ①) majd pontosan ilyen lekérdezéseket
fog generálni — csak nem kézzel, hanem a metrikakatalógusból.

(Korábban `inspect.py` volt a neve. Átneveztük, mert ütközött a Python
beépített `inspect` moduljával, ami bizonyos futtatási módokban — pl. a
PyCharm Run gombjával a data/ mappából indítva — rejtélyes hibákat okozott.)

Futtatás:
    python -m data.describe_warehouse
"""

from __future__ import annotations

import sys
from pathlib import Path

from data.db import DB_PATH, WarehouseUnavailable, connect, use_utf8_console


def main(db_path: Path = DB_PATH) -> None:
    try:
        con = connect(db_path, read_only=True)
    except WarehouseUnavailable as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    size_mb = Path(db_path).stat().st_size / 1024 / 1024
    print(f"Adatbázis: {db_path}")
    print(f"Méret:     {size_mb:.1f} MB")

    # ------------------------------------------------------------- eredet
    meta = con.execute("SELECT * FROM meta_build").df().iloc[0]
    forras = str(meta["adatforras"]).upper()
    print(f"Adatforrás: {forras}   (építve: {meta['epitve']})")
    if meta["adatforras"] == "szintetikus":
        print("  ! Szintetikus adat — a számok a gépezet működését mutatják,")
        print("    nem a valóságot.")

    # ------------------------------------------------------------- táblák
    print("\nTÁBLÁK")
    for (t,) in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name NOT LIKE 'meta_%' ORDER BY table_name").fetchall():
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"  {t:<16} {n:>9,} sor")

    # --------------------------------------------------- ténytábla sémája
    print("\nfact_orders OSZLOPAI")
    for name, dtype, *_ in con.execute("DESCRIBE fact_orders").fetchall():
        jelzes = ""
        if name in ("kezbesites_datuma", "feladas_datuma"):
            jelzes = "   <- csak címke / as-of előzmény; jellemzőnek TILOS"
        if name == "kesett":
            jelzes = "   <- a címke"
        print(f"  {name:<22} {dtype:<14}{jelzes}")

    # ------------------------------------------------------------ mintasorok
    print("\nMINTA (3 sor)")
    print(con.execute("""
        SELECT order_key, date_key, vallalt_hatarido,
               round(tavolsag_km) AS tav_km, tetel_szam, kesett
        FROM fact_orders
        ORDER BY date_key, order_key
        LIMIT 3
    """).df().to_string(index=False))

    # ------------------------------------------------- tipikus BI-lekérdezés
    # Pontosan ilyet fog generálni a szemantikus réteg a metrikakatalógusból.
    print("\nPÉLDA METRIKA — szállítási idő és késés vevői állam szerint")
    print(con.execute("""
        SELECT
            c.allam                                             AS allam,
            count(*)                                            AS rendelesek,
            round(avg(date_diff('day', f.date_key,
                      CAST(f.kezbesites_datuma AS DATE))), 1)   AS atlag_nap,
            round(100.0 * avg(CASE WHEN f.kesett THEN 1 ELSE 0 END), 1) AS keses_szazalek
        FROM fact_orders f
        JOIN dim_customer c ON f.customer_key = c.customer_key
        GROUP BY c.allam
        HAVING count(*) >= 100
        ORDER BY keses_szazalek DESC
        LIMIT 8
    """).df().to_string(index=False))

    # ---------------------------------------------------- validáció, eredet
    print("\nV-1 KARANTÉN")
    kar = con.execute("SELECT ok, sorok FROM meta_quarantine").fetchall()
    if kar:
        for ok, n in kar:
            print(f"  {ok:<34} {n:>6,} sor")
    else:
        print("  üres — egyetlen sor sem került karanténba")

    print("\nFORRÁSFÁJLOK (SHA256, első 12 karakter)")
    for fajl, sha, sorok in con.execute(
            "SELECT fajl, sha256, sorok FROM meta_sources ORDER BY fajl").fetchall():
        print(f"  {fajl:<40} {sha[:12]}  {sorok:>9,} sor")

    row = con.execute("""
        SELECT min(date_key), max(date_key), count(*),
               avg(CASE WHEN kesett THEN 1 ELSE 0 END)
        FROM fact_orders
    """).fetchone()
    print("\nÖSSZEGZÉS")
    print(f"  időszak:      {row[0]} .. {row[1]}")
    print(f"  rendelések:   {row[2]:,}")
    print(f"  késési arány: {row[3]:.1%}")
    con.close()


if __name__ == "__main__":
    use_utf8_console()
    main()
