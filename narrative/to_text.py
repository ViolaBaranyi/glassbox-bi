"""
② hívás: a lekérdezés eredményéből (MetricResult) magyar válasz — hely-kitöltéssel
(rendszerterv 02/D, 14.).

A modell az eredmény egy szöveges nézetét látja, amelyben minden szám mellett egy jelölő áll
({N} = 96 470, {S1} = 21,4% …). A válaszában a számok helyére a jelölőt írja; a
behelyettesítést a kód végzi, utána a KAPU ② (verifier.py) ellenőriz. Ha a szöveg nem megy át,
vagy a modell nem érhető el, a sablonos válasz (semantic/answer.py) látszik — a felület
nyelvi modell nélkül is teljes (NF-4).

A v2-től a válasz kerete a kódé: a hatókör mondata (hány rendelés, melyik időszak, milyen
szűréssel) a válasz elé, a korlátok (kevés adat, együttjárás) mögé kerülnek, és a modell csak
a magot írja — legfeljebb három mondatot, ami közvetlenül felel a kérdésre. Az első valódi
futásban (v1) a modell a hatókört döcögősen fogalmazta, és ugyanazt a számot kétszer írta le;
a keret így mindig pontos, és a modellnek kevesebbet kell írnia (gyorsabb).

Kontrollág a méréshez (``mod="szabad"``, külön prompt: to_text_szabad): ugyanez jelölők
nélkül — a modell maga írja a számokat, a kapu csak mér, nem cserél (rendszerterv 01: „ha
bármelyik kaput kivesszük …”).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import date

from narrative.client import LlmClient, LLMUnavailable
from narrative.to_spec import load_template, parse_json
from narrative.verifier import PLACEHOLDER, Verdict, verify
from semantic import answer as ans
from semantic.answer import _NUMBER
from semantic.catalog import fmt_long_date
from semantic.engine import MetricResult
from xai import narrative as nv

SCHEMA = {"type": "object", "properties": {"szoveg": {"type": "string"}}, "required": ["szoveg"],
          "additionalProperties": False}
TIME_LIKE = ("honap", "ev", "het_napja")


@dataclass
class View:
    """Amit a modell az eredményből lát: szöveg jelölőkkel + a jelölők értéke."""
    text: str
    values: dict = field(default_factory=dict)       # jelölő → (megjelenített érték, payload-útvonal)


def _rows_for_view(r: MetricResult) -> list[int]:
    """A nézetbe kerülő sorok indexe: időbeli bontásnál minden megbízható sor időrendben,
    egyébként a rangsor eleje (limit) és a másik vége."""
    reliable = [i for i, row in enumerate(r.sorok) if not row["keves_adat"] and row["ertek"] is not None]
    if r.spec.rendezes == "bontas" and (r.bontas["id"] in TIME_LIKE or len(reliable) <= r.spec.limit):
        return reliable
    shown = reliable[: r.spec.limit]
    if len(reliable) > len(shown):
        shown.append(reliable[-1])
    return shown


def build_view(r: MetricResult, placeholders: bool = True) -> View:
    view = View(text="")
    m = r.metrika

    def put(key: str, shown: str, path: str) -> str:
        view.values[key] = (shown, path)
        return f"{{{key}}} = {shown}" if placeholders else shown

    lines = [f"Hatókör: {put('N', ans.fmt_count(r.osszesen['rendelesek']), 'osszesen.rendelesek')} "
             "kézbesített rendelés."]
    tol, ig = date.fromisoformat(r.idoablak["tol"]), date.fromisoformat(r.idoablak["ig"])
    lines.append(f"Időszak (a rendelés leadása): {put('TOL', fmt_long_date(tol), 'idoablak.tol')} – "
                 f"{put('IG', fmt_long_date(ig), 'idoablak.ig')}"
                 + (" — a teljes adat." if r.idoablak["teljes"] else "."))
    if r.szurok:
        lines.append("Szűrés: " + "; ".join(f"{f['rovid']}: " + " vagy ".join(f["cimkek"]) for f in r.szurok) + ".")
    else:
        lines.append("Szűrés: nincs.")
    if "idoablak_szukitve" in r.megjegyzesek:
        lines.append(f"Megjegyzés: a kérdés időszaka túlnyúlt az adaton; az adat "
                     f"{put('ADAT_TOL', fmt_long_date(date.fromisoformat(r.adat['tol'])), 'adat.tol')} és "
                     f"{put('ADAT_IG', fmt_long_date(date.fromisoformat(r.adat['ig'])), 'adat.ig')} közötti.")
    # a leírás zárójeles számpéldája („36 óra = 1,5 nap”) nem eredmény — ne lássa számként
    lines.append(f"Mérőszám: {m['nev']} — {re.sub(r'\s*\([^)]*\d[^)]*\)', '', m['leiras'])}")
    tot = r.osszesen
    if tot["ertek"] is None:
        lines.append(f"Összesített érték: nincs (ebben a körben nincs {m['alap_nev']}).")
    else:
        s = f"Összesített érték: {put('O', ans.fmt_value(m, tot['ertek']), 'osszesen.ertek')}"
        if tot.get("ci") and tot["ci"][0] is not None:
            s += (f"; 95%-os tartomány: {put('O_A', ans.fmt_value(m, tot['ci'][0]), 'osszesen.ci[0]')} – "
                  f"{put('O_F', ans.fmt_value(m, tot['ci'][1]), 'osszesen.ci[1]')}")
        if "alap" in tot:
            s += f"; alapja: {put('O_ALAP', ans.fmt_count(tot['alap']), 'osszesen.alap')} {m['alap_nev']}"
        lines.append(s + ".")
    if r.bontas and r.sorok:
        order = {"ertek_csokkeno": "a legnagyobb elöl", "ertek_novekvo": "a legkisebb elöl",
                 "bontas": "a bontás sorrendjében"}[r.spec.rendezes]
        lines.append(f"Bontás {r.bontas['szerint']} ({order}; csak az elég adatból számolt csoportok):")
        rows = _rows_for_view(r)
        reliable = sum(1 for row in r.sorok if not row["keves_adat"] and row["ertek"] is not None)
        for k, i in enumerate(rows, 1):
            if k == len(rows) and len(rows) < reliable and r.spec.rendezes != "bontas":
                skipped = put("KIHAGY", str(reliable - len(rows)), "sorok (a nézetből kihagyva)")
                lines.append(f"  … (további {skipped} csoport kihagyva; az utolsó a sor másik vége:)")
            row = r.sorok[i]
            parts = [f"  {row['megnevezes']}: {put(f'S{k}', ans.fmt_value(m, row['ertek']), f'sorok[{i}].ertek')}"]
            if m["egyseg"] != "darab":
                key = "alap" if "alap" in row else "rendelesek"
                word = m["alap_nev"] if key == "alap" else "rendelés"
                parts.append(f"{put(f'S{k}_N', ans.fmt_count(row[key]), f'sorok[{i}].{key}')} {word}")
            if "reszesedes" in row:
                parts.append(f"az összes {put(f'S{k}_X', nv.fmt_pct(row['reszesedes'], 1), f'sorok[{i}].reszesedes')}-a")
            elif "relativ" in row:
                parts.append(f"az összesített érték {put(f'S{k}_X', nv.fmt_num(row['relativ'], 1), f'sorok[{i}].relativ')}-szerese")
            lines.append("; ".join(parts))
        small = [row for row in r.sorok if row["keves_adat"]]
        if small:
            lines.append(f"Kevés adat: {put('K', str(len(small)), 'sorok (kevés adat)')} csoport (kevesebb mint "
                         f"{put('MIN', ans.fmt_count(m['min_csoport']), 'metrika.min_csoport')} rendelés) — "
                         "ezekre ne építs állítást.")
    if m["egyseg"] == "arany" and r.bontas:
        lines.append("Korlát: a csoportok közti különbség együttjárás, nem ok.")
    view.text = "\n".join(lines)
    return view


def fill(model_text: str, view: View) -> tuple[str, list[tuple[str, str]], list[str]]:
    """A jelölők helyére az értékek; vissza: a kész szöveg, a hivatkozások, az ismeretlen jelölők."""
    refs: list[tuple[str, str]] = []
    unknown: list[str] = []

    def sub(match):
        key = match.group(1)
        if key not in view.values:
            unknown.append(key)
            return match.group(0)
        shown, path = view.values[key]
        refs.append((shown, path))
        return shown

    out = PLACEHOLDER.sub(sub, model_text)
    out = re.sub(r"%\s*%", "%", out)                                  # „{S1}%” → 21,4%%
    for unit in ("nap", "BRL", "km"):
        out = re.sub(rf"\b{unit}\s+{unit}\b", unit, out)
    return out, refs, unknown


@dataclass
class TextAttempt:
    szoveg: str                       # amit a felhasználó lát
    sablon: bool                      # True: a sablonos válasz látszik
    ok_sablon: str | None = None      # miért a sablon
    modell_szoveg: str | None = None  # a modell szövege jelölőkkel (v2-től: csak a mag)
    verdict: Verdict | None = None
    hivatkozasok: list = field(default_factory=list)
    modell: str = ""
    digest: str | None = None
    ido_ms: float = 0.0
    nezet: str = ""
    modell_hiba: bool = False         # a modell nem volt elérhető (nem a szövege bukott el)
    prompt: str = ""                  # a prompt változata
    keret: bool = False               # True: a hatókört és a korlátot a kód írta (v2)
    idok: dict = field(default_factory=dict)   # betöltés, prompt, generálás (ms), ha a szolgáltató megadja


def _template(r: MetricResult, reason: str, **kw) -> TextAttempt:
    a = ans.answer(r)
    return TextAttempt(szoveg=a.text, sablon=True, ok_sablon=reason, hivatkozasok=a.hivatkozasok, **kw)


def _call(client: LlmClient, mod: str) -> str:
    """Melyik hívás-beállítás: a fő ág a to_text, a kontrollág a to_text_szabad."""
    return "to_text_szabad" if mod == "szabad" and "to_text_szabad" in client.cfg.hivasok else "to_text"


def framed(version: str) -> bool:
    """A v1 prompt a teljes választ a modellel íratta; a v2-től a keret a kódé."""
    return not version.endswith(".v1")


def to_text(question: str, r: MetricResult, client: LlmClient, mod: str = "jelolo",
            question_id: str | None = None) -> TextAttempt:
    """Eredmény → mondat. mod: "jelolo" (fő ág, hely-kitöltés) | "szabad" (kontrollág)."""
    if r.empty or r.osszesen["ertek"] is None:
        return _template(r, "üres eredmény — nincs mit megfogalmazni")
    call = _call(client, mod)
    version = client.cfg.hivasok[call].version
    keret = framed(version)
    view = build_view(r, placeholders=(mod == "jelolo"))
    system = load_template(client, call)
    if mod == "szabad" and call == "to_text":           # régi beállítás, külön kontrollprompt nélkül
        system = system.split("Szabályok:")[0] + "Válaszolj legfeljebb öt mondatban. A válaszod egy JSON-objektum: {\"szoveg\": \"…\"}."
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": f"A felhasználó kérdése: «{question.strip()}»\n\nAz eredmény:\n{view.text}"}]
    t0 = time.perf_counter()
    try:
        reply = client.chat(call, messages, SCHEMA, "valasz")
    except LLMUnavailable as exc:
        return _template(r, f"a nyelvi modell nem érhető el ({exc})", nezet=view.text, modell_hiba=True,
                         prompt=version)
    elapsed = (time.perf_counter() - t0) * 1000.0
    try:
        model_text = str(parse_json(reply.text).get("szoveg", "")).strip()
    except json.JSONDecodeError:
        model_text = ""
    if mod == "szabad":
        # kontrollág: a modell maga írja a számokat — minden értékhez illesztünk (csak mérünk)
        core, refs, unknown = model_text, [], []
    else:
        core, refs, unknown = fill(model_text, view)
    verdict = verify(model_text, core, view.values, unknown, r, mod=mod)
    if not model_text:
        verdict.ok = False
        verdict.problemak.append("üres vagy nem értelmezhető válasz")
    final = core
    if keret:
        head, tail = ans.frame(r)
        final = " ".join(p for p in (head.text, core, tail.text) if p)
        refs = head.hivatkozasok + refs + tail.hivatkozasok
    verdict.szamok = len(_NUMBER.findall(final))          # a kész szöveg összes száma (a keretével)
    client.log(hivas="to_text", prompt=version, mod=mod, **reply.log_fields(), ervenyes=verdict.ok,
               szamok=verdict.szamok, fedetlen=verdict.fedetlen, problemak=verdict.problemak,
               kozvetlen_szamok=verdict.kozvetlen_szamok, ismetelt_jelolok=verdict.ismetelt_jelolok or None,
               kerdes_id=question_id, kerdes=question, valasz=reply.text)
    meta = dict(modell_szoveg=model_text, verdict=verdict, modell=reply.model, digest=reply.digest,
                ido_ms=elapsed, nezet=view.text, prompt=version, keret=keret, idok=reply.idok)
    if verdict.ok or mod == "szabad":
        return TextAttempt(szoveg=final, sablon=False, hivatkozasok=refs, **meta)
    return _template(r, "a modell szövege nem ment át a 2. kapun: " + "; ".join(verdict.problemak), **meta)
