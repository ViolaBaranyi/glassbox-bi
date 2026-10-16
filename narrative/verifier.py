"""
KAPU ② — a nyelvi modell szövegének ellenőrzése (rendszerterv 15., 16. V-5).

A modell a számokat jelölővel írja ({O}, {S1} …), a behelyettesítést a kód végzi. A kapu
utána ezt nézi:

  1. minden jelölő létezik-e (kitalált jelölő = kitalált szám);
  2. a kész szöveg minden száma visszavezethető-e az eredményre: a jelölők értékeire, a
     csoport- és szűrőnevekre (pl. „2018. március”), ill. — ha a modell a jelölő helyett
     mégis maga írta le — az eredmény egy megkülönböztethető értékére (tizedesvesszős,
     mértékegységes vagy legalább háromjegyű szám). Kis egész számot (pl. „3”) csak jelölővel
     írhat: az túl könnyen egyezne véletlenül (a 02. szakasz 9,8%-os mérése);
  3. a csoport értéke a saját csoportja mellett áll-e: „az Észak ({S1})” hamis, ha az {S1}
     az Északkelet értéke. A szám maga visszavezethető — a hiba a kötésben van, ezért ezt
     külön kell nézni (a felcserélt érték a hallucináció egyik tipikus alakja);
  4. a „legmagasabb / legalacsonyabb” állítás tényleg a legnagyobb / legkisebb megbízható
     csoportról szól-e — akár előtte, akár utána áll a csoport neve;
  5. nincs-e oksági állítás („okozza”, „eredményezi” …) — az eredmény együttjárás.

A csoportnevet ragozva is felismeri („Északkeleten”, „São Paulóban”, „2018 márciusában”):
a keresés kis- és nagybetűtől, valamint ékezettől függetlenül, a név elejére illeszt. A
mondatot tagmondatokra bontja (vessző, „míg”, „de”, „és” …), és a jelölőhöz, illetve a
felsőfokú szóhoz a saját tagmondatában legközelebb álló nevet keresi; ha ott nincs, a mondat
legközelebbi nevét. „Illetve / rendre” felsorolásnál a sorrend dönt.

Ami nem megy át, azt a felület nem mutatja: a sablonos válasz lép a helyére, és a hiba a
naplóba kerül — ez a K1 mérés nyersanyaga.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from semantic.answer import _NUMBER, CONFIDENCE, uncovered_numbers
from semantic.engine import MetricResult

PLACEHOLDER = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")
ROW_PATH = re.compile(r"sorok\[(\d+)\]\.(?:ertek|rendelesek|alap|reszesedes|relativ)$")
MAX_WORDS = ("legmagasabb", "legnagyobb", "legtobb", "leghosszabb", "leglassabb")
MIN_WORDS = ("legalacsonyabb", "legkisebb", "legkevesebb", "legrovidebb", "leggyorsabb")
ORDINAL = re.compile(r"(?:masodik|harmadik|negyedik|otodik|hatodik)\s*$")
CLAUSE = re.compile(r"[,;:–—]|\s(?:mig|de|viszont|pedig|illetve|es|valamint|ugyanakkor|azonban)\s")
LISTING = re.compile(r"\b(?:illetve|rendre)\b")
CAUSAL = re.compile(r"\b(okoz\w*|okozój\w*|eredményez\w*|következtében|hatására)\b", re.I)


@dataclass
class Verdict:
    ok: bool
    problemak: list[str] = field(default_factory=list)
    szamok: int = 0                  # a kész szöveg összes száma
    fedetlen: list[str] = field(default_factory=list)
    ismeretlen_jelolok: list[str] = field(default_factory=list)
    kozvetlen_szamok: int = 0        # amit a modell jelölő helyett maga írt le (de visszavezethető)
    ismetelt_jelolok: list[str] = field(default_factory=list)   # stílus: ugyanaz a szám többször (nem hiba)

    @property
    def fedett(self) -> int:
        return self.szamok - len(self.fedetlen)


def distinctive(shown: str) -> bool:
    """Elég jellegzetes-e egy érték ahhoz, hogy közvetlenül leírva is elfogadjuk."""
    digits = re.sub(r"\D", "", shown)
    return "," in shown or "%" in shown or re.search(r"[A-Za-zÁ-ű]", shown) is not None or len(digits) >= 3


# ------------------------------------------------------------ a nevek felismerése
def fold(text: str) -> str:
    """Kisbetűs, ékezet nélküli alak betűről betűre — a pozíciók nem változnak."""
    return "".join((unicodedata.normalize("NFKD", ch)[:1] or ch).lower()[:1] or ch for ch in text)


def _name_patterns(label: str) -> list[tuple[re.Pattern, bool]]:
    """Egy csoportnév keresőmintái: (minta, a hajtogatott szövegen fut-e)."""
    f = fold(label)
    m = re.fullmatch(r"(\d{4})\. (\w+)", f)                       # „2018. március” → „2018 márciusában”
    if m:
        return [(re.compile(rf"(?<!\w){m.group(1)}\.?\s+{m.group(2)}\w*"), True)]
    m = re.fullmatch(r"(.+?) \(([a-z]{2})\)", f)                   # „são paulo (sp)” → „São Paulóban”, „SP”
    if m:
        code = label[-3:-1]
        return [(re.compile(rf"(?<!\w){re.escape(m.group(1))}\w*(?:\s*\({m.group(2)}\))?"), True),
                (re.compile(rf"(?<![\w{{]){code}(?![\w}}])"), False)]
    tail = r"\w*" if f[-1:].isalnum() else ""
    return [(re.compile(rf"(?<!\w){re.escape(f)}{tail}"), True)]


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    row: int | None                  # a csoport sora; None: szűrő neve (nem csoport)


def name_spans(text: str, result: MetricResult) -> list[Span]:
    """A csoport- és szűrőnevek előfordulásai a szövegben (a hosszabb név nyer: „Északkelet”
    előbb, mint „Észak”)."""
    names = [(row["megnevezes"], i) for i, row in enumerate(result.sorok)]
    names += [(c, None) for f in result.szurok for c in f["cimkek"]]
    folded = fold(text)
    spans: list[Span] = []
    for label, row in sorted(names, key=lambda n: -len(n[0])):
        for pattern, on_folded in _name_patterns(label):
            for m in pattern.finditer(folded if on_folded else text):
                if not any(m.start() < s.end and s.start < m.end() for s in spans):
                    spans.append(Span(m.start(), m.end(), row))
    return sorted(spans, key=lambda s: s.start)


def _clause(folded: str, spans: list[Span], pos: int) -> tuple[int, int]:
    """A pos-t tartalmazó tagmondat határai (a nevek belsejében nem vág: „egészség és …”)."""
    cuts = [m.start() for m in CLAUSE.finditer(folded)
            if not any(s.start <= m.start() < s.end for s in spans)]
    lo = max((c for c in cuts if c <= pos), default=0)
    hi = min((c for c in cuts if c > pos), default=len(folded))
    return lo, hi


def _nearest(spans: list[Span], clause: tuple[int, int], start: int, end: int, prefer_before: bool) -> Span | None:
    """A legközelebbi név a tagmondatban; ha ott nincs, a mondatban."""
    for pool in ([s for s in spans if clause[0] <= s.start < clause[1]], spans):
        before = [s for s in pool if s.end <= start]
        after = [s for s in pool if s.start >= end]
        if not before and not after:
            continue
        if pool is spans:                 # a mondat szintjén: a kifejezés előtti név (ha van)
            return before[-1] if before and prefer_before else (after[0] if after else before[-1])
        b = before[-1] if before else None
        a = after[0] if after else None
        if b and a:
            return b if (start - b.end) < (a.start - end) or (prefer_before and start - b.end == a.start - end) else a
        return b or a
    return None


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?;])\s+", text) if s.strip()]


# ------------------------------------------------------------ 3. a kötés
def binding_problems(model_text: str, result: MetricResult, row_of: dict[str, int]) -> list[str]:
    """A csoportértékek jelölője a saját csoportja mellett áll-e. row_of: jelölő → sor."""
    if not result.bontas or not row_of:
        return []
    out = []
    for sentence in _sentences(model_text):
        spans = name_spans(sentence, result)
        if not spans:
            continue
        folded = fold(sentence)
        marks = [m for m in PLACEHOLDER.finditer(sentence) if m.group(1) in row_of]
        rows_named = [s for s in spans if s.row is not None]
        if LISTING.search(folded) and len(rows_named) == len({row_of[m.group(1)] for m in marks}) > 1:
            # „az Észak és az Északkelet aránya {S2}, illetve {S1}” — a sorrend dönt
            order = list(dict.fromkeys(row_of[m.group(1)] for m in marks))
            if [s.row for s in rows_named] != order:
                out.append("a felsorolásban a csoportnevek és az értékek sorrendje nem egyezik")
            continue
        for m in marks:
            span = _nearest(spans, _clause(folded, spans, m.start()), m.start(), m.end(), prefer_before=True)
            want = row_of[m.group(1)]
            if span is not None and span.row is not None and span.row != want:
                out.append(f"a(z) {{{m.group(1)}}} „{result.sorok[want]['megnevezes']}” értéke, de "
                           f"„{result.sorok[span.row]['megnevezes']}” mellett áll")
    return out


# ------------------------------------------------------------ 4. a felsőfok
def superlative_problems(text: str, result: MetricResult) -> list[str]:
    if not result.bontas:
        return []
    reliable = [(i, r) for i, r in enumerate(result.sorok) if not r["keves_adat"] and r["ertek"] is not None]
    if len(reliable) < 2:
        return []
    top = max(r["ertek"] for _, r in reliable)
    bottom = min(r["ertek"] for _, r in reliable)
    hi = {i for i, r in reliable if r["ertek"] == top}
    lo = {i for i, r in reliable if r["ertek"] == bottom}
    volume = result.metrika["id"] != "rendelesek_szama"
    out = []
    for sentence in _sentences(text):
        folded = fold(sentence)
        spans = name_spans(sentence, result)
        if not any(s.row is not None for s in spans):
            continue
        for words, expected, what in ((MAX_WORDS, hi, "legnagyobb"), (MIN_WORDS, lo, "legkisebb")):
            for word in words:
                for m in re.finditer(word, folded):
                    if ORDINAL.search(folded[:m.start()]):
                        continue                               # „a második legmagasabb”
                    nxt = re.match(r"\w*\s+(\w+)", folded[m.start():])       # a felsőfok utáni szó
                    if volume and nxt and nxt.group(1).startswith("rendeles"):
                        continue                               # „a legtöbb rendelés” — a mennyiségről szól
                    span = _nearest(spans, _clause(folded, spans, m.start()), m.start(), m.end(),
                                    prefer_before=False)
                    if span is None or span.row is None or span.row in expected:
                        continue
                    want = result.sorok[min(expected)]["megnevezes"]
                    out.append(f"„{result.sorok[span.row]['megnevezes']}” nem a {what} érték (az: „{want}”)")
    return list(dict.fromkeys(out))


# ------------------------------------------------------------ a kapu
def verify(model_text: str, final_text: str, view_values: dict, unknown: list[str],
           result: MetricResult, mod: str = "jelolo") -> Verdict:
    """model_text: a modell szövege (jelölőkkel); final_text: behelyettesítve; view_values:
    minden jelölő → (megjelenített érték, payload-útvonal); unknown: a nem létező jelölők.

    A jelölők helyére írt értékek szerkezetileg visszavezethetők — ezért csak azt kell nézni,
    amit a modell maga írt (a szövege a jelölők nélkül). „szabad” módban (kontrollág) minden
    eredményértékhez illesztünk, a fő ágban csak a jellegzetesekhez (lásd distinctive)."""
    v = Verdict(ok=True, ismeretlen_jelolok=list(unknown))
    if unknown:
        v.problemak.append("ismeretlen jelölő: " + ", ".join("{" + u + "}" for u in unknown))
    names = [(r["megnevezes"], f"sorok[{i}].megnevezes") for i, r in enumerate(result.sorok)]
    names += [(c, f"szurok[{i}].cimkek") for i, f in enumerate(result.szurok) for c in f["cimkek"]]
    # évszám a címkékből és a dátumokból („2018 márciusában”): megnevezés, nem állítás
    years = {y for text, _ in names + list(view_values.values()) for y in re.findall(r"\b(?:19|20)\d\d\b", text)}
    fixed = [(CONFIDENCE, "konstans: a tartományok szintje")] + [(y, "évszám") for y in years]
    values = [(shown, path) for shown, path in view_values.values() if mod == "szabad" or distinctive(shown)]
    own = PLACEHOLDER.sub(" ", model_text)                       # amit a modell maga írt
    plain = own
    for text, _ in sorted(names + fixed, key=lambda r: -len(r[0])):
        plain = plain.replace(text, " ")
    written = _NUMBER.findall(plain)                             # a modell saját számai
    v.fedetlen = uncovered_numbers(own, names + fixed + values)
    v.szamok = len(_NUMBER.findall(final_text))
    v.kozvetlen_szamok = len(written) - len(v.fedetlen)
    v.ismetelt_jelolok = sorted(k for k, n in Counter(PLACEHOLDER.findall(model_text)).items() if n > 1)
    if v.fedetlen:
        v.problemak.append("vissza nem vezethető szám: " + ", ".join(v.fedetlen))
    if mod != "szabad":
        used = set(PLACEHOLDER.findall(model_text))
        row_of = {k: int(m.group(1)) for k, (_, path) in view_values.items()
                  if k in used and (m := ROW_PATH.match(path))}
        v.problemak += binding_problems(model_text, result, row_of)
    v.problemak += superlative_problems(final_text, result)
    causal = sorted({m.group(0).lower() for m in CAUSAL.finditer(final_text)})
    if causal:
        v.problemak.append("oksági állítás: " + ", ".join(causal))
    v.ok = not v.problemak
    return v
