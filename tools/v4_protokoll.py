"""
A v3 mérés protokolljának (docs/k1_protokoll_v3.json) változata a v4 futáshoz: minden ugyanaz, csak a
„kod.ujjlenyomat” a v4-é (kod.v4.ujjlenyomat) — a v4 mérőprogramja csak ezzel indul el. A
tools/v4_futtatas.bat hívja; az összevető eszköz (tools/k1_v3_osszevetes.py) ugyanígy előállítja,
és ellenőrzi, hogy a v4 futás fejlécében ennek az ujjlenyomata áll.

    uv run python tools/v4_protokoll.py v4_kod/docs/k1_protokoll_v3.json
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORRAS = ROOT / "docs" / "k1_protokoll_v3.json"


def derive(protocol: dict) -> dict:
    d = copy.deepcopy(protocol)
    d["kod"]["ujjlenyomat"] = protocol["kod"]["v4"]["ujjlenyomat"]
    d["kod"]["szarmaztatott"] = ("a v4 futáshoz: a kód-ujjlenyomat a kod.v4.ujjlenyomat, minden más a "
                                 "docs/k1_protokoll_v3.json-é (tools/v4_protokoll.py)")
    return d


def text(protocol: dict) -> str:
    return json.dumps(derive(protocol), ensure_ascii=False, indent=2) + "\n"


def sha256(protocol: dict) -> str:
    """A származtatott fájl ujjlenyomata egységesített (LF) sorvégekkel — mint a mérőprogramé."""
    return hashlib.sha256(text(protocol).encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        raise SystemExit("használat: python tools/v4_protokoll.py CÉLFÁJL")
    protocol = json.loads(FORRAS.read_text(encoding="utf-8"))
    if protocol.get("allapot") != "jovahagyva":
        raise SystemExit("A v3 protokoll még nincs jóváhagyva — a v4 futás csak utána indulhat.")
    out = Path(argv[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text(protocol), encoding="utf-8")
    print(f"A v4 futás protokollja: {out} (SHA256 {sha256(protocol)[:16]}…)")


if __name__ == "__main__":
    main()
