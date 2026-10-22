"""
Visszajátszás: a már lefutott mérések eltárolt ① űrlapjai (a modell válaszai) a MOSTANI kódon —
modell nélkül, másodpercek alatt. Fejlesztéshez való: megmutatja, mit javít vagy ront egy
kódváltozás a már látott kérdéseken.

    uv run python tools/visszajatszas.py logs\\meres\\MAPPA [logs\\meres\\MAPPA2 …]
    uv run python tools/visszajatszas.py … --reszletes      # kérdésenként is: mi változott

Minden futás a saját kérdéssorán (a fej.json szerint) pontozódik. Az alapvonal a futás tárolt
ítélete (a futás kódjával); mellette ugyanaz a mostani kóddal.

Korlátok — ezért ez csak OPTIMISTA fejlesztési becslés, nem mérés:
  * a kérdéseket már láttuk, a javítások épp ezekhez készülnek (a mérés új, lezárt kérdéssoron megy);
  * csak a modell utáni részt (értékfeloldás, kódbeli javítások, KAPU ①) futtatja újra: ha a kód a
    prompton is változtat, a modell válasza is más lenne — azt csak új futás mutatja meg;
  * a javító kört nem játssza újra: ha az új kód egy olyan űrlapot utasít el, amelyre a rendszer
    javító kört kérne, itt az elutasítás marad.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.db import DB_PATH, connect, use_utf8_console  # noqa: E402
from narrative import meres, proba  # noqa: E402
from narrative import to_spec as ts  # noqa: E402
from semantic import catalog  # noqa: E402

OK = ("helyes", "helyes elutasítás")


def replay_run(run: Path, cat, wl, con, groups, root: Path = ROOT) -> dict:
    head = json.loads((run / "fej.json").read_text(encoding="utf-8"))
    qfile = root / head["kerdessor"]["fajl"]
    gold = {q["id"]: q for q in proba.load_questions(qfile)}
    rows = [r for r in meres.latest_rows(meres.read_rows(run)) if not r["hiba"] and r["id"] in gold]
    old, new = Counter(), Counter()
    changes = []
    for r in rows:
        q = gold[r["id"]]
        trap = bool(q.get("elutasitas"))
        if r["urlap"] is None:                       # nem lett értelmezhető űrlap: marad, ami volt
            verdict, f1, rejected, spec = r["itelet"], r["f1"], r["elutasitva"], None
        else:
            _, gate, _, fixes = ts.interpret(r["urlap"], r["kerdes"], cat, wl, con)
            verdict, diffs = proba.judge(q, gate, cat, wl, groups=groups)
            f1, rejected = proba.core_ok(q, gate), not gate.ok
            spec = gate.spec.to_dict() if gate.ok else f"elutasítva: {gate.elutasitas.kod}"
        for c, (v, f, rej) in ((old, (r["itelet"], r["f1"], r["elutasitva"])), (new, (verdict, f1, rejected))):
            if trap:
                c["csapda"] += 1
                c["elutasitva"] += bool(rej)
                c["elvart_indok"] += v == "helyes elutasítás"
            else:
                c["valasz"] += 1
                c["f1"] += bool(f)
                c["helyes"] += v == "helyes"
        if verdict != r["itelet"]:
            changes.append({"id": r["id"], "ismetles": r["ismetles"], "kerdes": r["kerdes"], "regi": r["itelet"],
                            "uj": verdict, "uj_alak": spec,
                            "irany": "javult" if verdict in OK and r["itelet"] not in OK else
                                     "romlott" if r["itelet"] in OK and verdict not in OK else "más"})
    return {"futas": run.name, "modell": head.get("modell"), "kod": head["kod"].get("ujjlenyomat", "")[:8],
            "kerdessor": head["kerdessor"]["fajl"], "regi": dict(old), "uj": dict(new), "valtozasok": changes}


def _pct(k, n) -> str:
    return "—" if not n else f"{100 * k / n:.1f}%".replace(".", ",")


def line(res: dict) -> str:
    o, n = res["regi"], res["uj"]
    parts = []
    for key, base in (("helyes", "valasz"), ("f1", "valasz"), ("elutasitva", "csapda")):
        name = {"helyes": "teljes egyezés", "f1": "F-1", "elutasitva": "F-2"}[key]
        parts.append(f"{name} {_pct(o.get(key, 0), o.get(base, 0))} → {_pct(n.get(key, 0), n.get(base, 0))}")
    dirs = Counter(c["irany"] for c in res["valtozasok"])
    return (f"{res['futas']} ({res['modell']}, kód {res['kod']}, {res['kerdessor']}): " + " · ".join(parts)
            + f"  [javult {dirs['javult']}, romlott {dirs['romlott']}, más {dirs['más']}]")


def main(argv: list[str] | None = None) -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="A tárolt ① űrlapok a mostani kódon (fejlesztési, optimista).")
    ap.add_argument("futasok", nargs="+", type=Path, help="mérési mappák (logs/meres/…)")
    ap.add_argument("--reszletes", action="store_true", help="kérdésenként is")
    ap.add_argument("--json", type=Path, help="az eredmény JSON-ban ide")
    a = ap.parse_args(argv)
    cat = catalog.load()
    con = connect(DB_PATH, read_only=True)
    wl = catalog.whitelist(cat, con)
    groups = meres._groups_counter(cat, wl, con)
    out = []
    for run in a.futasok:
        res = replay_run(run, cat, wl, con, groups)
        out.append(res)
        print(line(res))
        if a.reszletes:
            for c in res["valtozasok"]:
                print(f"   {c['irany']:7} {c['id']}#{c['ismetles']} {c['regi']} → {c['uj']}  «{c['kerdes'][:60]}»  {c['uj_alak']}")
    if a.json:
        a.json.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
