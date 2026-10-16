"""
SQL-építő: elfogadott QuerySpec → SQL (rendszerterv 06., M1).

Az SQL kizárólag a katalógus SQL-töredékeiből és a fehérlistás értékekből áll össze, a
sqlglot szintaxisfájával (nem szövegösszefűzéssel): az értékek idézése így mindig
helyes, és ugyanabból a fából PostgreSQL-változat is készül (a kanonikus dialektus a
DuckDB-é). Két lekérdezés készül: az egész szűrt halmazé („összesen”) és — ha van
bontás — csoportonként. Kerekítés nincs: a számokat a megjelenítés kerekíti.

Mielőtt bármi lefutna, a `guard` a kész SQL-t újra elemzi: egyetlen SELECT lehet, csak a
katalógus tábláira és álneveire hivatkozhat, adatmódosító vagy rendszerparancs nem
lehet benne. A felület és a válasz ugyanezt a szöveget mutatja, ami lefutott.
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from semantic.catalog import Catalog
from semantic.spec import QuerySpec

DIALECT = "duckdb"
FORBIDDEN = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command,
             exp.Merge, exp.Copy, exp.Set, exp.Use, exp.Pragma, exp.Attach, exp.Detach, exp.Into)


class UnsafeSQL(ValueError):
    """A kész SQL nem felel meg a szabályoknak — nem futhat le."""


@dataclass(frozen=True)
class BuiltQuery:
    total: str                     # az egész szűrt halmaz (DuckDB)
    groups: str | None             # csoportonként, ha van bontás (DuckDB)
    total_pg: str                  # ugyanez PostgreSQL-ben (sqlglot fordítás)
    groups_pg: str | None


def _frag(sql: str) -> exp.Expression:
    return sqlglot.parse_one(sql, read=DIALECT)


def _literal(dim, value: str) -> exp.Expression:
    return exp.Literal.number(int(value)) if dim.tipus == "egesz" else exp.Literal.string(value)


def _natural(dim) -> tuple:
    return tuple(sorted(dim.ertekek, key=int)) if dim.tipus == "egesz" else tuple(sorted(dim.ertekek))


def _dim_order(dim) -> exp.Expression:
    """A „bontás sorrendje”: a rögzített listájú dimenziónál a katalógus sorrendje (a régiók
    északról délre, előbb a késett), egyébként maga a kulcs (idő, államkód…). A lista
    sorrendjét CASE adja a bemeneti kifejezésen — PostgreSQL-ben a kimeneti álnév
    kifejezésen belül nem használható."""
    if isinstance(dim.ertekek, str) or tuple(dim.ertekek) == _natural(dim):
        return exp.column("bontas")
    return exp.Case(this=_frag(dim.sql),
                    ifs=[exp.If(this=_literal(dim, v), true=exp.Literal.number(i))
                         for i, v in enumerate(dim.ertekek, 1)],
                    default=exp.Literal.number(len(dim.ertekek) + 1))


def _select(spec: QuerySpec, cat: Catalog, with_group: bool) -> exp.Select:
    metric = cat.metrics[spec.metrika]
    dims_needed = [cat.dimensions[d] for d in spec.bontas] if with_group else []
    dims_needed += [cat.dimensions[d] for d in spec.filters]
    cols: list[exp.Expression] = []
    if with_group:
        dim = cat.dimensions[spec.bontas[0]]
        cols.append(exp.alias_(_frag(dim.sql), "bontas"))
    cols.append(exp.alias_(_frag(metric.sql), "ertek"))
    cols.append(exp.alias_(exp.Count(this=exp.Star()), "rendelesek"))
    if metric.alap:
        cols.append(exp.alias_(_frag(metric.alap), "alap"))
    if metric.szamlalo:
        cols.append(exp.alias_(_frag(metric.szamlalo), "szamlalo"))

    q = exp.select(*cols).from_(exp.alias_(exp.to_table(cat.fact), cat.alias, table=True))
    joined: list[str] = []
    for dim in dims_needed:
        if dim.kapcsolat and dim.kapcsolat not in joined:
            j = cat.joins[dim.kapcsolat]
            q = q.join(exp.alias_(exp.to_table(dim.kapcsolat), j["alias"], table=True),
                       on=_frag(j["on"]), join_type="left")
            joined.append(dim.kapcsolat)

    conds: list[exp.Expression] = []
    datum = _frag(cat.settings["datum"])
    if spec.tol:
        conds.append(exp.GTE(this=datum.copy(), expression=exp.cast(exp.Literal.string(spec.tol.isoformat()), "DATE")))
    if spec.ig:
        conds.append(exp.LTE(this=datum.copy(), expression=exp.cast(exp.Literal.string(spec.ig.isoformat()), "DATE")))
    for dim_id, values in spec.szuro:
        dim = cat.dimensions[dim_id]
        conds.append(exp.In(this=_frag(dim.sql), expressions=[_literal(dim, v) for v in values]))
    if conds:
        q = q.where(exp.and_(*conds))

    if with_group:
        dim = cat.dimensions[spec.bontas[0]]
        q = q.group_by(_frag(dim.sql))
        if spec.rendezes == "bontas":
            q = q.order_by(exp.Ordered(this=_dim_order(dim), desc=False, nulls_first=False))
        else:   # érték szerint; egyezésnél a kulcs dönt, hogy a sorrend mindig ugyanaz legyen
            q = q.order_by(exp.Ordered(this=exp.column("ertek"), desc=spec.rendezes == "ertek_csokkeno",
                                       nulls_first=False),
                           exp.Ordered(this=exp.column("bontas"), desc=False, nulls_first=False))
    return q


def _sql(q: exp.Select, dialect: str) -> str:
    return q.sql(dialect=dialect, pretty=True)


def build(spec: QuerySpec, cat: Catalog) -> BuiltQuery:
    total = _select(spec, cat, with_group=False)
    groups = _select(spec, cat, with_group=True) if spec.bontas else None
    built = BuiltQuery(total=_sql(total, DIALECT), groups=_sql(groups, DIALECT) if groups else None,
                       total_pg=_sql(total, "postgres"),
                       groups_pg=_sql(groups, "postgres") if groups else None)
    for sql in (built.total, built.groups):
        if sql:
            guard(sql, cat)
    return built


def guard(sql: str, cat: Catalog) -> None:
    """A kész SQL utólagos ellenőrzése (a KAPU ① része): ha bármi gyanús, nem fut le."""
    try:
        trees = sqlglot.parse(sql, read=DIALECT)
    except sqlglot.errors.ParseError as exc:
        raise UnsafeSQL(f"Az SQL nem értelmezhető: {exc}") from exc
    if len(trees) != 1 or trees[0] is None:
        raise UnsafeSQL("Pontosan egy utasítás lehet.")
    tree = trees[0]
    if not isinstance(tree, exp.Select):
        raise UnsafeSQL(f"Csak SELECT futhat (ez: {type(tree).__name__}).")
    bad = [type(n).__name__ for n in tree.walk() if isinstance(n, FORBIDDEN)]
    if bad:
        raise UnsafeSQL(f"Tiltott elem az SQL-ben: {', '.join(sorted(set(bad)))}.")
    if any(isinstance(n, (exp.Subquery, exp.Union)) for n in tree.walk()):
        raise UnsafeSQL("Allekérdezés és UNION nem lehet az SQL-ben.")
    tables = {t.name for t in tree.find_all(exp.Table)}
    unknown = tables - cat.tables()
    if unknown:
        raise UnsafeSQL(f"Ismeretlen tábla: {', '.join(sorted(unknown))}.")
    aliases = {cat.alias} | {j["alias"] for j in cat.joins.values()}
    outputs = {"bontas", "ertek", "rendelesek", "alap", "szamlalo"}
    for col in tree.find_all(exp.Column):
        if col.table and col.table not in aliases:
            raise UnsafeSQL(f"Ismeretlen táblanév az oszlopnál: {col.table}.{col.name}.")
        if not col.table and col.name not in outputs:
            raise UnsafeSQL(f"Tábla nélküli oszlop: {col.name}.")
