"""
Sablonos válasz a MetricResultból — nyelvi modell nélkül (a kísérlet viszonyítási ága).

Minden szám a payloadból jön, és a behelyettesítést a kód végzi („hely-kitöltés”): a
szöveg minden számához feljegyezzük, a payload melyik mezőjéből származik
(`hivatkozasok`). A `fedetlen_szamok` ugyanazt nézi, amit később a KAPU ② a nyelvi
modell szövegén: marad-e a szövegben olyan szám, amely nem vezethető vissza. A sablonos
válasznál ez szerkezetileg mindig üres — ezt teszt őrzi.

Szerkezet (rendszerterv 14., hívás ②): hatókör → állítás → bontás → korlát.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from semantic.catalog import fmt_long_date
from semantic.engine import MetricResult
from semantic.spec import az
from xai import narrative as nv

CONFIDENCE = "95%-os"            # a tartományok szintje — rögzített érték, nem a payloadból
UNIT_WORDS = {"nap": "nap", "brl": "BRL", "km": "km"}
_NUMBER = re.compile(r"\d+(?:[\u00a0\u202f]\d{3})*(?:,\d+)?")   # magyar számalak: ezres tagolás nem törő szóközzel


@dataclass
class Answer:
    text: str
    hivatkozasok: list[tuple[str, str]] = field(default_factory=list)   # (a szövegben, payload-útvonal)

    def fedetlen_szamok(self) -> list[str]:
        return uncovered_numbers(self.text, self.hivatkozasok)


def uncovered_numbers(text: str, refs) -> list[str]:
    """A szöveg számai közül azok, amelyek nem vezethetők vissza a hivatkozásokra."""
    rest = text
    for shown, _ in sorted(refs, key=lambda r: -len(r[0])):
        rest = rest.replace(shown, " ")
    return _NUMBER.findall(rest)


def fmt_value(metric: dict, v: float) -> str:
    unit, digits = metric["egyseg"], int(metric["tizedes"])
    if unit == "arany":
        return nv.fmt_pct(v, digits)
    text = nv.fmt_num(v, digits)
    return f"{text} {UNIT_WORDS[unit]}" if unit in UNIT_WORDS else text


def fmt_count(n: int) -> str:
    return nv.fmt_num(n, 0)


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


class _Writer:
    def __init__(self, r: MetricResult):
        self.r = r
        self.refs: list[tuple[str, str]] = []
        self.parts: list[str] = []

    def ref(self, shown: str, path: str) -> str:
        self.refs.append((shown, path))
        return shown

    def value(self, v: float, path: str) -> str:
        return self.ref(fmt_value(self.r.metrika, v), path)

    def count(self, n: int, path: str) -> str:
        return self.ref(fmt_count(n), path)

    def label(self, row: dict, i: int) -> str:
        return self.ref(row["megnevezes"], f"sorok[{i}].megnevezes")

    def date(self, d: date, path: str) -> str:
        return self.ref(fmt_long_date(d), path)

    def level(self) -> str:
        return self.ref(CONFIDENCE, "konstans: a tartományok szintje")


def _when_where(w: _Writer) -> str:
    r = w.r
    tol, ig = date.fromisoformat(r.idoablak["tol"]), date.fromisoformat(r.idoablak["ig"])
    span = f"{w.date(tol, 'idoablak.tol')} és {w.date(ig, 'idoablak.ig')} között"
    when = f"a teljes időszakban ({span})" if r.idoablak["teljes"] else span
    filters = [f"{f['rovid']}: " + " vagy ".join(w.ref(c, f"szurok[{i}].cimkek[{j}]")
                                                for j, c in enumerate(f["cimkek"]))
               for i, f in enumerate(r.szurok)]
    return when + (("; " + "; ".join(filters)) if filters else "")


def _scope(w: _Writer) -> str:
    n = w.count(w.r.osszesen["rendelesek"], "osszesen.rendelesek")
    return f"A kérdés {n} kézbesített rendelésre vonatkozik: {_when_where(w)}."


def _overall(w: _Writer) -> str | None:
    m, tot = w.r.metrika, w.r.osszesen
    name = _cap(f"{az(m['nev'])} {m['nev']}")
    if tot["ertek"] is None:
        return f"Ebben a körben nincs {m['alap_nev']}, ezért {az(m['nev'])} {m['nev']} nem számolható."
    if m["id"] == "rendelesek_szama":
        return None                                    # a hatókör mondata már kimondta
    s = f"{name} {w.value(tot['ertek'], 'osszesen.ertek')}"
    if "ci" in tot and tot["ci"][0] is not None:
        lo = nv.fmt_num(100 * tot["ci"][0], m["tizedes"])
        hi = fmt_value(m, tot["ci"][1])
        s += f" ({w.level()} tartomány: {w.ref(lo, 'osszesen.ci[0]')}–{w.ref(hi, 'osszesen.ci[1]')})"
    if "alap" in tot:
        s += f" (alapja: {w.count(tot['alap'], 'osszesen.alap')} {m['alap_nev']})"
    s += "."
    if tot["keves_adat"]:
        s += (f" Ez kevés rendelésből számolt érték (kevesebb mint "
              f"{w.count(m['min_csoport'], 'metrika.min_csoport')}) — óvatosan értelmezd.")
    return s


def _compare(w: _Writer, row: dict, i: int) -> str:
    if "reszesedes" in row:
        return f"az összes {w.ref(nv.fmt_pct(row['reszesedes'], 1), f'sorok[{i}].reszesedes')}-a"
    if "relativ" in row:
        return f"az összesített érték {w.ref(nv.fmt_num(row['relativ'], 1), f'sorok[{i}].relativ')}-szerese"
    return ""


def _item(w: _Writer, row: dict, i: int, with_n: bool = True) -> str:
    s = f"{w.label(row, i)}: {w.value(row['ertek'], f'sorok[{i}].ertek')}"
    if with_n and w.r.metrika["egyseg"] != "darab":          # darabnál az érték maga a darabszám
        base_key = "alap" if "alap" in row else "rendelesek"
        word = w.r.metrika["alap_nev"] if base_key == "alap" else "rendelés"
        s += f" ({w.count(row[base_key], f'sorok[{i}].{base_key}')} {word})"
    return s


def _breakdown(w: _Writer) -> list[str]:
    r, spec = w.r, w.r.spec
    if not r.bontas:
        return []
    index = {id(row): i for i, row in enumerate(r.sorok)}
    reliable = [row for row in r.sorok if not row["keves_adat"] and row["ertek"] is not None]
    small = [row for row in r.sorok if row["keves_adat"]]
    dim_name = _cap(r.bontas["szerint"])
    out: list[str] = []
    if not reliable:
        out.append(f"{dim_name} egyik csoportban sincs elég rendelés a megbízható értékhez.")
    elif spec.rendezes == "bontas":
        if r.bontas["id"] in ("honap", "ev", "het_napja") and len(reliable) > 3:
            hi = max(reliable, key=lambda row: row["ertek"])
            lo = min(reliable, key=lambda row: row["ertek"])
            s = (f"{dim_name} a legmagasabb {_item(w, hi, index[id(hi)], with_n=False)}, "
                 f"a legalacsonyabb {_item(w, lo, index[id(lo)], with_n=False)}.")
            last = reliable[-1]
            if r.bontas["id"] == "honap" and last is not hi and last is not lo:
                i = index[id(last)]
                s += (f" Az utolsó hónap ({w.label(last, i)}) értéke "
                      f"{w.value(last['ertek'], f'sorok[{i}].ertek')}.")
            out.append(s)
        else:
            shown = reliable[: spec.limit]
            out.append(f"{dim_name}: " + "; ".join(_item(w, row, index[id(row)]) for row in shown) + ".")
    else:
        shown = reliable[: spec.limit]
        word = "a legmagasabb" if spec.rendezes == "ertek_csokkeno" else "a legalacsonyabb"
        first = shown[0]
        s = f"{dim_name} {word} {_item(w, first, index[id(first)])}"
        cmp = _compare(w, first, index[id(first)])
        s += f", {cmp}" if cmp else ""
        if len(shown) > 1:
            s += "; utána " + "; ".join(_item(w, row, index[id(row)]) for row in shown[1:])
        s += "."
        if len(reliable) > len(shown):
            other = reliable[-1]
            other_word = "a legalacsonyabb" if spec.rendezes == "ertek_csokkeno" else "a legmagasabb"
            s += f" {_cap(other_word)} {_item(w, other, index[id(other)])}."
        out.append(s)
    if small:
        out.append(_small(w))
    return out


def _small(w: _Writer) -> str | None:
    """A kevés adatú csoportok mondata (ha van ilyen)."""
    r = w.r
    small = [row for row in r.sorok if row["keves_adat"]] if r.bontas else []
    if not small:
        return None
    k = w.ref(str(len(small)), "sorok (kevés adat)")
    return (f"{k} csoport kevés adat miatt (kevesebb mint "
            f"{w.count(r.metrika['min_csoport'], 'metrika.min_csoport')} rendelés) "
            "nem szerepel a fenti összegzésben.")


def _limits(w: _Writer, framed: bool = False) -> list[str]:
    r = w.r
    out = []
    if "idoablak_szukitve" in r.megjegyzesek:
        lo, hi = date.fromisoformat(r.adat["tol"]), date.fromisoformat(r.adat["ig"])
        out.append(f"Az adat {w.date(lo, 'adat.tol')} és {w.date(hi, 'adat.ig')} közötti; "
                   "a kérdés időablakát erre szűkítettem.")
    if r.metrika["egyseg"] == "arany" and r.bontas:
        if framed:      # a modell szövege nem feltétlenül említi a tartományt: ide nem hivatkozhat vissza
            out.append("A különbségek együttjárást jeleznek, nem okot; a véletlen ingadozás mértékét "
                       f"a {w.level()} tartomány mutatja (az ábrán és a táblázatban).")
        else:
            out.append(f"A {w.level()} tartomány a véletlen ingadozást mutatja; a különbségek "
                       "együttjárást jeleznek, nem okot.")
    return out


def frame(r: MetricResult) -> tuple[Answer, Answer]:
    """A nyelvi modell válaszának kerete (② v2): a hatókör mondata a válasz elé, a korlátok
    (kevés adat, szűkített időablak, együttjárás) mögé. Ezeket a kód írja — a modell csak a
    válasz magját fogalmazza, így a hatókör és a korlát mindig ott van, és mindig pontos."""
    head = _Writer(r)
    scope = _scope(head)
    tail = _Writer(r)
    parts = [p for p in [_small(tail), *_limits(tail, framed=True)] if p]
    return Answer(scope, head.refs), Answer(" ".join(parts), tail.refs)


def answer(r: MetricResult) -> Answer:
    """A teljes sablonos válasz (hatókör → állítás → bontás → korlát)."""
    w = _Writer(r)
    if r.empty:
        return Answer(f"Ebben a körben ({_when_where(w)}) nincs egyetlen kézbesített rendelés sem "
                      "az adatban, ezért nincs mit kiszámolni.", w.refs)
    parts = [_scope(w)]
    overall = _overall(w)
    if overall:
        parts.append(overall)
    parts += _breakdown(w)
    parts += _limits(w)
    return Answer(" ".join(parts), w.refs)
