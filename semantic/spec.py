"""
A kérdés gépi alakja (QuerySpec) és a KAPU ① — rendszerterv 15. és 16. (V-2).

Egy kérdés gépi alakja:

    {"metrika": "kesesi_arany", "bontas": ["vevo_allam"],
     "szuro": {"kategoria": ["health_beauty"]},
     "idoablak": {"tol": "2018-01-01", "ig": "2018-06-30"},
     "rendezes": "ertek_csokkeno", "limit": 5}

A KAPU ① ezt a metrikakatalógushoz és az adatból generált fehérlistához méri:

  * csak katalógusban szereplő mérőszám, bontás és szűrő mehet át — szabad SQL soha;
  * a szűrők értékeinek a tárházban ténylegesen elő kell fordulniuk (P7); a kérdésben
    szereplő írásmód („Sao Paulo”, „sp”, „São Paulo (SP)”) a kanonikus kódra fordul;
  * az időablaknak az adat tartományába kell esnie (ha csak részben esik bele, rá szűkül,
    és erről megjegyzés kerül a válaszba);
  * ami nem felel meg, arra INDOKOLT ELUTASÍTÁS jön (kód + magyar üzenet + javaslatok),
    és a rendszer nem mond számot (UC-2, F-2).

Elfogadás esetén a normalizált specifikáció (kanonikus értékek, kitöltött
alapértelmezések) megy tovább — ebből determinisztikusan épül az SQL (builder.py).
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from datetime import date

from semantic.catalog import (SORT_ORDERS, Catalog, Whitelist, _fold, fmt_long_date,
                              normalize_value, value_aliases, value_label)

FIELDS = ("metrika", "bontas", "szuro", "idoablak", "rendezes", "limit")
SORT_NAMES = {"ertek_csokkeno": "érték szerint csökkenő", "ertek_novekvo": "érték szerint növekvő",
              "bontas": "a bontás sorrendjében"}
_VOWELS = set("aáeéiíoóöőuúüű")


def az(word: str) -> str:
    """A magyar névelő: „az eladó állama”, „a vevő állama”."""
    return "az" if word[:1].lower() in _VOWELS else "a"


# ---------------------------------------------------------------- a specifikáció
@dataclass(frozen=True)
class QuerySpec:
    metrika: str
    bontas: tuple[str, ...] = ()
    szuro: tuple[tuple[str, tuple[str, ...]], ...] = ()   # (dimenzió, kanonikus értékek), rendezve
    tol: date | None = None
    ig: date | None = None
    rendezes: str = "ertek_csokkeno"
    limit: int = 10

    def to_dict(self) -> dict:
        """A kanonikus (normalizált) alak — ezt mutatja a felület, ez a gyorsítótár kulcsa."""
        out: dict = {"metrika": self.metrika, "bontas": list(self.bontas),
                     "szuro": {d: list(v) for d, v in self.szuro}}
        if self.tol or self.ig:
            out["idoablak"] = {k: v.isoformat() for k, v in (("tol", self.tol), ("ig", self.ig)) if v}
        out["rendezes"] = self.rendezes
        out["limit"] = self.limit
        return out

    def key(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @property
    def filters(self) -> dict[str, tuple[str, ...]]:
        return dict(self.szuro)


@dataclass(frozen=True)
class Rejection:
    """Indokolt elutasítás: a felület ezt mutatja, szám nélkül."""
    kod: str
    uzenet: str
    mezo: str | None = None
    javaslatok: tuple[str, ...] = ()        # azonosítók (mérőszám, dimenzió vagy érték)


@dataclass(frozen=True)
class GateResult:
    ok: bool
    spec: QuerySpec | None = None
    elutasitas: Rejection | None = None
    megjegyzesek: tuple[str, ...] = field(default=())   # kódok, pl. "idoablak_szukitve"

    @property
    def status(self) -> str:
        return "elfogadva" if self.ok else f"elutasítva ({self.elutasitas.kod})"


class _Reject(Exception):
    def __init__(self, kod: str, uzenet: str, mezo: str | None = None, javaslatok=()):
        super().__init__(uzenet)
        self.rejection = Rejection(kod, uzenet, mezo, tuple(javaslatok))


# ------------------------------------------------------------------ segédek
def _names(items) -> str:
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " és " + items[-1]


def _quote(x) -> str:
    return f"„{x}”"


def _close(word: str, candidates: dict[str, str], n: int = 3) -> list[str]:
    """A beírt szóhoz legközelebbi azonosítók (kis- és nagybetű-, ékezet- és szóközfüggetlenül).
    candidates: összehasonlítandó alak → azonosító."""
    hits = difflib.get_close_matches(_fold(word), list(candidates), n=n * 3, cutoff=0.6)
    out: list[str] = []
    for h in hits:
        if candidates[h] not in out:
            out.append(candidates[h])
    return out[:n]


def metric_candidates(cat: Catalog) -> dict[str, str]:
    c = {}
    for m in cat.metrics.values():
        c[_fold(m.id)] = m.id
        c[_fold(m.nev)] = m.id
    return c


def unavailable_hit(cat: Catalog, text: str):
    """Ha a kért mérőszám olyasmi, amit az adat nem tud (haszon, értékelés, fizetés …)."""
    folded = _fold(text)
    for u in cat.unavailable:
        if any(_fold(k) in folded for k in u.kulcsszavak):
            return u
    return None


def _metric(cat: Catalog, raw):
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise _Reject("hianyzo_metrika", "Nem derül ki, mit mérjünk: a „metrika” mező hiányzik.", "metrika")
    if not isinstance(raw, str):
        raise _Reject("formatum", "A „metrika” mező egy mérőszám azonosítója kell legyen (szöveg).",
                      "metrika")
    if raw in cat.metrics:
        return cat.metrics[raw]
    u = unavailable_hit(cat, raw)
    if u is not None:
        alt = [cat.metrics[h].nev for h in u.helyette]
        raise _Reject("nem_elerheto", f"Ezt nem tudom kiszámolni: {u.indok}. "
                      f"Ami közel áll hozzá: {_names(alt)}.", "metrika", u.helyette)
    close = _close(raw, metric_candidates(cat))
    tip = (f" Ami közel áll hozzá: {_names(cat.metrics[c].nev for c in close)}." if close else
           f" A katalógusban szereplő mérőszámok: {_names(m.nev for m in cat.metrics.values())}.")
    raise _Reject("ismeretlen_metrika",
                  f"Ezt nem tudom kiszámolni: {_quote(raw)} nincs a metrikakatalógusban.{tip}",
                  "metrika", close)


def _dimension(cat: Catalog, raw, field_name: str):
    if not isinstance(raw, str) or raw not in cat.dimensions:
        cands = {}
        for d in cat.dimensions.values():
            cands[_fold(d.id)] = d.id
            cands[_fold(d.rovid)] = d.id
        close = _close(str(raw), cands)
        kind = "bontás" if field_name == "bontas" else "szűrő"
        allowed = [d.rovid for d in cat.dimensions.values() if field_name == "bontas" or d.szurheto]
        tip = (f" Talán: {_names(cat.dimensions[c].rovid for c in close)}." if close else
               f" Lehetséges: {_names(allowed)}.")
        raise _Reject(f"ismeretlen_{'bontas' if field_name == 'bontas' else 'szuro'}",
                      f"Ilyen {kind} nincs: {_quote(raw)}.{tip}", field_name, close)
    return cat.dimensions[raw]


def _forbidden(metric, dim, field_name: str) -> None:
    if dim.id in metric.tiltott_dimenzio:
        raise _Reject("tiltott_kombinacio",
                      f"{az(metric.nev).capitalize()} {metric.nev} a késésből számolódik, ezért nem "
                      f"{'bontható' if field_name == 'bontas' else 'szűrhető'} aszerint, hogy a "
                      "rendelés késett-e (az eredmény definíció szerint 0 vagy 100% lenne).",
                      field_name)


def _as_list(raw, field_name: str) -> list:
    if raw is None:
        return []
    if isinstance(raw, (str, int)) and not isinstance(raw, bool):
        return [raw]
    if isinstance(raw, (list, tuple)):
        return list(raw)
    raise _Reject("formatum", f"A(z) {_quote(field_name)} mező értéke szöveg vagy lista lehet.", field_name)


def _parse_date(raw, field_name: str) -> date | None:
    if raw is None or raw == "":
        return None
    try:
        return date.fromisoformat(str(raw).strip())
    except ValueError:
        raise _Reject("ervenytelen_datum", f"Érvénytelen dátum: {_quote(raw)} — ÉÉÉÉ-HH-NN alakot "
                      "vártam (például 2018-01-31).", field_name) from None


def _value_candidates(cat: Catalog, wl: Whitelist, dim_id: str) -> dict[str, str]:
    c = {}
    for key in wl.values.get(dim_id, ()):
        for alias in value_aliases(cat, dim_id, key):
            c[alias] = key
    return c


# ----------------------------------------------------------------- a kapu
def check(raw, cat: Catalog, wl: Whitelist) -> GateResult:
    """KAPU ①: a beérkező specifikáció ellenőrzése és normalizálása."""
    try:
        spec, notes = _check(raw, cat, wl)
        return GateResult(True, spec, None, tuple(notes))
    except _Reject as r:
        return GateResult(False, None, r.rejection)


def _check(raw, cat: Catalog, wl: Whitelist):
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raise _Reject("formatum", "A kérdés gépi alakja nem értelmezhető: egy JSON-objektumot "
                          "vártam (kulcs–érték párokat kapcsos zárójelben).") from None
    if not isinstance(raw, dict):
        raise _Reject("formatum", "A kérdés gépi alakja nem értelmezhető: egy JSON-objektumot "
                      "vártam (kulcs–érték párokat kapcsos zárójelben).")
    unknown = [k for k in raw if k not in FIELDS]
    if unknown:
        raise _Reject("ismeretlen_mezo", f"Ismeretlen mező a kérdésben: {_names(map(_quote, unknown))}. "
                      f"Megengedett mezők: {_names(FIELDS)}.", unknown[0])
    s = cat.settings
    notes: list[str] = []

    metric = _metric(cat, raw.get("metrika"))

    # ------------------------------------------------------------ bontás
    dims = []
    for d in _as_list(raw.get("bontas"), "bontas"):
        dim = _dimension(cat, d, "bontas")
        _forbidden(metric, dim, "bontas")
        if dim.id not in dims:
            dims.append(dim.id)
    if len(dims) > int(s["max_bontas"]):
        raise _Reject("tul_sok_bontas", f"Egyszerre legfeljebb {s['max_bontas']} bontás lehet "
                      f"(a kérdésben {len(dims)} van).", "bontas")

    # ------------------------------------------------------------- szűrők
    filters: dict[str, tuple[str, ...]] = {}
    szuro = raw.get("szuro") or {}
    if not isinstance(szuro, dict):
        raise _Reject("formatum", "A „szuro” mező dimenzió → érték(ek) párokat várt.", "szuro")
    for d, vals in szuro.items():
        dim = _dimension(cat, d, "szuro")
        if not dim.szurheto:
            raise _Reject("nem_szurheto", f"{az(dim.nev).capitalize()} {dim.nev} szerint nem lehet szűrni; "
                          "az időszakot az időablak adja meg („tol”, „ig”).", "szuro")
        _forbidden(metric, dim, "szuro")
        vals = _as_list(vals, "szuro")
        if not vals:
            raise _Reject("ures_szuro", f"A(z) {dim.rovid} szűrőben nincs egyetlen érték sem.", "szuro")
        if len(vals) > int(s["max_szuroertek"]):
            raise _Reject("tul_sok_ertek", f"Egy szűrőben legfeljebb {s['max_szuroertek']} érték lehet "
                          f"(a(z) {dim.rovid} szűrőben {len(vals)} van).", "szuro")
        keys = []
        for v in vals:
            key = normalize_value(cat, wl, dim.id, v)
            if key is None:
                close = _close(str(v), _value_candidates(cat, wl, dim.id))
                tip = (f" Talán: {_names(value_label(cat, dim.id, c) for c in close)}." if close else "")
                raise _Reject("ismeretlen_ertek", f"{_quote(v)} nem szerepel az adatban "
                              f"({dim.nev}).{tip}", "szuro", close)
            if key not in keys:
                keys.append(key)
        filters[dim.id] = tuple(sorted(keys, key=lambda k: wl.values[dim.id].index(k)))

    # ----------------------------------------------------------- időablak
    window = raw.get("idoablak") or {}
    if not isinstance(window, dict) or any(k not in ("tol", "ig") for k in window):
        raise _Reject("formatum", "Az „idoablak” mező egy {\"tol\": …, \"ig\": …} objektum lehet.",
                      "idoablak")
    tol, ig = _parse_date(window.get("tol"), "idoablak"), _parse_date(window.get("ig"), "idoablak")
    if tol and ig and tol > ig:
        raise _Reject("forditott_idoablak", f"Az időablak eleje ({fmt_long_date(tol)}) későbbi, mint "
                      f"a vége ({fmt_long_date(ig)}).", "idoablak")
    span = f"{fmt_long_date(wl.date_min)} és {fmt_long_date(wl.date_max)}"
    if (tol and tol > wl.date_max) or (ig and ig < wl.date_min):
        raise _Reject("adaton_kivuli_idoablak", f"Erre az időszakra nincs adat: a kézbesített "
                      f"rendelések {span} között vannak.", "idoablak")
    if (tol and tol < wl.date_min) or (ig and ig > wl.date_max):
        notes.append("idoablak_szukitve")          # a válasz a payloadból mondja ki (dátumokkal)
        tol = max(tol, wl.date_min) if tol else None
        ig = min(ig, wl.date_max) if ig else None
    if tol == wl.date_min:
        tol = None
    if ig == wl.date_max:
        ig = None

    # ------------------------------------------------- rendezés és limit
    time_like = bool(dims) and (cat.dimensions[dims[0]].ertekek == "ido" or dims[0] == "het_napja")
    order = raw.get("rendezes") or ("bontas" if time_like else "ertek_csokkeno")
    if order not in SORT_ORDERS:
        raise _Reject("ervenytelen_rendezes", f"Ismeretlen rendezés: {_quote(order)}. Lehetséges: "
                      f"{_names(SORT_ORDERS)}.", "rendezes")
    if order == "bontas" and dims and not cat.dimensions[dims[0]].termeszetes_sorrend:
        rovid = cat.dimensions[dims[0]].rovid
        raise _Reject("ervenytelen_rendezes", f"{az(rovid).capitalize()} {rovid} értékeinek nincs "
                      "természetes sorrendje — rendezz érték szerint („ertek_csokkeno” vagy "
                      "„ertek_novekvo”).", "rendezes", ("ertek_csokkeno", "ertek_novekvo"))
    limit = raw.get("limit")
    if limit is None:
        limit = int(s["max_limit"]) if time_like else int(s["alap_limit"])
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= int(s["max_limit"]):
        raise _Reject("ervenytelen_limit", f"A „limit” 1 és {s['max_limit']} közötti egész szám lehet.",
                      "limit")

    spec = QuerySpec(metrika=metric.id, bontas=tuple(dims),
                     szuro=tuple(sorted(filters.items())), tol=tol, ig=ig,
                     rendezes=order, limit=int(limit))
    return spec, notes
