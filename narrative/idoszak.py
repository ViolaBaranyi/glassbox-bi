"""
Időkifejezések a kérdésben → időablak, determinisztikusan.

A nyelvi modell a dátumszámolásban megbízhatatlan: a fejlesztői próbán (2026-10-16) a
„tavaly” egyszer a „mától visszafelé egy év” lett (2017-09-01 – 2018-08-31), és első körre
fordított időablak jött ki. A gyakori magyar kifejezéseket ezért a kód számolja a rendszer
„mai” napjából (katalógus: szimulalt_ma); ha a kérdésben ilyet talál, ez felülírja a modell
időablakát, és a felület meg is mondja, melyik kifejezésből lett. Amit nem ismer fel (pl.
„márciusban” évszám nélkül), azt a modellre hagyja.

Felismert alakok: „2017-ben”, „2017-es”, „2017 első / második felében” (félévében, félév),
„2018 első negyedévében” (és „1. negyedév”, „utolsó negyedév”, „Q1”), „2018 márciusában” /
„2018. március”, „2017 és 2018 között”, „2017-től”, „2018-ig”, „tavaly”, „tavalyelőtt”,
„idén”, „az elmúlt / utolsó N nap / hét / hónap / év” (számmal vagy betűvel), „a múlt /
előző hónapban”. v4 (a v3 mérése után, okt. 20.): a viszonylagos év is kaphat félévet,
negyedévet vagy hónapot („tavaly negyedik negyedévben”, „tavalyi év Q3-ban”, „tavaly
augusztusban”, „az idei első negyedévben”), és ékezet nélkül is felismeri („mult evben”).
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta

MONTHS = ["január", "február", "március", "április", "május", "június", "július", "augusztus",
          "szeptember", "október", "november", "december"]
NUMBERS = {"egy": 1, "két": 2, "kettő": 2, "három": 3, "négy": 4, "öt": 5, "hat": 6, "hét": 7,
           "nyolc": 8, "kilenc": 9, "tíz": 10, "tizenegy": 11, "tizenkét": 12, "tizenkettő": 12}


def fold(text: str) -> str:
    """Kisbetűs, ékezet nélküli alak betűről betűre — a pozíciók nem változnak."""
    return "".join((unicodedata.normalize("NFKD", ch)[:1] or ch).lower()[:1] or ch for ch in text)


F_MONTHS = [fold(m) for m in MONTHS]
F_NUMBERS = {fold(k): v for k, v in NUMBERS.items()}
_NUM = r"(\d{1,2}|" + "|".join(sorted(F_NUMBERS, key=len, reverse=True)) + r")"
_ORD = {"elso": 1, "masodik": 2, "harmadik": 3, "negyedik": 4, "utolso": 4}
# a viszonylagos év: tavalyelőtt / tavaly (tavalyi, múlt / előző év) / idén (idei, ebben az évben)
_REL_YEAR = [
    (re.compile(r"\btavalyelott\w*"), -2),
    (re.compile(r"\b(?:tavaly\w*|(?:a\s+)?(?:mult|elozo)\s+ev\w*)"), -1),
    (re.compile(r"\b(?:iden|idei(?:ben|ek|nek|re)?\b|ebben\s+az\s+evben)"), 0),     # az „ideig” nem „idei”
]
_HALF = r"(elso|masodik)\s+(?:fel(?:e|ev)\w*|fel\s+ev\w*)"
_QUARTER = r"(?:(elso|masodik|harmadik|negyedik|utolso|[1-4]\.)\s+negyedev\w*|q([1-4])\b)"
_MONTH = r"(" + "|".join(F_MONTHS) + r")\w*"


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
    return int(word) if word.isdigit() else F_NUMBERS[word]


def _sub_period(f: str, start: int, y: int, ma: date) -> tuple[date, date, int] | None:
    """Félév, negyedév vagy hónap egy adott évben, a kérdés `start` pozíciójától keresve.
    Visszaad: (tól, ig, a találat vége)."""
    rest = f[start:]
    found = []
    for pattern, kind in ((_HALF, "felev"), (_QUARTER, "negyedev"), (_MONTH, "honap")):
        m = re.search(pattern, rest)
        if m:
            found.append((m.start(), m, kind))
    if not found:
        return None
    _, m, kind = min(found, key=lambda x: x[0])
    if kind == "felev":
        tol, ig = (date(y, 1, 1), date(y, 6, 30)) if m.group(1) == "elso" else (date(y, 7, 1), date(y, 12, 31))
    elif kind == "negyedev":
        k = int(m.group(2)) if m.group(2) else (_ORD.get(m.group(1)) or int(m.group(1)[0]))
        tol, ig = date(y, 3 * k - 2, 1), _month_end(y, 3 * k)
    else:
        mo = F_MONTHS.index(m.group(1)) + 1
        tol, ig = date(y, mo, 1), _month_end(y, mo)
    return tol, ig, start + m.end()             # a jövőbe nyúló részt a kapu vágja le (vagy előrejelzés)


def parse_window(question: str, ma: date) -> TimeHit | None:
    """A kérdés időkifejezéséből az időablak (vagy None, ha nincs felismerhető, egyértelmű)."""
    q = " ".join(question.split())
    f = fold(q)
    yesterday = ma - timedelta(days=1)

    def hit(tol, ig, a, b):
        return TimeHit(tol, ig, q[a:b])

    # --- két évszám között
    m = re.search(r"\b(20\d\d)\.?\s*(?:es|–|-)\s*(20\d\d)\.?\s*(?:kozott|kozt)", f)
    if m:
        y1, y2 = sorted((int(m.group(1)), int(m.group(2))))
        return hit(date(y1, 1, 1), date(y2, 12, 31), m.start(), m.end())
    years = set(re.findall(r"\b(20\d\d)\b", f))
    if len(years) > 1:
        return None                                  # több évszám, „között” nélkül: a modellre bízzuk
    # --- évszám + félév / negyedév / hónap („2018 első félévében”, „2017 Q3”, „2018 márciusában”)
    m = re.search(r"\b(20\d\d)\.?\s+", f)
    if m:
        sub = re.match(r"(?:" + _HALF + "|" + _QUARTER + "|" + _MONTH + r")", f[m.end():])
        if sub:
            got = _sub_period(f, m.end(), int(m.group(1)), ma)
            if got:
                return hit(got[0], got[1], m.start(), got[2])
    # --- évszám -tól / -ig / magában
    m = re.search(r"\b(20\d\d)-(?:tol)\b", f)
    if m:
        return hit(date(int(m.group(1)), 1, 1), None, m.start(), m.end())
    m = re.search(r"\b(20\d\d)-ig\b", f)
    if m:
        return hit(None, date(int(m.group(1)), 12, 31), m.start(), m.end())
    m = re.search(r"\b(20\d\d)(?:-?(?:ban|ben|as|es|os|ra|re)|\.?\s+(?:evben|ev\b|soran))", f)
    if m:
        y = int(m.group(1))
        return hit(date(y, 1, 1), date(y, 12, 31), m.start(), m.end())
    # --- viszonylagos év, félévvel / negyedévvel / hónappal vagy magában
    for pattern, offset in _REL_YEAR:
        m = pattern.search(f)
        if not m:
            continue
        y = ma.year + offset
        # „tavaly negyedik negyedévben”, „tavalyi év Q3-ban”, „az idei első negyedévben” — a
        # részidőszak a viszonylagos év után (legfeljebb két szóval) vagy közvetlenül előtte állhat
        after = re.match(r"(?:\s+\w+){0,2}?\s+(?=" + _HALF + "|" + _QUARTER + "|" + _MONTH + ")", f[m.end():])
        if after:
            got = _sub_period(f, m.end() + after.end(), y, ma)
            if got:
                return hit(got[0], got[1], m.start(), got[2])
        if offset == 0:
            return hit(date(y, 1, 1), yesterday, m.start(), m.end())
        return hit(date(y, 1, 1), date(y, 12, 31), m.start(), m.end())
    m = re.search(r"\b(?:az?\s+)?(?:elmult|utolso|legutobbi)\s+" + _NUM + r"\s+(nap|het|honap|ev)\w*", f)
    if m:
        n, unit = _number(m.group(1)), m.group(2)
        tol = {"nap": lambda: ma - timedelta(days=n), "het": lambda: ma - timedelta(weeks=n),
               "honap": lambda: _minus_months(ma, n), "ev": lambda: _minus_months(ma, 12 * n)}[unit]()
        return hit(tol, yesterday, m.start(), m.end())
    m = re.search(r"\b(?:az?\s+)?(?:elmult|utolso|legutobbi)\s+fel\s*ev\w*", f)
    if m:                                            # „az elmúlt fél évben”
        return hit(_minus_months(ma, 6), yesterday, m.start(), m.end())
    m = re.search(r"\b(?:a\s+)?(?:mult|elozo|elmult)\s+honap\w*", f)
    if m:
        prev = _minus_months(date(ma.year, ma.month, 1), 1)
        return hit(prev, _month_end(prev.year, prev.month), m.start(), m.end())
    return None


# Van-e a kérdésben bármilyen időre utaló szó? (v4: ha nincs, a modell időablaka kitalált.)
# A „havonta”, „évente”, „hónapról hónapra”, „melyik hónapban” bontás, nem időablak.
TIME_WORDS = re.compile(
    r"\b20\d\d\b|\b'?1[6-8]\b|\b(?:" + "|".join(F_MONTHS) + r")\w*|"
    r"\b(?:tavaly\w*|tavaj\w*|iden|idei(?:ben|ek|nek|re)?\b|elmult\w*|utolso\w*|legutobbi\w*|mult\s+\w+|elozo\s+\w+|"
    r"mostanaban|jelenleg|az\s+utobbi\w*|negyedev\w*|felev\w*|fel\s+ev\w*|q[1-4]|nyar\w*|tavasz\w*|osszel|oszi\w*|osz\b|"
    r"tel(?:en|i)\b|elejen|elejei|vegen|vegeig|ota\b|kezdve|kovetkezo\s+\w+|jovo\w*|holnap\w*|majd\b)\b")


def mentions_time(question: str) -> bool:
    return TIME_WORDS.search(fold(" ".join(question.split()))) is not None
