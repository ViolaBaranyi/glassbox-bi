"""
A K1 mérés v2-jének összevetése (docs/k1_protokoll_v2.json, „mutatok” és „statisztika”): a v3 és a
v4 nyelvi réteg ugyanazon a lezárt kérdéssoron, kérdésenként párosítva — modell nélkül, a futások
mappáiból.

    uv run python tools/k1_v2_osszevetes.py --v4 logs\\meres\\MAPPA --v3 v3_kod\\logs\\meres\\MAPPA
                                            [--v4-2b logs\\meres\\MAPPA]

Kimenet: docs/k1_v2_eredmeny.md és .json (más hely: --kimenet ÚTVONAL.md).

Az eszköz az eredmények ELŐTT készült (2026-10-20, a kérdéssor lezárása előtt): az elemzés módja így
nem igazodhat a számokhoz. A nyelvi réteg kódját nem érinti (a tools/ nincs a kód ujjlenyomatában).

Mit számol
  * Fő mutató: teljes egyezés (mérőszám, bontás, szűrő, időablak, rendezés) a megválaszolandó
    kérdéseken, a v4 és a v3 különbsége a 4B-vel, kérdésenként párosítva; 95%-os bootstrap a
    kérdések újramintavételével (B és mag a protokollból). Mellé a négymezős tábla (mindkettő
    helyes / csak a v4 / csak a v3 / egyik sem).
  * F-1 és F-2 a két kódnál, ugyanígy párosítva; típusonként a teljes egyezés.
  * K1: a v4 futás szövegei a v4 kapujával (ahogy a mérés pontozta); a v3 futás szövegei a saját
    (v3) kapujukkal ÉS a v4 kapujával újrapontozva — így a két kód szövegei ugyanazzal a mércével
    is összevethetők. Az újrapontozás módszerét az eszköz önmagán ellenőrzi: a v4 futás saját
    szövegeit újrapontozva a tárolt ítéletet kell visszakapnia.
  * A 2B a v4-gyel (leíró), és az idők mediánja.

A protokoll („elemzes”) rögzíti ennek a fájlnak az ujjlenyomatát; ha az eszköz utána változik, a
jelentés figyelmeztet. Mielőtt számol, ellenőriz: jóváhagyott-e a protokoll; minden futás a lezárt kérdéssoron, a
protokollban rögzített kóddal (ujjlenyomat), a megadott modellel, egy ismétléssel ment-e; és a
tárolt ítéletek újraszámolva ugyanazok-e (a pontozás kódja a v3 és a v4 között nem változott).
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.db import DB_PATH, connect, use_utf8_console  # noqa: E402
from narrative import meres, proba  # noqa: E402
from narrative import to_text as tt  # noqa: E402
from narrative import verifier as vf  # noqa: E402
from narrative.client import load_config  # noqa: E402
from semantic import catalog, engine  # noqa: E402
from semantic import spec as sp  # noqa: E402

PROTOKOLL = ROOT / "docs" / "k1_protokoll_v2.json"
KIMENET = ROOT / "docs" / "k1_v2_eredmeny.md"
AGAK = meres.AGAK
JEL = {"helyes": "✓", "helyes elutasítás": "✓", "hibás értelmezés": "✗", "téves elutasítás": "⊘",
       "hiányzó elutasítás": "!", "más elutasítás": "≈", None: "—"}
_PH = re.compile(r"\{[A-Z]+\d*\}")
_PERIOD_LINE = re.compile(r"^Időszak: .*$\n?", re.M)


# ------------------------------------------------------------------ betöltés és ellenőrzés
class Run:
    def __init__(self, path: Path, label: str):
        self.path, self.label = path, label
        self.head = json.loads((path / "fej.json").read_text(encoding="utf-8"))
        rows = meres.latest_rows(meres.read_rows(path))
        self.errors = sorted(r["id"] for r in rows if r["hiba"])
        self.rows = {r["id"]: r for r in rows if not r["hiba"]}

    @property
    def model(self) -> str:
        return self.head.get("modell")


def check_runs(runs: dict[str, Run], protocol: dict, p_sha: str, questions: list[dict]) -> tuple[list[str], list[str]]:
    """(hibák, figyelmeztetések). Hiba: a futás nem a protokoll szerinti — az összevetés nem készül el."""
    err, warn = [], []
    if protocol.get("allapot") != "jovahagyva":
        err.append(f"a protokoll állapota „{protocol.get('allapot')}”, nem „jovahagyva”")
    want_q = protocol["kerdessor"]["sha256"]
    fps = {"v4": protocol["kod"]["ujjlenyomat"], "v3": protocol["kod"]["v3"]["ujjlenyomat"]}
    models = {m["nev"] for m in protocol["modellek"]}
    reps = int(protocol["beallitasok"]["ismetles"])
    ids = {q["id"] for q in questions}
    for key, run in runs.items():
        code = key.split("-")[0]
        h, name = run.head, f"{run.label} ({run.path.name})"
        if h["kerdessor"]["sha256"] != want_q:
            err.append(f"{name}: más kérdéssoron futott ({h['kerdessor']['sha256'][:16]} ≠ {want_q[:16]})")
        if h.get("protokoll", {}).get("sha256") != p_sha:
            err.append(f"{name}: a fejlécben más protokoll ujjlenyomata áll ({str(h.get('protokoll', {}).get('sha256'))[:16]}"
                       f" ≠ {p_sha[:16]}) — a jóváhagyott protokollal kell futnia")
        if h["kod"].get("ujjlenyomat") != fps[code]:
            err.append(f"{name}: a kód ujjlenyomata {str(h['kod'].get('ujjlenyomat'))[:16]}, a protokoll szerinti "
                       f"{code}-é {fps[code][:16]}")
        if h["kod"].get("nem_commitolt_valtozas"):
            warn.append(f"{name}: nem commitolt változással futott (a kód ujjlenyomata ettől még a rögzített)")
        if run.model not in models:
            err.append(f"{name}: a modell ({run.model}) nem szerepel a protokollban")
        if int(h.get("ismetles", 0)) != reps or h.get("csak_ertelmezes"):
            err.append(f"{name}: {h.get('ismetles')} ismétlés{' csak értelmezéssel' if h.get('csak_ertelmezes') else ''}"
                       f" (a protokoll: {reps}, teljes futás)")
        missing = sorted(ids - set(run.rows))
        if missing:
            warn.append(f"{name}: {len(missing)} kérdés eredménye hiányzik vagy modellhibás, kimarad a párosításból: "
                        + ", ".join(missing))
    if runs["v4"].model != runs["v3"].model:
        err.append(f"a v4 és a v3 futás más modellel ment ({runs['v4'].model} ≠ {runs['v3'].model})")
    elif runs["v4"].head.get("digest") != runs["v3"].head.get("digest"):
        warn.append("a v4 és a v3 futás modelljének lenyomata (digest) eltér — ugyanaz a név, de más modellfájl")
    return err, warn


# ------------------------------------------------------------------ újrapontozás
def gate_of(row: dict, cat, wl) -> sp.GateResult:
    """A tárolt eredményből a kapu ítélete (elfogadott: a gépi alak újra a kapun át)."""
    if row["spec"] is not None:
        g = sp.check(row["spec"], cat, wl)
        if not g.ok:
            raise ValueError(f"{row['id']}: a tárolt gépi alakot a kapu most elutasítja ({g.elutasitas.kod})")
        return g
    return sp.GateResult(False, None, sp.Rejection(row["kapu1"], ""))


def rejudge(runs: dict[str, Run], qmap: dict, cat, wl, con) -> list[str]:
    """A tárolt ítélet újraszámolva (a pontozás kódja — narrative/proba.py — a v3 és a v4 közt azonos)."""
    groups = meres._groups_counter(cat, wl, con)
    out = []
    for run in runs.values():
        for qid, row in run.rows.items():
            q = qmap[qid]
            g = gate_of(row, cat, wl)
            verdict, _ = proba.judge(q, g, cat, wl, groups=groups)
            if verdict != row["itelet"] or proba.core_ok(q, g) != row["f1"]:
                out.append(f"{run.label} {qid}: tárolt „{row['itelet']}”, újraszámolva „{verdict}”")
    return out


def v4_flag(text: str | None, mod: str, res, minimal: bool) -> tuple[bool, list[str], str]:
    """Egy modellszöveg a v4 2. kapujával — pontosan úgy, ahogy a v4 to_text pontoz.
    (megjelölt-e, a problémák fajtái, a nézet szövege)."""
    view = tt.build_view(res, placeholders=(mod == "jelolo"), minimal=minimal)
    if mod == "jelolo":
        core, _, unknown = tt.fill(text or "", view)
    else:
        core, unknown = text or "", []
    v = vf.verify(text or "", core, view.values, unknown, res, mod=mod)
    if not text:
        v.problemak.append("üres vagy nem értelmezhető válasz")
    kinds = [meres.classify(p) for p in v.problemak]
    return any(k != "ures" for k in kinds), kinds, view.text


def rescore(run: Run, qmap: dict, cat, wl, con, minimal: bool, own: bool) -> dict:
    """A futás modellszövegei a v4 kapujával. own=True: a v4 saját futása (önellenőrzés: egyeznie
    kell a tárolt ítélettel); own=False: a v3 futás szövegei (a nézet összevetése a v4 nézetével)."""
    out = {mod: {} for mod in AGAK}
    mismatch, view_diff = [], Counter()
    for qid, row in sorted(run.rows.items()):
        if qmap[qid].get("elutasitas") or not row["agak"]:
            continue
        g = gate_of(row, cat, wl)
        res = engine.run(g.spec, cat, wl, con, g.megjegyzesek)
        for mod in AGAK:
            t = row["agak"].get(mod)
            if not t or t["modell_szoveg"] is None:
                continue
            flag, kinds, view_text = v4_flag(t["modell_szoveg"], mod, res, minimal)
            stored = t["allitasok"] > 0
            out[mod][qid] = {"v4_kapu": flag, "sajat_kapu": stored, "fajtak": Counter(k for k in kinds if k != "ures")}
            if own and flag != stored:
                mismatch.append(f"{qid} {mod}: tárolt {stored}, újrapontozva {flag}")
            if own and t.get("nezet") is not None and t["nezet"] != view_text:
                view_diff[mod] += 1
            if not own and t.get("nezet") is not None:
                same_ph = set(_PH.findall(t["nezet"])) == set(_PH.findall(view_text))
                same = _PERIOD_LINE.sub("", view_text) == t["nezet"]
                view_diff[f"{mod}_mas_nezet"] += not same
                view_diff[f"{mod}_mas_jelolok"] += not same_ph
    return {"szovegek": out, "elteres": mismatch, "nezet": dict(view_diff)}


# ------------------------------------------------------------------ statisztika
def paired(a: dict[str, bool], b: dict[str, bool], boot: dict) -> dict:
    """Kérdésenként párosítva: a (v4) − b (v3), 95%-os bootstrap; négymezős tábla."""
    common = sorted(set(a) & set(b))
    diffs = [float(a[i]) - float(b[i]) for i in common]
    res = meres.bootstrap_mean(diffs, int(boot["B"]), int(boot["mag"]))
    return {"n": len(common), "v4": meres._rate(sum(a[i] for i in common), len(common)),
            "v3": meres._rate(sum(b[i] for i in common), len(common)),
            "kulonbseg": res[0] if res else None, "also": res[1] if res else None, "felso": res[2] if res else None,
            "mindketto": sum(a[i] and b[i] for i in common), "csak_v4": sum(a[i] and not b[i] for i in common),
            "csak_v3": sum(b[i] and not a[i] for i in common), "egyik_sem": sum(not a[i] and not b[i] for i in common)}


def compare(runs: dict[str, Run], questions: list[dict], protocol: dict, rescored: dict) -> dict:
    qmap = {q["id"]: q for q in questions}
    boot = protocol["statisztika"]["bootstrap"]
    ans = [q["id"] for q in questions if not q.get("elutasitas")]
    traps = [q["id"] for q in questions if q.get("elutasitas")]
    v4, v3 = runs["v4"].rows, runs["v3"].rows

    def pick(rows, ids, fn):
        return {i: fn(rows[i]) for i in ids if i in rows}

    out = {
        "fo": paired(pick(v4, ans, lambda r: r["itelet"] == "helyes"), pick(v3, ans, lambda r: r["itelet"] == "helyes"), boot),
        "F1": paired(pick(v4, ans, lambda r: bool(r["f1"])), pick(v3, ans, lambda r: bool(r["f1"])), boot),
        "F2": paired(pick(v4, traps, lambda r: r["elutasitva"]), pick(v3, traps, lambda r: r["elutasitva"]), boot),
        "F2_elvart_indok": paired(pick(v4, traps, lambda r: r["itelet"] == "helyes elutasítás"),
                                  pick(v3, traps, lambda r: r["itelet"] == "helyes elutasítás"), boot),
    }
    by_type: dict[str, dict] = defaultdict(lambda: {"n": 0, "v3": 0, "v4": 0})
    for qid in ans + traps:
        if qid in v4 and qid in v3:
            t = by_type[qmap[qid]["tipus"]]
            t["n"] += 1
            t["v3"] += v3[qid]["itelet"] in ("helyes", "helyes elutasítás")
            t["v4"] += v4[qid]["itelet"] in ("helyes", "helyes elutasítás")
    out["tipus_szerint"] = dict(sorted(by_type.items()))
    # K1 — a 4B két futása; a v3 szövegei a saját és a v4 kapujával
    k1 = {}
    for mod in AGAK:
        s4 = rescored["v4"]["szovegek"][mod]
        s3 = rescored["v3"]["szovegek"][mod]
        rec4 = {i: v4[i]["agak"][mod] for i in s4}
        rec3 = {i: v3[i]["agak"][mod] for i in s3}
        k1[mod] = {
            "v4_szoveg_v4_kapu": meres._rate(sum(x["v4_kapu"] for x in s4.values()), len(s4)),
            "v3_szoveg_v3_kapu": meres._rate(sum(x["sajat_kapu"] for x in s3.values()), len(s3)),
            "v3_szoveg_v4_kapu": meres._rate(sum(x["v4_kapu"] for x in s3.values()), len(s3)),
            "eljut_v4": meres._rate(sum(t["allitasok"] > 0 and not t["sablon"] for t in rec4.values()), len(rec4)),
            "eljut_v3": meres._rate(sum(t["allitasok"] > 0 and not t["sablon"] for t in rec3.values()), len(rec3)),
            "sablonra_valt_v4": meres._rate(sum(t["sablon"] for t in rec4.values()), len(rec4)),
            "sablonra_valt_v3": meres._rate(sum(t["sablon"] for t in rec3.values()), len(rec3)),
            "paros_v4_kapuval": paired({i: x["v4_kapu"] for i, x in s4.items()}, {i: x["v4_kapu"] for i, x in s3.items()},
                                      boot),
            "fajtak_v4": dict(sum((x["fajtak"] for x in s4.values()), Counter())),
            "fajtak_v3_v4_kapuval": dict(sum((x["fajtak"] for x in s3.values()), Counter())),
        }
    out["K1"] = k1
    out["kerdesenkent"] = [{"id": q["id"], "tipus": q["tipus"], "kerdes": q["kerdes"],
                            "v3": v3.get(q["id"], {}).get("itelet"), "v4": v4.get(q["id"], {}).get("itelet"),
                            "v3_elteres": v3.get(q["id"], {}).get("elteresek", []),
                            "v4_elteres": v4.get(q["id"], {}).get("elteresek", [])} for q in questions]
    return out


def describe_run(run: Run, questions: list[dict], protocol: dict) -> dict:
    """Egy futás saját összegzése (a mérőprogram számolásával) — a 2B-hez és az időkhöz."""
    rows = list(run.rows.values())
    return meres.summarize(rows, questions, protocol)


# ------------------------------------------------------------------ jelentés
def _pp(x) -> str:
    return "—" if x is None else ("+" if x > 0 else "") + meres.nv.fmt_num(100 * x, 1) + " pp"


def _r(r: dict) -> str:
    return meres._rate_text(r) if r["n"] else "—"


def _paired_row(name: str, p: dict) -> str:
    return (f"| {name} | {p['n']} | {_r(p['v3'])} | {_r(p['v4'])} | **{_pp(p['kulonbseg'])}** "
            f"({_pp(p['also'])} – {_pp(p['felso'])}) | {p['mindketto']} / {p['csak_v4']} / {p['csak_v3']} / {p['egyik_sem']} |")


def _sec(ms) -> str:
    return "—" if ms is None else meres.nv.fmt_num(ms / 1000.0, 1) + " mp"


def report_md(res: dict, runs: dict[str, Run], protocol: dict, p_sha: str, checks: dict, extra: dict) -> str:
    boot = protocol["statisztika"]["bootstrap"]
    L = ["# K1 mérés v2 — a v3 és a v4 nyelvi réteg ugyanazon a kérdéssoron", "",
         f"Géppel készült (`tools/k1_v2_osszevetes.py`), a futások mappáiból, modell nélkül. Protokoll: "
         f"`docs/k1_protokoll_v2.json` (SHA256 `{p_sha[:16]}…`, jóváhagyta: "
         f"{(protocol.get('jovahagyas') or {}).get('ki', '—')}, {(protocol.get('jovahagyas') or {}).get('mikor', '—')}); "
         f"kérdéssor: `{protocol['kerdessor']['fajl']}` (SHA256 `{protocol['kerdessor']['sha256'][:16]}…`, "
         f"{protocol['kerdessor']['kerdesek']} kérdés: {protocol['kerdessor']['megvalaszolando']} megválaszolandó, "
         f"{protocol['kerdessor']['csapda']} csapda).", "", "## Futások", "",
         "| futás | mappa | kezdés | modell | kód (commit · ujjlenyomat) |", "|---|---|---|---|---|"]
    for run in runs.values():
        h = run.head
        L.append(f"| {run.label} | `{run.path.name}` | {h.get('kezdes', '—')} | {run.model} (`{str(h.get('digest'))[:12]}`) | "
                 f"`{str(h['kod'].get('commit'))[:7]}` · `{str(h['kod'].get('ujjlenyomat'))[:16]}` |")
    L += ["", "Ellenőrzés: " + ("minden futás a jóváhagyott protokoll szerint ment (kérdéssor, kód, modell, ismétlés)."
                                if not checks["hibak"] else "**HIBA** — " + "; ".join(checks["hibak"]))]
    for w in checks["figyelmeztetesek"]:
        L.append(f"- figyelmeztetés: {w}")
    L.append(f"- a tárolt ítéletek újraszámolva: "
             + ("mind egyezik." if not checks["ujraszamolas"] else f"**{len(checks['ujraszamolas'])} eltérés** — "
                + "; ".join(checks["ujraszamolas"][:10])))
    L.append(f"- az újrapontozás önellenőrzése (a v4 futás saját szövegei a v4 kapujával): "
             + ("mind egyezik a tárolt ítélettel." if not checks["onellenorzes"] else
                f"**{len(checks['onellenorzes'])} eltérés** — " + "; ".join(checks["onellenorzes"][:10])))
    nz = checks.get("v3_nezet", {})
    if nz:
        L.append("- a v3 szövegeinek nézete a v4-ével összevetve (az időszak-sor nélkül): "
                 + ", ".join(f"{k}: {v}" for k, v in sorted(nz.items())))
    fo = res["fo"]
    L += ["", "## Fő mutató: helyes válasz a feltett kérdésre (4B)", "",
          f"Teljes egyezés (mérőszám, bontás, szűrő, időablak, rendezés) a megválaszolandó kérdéseken, kérdésenként "
          f"párosítva; a különbség 95%-os intervalluma bootstrap a kérdések újramintavételével (B = {boot['B']}, "
          f"mag {boot['mag']}). A négy szám: mindkettő helyes / csak a v4 / csak a v3 / egyik sem.", "",
          "| mutató | kérdés | v3 | v4 | v4 − v3 (95%) | ✓✓ / csak v4 / csak v3 / ✗✗ |", "|---|---|---|---|---|---|",
          _paired_row("**teljes egyezés**", fo), _paired_row("F-1 (mérőszám és bontás)", res["F1"]),
          _paired_row("F-2 (a csapdát elutasítja)", res["F2"]),
          _paired_row("F-2, az elvárt indokkal", res["F2_elvart_indok"]), "",
          "### Kérdéstípusonként (helyes értelmezés / helyes elutasítás)", "", "| típus | kérdés | v3 | v4 |", "|---|---|---|---|"]
    for t, v in res["tipus_szerint"].items():
        L.append(f"| {t} | {v['n']} | {v['v3']} | {v['v4']} |")
    L += ["", "## K1: alá nem támasztott állítás a modell szövegében (4B, megválaszolandó kérdések)", "",
          "A v3 szövegei a saját (v3) kapujukkal, és a v4 kapujával újrapontozva — az utóbbi a két kód szövegeit "
          "ugyanazzal a mércével méri. „Eljut”: a megjelölt szöveg a felhasználóhoz kerül (a fő ágon a megjelölt "
          "szöveg helyett sablon megy ki).", "",
          "| ág | v3 szöveg, v3 kapu | v3 szöveg, v4 kapu | v4 szöveg, v4 kapu | v4 − v3 (v4 kapuval, párosítva) | eljut: v3 / v4 | sablonra vált: v3 / v4 |",
          "|---|---|---|---|---|---|---|"]
    for mod in AGAK:
        k = res["K1"][mod]
        p = k["paros_v4_kapuval"]
        L.append(f"| {meres.AG_NEV[mod]} | {_r(k['v3_szoveg_v3_kapu'])} | {_r(k['v3_szoveg_v4_kapu'])} | {_r(k['v4_szoveg_v4_kapu'])} | "
                 f"{_pp(p['kulonbseg'])} ({_pp(p['also'])} – {_pp(p['felso'])}; {p['n']} kérdés) | "
                 f"{meres._pct(k['eljut_v3']['arany'])} / {meres._pct(k['eljut_v4']['arany'])} | "
                 f"{meres._pct(k['sablonra_valt_v3']['arany'])} / {meres._pct(k['sablonra_valt_v4']['arany'])} |")
    L += ["", "A megjelölések fajtái (a v4 kapujával): " + "; ".join(
        f"{meres.AG_NEV[mod]} — v3: {_kinds(res['K1'][mod]['fajtak_v3_v4_kapuval'])}, v4: {_kinds(res['K1'][mod]['fajtak_v4'])}"
        for mod in AGAK)]
    if extra.get("v4-2b"):
        s = extra["v4-2b"]
        L += ["", "## A 2B a v4-gyel (leíró)", "", "| mutató | eredmény |", "|---|---|",
              f"| teljes egyezés | {_r(s['teljes_egyezes'])} |", f"| F-1 | {_r(s['F1'])} |", f"| F-2 | {_r(s['F2'])} |"]
        for mod in AGAK:
            L.append(f"| K1, {meres.AG_NEV[mod]}: megjelölt / eljut | {_r(s['K1'][mod]['fo'])} / "
                     f"{meres._pct(s['K1'][mod]['eljut']['arany'])} |")
    L += ["", "## Idő (medián)", "", "| futás | ① (értelmezés) | ② fő ág | ② kontrollág | összesen |", "|---|---|---|---|---|"]
    for key, run in runs.items():
        t = extra["osszegzes"][key]["ido"]
        L.append(f"| {run.label} | {_sec(t.get('ido1_median_ms'))} | {_sec(t.get('ido2_jelolo_median_ms'))} | "
                 f"{_sec(t.get('ido2_szabad_median_ms'))} | {meres.nv.fmt_num(t['osszes_ms'] / 60000.0, 0)} perc |")
    L += ["", "## Kérdésenként (4B)", "",
          "✓ helyes (vagy helyes elutasítás) · ✗ hibás értelmezés · ⊘ téves elutasítás · ! hiányzó elutasítás · "
          "≈ más indokú elutasítás", "", "| # | típus | kérdés | v3 | v4 | a v4 eltérése az elvárttól |", "|---|---|---|---|---|---|"]
    for row in res["kerdesenkent"]:
        change = ""
        if row["v3"] and row["v4"]:
            ok3, ok4 = JEL[row["v3"]] == "✓", JEL[row["v4"]] == "✓"
            change = " ↑" if ok4 and not ok3 else (" ↓" if ok3 and not ok4 else "")
        q = row["kerdes"] if len(row["kerdes"]) <= 70 else row["kerdes"][:68] + "…"
        L.append(f"| {row['id']} | {row['tipus']} | {q.replace('|', '/')} | {JEL[row['v3']]} | {JEL[row['v4']]}{change} | "
                 f"{'; '.join(row['v4_elteres'])[:160].replace('|', '/')} |")
    return "\n".join(L) + "\n"


def _kinds(c: dict) -> str:
    return ", ".join(f"{meres.FAJTA_NEV.get(k, k)} {n}" for k, n in sorted(c.items(), key=lambda x: -x[1])) or "nincs"


# ------------------------------------------------------------------ parancs
def run(v4: Path, v3: Path, v4_2b: Path | None = None, protokoll: Path = PROTOKOLL, kimenet: Path = KIMENET,
        db_path: Path | None = None) -> dict:
    protocol, p_sha = meres.load_protocol(protokoll)
    questions = proba.load_questions(meres.question_file(protocol, protokoll.parent.parent))
    if meres.sha256_text(meres.question_file(protocol, protokoll.parent.parent)) != protocol["kerdessor"].get("sha256"):
        raise SystemExit("A kérdéssor nem az, amit a protokoll lezárt (az ujjlenyomat nem egyezik).")
    qmap = {q["id"]: q for q in questions}
    runs = {"v4": Run(v4, "v4 · 4B"), "v3": Run(v3, "v3 · 4B")}
    if v4_2b:
        runs["v4-2b"] = Run(v4_2b, "v4 · 2B")
    err, warn = check_runs(runs, protocol, p_sha, questions)
    pinned = (protocol.get("elemzes") or {}).get("sha256")
    mine = meres.sha256_text(Path(__file__))
    if pinned and pinned != mine:
        warn.append(f"az összevető eszköz a protokoll jóváhagyása óta megváltozott ({mine[:16]} ≠ {pinned[:16]}) — "
                    "az eltérést a dolgozatban jelezni kell")
    if err:
        raise SystemExit("Az összevetés nem készül el:\n  " + "\n  ".join(err))
    cat = catalog.load()
    con = connect(db_path or DB_PATH, read_only=True)
    wl = catalog.whitelist(cat, con)
    cfg = load_config()
    minimal = tt.minimal_view(cfg.hivasok["to_text"].version)
    rejudged = rejudge(runs, qmap, cat, wl, con)
    rescored = {"v4": rescore(runs["v4"], qmap, cat, wl, con, minimal, own=True),
                "v3": rescore(runs["v3"], qmap, cat, wl, con, minimal, own=False)}
    con.close()
    res = compare(runs, questions, protocol, rescored)
    extra = {"osszegzes": {k: describe_run(r, questions, protocol) for k, r in runs.items()}}
    if "v4-2b" in runs:
        extra["v4-2b"] = extra["osszegzes"]["v4-2b"]
    checks = {"hibak": err, "figyelmeztetesek": warn, "ujraszamolas": rejudged,
              "onellenorzes": rescored["v4"]["elteres"], "v3_nezet": rescored["v3"]["nezet"],
              "v4_nezet_elter": rescored["v4"]["nezet"]}
    kimenet.parent.mkdir(parents=True, exist_ok=True)
    kimenet.write_text(report_md(res, runs, protocol, p_sha, checks, extra), encoding="utf-8")
    payload = {"protokoll": {"fajl": str(protokoll.name), "sha256": p_sha},
               "futasok": {k: {"mappa": r.path.name, **r.head} for k, r in runs.items()},
               "ellenorzes": checks, "eredmeny": res,
               "osszegzes": extra["osszegzes"]}
    kimenet.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str),
                                            encoding="utf-8")
    return {"eredmeny": res, "ellenorzes": checks}


def main(argv: list[str] | None = None) -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="A K1 v2 összevetése: v3 és v4, kérdésenként párosítva.")
    ap.add_argument("--v4", type=Path, required=True, help="a v4 4B futás mappája (logs/meres/…)")
    ap.add_argument("--v3", type=Path, required=True, help="a v3 4B futás mappája (v3_kod/logs/meres/…)")
    ap.add_argument("--v4-2b", type=Path, dest="v4_2b", help="a v4 2B futás mappája (leíró)")
    ap.add_argument("--protokoll", type=Path, default=PROTOKOLL)
    ap.add_argument("--kimenet", type=Path, default=KIMENET, help="a jelentés (.md; mellé .json)")
    a = ap.parse_args(argv)
    out = run(a.v4, a.v3, a.v4_2b, a.protokoll, a.kimenet)
    fo = out["eredmeny"]["fo"]
    c = out["ellenorzes"]
    print(f"Teljes egyezés (4B, {fo['n']} kérdés): v3 {meres._pct(fo['v3']['arany'])} → v4 {meres._pct(fo['v4']['arany'])}, "
          f"különbség {_pp(fo['kulonbseg'])} (95%: {_pp(fo['also'])} – {_pp(fo['felso'])})")
    print(f"Ellenőrzés: újraszámolt ítélet eltérése {len(c['ujraszamolas'])}, önellenőrzés eltérése {len(c['onellenorzes'])}")
    print(f"Jelentés: {a.kimenet}")


if __name__ == "__main__":
    main()
