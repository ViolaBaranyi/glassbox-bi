"""
A K1 géphatás (docs/k1_protokoll_gepvaltas.json): mindhárom mérés konfigurációi több gépen, gépenként
háromszor, ugyanazzal a rögzített seeddel — ugyanaz a modellfájl, kód, kérdéssor és futási protokoll.

    uv run python tools/k1_gepvaltas.py                       # → docs/k1_gepvaltas_eredmeny.md és .json
    uv run python tools/k1_gepvaltas.py --kimenet MAS.md      # más helyre (összevetéshez)

Futások: a korábbiakat (a dolgozatban közölteket) a protokoll név szerint rögzíti (logs/meres/<mappa>); az
újak gépenként a logs/meres/<gép>/ mappában vannak, mellettük a futtató gep.json-ja. Egy gépen egy
konfigurációból pontosan `ismetles_futas.szam` teljes új futás kell; a sorszámuk az indításuk sorrendje.
Ha több teljes futás illik egy helyre, nem választ: hibát jelez.

Három összevetés, mind a rögzített két-futásos eszközzel (tools/k1_futas_osszevetes.py):
  1. ismételhetőség — ugyanaz a gép, ugyanaz a seed, egymás utáni futások (#1–#2, #1–#3, #2–#3);
  2. a korábbi (közölt) futás megismétlése ugyanazon a gépen (korábbi – #i);
  3. gépek között — ugyanaz a sorszám a két gépen (#i – #i, korábbi – korábbi), és ahol az egyik gépnek
     csak korábbi futása van, az a másik gép minden új futásával.
A dolgozat mérésenkénti következtetései minden „készleten” külön (gép × korábbi / #1 / #2 / #3); egy
következtetés géptől és ismétléstől független, ha minden készleten ugyanaz az ítélete.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.db import DB_PATH, connect, use_utf8_console  # noqa: E402
from narrative import meres, proba  # noqa: E402
from semantic import catalog  # noqa: E402


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fo = _load("k1_futas_osszevetes")
v2 = fo.v2

PROTOKOLL = ROOT / "docs" / "k1_protokoll_gepvaltas.json"
GEPEK_DIR = ROOT / "docs" / "gepvaltas_gepek"
MERES = ROOT / "logs" / "meres"
KIMENET = ROOT / "docs" / "k1_gepvaltas_eredmeny.md"
OSZTALY = {"videokartya": "videókártya", "processzor": "processzor"}
K = "k"                                             # a korábbi (közölt) futás készlete


# ------------------------------------------------------------------ gépek
def machines(protocol: dict, gepek_dir: Path = GEPEK_DIR, extra: tuple[str, ...] = ()) -> dict[str, dict]:
    """A gépek sorrendben: előbb a protokoll gépei, utána a felvettek (név szerint) — a kihagyottak
    (protokoll: „kimarad”) nélkül. Mindegyiknél az osztály (videókártya / processzor), és ha már felvették,
    a nyilvántartás."""
    skip = set(protocol.get("kimarad") or {})
    out: dict[str, dict] = {}
    for gid, d in protocol["gepek"].items():
        out[gid] = {"osztaly": d.get("osztaly"), "leiras": d.get("leiras", ""), "nyilvantartas": None}
    for f in sorted(gepek_dir.glob("*.json")) if gepek_dir.is_dir() else []:
        if f.stem in skip:
            continue
        reg = json.loads(f.read_text(encoding="utf-8"))
        g = out.setdefault(f.stem, {"osztaly": None, "leiras": "", "nyilvantartas": None})
        g["nyilvantartas"] = reg
        if not g["osztaly"]:
            g["osztaly"] = reg.get("osztaly")
    for gid in extra:               # a futtató gépe, ha még nincs felvéve (az állapothoz)
        if gid not in skip:
            out.setdefault(gid, {"osztaly": None, "leiras": "", "nyilvantartas": None})
    return out


# ------------------------------------------------------------------ futások és helyek
def scan(meres_dir: Path, kuszob_ms: int) -> list[dict]:
    out = []
    for fej in sorted(meres_dir.glob("*/fej.json")) if meres_dir.is_dir() else []:
        run = fej.parent
        head = json.loads(fej.read_text(encoding="utf-8"))
        rows = meres.latest_rows(meres.read_rows(run)) if (run / "sorok.jsonl").exists() else []
        good = [r for r in rows if not r["hiba"]]
        need = int(head["kerdessor"]["kerdesek"]) * int(head.get("ismetles", 1))
        t1 = [r["ido1_ms"] for r in rows if r.get("ido1_ms")]
        med = statistics.median(t1) if t1 else None
        gj = run / "gep.json"
        out.append({"path": run, "head": head, "kesz": len(good), "kell": need,
                    "teljes": len(good) == need and not head.get("csak_ertelmezes"),
                    "ido1_median_ms": med,
                    "osztaly_ido_szerint": None if med is None else ("videokartya" if med < kuszob_ms else "processzor"),
                    "gep_json": json.loads(gj.read_text(encoding="utf-8")) if gj.exists() else None})
    return out


def fits(c: dict, par: dict) -> bool:
    h = c["head"]
    return (h.get("modell") == par["modell"] and (h.get("kod") or {}).get("ujjlenyomat") == par["kod"]["ujjlenyomat"]
            and h["kerdessor"]["sha256"] == par["kerdessor"]["sha256"]
            and (h.get("protokoll") or {}).get("sha256") == par["futas_protokoll"]["sha256"]
            and int(h.get("ismetles", 1)) == int(par["ismetles"]))


def started(c: dict) -> tuple[str, str]:
    """Az új futások sorszámának alapja: az első indítás ideje (gep.json), utána a mappa neve."""
    ind = (c["gep_json"] or {}).get("inditasok") or []
    return (ind[0].get("kezdes") if ind else None) or c["head"].get("kezdes") or "", c["path"].name


def _gep_json_problems(c: dict, par: dict, gep: str, gepinfo: dict) -> list[str]:
    gj = c["gep_json"]
    if gj is None:
        return ["nincs mellette gep.json"]
    out = []
    if gj.get("gep") != gep:
        out.append(f"a gep.json szerint a(z) {gj.get('gep')} gépé")
    if gj.get("par") != par["id"]:
        out.append(f"a gep.json szerint a(z) {gj.get('par')} pár futása")
    reg = gepinfo.get("nyilvantartas") or {}
    if reg.get("gepnev") and any(i.get("gepnev") != reg["gepnev"] for i in gj.get("inditasok", [])):
        out.append("nem mindegyik indítása ezen a gépen volt (a gépnév más)")
    return out


def resolve_korabbi(par: dict, gep: str, flat: list[dict], gepinfo: dict) -> dict | None:
    """A gép korábbi (közölt) futása ebből a konfigurációból, ha a protokoll név szerint rögzít egyet."""
    named = (par.get("korabbi") or {}).get(gep)
    if not named:
        return None
    c = next((r for r in flat if r["path"].name == named), None)
    if c is None:
        return {"allapot": "hiányzik", "futas": None, "megjegyzes": f"a rögzített mappa ({named}) még nincs a logs/meres alatt"}
    problems = []
    if not fits(c, par):
        problems.append("a fejléce nem a pár szerinti")
    if gepinfo.get("osztaly") and c["osztaly_ido_szerint"] and c["osztaly_ido_szerint"] != gepinfo["osztaly"]:
        problems.append(f"az ① ideje szerint {OSZTALY[c['osztaly_ido_szerint']]}-futás")
    if problems:
        return {"allapot": "hiba", "futas": c, "megjegyzes": "; ".join(problems)}
    if not c["teljes"]:
        return {"allapot": "folyamatban", "futas": c, "megjegyzes": f"{named}: {c['kesz']}/{c['kell']}"}
    return {"allapot": "megvan", "futas": c, "megjegyzes": ""}


def resolve_uj(par: dict, gep: str, own: list[dict], gepinfo: dict, n: int) -> dict:
    """A gép új futásai ebből a konfigurációból: {allapot, futasok (teljesek, sorszám szerint), felkesz,
    megjegyzes}. Állapot: megvan (n teljes) / részben / hiányzik / hiba."""
    same = [r for r in own if fits(r, par)]
    base = {"futasok": [], "felkesz": None}
    bad = [(r, p) for r in same if (p := _gep_json_problems(r, par, gep, gepinfo))]
    if bad:
        return {**base, "allapot": "hiba", "megjegyzes": "; ".join(f"{r['path'].name}: {', '.join(p)}" for r, p in bad)}
    full = sorted((r for r in same if r["teljes"]), key=started)
    part = [r for r in same if not r["teljes"]]
    if len(full) > n:
        return {**base, "allapot": "hiba", "megjegyzes": f"{len(full)} teljes futás illik ide ({n} kell): "
                + ", ".join(r["path"].name for r in full) + " — az eszköz nem választ (a döntés a naplóba kerül)"}
    if len(part) > 1:
        return {**base, "allapot": "hiba", "megjegyzes": "több félkész futás: " + ", ".join(r["path"].name for r in part)}
    note = f"{len(full)}/{n}" + (f"; folyamatban: {part[0]['path'].name} ({part[0]['kesz']}/{part[0]['kell']})" if part else "")
    state = "megvan" if len(full) == n else ("részben" if full or part else "hiányzik")
    return {"allapot": state, "futasok": full, "felkesz": part[0] if part else None, "megjegyzes": note}


def slots(protocol: dict, meres_dir: Path = MERES, gepek_dir: Path = GEPEK_DIR,
          extra: tuple[str, ...] = ()) -> tuple[dict, dict, dict]:
    """(gépek, helyek {pár: {gép: {"korabbi": hely | None, "uj": hely}}}, idegen futások {gép: [mappa]})."""
    kuszob = int(protocol["gep_azonositas"]["kuszob_ms"])
    n = int(protocol["ismetles_futas"]["szam"])
    gepek = machines(protocol, gepek_dir, extra)
    flat = scan(meres_dir, kuszob)
    own = {g: scan(meres_dir / g, kuszob) for g in gepek}
    pairs = protocol["parok"]
    out = {p["id"]: {g: {"korabbi": resolve_korabbi(p, g, flat, gepek[g]), "uj": resolve_uj(p, g, own[g], gepek[g], n)}
                     for g in gepek} for p in pairs}
    foreign = {g: [r["path"].name for r in own[g] if not any(fits(r, p) for p in pairs)] for g in gepek}
    stray = sorted(d.name for d in meres_dir.iterdir() if d.is_dir() and not (d / "fej.json").exists()
                   and d.name not in gepek) if meres_dir.is_dir() else []
    if stray:
        foreign["(nem számító gép)"] = stray
    return gepek, out, {g: v for g, v in foreign.items() if v}


def run_sets(hely_g: dict) -> list:
    """Egy hely (pár × gép) készletei: K (korábbi), ha megvan, és az új futások sorszámai."""
    out = [K] if hely_g["korabbi"] and hely_g["korabbi"]["allapot"] == "megvan" else []
    return out + list(range(1, len(hely_g["uj"]["futasok"]) + 1))


def run_of(hely_g: dict, s) -> Path | None:
    if s == K:
        k = hely_g["korabbi"]
        return k["futas"]["path"] if k and k["allapot"] == "megvan" else None
    fs = hely_g["uj"]["futasok"]
    return fs[s - 1]["path"] if 1 <= s <= len(fs) else None


def label(gep: str, s) -> str:
    return f"{gep} (korábbi)" if s == K else f"{gep} #{s}"


def pairings(sa: list, sb: list) -> list[tuple]:
    """Két gép készletei közti párosítások: azonos készlet (korábbi–korábbi, #i–#i); és ha az egyik gépnek
    csak korábbi futása van, az a másik gép minden új futásával."""
    out = [(x, x) for x in sa if x in sb]
    if sa == [K]:
        out += [(K, x) for x in sb if x != K]
    elif sb == [K]:
        out += [(x, K) for x in sa if x != K]
    return out


# ------------------------------------------------------------------ összevetés
def _proto(par: dict, boot: dict) -> dict:
    """A két-futásos eszköz ellenőrzéséhez és összevetéséhez kellő protokoll-részek."""
    return {"allapot": "jovahagyva", "kerdessor": par["kerdessor"], "kod": {"ujjlenyomat": par["kod"]["ujjlenyomat"]},
            "beallitasok": {"ismetles": par["ismetles"]}, "statisztika": {"bootstrap": boot}}


def _questions(par: dict, root: Path) -> list[dict]:
    qfile = root / par["kerdessor"]["fajl"]
    if meres.sha256_text(qfile) != par["kerdessor"]["sha256"]:
        raise SystemExit(f"A kérdéssor ({par['kerdessor']['fajl']}) nem az, amit a protokoll rögzít.")
    return proba.load_questions(qfile)


def same_text(a: v2.Run, b: v2.Run) -> dict:
    """Ágonként: hány kérdésen ugyanaz a modell nyers szövege a két futásban (ahol mindkettőben van)."""
    out = {}
    for arm in fo.AGAK:
        n = k = 0
        for i in a.rows.keys() & b.rows.keys():
            ta, tb = a.rows[i]["agak"].get(arm), b.rows[i]["agak"].get(arm)
            if ta and tb and ta.get("modell_szoveg") is not None and tb.get("modell_szoveg") is not None:
                n += 1
                k += ta["modell_szoveg"] == tb["modell_szoveg"]
        out[arm] = {"k": k, "n": n}
    return out


def verdict(d: dict | None) -> tuple[int, bool] | None:
    if not d or d.get("kulonbseg") is None:
        return None
    x = d["kulonbseg"]
    return (x > 0) - (x < 0), bool(d["also"] > 0 or d["felso"] < 0)


def independent(per_set: dict[str, dict | None]) -> bool | None:
    """Független-e a géptől és az ismétléstől: legalább két készleten van eredmény, és mindegyiken ugyanaz a
    különbség előjele és az intervallum ítélete (tartalmazza-e a 0-t). None: kevesebb mint két készleten."""
    vs = [v for v in (verdict(x) for x in per_set.values()) if v is not None]
    return None if len(vs) < 2 else len(set(vs)) == 1


def mp_key(a: str, b: str) -> str:
    return f"{a}|{b}"


def _slim(res: dict) -> dict:
    """A kérdésenkénti részletek nélkül (a jelentés JSON-ja így kicsi marad; az eltérő kérdések külön listában)."""
    return {k: v for k, v in res.items() if k != "kerdesenkent"}


def analyze(protocol_path: Path = PROTOKOLL, meres_dir: Path = MERES, root: Path = ROOT,
            gepek_dir: Path = GEPEK_DIR, db_path: Path | None = None, rejudge: bool = True) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    p_sha = meres.sha256_text(protocol_path)
    gepek, hely, foreign = slots(protocol, meres_dir, gepek_dir)
    order = list(gepek)
    pairs = {p["id"]: p for p in protocol["parok"]}
    qs = {pid: _questions(p, root) for pid, p in pairs.items()}

    con = cat = wl = None
    if rejudge:
        try:
            con = connect(db_path or DB_PATH, read_only=True)
            cat = catalog.load()
            wl = catalog.whitelist(cat, con)
        except Exception as exc:  # a tárház nélkül is elkészül, csak az újraszámolás marad ki
            con, rejudge = None, False
            print(f"(A tárház nem érhető el, az ítéletek újraszámolása kimarad: {exc})")

    cache: dict[Path, v2.Run] = {}

    def load(pid: str, gep: str, s) -> v2.Run | None:
        p = run_of(hely[pid][gep], s)
        if p is None:
            return None
        if p not in cache:
            cache[p] = v2.Run(p, label(gep, s))
        return cache[p]

    def cmp(pid: str, a: v2.Run, b: v2.Run) -> dict:      # különbség: b − a
        proto = _proto(pairs[pid], pairs[pid]["bootstrap"])
        err, warn = fo.check(b, a, proto, qs[pid])
        res = fo.compare(b, a, qs[pid], proto)
        return {"hibak": err, "figyelmeztetesek": warn, "eredmeny": _slim(res), "azonos_szoveg": same_text(a, b),
                "eltero_ertelmezes": [r["id"] for r in res["kerdesenkent"] if r["azonos_ertelmezes"] is False]}

    ism: dict[str, dict] = {}
    megism: dict[str, dict] = {}
    kozott: dict[str, dict] = {}
    rejudged: dict[str, list[str]] = {}
    for pid in pairs:
        sets = {g: run_sets(hely[pid][g]) for g in order}
        ism[pid], megism[pid], kozott[pid] = {}, {}, {}
        for g in order:
            reps = [s for s in sets[g] if s != K]
            if len(reps) >= 2:
                rr = {s: load(pid, g, s) for s in reps}
                common = set.intersection(*(set(r.rows) for r in rr.values()))
                ism[pid][g] = {"parok": [{"a": i, "b": j, **cmp(pid, rr[i], rr[j])} for i, j in combinations(reps, 2)],
                               "mind_azonos": {"k": sum(all(fo.same_reading(rr[reps[0]].rows[q], rr[s].rows[q]) for s in reps[1:])
                                                        for q in common), "n": len(common), "futasok": len(reps)}}
            if K in sets[g] and reps:
                megism[pid][g] = [{"b": s, **cmp(pid, load(pid, g, K), load(pid, g, s))} for s in reps]
        for ga, gb in combinations(order, 2):
            pp = pairings(sets[ga], sets[gb])
            if pp:
                kozott[pid][mp_key(ga, gb)] = [{"a": sa, "b": sb, **cmp(pid, load(pid, ga, sa), load(pid, gb, sb))}
                                               for sa, sb in pp]
        if rejudge:
            runs = {label(g, s): load(pid, g, s) for g in order for s in sets[g]}
            if runs:
                qmap = {q["id"]: q for q in qs[pid]}
                rejudged[pid] = v2.rejudge(runs, qmap, cat, wl, con)

    all_sets = []
    for g in order:
        ks = {s for pid in pairs for s in run_sets(hely[pid][g])}
        all_sets += [(g, s) for s in ([K] if K in ks else []) + sorted(x for x in ks if x != K)]
    concl = []
    for k in protocol["kovetkeztetesek"]:
        row = {"id": k["id"], "meres": k["meres"], "leiras": k["leiras"], "kozolt": k.get("kozolt"), "keszletenkent": {}}
        for g, s in all_sets:
            lab = label(g, s)
            if "futasok" in k:      # K1 a futás saját összesítéséből
                vals = {}
                for pid in k["futasok"]:
                    p = run_of(hely[pid][g], s)
                    vals[pid] = (json.loads((p / "osszegzes.json").read_text(encoding="utf-8"))["osszegzes"].get("K1_paros")
                                 if p else None)
                row["keszletenkent"][lab] = vals
            else:
                a, b = load(k["a"], g, s), load(k["b"], g, s)
                row["keszletenkent"][lab] = (fo.compare(a, b, qs[k["a"]], _proto(pairs[k["a"]], k["bootstrap"]))["fo"]
                                             if a and b else None)
        if "futasok" in k:
            row["fuggetlen"] = {pid: independent({lab: v[pid] for lab, v in row["keszletenkent"].items()})
                                for pid in k["futasok"]}
        else:
            row["fuggetlen"] = independent(row["keszletenkent"])
        concl.append(row)
    if con is not None:
        con.close()

    def pool(items: list[dict]) -> dict | None:
        if not items:
            return None
        same_n = sum(x["eredmeny"]["egyezes"]["azonos_ertelmezes"] for x in items)
        all_n = sum(x["eredmeny"]["egyezes"]["kerdesek"] for x in items)
        return {"azonos_ertelmezes": meres._rate(same_n, all_n), "osszevetesek": len(items)}

    osszesitve = {
        "ismetlesek": {g: pool([x for pid in pairs for x in ism[pid].get(g, {}).get("parok", [])]) for g in order},
        "megismetles": {g: pool([x for pid in pairs for x in megism[pid].get(g, [])]) for g in order},
        "gepek_kozott": {mp_key(a, b): pool([x for pid in pairs for x in kozott[pid].get(mp_key(a, b), [])])
                         for a, b in combinations(order, 2)},
    }
    for part in osszesitve.values():
        for key in [k for k, v in part.items() if v is None]:
            del part[key]

    return {"protokoll": {"fajl": protocol_path.relative_to(root).as_posix() if protocol_path.is_relative_to(root)
                          else protocol_path.name, "sha256": p_sha,
                          "jovahagyas": protocol.get("jovahagyas"),
                          "elemzes_rogzitett": (protocol.get("elemzes") or {}).get("sha256"),
                          "elemzes_most": meres.sha256_text(Path(__file__))},
            "ismetles_futas": int(protocol["ismetles_futas"]["szam"]),
            "gepek": {g: _machine_json(v) for g, v in gepek.items()},
            "helyek": {pid: {g: _slot_json(s) for g, s in v.items()} for pid, v in hely.items()},
            "idegen_futasok": foreign,
            "ismetelhetoseg": ism, "megismetles": megism, "gepek_kozott": kozott, "osszesitve": osszesitve,
            "kovetkeztetesek": concl, "ujraszamolas": rejudged if rejudge else None}


def _machine_json(g: dict) -> dict:
    reg = g["nyilvantartas"] or {}
    return {"osztaly": g["osztaly"], "leiras": g["leiras"], "felveve": reg.get("felveve"),
            "gepnev": reg.get("gepnev"), "processzor": reg.get("processzor"), "videokartyak": reg.get("videokartyak"),
            "ollama": reg.get("ollama"), "tarhaz": reg.get("tarhaz")}


def _run_json(c: dict | None) -> dict | None:
    if not c:
        return None
    gj = c.get("gep_json") or {}
    return {"mappa": c["path"].name, "ido1_median_ms": c["ido1_median_ms"], "osztaly_ido_szerint": c["osztaly_ido_szerint"],
            "kesz": c["kesz"], "kell": c["kell"], "digest": (c["head"].get("digest") or "")[:12],
            "ollama": gj.get("ollama"), "ollama_ps": gj.get("ollama_ps_utana"),
            "inditasok": len(gj.get("inditasok", [])) or None}


def _slot_json(s: dict) -> dict:
    k, u = s["korabbi"], s["uj"]
    return {"korabbi": {"allapot": k["allapot"], "megjegyzes": k["megjegyzes"], "futas": _run_json(k["futas"])} if k else None,
            "uj": {"allapot": u["allapot"], "megjegyzes": u["megjegyzes"], "futasok": [_run_json(c) for c in u["futasok"]],
                   "felkesz": _run_json(u["felkesz"])}}


# ------------------------------------------------------------------ jelentés
def _d(p: dict | None) -> str:
    if not p or p.get("kulonbseg") is None:
        return "—"
    return f"{v2._pp(p['kulonbseg'])} ({v2._pp(p['also'])} – {v2._pp(p['felso'])})"


def _proc_split(ps: str | None) -> str:
    """Az `ollama ps` PROCESSOR oszlopa (pl. „100% GPU”, „48%/52% CPU/GPU”), ha kiolvasható."""
    for line in (ps or "").splitlines()[1:]:
        for tok in ("CPU/GPU", "GPU", "CPU"):
            i = line.find(tok)
            if i > 0:
                start = line.rfind("  ", 0, i)
                return line[start:i + len(tok)].strip()
    return ""


def _set_name(s) -> str:
    return "korábbi" if s == K else f"#{s}"


def _cmp_row(name: str, x: dict) -> str:
    e, f, t = x["eredmeny"]["egyezes"], x["eredmeny"]["fo"], x["azonos_szoveg"]
    txt = " / ".join(f"{t[a]['k']}/{t[a]['n']}" for a in fo.AGAK)
    return (f"| {name} | {e['azonos_ertelmezes']}/{e['kerdesek']} | {txt} | {v2._r(f['v3'])} / {v2._r(f['v4'])} | {_d(f)} |")


def _pool_line(name: str, o: dict) -> str:
    a = o["azonos_ertelmezes"]
    return (f"- {name}: {a['k']}/{a['n']} = {meres._pct(a['arany'])} ({meres._pct(a['also'])} – {meres._pct(a['felso'])}), "
            f"{o['osszevetesek']} összevetésből")


def report_md(res: dict, protocol: dict) -> str:
    pr = res["protokoll"]
    order = list(res["gepek"])
    n = res["ismetles_futas"]
    yn = {True: "igen", False: "**nem**", None: "—"}
    head_cmp = ("| | azonos ① értelmezés | azonos szöveg (fő ág / kontrollág) | teljes egyezés: A / B | különbség B − A (95%) |",
                "|---|---|---|---|---|")
    L = ["# K1 géphatás: a mérések több gépen, gépenként háromszor", "",
         f"Géppel készült (`tools/k1_gepvaltas.py`), a futások mappáiból, modell nélkül. Protokoll: `{pr['fajl']}` "
         f"(SHA256 `{pr['sha256'][:16]}…`, jóváhagyta: {(pr['jovahagyas'] or {}).get('ki', '—')}, "
         f"{(pr['jovahagyas'] or {}).get('mikor', '—')}). Minden konfigurációban ugyanaz a modellfájl, kód, kérdéssor, "
         f"futási protokoll és seed; egy gépen {n} új futás, a sorszám az indítás sorrendje. Két futás különbsége mindig "
         "**B − A**. Azonos szöveg: a modell nyers szövege betűre ugyanaz.", ""]
    if pr["elemzes_rogzitett"] and pr["elemzes_rogzitett"] != pr["elemzes_most"]:
        L += [f"**Figyelmeztetés:** ez az eszköz a protokoll jóváhagyása óta megváltozott "
              f"(`{pr['elemzes_most'][:16]}…` ≠ `{pr['elemzes_rogzitett'][:16]}…`).", ""]
    L += ["## Gépek", "", "| gép | osztály | gépnév | processzor | videókártya | ollama | felvéve |", "|---|---|---|---|---|---|---|"]
    for g, m in res["gepek"].items():
        vk = "; ".join(m["videokartyak"] or []) or ("—" if m["gepnev"] else "")
        L.append(f"| {g} | {OSZTALY.get(m['osztaly'], '?')} | {m['gepnev'] or ''} | {m['processzor'] or ''} | {vk} | "
                 f"{m['ollama'] or ''} | {m['felveve'] or ('a protokollban' if m['leiras'] else '')} |")
    L += ["", "## Futások", "", "| pár | mérés | modell | kód | " + " | ".join(order) + " |",
          "|---|---|---|---|" + "---|" * len(order)]
    pairs = {p["id"]: p for p in protocol["parok"]}

    def cell(s):
        parts = []
        k = s["korabbi"]
        if k:
            parts.append(f"korábbi: `{k['futas']['mappa']}` (① {v2._sec(k['futas']['ido1_median_ms'])})"
                         if k["allapot"] == "megvan" else f"korábbi: **{k['allapot']}** {k['megjegyzes']}")
        u = s["uj"]
        splits = sorted({_proc_split(c["ollama_ps"]) for c in u["futasok"]} - {""})
        parts.append(f"új: {u['megjegyzes']}" + (f" ({', '.join(splits)})" if splits else "")
                     if u["allapot"] != "hiba" else f"új: **hiba** — {u['megjegyzes']}")
        return "<br>".join(parts) or "—"
    for pid, v in res["helyek"].items():
        p = pairs[pid]
        L.append(f"| {pid} | {p['meres']}. | {p['modell']} | {p['kod']['verzio']} | " + " | ".join(cell(v[g]) for g in order) + " |")
    if res["idegen_futasok"]:
        L += ["", "Egyik párhoz sem illő futások (nem számítanak bele): "
              + "; ".join(f"{g}: {', '.join(v)}" for g, v in res["idegen_futasok"].items()) + "."]

    L += ["", "## 1. Ismételhetőség: ugyanaz a gép, ugyanaz a seed", "",
          "Ugyanaz a konfiguráció ugyanazon a gépen egymás után; ha a rögzített seed mindent meghatározna, minden "
          "egyezne. Ez az alap, amihez a gépek közti eltérést mérjük.", "", *head_cmp]
    any_row = False
    for pid, per in res["ismetelhetoseg"].items():
        for g, v in per.items():
            any_row = True
            m = v["mind_azonos"]
            for x in v["parok"]:
                L.append(_cmp_row(f"{pid} · {g} #{x['a']} → #{x['b']}", x))
            L.append(f"| {pid} · {g}: mind a {m['futasok']} futásban azonos ① | {m['k']}/{m['n']} | | | |")
    if not any_row:
        L.append("| még nincs gép két új futással | | | | |")
    L += ["", "## 2. A korábbi (közölt) futás megismétlése ugyanazon a gépen", "", *head_cmp]
    any_row = False
    for pid, per in res["megismetles"].items():
        for g, xs in per.items():
            for x in xs:
                any_row = True
                L.append(_cmp_row(f"{pid} · {g} korábbi → #{x['b']}", x))
    if not any_row:
        L.append("| még nincs új futás korábbi mellett | | | | |")
    L += ["", "## 3. Gépek között", "", *head_cmp]
    any_row = False
    for pid, per in res["gepek_kozott"].items():
        for key, xs in per.items():
            ga, gb = key.split("|")
            for x in xs:
                any_row = True
                L.append(_cmp_row(f"{pid} · {ga} {_set_name(x['a'])} → {gb} {_set_name(x['b'])}", x))
    if not any_row:
        L.append("| még nincs két gépen futás | | | | |")
    o = res["osszesitve"]
    L += ["", "## Összesítve: azonos ① értelmezés (Wilson 95%)", ""]
    for g, v in o["ismetlesek"].items():
        L.append(_pool_line(f"ugyanazon a gépen, egymás után ({g})", v))
    for g, v in o["megismetles"].items():
        L.append(_pool_line(f"a korábbi futás és az újak ({g})", v))
    for key, v in o["gepek_kozott"].items():
        L.append(_pool_line(f"gépek között ({key.replace('|', ' – ')})", v))
    if not any(o.values()):
        L.append("- még nincs összevetés")

    sets = list(next(iter(res["kovetkeztetesek"]))["keszletenkent"]) if res["kovetkeztetesek"] else []
    L += ["", "## A mérések következtetései készletenként", "",
          "Mindegyik összevetés (modellek, kódváltozatok — ugyanazon a gépen, ugyanazzal a seeddel) külön minden készleten: "
          "gép × korábbi / #1 / #2 / #3. **Független** (a géptől és az ismétléstől), ha legalább két készleten van eredmény, "
          "és mindegyiken ugyanaz a különbség előjele és az intervallum ítélete (tartalmazza-e a 0-t).", "",
          "| | mérés | összevetés | " + " | ".join(sets) + " | független? | közölt |",
          "|---|---|---|" + "---|" * len(sets) + "---|---|"]
    for k in res["kovetkeztetesek"]:
        if isinstance(k["fuggetlen"], dict):
            for pid in k["fuggetlen"]:
                L.append(f"| {k['id']} | {k['meres']}. | {k['leiras']}: {pid} | "
                         + " | ".join(_d(k["keszletenkent"][s][pid]) for s in sets)
                         + f" | {yn[k['fuggetlen'][pid]]} | {k.get('kozolt') or ''} |")
        else:
            L.append(f"| {k['id']} | {k['meres']}. | {k['leiras']} | " + " | ".join(_d(k["keszletenkent"][s]) for s in sets)
                     + f" | {yn[k['fuggetlen']]} | {k.get('kozolt') or ''} |")
    L += ["", "## Ellenőrzés", ""]
    for pid in res["helyek"]:
        msgs = []
        for sect in ("ismetelhetoseg", "megismetles", "gepek_kozott"):
            for key, v in res[sect].get(pid, {}).items():
                for x in (v["parok"] if isinstance(v, dict) else v):
                    msgs += [f"{key}: hiba: {e}" for e in x["hibak"]] + [f"{key}: figyelmeztetés: {w}" for w in x["figyelmeztetesek"]]
        if res["ujraszamolas"] is not None and pid in res["ujraszamolas"]:
            c = len(res["ujraszamolas"][pid])
            msgs.append("a tárolt ítéletek újraszámolva: " + ("mind egyezik" if not c else f"**{c} eltérés**"))
        L.append(f"- {pid}: " + ("; ".join(msgs) if msgs else "rendben"))
    if res["ujraszamolas"] is None:
        L.append("- a tárolt ítéletek újraszámolása kimaradt (a tárház nem volt elérhető)")
    return "\n".join(L) + "\n"


def to_json(res: dict) -> str:
    return json.dumps(res, ensure_ascii=False, indent=1, default=str)


def main(argv: list[str] | None = None) -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="A K1 géphatás: minden konfiguráció több gépen, gépenként háromszor.")
    ap.add_argument("--protokoll", type=Path, default=PROTOKOLL)
    ap.add_argument("--meres", type=Path, default=MERES, help="a futások mappája (alapból logs/meres)")
    ap.add_argument("--kimenet", type=Path, default=KIMENET)
    ap.add_argument("--ujraszamolas-nelkul", action="store_true", help="a tárolt ítéletek újraszámolása nélkül")
    x = ap.parse_args(argv)
    res = analyze(x.protokoll, x.meres, rejudge=not x.ujraszamolas_nelkul)
    protocol = json.loads(x.protokoll.read_text(encoding="utf-8"))
    x.kimenet.parent.mkdir(parents=True, exist_ok=True)
    x.kimenet.write_text(report_md(res, protocol), encoding="utf-8")
    x.kimenet.with_suffix(".json").write_text(to_json(res), encoding="utf-8")
    nk = sum(len(xs) for per in res["gepek_kozott"].values() for xs in per.values())
    print(f"{len(res['gepek'])} gép, {nk} gépek közti összevetés. Jelentés: {x.kimenet}")


if __name__ == "__main__":
    main()
