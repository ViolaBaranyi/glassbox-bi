"""
A szemantikus réteg parancssorból — a felület nélkül is kipróbálható.

    uv run python -m semantic --katalogus
    uv run python -m semantic --metrika kesesi_arany --bontas vevo_allam --limit 5
    uv run python -m semantic --metrika atlagos_szallitasi_ido --bontas honap \\
        --szuro vevo_allam=SP --tol 2018-01-01 --ig 2018-06-30 --sql
    uv run python -m semantic --metrika haszonkulcs          # a KAPU ① elutasítja

A kapcsolók ugyanazt a kérdés-specifikációt (QuerySpec) állítják elő, amit a felület
kérdésépítője — és később a nyelvi modell.
"""

from __future__ import annotations

import argparse
import json
import sys

from data.db import DB_PATH, WarehouseUnavailable, connect, use_utf8_console
from semantic import answer as ans
from semantic import catalog, engine
from semantic import spec as sp


def _filters(items) -> dict:
    out: dict[str, list[str]] = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"A --szuro alakja dimenzio=ertek[,ertek…], ez nem az: {item!r}")
        dim, vals = item.split("=", 1)
        out.setdefault(dim.strip(), []).extend(v.strip() for v in vals.split(",") if v.strip())
    return out


def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="Kérdés a metrikakatalógushoz (KAPU ① + SQL + sablonos válasz)")
    ap.add_argument("--katalogus", action="store_true", help="a mérőszámok és a bontások listája")
    ap.add_argument("--metrika")
    ap.add_argument("--bontas", action="append")
    ap.add_argument("--szuro", action="append", help="dimenzio=ertek[,ertek…] (többször is megadható)")
    ap.add_argument("--tol")
    ap.add_argument("--ig")
    ap.add_argument("--rendezes")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--sql", action="store_true", help="a lefuttatott SQL kiírása (és PostgreSQL-ben)")
    ap.add_argument("--json", action="store_true", help="a teljes payload JSON-ban")
    a = ap.parse_args()

    cat = catalog.load()
    if a.katalogus:
        print("MÉRŐSZÁMOK")
        for m in cat.metrics.values():
            print(f"  {m.id:<24} {m.nev} — {m.leiras}")
        print("\nBONTÁSOK ÉS SZŰRŐK")
        for d in cat.dimensions.values():
            print(f"  {d.id:<24} {d.rovid}{'' if d.szurheto else ' (csak bontás; szűrni az időablakkal)'}")
        return
    raw = {"metrika": a.metrika, "bontas": a.bontas or [], "szuro": _filters(a.szuro)}
    if a.tol or a.ig:
        raw["idoablak"] = {k: v for k, v in (("tol", a.tol), ("ig", a.ig)) if v}
    if a.rendezes:
        raw["rendezes"] = a.rendezes
    if a.limit is not None:
        raw["limit"] = a.limit
    try:
        con = connect(DB_PATH, read_only=True)
    except WarehouseUnavailable as exc:
        print(f"\nHIBA:\n{exc}", file=sys.stderr)
        sys.exit(1)
    wl = catalog.whitelist(cat, con)
    gate = sp.check(raw, cat, wl)
    print(f"KAPU ①: {gate.status}")
    if not gate.ok:
        print(gate.elutasitas.uzenet)
        sys.exit(2)
    result = engine.run(gate.spec, cat, wl, con, gate.megjegyzesek)
    con.close()
    print(json.dumps(gate.spec.to_dict(), ensure_ascii=False))
    print("\n" + ans.answer(result).text + "\n")
    for row in result.sorok[: max(gate.spec.limit, 1) if result.spec.rendezes != "bontas" else None]:
        flag = "  (kevés adat)" if row["keves_adat"] else ""
        value = "—" if row["ertek"] is None else ans.fmt_value(result.metrika, row["ertek"])
        print(f"  {row['megnevezes']:<40} {value:>16}   {ans.fmt_count(row['rendelesek'])} rendelés{flag}")
    if a.sql:
        for title, sql in (("SQL (DuckDB)", result.sql), ("SQL (PostgreSQL)", result.sql_postgres)):
            for part, text in sql.items():
                if text:
                    print(f"\n-- {title}, {part}\n{text}")
    if a.json:
        print(json.dumps(result.to_payload(), ensure_ascii=False, indent=1, default=str))
    print(f"\n({result.ido_ms:.0f} ms)")


if __name__ == "__main__":
    main()
