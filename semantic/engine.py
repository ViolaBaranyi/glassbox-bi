"""
A lekérdezés futtatása és az eredmény (MetricResult) — a determinisztikus réteg kimenete.

Minden szám, amit a Kérdezz oldal kimond, ebből a payloadból jön: a sablonos válasz is,
és később a nyelvi modell is csak ezt látja (rendszerterv 15.). A payload tartalmazza a
lefuttatott SQL-t is, hogy minden szám visszavezethető legyen (F-9, NF-3).

Ugyanarra a specifikációra az eredmény bitre azonos (F-3) — az időmérés kivételével.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from pipeline.cohort_report import wilson
from semantic import builder
from semantic.catalog import Catalog, Whitelist, value_label
from semantic.spec import QuerySpec


@dataclass
class MetricResult:
    spec: QuerySpec
    metrika: dict
    bontas: dict | None
    idoablak: dict
    szurok: list[dict]
    osszesen: dict
    sorok: list[dict]
    sql: dict
    sql_postgres: dict
    megjegyzesek: list[str]
    adat: dict
    ido_ms: float = field(default=0.0, compare=False)

    def to_payload(self) -> dict:
        return {"kerdes": self.spec.to_dict(), "metrika": self.metrika, "bontas": self.bontas,
                "idoablak": self.idoablak, "szurok": self.szurok, "osszesen": self.osszesen,
                "sorok": self.sorok, "sql": self.sql, "sql_postgres": self.sql_postgres,
                "megjegyzesek": self.megjegyzesek, "adat": self.adat}

    @property
    def empty(self) -> bool:
        return self.osszesen["rendelesek"] == 0

    def shown_rows(self) -> list[dict]:
        """A rangsorba / ábrába kerülő sorok: a megbízhatók a rendezés szerint, legfeljebb
        `limit` darab (időbeli bontásnál az összes megbízható, időrendben)."""
        rows = [r for r in self.sorok if not r["keves_adat"] and r["ertek"] is not None]
        return rows[: self.spec.limit]


def _num(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v) if isinstance(v, float) else int(v)
    return float(v)


def _key(dim, v) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _row(metric, rec: dict, total_value=None) -> dict:
    n = int(rec["rendelesek"])
    base = int(rec["alap"]) if "alap" in rec and rec["alap"] is not None else n
    out = {"ertek": _num(rec["ertek"]), "rendelesek": n}
    if metric.alap:
        out["alap"] = base
    if metric.szamlalo:
        k = int(rec["szamlalo"] or 0)
        out["szamlalo"] = k
        lo, hi = wilson(k, n) if n else (None, None)
        out["ci"] = [lo, hi]
    out["keves_adat"] = bool(base < metric.min_csoport)
    if total_value not in (None, 0) and out["ertek"] is not None:
        # összeadható mérőszámnál a csoport részesedése az egészből, egyébként az összesített
        # érték hányszorosa (pl. a késési arány az átlag 3,2-szerese)
        out["reszesedes" if metric.osszeadhato else "relativ"] = out["ertek"] / total_value
    return out


def _fetch(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def run(spec: QuerySpec, cat: Catalog, wl: Whitelist, con, notes=()) -> MetricResult:
    """Lefuttatja az elfogadott specifikációt a tárházon (csak olvasás)."""
    t0 = time.perf_counter()
    metric = cat.metrics[spec.metrika]
    built = builder.build(spec, cat)
    total_rec = _fetch(con, built.total)[0]
    total = _row(metric, total_rec)
    rows: list[dict] = []
    dim = cat.dimensions[spec.bontas[0]] if spec.bontas else None
    if built.groups:
        for rec in _fetch(con, built.groups):
            r = _row(metric, rec, total["ertek"])
            key = _key(dim, rec["bontas"])
            rows.append({"kulcs": key, "megnevezes": value_label(cat, dim.id, key), **r})
    elapsed = (time.perf_counter() - t0) * 1000.0

    tol, ig = spec.tol or wl.date_min, spec.ig or wl.date_max
    return MetricResult(
        spec=spec,
        metrika={"id": metric.id, "nev": metric.nev, "leiras": metric.leiras, "egyseg": metric.egyseg,
                 "tizedes": metric.tizedes, "min_csoport": metric.min_csoport,
                 "osszeadhato": metric.osszeadhato,
                 "alap_nev": metric.alap_nev if metric.alap else "rendelés"},
        bontas={"id": dim.id, "nev": dim.nev, "rovid": dim.rovid, "szerint": dim.szerint} if dim else None,
        idoablak={"tol": tol.isoformat(), "ig": ig.isoformat(),
                  "teljes": spec.tol is None and spec.ig is None},
        szurok=[{"dimenzio": d, "nev": cat.dimensions[d].nev, "rovid": cat.dimensions[d].rovid,
                 "ertekek": list(v), "cimkek": [value_label(cat, d, x) for x in v]}
                for d, v in spec.szuro],
        osszesen=total,
        sorok=rows,
        sql={"osszesen": built.total, "bontas": built.groups},
        sql_postgres={"osszesen": built.total_pg, "bontas": built.groups_pg},
        megjegyzesek=list(notes),
        adat={"forras": wl.source, "epitve": wl.built, "tol": wl.date_min.isoformat(),
              "ig": wl.date_max.isoformat(), "katalogus_sha256": cat.sha256},
        ido_ms=elapsed,
    )
