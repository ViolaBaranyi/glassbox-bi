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
  5. nincs-e oksági állítás („okozza”, „eredményezi” …) — az eredmény együttjárás;
  6. a 95%-os tartomány határai tartományként szerepelnek-e (a fejlesztői próbán a modell az
     összesített érték tartományát az időszak „mélypontjának” és „csúcsának” nevezte — a
     számok visszavezethetők voltak, a szerepük hamis);
  7. nem tagadja-e a modell a szűrést („nem tartalmaz időbeli vagy regionális szűrést” — a
     hatókört a kód írja, a modellnek nincs róla mondanivalója).

Havi bontásnál a hónap neve évszám nélkül is a sor neve („decemberben érte el a csúcsát”
— a „csúcs” és a „mélypont” is felsőfok), „X: Y” alakú névnél az Y is; többes számú
felsőfoknál („az Észak és a Közép-Nyugat … a legkisebb”) elég, ha a mellérendelt nevek
egyike a szélső érték.

A számokat ezres tagolással is felismeri, akár nem törő, akár sima szóközzel írták („987 648”
— a modell a nézet nem törő szóközét gyakran simára cseréli; a fejlesztői próbán ezért esett
el négy helyes szöveg). A mondathatár csak nagybetű vagy jelölő előtt van, és nem vág bele a
csoportnevekbe („háztartási gépek (2. csoport)”). Az eredmény dátumai rövidítve is
elfogadottak („augusztus 29.”).

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
from datetime import date

from semantic.answer import CONFIDENCE
from semantic.catalog import MONTHS, fmt_long_date
from semantic.engine import MetricResult

PLACEHOLDER = re.compile(r"\{([A-Z][A-Z0-9_]*)\}")
ROW_PATH = re.compile(r"sorok\[(\d+)\]\.(?:ertek|rendelesek|alap|reszesedes|relativ)$")
MAX_WORDS = ("legmagasabb", "legnagyobb", "legtobb", "leghosszabb", "leglassabb", "csucs")
MIN_WORDS = ("legalacsonyabb", "legkisebb", "legkevesebb", "legrovidebb", "leggyorsabb", "melypont")
COORDINATED = re.compile(r"^\s*(?:\([^)]*\))?\s*(?:es|valamint|illetve|,)\s*(?:az?\s+)?$")
SCOPE_DENIAL = re.compile(r"(?:\bnem\b|\bnincs\w*|\bnelkul)[^.;]*\bszur|\bszur\w*[^.;]*(?:\bnem\b|\bnincs\w*|\bnelkul)")
ORDINAL = re.compile(r"(?:masodik|harmadik|negyedik|otodik|hatodik)\s*$")
CLAUSE = re.compile(r"[,;:–—]|\s(?:mig|de|viszont|pedig|illetve|es|valamint|ugyanakkor|azonban)\s")
LISTING = re.compile(r"\b(?:illetve|rendre)\b")
CAUSAL = re.compile(r"\b(okoz\w*|okozój\w*|eredményez\w*|következtében|hatására)\b", re.I)
NBSP = re.compile(r"[\u00a0\u202f]")
# szám magyar alakban: ezres tagolás (nem törő vagy sima szóközzel), tizedesvessző
NUMBER = re.compile(r"\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:,\d+)?|\d+(?:,\d+)?")
SENTENCE_END = re.compile(r"(?<=[.!?;])\s+(?=[A-ZÁÉÍÓÖŐÚÜŰ{„])")
CI_KEYS = ("O_A", "O_F")
CI_WORDS = re.compile(r"tartomany|intervallum|95|bizonytalan|ingadoz|hibahatar")


@dataclass
class Verdict:
    ok: bool
    problemak: list[str] = field(default_factory=list)
    szamok: int = 0                  # a kész szöveg összes száma
    fedetlen: list[str] = field(default_factory=list)
    ismeretlen_jelolok: list[str] = field(default_factory=list)
    kozvetlen_szamok: int = 0        # amit a modell jelölő helyett maga írt le (de visszavezethető)
    ismetelt_jelolok: list[str] = field(default_factory=list)   # stílus: ugyanaz a jelölő többször (nem hiba)
    ismetelt_ertekek: list[str] = field(default_factory=list)   # stílus: ugyanaz az érték többször a szövegben

    @property
    def fedett(self) -> int:
        return self.szamok - len(self.fedetlen)


def _as_date(v) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


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
    m = re.fullmatch(r"[^:]+: (.+)", f)                           # „kisgépek: sütők és kávéfőzők” → a második fele is
    if m and len(m.group(1)) >= 8:
        tail = r"\w*" if f[-1:].isalnum() else ""
        return [(re.compile(rf"(?<!\w){re.escape(f)}{tail}"), True),
                (re.compile(rf"(?<!\w){re.escape(m.group(1))}{tail}"), True)]
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

    def add(pattern, on_folded, row):
        for m in pattern.finditer(folded if on_folded else text):
            if not any(m.start() < s.end and s.start < m.end() for s in spans):
                spans.append(Span(m.start(), m.end(), row))

    for label, row in sorted(names, key=lambda n: -len(n[0])):
        for pattern, on_folded in _name_patterns(label):
            add(pattern, on_folded, row)
    # havi bontásnál a hónap neve évszám nélkül is a sor neve, ha egyértelmű („decemberben”)
    if result.bontas and result.bontas.get("id") == "honap":
        months = [fold(r["megnevezes"]).split(". ", 1)[-1] for r in result.sorok]
        if len(set(months)) == len(months):
            for i, month in enumerate(months):
                add(re.compile(rf"(?<!\w){re.escape(month)}\w*"), True, i)
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


def norm(text: str) -> str:
    """A nem törő szóközök simára — a modell és a nézet így ugyanazt a számalakot látja."""
    return NBSP.sub(" ", text)


def numbers(text: str) -> list[str]:
    return NUMBER.findall(norm(text))


def uncovered(text: str, refs) -> list[str]:
    """A szöveg számai közül azok, amelyek nem vezethetők vissza a hivatkozott alakokra."""
    rest = norm(text)
    for shown in sorted({norm(shown) for shown, _ in refs}, key=len, reverse=True):
        rest = rest.replace(shown, " ")
    return NUMBER.findall(rest)


def _sentences(text: str, result: MetricResult | None = None) -> list[str]:
    """Mondatok: határ csak írásjel + szóköz + nagybetű/jelölő előtt, és nem csoportnéven belül."""
    spans = name_spans(text, result) if result is not None else []
    out, start = [], 0
    for m in SENTENCE_END.finditer(text):
        if any(s.start < m.start() < s.end for s in spans):
            continue
        out.append(text[start:m.start()])
        start = m.end()
    out.append(text[start:])
    return [s for s in out if s.strip()]


def _date_forms(d) -> list[str]:
    """Egy eredménybeli dátum elfogadott alakjai: „2018. augusztus 29.”, „augusztus 29.”."""
    month = MONTHS[d.month - 1]
    return [fmt_long_date(d), f"{month} {d.day}.", f"{month} {d.day}"]


def ci_problems(model_text: str, view_values: dict, result: MetricResult) -> list[str]:
    """A 95%-os tartomány határa (jelölővel vagy leírva) csak tartományként szerepelhet."""
    keys = [k for k in CI_KEYS if k in view_values]
    if not keys:
        return []
    others = {norm(shown) for k, (shown, _) in view_values.items() if k not in CI_KEYS}
    literal = {k: norm(view_values[k][0]) for k in keys if norm(view_values[k][0]) not in others}
    out = []
    for sentence in _sentences(model_text, result):
        ns = norm(sentence)
        used = [k for k in keys if "{" + k + "}" in sentence or
                (k in literal and re.search(rf"(?<![\d,]){re.escape(literal[k])}", ns))]
        if used and not CI_WORDS.search(fold(sentence)):
            out.append("a 95%-os tartomány határa (" + ", ".join("{" + k + "}" for k in used)
                       + ") nem tartományként szerepel")
    return out


# ------------------------------------------------------------ 3. a kötés
def binding_problems(model_text: str, result: MetricResult, row_of: dict[str, int]) -> list[str]:
    """A csoportértékek jelölője a saját csoportja mellett áll-e. row_of: jelölő → sor."""
    if not result.bontas or not row_of:
        return []
    out = []
    for sentence in _sentences(model_text, result):
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


def _coordinated(spans: list[Span], span: Span, folded: str) -> list[Span]:
    """A névvel „és”-sel (vesszővel) mellérendelt nevek: többes számú felsőfoknál a csoport."""
    rows = [s for s in spans if s.row is not None]
    i = rows.index(span)
    group = [span]
    j = i
    while j > 0 and COORDINATED.match(folded[rows[j - 1].end:rows[j].start]):
        j -= 1
        group.append(rows[j])
    j = i
    while j + 1 < len(rows) and COORDINATED.match(folded[rows[j].end:rows[j + 1].start]):
        j += 1
        group.append(rows[j])
    return group


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
    for sentence in _sentences(text, result):
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
                    if any(s.row in expected for s in _coordinated(spans, span, folded)):
                        continue                               # „az Észak és a Közép-Nyugat … a legkisebb”
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
    # az eredmény dátumai (az időablak és az adat széle), rövidítve is: a kérdés hatóköre, nem állítás
    dates = [(form, f"{part}.{end}") for part in ("idoablak", "adat") for end in ("tol", "ig")
             if (getattr(result, part) or {}).get(end)
             for form in _date_forms(_as_date((getattr(result, part))[end]))]
    # évszám a címkékből és a dátumokból („2018 márciusában”): megnevezés, nem állítás
    years = {y for text, _ in names + dates + list(view_values.values())
             for y in re.findall(r"\b(?:19|20)\d\d\b", text)}
    fixed = [(CONFIDENCE, "konstans: a tartományok szintje")] + [(y, "évszám") for y in years] + dates
    values = [(shown, path) for shown, path in view_values.values() if mod == "szabad" or distinctive(shown)]
    own = PLACEHOLDER.sub(" ", model_text)                       # amit a modell maga írt
    plain = norm(own)
    for text, _ in sorted(names + fixed, key=lambda r: -len(r[0])):
        plain = plain.replace(norm(text), " ")
    written = NUMBER.findall(plain)                              # a modell saját számai
    v.fedetlen = uncovered(own, names + fixed + values)
    v.szamok = len(numbers(final_text))
    v.kozvetlen_szamok = len(written) - len(v.fedetlen)
    v.ismetelt_jelolok = sorted(k for k, n in Counter(PLACEHOLDER.findall(model_text)).items() if n > 1)
    nf = norm(final_text)
    v.ismetelt_ertekek = sorted({norm(shown) for shown, _ in view_values.values()
                                 if distinctive(shown) and len(re.findall(rf"(?<![\d,]){re.escape(norm(shown))}", nf)) > 1})
    if v.fedetlen:
        v.problemak.append("vissza nem vezethető szám: " + ", ".join(v.fedetlen))
    if mod != "szabad":
        used = set(PLACEHOLDER.findall(model_text))
        row_of = {k: int(m.group(1)) for k, (_, path) in view_values.items()
                  if k in used and (m := ROW_PATH.match(path))}
        v.problemak += binding_problems(model_text, result, row_of)
    v.problemak += superlative_problems(final_text, result)
    v.problemak += ci_problems(model_text, view_values, result)
    if any(SCOPE_DENIAL.search(fold(sentence)) for sentence in _sentences(model_text, result)):
        v.problemak.append("állítás a szűrésről (a hatókört a rendszer írja; a modell tagadta a szűrést)")
    causal = sorted({m.group(0).lower() for m in CAUSAL.finditer(final_text)})
    if causal:
        v.problemak.append("oksági állítás: " + ", ".join(causal))
    v.ok = not v.problemak
    return v
