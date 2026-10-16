"""
Fejlesztői próba: a nyelvi réteg végigfuttatása a fejlesztői próbasoron
(eval/fejlesztoi_kerdessor.toml) — értelmezés, elutasítás, 2. kapu és idő kérdésenként.

    uv run python -m narrative.proba
    uv run python -m narrative.proba --csak-ertelmezes          # csak az ① hívás (gyorsabb)
    uv run python -m narrative.proba --kerdes f03 --kerdes f11  # csak ezek
    uv run python -m narrative.proba --modell gemma3:4b         # másik helyi modellel

A jelentés a logs/ mappába kerül (proba_ÉÉÉÉHHNN_ÓÓPPMM.md és .json), a hívások a szokásos
naplóba (logs/llm_calls.jsonl, kérdés-azonosítóval). Ez hangolásra való: a dolgozat mérése a
lezárt kérdéssoron megy (a próbasor fejléce szerint).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import statistics
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path

from data.db import DB_PATH, WarehouseUnavailable, connect, use_utf8_console
from narrative.client import ROOT, LlmClient, load_config
from narrative.pipeline import FreeAnswer, ask
from narrative.to_spec import to_spec
from semantic import catalog
from semantic import spec as sp
from xai import narrative as nv

KERDESSOR = ROOT / "eval" / "fejlesztoi_kerdessor.toml"
LOGS = ROOT / "logs"


def load_questions(path: Path = KERDESSOR) -> list[dict]:
    items = tomllib.loads(path.read_text(encoding="utf-8"))["kerdes"]
    ids = [q["id"] for q in items]
    if len(ids) != len(set(ids)):
        raise ValueError("a próbasorban ismétlődő azonosító van")
    return items


def _window(q: dict, metric: str, cat, wl) -> tuple[str | None, str | None]:
    """Az elvárt időablak ugyanúgy normalizálva, mint a kapuban (az adat széleire szűkítve)."""
    window = {k: q[k] for k in ("tol", "ig") if q.get(k)}
    g = sp.check({"metrika": metric, "idoablak": window}, cat, wl)
    if not g.ok:
        return None, None
    return (g.spec.tol.isoformat() if g.spec.tol else None, g.spec.ig.isoformat() if g.spec.ig else None)


def _as_list(v) -> list:
    return list(v) if isinstance(v, (list, tuple)) else [v]


def core_ok(q: dict, gate: sp.GateResult) -> bool | None:
    """F-1 (rendszerterv 04.): helyes-e a mérőszám és a bontás. None: csapdakérdés."""
    if q.get("elutasitas"):
        return None
    if not gate.ok:
        return False
    return any(gate.spec.metrika in _as_list(c.get("metrika")) and list(gate.spec.bontas) == list(c.get("bontas", []))
               for c in variants(q))


ALT_FIELDS = ("metrika", "bontas", "szuro", "tol", "ig", "rendezes", "limit", "teljes")


def variants(q: dict) -> list[dict]:
    """Az elvárt értelmezés és az elfogadható alternatívái („alternativak”: a felsorolt mezők
    felülírják a fő elvárást — pl. „bútor” = a fő bútorkategória VAGY az összes bútorkategória)."""
    base = {k: v for k, v in q.items() if k != "alternativak"}
    return [base] + [{**base, **{k: v for k, v in alt.items() if k in ALT_FIELDS}} for alt in q.get("alternativak", [])]


def judge(q: dict, gate: sp.GateResult, cat, wl, groups=None) -> tuple[str, list[str]]:
    """Az ítélet a fő elvárásra és az alternatívákra: ha bármelyik pontosan egyezik, „helyes”;
    különben a fő elváráshoz mért eltérések."""
    results = [_judge_one(c, gate, cat, wl, groups) for c in variants(q)]
    return next((r for r in results if r[0] == "helyes"), results[0])


def _judge_one(q: dict, gate: sp.GateResult, cat, wl, groups=None) -> tuple[str, list[str]]:
    """(ítélet, eltérések). Ítélet: helyes | hibás értelmezés | helyes elutasítás |
    téves elutasítás | hiányzó elutasítás | más elutasítás.

    A metrika, a rendezés és az elvárt elutasítás lista is lehet (bármelyik jó). „teljes”:
    természetes sorrendnél a sor nem lehet csonka — ehhez kell a groups(spec) → a csoportok
    száma a teljes sorban (a mérés az adatbázisból számolja; nélküle ez az ellenőrzés kimarad)."""
    want_reject = q.get("elutasitas")
    if want_reject:
        if gate.ok:
            return "hiányzó elutasítás", [f"elfogadva: {gate.spec.key()}"]
        kod = gate.elutasitas.kod
        wanted = _as_list(want_reject)
        return ("helyes elutasítás", []) if "*" in wanted or kod in wanted else \
            ("más elutasítás", [f"elvárt: {' vagy '.join(wanted)}, kapott: {kod}"])
    if not gate.ok:
        return "téves elutasítás", [f"{gate.elutasitas.kod}: {gate.elutasitas.uzenet}"]
    s, diffs = gate.spec, []
    metrics = q["metrika"] if isinstance(q.get("metrika"), list) else [q.get("metrika")]
    if "metrika" in q and s.metrika not in metrics:
        diffs.append(f"metrika: {s.metrika} (elvárt: {' vagy '.join(metrics)})")
    if "bontas" in q and list(s.bontas) != list(q["bontas"]):
        diffs.append(f"bontás: {list(s.bontas)} (elvárt: {q['bontas']})")
    if "szuro" in q:
        got = {d: sorted(v) for d, v in s.szuro}
        want = {d: sorted(v) for d, v in q["szuro"].items()}
        if got != want:
            diffs.append(f"szűrő: {got} (elvárt: {want})")
    if q.get("idoablak") == "barmely":
        pass                                         # „mostanában”: bármilyen időablak elfogadható
    elif "tol" in q or "ig" in q:
        tol, ig = _window(q, s.metrika, cat, wl)
        got_tol, got_ig = (s.tol.isoformat() if s.tol else None), (s.ig.isoformat() if s.ig else None)
        if "tol" in q and got_tol != tol:
            diffs.append(f"tól: {got_tol or 'az adat eleje'} (elvárt: {tol or 'az adat eleje'})")
        if "ig" in q and got_ig != ig:
            diffs.append(f"ig: {got_ig or 'az adat vége'} (elvárt: {ig or 'az adat vége'})")
    if "rendezes" in q and s.rendezes not in _as_list(q["rendezes"]):
        diffs.append(f"rendezes: {s.rendezes} (elvárt: {' vagy '.join(_as_list(q['rendezes']))})")
    if "limit" in q and s.limit != q["limit"]:
        diffs.append(f"limit: {s.limit} (elvárt: {q['limit']})")
    if q.get("teljes") and groups is not None and s.rendezes == "bontas" and s.bontas:
        n = groups(s)
        if s.limit < n:
            diffs.append(f"csonka sor: {s.limit} csoport látszik a {n}-ból")
    return ("helyes", []) if not diffs else ("hibás értelmezés", diffs)


def _sum_times(times: list[dict]) -> dict:
    out: dict[str, int] = {}
    for t in times:
        for k, v in t.items():
            out[k] = out.get(k, 0) + v
    return out


def run_one(q: dict, cat, wl, con, client: LlmClient, only_spec: bool, mod: str) -> dict:
    t0 = time.perf_counter()
    if only_spec:
        att = to_spec(q["kerdes"], cat, wl, client, question_id=q["id"])
        fa = FreeAnswer(q["kerdes"], att, None, None, (time.perf_counter() - t0) * 1000.0)
    else:
        fa = ask(q["kerdes"], cat, wl, con, client, mod=mod, question_id=q["id"])
    s = fa.spec
    verdict, diffs = judge(q, s.gate, cat, wl)
    row = {"id": q["id"], "kerdes": q["kerdes"], "itelet": verdict, "elteresek": diffs,
           "kapu1": s.gate.status, "spec": s.gate.spec.to_dict() if s.gate.ok else None,
           "javito_kor": s.javito_kor, "feloldasok": [dataclasses.asdict(n) for n in s.feloldasok],
           "javitasok": [dataclasses.asdict(f) for f in s.javitasok],
           "urlap": s.urlap, "ido1_ms": round(s.ido_ms), "idok1": _sum_times(s.idok),
           "modell_hiba": s.hiba}
    t = fa.szoveg
    if t is not None:
        row.update({"szoveg": t.szoveg, "sablon": t.sablon, "ok_sablon": t.ok_sablon,
                    "modell_szoveg": t.modell_szoveg, "kapu2": None if t.verdict is None else t.verdict.ok,
                    "kapu2_problemak": [] if t.verdict is None else t.verdict.problemak,
                    "ismetelt_jelolok": [] if t.verdict is None else t.verdict.ismetelt_jelolok,
                    "ismetelt_ertekek": [] if t.verdict is None else t.verdict.ismetelt_ertekek,
                    "sajat_szamok": 0 if t.verdict is None else t.verdict.kozvetlen_szamok,
                    "ido2_ms": round(t.ido_ms), "idok2": t.idok})
    row["ido_ms"] = round(fa.ido_ms)
    return row


def _sec(ms) -> str:
    return "—" if ms is None else nv.fmt_num(ms / 1000, 1)


def summary(rows: list[dict]) -> dict:
    expected_ok = [r for r in rows if r["tipus"] == "valasz"]
    traps = [r for r in rows if r["tipus"] == "csapda"]
    texts = [r for r in rows if r.get("kapu2") is not None]
    out = {
        "kerdesek": len(rows),
        "helyes_ertelmezes": sum(r["itelet"] == "helyes" for r in expected_ok),
        "ertelmezendo": len(expected_ok),
        "helyes_elutasitas": sum(r["itelet"] == "helyes elutasítás" for r in traps),
        "csapda": len(traps),
        "javito_kor": sum(r["javito_kor"] for r in rows),
        "kodbeli_javitas": sum(bool(r.get("javitasok")) for r in rows),
        "sajat_szam_szoveg": sum(bool(r.get("sajat_szamok")) for r in texts),
        "ismetelt_szoveg": sum(bool(r.get("ismetelt_ertekek") or r.get("ismetelt_jelolok")) for r in texts),
        "kapu2_atment": sum(bool(r["kapu2"]) for r in texts),
        "szoveg": len(texts),
        "ido1_median_ms": statistics.median(r["ido1_ms"] for r in rows) if rows else None,
        "ido2_median_ms": statistics.median(r["ido2_ms"] for r in texts) if texts else None,
        "ido_median_ms": statistics.median(r["ido_ms"] for r in rows) if rows else None,
    }
    for part in ("betoltes_ms", "prompt_ms", "generalas_ms"):
        for n, key, pool in (("1", "idok1", rows), ("2", "idok2", texts)):
            vals = [r[key].get(part) for r in pool if (r.get(key) or {}).get(part) is not None]
            if vals:
                out[f"ido{n}_{part.removesuffix('_ms')}_median_ms"] = statistics.median(vals)
    return out


def report_md(rows: list[dict], head: dict) -> str:
    s = head["osszegzes"]
    lines = [f"# Fejlesztői próba — {head['futtatva']}", "",
             f"Modell: **{head['modell']}**" + (f" (`{head['digest'][:12]}`)" if head.get("digest") else "")
             + f" · promptok: {', '.join(head['promptok'])} · mód: {head['mod']}"
             + (" · csak értelmezés" if head["csak_ertelmezes"] else ""), "",
             "| | |", "|---|---|",
             f"| helyes értelmezés | {s['helyes_ertelmezes']}/{s['ertelmezendo']} |",
             f"| helyes elutasítás (csapda) | {s['helyes_elutasitas']}/{s['csapda']} |",
             f"| javító kör kellett | {s['javito_kor']} |",
             f"| a kód javított az értelmezésen | {s['kodbeli_javitas']} |"]
    if s["szoveg"]:
        lines += [f"| 2. kapu átment (a modell szövege látszik) | {s['kapu2_atment']}/{s['szoveg']} |",
                  f"| a modell jelölő helyett maga írt számot | {s['sajat_szam_szoveg']}/{s['szoveg']} |",
                  f"| ugyanaz az érték kétszer a szövegben | {s['ismetelt_szoveg']}/{s['szoveg']} |"]
    for n, name in (("1", "①"), ("2", "②")):
        if s.get(f"ido{n}_median_ms") is None:
            continue
        lines.append(f"| {name} ideje, medián | {_sec(s[f'ido{n}_median_ms'])} mp |")
        for part, pname in (("betoltes", "ebből betöltés"), ("prompt", "ebből a prompt beolvasása"),
                            ("generalas", "ebből generálás")):
            if f"ido{n}_{part}_median_ms" in s:
                lines.append(f"| … {pname}, medián | {_sec(s[f'ido{n}_{part}_median_ms'])} mp |")
    lines += [f"| egy kérdés összesen, medián | {_sec(s['ido_median_ms'])} mp |", "",
              "| # | kérdés | ítélet | ① mp | ② mp | megjegyzés |", "|---|---|---|---|---|---|"]
    for r in rows:
        note = "; ".join(r["elteresek"])
        if r["javito_kor"]:
            note = ("javító kör; " + note).rstrip("; ")
        if r.get("feloldasok"):
            note += ("; " if note else "") + "feloldva: " + ", ".join(
                f"„{f['beirt']}” → {f['kulcs'] or '?'}" for f in r["feloldasok"])
        if r.get("javitasok"):
            note += ("; " if note else "") + "a kód javította: " + ", ".join(
                f"{f['mezo']} ({f['ok']})" for f in r["javitasok"])
        if r.get("kapu2") is False:
            note += ("; " if note else "") + "2. kapu: " + "; ".join(r["kapu2_problemak"])
        lines.append(f"| {r['id']} | {r['kerdes']} | {r['itelet']} | {_sec(r['ido1_ms'])} | "
                     f"{_sec(r.get('ido2_ms'))} | {note.replace('|', '/')} |")
    texts = [r for r in rows if r.get("szoveg")]
    if texts:
        lines += ["", "## A válaszok", ""]
        for r in texts:
            who = "sablon" if r["sablon"] else "nyelvi modell"
            lines += [f"**{r['id']}** — {r['kerdes']} *({who})*", "", f"> {r['szoveg']}", ""]
            if r.get("modell_szoveg") and r["sablon"]:
                lines += [f"A modell szövege (nem ment át): `{r['modell_szoveg']}`", ""]
    return "\n".join(lines) + "\n"


def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="A nyelvi réteg fejlesztői próbája")
    ap.add_argument("--csak-ertelmezes", action="store_true", help="csak az ① hívás és a KAPU ①")
    ap.add_argument("--kerdes", action="append", help="csak ez a kérdés (azonosító; többször is megadható)")
    ap.add_argument("--modell", help="másik modell (felülírja a configs/llm.toml-t)")
    ap.add_argument("--szabad", action="store_true", help="a ② a kontrollágon (a modell maga írja a számokat)")
    ap.add_argument("--fajl", type=Path, default=KERDESSOR, help="a próbasor fájlja")
    a = ap.parse_args()

    questions = load_questions(a.fajl)
    if a.kerdes:
        questions = [q for q in questions if q["id"] in set(a.kerdes)]
    cfg = load_config()
    if a.modell:
        cfg = dataclasses.replace(cfg, modell=a.modell)
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
    client.preload()
    mod = "szabad" if a.szabad else "jelolo"
    print(f"{len(questions)} kérdés; a jelentés a logs/ mappába kerül.\n")
    rows = []
    for i, q in enumerate(questions, 1):
        row = run_one(q, cat, wl, con, client, a.csak_ertelmezes, mod)
        row["tipus"] = "csapda" if q.get("elutasitas") else "valasz"
        rows.append(row)
        extra = "" if row.get("kapu2") is None else f" · 2. kapu: {'átment' if row['kapu2'] else 'NEM'}"
        print(f"[{i:2}/{len(questions)}] {q['id']} {row['itelet']:<20} {_sec(row['ido_ms']):>6} mp{extra}"
              f"  {q['kerdes']}")
        for d in row["elteresek"]:
            print(f"        {d}")
    con.close()
    calls = cfg.hivasok
    head = {"futtatva": datetime.now().isoformat(timespec="seconds"), "modell": cfg.modell,
            "digest": client._digest, "mod": mod, "csak_ertelmezes": a.csak_ertelmezes,
            "promptok": [calls["to_spec"].version] + ([] if a.csak_ertelmezes else
                                                       [calls["to_text_szabad" if a.szabad and "to_text_szabad" in calls
                                                              else "to_text"].version]),
            "kerdessor": str(a.fajl.relative_to(ROOT)) if a.fajl.is_relative_to(ROOT) else a.fajl.name,
            "osszegzes": summary(rows)}
    LOGS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md, js = LOGS / f"proba_{stamp}.md", LOGS / f"proba_{stamp}.json"
    md.write_text(report_md(rows, head), encoding="utf-8")
    js.write_text(json.dumps({**head, "kerdesek": rows}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    s = head["osszegzes"]
    print(f"\nHelyes értelmezés: {s['helyes_ertelmezes']}/{s['ertelmezendo']} · helyes elutasítás: "
          f"{s['helyes_elutasitas']}/{s['csapda']}" + (f" · 2. kapu átment: {s['kapu2_atment']}/{s['szoveg']}"
                                                         if s["szoveg"] else "")
          + f" · medián idő/kérdés: {_sec(s['ido_median_ms'])} mp")
    print(f"Jelentés: {md.relative_to(ROOT) if md.is_relative_to(ROOT) else md}")


if __name__ == "__main__":
    main()
