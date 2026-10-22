"""
Két mérőfutás összevetése ugyanazon a lezárt kérdéssoron, ugyanazzal a nyelvi réteggel (kód) —
kérdésenként párosítva, modell nélkül, a futások mappáiból. Arra való, amikor nem a kód, hanem a
modell vagy a gép változik:

  * nagyobb modell: a qwen3.5:9b a qwen3.5:4b-vel szemben, ugyanazon a gépen
    (docs/k1_protokoll_v2_9b.json — ez a protokoll rögzíti ennek a fájlnak az ujjlenyomatát);
  * gépváltás: a 4B ugyanazzal a modellfájllal a laptop processzorán és a videókártyán
    (a döntési napló 2026-10-22-i sora szerint).

    uv run python tools/k1_futas_osszevetes.py --a logs\\meres\\MAPPA_A --b logs\\meres\\MAPPA_B
        --cimke-a "9B (GPU)" --cimke-b "4B (GPU)" --protokoll docs\\k1_protokoll_v2_9b.json
        --kimenet docs\\k1_9b_eredmeny.md

A különbség mindig A − B. Kimenet: a --kimenet .md fájl, mellé .json.

Mit számol (az eredmények előtt rögzítve, 2026-10-22)
  * Fő mutató: teljes egyezés (mérőszám, bontás, szűrő, időablak, rendezés) a megválaszolandó
    kérdéseken, A − B kérdésenként párosítva, 95%-os bootstrap (B és mag a protokollból); a
    négymezős tábla. Mellette F-1, F-2 (bármilyen és az elvárt indokú elutasítás), típusonként.
  * Egyezés kérdésenként: ugyanaz-e az ① gépi alak (vagy ugyanaz az elutasítás), és ugyanaz-e
    az ítélet — gépváltásnál ez a reprodukálhatóság mértéke.
  * K1 ágonként: a modell szövegének megjelölt aránya (a két futás ugyanazzal a kóddal, tehát
    ugyanazzal a 2. kapuval pontozott), a felhasználóhoz jutó megjelölt szöveg, a sablonra váltás,
    és a megjelölt arány különbsége kérdésenként párosítva.
  * Idő: az ① és a ② mediánja, az összes idő.

Mielőtt számol, ellenőriz: mindkét futás a protokoll kérdéssorán, a protokollban rögzített kóddal
(ujjlenyomat), egy ismétléssel, teljes futásként ment-e; és a tárolt ítéletek újraszámolva
ugyanazok-e. Ha a két futás ugyanazt a modellnevet használta, de más modellfájllal (lenyomat),
figyelmeztet. Ha a protokoll „elemzes” mezője ezt a fájlt rögzíti, és a fájl azóta változott,
a jelentés figyelmeztet.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.db import DB_PATH, connect, use_utf8_console  # noqa: E402
from narrative import meres, proba  # noqa: E402
from semantic import catalog  # noqa: E402

_spec = importlib.util.spec_from_file_location("k1_v2_osszevetes", ROOT / "tools" / "k1_v2_osszevetes.py")
v2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v2)

AGAK = meres.AGAK
SAJAT = "tools/k1_futas_osszevetes.py"


# ------------------------------------------------------------------ ellenőrzés
def check(a: v2.Run, b: v2.Run, protocol: dict, questions: list[dict]) -> tuple[list[str], list[str]]:
    err, warn = [], []
    if protocol.get("allapot") != "jovahagyva":
        err.append(f"a protokoll állapota „{protocol.get('allapot')}”, nem „jovahagyva”")
    want_q, want_fp = protocol["kerdessor"]["sha256"], protocol["kod"]["ujjlenyomat"]
    reps = int(protocol["beallitasok"]["ismetles"])
    ids = {q["id"] for q in questions}
    for run in (a, b):
        h, name = run.head, f"{run.label} ({run.path.name})"
        if h["kerdessor"]["sha256"] != want_q:
            err.append(f"{name}: más kérdéssoron futott ({h['kerdessor']['sha256'][:16]} ≠ {str(want_q)[:16]})")
        if h["kod"].get("ujjlenyomat") != want_fp:
            err.append(f"{name}: a kód ujjlenyomata {str(h['kod'].get('ujjlenyomat'))[:16]}, a protokoll szerinti "
                       f"{want_fp[:16]}")
        if h["kod"].get("nem_commitolt_valtozas"):
            warn.append(f"{name}: nem commitolt változással futott (a kód ujjlenyomata ettől még a rögzített)")
        if int(h.get("ismetles", 0)) != reps or h.get("csak_ertelmezes"):
            err.append(f"{name}: {h.get('ismetles')} ismétlés{' csak értelmezéssel' if h.get('csak_ertelmezes') else ''}"
                       f" (a protokoll: {reps}, teljes futás)")
        missing = sorted(ids - set(run.rows))
        if missing:
            warn.append(f"{name}: {len(missing)} kérdés eredménye hiányzik vagy modellhibás, kimarad a párosításból: "
                        + ", ".join(missing))
    if a.model == b.model and a.head.get("digest") != b.head.get("digest"):
        warn.append(f"a két futás ugyanazzal a modellnévvel ({a.model}), de más modellfájllal ment "
                    f"({str(a.head.get('digest'))[:12]} ≠ {str(b.head.get('digest'))[:12]})")
    pin = protocol.get("elemzes") or {}
    if pin.get("eszkoz") == SAJAT:
        mine = meres.sha256_text(Path(__file__))
        if pin.get("sha256") != mine:
            warn.append(f"az összevető eszköz a protokoll jóváhagyása óta megváltozott ({mine[:16]} ≠ "
                        f"{str(pin.get('sha256'))[:16]}) — az eltérést a dolgozatban jelezni kell")
    return err, warn


# ------------------------------------------------------------------ összevetés
def same_reading(ra: dict, rb: dict) -> bool:
    """Ugyanaz-e az ① eredménye: ugyanaz a gépi alak, vagy ugyanazzal a kóddal elutasítva."""
    if ra["spec"] is None or rb["spec"] is None:
        return ra["spec"] is None and rb["spec"] is None and ra["kapu1"] == rb["kapu1"]
    return json.dumps(ra["spec"], sort_keys=True) == json.dumps(rb["spec"], sort_keys=True)


def compare(a: v2.Run, b: v2.Run, questions: list[dict], protocol: dict) -> dict:
    boot = protocol["statisztika"]["bootstrap"]
    qmap = {q["id"]: q for q in questions}
    ans = [q["id"] for q in questions if not q.get("elutasitas")]
    traps = [q["id"] for q in questions if q.get("elutasitas")]
    A, B = a.rows, b.rows

    def pick(rows, ids, fn):
        return {i: fn(rows[i]) for i in ids if i in rows}

    out = {
        "fo": v2.paired(pick(A, ans, lambda r: r["itelet"] == "helyes"), pick(B, ans, lambda r: r["itelet"] == "helyes"), boot),
        "F1": v2.paired(pick(A, ans, lambda r: bool(r["f1"])), pick(B, ans, lambda r: bool(r["f1"])), boot),
        "F2": v2.paired(pick(A, traps, lambda r: r["elutasitva"]), pick(B, traps, lambda r: r["elutasitva"]), boot),
        "F2_elvart_indok": v2.paired(pick(A, traps, lambda r: r["itelet"] == "helyes elutasítás"),
                                     pick(B, traps, lambda r: r["itelet"] == "helyes elutasítás"), boot),
    }
    common = [q["id"] for q in questions if q["id"] in A and q["id"] in B]
    out["egyezes"] = {"kerdesek": len(common),
                      "azonos_ertelmezes": sum(same_reading(A[i], B[i]) for i in common),
                      "azonos_itelet": sum(A[i]["itelet"] == B[i]["itelet"] for i in common)}
    by_type: dict[str, dict] = defaultdict(lambda: {"n": 0, "a": 0, "b": 0})
    for i in common:
        t = by_type[qmap[i]["tipus"]]
        t["n"] += 1
        t["a"] += A[i]["itelet"] in ("helyes", "helyes elutasítás")
        t["b"] += B[i]["itelet"] in ("helyes", "helyes elutasítás")
    out["tipus_szerint"] = dict(sorted(by_type.items()))
    k1 = {}
    for mod in AGAK:
        def texts(rows):
            return {i: rows[i]["agak"][mod] for i in ans if i in rows and mod in rows[i]["agak"]
                    and rows[i]["agak"][mod]["modell_szoveg"] is not None}
        ta, tb = texts(A), texts(B)
        k1[mod] = {
            "a": meres._rate(sum(t["allitasok"] > 0 for t in ta.values()), len(ta)),
            "b": meres._rate(sum(t["allitasok"] > 0 for t in tb.values()), len(tb)),
            "eljut_a": meres._rate(sum(t["allitasok"] > 0 and not t["sablon"] for t in ta.values()), len(ta)),
            "eljut_b": meres._rate(sum(t["allitasok"] > 0 and not t["sablon"] for t in tb.values()), len(tb)),
            "sablon_a": meres._rate(sum(t["sablon"] for t in ta.values()), len(ta)),
            "sablon_b": meres._rate(sum(t["sablon"] for t in tb.values()), len(tb)),
            "paros": v2.paired({i: t["allitasok"] > 0 for i, t in ta.items()},
                               {i: t["allitasok"] > 0 for i, t in tb.items()}, boot),
        }
    out["K1"] = k1
    out["kerdesenkent"] = [{"id": q["id"], "tipus": q["tipus"], "kerdes": q["kerdes"],
                            "a": A.get(q["id"], {}).get("itelet"), "b": B.get(q["id"], {}).get("itelet"),
                            "azonos_ertelmezes": (same_reading(A[q["id"]], B[q["id"]])
                                                  if q["id"] in A and q["id"] in B else None),
                            "a_elteres": A.get(q["id"], {}).get("elteresek", [])} for q in questions]
    return out


# ------------------------------------------------------------------ jelentés
def _row(name: str, p: dict) -> str:
    return (f"| {name} | {p['n']} | {v2._r(p['v3'])} | {v2._r(p['v4'])} | **{v2._pp(p['kulonbseg'])}** "
            f"({v2._pp(p['also'])} – {v2._pp(p['felso'])}) | {p['mindketto']} / {p['csak_v4']} / {p['csak_v3']} / {p['egyik_sem']} |")


def report_md(res: dict, a: v2.Run, b: v2.Run, protocol: dict, p_sha: str, checks: dict, times: dict, title: str) -> str:
    boot = protocol["statisztika"]["bootstrap"]
    la, lb = a.label, b.label
    L = [f"# {title}", "",
         f"Géppel készült (`{SAJAT}`), a futások mappáiból, modell nélkül. Protokoll: "
         f"`{protocol.get('_fajl', 'protokoll')}` (SHA256 `{p_sha[:16]}…`, jóváhagyta: "
         f"{(protocol.get('jovahagyas') or {}).get('ki', '—')}, {(protocol.get('jovahagyas') or {}).get('mikor', '—')}); "
         f"kérdéssor: `{protocol['kerdessor']['fajl']}` (SHA256 `{protocol['kerdessor']['sha256'][:16]}…`). "
         f"A különbség mindig **A − B**: A = {la}, B = {lb}.", "", "## Futások", "",
         "| | futás | mappa | kezdés | modell | kód (commit · ujjlenyomat) | protokoll |", "|---|---|---|---|---|---|---|"]
    for tag, run in (("A", a), ("B", b)):
        h = run.head
        L.append(f"| {tag} | {run.label} | `{run.path.name}` | {h.get('kezdes', '—')} | {run.model} (`{str(h.get('digest'))[:12]}`) | "
                 f"`{str(h['kod'].get('commit'))[:7]}` · `{str(h['kod'].get('ujjlenyomat'))[:16]}` | "
                 f"`{str((h.get('protokoll') or {}).get('fajl'))}` |")
    L += ["", "Ellenőrzés: " + ("mindkét futás a protokoll kérdéssorán, a rögzített kóddal, teljes futásként ment."
                                if not checks["hibak"] else "**HIBA** — " + "; ".join(checks["hibak"]))]
    for w in checks["figyelmeztetesek"]:
        L.append(f"- figyelmeztetés: {w}")
    L.append("- a tárolt ítéletek újraszámolva: " + ("mind egyezik." if not checks["ujraszamolas"] else
             f"**{len(checks['ujraszamolas'])} eltérés** — " + "; ".join(checks["ujraszamolas"][:10])))
    e = res["egyezes"]
    L += ["", "## Fő mutató: helyes válasz a feltett kérdésre", "",
          f"Teljes egyezés (mérőszám, bontás, szűrő, időablak, rendezés) a megválaszolandó kérdéseken, kérdésenként "
          f"párosítva; 95%-os bootstrap a kérdések újramintavételével (B = {boot['B']}, mag {boot['mag']}). A négy szám: "
          "mindkettő helyes / csak A / csak B / egyik sem.", "",
          f"| mutató | kérdés | B: {lb} | A: {la} | A − B (95%) | ✓✓ / csak A / csak B / ✗✗ |", "|---|---|---|---|---|---|",
          _row("**teljes egyezés**", res["fo"]), _row("F-1 (mérőszám és bontás)", res["F1"]),
          _row("F-2 (a csapdát elutasítja)", res["F2"]), _row("F-2, az elvárt indokkal", res["F2_elvart_indok"]), "",
          f"Egyezés kérdésenként ({e['kerdesek']} kérdés): azonos ① értelmezés {e['azonos_ertelmezes']}, azonos ítélet "
          f"{e['azonos_itelet']}.", "",
          "### Kérdéstípusonként (helyes értelmezés / helyes elutasítás)", "", f"| típus | kérdés | B: {lb} | A: {la} |",
          "|---|---|---|---|"]
    for t, v in res["tipus_szerint"].items():
        L.append(f"| {t} | {v['n']} | {v['b']} | {v['a']} |")
    L += ["", "## K1: alá nem támasztott állítás a modell szövegében (megválaszolandó kérdések)", "",
          "Mindkét futás ugyanazzal a kóddal, tehát ugyanazzal a 2. kapuval pontozott. „Eljut”: a megjelölt szöveg a "
          "felhasználóhoz kerül (a fő ágon a megjelölt helyett sablon megy ki).", "",
          f"| ág | B: {lb} | A: {la} | A − B (párosítva) | eljut: B / A | sablonra vált: B / A |", "|---|---|---|---|---|---|"]
    for mod in AGAK:
        k, p = res["K1"][mod], res["K1"][mod]["paros"]
        L.append(f"| {meres.AG_NEV[mod]} | {v2._r(k['b'])} | {v2._r(k['a'])} | {v2._pp(p['kulonbseg'])} ({v2._pp(p['also'])} – "
                 f"{v2._pp(p['felso'])}; {p['n']} kérdés) | {meres._pct(k['eljut_b']['arany'])} / {meres._pct(k['eljut_a']['arany'])} | "
                 f"{meres._pct(k['sablon_b']['arany'])} / {meres._pct(k['sablon_a']['arany'])} |")
    L += ["", "## Idő (medián)", "", "| futás | ① (értelmezés) | ② fő ág | ② kontrollág | összesen |", "|---|---|---|---|---|"]
    for run in (a, b):
        t = times[run.label]
        L.append(f"| {run.label} | {v2._sec(t.get('ido1_median_ms'))} | {v2._sec(t.get('ido2_jelolo_median_ms'))} | "
                 f"{v2._sec(t.get('ido2_szabad_median_ms'))} | {meres.nv.fmt_num(t['osszes_ms'] / 60000.0, 1)} perc |")
    L += ["", "## Kérdésenként", "",
          "✓ helyes (vagy helyes elutasítás) · ✗ hibás értelmezés · ⊘ téves elutasítás · ! hiányzó elutasítás · "
          "≈ más indokú elutasítás · „=”: azonos ① értelmezés", "",
          f"| # | típus | kérdés | B: {lb} | A: {la} | = | A eltérése az elvárttól |", "|---|---|---|---|---|---|---|"]
    for row in res["kerdesenkent"]:
        change = ""
        if row["a"] and row["b"]:
            ok_a, ok_b = v2.JEL[row["a"]] == "✓", v2.JEL[row["b"]] == "✓"
            change = " ↑" if ok_a and not ok_b else (" ↓" if ok_b and not ok_a else "")
        q = row["kerdes"] if len(row["kerdes"]) <= 70 else row["kerdes"][:68] + "…"
        same = {True: "=", False: "≠", None: "—"}[row["azonos_ertelmezes"]]
        L.append(f"| {row['id']} | {row['tipus']} | {q.replace('|', '/')} | {v2.JEL[row['b']]} | {v2.JEL[row['a']]}{change} | "
                 f"{same} | {'; '.join(row['a_elteres'])[:160].replace('|', '/')} |")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ parancs
def run(a_dir: Path, b_dir: Path, label_a: str, label_b: str, protokoll: Path, kimenet: Path,
        title: str | None = None, db_path: Path | None = None) -> dict:
    protocol, p_sha = meres.load_protocol(protokoll)
    protocol["_fajl"] = protokoll.name
    qfile = meres.question_file(protocol, protokoll.parent.parent)
    if not protocol["kerdessor"].get("sha256") or meres.sha256_text(qfile) != protocol["kerdessor"]["sha256"]:
        raise SystemExit("A kérdéssor nem az, amit a protokoll lezárt (vagy még nincs lezárva).")
    questions = proba.load_questions(qfile)
    qmap = {q["id"]: q for q in questions}
    a, b = v2.Run(a_dir, label_a), v2.Run(b_dir, label_b)
    err, warn = check(a, b, protocol, questions)
    if err:
        raise SystemExit("Az összevetés nem készül el:\n  " + "\n  ".join(err))
    cat = catalog.load()
    con = connect(db_path or DB_PATH, read_only=True)
    wl = catalog.whitelist(cat, con)
    rejudged = v2.rejudge({"a": a, "b": b}, qmap, cat, wl, con)
    con.close()
    res = compare(a, b, questions, protocol)
    times = {r.label: meres.summarize(list(r.rows.values()), questions, protocol)["ido"] for r in (a, b)}
    checks = {"hibak": err, "figyelmeztetesek": warn, "ujraszamolas": rejudged}
    title = title or f"Két futás összevetése: {label_a} és {label_b}"
    kimenet.parent.mkdir(parents=True, exist_ok=True)
    kimenet.write_text(report_md(res, a, b, protocol, p_sha, checks, times, title), encoding="utf-8")
    payload = {"cim": title, "protokoll": {"fajl": protokoll.name, "sha256": p_sha},
               "futasok": {"A": {"cimke": label_a, "mappa": a.path.name, **a.head},
                           "B": {"cimke": label_b, "mappa": b.path.name, **b.head}},
               "ellenorzes": checks, "eredmeny": res, "ido": times}
    kimenet.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return {"eredmeny": res, "ellenorzes": checks}


def main(argv: list[str] | None = None) -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="Két mérőfutás összevetése (A − B), kérdésenként párosítva.")
    ap.add_argument("--a", type=Path, required=True, help="az A futás mappája (logs/meres/…)")
    ap.add_argument("--b", type=Path, required=True, help="a B futás mappája (az összevetés alapja)")
    ap.add_argument("--cimke-a", dest="cimke_a", required=True, help="az A futás neve a jelentésben, pl. „9B (GPU)”")
    ap.add_argument("--cimke-b", dest="cimke_b", required=True, help="a B futás neve, pl. „4B (GPU)”")
    ap.add_argument("--protokoll", type=Path, required=True, help="a jóváhagyott protokoll (a kérdéssor és a kód)")
    ap.add_argument("--kimenet", type=Path, required=True, help="a jelentés (.md; mellé .json)")
    ap.add_argument("--cim", help="a jelentés címe")
    x = ap.parse_args(argv)
    out = run(x.a, x.b, x.cimke_a, x.cimke_b, x.protokoll, x.kimenet, x.cim)
    fo, e, c = out["eredmeny"]["fo"], out["eredmeny"]["egyezes"], out["ellenorzes"]
    print(f"Teljes egyezés ({fo['n']} kérdés): {x.cimke_b} {meres._pct(fo['v3']['arany'])} → {x.cimke_a} "
          f"{meres._pct(fo['v4']['arany'])}, különbség {v2._pp(fo['kulonbseg'])} (95%: {v2._pp(fo['also'])} – {v2._pp(fo['felso'])})")
    print(f"Azonos ① értelmezés: {e['azonos_ertelmezes']}/{e['kerdesek']} · újraszámolt ítélet eltérése: {len(c['ujraszamolas'])}")
    for w in c["figyelmeztetesek"]:
        print(f"Figyelmeztetés: {w}")
    print(f"Jelentés: {x.kimenet}")


if __name__ == "__main__":
    main()
