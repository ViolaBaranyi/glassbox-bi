"""
K1 mérés (rendszerterv 18.): a nyelvi réteg a lezárt kérdéssoron, a lezárt protokoll szerint
(docs/k1_protokoll.json). Ez adja a dolgozat F-1, F-2 és K1 számait.

    uv run python -m narrative.meres --ellenoriz        # a kérdéssor és a protokoll állapota (modell nélkül)
    uv run python -m narrative.meres --lezar            # a kérdéssor ujjlenyomata a protokollba (egyszer)
    uv run python -m narrative.meres --jovahagy "Név"   # a protokoll jóváhagyása (a lezárás után)
    uv run python -m narrative.meres                    # mérés a protokoll első modelljével
    uv run python -m narrative.meres --modell qwen3:8b  # a protokoll másik modelljével
    uv run python -m narrative.meres --folytat logs/meres/<mappa>     # megszakadt mérés folytatása
    uv run python -m narrative.meres --jelentes logs/meres/<mappa>    # a jelentés újra (modell nélkül)
    uv run python -m narrative.meres --olvashato        # a kérdéssor olvasható változata (.md)

Mérni csak jóváhagyott protokollal és a lezárt kérdéssorral lehet: ha a kérdéssor ujjlenyomata
nem egyezik a protokollba írttal, a parancs nem indul el. Egy kérdés egy ismétlésében az ①
hívás egyszer fut, és ugyanabból az eredményből készül a fő ág (jelölőkkel) és a kontrollág
(a modell maga írja a számokat) szövege; a két ág sorrendje ismétlésenként váltakozik.

Minden kérdés eredménye azonnal a mappa sorok.jsonl fájljába kerül, így a megszakadt mérés
folytatható (a kód és a promptok ujjlenyomatának egyeznie kell). A végén: jelentes.md,
osszegzes.json és a kézi ellenőrzés mintája (kezi_ellenorzes.csv, a kulcs külön fájlban).
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
import math
import random
import re
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from data.db import DB_PATH, WarehouseUnavailable, connect, use_utf8_console
from narrative import VERZIO, proba
from narrative.client import ROOT, LlmClient, load_config
from narrative.to_spec import to_spec
from narrative.to_text import TextAttempt, to_text
from semantic import catalog, engine
from semantic import spec as sp
from xai import narrative as nv

PROTOKOLL = ROOT / "docs" / "k1_protokoll.json"
KERDESSOR_NEV = "eval/meresi_kerdessor.toml"
MERES = ROOT / "logs" / "meres"
AGAK = ("jelolo", "szabad")
AG_NEV = {"jelolo": "fő ág (jelölők)", "szabad": "kontrollág (szabad)"}
TIPUSOK = ("osszesito", "rangsor", "szures", "idoszak", "idosor", "kombinalt", "nyelvi", "csapda")
CSAPDAK = ("nincs_adat", "jovo", "adaton_kivul", "katalogus_kivul", "tiltott", "korlat", "atveres", "nem_adat",
           "ketertelmu", "tobblepeses")
SZERZOK = ("claude", "viola")
# a 2. kapu üzeneteinek fajtái (az alá nem támasztott állítások, rendszerterv 15–16.)
FAJTAK = [
    ("ismeretlen_jelolo", re.compile(r"^ismeretlen jelölő")),
    ("fedetlen_szam", re.compile(r"^vissza nem vezethető szám")),
    ("kotes", re.compile(r"értéke, de „|^a felsorolásban")),
    ("felsofok", re.compile(r"nem a (?:legnagyobb|legkisebb) érték")),
    ("tartomany", re.compile(r"^a 95%-os tartomány")),
    ("hatokor", re.compile(r"^állítás a szűrésről")),
    ("oksag", re.compile(r"^oksági állítás")),
    ("ures", re.compile(r"^üres vagy nem értelmezhető")),
]
FAJTA_NEV = {"ismeretlen_jelolo": "kitalált jelölő", "fedetlen_szam": "vissza nem vezethető szám",
             "kotes": "rossz csoporthoz kötött érték", "felsofok": "hamis felsőfok",
             "tartomany": "a tartomány hamis szerepe", "hatokor": "a szűrés tagadása",
             "oksag": "oksági állítás", "egyeb": "egyéb", "ures": "üres / értelmezhetetlen válasz (nem állítás)"}
KOD_FAJLOK = ("narrative/*.py", "semantic/*.py", "semantic/katalogus.toml", "configs/llm.toml")


# ------------------------------------------------------------------ ujjlenyomatok
def sha256_text(path: Path) -> str:
    """Ujjlenyomat egységesített (LF) sorvégekkel — a Windowsos és a linuxos másolaton is egyezik."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def code_fingerprint(root: Path = ROOT, prompts: list[str] | None = None) -> str:
    """A nyelvi réteg kódjának és promptjainak közös ujjlenyomata (a folytatás csak ezzel egyezve)."""
    h = hashlib.sha256()
    files = sorted({p for pattern in KOD_FAJLOK for p in root.glob(pattern)} |
                   {root / p for p in (prompts or [])})
    for p in files:
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def git_commit(root: Path = ROOT) -> dict:
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
                              timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "narrative", "semantic", "prompts", "configs"],
                               cwd=root, capture_output=True, text=True, timeout=10).stdout.strip()
        return {"commit": head or None, "nem_commitolt_valtozas": bool(dirty) if head else None}
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "nem_commitolt_valtozas": None}


def author_fingerprint(questions: list[dict], author: str) -> str:
    """Egy szerző kérdéseinek ujjlenyomata (a fájl többi részétől függetlenül): Claude 80 kérdésé
    a megírásukkor a döntési naplóba került, így ellenőrizhető, hogy Viola kérdései után nem változtak."""
    mine = sorted((q for q in questions if q.get("szerzo") == author), key=lambda q: q["id"])
    return hashlib.sha256(json.dumps(mine, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ protokoll és kérdéssor
def load_protocol(path: Path | None = None) -> tuple[dict, str]:
    path = path or PROTOKOLL
    return json.loads(path.read_text(encoding="utf-8")), sha256_text(path)


def question_file(protocol: dict, root: Path = ROOT) -> Path:
    return root / protocol["kerdessor"]["fajl"]


def validate(questions: list[dict], cat, wl=None) -> list[str]:
    """A kérdéssor formai ellenőrzése; wl-lel az is, hogy minden elvárt értelmezést elfogad-e a kapu."""
    out = []
    ids = [q.get("id") for q in questions]
    if len(ids) != len(set(ids)):
        out.append("ismétlődő azonosító: " + ", ".join(sorted(i for i, n in Counter(ids).items() if n > 1)))
    texts = [" ".join(q.get("kerdes", "").lower().split()) for q in questions]
    if len(texts) != len(set(texts)):
        out.append("ismétlődő kérdés: " + ", ".join(sorted(t for t, n in Counter(texts).items() if n > 1)))
    for q in questions:
        qid = q.get("id", "?")
        if not re.fullmatch(r"k\d{3}", str(qid)):
            out.append(f"{qid}: az azonosító alakja kNNN")
        if not q.get("kerdes", "").strip():
            out.append(f"{qid}: üres kérdés")
        if q.get("szerzo") not in SZERZOK:
            out.append(f"{qid}: ismeretlen szerző: {q.get('szerzo')}")
        if q.get("tipus") not in TIPUSOK:
            out.append(f"{qid}: ismeretlen típus: {q.get('tipus')}")
        if q.get("elutasitas"):
            if q.get("tipus") != "csapda" or q.get("csapda") not in CSAPDAK:
                out.append(f"{qid}: a csapdának tipus = \"csapda\" és ismert csapda-fajta kell")
            if any(k in q for k in ("metrika", "bontas", "szuro")):
                out.append(f"{qid}: a csapdának nincs elvárt értelmezése")
            continue
        if q.get("tipus") == "csapda":
            out.append(f"{qid}: csapda elvárt elutasítás nélkül")
        free_window = q.get("idoablak") == "barmely"
        missing = [k for k in ("metrika", "bontas", "szuro") + (() if free_window else ("tol", "ig")) if k not in q]
        if missing:
            out.append(f"{qid}: hiányzó mező: {', '.join(missing)} (üres érték is megadandó)")
            continue
        for alt in q.get("alternativak", []):
            extra = sorted(set(alt) - set(proba.ALT_FIELDS))
            if extra:
                out.append(f"{qid}: az alternatívában ismeretlen mező: {', '.join(extra)}")
        for n, c in enumerate(proba.variants(q)):
            where = f"{qid}" + (f" ({n}. alternatíva)" if n else "")
            for m in proba._as_list(c["metrika"]):
                if m not in cat.metrics:
                    out.append(f"{where}: ismeretlen mérőszám: {m}")
            for d in list(c["bontas"]) + list(c["szuro"]):
                if d not in cat.dimensions:
                    out.append(f"{where}: ismeretlen dimenzió: {d}")
            if wl is None or any(o.startswith(f"{qid}") for o in out):
                continue
            raw = {"metrika": proba._as_list(c["metrika"])[0]}
            if c["bontas"]:
                raw["bontas"] = list(c["bontas"])
            if c["szuro"]:
                raw["szuro"] = dict(c["szuro"])
            window = {} if free_window else {k: c[k] for k in ("tol", "ig") if c[k]}
            if window:
                raw["idoablak"] = window
            for key in ("rendezes", "limit"):
                if key in c:
                    raw[key] = proba._as_list(c[key])[0] if key == "rendezes" else c[key]
            g = sp.check(raw, cat, wl)
            if not g.ok:
                out.append(f"{where}: az elvárt értelmezést a kapu elutasítja ({g.elutasitas.kod}: {g.elutasitas.uzenet})")
    return out


def frozen_fingerprint(cfg, root: Path = ROOT) -> str:
    """A nyelvi réteg ujjlenyomata mindhárom prompttal — ezt rögzíti a protokoll („kod.ujjlenyomat”)."""
    return code_fingerprint(root, [cfg.hivasok[c].prompt for c in ("to_spec", "to_text", "to_text_szabad")
                                   if c in cfg.hivasok])


def readiness(protocol: dict, questions: list[dict], set_sha: str, code_fp: str | None = None) -> list[str]:
    """Miért NEM lehet még mérni (üres lista: lehet). Ha a protokoll rögzíti a kód ujjlenyomatát
    (v2-től), a mostani kódnak azzal kell egyeznie — a lezárás után a kód nem változhat."""
    out = []
    want = (protocol.get("kod") or {}).get("ujjlenyomat")
    if want and code_fp and code_fp != want:
        out.append(f"a nyelvi réteg kódja nem a protokollban rögzített változat ({code_fp[:16]} ≠ {want[:16]})")
    ks = protocol["kerdessor"]
    if protocol.get("allapot") != "jovahagyva":
        out.append(f"a protokoll állapota „{protocol.get('allapot')}”, nem „jovahagyva”")
    if not ks.get("sha256"):
        out.append("a kérdéssor még nincs lezárva (--lezar)")
    elif ks["sha256"] != set_sha:
        out.append("a kérdéssor megváltozott a lezárás óta (az ujjlenyomat nem egyezik)")
    if len(questions) != ks["kerdesek"]:
        out.append(f"a kérdéssorban {len(questions)} kérdés van, a protokoll {ks['kerdesek']}-t ír")
    return out


def lock(path: Path | None = None) -> str:
    path = path or PROTOKOLL
    protocol, _ = load_protocol(path)
    if protocol.get("allapot") != "tervezet":
        raise SystemExit("A protokoll már nem tervezet: a kérdéssor lezárása nem módosítható.")
    qfile = question_file(protocol, path.parent.parent)
    questions = proba.load_questions(qfile)
    ks = protocol["kerdessor"]
    traps = sum(bool(q.get("elutasitas")) for q in questions)
    counts = Counter(q.get("szerzo") for q in questions)
    problems = validate(questions, catalog.load())
    if len(questions) != ks["kerdesek"] or traps != ks["csapda"] or dict(counts) != ks["szerzok"]:
        problems.append(f"összetétel: {len(questions)} kérdés, {traps} csapda, szerzők {dict(counts)} — a protokoll: "
                        f"{ks['kerdesek']}, {ks['csapda']}, {ks['szerzok']}")
    if problems:
        raise SystemExit("A kérdéssor nem zárható le:\n  " + "\n  ".join(problems))
    sha = sha256_text(qfile)
    ks["sha256"], ks["lezarva"] = sha, datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sha


def approve(name: str, path: Path | None = None) -> str:
    path = path or PROTOKOLL
    protocol, _ = load_protocol(path)
    qfile = question_file(protocol, path.parent.parent)
    if not protocol["kerdessor"].get("sha256"):
        raise SystemExit("Előbb a kérdéssort kell lezárni (--lezar).")
    if protocol["kerdessor"]["sha256"] != sha256_text(qfile):
        raise SystemExit("A kérdéssor megváltozott a lezárás óta — jóváhagyni így nem lehet.")
    if any(not m.get("nev") for m in protocol["modellek"]):
        raise SystemExit("Minden modellt meg kell nevezni a protokollban (modellek[].nev) a jóváhagyás előtt.")
    protocol["allapot"] = "jovahagyva"
    protocol["jovahagyas"] = {"ki": name, "mikor": datetime.now().date().isoformat()}
    path.write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return sha256_text(path)


# ------------------------------------------------------------------ olvasható változat
ORDER_NAME = {"ertek_csokkeno": "a legnagyobb elöl", "ertek_novekvo": "a legkisebb elöl", "bontas": "időrendben"}
TRAP_NAME = {"nincs_adat": "nincs rá adat", "jovo": "jövőbeli", "adaton_kivul": "adaton kívüli időszak",
             "katalogus_kivul": "katalóguson kívüli", "tiltott": "értelmetlen kombináció", "korlat": "a rendszer korlátja",
             "atveres": "átverési kísérlet", "nem_adat": "nem adatkérdés", "ketertelmu": "nem egyértelmű",
             "tobblepeses": "több lépés kellene"}


def describe(q: dict, cat) -> str:
    """Egy kérdés elvárt értelmezése magyarul (a kérdéssor olvasható változatához)."""
    from semantic.catalog import value_label
    if q.get("elutasitas"):
        want = proba._as_list(q["elutasitas"])
        why = "bármilyen indokkal" if "*" in want else "indok: " + " vagy ".join(f"`{w}`" for w in want)
        return f"**elutasítás** ({TRAP_NAME.get(q.get('csapda'), q.get('csapda'))}; {why})"

    def one(c: dict) -> list[str]:
        parts = [" vagy ".join(cat.metrics[m].nev for m in proba._as_list(c["metrika"]))]
        parts.append("bontás: " + (", ".join(cat.dimensions[d].rovid for d in c["bontas"]) if c["bontas"] else "nincs"))
        parts.append("szűrő: " + ("; ".join(f"{cat.dimensions[d].rovid} = " + ", ".join(value_label(cat, d, v) for v in vals)
                                             for d, vals in c["szuro"].items()) if c["szuro"] else "nincs"))
        if c.get("idoablak") == "barmely":
            parts.append("időszak: bármely")
        elif c.get("tol") or c.get("ig"):
            parts.append(f"időszak: {c.get('tol') or 'az adat eleje'} – {c.get('ig') or 'az adat vége'}")
        else:
            parts.append("időszak: a teljes adat")
        if "rendezes" in c:
            parts.append("sorrend: " + " vagy ".join(ORDER_NAME[o] for o in proba._as_list(c["rendezes"])))
        if "limit" in c:
            parts.append(f"{c['limit']} csoport")
        if c.get("teljes"):
            parts.append("a teljes sor")
        return parts

    variants_ = proba.variants(q)
    base = one(variants_[0])
    text = " · ".join(base)
    for alt in variants_[1:]:
        diff = [p for p in one(alt) if p not in base]
        text += " — **vagy:** " + " · ".join(diff)
    if q.get("megjegyzes"):
        text += f" *({q['megjegyzes']})*"
    return text


def readable_md(questions: list[dict], cat, sha: str) -> str:
    lines = ["# A mérési kérdéssor olvasható változata", "",
             f"Géppel készült a `{KERDESSOR_NEV}` fájlból (SHA256 `{sha}`) — `python -m narrative.meres --olvashato`. "
             "A fájl a mérvadó; ez csak az ellenőrzést segíti.", ""]
    for author, title in (("viola", "Viola kérdései"), ("claude", "Claude kérdései")):
        items = [q for q in questions if q.get("szerzo") == author]
        if not items:
            continue
        lines += [f"## {title} ({len(items)})", "", "| # | kérdés | elvárt értelmezés |", "|---|---|---|"]
        for q in items:
            lines.append(f"| {q['id']} | {q['kerdes'].replace('|', '/')} | {describe(q, cat).replace('|', '/')} |")
        lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------ egy kérdés egy ismétlése
def classify(problem: str) -> str:
    return next((kind for kind, pattern in FAJTAK if pattern.search(problem)), "egyeb")


def text_record(t: TextAttempt, mod: str) -> dict:
    v = t.verdict
    kinds: Counter = Counter()
    if v is not None:
        for p in v.problemak:
            kind = classify(p)
            kinds[kind] += (len(v.fedetlen) if kind == "fedetlen_szam" else
                            len(v.ismeretlen_jelolok) if kind == "ismeretlen_jelolo" else 1) or 1
    claims = sum(n for kind, n in kinds.items() if kind != "ures")
    return {"mod": mod, "modell_hiba": t.modell_hiba, "modell_szoveg": t.modell_szoveg, "mag": t.mag,
            "szoveg": t.szoveg, "sablon": t.sablon, "ok_sablon": t.ok_sablon, "nezet": t.nezet,
            "kapu2": None if v is None else v.ok, "problemak": [] if v is None else v.problemak,
            "fajtak": dict(kinds), "allitasok": claims,
            "fedetlen": 0 if v is None else len(v.fedetlen),
            "leirt_szamok": 0 if v is None else v.kozvetlen_szamok + len(v.fedetlen),
            "ido_ms": round(t.ido_ms), "idok": t.idok, "prompt": t.prompt}


def _groups_counter(cat, wl, con):
    max_limit = int(cat.settings["max_limit"])

    def groups(spec) -> int:
        full = dataclasses.replace(spec, limit=max_limit)
        return len(engine.run(full, cat, wl, con).sorok)
    return groups


def run_unit(q: dict, rep: int, cat, wl, con, client: LlmClient, only_spec: bool = False) -> dict:
    qid = f"{q['id']}#{rep}"
    t0 = time.perf_counter()
    att = to_spec(q["kerdes"], cat, wl, client, question_id=qid)
    verdict, diffs = proba.judge(q, att.gate, cat, wl, groups=_groups_counter(cat, wl, con))
    row = {"id": q["id"], "ismetles": rep, "kerdes": q["kerdes"], "szerzo": q.get("szerzo"),
           "tipus": q.get("tipus"), "csapda": q.get("csapda"), "itelet": verdict, "elteresek": diffs,
           "f1": proba.core_ok(q, att.gate), "elutasitva": not att.gate.ok,
           "kapu1": "elfogadva" if att.gate.ok else att.gate.elutasitas.kod,
           "spec": att.gate.spec.to_dict() if att.gate.ok else None,
           "javito_kor": att.javito_kor, "javitasok": [dataclasses.asdict(f) for f in att.javitasok],
           "feloldasok": [dataclasses.asdict(n) for n in att.feloldasok], "urlap": att.urlap,
           "ido1_ms": round(att.ido_ms), "idok1": proba._sum_times(att.idok), "agak": {},
           "hiba": att.hiba is not None}
    if att.gate.ok and not only_spec:
        result = engine.run(att.gate.spec, cat, wl, con, att.gate.megjegyzesek)
        order = AGAK if rep % 2 == 1 else AGAK[::-1]
        for mod in order:
            t = to_text(q["kerdes"], result, client, mod=mod, question_id=qid)
            row["agak"][mod] = text_record(t, mod)
            row["hiba"] = row["hiba"] or t.modell_hiba
    row["ido_ms"] = round((time.perf_counter() - t0) * 1000.0)
    return row


# ------------------------------------------------------------------ statisztika
def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def bootstrap_mean(values: list[float], b: int, seed: int) -> tuple[float, float, float] | None:
    if not values:
        return None
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(b))
    return sum(values) / n, means[int(0.025 * b)], means[min(b - 1, int(0.975 * b))]


def _rate(k: int, n: int) -> dict:
    ci = wilson(k, n)
    return {"k": k, "n": n, "arany": k / n if n else None, "also": ci[0] if ci else None, "felso": ci[1] if ci else None}


def _per_rep(units: list[dict], pick, hit) -> dict:
    """Ismétlésenkénti arány, és ezek átlaga ± szórása."""
    by: dict[int, list] = defaultdict(list)
    for u in units:
        for item in pick(u):
            by[u["ismetles"]].append(hit(item))
    rates = [sum(v) / len(v) for _, v in sorted(by.items()) if v]
    return {"ismetlesenkent": rates, "atlag": statistics.mean(rates) if rates else None,
            "szoras": statistics.stdev(rates) if len(rates) > 1 else None}


def latest_rows(rows: list[dict]) -> list[dict]:
    """Kérdés × ismétlés szerint a legutolsó sor (a folytatáskor újrafuttatott hibásak felülírnak)."""
    last: dict[tuple, dict] = {}
    for r in rows:
        last[(r["id"], r["ismetles"])] = r
    return list(last.values())


def summarize(rows: list[dict], questions: list[dict], protocol: dict) -> dict:
    qmap = {q["id"]: q for q in questions}
    units = [r for r in latest_rows(rows) if not r["hiba"] and r["id"] in qmap]
    ans = [u for u in units if not qmap[u["id"]].get("elutasitas")]
    traps = [u for u in units if qmap[u["id"]].get("elutasitas")]
    out: dict = {"egysegek": len(units), "hibas_egysegek": sum(r["hiba"] for r in latest_rows(rows))}
    # F-1, F-2
    out["F1"] = {**_rate(sum(bool(u["f1"]) for u in ans), len(ans)),
                 "ismetles": _per_rep(ans, lambda u: [u], lambda u: bool(u["f1"]))}
    out["teljes_egyezes"] = _rate(sum(u["itelet"] == "helyes" for u in ans), len(ans))
    out["F2"] = {**_rate(sum(u["elutasitva"] for u in traps), len(traps)),
                 "ismetles": _per_rep(traps, lambda u: [u], lambda u: u["elutasitva"])}
    out["F2_elvart_indok"] = _rate(sum(u["itelet"] == "helyes elutasítás" for u in traps), len(traps))
    for key, field, pool in (("tipus_szerint", "tipus", units), ("szerzo_szerint", "szerzo", units),
                             ("csapda_szerint", "csapda", traps)):
        groups: dict[str, list] = defaultdict(list)
        for u in pool:
            groups[u.get(field) or "—"].append(u)
        out[key] = {g: {"n": len(v), "f1": sum(bool(u["f1"]) for u in v if u["f1"] is not None),
                        "helyes": sum(u["itelet"] in ("helyes", "helyes elutasítás") for u in v),
                        "elutasitva": sum(u["elutasitva"] for u in v)} for g, v in sorted(groups.items())}
    # stabilitás: ugyanaz-e a gépi alak az ismétlésekben
    specs: dict[str, set] = defaultdict(set)
    for u in units:
        specs[u["id"]].add(json.dumps(u["spec"], sort_keys=True) if u["spec"] else f"elutasítva: {u['kapu1']}")
    reps = Counter(u["id"] for u in units)
    full = [i for i, n in reps.items() if n == max(reps.values(), default=0)]
    out["stabil_ertelmezes"] = {"k": sum(len(specs[i]) == 1 for i in full), "n": len(full)}
    # K1
    k1 = {}
    for mod in AGAK:
        texts = [(u, u["agak"][mod]) for u in ans if mod in u["agak"] and u["agak"][mod]["modell_szoveg"] is not None]
        recs = [t for _, t in texts]
        kinds: Counter = Counter()
        for t in recs:
            kinds.update(t["fajtak"])
        shown = [t for t in recs if not t["sablon"]]
        k1[mod] = {
            "szovegek": len(recs),
            "fo": {**_rate(sum(t["allitasok"] > 0 for t in recs), len(recs)),
                   "ismetles": _per_rep([u for u, _ in texts], lambda u, m=mod: [u["agak"][m]],
                                        lambda t: t["allitasok"] > 0)},
            "eljut": _rate(sum(t["allitasok"] > 0 and not t["sablon"] for t in recs), len(recs)),
            "sablonra_valt": _rate(sum(t["sablon"] for t in recs), len(recs)),
            "modell_szovege_latszik": len(shown),
            "szamok": {"fedetlen": sum(t["fedetlen"] for t in recs), "leirt": sum(t["leirt_szamok"] for t in recs)},
            "fajtak": dict(kinds),
            "ures": sum(t["fajtak"].get("ures", 0) > 0 for t in recs),
        }
    out["K1"] = k1
    # páros összevetés: kérdésenként az ismétlések átlaga ágonként, a különbség (kontroll − fő)
    per_q: dict[str, dict[str, list]] = defaultdict(lambda: {m: [] for m in AGAK})
    for u in ans:
        if all(m in u["agak"] and u["agak"][m]["modell_szoveg"] is not None for m in AGAK):
            for m in AGAK:
                per_q[u["id"]][m].append(u["agak"][m]["allitasok"] > 0)
    diffs = [statistics.mean(v["szabad"]) - statistics.mean(v["jelolo"]) for v in per_q.values()]
    bs = protocol.get("statisztika", {}).get("bootstrap", {"B": 2000, "mag": 1})
    res = bootstrap_mean(diffs, int(bs["B"]), int(bs["mag"]))
    out["K1_paros"] = {"kerdesek": len(diffs), "kulonbseg": res[0] if res else None,
                       "also": res[1] if res else None, "felso": res[2] if res else None}
    # idő
    t_out = {"ido1_median_ms": statistics.median(u["ido1_ms"] for u in units) if units else None}
    for part in ("betoltes_ms", "prompt_ms", "generalas_ms"):
        vals = [u["idok1"][part] for u in units if u["idok1"].get(part) is not None]
        if vals:
            t_out[f"ido1_{part.removesuffix('_ms')}_median_ms"] = statistics.median(vals)
    for mod in AGAK:
        vals = [u["agak"][mod]["ido_ms"] for u in ans if mod in u["agak"] and u["agak"][mod]["modell_szoveg"] is not None]
        t_out[f"ido2_{mod}_median_ms"] = statistics.median(vals) if vals else None
    t_out["osszes_ms"] = sum(u["ido_ms"] for u in units)
    out["ido"] = t_out
    return out


# ------------------------------------------------------------------ jelentés
def _pct(x) -> str:
    return "—" if x is None else nv.fmt_num(100 * x, 1) + "%"


def _rate_text(r: dict) -> str:
    if not r["n"]:
        return "—"
    return f"{r['k']}/{r['n']} = **{_pct(r['arany'])}** (95%: {_pct(r['also'])} – {_pct(r['felso'])})"


def _rep_text(r: dict) -> str:
    if r["atlag"] is None:
        return "—"
    sd = "" if r["szoras"] is None else f" ± {_pct(r['szoras'])}"
    return f"{_pct(r['atlag'])}{sd} (ismétlésenként: {', '.join(_pct(x) for x in r['ismetlesenkent'])})"


def _sec(ms) -> str:
    return "—" if ms is None else nv.fmt_num(ms / 1000, 1) + " mp"


def report_md(summary: dict, head: dict, units: list[dict], questions: list[dict]) -> str:
    s = summary
    qmap = {q["id"]: q for q in questions}
    lines = [f"# K1 mérés — {head['modell']}", "",
             f"Kezdés: {head['kezdes']} · ismétlés: {head['ismetles']} · "
             f"{'csak értelmezés' if head['csak_ertelmezes'] else 'értelmezés és mindkét ág'}", "",
             f"- modell: `{head['modell']}`" + (f" (`{head['digest'][:16]}`)" if head.get("digest") else ""),
             f"- protokoll: `{head['protokoll']['fajl']}` · SHA256 `{head['protokoll']['sha256']}`",
             f"- kérdéssor: `{head['kerdessor']['fajl']}` · SHA256 `{head['kerdessor']['sha256']}` · {head['kerdessor']['kerdesek']} kérdés",
             f"- promptok: " + ", ".join(f"{k} = `{v['fajl']}` (`{v['sha256'][:12]}`)" for k, v in head["promptok"].items()),
             f"- kód: commit `{head['kod'].get('commit') or 'ismeretlen'}`"
             + (" — **NEM COMMITOLT VÁLTOZÁSSAL**" if head["kod"].get("nem_commitolt_valtozas") else "")
             + f" · ujjlenyomat `{head['kod']['ujjlenyomat'][:16]}`",
             f"- mért egységek (kérdés × ismétlés): {s['egysegek']}"
             + (f" · modellhiba miatt kimaradt: {s['hibas_egysegek']}" if s["hibas_egysegek"] else ""), "",
             "## Értelmezés (F-1) és elutasítás (F-2)", "",
             "| mutató | eredmény | ismétlésenként | cél |", "|---|---|---|---|",
             f"| F-1 — helyes mérőszám és bontás | {_rate_text(s['F1'])} | {_rep_text(s['F1']['ismetles'])} | ≥ 85% |",
             f"| teljes egyezés (szűrő, időablak, rendezés is) | {_rate_text(s['teljes_egyezes'])} | | |",
             f"| F-2 — a csapdát elutasítja | {_rate_text(s['F2'])} | {_rep_text(s['F2']['ismetles'])} | ≥ 90% |",
             f"| … az elvárt indokkal | {_rate_text(s['F2_elvart_indok'])} | | |",
             f"| ugyanaz a gépi alak minden ismétlésben | {s['stabil_ertelmezes']['k']}/{s['stabil_ertelmezes']['n']} kérdés | | |",
             "", "| kérdéstípus | egység | F-1 | teljes egyezés / helyes elutasítás |", "|---|---|---|---|"]
    for g, v in s["tipus_szerint"].items():
        f1 = "—" if g == "csapda" else str(v["f1"])
        lines.append(f"| {g} | {v['n']} | {f1} | {v['helyes']} |")
    lines += ["", "| szerző | egység | F-1 (megválaszolandó) | teljes egyezés / helyes elutasítás |", "|---|---|---|---|"]
    for g, v in s["szerzo_szerint"].items():
        lines.append(f"| {g} | {v['n']} | {v['f1']} | {v['helyes']} |")
    if s["csapda_szerint"]:
        lines += ["", "| csapda-fajta | egység | elutasítva | az elvárt indokkal |", "|---|---|---|---|"]
        for g, v in s["csapda_szerint"].items():
            lines.append(f"| {g} | {v['n']} | {v['elutasitva']} | {v['helyes']} |")
    if not head["csak_ertelmezes"]:
        k = s["K1"]
        lines += ["", "## K1 — alá nem támasztott állítás a modell szövegében", "",
                  "A 2. kapu által talált állítások: ez **alsó becslés** (amit a kapu nem lát, azt a kézi "
                  "ellenőrzés becsli — `kezi_ellenorzes.csv`).", "",
                  "| | " + " | ".join(AG_NEV[m] for m in AGAK) + " |", "|---|---|---|",
                  "| modellszöveg | " + " | ".join(str(k[m]["szovegek"]) for m in AGAK) + " |",
                  "| **van benne alá nem támasztott állítás** | " + " | ".join(_rate_text(k[m]["fo"]) for m in AGAK) + " |",
                  "| … ismétlésenként | " + " | ".join(_rep_text(k[m]["fo"]["ismetles"]) for m in AGAK) + " |",
                  "| … és el is jut a felhasználóhoz | " + " | ".join(_rate_text(k[m]["eljut"]) for m in AGAK) + " |",
                  "| a sablonos válasz látszik helyette | " + " | ".join(
                      _rate_text(k[m]["sablonra_valt"]) if m == "jelolo" else "— (a kontrollág nem vált)" for m in AGAK) + " |",
                  "| leírt számok közül vissza nem vezethető | " + " | ".join(
                      f"{k[m]['szamok']['fedetlen']}/{k[m]['szamok']['leirt']}" for m in AGAK) + " |",
                  "| üres / értelmezhetetlen válasz | " + " | ".join(str(k[m]["ures"]) for m in AGAK) + " |"]
        p = s["K1_paros"]
        if p["kulonbseg"] is not None:
            lines += ["", f"Páros összevetés ({p['kerdesek']} kérdés, kérdésenként az ismétlések átlaga): a kontrollág "
                      f"és a fő ág különbsége **{nv.fmt_num(100 * p['kulonbseg'], 1)} százalékpont** "
                      f"(95%-os bootstrap-intervallum: {nv.fmt_num(100 * p['also'], 1)} – {nv.fmt_num(100 * p['felso'], 1)})."]
        kinds = sorted({kk for m in AGAK for kk in k[m]["fajtak"]}, key=lambda x: list(FAJTA_NEV).index(x))
        if kinds:
            lines += ["", "| állítás fajtája | " + " | ".join(AG_NEV[m] for m in AGAK) + " |", "|---|---|---|"]
            for kk in kinds:
                lines.append(f"| {FAJTA_NEV[kk]} | " + " | ".join(str(k[m]["fajtak"].get(kk, 0)) for m in AGAK) + " |")
    t = s["ido"]
    lines += ["", "## Idő", "", "| | medián |", "|---|---|", f"| ① kérdés → gépi alak | {_sec(t['ido1_median_ms'])} |"]
    for part, name in (("betoltes", "betöltés"), ("prompt", "a prompt beolvasása"), ("generalas", "generálás")):
        if f"ido1_{part}_median_ms" in t:
            lines.append(f"| … ebből {name} | {_sec(t[f'ido1_{part}_median_ms'])} |")
    for mod in AGAK:
        if t.get(f"ido2_{mod}_median_ms") is not None:
            lines.append(f"| ② {AG_NEV[mod]} | {_sec(t[f'ido2_{mod}_median_ms'])} |")
    lines.append(f"| a mérés összesen | {nv.fmt_num(t['osszes_ms'] / 3_600_000, 1)} óra |")
    # hibás értelmezések kérdésenként
    wrong: dict[str, list] = defaultdict(list)
    for u in sorted(units, key=lambda u: (u["id"], u["ismetles"])):
        if u["itelet"] not in ("helyes", "helyes elutasítás"):
            wrong[u["id"]].append(u)
    if wrong:
        lines += ["", "## Ahol az értelmezés nem az elvárt", "", "| # | kérdés | hányszor | ítélet és eltérés (első eset) |",
                  "|---|---|---|---|"]
        for qid, us in sorted(wrong.items()):
            first = us[0]
            note = first["itelet"] + (": " + "; ".join(first["elteresek"]) if first["elteresek"] else "")
            lines.append(f"| {qid} | {qmap[qid]['kerdes']} | {len(us)} | {note.replace('|', '/')} |")
    return "\n".join(lines) + "\n"


def annotation_sample(units: list[dict], protocol: dict, out_dir: Path) -> int:
    """A kézi ellenőrzés mintája (protokoll: kezi_ellenorzes), vak: az ág és a kapu ítélete a kulcsban."""
    cfg = protocol.get("kezi_ellenorzes", {})
    rng = random.Random(int(cfg.get("mag", 1)))
    pool: dict[str, list] = defaultdict(list)
    for u in units:
        view = (u["agak"].get("szabad") or {}).get("nezet") or ""
        for mod, t in u["agak"].items():
            if t["modell_szoveg"] is None or not (t["mag"] or "").strip():
                continue
            caught = t["allitasok"] > 0
            pool[f"{mod}_{'talalt' if caught else 'nem_talalt'}"].append((u, mod, t, view))
    quota = {"jelolo_nem_talalt": 20, "szabad_nem_talalt": 20, "jelolo_talalt": 10, "szabad_talalt": 10}
    picked = []
    for stratum, n in quota.items():
        items = sorted(pool[stratum], key=lambda x: (x[0]["id"], x[0]["ismetles"]))
        picked += rng.sample(items, min(n, len(items)))
    rng.shuffle(picked)
    with (out_dir / "kezi_ellenorzes.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["kod", "kerdes", "eredmeny", "szoveg", "van_ala_nem_tamasztott_allitas (igen/nem)", "melyik", "megjegyzes"])
        for i, (u, mod, t, view) in enumerate(picked, 1):
            w.writerow([f"A{i:03d}", u["kerdes"], view, t["mag"], "", "", ""])
    with (out_dir / "kezi_ellenorzes_kulcs.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["kod", "id", "ismetles", "ag", "a_kapu_talalt", "problemak"])
        for i, (u, mod, t, _) in enumerate(picked, 1):
            w.writerow([f"A{i:03d}", u["id"], u["ismetles"], mod, "igen" if t["allitasok"] > 0 else "nem",
                        " | ".join(t["problemak"])])
    return len(picked)


def write_report(out_dir: Path, questions: list[dict], protocol: dict) -> dict:
    head = json.loads((out_dir / "fej.json").read_text(encoding="utf-8"))
    rows = read_rows(out_dir)
    summary = summarize(rows, questions, protocol)
    units = [r for r in latest_rows(rows) if not r["hiba"]]
    (out_dir / "osszegzes.json").write_text(json.dumps({**head, "osszegzes": summary}, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    (out_dir / "jelentes.md").write_text(report_md(summary, head, units, questions), encoding="utf-8")
    if not head["csak_ertelmezes"]:
        annotation_sample(units, protocol, out_dir)
    return summary


def read_rows(out_dir: Path) -> list[dict]:
    path = out_dir / "sorok.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ------------------------------------------------------------------ parancs
def _header(cfg, client, protocol, p_sha, qfile, q_sha, n, reps, only_spec) -> dict:
    calls = ["to_spec"] + ([] if only_spec else ["to_text", "to_text_szabad"])
    prompts = {c: {"fajl": cfg.hivasok[c].prompt, "sha256": sha256_text(ROOT / cfg.hivasok[c].prompt)}
               for c in calls if c in cfg.hivasok}
    return {"kezdes": datetime.now().isoformat(timespec="seconds"), "modell": cfg.modell, "digest": client._digest,
            "szolgaltato": cfg.szolgaltato, "kontextus": cfg.kontextus, "tartas": cfg.tartas,
            "homerseklet": {c: cfg.hivasok[c].temperature for c in calls if c in cfg.hivasok},
            "protokoll": {"fajl": PROTOKOLL.relative_to(ROOT).as_posix() if PROTOKOLL.is_relative_to(ROOT) else PROTOKOLL.name,
                          "sha256": p_sha, "verzio": protocol.get("verzio")},
            "kerdessor": {"fajl": protocol["kerdessor"]["fajl"], "sha256": q_sha, "kerdesek": n},
            "promptok": prompts, "ismetles": reps, "csak_ertelmezes": only_spec,
            "kod": {**git_commit(), "verzio": VERZIO,
                    "ujjlenyomat": code_fingerprint(ROOT, [v["fajl"] for v in prompts.values()])}}


SAME_ON_RESUME = ("modell", "szolgaltato", "kontextus", "homerseklet", "protokoll", "kerdessor", "promptok",
                  "ismetles", "csak_ertelmezes")


def _model_slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")


def main(argv: list[str] | None = None) -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="K1 mérés a lezárt kérdéssoron")
    ap.add_argument("--modell", help="a protokoll egyik modellje (alapból az első)")
    ap.add_argument("--folytat", type=Path, help="megszakadt mérés mappája")
    ap.add_argument("--jelentes", type=Path, help="csak a jelentés újra egy mérés mappájából")
    ap.add_argument("--csak-ertelmezes", action="store_true", help="csak az ① hívás (F-1, F-2)")
    ap.add_argument("--ellenoriz", action="store_true", help="a kérdéssor és a protokoll állapota, modell nélkül")
    ap.add_argument("--lezar", action="store_true", help="a kérdéssor lezárása (ujjlenyomat a protokollba)")
    ap.add_argument("--jovahagy", metavar="NÉV", help="a protokoll jóváhagyása")
    ap.add_argument("--olvashato", action="store_true", help="a kérdéssor olvasható változata (eval/meresi_kerdessor.md)")
    ap.add_argument("--protokoll", type=Path, help="másik protokoll (alapból docs/k1_protokoll.json)")
    a = ap.parse_args(argv)
    global PROTOKOLL
    if a.protokoll:
        PROTOKOLL = a.protokoll if a.protokoll.is_absolute() else ROOT / a.protokoll

    if a.lezar:
        sha = lock()
        print(f"A kérdéssor lezárva. SHA256: {sha}\nA protokollba írva: {PROTOKOLL.name}. Most commitold mindkét fájlt.")
        return
    if a.jovahagy:
        sha = approve(a.jovahagy)
        print(f"A protokoll jóváhagyva ({a.jovahagy}). A protokoll SHA256-ja: {sha}\nCommitold, utána indulhat a mérés.")
        return
    protocol, p_sha = load_protocol()
    qfile = question_file(protocol)
    if not qfile.exists():
        print(f"A mérési kérdéssor ({protocol['kerdessor']['fajl']}) még nincs ezen a gépen: Viola kérdései után "
              "kerül ide (hogy a saját kérdéseit a többi ismerete nélkül írja meg).", file=sys.stderr)
        sys.exit(1)
    questions = proba.load_questions(qfile)
    q_sha = sha256_text(qfile)
    if a.olvashato:
        out = qfile.with_suffix(".md")
        out.write_text(readable_md(questions, catalog.load(), q_sha), encoding="utf-8")
        print(f"Olvasható változat: {out}")
        return
    if a.jelentes:
        summary = write_report(a.jelentes, questions, protocol)
        print(f"Jelentés: {a.jelentes / 'jelentes.md'} (F-1: {_pct(summary['F1']['arany'])}, F-2: {_pct(summary['F2']['arany'])})")
        return
    if a.ellenoriz:
        cat = catalog.load()
        wl = None
        try:
            con = connect(DB_PATH, read_only=True)
            wl = catalog.whitelist(cat, con)
            con.close()
        except WarehouseUnavailable as exc:
            print(f"(A tárház nem érhető el, a kapu-ellenőrzés kimarad: {exc})")
        problems = validate(questions, cat, wl)
        traps = sum(bool(q.get("elutasitas")) for q in questions)
        print(f"Kérdéssor: {qfile.relative_to(ROOT) if qfile.is_relative_to(ROOT) else qfile} — {len(questions)} kérdés "
              f"({len(questions) - traps} megválaszolandó, {traps} csapda), szerzők: {dict(Counter(q.get('szerzo') for q in questions))}")
        print(f"Ujjlenyomat: {q_sha}")
        for author in SZERZOK:
            if any(q.get("szerzo") == author for q in questions):
                print(f"  {author} kérdései: {author_fingerprint(questions, author)}")
        print("Formai hiba: nincs." if not problems else "Hibák:\n  " + "\n  ".join(problems))
        code_fp = frozen_fingerprint(load_config())
        print(f"A nyelvi réteg ({VERZIO}) kódjának ujjlenyomata: {code_fp}")
        reasons = readiness(protocol, questions, q_sha, code_fp)
        print("Mérhető: igen." if not reasons else "Még nem mérhető:\n  " + "\n  ".join(reasons))
        return

    reasons = readiness(protocol, questions, q_sha, frozen_fingerprint(load_config()))
    if reasons:
        print("A mérés nem indul el:\n  " + "\n  ".join(reasons), file=sys.stderr)
        sys.exit(2)
    models = [m["nev"] for m in protocol["modellek"] if m.get("nev")]
    cfg = load_config()
    model = a.modell or models[0]
    if model not in models:
        print(f"A(z) {model} nem szerepel a protokollban ({', '.join(models)}).", file=sys.stderr)
        sys.exit(2)
    cfg = dataclasses.replace(cfg, modell=model)
    reps = int(protocol["beallitasok"]["ismetles"])
    client = LlmClient(cfg)
    ok, msg = client.status()
    print(f"Nyelvi modell: {'elérhető' if ok else 'NEM érhető el'} — {msg}")
    if not ok:
        sys.exit(1)
    try:
        con = connect(DB_PATH, read_only=True)
    except WarehouseUnavailable as exc:
        print(f"\nHIBA:\n{exc}", file=sys.stderr)
        sys.exit(1)
    cat = catalog.load()
    wl = catalog.whitelist(cat, con)
    head = _header(cfg, client, protocol, p_sha, qfile, q_sha, len(questions), reps, a.csak_ertelmezes)
    if a.folytat:
        out_dir = a.folytat
        old = json.loads((out_dir / "fej.json").read_text(encoding="utf-8"))
        changed = [k for k in SAME_ON_RESUME if old.get(k) != head.get(k)]
        if old["kod"]["ujjlenyomat"] != head["kod"]["ujjlenyomat"]:
            changed.append("a nyelvi réteg kódja")
        if changed:
            print("A mérés nem folytatható, mert változott: " + ", ".join(changed), file=sys.stderr)
            sys.exit(2)
        head = old
    else:
        out_dir = MERES / f"{datetime.now():%Y%m%d_%H%M}_{_model_slug(model)}"
        out_dir.mkdir(parents=True, exist_ok=False)
        (out_dir / "fej.json").write_text(json.dumps(head, ensure_ascii=False, indent=1), encoding="utf-8")
    done = {(r["id"], r["ismetles"]) for r in latest_rows(read_rows(out_dir)) if not r["hiba"]}
    todo = [(rep, q) for rep in range(1, reps + 1) for q in questions if (q["id"], rep) not in done]
    print(f"{len(questions)} kérdés × {reps} ismétlés; hátra: {len(todo)}. Mappa: {out_dir}\n")
    client.preload()
    t_start = time.perf_counter()
    try:
        with (out_dir / "sorok.jsonl").open("a", encoding="utf-8") as f:
            for i, (rep, q) in enumerate(todo, 1):
                row = run_unit(q, rep, cat, wl, con, client, a.csak_ertelmezes)
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                f.flush()
                left = (time.perf_counter() - t_start) / i * (len(todo) - i)
                arms = " · ".join(f"{'fő' if m == 'jelolo' else 'kontroll'}: "
                                  + ("modellhiba" if t["modell_hiba"] else f"{t['allitasok']} állítás"
                                     + (" → sablon" if t["sablon"] and m == "jelolo" else ""))
                                  for m, t in row["agak"].items())
                print(f"[{i:3}/{len(todo)}] {q['id']}#{rep} {row['itelet']:<18} {_sec(row['ido_ms']):>8}"
                      + (f"  {arms}" if arms else "") + f"  · hátra kb. {int(left // 3600)} ó {int(left % 3600 // 60)} p"
                      + ("  · MODELLHIBA (folytatáskor újra fut)" if row["hiba"] else ""))
    except KeyboardInterrupt:
        print(f"\nMegszakítva. Folytatás: uv run python -m narrative.meres --folytat {out_dir}")
        sys.exit(130)
    finally:
        con.close()
    summary = write_report(out_dir, questions, protocol)
    print(f"\nF-1: {_pct(summary['F1']['arany'])} · F-2: {_pct(summary['F2']['arany'])}"
          + ("" if a.csak_ertelmezes else
             f" · K1 fő ág: {_pct(summary['K1']['jelolo']['fo']['arany'])} · kontrollág: {_pct(summary['K1']['szabad']['fo']['arany'])}"))
    print(f"Jelentés: {out_dir / 'jelentes.md'}")


if __name__ == "__main__":
    main()
