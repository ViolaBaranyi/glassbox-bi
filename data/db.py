"""
Kapcsolat a tárházhoz — egyetlen helyen.

Minden modul innen kér kapcsolatot, nem közvetlenül a duckdb-től. Két oka van:

1. Érthető hibaüzenet a leggyakoribb helyzetekre (nincs még tárház; a fájlt
   egy másik program — pl. DBeaver vagy a PyCharm adatbázis-panelje — zárolja).
2. Ez a pont, ahol a rendszerterv NF-6 követelménye (motorfüggetlenség)
   később bekapcsolódik: egy PostgreSQL-profil ide kerül, a hívó kód nem változik.
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "warehouse.duckdb"


class WarehouseUnavailable(RuntimeError):
    """A tárház nem nyitható meg — a hibaüzenet megmondja, mit kell tenni."""


def connect(db_path: Path = DB_PATH, read_only: bool = True):
    db_path = Path(db_path)
    if read_only and not db_path.exists():
        raise WarehouseUnavailable(
            f"Nincs tárház itt: {db_path}\n"
            "Építsd fel előbb (vagy futtasd: python demo.py):\n"
            "  python -m data.fetch_olist\n"
            "  python -m data.build_warehouse"
        )
    try:
        return duckdb.connect(str(db_path), read_only=read_only)
    except duckdb.IOException as exc:
        raise WarehouseUnavailable(
            f"A tárházfájlt egy másik program zárolja: {db_path}\n"
            "Zárd be a kapcsolatot a DBeaverben / a PyCharm adatbázis-paneljén, "
            "majd futtasd újra.\n"
            f"(Eredeti hiba: {exc})"
        ) from exc


def use_utf8_console() -> None:
    """
    Windows alatt, ha a kimenet nem közvetlenül a konzolra megy (pl. PyCharm
    futtatóablak, átirányítás fájlba), a Python a helyi kódlapot (cp1250)
    használná, és egy nem latin-2 karakteren elhasalna. Ez megelőzi.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass
