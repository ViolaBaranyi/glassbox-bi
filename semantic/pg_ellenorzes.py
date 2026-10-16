"""
A PostgreSQL-változat ellenőrzése: ugyanaz-e az eredmény DuckDB-ben és PostgreSQL-ben?

Az SQL-építő minden lekérdezést PostgreSQL-dialektusban is előállít (sqlglot-fordítás,
builder.py). Hogy ez ne csak szintaktikailag legyen helyes, ez a szkript a tárház tábláit
betölti egy valódi PostgreSQL-be (PGlite: a PostgreSQL WebAssemblyre fordítva, Node.js-ben
fut, telepítés és szerver nélkül), lefuttatja rajta a katalógus minden mérőszámát minden
megengedett bontással (és szűrt, időablakos, másképp rendezett változatokkal), és cellánként
összeveti a DuckDB-eredménnyel.

    uv run python -m semantic.pg_ellenorzes          # Node.js kell hozzá (nodejs.org)

Kimenet: docs/pg_ellenorzes.json és .md (a valódi adaton futtatva ez a lezárt eredmény);
a köztes fájlok az artifacts/pg_ellenorzes/ mappába kerülnek (rendelésazonosítókkal —
ezért nem kerülnek a repóba). A katalógus változása után újra kell futtatni.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import duckdb
import sqlglot

from data.db import DB_PATH, WarehouseUnavailable, connect, use_utf8_console
from semantic import builder, catalog
from semantic import spec as sp

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "artifacts" / "pg_ellenorzes"
RUNNER = ROOT / "tools" / "pg"
DOCS = ROOT / "docs"
TABLES = ("fact_orders", "dim_customer", "dim_seller", "dim_product")
PG_TYPES = {"VARCHAR": "text", "DATE": "date", "TIMESTAMP": "timestamp", "INTEGER": "integer",
            "BIGINT": "bigint", "DOUBLE": "double precision", "BOOLEAN": "boolean"}
REL_TOL, ABS_TOL = 1e-9, 1e-12


def _pg_type(duck_type: str) -> str:
    if duck_type.startswith("DECIMAL"):
        return duck_type.replace("DECIMAL", "numeric")
    return PG_TYPES[duck_type]


def questions(cat: catalog.Catalog, wl: catalog.Whitelist) -> list[dict]:
    """A vizsgált kérdések: minden mérőszám × (nincs bontás + minden megengedett bontás),
    szűrt és időablakos változatok, és minden rendezés. Amit a kapu elutasít, kimarad."""
    raws = []
    for m in cat.metrics.values():
        raws.append({"metrika": m.id})
        raws += [{"metrika": m.id, "bontas": [d.id]} for d in cat.dimensions.values()
                 if d.id not in m.tiltott_dimenzio]
    cats = wl.values.get("kategoria", ())
    filters = [{"vevo_allam": list(wl.values["vevo_allam"][-2:])}, {"vevo_regio": ["NE"]},
               {"het_napja": ["1", "7"]}, {"kesett": ["kesett"]},
               {"elado_allam": list(wl.values["elado_allam"][-1:]), "vevo_allam": list(wl.values["vevo_allam"][:1])}]
    if len(cats) > 3:
        filters.append({"kategoria": [cats[1], cats[-2]]})
    mid = wl.date_min + (wl.date_max - wl.date_min) / 3
    window = {"tol": mid.isoformat(), "ig": (mid + (wl.date_max - wl.date_min) / 3).isoformat()}
    for m, f, d in itertools.product(("kesesi_arany", "atlagos_szallitasi_ido", "median_szallitasi_ido",
                                      "forgalom", "atlagos_tavolsag"), filters, (None, "vevo_regio", "honap")):
        raw = {"metrika": m, "szuro": f, "idoablak": window}
        if d:
            raw["bontas"] = [d]
        raws.append(raw)
    for d, order in itertools.product(("vevo_regio", "kesett", "kategoria", "vevo_allam", "het_napja"),
                                      catalog.SORT_ORDERS):
        raws.append({"metrika": "atlagos_szallitasi_ido", "bontas": [d], "rendezes": order, "limit": 5})
    return [r for r in raws if sp.check(r, cat, wl).ok]


def _plain(v):
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, (datetime, date)):
        return str(v)[:10]
    if isinstance(v, Decimal):
        return float(v)
    return str(v)


def export(con, cat, wl, work: Path) -> dict:
    """1. lépés: a táblák CSV-be, a lekérdezések (PG-SQL + DuckDB-eredmény) JSON-ba."""
    work.mkdir(parents=True, exist_ok=True)
    ddl = []
    for t in TABLES:
        cols = con.execute(f"DESCRIBE {t}").fetchall()
        ddl.append(f"CREATE TABLE {t} (" + ", ".join(f"{c[0]} {_pg_type(c[1])}" for c in cols) + ")")
        con.execute(f"COPY {t} TO '{(work / (t + '.csv')).as_posix()}' (HEADER, DELIMITER ',')")
    cases = []
    for raw in questions(cat, wl):
        gate = sp.check(raw, cat, wl)
        built = builder.build(gate.spec, cat)
        case = {"kerdes": gate.spec.to_dict(), "pg": {}, "duckdb": {}}
        for part, sql, pg in (("osszesen", built.total, built.total_pg),
                              ("bontas", built.groups, built.groups_pg)):
            if sql is None:
                continue
            cur = con.execute(sql)
            case["duckdb"][part] = {"oszlopok": [c[0] for c in cur.description],
                                    "sorok": [[_plain(v) for v in row] for row in cur.fetchall()]}
            case["pg"][part] = pg
        cases.append(case)
    (work / "ddl.json").write_text(json.dumps(ddl), encoding="utf-8")
    (work / "esetek.json").write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    return {"esetek": len(cases), "lekerdezesek": sum(len(c["pg"]) for c in cases)}


def run_postgres(work: Path) -> None:
    """2. lépés: a Node.js-futtató (tools/pg) betölti és lefuttatja a PostgreSQL-ben."""
    node, npm = shutil.which("node"), shutil.which("npm")
    if not node or not npm:
        raise SystemExit("Ehhez az ellenőrzéshez Node.js kell (https://nodejs.org, LTS-változat); "
                         "telepítés után nyiss új terminált, és futtasd újra.")
    if not (RUNNER / "node_modules" / "@electric-sql" / "pglite").exists():
        print("PGlite telepítése (egyszer, a tools/pg mappába)…", flush=True)
        subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=RUNNER, check=True)
    subprocess.run([node, str(RUNNER / "futtat.mjs"), str(work)], check=True)


def _norm(col: str, v):
    if v is None:
        return None
    if col == "bontas":
        s = str(v)
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return s[:10]
        try:
            f = float(s)
        except ValueError:
            return s
        return str(int(f)) if f.is_integer() else s
    return float(v)


def compare(work: Path) -> dict:
    """3. lépés: cellánkénti összevetés (szám: relatív 1e-9 tűréssel; kulcs és sorrend: pontosan)."""
    cases = json.loads((work / "esetek.json").read_text(encoding="utf-8"))
    pg = json.loads((work / "pg_eredmeny.json").read_text(encoding="utf-8"))
    if len(pg) != len(cases):
        raise SystemExit("A PostgreSQL-eredmény nem a mostani esetekhez tartozik — futtasd újra az egészet.")
    diffs, rows, cells, max_rel = [], 0, 0, 0.0
    for case, got in zip(cases, pg):
        for part, duck in case["duckdb"].items():
            res = got.get(part, {})
            where = {"kerdes": case["kerdes"], "resz": part}
            if "hiba" in res:
                diffs.append({**where, "hiba": res["hiba"][:300]})
                continue
            if res["oszlopok"] != duck["oszlopok"] or len(res["sorok"]) != len(duck["sorok"]):
                diffs.append({**where, "hiba": "eltérő oszlopok vagy sorszám"})
                continue
            for i, (rd, rp) in enumerate(zip(duck["sorok"], res["sorok"])):
                rows += 1
                for col, a, b in zip(duck["oszlopok"], rd, rp):
                    cells += 1
                    a, b = _norm(col, a), _norm(col, b)
                    if a is None or b is None or col == "bontas":
                        same = a == b
                    else:
                        same = math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)
                        if a:
                            max_rel = max(max_rel, abs(a - b) / abs(a))
                    if not same:
                        diffs.append({**where, "sor": i, "oszlop": col, "duckdb": a, "postgresql": b})
    return {"esetek": len(cases), "lekerdezesek": sum(len(c["duckdb"]) for c in cases), "sorok": rows,
            "cellak": cells, "elteres": len(diffs), "legnagyobb_relativ_kulonbseg": max_rel,
            "eltero_esetek": diffs[:20]}


_SUP = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")


def _sci(x: float) -> str:
    """8,6 · 10⁻¹⁵ (0 → 0)."""
    if not x:
        return "0"
    mant, exp = f"{x:.1e}".split("e")
    return f"{mant.replace('.', ',')} · 10{str(int(exp)).translate(_SUP)}"


def write_report(summary: dict, out: Path = DOCS) -> None:
    (out / "pg_ellenorzes.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n",
                                            encoding="utf-8")
    ok = summary["elteres"] == 0
    md = [
        "# A PostgreSQL-változat ellenőrzése",
        "",
        f"*Futtatva: {summary['futtatva']} · adat: {summary['adat']} (tárház: {summary['tarhaz_epitve']}) · "
        f"metrikakatalógus: `{summary['katalogus_sha256'][:12]}…`*",
        "",
        "Az SQL-építő minden kérdésből DuckDB- és PostgreSQL-lekérdezést is készít (sqlglot). "
        "Ez az ellenőrzés a tárház tábláit betöltötte egy valódi PostgreSQL-be, és mindkét "
        "rendszeren lefuttatta ugyanazokat a kérdéseket: a katalógus minden mérőszámát bontás "
        "nélkül és minden megengedett bontással, továbbá szűrt, időablakos és többféleképpen "
        "rendezett változatokat.",
        "",
        "| | |",
        "|---|---|",
        f"| kérdés | {summary['esetek']} |",
        f"| lekérdezés (összesen + csoportonként) | {summary['lekerdezesek']} |",
        f"| összevetett sor / cella | {summary['sorok']} / {summary['cellak']} |",
        f"| eltérés | **{summary['elteres']}** |",
        f"| legnagyobb relatív különbség a számokban | {_sci(summary['legnagyobb_relativ_kulonbseg'])} |",
        "",
        f"Rendszerek: {summary['duckdb']}; {summary['postgresql']}; fordító: sqlglot {summary['sqlglot']}.",
        "",
        ("**Eredmény:** a két rendszer minden cellában ugyanazt adja (a számok relatív 10⁻⁹ "
         "tűréssel, a csoportkulcsok és a sorrend pontosan)." if ok else
         "**Eredmény: eltérés van** — a részletek a JSON-fájl `eltero_esetek` mezőjében."),
        "",
        "Korlát: a szöveges kulcsok sorrendje (`ORDER BY`) az adatbázis rendezési szabályától "
        f"(collation) függ; itt `{summary['pg_collation']}`, ami bájtsorrend, mint a DuckDB-é. Más "
        "collationnel (pl. hu_HU) az ábécérend eltérhet; a számok nem.",
        "",
        "Újrafuttatás: `uv run python -m semantic.pg_ellenorzes` (Node.js kell hozzá).",
        "",
    ]
    (out / "pg_ellenorzes.md").write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="DuckDB és PostgreSQL eredményének összevetése")
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--kimenet", type=Path, default=None,
                    help="a jelentés mappája (alapból docs/, ha a valódi adaton fut; különben artifacts/)")
    a = ap.parse_args()
    try:
        con = connect(a.db, read_only=True)
    except WarehouseUnavailable as exc:
        print(f"\nHIBA:\n{exc}", file=sys.stderr)
        sys.exit(1)
    cat = catalog.load()
    wl = catalog.whitelist(cat, con)
    print("1/3 Táblák és lekérdezések kiírása…", flush=True)
    counts = export(con, cat, wl, WORK)
    con.close()
    print(f"    {counts['esetek']} kérdés, {counts['lekerdezesek']} lekérdezés", flush=True)
    print("2/3 Futtatás PostgreSQL-ben (PGlite)…", flush=True)
    run_postgres(WORK)
    print("3/3 Összevetés…", flush=True)
    summary = compare(WORK)
    info = json.loads((WORK / "pg_info.json").read_text(encoding="utf-8"))
    summary = {"futtatva": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "adat": wl.source or "ismeretlen", "tarhaz_epitve": wl.built,
               "katalogus_sha256": cat.sha256, "duckdb": f"DuckDB {duckdb.__version__}",
               "postgresql": info["postgresql"], "pg_collation": info["collation"],
               "sqlglot": sqlglot.__version__, "tolerancia": {"relativ": REL_TOL, "abszolut": ABS_TOL},
               **summary}
    out = a.kimenet or (DOCS if wl.source == "valós" else WORK)
    out.mkdir(parents=True, exist_ok=True)
    write_report(summary, out)
    report = out / "pg_ellenorzes.md"
    shown = report.relative_to(ROOT) if report.is_relative_to(ROOT) else report
    print(f"\n{summary['lekerdezesek']} lekérdezés, {summary['cellak']} cella: "
          f"{summary['elteres']} eltérés  →  {shown}")
    sys.exit(0 if summary["elteres"] == 0 else 1)


if __name__ == "__main__":
    main()
