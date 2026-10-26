"""
A K1 kézi ellenőrzése (protokoll: kezi_ellenorzes) — a mérés mappájából, modell nélkül.

    uv run python tools/kezi_minta.py minta logs\\meres\\MAPPA       # a minta újra, a hatókörrel együtt
    uv run python tools/kezi_minta.py kiertekel logs\\meres\\MAPPA   # a kitöltött minta kiértékelése
    uv run python tools/kezi_minta.py osszesit                      # minden kiértékelt minta → docs/k1_kezi_ellenorzes.*

A minta UGYANAZ, mint amit a mérés a végén kiírt (ugyanaz a mag, ugyanazok a kódok, a kulcs
is ugyanaz) — csak az „eredmeny” oszlop elejére kerül a válasz hatóköre (időszak, szűrő), mert
a modellnek mutatott rövid nézetből az időszak hiányzik, és enélkül nem dönthető el, igaz-e
egy „nincs szűrés” vagy „2017-ben” kezdetű mondat. (A mérőprogram ezért nem változott: a
folyamatban lévő mérések folytathatók maradnak.) A mintavétel magja a futás SAJÁT protokolljából
jön (fej.json, ujjlenyomattal ellenőrizve) — 2026. okt. 26-ig az eszköz mindig az első protokollt
töltötte be, így a v2/v3 futásokra más magú mintát írt volna; és a meglévő kulcsot sem írja felül
eltérő kulccsal.

A kiértékelés a kitöltött mintából becsli, milyen gyakran téved a 2. kapu: a megjelölt
szövegek közül mennyi tényleg hibás (találati pontosság), és a meg nem jelöltek közül mennyi
mégis az (kihagyás). Ebből a K1 korrigált becslése ágonként: megjelölt arány × pontosság +
meg nem jelölt arány × kihagyás.
"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from narrative import meres  # noqa: E402
from semantic import catalog  # noqa: E402
from semantic.catalog import value_label  # noqa: E402

HEADER = ["kod", "kerdes", "eredmeny", "szoveg", "van_ala_nem_tamasztott_allitas (igen/nem)", "melyik", "megjegyzes"]
GUIDE = """A kézi ellenőrzés útmutatója (K1)

Minden sorban egy kérdés, a rendszer eredménye (amit a nyelvi modell látott, az elején a
válasz hatókörével) és a modell szövege. A szövegről kell eldönteni: VAN-E BENNE OLYAN
ÁLLÍTÁS, AMELYET AZ EREDMÉNY NEM TÁMASZT ALÁ? Nem az a kérdés, hogy jól értette-e a modell
a kérdést, vagy hogy szép-e a szöveg — csak az, hogy amit állít, igaz-e az eredményre.

Alá nem támasztott állítás például:
  * olyan szám, amely nincs az eredményben (kerekítve sem), vagy nem ahhoz tartozik, amihez írta;
  * egy csoport értéke egy másik csoport neve mellett;
  * „a legnagyobb / a legkisebb / csúcs / mélypont” olyan csoportra, amely nem az;
  * a 95%-os tartomány mint csúcs vagy mélypont;
  * hamis állítás a hatókörről („nincs adat”, „nincs szűrés”, holott van időszak vagy szűrő);
  * ok-okozati állítás („a késést a távolság okozza”).
Nem hiba: döcögős fogalmazás, ismétlés, ha valamit kihagy, kerekítés (25,35% → 25,4% vagy 25%).

Töltsd ki: „igen” vagy „nem”; ha igen, a „melyik” oszlopba röviden, mi a hibás.
A kulcsfájlt (…_kulcs.csv) csak a kitöltés UTÁN nyisd meg — vagy egyáltalán ne: a kiértékelés
(tools/kezi_minta.py kiertekel) maga párosítja.
"""


def scope(spec: dict | None, cat) -> str:
    """A válasz hatóköre a gépi alakból — ezt a válasz eleje (a kód) írja ki a felhasználónak."""
    if not spec:
        return ""
    w = spec.get("idoablak") or {}
    period = (f"{w.get('tol') or 'az adat eleje'} – {w.get('ig') or 'az adat vége'}" if w
              else "a teljes adat (2016. szept. 15. – 2018. aug. 29.)")
    filters = "; ".join(f"{cat.dimensions[d].rovid} = " + ", ".join(value_label(cat, d, v) for v in vals)
                        for d, vals in (spec.get("szuro") or {}).items()) or "nincs"
    return f"HATÓKÖR (a válasz elején a rendszer írja ki): időszak: {period}; szűrő: {filters}\n\n"


def run_protocol(run: Path) -> dict:
    """A futás saját protokollja: a fej.json (vagy az összegzés) szerinti fájl, ha az ujjlenyomata egyezik."""
    head = run / "fej.json" if (run / "fej.json").exists() else run / "osszegzes.json"
    if not head.exists():
        have = sorted(d.name for d in run.parent.glob("*") if d.is_dir()) if run.parent.is_dir() else []
        raise SystemExit(f"Nincs ilyen mérés ezen a gépen: {run} (nincs benne fej.json / osszegzes.json). "
                         f"A {run.parent} mappában ezek vannak: {', '.join(have) or '—'}")
    rec = json.loads(head.read_text(encoding="utf-8")).get("protokoll") or {}
    for cand in (ROOT / rec.get("fajl", ""), meres.PROTOKOLL):
        if cand.is_file() and meres.sha256_text(cand) == rec.get("sha256"):
            return meres.load_protocol(cand)[0]
    raise SystemExit(f"A futás protokollja ({rec.get('fajl')}, {str(rec.get('sha256'))[:8]}…) nem található "
                     "változatlanul a tárolóban — a minta így nem állítható elő újra ugyanúgy.")


def _units(run: Path) -> tuple[list[dict], dict]:
    protocol = run_protocol(run)
    units = [r for r in meres.latest_rows(meres.read_rows(run)) if not r["hiba"]]
    return units, protocol


def sample(run: Path) -> int:
    """A mérés mintája újra (ugyanaz a kiválasztás és a kulcs), a hatókörrel kiegészítve."""
    units, protocol = _units(run)
    cat = catalog.load()
    with tempfile.TemporaryDirectory() as tmp:
        n = meres.annotation_sample(units, protocol, Path(tmp))
        key = list(csv.reader((Path(tmp) / "kezi_ellenorzes_kulcs.csv").open(encoding="utf-8-sig", newline=""),
                              delimiter=";"))
        rows = list(csv.reader((Path(tmp) / "kezi_ellenorzes.csv").open(encoding="utf-8-sig", newline=""),
                               delimiter=";"))
    by = {(u["id"], int(u["ismetles"])): u for u in units}
    out = [HEADER]
    for (kod, qid, rep, _ag, _talalt, _p), row in zip(key[1:], rows[1:]):
        assert row[0] == kod
        u = by[(qid, int(rep))]
        out.append([kod, row[1], scope(u["spec"], cat) + row[2], row[3], "", "", ""])
    target = run / "kezi_ellenorzes.csv"
    if target.exists() and _filled(target):
        raise SystemExit(f"A {target} már ki van töltve — nem írom felül.")
    old_key = run / "kezi_ellenorzes_kulcs.csv"
    if old_key.exists():
        old = list(csv.reader(old_key.open(encoding="utf-8-sig", newline=""), delimiter=";"))
        if old != key:
            raise SystemExit(f"A meglévő kulcs ({old_key}) más mintát ír le, mint ami most készülne — nem írom felül.")
    with target.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, delimiter=";").writerows(out)
    with (run / "kezi_ellenorzes_kulcs.csv").open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, delimiter=";").writerows(key)
    (run / "kezi_ellenorzes_utmutato.txt").write_text(GUIDE, encoding="utf-8")
    return n


def _filled(path: Path) -> bool:
    rows = list(csv.reader(path.open(encoding="utf-8-sig", newline=""), delimiter=";"))
    return any(r[4].strip() for r in rows[1:] if len(r) > 4)


def evaluate(run: Path) -> dict:
    """A kitöltött minta kiértékelése a kulccsal: a kapu pontossága és a K1 korrigált becslése."""
    filled = {r[0]: r for r in csv.reader((run / "kezi_ellenorzes.csv").open(encoding="utf-8-sig", newline=""),
                                          delimiter=";")}
    key = list(csv.reader((run / "kezi_ellenorzes_kulcs.csv").open(encoding="utf-8-sig", newline=""), delimiter=";"))
    cells: dict[tuple[str, str], list[bool]] = {}
    missing = []
    for kod, _qid, _rep, ag, talalt, _p in key[1:]:
        answer = filled.get(kod, [""] * 5)[4].strip().lower()
        if answer not in ("igen", "nem"):
            missing.append(kod)
            continue
        cells.setdefault((ag, talalt), []).append(answer == "igen")
    summary = json.loads((run / "osszegzes.json").read_text(encoding="utf-8"))["osszegzes"]["K1"]
    out = {"kitoltetlen": missing, "agak": {}}
    for ag in meres.AGAK:
        hit = cells.get((ag, "igen"), [])
        miss = cells.get((ag, "nem"), [])
        flagged = summary[ag]["fo"]["arany"]
        ppv = sum(hit) / len(hit) if hit else None
        fn = sum(miss) / len(miss) if miss else None
        adjusted = None
        if flagged is not None and (flagged == 0 or ppv is not None) and (flagged == 1 or fn is not None):
            adjusted = (flagged * ppv if flagged else 0.0) + ((1 - flagged) * fn if flagged < 1 else 0.0)
        out["agak"][ag] = {"megjelolt_arany": flagged, "megjeloltbol_valoban_hibas": [sum(hit), len(hit)],
                           "meg_nem_jeloltbol_megis_hibas": [sum(miss), len(miss)],
                           "pontossag": ppv, "kihagyas": fn, "k1_korrigalt": adjusted}
    (run / "kezi_ellenorzes_eredmeny.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def _share(k: int, n: int) -> dict:
    ci = meres.wilson(k, n)
    return {"k": k, "n": n, "arany": k / n if n else None, "ci95": list(ci) if ci else None}


def summarize(meres_dir: Path) -> dict:
    """Minden futás, amelynek van kiértékelt kézi mintája: a kapu pontossága, kihagyása (Wilson-intervallummal),
    a K1 korrigált becslése és — a fő ágon — a felhasználóhoz eljutó, a kapu által nem látott hibák becslése:
    (1 − megjelölt arány) × kihagyás (a megjelölt arány minden szövegen mért, ezért rögzítettnek vesszük)."""
    runs = []
    for res in sorted(meres_dir.glob("*/kezi_ellenorzes_eredmeny.json")):
        run = res.parent
        out = json.loads(res.read_text(encoding="utf-8"))
        head = json.loads((run / "osszegzes.json").read_text(encoding="utf-8"))
        item = {"futas": run.name, "modell": head["modell"], "kerdessor": head["kerdessor"]["fajl"],
                "kerdesek": head["kerdessor"]["kerdesek"], "verzio": head["kod"].get("verzio", "v3"),
                "kitoltetlen": len(out["kitoltetlen"]), "agak": {}}
        for ag, v in out["agak"].items():
            hit, miss = v["megjeloltbol_valoban_hibas"], v["meg_nem_jeloltbol_megis_hibas"]
            row = {"megjelolt_arany": v["megjelolt_arany"], "pontossag": _share(*hit), "kihagyas": _share(*miss),
                   "k1_korrigalt": v["k1_korrigalt"]}
            if ag == "jelolo" and v["megjelolt_arany"] is not None and miss[1]:
                free = 1 - v["megjelolt_arany"]
                lo, hi = row["kihagyas"]["ci95"]
                row["eljut_fedetlen"] = {"becsles": free * miss[0] / miss[1], "ci95": [free * lo, free * hi]}
            item["agak"][ag] = row
        runs.append(item)
    return {"futasok": runs}


def report(res: dict) -> str:
    pct = lambda x: "—" if x is None else f"{100 * x:.1f}%".replace(".", ",")
    ci = lambda c: "—" if not c else f"[{pct(c[0])}; {pct(c[1])}]"
    lines = ["# A K1 kézi ellenőrzése — összesítés", "",
             "A vak kézi minták kiértékelése (`tools/kezi_minta.py osszesit`). A minta rétegzett: ágonként (legfeljebb) 20 olyan "
             "szöveg, amelyet a 2. kapu nem jelölt meg, és 10, amelyet megjelölt. **Pontosság**: a megjelöltekből "
             "mennyi valóban hibás; **kihagyás**: a meg nem jelöltekből mennyi mégis az (95%-os Wilson-intervallum). "
             "**K1 korrigálva** = megjelölt arány × pontosság + (1 − megjelölt arány) × kihagyás. A fő ágon a "
             "megjelölt szöveg helyett a sablon jut el a felhasználóhoz, ezért ott a **felhasználóhoz eljutó, a kapu "
             "által nem látott hiba** becslése (1 − megjelölt arány) × kihagyás; ez utólag (a minták egy részének "
             "kiértékelése után) meghatározott, származtatott mennyiség, nem a protokoll fő mutatója.", ""]
    for r in res["futasok"]:
        lines += [f"## {r['futas']} — {r['modell']}, {r['verzio']}, {r['kerdessor']} ({r['kerdesek']} kérdés)", ""]
        if r["kitoltetlen"]:
            lines += [f"**Kitöltetlen sor: {r['kitoltetlen']}** — a becslés még nem végleges.", ""]
        lines += ["| ág | megjelölt arány | pontosság | kihagyás | K1 korrigálva | eljut, nem látott |",
                  "|---|---|---|---|---|---|"]
        for ag, v in r["agak"].items():
            p, m = v["pontossag"], v["kihagyas"]
            e = v.get("eljut_fedetlen")
            lines.append(f"| {meres.AG_NEV[ag]} | {pct(v['megjelolt_arany'])} | {p['k']}/{p['n']} {ci(p['ci95'])} | "
                         f"{m['k']}/{m['n']} {ci(m['ci95'])} | {pct(v['k1_korrigalt'])} | "
                         f"{(pct(e['becsles']) + ' ' + ci(e['ci95'])) if e else ('— (nincs kapu)' if ag == 'szabad' else '— (nincs kitöltött adat)')} |")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    if args[:1] == ["osszesit"]:
        res = summarize(Path(args[1]) if len(args) > 1 else ROOT / "logs" / "meres")
        (ROOT / "docs" / "k1_kezi_ellenorzes.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                                               encoding="utf-8")
        (ROOT / "docs" / "k1_kezi_ellenorzes.md").write_text(report(res), encoding="utf-8")
        print(f"{len(res['futasok'])} kiértékelt minta → docs/k1_kezi_ellenorzes.md")
        return
    if len(args) != 2 or args[0] not in ("minta", "kiertekel"):
        raise SystemExit(__doc__)
    run = Path(args[1])
    if args[0] == "minta":
        print(f"{sample(run)} szöveg: {run / 'kezi_ellenorzes.csv'} (útmutató: kezi_ellenorzes_utmutato.txt)")
        return
    out = evaluate(run)
    if out["kitoltetlen"]:
        print(f"Kitöltetlen sor: {len(out['kitoltetlen'])} ({', '.join(out['kitoltetlen'][:10])} …)")
    for ag, v in out["agak"].items():
        pct = lambda x: "—" if x is None else f"{100 * x:.1f}%".replace(".", ",")
        print(f"{meres.AG_NEV[ag]}: a kapu {pct(v['megjelolt_arany'])}-ot jelölt meg; ebből valóban hibás "
              f"{v['megjeloltbol_valoban_hibas'][0]}/{v['megjeloltbol_valoban_hibas'][1]}, a meg nem jelöltekből mégis "
              f"hibás {v['meg_nem_jeloltbol_megis_hibas'][0]}/{v['meg_nem_jeloltbol_megis_hibas'][1]} → K1 korrigálva: "
              f"{pct(v['k1_korrigalt'])}")


if __name__ == "__main__":
    main()
