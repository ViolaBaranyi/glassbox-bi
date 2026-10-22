"""
A második kapu véletlen átcsúszása: ha a modell egy számot KITALÁL, mekkora eséllyel engedi át
a KAPU ② — mert a kitalált szám véletlenül egyezik az eredmény egy megjelenített értékével?

A rendszerterv egy korai, szintetikus becslést adott (egy kitalált egész százalékérték 9,8%-os
eséllyel csúszik át). Ez az eszköz a valódi tárházon, a lezárt (v5) kapuval méri, modell nélkül.
A beállításokat a futás előtt a döntési napló rögzíti.

  * Eredmények: a három lezárt kérdéssor (eval/meresi_kerdessor*.toml) megválaszolandó
    kérdéseinek fő elvárt értelmezése, a valódi tárházon lefuttatva (üres eredmény kimarad).
  * Nézet: amit a modell a mérésekben látott (rövid nézet); fő ág jelölőkkel, kontrollág nélkülük.
  * Kitalált szám: egyenletes eloszlásból az eredmény mérőszám-értékei (összesített érték és a
    nézet sorai) által kifeszített [0,5 · legkisebb; 1,5 · legnagyobb] tartományból; ha a
    megjelenített alakja az összesített értékével egyezne, újrahúzzuk (az nem kitalált szám).
  * Három alak: (a) a megjelenítés pontosságával és mértékegységével; (b) eggyel kevesebb
    tizedesjeggyel (csak ha a megjelenítés tizedes); (c) mint (b), „kb.” előtaggal (a v5 kapu a
    jelzett kerekítést elfogadja, ha az az eredmény egy értékének kerekítése).
  * Mondat: „Az érték X.” — egyetlen szám, csoportnév nélkül; átcsúszik, ha a kapu átengedi.
  * K húzás kérdésenként, áganként és alakonként; az arány kérdésenként, majd a kérdések átlaga,
    a kérdések feletti bootstrap 95%-os intervallummal.

    uv run python tools/kapu_atcsuszas.py            # → docs/kapu_atcsuszas.json és .md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.db import DB_PATH, connect, use_utf8_console  # noqa: E402
from narrative import meres, proba  # noqa: E402
from narrative.to_text import _rows_for_view, build_view  # noqa: E402
from narrative.verifier import verify  # noqa: E402
from semantic import answer as ans  # noqa: E402
from semantic import catalog, engine  # noqa: E402
from semantic import spec as sp  # noqa: E402

SETS = ("eval/meresi_kerdessor.toml", "eval/meresi_kerdessor_v2.toml", "eval/meresi_kerdessor_v3.toml")
K = 200
SEED = 20261026
CI_SEED = 20261027
LO, HI = 0.5, 1.5
FORMS = ("a", "b", "c")
FORM_NAMES = {"a": "a megjelenítés pontosságával", "b": "eggyel kevesebb tizedessel",
              "c": "eggyel kevesebb tizedessel, „kb.” előtaggal"}
BRANCHES = {"jelolo": "fő ág (jelölők)", "szabad": "kontrollág (szabad)"}
UNIT_NAMES = {"arany": "arány (%)", "nap": "nap", "brl": "BRL", "km": "km", "darab": "darab"}


# ------------------------------------------------------------------ eredmények
def raw_spec(q: dict) -> dict:
    """A kérdés fő elvárt értelmezése a kapu bemeneti alakjában (mint meres.validate)."""
    c = proba.variants(q)[0]
    raw = {"metrika": proba._as_list(c["metrika"])[0]}
    if c["bontas"]:
        raw["bontas"] = list(c["bontas"])
    if c["szuro"]:
        raw["szuro"] = dict(c["szuro"])
    if q.get("idoablak") != "barmely":
        window = {k: c[k] for k in ("tol", "ig") if c.get(k)}
        if window:
            raw["idoablak"] = window
    for key in ("rendezes", "limit"):
        if key in c:
            raw[key] = proba._as_list(c[key])[0] if key == "rendezes" else c[key]
    return raw


def results(cat, wl, con, sets=SETS, root: Path = ROOT) -> list[dict]:
    """A megválaszolandó kérdések eredményei: [{halmaz, id, eredmeny}]; üres eredmény kimarad."""
    out = []
    for path in sets:
        for q in proba.load_questions(root / path):
            if q.get("elutasitas"):
                continue
            g = sp.check(raw_spec(q), cat, wl)
            if not g.ok:
                raise ValueError(f"{path} {q['id']}: az elvárt értelmezést a kapu elutasítja")
            r = engine.run(g.spec, cat, wl, con, g.megjegyzesek)
            if r.empty or r.osszesen["ertek"] is None:
                continue
            out.append({"halmaz": Path(path).stem, "id": q["id"], "eredmeny": r})
    return out


def metric_values(r) -> list[float]:
    """A mérőszám nézetbeli értékei: az összesített érték és a nézet sorai."""
    vals = [float(r.osszesen["ertek"])]
    vals += [float(r.sorok[i]["ertek"]) for i in _rows_for_view(r)] if r.bontas and r.sorok else []
    return vals


def unit_of(r) -> str:
    return str(r.metrika["egyseg"]).lower()


# ------------------------------------------------------------------ kitalált számok
def fmt(metric: dict, v: float, digits: int) -> str:
    return ans.fmt_value({**metric, "tizedes": digits}, v)


def forms_for(r) -> list[str]:
    """Az alakok, amelyek ennél az eredménynél értelmesek: (b) és (c) csak tizedes megjelenítésnél."""
    return list(FORMS) if int(r.metrika["tizedes"]) > 0 else ["a"]


def draw(r, form: str, rng: np.random.Generator) -> str:
    """Egy kitalált szám a mondatba írható alakban; nem egyezhet az összesített érték alakjával."""
    m = r.metrika
    digits = int(m["tizedes"]) - (0 if form == "a" else 1)
    vals = metric_values(r)
    lo, hi = LO * min(vals), HI * max(vals)
    truth = fmt(m, float(r.osszesen["ertek"]), digits)
    for _ in range(1000):
        shown = fmt(m, float(rng.uniform(lo, hi)), digits)
        if shown != truth:
            return ("kb. " if form == "c" else "") + shown
    raise RuntimeError("nem sikerült az összesített értéktől eltérő számot húzni")


def slips(r, text: str, mod: str, view=None) -> bool:
    """Átengedi-e a kapu a kitalált számot tartalmazó mondatot."""
    view = view or build_view(r, placeholders=(mod == "jelolo"), minimal=True)
    v = verify(text, text, view.values, [], r, mod=mod)
    return bool(v.ok)


def measure(items: list[dict], k: int = K, seed: int = SEED) -> list[dict]:
    """Kérdésenként, áganként és alakonként az átcsúszás aránya (k húzásból)."""
    rows = []
    for n, it in enumerate(items):
        r = it["eredmeny"]
        for mod in BRANCHES:
            view = build_view(r, placeholders=(mod == "jelolo"), minimal=True)
            for form in forms_for(r):
                rng = np.random.default_rng([seed, n, list(BRANCHES).index(mod), FORMS.index(form)])
                hits = sum(slips(r, f"Az érték {draw(r, form, rng)}.", mod, view) for _ in range(k))
                rows.append({"halmaz": it["halmaz"], "id": it["id"], "ag": mod, "alak": form,
                             "egyseg": unit_of(r), "ertekek": len(metric_values(r)),
                             "atcsuszas": hits / k})
    return rows


# ------------------------------------------------------------------ összegzés
def mean_ci(values, b: int = 2000, seed: int = CI_SEED) -> dict:
    v = np.asarray(values, dtype=float)
    if len(v) == 0:
        return {"atlag": None, "ci95": [None, None], "n": 0}
    rng = np.random.default_rng(seed)
    boots = v[rng.integers(0, len(v), size=(b, len(v)))].mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"atlag": float(v.mean()), "ci95": [float(lo), float(hi)], "n": int(len(v))}


def size_band(n: int) -> str:
    return "1 érték" if n == 1 else "2–5 érték" if n <= 5 else "6 vagy több érték"


def summarize(rows: list[dict]) -> dict:
    out = {"osszes": {}, "egyseg": {}, "ertekek": {}, "halmaz": {}}
    for mod in BRANCHES:
        for form in FORMS:
            sel = [x for x in rows if x["ag"] == mod and x["alak"] == form]
            if not sel:
                continue
            key = f"{mod}|{form}"
            out["osszes"][key] = mean_ci([x["atcsuszas"] for x in sel])
            for field, group, fn in (("egyseg", "egyseg", lambda x: x["egyseg"]),
                                     ("ertekek", "ertekek", lambda x: size_band(x["ertekek"])),
                                     ("halmaz", "halmaz", lambda x: x["halmaz"])):
                for g in sorted({fn(x) for x in sel}):
                    out[field].setdefault(g, {})[key] = mean_ci([x["atcsuszas"] for x in sel if fn(x) == g])
    return out


def _p(m: dict | None) -> str:
    if not m or m.get("atlag") is None:
        return "—"
    lo, hi = m["ci95"]
    f = lambda x: f"{100 * x:.1f}".replace(".", ",")
    return f"{f(m['atlag'])}% [{f(lo)}; {f(hi)}] (n = {m['n']})"


def report(res: dict) -> str:
    s = res["osszegzes"]
    keys = [f"{mod}|{form}" for mod in BRANCHES for form in FORMS if f"{mod}|{form}" in s["osszes"]]
    head = "| | " + " | ".join(f"{BRANCHES[k.split('|')[0]]}, ({k.split('|')[1]})" for k in keys) + " |"
    sep = "|---|" + "---|" * len(keys)
    L = ["# A második kapu véletlen átcsúszása", "",
         f"Géppel készült (`tools/kapu_atcsuszas.py`), {res['letrehozva']}; modell nélkül, a valódi tárházon, a lezárt "
         f"kapuval (kód-ujjlenyomat `{res['kod_ujjlenyomat'][:16]}…`). {res['eredmenyek']} eredmény a három lezárt "
         f"kérdéssor megválaszolandó kérdéseiből; kérdésenként, áganként és alakonként {res['beallitas']['K']} kitalált "
         f"szám (mag {res['beallitas']['mag']}), a [{res['beallitas']['tartomany'][0]:g}; {res['beallitas']['tartomany'][1]:g}]"
         " · (legkisebb; legnagyobb) tartományból, az összesített érték alakja nélkül. Átcsúszás: a kapu átengedi az "
         "„Az érték X.” mondatot. Az arány kérdésenként, majd a kérdések átlaga, 95%-os bootstrap-intervallummal "
         f"(a kérdések felett, mag {res['beallitas']['ci_mag']}).", "",
         "Alakok: " + "; ".join(f"({k}) {v}" for k, v in FORM_NAMES.items()) + ". A (b) és a (c) csak tizedes "
         "megjelenítésű mérőszámnál értelmezett.", "",
         "## Összesen", "", head, sep,
         "| átcsúszik | " + " | ".join(_p(s["osszes"][k]) for k in keys) + " |"]
    for field, title in (("egyseg", "Mértékegység szerint"), ("ertekek", "A nézet értékeinek száma szerint"),
                         ("halmaz", "Kérdéssor szerint")):
        L += ["", f"## {title}", "", head, sep]
        for g, d in s[field].items():
            name = UNIT_NAMES.get(g, g) if field == "egyseg" else g
            L.append(f"| {name} | " + " | ".join(_p(d.get(k)) for k in keys) + " |")
    return "\n".join(L) + "\n"


def run(con, k: int = K, sets=SETS, root: Path = ROOT) -> dict:
    t0 = time.time()
    cat = catalog.load()
    wl = catalog.whitelist(cat, con)
    items = results(cat, wl, con, sets, root)
    rows = measure(items, k)
    from narrative.client import load_config
    return {"letrehozva": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kod_ujjlenyomat": meres.frozen_fingerprint(load_config()),
            "beallitas": {"K": k, "mag": SEED, "ci_mag": CI_SEED, "tartomany": [LO, HI],
                          "kerdessorok": list(sets), "alakok": FORM_NAMES},
            "eredmenyek": len(items), "sorok": rows, "osszegzes": summarize(rows),
            "ido_mp": round(time.time() - t0, 1)}


def main(argv: list[str] | None = None) -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="A második kapu véletlen átcsúszása (modell nélkül).")
    ap.add_argument("--k", type=int, default=K, help="kitalált számok kérdésenként, áganként, alakonként")
    ap.add_argument("--kimenet", type=Path, default=ROOT / "docs" / "kapu_atcsuszas.json")
    a = ap.parse_args(argv)
    con = connect(DB_PATH, read_only=True)
    res = run(con, a.k)
    con.close()
    a.kimenet.parent.mkdir(parents=True, exist_ok=True)
    a.kimenet.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    a.kimenet.with_suffix(".md").write_text(report(res), encoding="utf-8")
    print(f"Eredmény: {a.kimenet} (és {a.kimenet.with_suffix('.md').name}); {res['ido_mp']} mp")


if __name__ == "__main__":
    main()
