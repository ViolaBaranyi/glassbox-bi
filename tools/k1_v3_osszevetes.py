"""
A K1 mérés v3-ának összevetése (docs/k1_protokoll_v3.json, „mutatok” és „statisztika”): a v4 és a
v5 nyelvi réteg ugyanazon a lezárt kérdéssoron, kérdésenként párosítva — modell nélkül, a futások
mappáiból.

    uv run python tools/k1_v3_osszevetes.py --v5 logs\\meres\\MAPPA --v4 v4_kod\\logs\\meres\\MAPPA
                                            [--v5-9b logs\\meres\\MAPPA]

Kimenet: docs/k1_v3_eredmeny.md és .json (más hely: --kimenet ÚTVONAL.md).

Az eszköz az eredmények ELŐTT készült (2026-10-22, a kérdéssor lezárása előtt): az elemzés módja így
nem igazodhat a számokhoz. A nyelvi réteg kódját nem érinti (a tools/ nincs a kód ujjlenyomatában).
A v2 eszközének (tools/k1_v2_osszevetes.py) betöltését, újraszámolását és újrapontozását használja.

Mit számol
  * Fő mutató: teljes egyezés (mérőszám, bontás, szűrő, időablak, rendezés) a megválaszolandó
    kérdéseken, a v5 és a v4 különbsége a 4B-vel, kérdésenként párosítva; 95%-os bootstrap a
    kérdések újramintavételével (B és mag a protokollból). Mellé a négymezős tábla.
  * F-1 és F-2 (bármilyen és az elvárt indokú elutasítás) a két kódnál, ugyanígy párosítva;
    kérdéstípusonként és szerepkártyánként a helyes értelmezés / helyes elutasítás.
  * A kód tiszta hatása: a v4 és a v5 promptja azonos, ezért kérdésenként megnézi, ugyanazt a nyers
    űrlapot adta-e a modell a két futásban; ahol igen, ott az ítélet különbsége csak a kódé.
  * K1: a v5 futás szövegei a v5 kapujával (önellenőrzés: a tárolt ítéletet kell visszakapnia); a v4
    futás szövegei a saját (v4) kapujukkal ÉS a v5 kapujával — így a két kód szövegei ugyanazzal a
    mércével is összevethetők; a felhasználóhoz jutó megjelölt szöveg, a sablonra váltás.
  * A 9B a v5-tel (leíró, ha fut), és az idők mediánja.

Mielőtt számol, ellenőriz: jóváhagyott-e a protokoll; minden futás a lezárt kérdéssoron, a megadott
modellel, egy ismétléssel ment-e; a v5 futások a jóváhagyott protokollal és a v5 kódjával, a v4 futás
a protokoll v4-es változatával (tools/v4_protokoll.py: csak a kód-ujjlenyomat más) és a v4 kódjával;
és a tárolt ítéletek újraszámolva ugyanazok-e. A protokoll („elemzes”) rögzíti ennek a fájlnak az
ujjlenyomatát; ha az eszköz utána változik, a jelentés figyelmeztet.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.db import DB_PATH, connect, use_utf8_console  # noqa: E402
from narrative import meres, proba  # noqa: E402
from narrative import to_text as tt  # noqa: E402
from narrative.client import load_config  # noqa: E402
from semantic import catalog  # noqa: E402


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


v2 = _load("k1_v2_osszevetes")
v4p = _load("v4_protokoll")

PROTOKOLL = ROOT / "docs" / "k1_protokoll_v3.json"
KIMENET = ROOT / "docs" / "k1_v3_eredmeny.md"
AGAK = meres.AGAK
JEL = v2.JEL
OK = ("helyes", "helyes elutasítás")


# ------------------------------------------------------------------ ellenőrzés
def check_runs(runs: dict, protocol: dict, p_sha: str, questions: list[dict]) -> tuple[list[str], list[str]]:
    """(hibák, figyelmeztetések). Hiba: a futás nem a protokoll szerinti — az összevetés nem készül el."""
    err, warn = [], []
    if protocol.get("allapot") != "jovahagyva":
        err.append(f"a protokoll állapota „{protocol.get('allapot')}”, nem „jovahagyva”")
    want_q = protocol["kerdessor"]["sha256"]
    fps = {"v5": protocol["kod"]["ujjlenyomat"], "v4": protocol["kod"]["v4"]["ujjlenyomat"]}
    p_shas = {"v5": p_sha, "v4": v4p.sha256(protocol)}
    models = {m["nev"] for m in protocol["modellek"]}
    reps = int(protocol["beallitasok"]["ismetles"])
    ids = {q["id"] for q in questions}
    for key, run in runs.items():
        code = key.split("-")[0]
        h, name = run.head, f"{run.label} ({run.path.name})"
        if h["kerdessor"]["sha256"] != want_q:
            err.append(f"{name}: más kérdéssoron futott ({h['kerdessor']['sha256'][:16]} ≠ {want_q[:16]})")
        got_p = str(h.get("protokoll", {}).get("sha256"))
        if got_p != p_shas[code]:
            err.append(f"{name}: a fejlécben más protokoll ujjlenyomata áll ({got_p[:16]} ≠ {p_shas[code][:16]}) — "
                       + ("a jóváhagyott protokollal kell futnia" if code == "v5" else
                          "a protokoll v4-es változatával kell futnia (tools/v4_futtatas.bat)"))
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
    if runs["v5"].model != runs["v4"].model:
        err.append(f"a v5 és a v4 futás más modellel ment ({runs['v5'].model} ≠ {runs['v4'].model})")
    elif runs["v5"].head.get("digest") != runs["v4"].head.get("digest"):
        warn.append("a v5 és a v4 futás modelljének lenyomata (digest) eltér — ugyanaz a név, de más modellfájl")
    return err, warn


# ------------------------------------------------------------------ statisztika
def paired(a: dict[str, bool], b: dict[str, bool], boot: dict) -> dict:
    """Kérdésenként párosítva: a (v5) − b (v4), 95%-os bootstrap; négymezős tábla."""
    common = sorted(set(a) & set(b))
    diffs = [float(a[i]) - float(b[i]) for i in common]
    res = meres.bootstrap_mean(diffs, int(boot["B"]), int(boot["mag"]))
    return {"n": len(common), "v5": meres._rate(sum(a[i] for i in common), len(common)),
            "v4": meres._rate(sum(b[i] for i in common), len(common)),
            "kulonbseg": res[0] if res else None, "also": res[1] if res else None, "felso": res[2] if res else None,
            "mindketto": sum(a[i] and b[i] for i in common), "csak_v5": sum(a[i] and not b[i] for i in common),
            "csak_v4": sum(b[i] and not a[i] for i in common), "egyik_sem": sum(not a[i] and not b[i] for i in common)}


def _form_key(row: dict) -> str | None:
    return None if row.get("urlap") is None else json.dumps(row["urlap"], sort_keys=True, ensure_ascii=False)


def compare(runs: dict, questions: list[dict], protocol: dict, rescored: dict) -> dict:
    qmap = {q["id"]: q for q in questions}
    boot = protocol["statisztika"]["bootstrap"]
    ans = [q["id"] for q in questions if not q.get("elutasitas")]
    traps = [q["id"] for q in questions if q.get("elutasitas")]
    v5, v4 = runs["v5"].rows, runs["v4"].rows

    def pick(rows, ids, fn):
        return {i: fn(rows[i]) for i in ids if i in rows}

    out = {
        "fo": paired(pick(v5, ans, lambda r: r["itelet"] == "helyes"), pick(v4, ans, lambda r: r["itelet"] == "helyes"), boot),
        "F1": paired(pick(v5, ans, lambda r: bool(r["f1"])), pick(v4, ans, lambda r: bool(r["f1"])), boot),
        "F2": paired(pick(v5, traps, lambda r: r["elutasitva"]), pick(v4, traps, lambda r: r["elutasitva"]), boot),
        "F2_elvart_indok": paired(pick(v5, traps, lambda r: r["itelet"] == "helyes elutasítás"),
                                  pick(v4, traps, lambda r: r["itelet"] == "helyes elutasítás"), boot),
    }
    for field, name in (("tipus", "tipus_szerint"), ("szerep", "szerep_szerint")):
        groups: dict[str, dict] = defaultdict(lambda: {"n": 0, "v4": 0, "v5": 0})
        for qid in ans + traps:
            if qid in v5 and qid in v4:
                g = groups[qmap[qid].get(field) or "—"]
                g["n"] += 1
                g["v4"] += v4[qid]["itelet"] in OK
                g["v5"] += v5[qid]["itelet"] in OK
        out[name] = dict(sorted(groups.items()))
    # a kód tiszta hatása: ugyanaz a nyers űrlap a két futásban (a prompt azonos)
    same = {"kerdes": 0, "azonos_urlap": 0, "azonos_urlap_javult": 0, "azonos_urlap_romlott": 0,
            "mas_urlap": 0, "mas_urlap_javult": 0, "mas_urlap_romlott": 0, "javito_kor_v5": 0, "javito_kor_v4": 0}
    for qid in ans + traps:
        if qid not in v5 or qid not in v4:
            continue
        a, b = v5[qid], v4[qid]
        same["kerdes"] += 1
        same["javito_kor_v5"] += bool(a.get("javito_kor"))
        same["javito_kor_v4"] += bool(b.get("javito_kor"))
        tag = "azonos_urlap" if _form_key(a) == _form_key(b) and not a.get("javito_kor") and not b.get("javito_kor") \
            else "mas_urlap"
        same[tag] += 1
        ok5, ok4 = a["itelet"] in OK, b["itelet"] in OK
        same[f"{tag}_javult"] += ok5 and not ok4
        same[f"{tag}_romlott"] += ok4 and not ok5
    out["kod_hatasa"] = same
    # K1 — a 4B két futása; a v4 szövegei a saját és a v5 kapujával
    k1 = {}
    for mod in AGAK:
        s5 = rescored["v5"]["szovegek"][mod]
        s4 = rescored["v4"]["szovegek"][mod]
        rec5 = {i: v5[i]["agak"][mod] for i in s5}
        rec4 = {i: v4[i]["agak"][mod] for i in s4}
        k1[mod] = {
            "v5_szoveg_v5_kapu": meres._rate(sum(x["v4_kapu"] for x in s5.values()), len(s5)),
            "v4_szoveg_v4_kapu": meres._rate(sum(x["sajat_kapu"] for x in s4.values()), len(s4)),
            "v4_szoveg_v5_kapu": meres._rate(sum(x["v4_kapu"] for x in s4.values()), len(s4)),
            "eljut_v5": meres._rate(sum(t["allitasok"] > 0 and not t["sablon"] for t in rec5.values()), len(rec5)),
            "eljut_v4": meres._rate(sum(t["allitasok"] > 0 and not t["sablon"] for t in rec4.values()), len(rec4)),
            "sablonra_valt_v5": meres._rate(sum(t["sablon"] for t in rec5.values()), len(rec5)),
            "sablonra_valt_v4": meres._rate(sum(t["sablon"] for t in rec4.values()), len(rec4)),
            "paros_v5_kapuval": paired({i: x["v4_kapu"] for i, x in s5.items()}, {i: x["v4_kapu"] for i, x in s4.items()},
                                      boot),
            "fajtak_v5": dict(sum((x["fajtak"] for x in s5.values()), Counter())),
            "fajtak_v4_v5_kapuval": dict(sum((x["fajtak"] for x in s4.values()), Counter())),
        }
    out["K1"] = k1
    out["kerdesenkent"] = [{"id": q["id"], "tipus": q["tipus"], "szerep": q.get("szerep"), "kerdes": q["kerdes"],
                            "v4": v4.get(q["id"], {}).get("itelet"), "v5": v5.get(q["id"], {}).get("itelet"),
                            "azonos_urlap": (q["id"] in v4 and q["id"] in v5 and _form_key(v4[q["id"]]) == _form_key(v5[q["id"]])),
                            "v4_elteres": v4.get(q["id"], {}).get("elteresek", []),
                            "v5_elteres": v5.get(q["id"], {}).get("elteresek", [])} for q in questions]
    return out


# ------------------------------------------------------------------ jelentés
_pp, _r, _sec, _kinds = v2._pp, v2._r, v2._sec, v2._kinds


def _paired_row(name: str, p: dict) -> str:
    return (f"| {name} | {p['n']} | {_r(p['v4'])} | {_r(p['v5'])} | **{_pp(p['kulonbseg'])}** "
            f"({_pp(p['also'])} – {_pp(p['felso'])}) | {p['mindketto']} / {p['csak_v5']} / {p['csak_v4']} / {p['egyik_sem']} |")


def report_md(res: dict, runs: dict, protocol: dict, p_sha: str, checks: dict, extra: dict) -> str:
    boot = protocol["statisztika"]["bootstrap"]
    ks = protocol["kerdessor"]
    L = ["# K1 mérés v3 — a v4 és a v5 nyelvi réteg ugyanazon a kérdéssoron", "",
         f"Géppel készült (`tools/k1_v3_osszevetes.py`), a futások mappáiból, modell nélkül. Protokoll: "
         f"`docs/k1_protokoll_v3.json` (SHA256 `{p_sha[:16]}…`, jóváhagyta: "
         f"{(protocol.get('jovahagyas') or {}).get('ki', '—')}, {(protocol.get('jovahagyas') or {}).get('mikor', '—')}); "
         f"kérdéssor: `{ks['fajl']}` (SHA256 `{ks['sha256'][:16]}…`, {ks['kerdesek']} kérdés: {ks['megvalaszolando']} "
         f"megválaszolandó, {ks['csapda']} csapda; Viola kérdései, a v5 lezárása után).", "", "## Futások", "",
         "| futás | mappa | kezdés | modell | kód (commit · ujjlenyomat) |", "|---|---|---|---|---|"]
    for run in runs.values():
        h = run.head
        L.append(f"| {run.label} | `{run.path.name}` | {h.get('kezdes', '—')} | {run.model} (`{str(h.get('digest'))[:12]}`) | "
                 f"`{str(h['kod'].get('commit'))[:7]}` · `{str(h['kod'].get('ujjlenyomat'))[:16]}` |")
    L += ["", "Ellenőrzés: " + ("minden futás a jóváhagyott protokoll szerint ment (kérdéssor, kód, modell, ismétlés)."
                                if not checks["hibak"] else "**HIBA** — " + "; ".join(checks["hibak"]))]
    for w in checks["figyelmeztetesek"]:
        L.append(f"- figyelmeztetés: {w}")
    L.append("- a tárolt ítéletek újraszámolva: "
             + ("mind egyezik." if not checks["ujraszamolas"] else f"**{len(checks['ujraszamolas'])} eltérés** — "
                + "; ".join(checks["ujraszamolas"][:10])))
    L.append("- az újrapontozás önellenőrzése (a v5 futás saját szövegei a v5 kapujával): "
             + ("mind egyezik a tárolt ítélettel." if not checks["onellenorzes"] else
                f"**{len(checks['onellenorzes'])} eltérés** — " + "; ".join(checks["onellenorzes"][:10])))
    nz = checks.get("v4_nezet", {})
    if nz:
        L.append("- a v4 szövegeinek nézete a v5-ével összevetve (az időszak-sor nélkül): "
                 + ", ".join(f"{k}: {v}" for k, v in sorted(nz.items())))
    fo = res["fo"]
    L += ["", "## Fő mutató: helyes válasz a feltett kérdésre (4B)", "",
          f"Teljes egyezés (mérőszám, bontás, szűrő, időablak, rendezés) a megválaszolandó kérdéseken, kérdésenként "
          f"párosítva; a különbség 95%-os intervalluma bootstrap a kérdések újramintavételével (B = {boot['B']}, "
          f"mag {boot['mag']}). A négy szám: mindkettő helyes / csak a v5 / csak a v4 / egyik sem.", "",
          "| mutató | kérdés | v4 | v5 | v5 − v4 (95%) | ✓✓ / csak v5 / csak v4 / ✗✗ |", "|---|---|---|---|---|---|",
          _paired_row("**teljes egyezés**", fo), _paired_row("F-1 (mérőszám és bontás)", res["F1"]),
          _paired_row("F-2 (a csapdát elutasítja)", res["F2"]),
          _paired_row("F-2, az elvárt indokkal", res["F2_elvart_indok"])]
    c = res["kod_hatasa"]
    L += ["", "### A kód tiszta hatása", "",
          f"A v4 és a v5 promptja azonos. {c['kerdes']} kérdésből {c['azonos_urlap']}-nél ugyanazt a nyers űrlapot adta a "
          f"modell a két futásban (javító kör nélkül): itt az ítélet különbsége csak a kódé — javult {c['azonos_urlap_javult']}, "
          f"romlott {c['azonos_urlap_romlott']}. A többi {c['mas_urlap']} kérdésnél a modell válasza is más volt (a gép "
          f"számolási eltérése, ill. javító kör: v5 {c['javito_kor_v5']}, v4 {c['javito_kor_v4']}) — javult "
          f"{c['mas_urlap_javult']}, romlott {c['mas_urlap_romlott']}."]
    for field, title in (("tipus_szerint", "Kérdéstípusonként"), ("szerep_szerint", "Szerepkártyánként")):
        L += ["", f"### {title} (helyes értelmezés / helyes elutasítás)", "", "| | kérdés | v4 | v5 |", "|---|---|---|---|"]
        for t, v in res[field].items():
            L.append(f"| {t} | {v['n']} | {v['v4']} | {v['v5']} |")
    L += ["", "## K1: alá nem támasztott állítás a modell szövegében (4B, megválaszolandó kérdések)", "",
          "A v4 szövegei a saját (v4) kapujukkal, és a v5 kapujával újrapontozva — az utóbbi a két kód szövegeit "
          "ugyanazzal a mércével méri. „Eljut”: a megjelölt szöveg a felhasználóhoz kerül (a fő ágon a megjelölt "
          "szöveg helyett sablon megy ki).", "",
          "| ág | v4 szöveg, v4 kapu | v4 szöveg, v5 kapu | v5 szöveg, v5 kapu | v5 − v4 (v5 kapuval, párosítva) | eljut: v4 / v5 | sablonra vált: v4 / v5 |",
          "|---|---|---|---|---|---|---|"]
    for mod in AGAK:
        k = res["K1"][mod]
        p = k["paros_v5_kapuval"]
        L.append(f"| {meres.AG_NEV[mod]} | {_r(k['v4_szoveg_v4_kapu'])} | {_r(k['v4_szoveg_v5_kapu'])} | {_r(k['v5_szoveg_v5_kapu'])} | "
                 f"{_pp(p['kulonbseg'])} ({_pp(p['also'])} – {_pp(p['felso'])}; {p['n']} kérdés) | "
                 f"{meres._pct(k['eljut_v4']['arany'])} / {meres._pct(k['eljut_v5']['arany'])} | "
                 f"{meres._pct(k['sablonra_valt_v4']['arany'])} / {meres._pct(k['sablonra_valt_v5']['arany'])} |")
    L += ["", "A megjelölések fajtái (a v5 kapujával): " + "; ".join(
        f"{meres.AG_NEV[mod]} — v4: {_kinds(res['K1'][mod]['fajtak_v4_v5_kapuval'])}, v5: {_kinds(res['K1'][mod]['fajtak_v5'])}"
        for mod in AGAK)]
    if extra.get("v5-9b"):
        s = extra["v5-9b"]
        L += ["", "## A 9B a v5-tel (leíró)", "", "| mutató | eredmény |", "|---|---|",
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
          "≈ más indokú elutasítás · = a modell nyers űrlapja a két futásban azonos", "",
          "| # | típus | kérdés | v4 | v5 | a v5 eltérése az elvárttól |", "|---|---|---|---|---|---|"]
    for row in res["kerdesenkent"]:
        change = ""
        if row["v4"] and row["v5"]:
            ok4, ok5 = JEL[row["v4"]] == "✓", JEL[row["v5"]] == "✓"
            change = " ↑" if ok5 and not ok4 else (" ↓" if ok4 and not ok5 else "")
        q = row["kerdes"] if len(row["kerdes"]) <= 70 else row["kerdes"][:68] + "…"
        L.append(f"| {row['id']}{' =' if row['azonos_urlap'] else ''} | {row['tipus']} | {q.replace('|', '/')} | "
                 f"{JEL[row['v4']]} | {JEL[row['v5']]}{change} | {'; '.join(row['v5_elteres'])[:160].replace('|', '/')} |")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ parancs
def run(v5: Path, v4: Path, v5_9b: Path | None = None, protokoll: Path = PROTOKOLL, kimenet: Path = KIMENET,
        db_path: Path | None = None) -> dict:
    protocol, p_sha = meres.load_protocol(protokoll)
    qfile = meres.question_file(protocol, protokoll.parent.parent)
    questions = proba.load_questions(qfile)
    if meres.sha256_text(qfile) != protocol["kerdessor"].get("sha256"):
        raise SystemExit("A kérdéssor nem az, amit a protokoll lezárt (az ujjlenyomat nem egyezik).")
    qmap = {q["id"]: q for q in questions}
    runs = {"v5": v2.Run(v5, "v5 · 4B"), "v4": v2.Run(v4, "v4 · 4B")}
    if v5_9b:
        runs["v5-9b"] = v2.Run(v5_9b, "v5 · 9B")
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
    rejudged = v2.rejudge(runs, qmap, cat, wl, con)
    rescored = {"v5": v2.rescore(runs["v5"], qmap, cat, wl, con, minimal, own=True),
                "v4": v2.rescore(runs["v4"], qmap, cat, wl, con, minimal, own=False)}
    con.close()
    res = compare(runs, questions, protocol, rescored)
    extra = {"osszegzes": {k: v2.describe_run(r, questions, protocol) for k, r in runs.items()}}
    if "v5-9b" in runs:
        extra["v5-9b"] = extra["osszegzes"]["v5-9b"]
    checks = {"hibak": err, "figyelmeztetesek": warn, "ujraszamolas": rejudged,
              "onellenorzes": rescored["v5"]["elteres"], "v4_nezet": rescored["v4"]["nezet"],
              "v5_nezet_elter": rescored["v5"]["nezet"]}
    kimenet.parent.mkdir(parents=True, exist_ok=True)
    kimenet.write_text(report_md(res, runs, protocol, p_sha, checks, extra), encoding="utf-8")
    payload = {"protokoll": {"fajl": str(protokoll.name), "sha256": p_sha},
               "futasok": {k: {"mappa": r.path.name, **r.head} for k, r in runs.items()},
               "ellenorzes": checks, "eredmeny": res, "osszegzes": extra["osszegzes"]}
    kimenet.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str),
                                            encoding="utf-8")
    return {"eredmeny": res, "ellenorzes": checks}


def main(argv: list[str] | None = None) -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="A K1 v3 összevetése: v4 és v5, kérdésenként párosítva.")
    ap.add_argument("--v5", type=Path, required=True, help="a v5 4B futás mappája (logs/meres/…)")
    ap.add_argument("--v4", type=Path, required=True, help="a v4 4B futás mappája (v4_kod/logs/meres/…)")
    ap.add_argument("--v5-9b", type=Path, dest="v5_9b", help="a v5 9B futás mappája (leíró)")
    ap.add_argument("--protokoll", type=Path, default=PROTOKOLL)
    ap.add_argument("--kimenet", type=Path, default=KIMENET, help="a jelentés (.md; mellé .json)")
    a = ap.parse_args(argv)
    out = run(a.v5, a.v4, a.v5_9b, a.protokoll, a.kimenet)
    fo = out["eredmeny"]["fo"]
    c = out["ellenorzes"]
    print(f"Teljes egyezés (4B, {fo['n']} kérdés): v4 {meres._pct(fo['v4']['arany'])} → v5 {meres._pct(fo['v5']['arany'])}, "
          f"különbség {_pp(fo['kulonbseg'])} (95%: {_pp(fo['also'])} – {_pp(fo['felso'])})")
    print(f"Ellenőrzés: újraszámolt ítélet eltérése {len(c['ujraszamolas'])}, önellenőrzés eltérése {len(c['onellenorzes'])}")
    print(f"Jelentés: {a.kimenet}")


if __name__ == "__main__":
    main()
