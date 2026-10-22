"""
Magyar köznyelvi szótár a nyelvi réteghez (v5, a v2 mérése után, 2026-10-22).

A v2 mérésen a 4B és a 9B ugyanott hibázott: a köznyelvi kategórianevet („lakberendezés”,
„számítógépek”) a kód nem kötötte a katalógus értékéhez, és a kérdésben kimondott mérőszámot
(„mibe kerül a szállítás”, „végösszeg”, „mediám”) a modell egy másikkal cserélte vagy elutasította.
Ez a modul determinisztikusan, átlátható szólistákkal dönt — a felület meg is mondja, melyik szó
alapján (a v5 javítások a narrative/to_spec.py `correct` lépésében).

Két rész:
  * KATEGORIA: kategória → köznyelvi szavak (szótő, ékezet nélkül is). A címke szavain felül; a
    hosszabb egyezés nyer („játékkonzol” a konzoloké, nem a játékoké).
  * METRIKA_JEL: mérőszám → a kérdésben kimondó kifejezések. metric_cue() csak akkor ad választ, ha
    a kérdés egyetlen mérőszámot nevez meg (a specifikusabb nyer: „késett rendelések” a
    „rendelések száma” ellen, „medián” az „átlagos szállítási idő” ellen).
"""

from __future__ import annotations

import re
import unicodedata


def fold(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", str(text).lower()) if not unicodedata.combining(ch))


# ------------------------------------------------------------------ kategóriák
# Az első szó a fő köznyelvi név. A rövid szavak (4 betű alatt) csak ragozva illeszkednek (lásd _SUFFIX).
KATEGORIA: dict[str, list[str]] = {
    "furniture_decor": ["bútor", "lakberendezés", "lakásberendezés", "lakásdekor", "dekoráció", "lakberendezési"],
    "health_beauty": ["szépségápolás", "egészségügyi", "egészség", "kozmetikum", "kozmetika", "szépség"],
    "sports_leisure": ["sport", "sportszer", "szabadidő"],
    "fashion_sport": ["sportruházat", "sportruha"],
    "computers": ["számítógép", "laptop", "notebook"],
    "computers_accessories": ["számítógép-tartozék", "számítógéptartozék", "informatika", "számítástechnika"],
    "toys": ["játék"],
    "consoles_games": ["játékkonzol", "konzol", "videojáték"],
    "electronics": ["elektronika", "elektronikai"],
    "bed_bath_table": ["lakástextil", "ágynemű", "törölköző", "fürdőszobai textil"],
    "housewares": ["háztartási cikk", "konyhai eszköz", "edény"],
    "watches_gifts": ["karóra", "óra", "ajándék"],
    "telephony": ["telefon", "mobil", "okostelefon"],
    "fixed_telephony": ["vezetékes telefon"],
    "auto": ["autó", "autós", "autóalkatrész"],
    "baby": ["baba", "babatermék", "babacucc"],
    "perfumery": ["parfüm", "illatszer"],
    "garden_tools": ["kerti eszköz", "kert"],
    "pet_shop": ["kisállat", "háziállat", "állateledel", "kutya", "macska"],
    "stationery": ["írószer", "papíráru"],
    "fashion_bags_accessories": ["táska"],
    "office_furniture": ["irodabútor"],
    "books_general_interest": ["könyv"],
    "food": ["élelmiszer"],
    "drinks": ["ital"],
    "audio": ["hangtechnika", "hangfal", "fülhallgató"],
    "musical_instruments": ["hangszer"],
    "luggage_accessories": ["bőrönd"],
    "home_appliances": ["háztartási gép"],
    "small_appliances": ["háztartási kisgép", "kisgép"],
    "christmas_supplies": ["karácsonyi"],
    "fashion_shoes": ["cipő"],
}

# ragok a rövid (5 betű alatti) szavakhoz: „óra” ~ „órák, órát, órákat”, de nem „óraszám”
_SUFFIX = re.compile(r"(?:k|ok|ek|ak|at|et|ot|t|kat|okat|eket|akat|nal|nel|knal|oknal|eknel|aknal|ban|ben|kban|okban|"
                     r"ekben|akban|bol|rol|ra|re|kra|okra|ekre|akra|hoz|hez|i|ink|ja|je|ai|ei|ok|unk|unkat)?")
_SHORT = 5


def _matches(word: str, stem: str) -> bool:
    if not word.startswith(stem):
        return False
    return len(stem) >= _SHORT or _SUFFIX.fullmatch(word[len(stem):]) is not None


def _phrase_hits(words: list[str], phrase: str) -> int:
    """Hány betűs egyezés a kifejezésre (0: nincs) — több szavas kifejezésnél egymás utáni szavakkal."""
    parts = fold(phrase).replace("-", " ").split()
    for i in range(len(words) - len(parts) + 1):
        if all(_matches(words[i + j], p) if j == len(parts) - 1 else words[i + j].startswith(p[:max(3, len(p) - 2)])
               for j, p in enumerate(parts)):
            return sum(len(p) for p in parts)
    return 0


def category_mentions(text: str, keys=None) -> dict[str, int]:
    """A szövegben köznyelvi szóval megnevezett kategóriák → az egyezés hossza. Egy szóért a
    leghosszabb egyezés kapja a pontot (a „játékkonzolok” nem játék)."""
    words = re.findall(r"[a-z0-9]+", fold(text).replace("-", ""))
    best: dict[int, tuple[int, str]] = {}
    for key, aliases in KATEGORIA.items():
        if keys is not None and key not in keys:
            continue
        for alias in aliases:
            parts = fold(alias).replace("-", "").split()
            for i in range(len(words) - len(parts) + 1):
                if all(_matches(words[i + j], p) for j, p in enumerate(parts)):
                    score = sum(len(p) for p in parts)
                    pos = i + len(parts) - 1
                    if score > best.get(pos, (0, ""))[0]:
                        best[pos] = (score, key)
    out: dict[str, int] = {}
    for score, key in best.values():
        out[key] = max(out.get(key, 0), score)
    return out


def category_of(text: str, keys=None) -> str | None:
    """Egyetlen, köznyelvi szóval megnevezett kategória (vagy None, ha nincs vagy több van)."""
    found = category_mentions(text, keys)
    return next(iter(found)) if len(found) == 1 else None


# ------------------------------------------------------------------ régiók (a vevőé)
# a rövid tő („dél”) csak raggal: „délen, délre, déli”, de nem „délkeleti”
REGIO: dict[str, list[str]] = {"N": ["észak"], "NE": ["északkelet"], "CO": ["közép-nyugat", "középnyugat"],
                               "SE": ["délkelet"], "S": ["dél"]}
_REGION_SUFFIX = re.compile(r"(?:i|ra|re|on|en|rol|ban|ben|nak|nek|ba|be|ig|iak|ieknek|ieknel|iaknal|i\s*regio\w*)?")


def region_of(text: str) -> str | None:
    """Egyetlen, a kérdésben megnevezett vevői régió (vagy None, ha nincs vagy több van)."""
    f = fold(text).replace("-", "")
    found = set()
    for key, names in REGIO.items():
        for name in names:
            stem = fold(name).replace("-", "")
            for m in re.finditer(rf"\b{stem}(\w*)", f):
                if _REGION_SUFFIX.fullmatch(m.group(1)):
                    found.add(key)
    return next(iter(found)) if len(found) == 1 else None


# ------------------------------------------------------------------ mérőszámok
_COUNT_OBJ = r"(?!pez|penz|bevetel|forgalm|haszn|nyereseg)\w+(?:at|et|ot|t)\b"
METRIKA_JEL: dict[str, re.Pattern] = {
    "median_szallitasi_ido": re.compile(
        r"\bmedia[nm]\w*(?:\s+\w+){0,3}?\s+(?:ki)?szallitas\w*|\b(?:ki)?szallitasi\s+(?:ido|idej)\w*\s+media[nm]\w*"),
    "atlagos_vallalt_ido": re.compile(r"\bvallalt\s+(?:szallitasi\s+)?(?:ido|idej|hatarido)\w*|\bvallalt\s+kiszallit\w*"),
    "kesesi_arany": re.compile(r"\b(?:keses\w*|csuszas\w*|kesett\w*)\s+(?:arany\w*|szazalek\w*)|"
                               r"\b(?:arany\w*|szazalek\w*)\s+(?:a\s+)?(?:keses|csuszas|kesett)\w*|\bhany\s+szazalek\w*\s+kes\w*"),
    "atlagos_keses": re.compile(r"\b(?:keses|csuszas)\w*\s+(?:atlag\w*|napokban)|\batlagos\s+(?:keses|csuszas)\w*|"
                                r"\bhany\s+nap\w*\s+(?:a\s+)?(?:keses|csuszas)\w*|\bkeses\w*\s+(?:napokban\s+)?merve|"
                                r"\bmelle\s*fog\w*|\bfog(?:tak|nak|ott|ja|jak)?\s+(?:a\s+)?(?:\w+\s+)?melle\b"),   # „mellé fognak a határidővel”
    "kesett_rendelesek": re.compile(r"\bkesett\s+(?:rendeles|csomag|szallitas)\w*\s+szam\w*|"
                                    r"\bhany\s+(?:\w+\s+){0,3}?kes(?:ve|ett|ik|tek)\w*|\blegtobb?\s+kes(?:est|ese)\w*"),
    "atlagos_szallitasi_dij": re.compile(
        r"\b(?:szallitasi|fuvar|posta)\s*(?:dij|koltseg)\w*|\bfuvardij\w*|\bszallitas\w*\s+(?:ara|koltseg\w*)\b|"
        r"\bmibe\s+kerul\w*(?:\s+\w+){0,2}?\s+(?:a\s+)?szallitas\w*|\bszallitas\w*\s+mibe\s+kerul"),
    "atlagos_tavolsag": re.compile(r"\btavolsag\w*|\bkm\b|\bkilometer\w*|\bmessze\w*|\blegmesszebb\w*|\butazik\s+a\s+legtobbet"),
    "atlagos_kosarertek": re.compile(r"\bkosar\s*ertek\w*|\brendelesi\s+ertek\w*|\brendeles\w*\s+ertek(?:e|et)\b"),
    "forgalom": re.compile(r"\b(?:bevetel\w*|arbevetel\w*|vegosszeg\w*|forgalm\w*|pezt?\b|penz\w*\s+(?:jott|hoz\w*|csinal\w*|folyt))"),
    "atlagos_szallitasi_ido": re.compile(
        r"\b(?:ki)?szallitasi\s+(?:ido|idej)\w*|\bmennyi\s+ido\s+alatt|\bhany\s+nap\s+alatt|\bmeddig\s+tart\w*|\bmilyen\s+gyorsan"),
    "rendelesek_szama": re.compile(r"\brendeles\w*\s+szam\w*|\bhany\s+(?:darab\s+)?(?:meg)?rendeles\w*|"
                                   r"\bhany\s+(?:darab\s+)?csomag\w*|\blegtobb?\s+" + _COUNT_OBJ + r"|\blegkevesebb\s+" + _COUNT_OBJ +
                                   r"|\b(?:adtak|adtunk|adott)\s+el\s+(?:a\s+)?leg\w+|\beladt\w*\s+(?:a\s+)?leg\w+"),   # „miből adtak el a legkevesebbet”
}
# ha mindkettő megszólal, a specifikusabb nyer
SPECIFIKUSABB = {("kesett_rendelesek", "rendelesek_szama"), ("median_szallitasi_ido", "atlagos_szallitasi_ido"),
                 ("atlagos_vallalt_ido", "atlagos_szallitasi_ido"), ("atlagos_keses", "kesett_rendelesek"),
                 ("kesesi_arany", "kesett_rendelesek"),
                 # a késés a vállalt határidőhöz mért: ha mindkettő szól („mellé fognak a vállalt idővel”), a késés a kérdés
                 ("atlagos_keses", "atlagos_vallalt_ido"), ("kesesi_arany", "atlagos_vallalt_ido")}


def metric_cues(text: str) -> dict[str, str]:
    """A kérdésben kimondott mérőszámok → a kiváltó kifejezés (a specifikusabb elnyomja az általánosabbat)."""
    f = " ".join(fold(text).split())
    found = {m: hit.group(0) for m, p in METRIKA_JEL.items() if (hit := p.search(f))}
    # az eredeti találatokból — a halmaz bejárási sorrendje (hash) ne számítson
    weaker = {weak for strong, weak in SPECIFIKUSABB if strong in found and weak in found}
    return {m: w for m, w in found.items() if m not in weaker}


def metric_cue(text: str) -> tuple[str, str] | None:
    """Ha a kérdés egyetlen mérőszámot nevez meg: (azonosító, a kifejezés); különben None."""
    found = metric_cues(text)
    return next(iter(found.items())) if len(found) == 1 else None
