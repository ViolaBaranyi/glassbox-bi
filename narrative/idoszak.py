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
v5 (a v2 mérése után, okt. 22.): évszak („tavaly nyáron”, „2018 tavaszán”, „17 nyarán”), egy év
első / utolsó N hónapja („2017 utolsó 4 hónapjában”), „a 2 legutolsó hónap”, „tavaly előtt”
külön írva, „2017 óta / elejétől”, két év vagy egy év két részének összevetése („2017 vs 2018”,
„2018 Q1 vs Q2”) — és az idősor-szándék (series_intent): „mikor”, „melyik hónapban”, „hogy
változott”, két időszak összevetése → havi vagy éves bontás.
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
    (re.compile(r"\btavaly\s*elott\w*"), -2),                    # v5: külön írva is
    (re.compile(r"\b(?:tavaly\w*|(?:a\s+)?(?:mult|elozo)\s+ev\w*)"), -1),
    (re.compile(r"\b(?:iden|idei(?:ben|ek|nek|re)?\b|ebben\s+az\s+evben)"), 0),     # az „ideig” nem „idei”
]
_HALF = r"(elso|masodik)\s+(?:fel(?:e|ev)\w*|fel\s+ev\w*)"
_QUARTER = r"(?:(elso|masodik|harmadik|negyedik|utolso|[1-4]\.)\s+negyedev\w*|q([1-4])\b)"
_MONTH = r"(" + "|".join(F_MONTHS) + r")\w*"
# v5: évszak (a tél kimarad: két évre nyúlik, nem egyértelmű) és egy év első / utolsó N hónapja
_SEASON = r"\b(tavasz(?:on|szal|szan|an|a|i)?|nyar(?:on|an|a|i)?|osszel|osz(?:on|en|e|i)?)\b"
SEASONS = {"tavasz": (3, 5), "nyar": (6, 8), "osz": (9, 11)}
_N_MONTHS = r"(elso|utolso)\s+" + _NUM + r"\s+honap\w*"
_LINK = r"\s*(?:vs\.?|versus|es|meg|illetve|valamint|/|–|-)\s*"
_RECENT = r"\b(?:mostansag\w*|mostanaban|manapsag|ujabban|jelenleg|az?\s+utobbi\s+idoben|a\s+legutobbi\s+idoben)\b"
RECENT_MONTHS = 3
_SUB = r"(?:" + _HALF + "|" + _QUARTER + "|" + _MONTH + "|" + _SEASON + "|" + _N_MONTHS + r")"


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
    for pattern, kind in ((_HALF, "felev"), (_QUARTER, "negyedev"), (_MONTH, "honap"), (_SEASON, "evszak"),
                          (_N_MONTHS, "n_honap")):
        m = re.search(pattern, rest)
        if m:
            found.append((m.start(), m, kind))
    if not found:
        return None
    _, m, kind = min(found, key=lambda x: (x[0], x[2] != "n_honap"))
    if kind == "evszak":
        word = "osz" if m.group(1).startswith("oss") else m.group(1)          # „ősszel”
        first, last = next(v for k, v in SEASONS.items() if word.startswith(k))
        tol, ig = date(y, first, 1), _month_end(y, last)
    elif kind == "n_honap":
        n = min(12, _number(m.group(2)))
        tol, ig = (date(y, 1, 1), _month_end(y, n)) if m.group(1) == "elso" else (date(y, 13 - n, 1), date(y, 12, 31))
    elif kind == "felev":
        tol, ig = (date(y, 1, 1), date(y, 6, 30)) if m.group(1) == "elso" else (date(y, 7, 1), date(y, 12, 31))
    elif kind == "negyedev":
        k = int(m.group(2)) if m.group(2) else (_ORD.get(m.group(1)) or int(m.group(1)[0]))
        tol, ig = date(y, 3 * k - 2, 1), _month_end(y, 3 * k)
    else:
        mo = F_MONTHS.index(m.group(1)) + 1
        tol, ig = date(y, mo, 1), _month_end(y, mo)
    return tol, ig, start + m.end()             # a jövőbe nyúló részt a kapu vágja le (vagy előrejelzés)


def two_years(f: str):
    """Két évszám összevetése a kérdésben (ékezet nélküli alakon): „2017 vs 2018”, „2015-ös és
    2016-os”, „2017-ben meg 2018-ban” — None, ha nincs."""
    return re.search(r"\b(20\d\d)(?:-?\w{1,4})?" + _LINK + r"(20\d\d)\b", f)


def _pair(f: str, got: tuple, y: int, ma: date) -> tuple:
    """Ha egy részidőszak után összevetés jön egy másikkal ugyanabban az évben („Q1 vs Q2”, „első és
    második félév”), a kettőt átfogó ablak."""
    link = re.match(_LINK, f[got[2]:])
    if not link:
        return got
    start = got[2] + link.end()
    if not re.match(_SUB, f[start:]):
        return got
    other = _sub_period(f, start, y, ma)
    if not other:
        return got
    return min(got[0], other[0]), max(got[1], other[1]), other[2]


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
        # v5: két év összevetése („2017 vs 2018”, „a 2015-ös és 2016-os év”) — a kettőt átfogó ablak
        m = two_years(f)
        if m:
            y1, y2 = sorted((int(m.group(1)), int(m.group(2))))
            return hit(date(y1, 1, 1), date(y2, 12, 31), m.start(), m.end())
        return None                                  # több évszám, összevetés nélkül: a modellre bízzuk
    # --- évszám + félév / negyedév / hónap / évszak / első-utolsó N hónap („2018 első félévében”,
    # „2017 Q3”, „2018 márciusában”, „2018 tavaszán”, „2017 utolsó 4 hónapjában”)
    m = re.search(r"\b(20\d\d)\.?\s+", f)
    if m and re.match(_SUB, f[m.end():]):
        got = _sub_period(f, m.end(), int(m.group(1)), ma)
        if got:
            got = _pair(f, got, int(m.group(1)), ma)        # v5: „2018 Q1 vs Q2”
            return hit(got[0], got[1], m.start(), got[2])
    # --- két számjegyű év évszakkal („17 nyarán”)
    m = re.search(r"(?<![\d.])'?(1[6-8])\s+(?=" + _SEASON + ")", f)
    if m:
        got = _sub_period(f, m.end(), 2000 + int(m.group(1)), ma)
        if got:
            return hit(got[0], got[1], m.start(), got[2])
    # --- évszám -tól / óta / elejétől („2017-től”, „2017 óta”, „2017 elejétől”)
    m = re.search(r"\b(20\d\d)(?:-tol\b|\.?\s+(?:ota|elejetol|eleje\s+ota|kezdetetol)\b)", f)
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
        after = re.match(r"(?:\s+\w+){0,2}?\s+(?=" + _SUB + ")", f[m.end():])
        if after:
            got = _sub_period(f, m.end() + after.end(), y, ma)
            if got:
                got = _pair(f, got, y, ma)
                return hit(got[0], got[1], m.start(), got[2])
        since = re.match(r"\s+(?:ota|elejetol|eleje\s+ota)\b", f[m.end():])
        if since:                                   # v5: „tavaly óta”, „tavaly elejétől”
            return hit(date(y, 1, 1), None, m.start(), m.end() + since.end())
        if offset == 0:
            return hit(date(y, 1, 1), yesterday, m.start(), m.end())
        return hit(date(y, 1, 1), date(y, 12, 31), m.start(), m.end())
    m = (re.search(r"\b(?:az?\s+)?(?:elmult|utolso|legutobbi)\s+" + _NUM + r"\s+(nap|het|honap|ev)\w*", f)
         or re.search(r"\b(?:az?\s+)?" + _NUM + r"\s+(?:legutolso|utolso|elmult|legutobbi)\s+(nap|het|honap|ev)\w*", f))
    if m:                                            # v5: „a 2 legutolsó hónapban” is
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
    # v5: „mostanság”, „mostanában”, „az utóbbi időben” — rögzített értelmezés: az elmúlt 3 hónap
    # (a felület kimondja; a modell a „mai” napot vette, ami az adaton kívül esik)
    m = re.search(_RECENT, f)
    if m:
        return hit(_minus_months(ma, RECENT_MONTHS), yesterday, m.start(), m.end())
    return None


# Van-e a kérdésben bármilyen időre utaló szó? (v4: ha nincs, a modell időablaka kitalált.)
# A „havonta”, „évente”, „hónapról hónapra”, „melyik hónapban” bontás, nem időablak.
TIME_WORDS = re.compile(
    r"\b20\d\d\b|\b'?1[6-8]\b|\b(?:" + "|".join(F_MONTHS) + r")\w*|"
    r"\b(?:tavaly\w*|tavaj\w*|iden|idei(?:ben|ek|nek|re)?\b|elmult\w*|utolso\w*|legutobbi\w*|mult\s+\w+|elozo\s+\w+|"
    r"mostanaban|mostansag\w*|manapsag|ujabban|jelenleg|az\s+utobbi\w*|negyedev\w*|felev\w*|fel\s+ev\w*|q[1-4]|nyar\w*|tavasz\w*|osszel|oszi\w*|osz\b|"
    r"tel(?:en|i)\b|elejen|elejei|vegen|vegeig|ota\b|kezdve|kovetkezo\s+\w+|jovo\w*|holnap\w*|majd\b)\b")


def mentions_time(question: str) -> bool:
    return TIME_WORDS.search(fold(" ".join(question.split()))) is not None


# ------------------------------------------------------------------ v5: idősor-szándék
# A „mikor”, „melyik hónapban”, „hogy változott”, két időszak összevetése idősort kér: a v2 mérésen
# a 4B és a 9B is egyetlen számot adott rá (a hiba a rendszeré, nem a modell méretéé).
_SERIES_MONTH = re.compile(r"\bmelyik\s+(?:\w+\s+){0,2}?honap\w*|\baz?\s+ev\s+melyik\s+honap\w*|\bolyan\s+honap\w*|"
                           r"\bleg(?!utolso|utobbi|elso)\w+(?:\s+\w+)?\s+honap\w*")
_SERIES_YEAR = re.compile(r"\bmelyik\s+(?:\w+\s+)?ev(?:ben|et|re|nek)?\b|\bolyan\s+ev(?:ben)?\b|\bleg(?!utolso|utobbi|elso)\w+(?:\s+\w+)?\s+ev(?:ben|unk)?\b")
_SERIES_WHEN = re.compile(r"\bmikor\b")
_SERIES_CHANGE = re.compile(
    r"\b(?:hogy(?:an)?|mikent)\s+(?:\w+\s+){0,4}?(?:valtoz|alakul|nez\s+ki|fejlod)\w*|"
    r"\b(?:valtozott|valtozik|alakult|alakulasa|alakulasat|trend\w*|novekszik|novekedett|novekedes\w*|novekvo|nott|"
    r"csokkent|csokken|csokkeno|emelkedett|emelkedik|visszaesett)\b")
_YEARLY = re.compile(r"\bev(?:es|i)?\s+szint\w*|\bevrol\s+evre|\bevente|\bevenkent")
_QUARTERLY = re.compile(r"\bnegyedev(?:ente|enkent)\b")


def series_intent(question: str) -> tuple[str, str] | None:
    """Idősort kér-e a kérdés: („honap” | „ev”, a kiváltó kifejezés), vagy None.
    Két év összevetése → éves; egy év két része („Q1 vs Q2”) → havi (negyedéves bontás nincs);
    „melyik hónapban / év”, „mikor”, „hogy változott / alakult”, „csökkent”, „nőtt” → havi, ha a
    kérdés nem éves szintről beszél."""
    q = " ".join(question.split())
    f = fold(q)
    m = two_years(f)
    if m:
        return "ev", q[m.start():m.end()]
    for pattern, dim in ((_SERIES_YEAR, "ev"), (_SERIES_MONTH, "honap")):
        m = pattern.search(f)
        if m:
            return dim, q[m.start():m.end()]
    y = re.search(r"\b(20\d\d)\.?\s+", f)
    if y and re.match(_SUB, f[y.end():]):
        got = _sub_period(f, y.end(), int(y.group(1)), date(2100, 1, 1))
        pair = got and _pair(f, got, int(y.group(1)), date(2100, 1, 1))
        if got and pair != got:
            return "honap", q[y.start():pair[2]]
    for pattern in (_SERIES_WHEN, _SERIES_CHANGE):
        m = pattern.search(f)
        if m:
            return ("ev" if _YEARLY.search(f) else "honap"), q[m.start():m.end()]
    return None
