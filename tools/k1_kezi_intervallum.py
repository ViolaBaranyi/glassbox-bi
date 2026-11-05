"""
A K1 kézi ellenőrzésének bizonytalansága — utólagos, leíró kiegészítés a `docs/k1_kezi_ellenorzes.json`-hoz.

A kézi ellenőrzés (tools/kezi_minta.py) ágonként két réteget mintáz: a második kapu által megjelölt
és meg nem jelölt szövegeket. Ezekből (f = a megjelölt arány a futásban, rögzített):
  * K1 korrigált = f · pontosság + (1 − f) · kihagyás   (a modell szövegeinek alátámasztatlan aránya);
  * a fő ágon a felhasználóhoz eljutó, a kapu által nem látott hiba = (1 − f) · kihagyás
    (a megjelölt szöveg helyett a sablon jut el);
  * a kontrollágon nincs kapu: a felhasználó a modell szövegét kapja, vagyis a K1 korrigált értékét;
  * a kapu hatása: a kontrollág és a fő ág eljutó arányának különbsége és hányadosa.
A pontosságot és a kihagyást rétegenként Jeffreys-féle béta-eloszlással (Beta(k + ½, n − k + ½))
húzzuk, a rétegek és az ágak függetlenek; 40 000 húzás, rögzített mag. Az összevont érték a futások
súlyozatlan átlaga (húzásonként). A meglévő eljutó-intervallum (Wilson-alapú, a megjelölt arányt
rögzítettnek véve) más módszer — ez a táblázat a különbségre és a hányadosra is ad intervallumot.
A beállítások a kézi minták kiértékelése után készültek, ezért ez utólagos, nem előre rögzített elemzés.

    uv run python tools/k1_kezi_intervallum.py       # → docs/k1_kezi_intervallum.json és .md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SRC = ROOT / "docs" / "k1_kezi_ellenorzes.json"
OUT = ROOT / "docs" / "k1_kezi_intervallum.json"
DRAWS = 40_000
SEED = 20261104
MERES = {"v3": "1. mérés (v3)", "v4": "2. mérés (v4)", "v5": "3. mérés (v5)"}


def _beta(rng: np.random.Generator, k: int, n: int, size: int) -> np.ndarray:
    return rng.beta(k + 0.5, n - k + 0.5, size)


def _ci(x: np.ndarray) -> list[float]:
    lo, hi = np.percentile(x, [2.5, 97.5])
    return [float(lo), float(hi)]


def run_draws(agak: dict, rng: np.random.Generator, size: int) -> dict[str, np.ndarray]:
    """Egy futás húzásai: fő ág K1 korrigált, fő ág eljut, kontrollág (= eljut), különbség, hányados."""
    out = {}
    for ag in ("jelolo", "szabad"):
        a = agak[ag]
        f = a["megjelolt_arany"]
        ppv = _beta(rng, a["pontossag"]["k"], a["pontossag"]["n"], size)
        miss = _beta(rng, a["kihagyas"]["k"], a["kihagyas"]["n"], size)
        out[f"{ag}_k1"] = f * ppv + (1 - f) * miss
        if ag == "jelolo":
            out["jelolo_eljut"] = (1 - f) * miss
    out["kulonbseg"] = out["szabad_k1"] - out["jelolo_eljut"]
    out["hanyados"] = out["jelolo_eljut"] / out["szabad_k1"]
    return out


def point(agak: dict) -> dict[str, float]:
    j, s = agak["jelolo"], agak["szabad"]
    fj, fs = j["megjelolt_arany"], s["megjelolt_arany"]
    pj, mj = j["pontossag"]["k"] / j["pontossag"]["n"], j["kihagyas"]["k"] / j["kihagyas"]["n"]
    ps, ms = s["pontossag"]["k"] / s["pontossag"]["n"], s["kihagyas"]["k"] / s["kihagyas"]["n"]
    e = (1 - fj) * mj
    c = fs * ps + (1 - fs) * ms
    return {"jelolo_k1": fj * pj + (1 - fj) * mj, "jelolo_eljut": e, "szabad_k1": c,
            "kulonbseg": c - e, "hanyados": e / c}


KEYS = ("jelolo_k1", "jelolo_eljut", "szabad_k1", "kulonbseg", "hanyados")


def analyze(src: dict, draws: int = DRAWS, seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    rows, pooled = [], {k: [] for k in KEYS}
    for r in src["futasok"]:
        d = run_draws(r["agak"], rng, draws)
        p = point(r["agak"])
        rows.append({"futas": r["futas"], "meres": MERES.get(r["verzio"], r["verzio"]), "modell": r["modell"],
                     **{k: {"becsles": p[k], "ci95": _ci(d[k])} for k in KEYS}})
        for k in KEYS:
            pooled[k].append(d[k])
    pooled_draws = {k: np.mean(v, axis=0) for k, v in pooled.items()}
    pooled_draws["hanyados"] = pooled_draws["jelolo_eljut"] / pooled_draws["szabad_k1"]
    pts = {k: float(np.mean([r[k]["becsles"] for r in rows])) for k in KEYS}
    pts["hanyados"] = pts["jelolo_eljut"] / pts["szabad_k1"]
    return {"modszer": {"huzasok": draws, "mag": seed, "eloszlas": "Jeffreys, Beta(k + 1/2, n - k + 1/2)",
                        "osszevont": "a futások súlyozatlan átlaga (húzásonként); hányados: az átlagok hányadosa"},
            "futasok": rows,
            "osszevont": {k: {"becsles": pts[k], "ci95": _ci(pooled_draws[k])} for k in KEYS}}


def _p(x: float, d: int = 1) -> str:
    return f"{100 * x:.{d}f}".replace(".", ",")


def report(res: dict) -> str:
    head = ("| Futás | Modell | fő ág K1 korr. | fő ág: eljut | kontrollág: eljut | különbség (pp) | hányados |\n"
            "|---|---|---|---|---|---|---|")

    def cell(v: dict, ratio: bool = False) -> str:
        if ratio:
            return f"{v['becsles']:.2f} [{v['ci95'][0]:.2f}; {v['ci95'][1]:.2f}]".replace(".", ",")
        return f"{_p(v['becsles'])} [{_p(v['ci95'][0])}; {_p(v['ci95'][1])}]"

    lines = ["# A K1 kézi ellenőrzésének bizonytalansága (utólagos)", "",
             "Forrás: `docs/k1_kezi_ellenorzes.json`. Jeffreys-féle béta-eloszlás rétegenként, "
             f"{res['modszer']['huzasok']} húzás, mag {res['modszer']['mag']}; a megjelölt arány rögzített. "
             "Eljut: a fő ágon a kapu által nem látott, a kontrollágon minden alátámasztatlan szöveg (a modell "
             "szövege jut el). Különbség: kontrollág − fő ág; hányados: fő ág / kontrollág.", "", head]
    for r in res["futasok"]:
        lines.append(f"| {r['meres']} | {r['modell']} | {cell(r['jelolo_k1'])} | {cell(r['jelolo_eljut'])} | "
                     f"{cell(r['szabad_k1'])} | {cell(r['kulonbseg'])} | {cell(r['hanyados'], True)} |")
    o = res["osszevont"]
    lines.append(f"| összevont (súlyozatlan) | | {cell(o['jelolo_k1'])} | {cell(o['jelolo_eljut'])} | "
                 f"{cell(o['szabad_k1'])} | {cell(o['kulonbseg'])} | {cell(o['hanyados'], True)} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="A K1 kézi ellenőrzésének bizonytalansága (utólagos, leíró).")
    ap.add_argument("--forras", type=Path, default=SRC)
    ap.add_argument("--kimenet", type=Path, default=OUT)
    a = ap.parse_args(argv)
    res = analyze(json.loads(a.forras.read_text(encoding="utf-8")))
    a.kimenet.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    a.kimenet.with_suffix(".md").write_text(report(res), encoding="utf-8")
    print(report(res))


if __name__ == "__main__":
    main()
