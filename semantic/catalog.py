"""
A metrikakatalógus (semantic/katalogus.toml) betöltése és ellenőrzése, az adatból
generált fehérlista (P7) és a dimenzióértékek emberi nevei.

A katalógus a rendszer szerződése: a KAPU ① csak az itt felsorolt mérőszámot, bontást és
szűrőt engedi át, a szűrők értékeit pedig a tárházban ténylegesen előforduló értékekhez
méri. A katalógus SQL-töredékei megbízható forrásból (ebből a fájlból) jönnek; a
felhasználótól (később a nyelvi modelltől) csak azonosítók és fehérlistás értékek
érkezhetnek.
"""

from __future__ import annotations

import hashlib
import tomllib
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import sqlglot

from xai import labels

KATALOGUS = Path(__file__).with_name("katalogus.toml")
UNITS = {"darab", "arany", "nap", "brl", "km"}
DIMENSION_TYPES = {"szoveg", "egesz", "datum"}
SORT_ORDERS = ("ertek_csokkeno", "ertek_novekvo", "bontas")

KESETT_LABELS = {"kesett": "késett", "idoben": "időben érkezett"}
WEEKDAYS = ["hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap"]
MONTHS = ["január", "február", "március", "április", "május", "június", "július", "augusztus",
          "szeptember", "október", "november", "december"]


class CatalogError(ValueError):
    """A katalógusfájl hibás — a rendszer ilyenkor el sem indul."""


@dataclass(frozen=True)
class Metric:
    id: str
    nev: str
    leiras: str
    sql: str
    egyseg: str
    tizedes: int
    min_csoport: int
    alap: str | None = None              # hány rendelésből számolódik (ha nem az összes)
    alap_nev: str = "rendelés"
    szamlalo: str | None = None          # aránynál a számláló (a 95%-os Wilson-tartományhoz)
    tiltott_dimenzio: tuple[str, ...] = ()   # ezek szerint nem bontható és nem szűrhető
    osszeadhato: bool = False            # darab, összeg: a csoportok az egészre összeadódnak

    @property
    def is_rate(self) -> bool:
        return self.egyseg == "arany"


@dataclass(frozen=True)
class Dimension:
    id: str
    nev: str
    rovid: str
    sql: str
    kapcsolat: str | None
    ertekek: str | tuple[str, ...]       # "adat" | "ido" | rögzített lista
    szurheto: bool
    tipus: str = "szoveg"
    szerint: str = ""                    # a válasz bontásmondatának eleje: „a vevő állama szerint”
    termeszetes_sorrend: bool = True     # van-e értelme „a bontás sorrendjében” rendezni


@dataclass(frozen=True)
class Unavailable:
    kulcsszavak: tuple[str, ...]
    indok: str
    helyette: tuple[str, ...]


@dataclass(frozen=True)
class Catalog:
    settings: dict
    joins: dict
    metrics: dict
    dimensions: dict
    unavailable: tuple
    sha256: str

    @property
    def fact(self) -> str:
        return self.settings["tenytabla"]

    @property
    def alias(self) -> str:
        return self.settings["alias"]

    def tables(self) -> set[str]:
        return {self.fact, *self.joins}


def _req(d: dict, key: str, where: str):
    if key not in d:
        raise CatalogError(f"{where}: hiányzik a(z) „{key}” mező")
    return d[key]


def _parses(fragment: str, where: str) -> None:
    try:
        sqlglot.parse_one(f"SELECT {fragment} FROM t", read="duckdb")
    except sqlglot.errors.ParseError as exc:
        raise CatalogError(f"{where}: az SQL-töredék nem értelmezhető: {fragment!r}") from exc


def load(path: Path = KATALOGUS) -> Catalog:
    raw_bytes = Path(path).read_bytes()
    raw = tomllib.loads(raw_bytes.decode("utf-8"))
    settings = _req(raw, "beallitasok", "katalógus")
    for key in ("tenytabla", "alias", "datum", "alap_limit", "max_limit", "max_szuroertek",
                "max_bontas"):
        _req(settings, key, "beallitasok")
    joins = raw.get("kapcsolat", {})
    for name, j in joins.items():
        _req(j, "alias", f"kapcsolat.{name}")
        _req(j, "on", f"kapcsolat.{name}")

    metrics: dict[str, Metric] = {}
    for m in _req(raw, "metrika", "katalógus"):
        where = f"metrika {m.get('id', '?')}"
        mid = _req(m, "id", where)
        if mid in metrics:
            raise CatalogError(f"{where}: kétszer szerepel")
        metric = Metric(id=mid, nev=_req(m, "nev", where), leiras=_req(m, "leiras", where),
                        sql=_req(m, "sql", where), egyseg=_req(m, "egyseg", where),
                        tizedes=int(_req(m, "tizedes", where)),
                        min_csoport=int(_req(m, "min_csoport", where)),
                        alap=m.get("alap"), alap_nev=m.get("alap_nev", "rendelés"),
                        szamlalo=m.get("szamlalo"),
                        tiltott_dimenzio=tuple(m.get("tiltott_dimenzio", ())),
                        osszeadhato=bool(m.get("osszeadhato", False)))
        if metric.egyseg not in UNITS:
            raise CatalogError(f"{where}: ismeretlen egység {metric.egyseg!r}")
        if metric.is_rate and not metric.szamlalo:
            raise CatalogError(f"{where}: aránynál kötelező a „szamlalo” (a 95%-os tartományhoz)")
        for frag in (metric.sql, metric.alap, metric.szamlalo):
            if frag:
                _parses(frag, where)
        metrics[mid] = metric

    dims: dict[str, Dimension] = {}
    for d in _req(raw, "dimenzio", "katalógus"):
        where = f"dimenzio {d.get('id', '?')}"
        did = _req(d, "id", where)
        if did in dims or did in metrics:
            raise CatalogError(f"{where}: az azonosító már foglalt")
        values = _req(d, "ertekek", where)
        values = values if isinstance(values, str) else tuple(str(v) for v in values)
        if isinstance(values, str) and values not in ("adat", "ido"):
            raise CatalogError(f"{where}: az „ertekek” értéke „adat”, „ido” vagy egy lista lehet")
        nev = _req(d, "nev", where)
        dim = Dimension(id=did, nev=nev, rovid=_req(d, "rovid", where),
                        sql=_req(d, "sql", where), kapcsolat=d.get("kapcsolat"), ertekek=values,
                        szurheto=bool(_req(d, "szurheto", where)), tipus=d.get("tipus", "szoveg"),
                        szerint=d.get("szerint") or f"{nev} szerint",
                        termeszetes_sorrend=bool(d.get("termeszetes_sorrend", True)))
        if dim.kapcsolat and dim.kapcsolat not in joins:
            raise CatalogError(f"{where}: ismeretlen kapcsolat {dim.kapcsolat!r}")
        if dim.tipus not in DIMENSION_TYPES:
            raise CatalogError(f"{where}: ismeretlen típus {dim.tipus!r}")
        if dim.szurheto and dim.ertekek == "ido":
            raise CatalogError(f"{where}: időbeli bontás nem szűrhető (az időablak szűr)")
        _parses(dim.sql, where)
        dims[did] = dim

    for metric in metrics.values():
        unknown = [d for d in metric.tiltott_dimenzio if d not in dims]
        if unknown:
            raise CatalogError(f"metrika {metric.id}: ismeretlen tiltott dimenzió: {unknown}")

    unavailable = []
    for u in raw.get("nem_elerheto", []):
        item = Unavailable(kulcsszavak=tuple(_req(u, "kulcsszavak", "nem_elerheto")),
                           indok=_req(u, "indok", "nem_elerheto"),
                           helyette=tuple(_req(u, "helyette", "nem_elerheto")))
        missing = [h for h in item.helyette if h not in metrics]
        if missing:
            raise CatalogError(f"nem_elerheto: a javasolt mérőszám nincs a katalógusban: {missing}")
        unavailable.append(item)

    # az ujjlenyomat sorvégfüggetlen: Windowson a git CRLF-fel írhatja ki ugyanezt a fájlt
    digest = hashlib.sha256(raw_bytes.replace(b"\r\n", b"\n")).hexdigest()
    return Catalog(settings=settings, joins=joins, metrics=metrics, dimensions=dims,
                   unavailable=tuple(unavailable), sha256=digest)


# ------------------------------------------------------------------ fehérlista (P7)
@dataclass(frozen=True)
class Whitelist:
    """Az adatban ténylegesen előforduló szűrőértékek és az adat időtartománya."""
    values: dict                  # dimenzió → a megengedett (kanonikus) értékek
    date_min: date
    date_max: date
    source: str = ""              # valós | szintetikus
    built: str = ""


def _from_clause(cat: Catalog, dim: Dimension | None = None) -> str:
    sql = f"FROM {cat.fact} AS {cat.alias}"
    if dim is not None and dim.kapcsolat:
        j = cat.joins[dim.kapcsolat]
        sql += f" LEFT JOIN {dim.kapcsolat} AS {j['alias']} ON {j['on']}"
    return sql


def whitelist(cat: Catalog, con) -> Whitelist:
    """A szűrők megengedett értékei — az adatból (SELECT DISTINCT), nem kézzel írt listából."""
    values = {}
    for dim in cat.dimensions.values():
        if not dim.szurheto:
            continue
        if dim.ertekek == "adat":
            rows = con.execute(f"SELECT DISTINCT {dim.sql} AS v {_from_clause(cat, dim)} "
                               f"WHERE {dim.sql} IS NOT NULL ORDER BY 1").fetchall()
            values[dim.id] = tuple(str(r[0]) for r in rows)
        else:
            values[dim.id] = tuple(dim.ertekek)
    lo, hi = con.execute(f"SELECT min({cat.settings['datum']}), max({cat.settings['datum']}) "
                         f"FROM {cat.fact} AS {cat.alias}").fetchone()
    source = built = ""
    try:
        source, built = con.execute("SELECT adatforras, epitve FROM meta_build").fetchone()
    except Exception:   # noqa: BLE001 — a meta tábla hiánya nem akadálya a lekérdezésnek
        pass
    return Whitelist(values=values, date_min=_as_date(lo), date_max=_as_date(hi),
                     source=str(source or ""), built=str(built or ""))


def _as_date(v) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


# -------------------------------------------------------------- emberi nevek
def fmt_long_date(d: date) -> str:
    """„2018. január 1."."""
    return f"{d.year}. {MONTHS[d.month - 1]} {d.day}."


def value_label(cat: Catalog, dim_id: str, key) -> str:
    """Egy dimenzióérték neve a felületen és a válaszban: „São Paulo (SP)”, „Délkelet”…"""
    if key is None:
        if dim_id in ("vevo_allam", "elado_allam"):
            return labels.state_label(None)
        return labels.category_name(None) if dim_id == "kategoria" else "ismeretlen"
    if dim_id in ("vevo_allam", "elado_allam"):
        return labels.state_label(key)
    if dim_id == "vevo_regio":
        return labels.REGIONS.get(str(key), str(key))
    if dim_id == "kategoria":
        return labels.category_name(key)
    if dim_id == "kesett":
        return KESETT_LABELS.get(str(key), str(key))
    if dim_id == "het_napja":
        return WEEKDAYS[int(key) - 1]
    if dim_id == "honap":
        d = _as_date(key)
        return f"{d.year}. {MONTHS[d.month - 1]}"
    if dim_id == "ev":
        return str(int(key))
    return str(key)


def _fold(text: str) -> str:
    """Kis- és nagybetű-, ékezet- és szóközfüggetlen alak az értékek összevetéséhez."""
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    return " ".join(t.lower().replace("_", " ").split())


def value_aliases(cat: Catalog, dim_id: str, key: str) -> set[str]:
    """Egy kanonikus érték elfogadott írásmódjai (a kód, a név, a felületi címke)."""
    out = {_fold(key)}
    if dim_id in ("vevo_allam", "elado_allam"):
        out |= {_fold(labels.state_name(key)), _fold(labels.state_label(key))}
    elif dim_id in ("vevo_regio", "kategoria", "kesett", "het_napja"):
        out.add(_fold(value_label(cat, dim_id, key)))
    return out


def normalize_value(cat: Catalog, wl: Whitelist, dim_id: str, raw) -> str | None:
    """A kérdésben szereplő érték kanonikus alakja, ha szerepel a fehérlistán; különben None."""
    allowed = wl.values.get(dim_id, ())
    s = str(raw).strip()
    if s in allowed:
        return s
    folded = _fold(s)
    for key in allowed:
        if folded in value_aliases(cat, dim_id, key):
            return key
    return None
