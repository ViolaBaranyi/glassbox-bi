"""
Megjelenítés és szöveg: a magyarázatból olvasható mondat — determinisztikusan.

    SHORT            rövid magyar név minden jellemzőhöz (a grafikonok címkéi)
    format_value     egy jellemző értéke emberi alakban (8 nap, 1 234 km, július, igen)
    display_frame    egy rendelés hozzájárulásai a megjelenítéshez: a hónap két
                     kódoló oszlopa (szinusz, koszinusz) EGY tényezővé összevonva
    narrative        a magyarázat sablonból írt bekezdése
    record_phrase    a becslés hitelessége: a hasonló becslésű rendelések közül
                     ténylegesen hány késett (a modell száma mellé, nem helyette)

A sablonos szöveg a nyelvi réteg viszonyítási alapja: ugyanazokból a mezőkből
készül, amelyekből később a nyelvi modell dolgozik (hely-kitöltés), csak itt
rögzített mondatszerkezettel. Minden szám a magyarázatból jön, semmi nem
„fejben" számolt.

A hónap összevonása csak megjelenítés: a magyarázó motor (xai.explain) a 22
jellemzőt adja, itt a két hónap-oszlop hatását összeadjuk (az additivitás
megmarad: a tényezők összege ugyanúgy p − p₀).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from pipeline.features import BOOLEAN_FEATURES, CATEGORICAL_FEATURES, FEATURE_INFO, FEATURES

# ------------------------------------------------------------------ nevek
SHORT = {
    "tetel_szam": "tételek száma",
    "elado_szam": "eladók száma",
    "kategoria_szam": "kategóriák száma",
    "kosar_ertek": "kosárérték",
    "szallitasi_dij": "szállítási díj",
    "dij_arany": "szállítási díj aránya",
    "tavolsag_km": "távolság",
    "suly_g": "súly",
    "terfogat_cm3": "térfogat",
    "vallalt_ido_nap": "vállalt szállítási idő",
    "honap_sin": "hónap (szinusz)",
    "honap_cos": "hónap (koszinusz)",
    "het_napja": "hét napja",
    "elado_korabbi_keses_arany": "eladó korábbi késési aránya",
    "elado_korabbi_rendelesek": "eladó korábbi rendelései",
    "elado_atlagos_feladas_nap": "eladó átlagos feladási ideje",
    "vevo_korabbi_rendelesek": "vevő korábbi rendelései",
    "azonos_allam": "azonos állam",
    "unnep_kozeli": "ünnep közeli időszak",
    "kategoria": "termékkategória",
    "elado_allam": "eladó állama",
    "vevo_allam": "vevő állama",
}

# A megjelenítésben egy tényezővé összevont jellemzők.
MONTH = "honap"
DISPLAY_GROUPS = {MONTH: ["honap_sin", "honap_cos"]}
DISPLAY_SHORT = {MONTH: "rendelés hónapja"}
DISPLAY_INFO = {MONTH: "a rendelés hónapja (a modellben szinusz + koszinusz körkódolással)"}
DISPLAY_FEATURES = [MONTH if f == "honap_sin" else f for f in FEATURES if f != "honap_cos"]

MONTHS = ["január", "február", "március", "április", "május", "június", "július",
          "augusztus", "szeptember", "október", "november", "december"]
DAYS = ["hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap"]

# (tizedesjegyek, mértékegység) — a számjellemzők megjelenítése
_NUMBER = {
    "tetel_szam": (0, " db"),
    "elado_szam": (0, ""),
    "kategoria_szam": (0, ""),
    "kosar_ertek": (2, " BRL"),
    "szallitasi_dij": (2, " BRL"),
    "tavolsag_km": (0, " km"),
    "suly_g": (0, " g"),
    "terfogat_cm3": (0, " cm³"),
    "vallalt_ido_nap": (0, " nap"),
    "elado_korabbi_rendelesek": (0, ""),
    "elado_atlagos_feladas_nap": (1, " nap"),
    "vevo_korabbi_rendelesek": (0, ""),
}
_PERCENT = {"dij_arany", "elado_korabbi_keses_arany"}
_EMPTY = {
    "elado_korabbi_keses_arany": "nincs előzmény",
    "elado_atlagos_feladas_nap": "nincs előzmény",
    "tavolsag_km": "nincs koordináta",
}


def display_name(key: str) -> str:
    return DISPLAY_SHORT.get(key) or SHORT[key]


def display_info(key: str) -> str:
    return DISPLAY_INFO.get(key) or FEATURE_INFO[key][1]


# ----------------------------------------------------------- számformátum
def fmt_num(x: float, digits: int = 1) -> str:
    """Magyar számalak: tizedesvessző, ezres tagolás nem törő szóközzel."""
    return f"{x:,.{digits}f}".replace(",", " ").replace(".", ",")


def fmt_pct(p: float, digits: int = 1) -> str:
    return fmt_num(100.0 * p, digits) + "%"


def fmt_pp(pp: float, digits: int = 1) -> str:
    """Előjeles százalékpont (valódi mínuszjellel)."""
    s = fmt_num(abs(pp), digits)
    return ("+" if pp >= 0 else "−") + s


def month_number(sin_v: float, cos_v: float) -> int:
    """A körkódolt hónap visszafejtése (1–12)."""
    m = round(math.atan2(float(sin_v), float(cos_v)) * 12 / (2 * math.pi)) % 12
    return 12 if m == 0 else int(m)


def _missing(v) -> bool:
    try:
        return v is None or bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def format_value(feature: str, value, row: pd.Series | None = None) -> str:
    """Egy jellemző (vagy a „honap" tényező) értéke emberi alakban."""
    if feature in (MONTH, "honap_sin", "honap_cos"):
        if row is None:
            raise ValueError("A hónaphoz a teljes sor kell (szinusz és koszinusz).")
        return MONTHS[month_number(row["honap_sin"], row["honap_cos"]) - 1]
    if _missing(value):
        return "ismeretlen" if feature in CATEGORICAL_FEATURES else _EMPTY.get(feature, "nincs adat")
    if feature in BOOLEAN_FEATURES:
        return "igen" if bool(value) else "nem"
    if feature == "het_napja":
        return DAYS[int(value)]
    if feature in _PERCENT:
        return fmt_pct(float(value), 1)
    if feature in _NUMBER:
        digits, unit = _NUMBER[feature]
        return fmt_num(float(value), digits) + unit
    return str(value)


# ------------------------------------------------- megjelenítési tényezők
def merge_display(pp: pd.DataFrame) -> pd.DataFrame:
    """n × 22 hozzájárulás → n × 21 megjelenítési tényező (a hónap összevonva)."""
    out = pp.copy()
    for key, cols in DISPLAY_GROUPS.items():
        out[key] = out[cols].sum(axis=1)
        out = out.drop(columns=cols)
    return out[DISPLAY_FEATURES]


def display_frame(pp_row: pd.Series, x_row: pd.Series) -> pd.DataFrame:
    """
    Egy rendelés tényezői |hatás| szerint csökkenő sorrendben:
        tenyezo  (kulcs), nev, ertek (szöveg), hatas_pp (előjeles százalékpont)
    """
    merged = merge_display(pp_row.to_frame().T).iloc[0]
    rows = []
    for key in DISPLAY_FEATURES:
        raw = None if key == MONTH else x_row[key]
        rows.append({"tenyezo": key, "nev": display_name(key),
                     "ertek": format_value(key, raw, x_row),
                     "hatas_pp": float(merged[key])})
    df = pd.DataFrame(rows)
    order = np.argsort(-np.abs(df["hatas_pp"].to_numpy()), kind="stable")
    return df.iloc[order].reset_index(drop=True)


# ----------------------------------------------------------------- szöveg
_VOWELS = set("aáeéiíoóöőuúüű")


def _with_article(word: str) -> str:
    return ("az " if word[:1].lower() in _VOWELS else "a ") + word


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " és " + items[-1]


def _factor(r) -> str:
    return f"{_with_article(r.nev)} ({r.ertek}; {fmt_pp(r.hatas_pp)} százalékpont)"


def natural_frequency(rate: float) -> tuple[int, int]:
    """(N, alap): „100-ból N", vagy „1000-ből N", ha 100-ból 1 alatt maradna."""
    n100 = round(100 * rate)
    return (int(n100), 100) if n100 >= 1 else (int(round(1000 * rate)), 1000)


def per_base(base: int) -> str:
    """„100-ból" / „1000-ből" (a toldalék a kiejtett számhoz illeszkedik)."""
    return "100-ból" if base == 100 else "1000-ből"


def frequency_phrase(p: float) -> str:
    """
    A becslés természetes gyakoriságként — feltételesen: csak akkor igaz, ha a modell
    az adott tartományban kalibrált. (Ha van múltbeli adat, a record_phrase a helyes.)
    """
    n, base = natural_frequency(p)
    return (f"Ha a modell ebben a tartományban jól kalibrált, {base} ilyen becsült kockázatú "
            f"rendelésből kb. {n} késik.")


RECORD_WHERE = {
    "test": "A teszt-időszakban",
    "valid": "A validációs időszakban (a teszt előtti három hónapban)",
}


def record_phrase(rec: dict) -> str:
    """
    A becslés múltbeli pontossága egy mondatban (ui.backend.similar_orders kimenete):
    a hasonló becslésű rendelések közül ténylegesen hány késett, és ez egyezik-e.
    """
    where = RECORD_WHERE.get(rec["ablak"], "A kiértékelt időszakban")
    if rec["rendelesek"] == 0:
        return f"{where} nem volt más, hasonló ({rec['sav_szoveg']}) becslésű rendelés."
    n, base = natural_frequency(rec["tenyleges_arany"])
    other = "másik " if rec.get("onmaga_kihagyva") else ""
    s = (f"{where} a hasonló, {rec['sav_szoveg']} becslésű rendelések közül {per_base(base)} "
         f"kb. {n} késett ténylegesen ({fmt_num(rec['rendelesek'], 0)} {other}rendelésből "
         f"{fmt_num(rec['kesett'], 0)})")
    v = rec["itelet"]
    if v in ("túlbecsült", "alábecsült"):
        s += (f" — ebben a sávban a modell {v} (átlagosan {fmt_pct(rec['atlag_becsles'])}-ot "
              "mondott).")
    elif v == "összhangban":
        s += " — ez összhangban van a modell becslésével."
    else:
        s += " — ennyi rendelésből a modell pontosságáról még nem lehet ítélni."
    return s


def credibility_note(rec: dict) -> tuple[str, str]:
    """
    A becslés hitelessége a felületre: ("figyelmeztetes" | "megjegyzes", szöveg).
    Figyelmeztetés, ha a hasonló becslésűek tényleges aránya a 95%-os intervallummal
    együtt is eltér a modell átlagos becslésétől; különben rövid megjegyzés.
    """
    where = RECORD_WHERE.get(rec["ablak"], "A kiértékelt időszakban")
    n, v = rec["rendelesek"], rec["itelet"]
    if n == 0:
        return "megjegyzes", f"{where} nem volt más, hasonló ({rec['sav_szoveg']}) becslésű rendelés."
    other = "másik " if rec.get("onmaga_kihagyva") else ""
    facts = (f"A hasonló ({rec['sav_szoveg']}) becslésű {fmt_num(n, 0)} {other}rendelésből "
             f"{fmt_num(rec['kesett'], 0)} késett ({fmt_pct(rec['tenyleges_arany'])}; 95%-os "
             f"intervallum: {fmt_pct(rec['ci_also'])} – {fmt_pct(rec['ci_felso'])})")
    mean, base, rel = rec["atlag_becsles"], rec["idoszak_arany"], rec["relativ_tenyleges"]
    if v == "túlbecsült":
        text = (f"**{where} ebben a sávban a modell túlbecsült.** {facts}, miközben a modell "
                f"átlagosan {fmt_pct(mean)}-ot mondott. ")
        if np.isfinite(rel) and rel >= 1.1:
            text += (f"A sorrend ettől még használható: ezek a rendelések kb. {fmt_num(rel, 1)}-szer "
                     f"olyan gyakran késtek, mint az időszak átlaga ({fmt_pct(base)}). A pontos "
                     "százalékot viszont nem érdemes szó szerint venni.")
        else:
            text += (f"Ezek a rendelések nem késtek gyakrabban az időszak átlagánál "
                     f"({fmt_pct(base)}) — itt a becslés félrevezető.")
        return "figyelmeztetes", text
    if v == "alábecsült":
        return "figyelmeztetes", (
            f"**{where} ebben a sávban a modell alábecsült.** {facts}, miközben a modell átlagosan "
            f"csak {fmt_pct(mean)}-ot mondott: a valóság rosszabb volt a becslésnél.")
    lead = f"{where} {facts[0].lower()}{facts[1:]}"
    if v == "összhangban":
        return "megjegyzes", (f"{lead} — összhangban a modell átlagos {fmt_pct(mean)}-os "
                              "becslésével.")
    return "megjegyzes", f"{lead}. Ennyi rendelésből a becslés hitelességéről még nem lehet ítélni."


def relative_phrase(p: float, avg: float) -> str:
    rel = p / avg if avg > 0 else float("nan")
    if not np.isfinite(rel):
        return ""
    # egy tizedesjeggyel a szám „…tized”-re végződik, így a -szerese rag mindig helyes
    if rel >= 1.1:
        return f"ez az időszak átlagos becslésének ({fmt_pct(avg)}) {fmt_num(rel, 1)}-szerese"
    if rel <= 0.9:
        return f"ez az időszak átlagos becslésének ({fmt_pct(avg)}) csak {fmt_num(100 * rel, 0)}%-a"
    return f"ez nagyjából az időszak átlagos becslése ({fmt_pct(avg)})"


def narrative(p: float, p0: float, avg: float, frame: pd.DataFrame,
              k: int = 3, min_pp: float = 0.05, record: dict | None = None) -> str:
    """
    A magyarázat egy bekezdésben. `frame` a display_frame kimenete; csak a
    legalább `min_pp` százalékpontos tényezők kerülnek a szövegbe (legfeljebb k).
    A végén a becslés hitelessége: ha van `record` (a hasonló becslésűek múltbeli
    kimenete), az; ha nincs, a becslés feltételes természetes gyakorisága.
    """
    rel = relative_phrase(p, avg)
    parts = [f"A modell szerint ez a rendelés {fmt_pct(p)} eséllyel késik"
             + (f" — {rel}." if rel else ".")]
    up = [_factor(r) for r in frame[frame["hatas_pp"] >= min_pp].head(k).itertuples()]
    down = [_factor(r) for r in frame[frame["hatas_pp"] <= -min_pp].head(k).itertuples()]
    s = f"A modell kiindulópontja {fmt_pct(p0)}"
    if up and down:
        s += f"; a becslést leginkább {_join(up)} növeli, leginkább {_join(down)} csökkenti."
    elif up:
        s += f"; a becslést leginkább {_join(up)} növeli."
    elif down:
        s += f"; a becslést leginkább {_join(down)} csökkenti."
    else:
        s += "; egyik tényező sem mozdítja el számottevően."
    parts.append(s)
    parts.append(record_phrase(record) if record else frequency_phrase(p))
    return " ".join(parts)
