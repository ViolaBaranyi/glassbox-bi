"""
Időkifejezések a kérdésben → időablak, determinisztikusan.

A nyelvi modell a dátumszámolásban megbízhatatlan: a fejlesztői próbán (2026-10-16) a
„tavaly” egyszer a „mától visszafelé egy év” lett (2017-09-01 – 2018-08-31), és első körre
fordított időablak jött ki. A gyakori magyar kifejezéseket ezért a kód számolja a rendszer
„mai” napjából (katalógus: szimulalt_ma); ha a kérdésben ilyet talál, ez felülírja a modell
időablakát, és a felület meg is mondja, melyik kifejezésből lett. Amit nem ismer fel (pl.
„márciusban” évszám nélkül), azt a modellre hagyja.

Felismert alakok: „2017-ben”, „2017-es”, „2017 első / második felében”, „2018 első
negyedévében” (és „1. negyedév”), „2018 márciusában” / „2018. március”, „2017 és 2018
között”, „2017-től”, „2018-ig”, „tavaly”, „tavalyelőtt”, „idén”, „az elmúlt / utolsó N nap /
hét / hónap / év” (számmal vagy betűvel), „a múlt / előző hónapban”.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

MONTHS = ["január", "február", "március", "április", "május", "június", "július", "augusztus",
          "szeptember", "október", "november", "december"]
NUMBERS = {"egy": 1, "két": 2, "kettő": 2, "három": 3, "négy": 4, "öt": 5, "hat": 6, "hét": 7,
           "nyolc": 8, "kilenc": 9, "tíz": 10, "tizenegy": 11, "tizenkét": 12, "tizenkettő": 12}
_NUM = r"(\d{1,2}|" + "|".join(sorted(NUMBERS, key=len, reverse=True)) + r")"


@dataclass(frozen=True)
class TimeHit:
    tol: date | None
    ig: date | None
    kifejezes: str          # amit a kérdésben talált (a felületnek)

    def window(self) -> dict:
        return {k: v.isoformat() for k, v in (("tol", self.tol), ("ig", self.ig)) if v}


def _month_end(y: int, m: int) -> date:
    return date(y, m, calendar.monthrange(y, m)[1])


def _minus_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 - n, 12)
    y += d.year
    return date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1]))


def _number(word: str) -> int:
    return int(word) if word.isdigit() else NUMBERS[word]


def parse_window(question: str, ma: date) -> TimeHit | None:
    """A kérdés időkifejezéséből az időablak (vagy None, ha nincs felismerhető, egyértelmű)."""
    q = " ".join(question.lower().split())
    yesterday = ma - timedelta(days=1)

    # --- két évszám között
    m = re.search(r"\b(20\d\d)\.?\s*(?:és|–|-)\s*(20\d\d)\.?\s*(?:között|közt)", q)
    if m:
        y1, y2 = sorted((int(m.group(1)), int(m.group(2))))
        return TimeHit(date(y1, 1, 1), date(y2, 12, 31), m.group(0))
    years = set(re.findall(r"\b(20\d\d)\b", q))
    if len(years) > 1:
        return None                                  # több évszám, „között” nélkül: a modellre bízzuk
    # --- évszám + félév / negyedév / hónap
    m = re.search(r"\b(20\d\d)\.?\s+(első|második)\s+fel(?:é|e)\w*", q)
    if m:
        y = int(m.group(1))
        return (TimeHit(date(y, 1, 1), date(y, 6, 30), m.group(0)) if m.group(2) == "első"
                else TimeHit(date(y, 7, 1), date(y, 12, 31), m.group(0)))
    m = re.search(r"\b(20\d\d)\.?\s+(első|második|harmadik|negyedik|[1-4]\.)\s+negyedév\w*", q)
    if m:
        y = int(m.group(1))
        k = {"első": 1, "második": 2, "harmadik": 3, "negyedik": 4}.get(m.group(2)) or int(m.group(2)[0])
        return TimeHit(date(y, 3 * k - 2, 1), _month_end(y, 3 * k), m.group(0))
    m = re.search(r"\b(20\d\d)\.?\s+(" + "|".join(MONTHS) + r")\w*", q)
    if m:
        y, mo = int(m.group(1)), MONTHS.index(m.group(2)) + 1
        return TimeHit(date(y, mo, 1), _month_end(y, mo), m.group(0))
    # --- évszám -tól / -ig / magában
    m = re.search(r"\b(20\d\d)-(?:tól|től)\b", q)
    if m:
        return TimeHit(date(int(m.group(1)), 1, 1), None, m.group(0))
    m = re.search(r"\b(20\d\d)-ig\b", q)
    if m:
        return TimeHit(None, date(int(m.group(1)), 12, 31), m.group(0))
    m = re.search(r"\b(20\d\d)(?:-(?:ban|ben|as|es|ös|ös|ra|re)|\.?\s+(?:évben|év\b|során))", q)
    if m:
        y = int(m.group(1))
        return TimeHit(date(y, 1, 1), date(y, 12, 31), m.group(0))
    # --- viszonylagos kifejezések (a rendszer „mai” napjához)
    m = re.search(r"\btavalyelőtt\w*", q)
    if m:
        return TimeHit(date(ma.year - 2, 1, 1), date(ma.year - 2, 12, 31), m.group(0))
    m = re.search(r"\b(?:tavaly\w*|(?:a\s+)?(?:múlt|előző)\s+év\w*)", q)
    if m:
        return TimeHit(date(ma.year - 1, 1, 1), date(ma.year - 1, 12, 31), m.group(0))
    m = re.search(r"\b(?:idén|idei\w*|ebben\s+az\s+évben)", q)
    if m:
        return TimeHit(date(ma.year, 1, 1), yesterday, m.group(0))
    m = re.search(r"\b(?:az?\s+)?(?:elmúlt|utolsó|legutóbbi)\s+" + _NUM + r"\s+(nap|hét|hónap|év)\w*", q)
    if m:
        n, unit = _number(m.group(1)), m.group(2)
        tol = {"nap": lambda: ma - timedelta(days=n), "hét": lambda: ma - timedelta(weeks=n),
               "hónap": lambda: _minus_months(ma, n), "év": lambda: _minus_months(ma, 12 * n)}[unit]()
        return TimeHit(tol, yesterday, m.group(0))
    m = re.search(r"\b(?:a\s+)?(?:múlt|előző|elmúlt)\s+hónap\w*", q)
    if m:
        prev = _minus_months(date(ma.year, ma.month, 1), 1)
        return TimeHit(prev, _month_end(prev.year, prev.month), m.group(0))
    return None
