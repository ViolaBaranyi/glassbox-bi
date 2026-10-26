"""
A döntés stabilitása (K3/K4 kiegészítés): ha a tanítóadat kicsit változik, mennyire marad ugyanaz
a „legkockázatosabb 10%” — az a lista, amelyre egy logisztikus ügyintéző beavatkozna?

A K3 (xai/stability.py) a MAGYARÁZAT stabilitását mérte a 20 bootstrap-újratanításon és az 5
kontroll-magon. Ez az eszköz ugyanazokon a modelleken (ugyanazok a minták és magok, a lezárt
beállítások — a modellek bitre azonosak a K3-éival) a DÖNTÉSÉT méri, az időbeli teszt összes
rendelésén. Rokon fogalom: prediktív többértelműség (Marx, Calmon és Ustun, 2020) — közel azonos
pontosságú modellek eltérő döntései.

Modellenként, a lezárt modell listájához mérve:
  * átfedés: a felső 10% hányada marad a felső 10%-ban (mintánként; átlag, legkisebb);
  * stabil mag: a lezárt felső 10% hányada, amely MINDEN újratanított modellnél a felső 10%-ban van;
  * többértelműség: a teszt-rendelések hányada, amelyek tagsága legalább egy modellnél eltér;
  * legnagyobb eltérés: egyetlen modellnél a legtöbb tagság-változás (a rendelések hányadában);
  * a 200 legkockázatosabb rendelés (a felület listája) átfedése;
  * a becslések rangkorrelációja (Spearman);
  * a modellek teljesítménye (PR-AUC, a felső 10% a késések ennyiedét fogja) — a teszt-címke
    csak itt szerepel, leíró; semmit nem választunk vele.
A modellek páronkénti különbsége az átfedésben mintánként párosítva (ugyanaz az i. minta mind a
négy modellnél), a minták feletti bootstrap 95%-os intervallummal. A beállítások a futás előtt
a döntési naplóban.

    uv run python tools/dontesi_stabilitas.py               # → docs/dontesi_stabilitas.json és .md
    uv run python tools/dontesi_stabilitas.py --bootstrap 2 --magok 1 --kimenet artifacts/dontes_proba.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import average_precision_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.db import DB_PATH, use_utf8_console  # noqa: E402
from xai import stability as st  # noqa: E402
from xai.models import KINDS, NAMES, Bundle, load_bundle  # noqa: E402

TOP_SHARE = 0.10
UI_LIST = 200
CI_SEED = 20261102
B = 2000
# Előre rögzített sejtés (a döntési naplóban, a futás előtt): a felső 10% átfedése (bootstrap) a K3
# magyarázat-stabilitásának sorrendjét követi — LR > LightGBM, LR > RF, LightGBM > fa, RF > fa,
# LR > fa; a LightGBM és az RF sorrendjéről nincs előzetes állítás.
HYPOTHESIS = st.HYPOTHESIS


def top_mask(p: np.ndarray, n_top: int) -> np.ndarray:
    """A legnagyobb `n_top` becslés helye (holtversenyben az eredeti sorrend — determinisztikus)."""
    m = np.zeros(len(p), dtype=bool)
    m[np.argsort(-p, kind="stable")[:n_top]] = True
    return m


def capture(y: np.ndarray, mask: np.ndarray) -> float:
    return float(y[mask].sum() / y.sum()) if y.sum() else float("nan")


def decision_metrics(ref_p: np.ndarray, others: list[np.ndarray], share: float = TOP_SHARE,
                     ui_list: int = UI_LIST) -> dict:
    """A lezárt modell listájához mért döntési stabilitás (mintánkénti értékekkel)."""
    n = len(ref_p)
    n_top = max(1, int(round(share * n)))
    ref = top_mask(ref_p, n_top)
    n_ui = min(ui_list, n)
    ref_ui = top_mask(ref_p, n_ui)
    masks = [top_mask(p, n_top) for p in others]
    overlap = [float((m & ref).sum() / n_top) for m in masks]
    differs = np.zeros(n, dtype=bool)
    in_all = ref.copy()
    for m in masks:
        differs |= m != ref
        in_all &= m
    return {
        "n": int(n), "felso_n": int(n_top),
        "atfedes": overlap,
        "stabil_mag": float(in_all.sum() / n_top) if masks else float("nan"),
        "tobbertelmuseg": float(differs.mean()) if masks else float("nan"),
        "legnagyobb_elteres": float(max((m != ref).mean() for m in masks)) if masks else float("nan"),
        "ui_atfedes": [float((top_mask(p, n_ui) & ref_ui).sum() / n_ui) for p in others],
        "spearman": [float(spearmanr(ref_p, p).statistic) for p in others],
    }


def _mean_ci(values, seed: int = CI_SEED, b: int = B) -> dict:
    a = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    boots = a[rng.integers(0, len(a), (b, len(a)))].mean(axis=1) if len(a) > 1 else np.array([a.mean()])
    return {"ertek": float(a.mean()), "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "min": float(a.min()), "max": float(a.max())}


def run(b: Bundle, kinds=KINDS, n_boot: int = st.N_BOOT, control_seeds=st.CONTROL_SEEDS, verbose: bool = True) -> dict:
    t_start = time.time()
    kinds = tuple(kinds)

    def log(msg):
        if verbose:
            print(f"[{time.time() - t_start:6.0f} mp] {msg}", flush=True)

    te = b.split.test.sort_values()
    Xte, yte = b.X.loc[te], b.y.loc[te].to_numpy(dtype=float)
    ref_p = {k: b.models[k].predict_proba(Xte)[:, 1] for k in kinds}
    boot_p = {k: [] for k in kinds}
    ctrl_p = {k: [] for k in kinds}
    seed = int(b.info.get("mag", 42))
    for i in range(n_boot):
        models = st.fit_models(b, st.bootstrap_index(b, i), seed, kinds)
        for k in kinds:
            boot_p[k].append(models[k].predict_proba(Xte)[:, 1])
        log(f"bootstrap {i + 1}/{n_boot}")
    for s in control_seeds:
        models = st.fit_models(b, b.train_idx, int(s), kinds)
        for k in kinds:
            ctrl_p[k].append(models[k].predict_proba(Xte)[:, 1])
        log(f"kontroll (mag {s})")

    n_top = max(1, int(round(TOP_SHARE * len(te))))
    out = {}
    for k in kinds:
        dm = decision_metrics(ref_p[k], boot_p[k])
        dc = decision_metrics(ref_p[k], ctrl_p[k]) if ctrl_p[k] else None
        perf = {"pr_auc": [float(average_precision_score(yte, p)) for p in boot_p[k]],
                "felso10": [capture(yte, top_mask(p, n_top)) for p in boot_p[k]]}
        out[k] = {
            "nev": NAMES[k],
            "bootstrap": {**{m: dm[m] for m in ("stabil_mag", "tobbertelmuseg", "legnagyobb_elteres")},
                          "atfedes": _mean_ci(dm["atfedes"]), "ui_atfedes": _mean_ci(dm["ui_atfedes"]),
                          "spearman": _mean_ci(dm["spearman"]), "mintankent_atfedes": dm["atfedes"]},
            "kontroll_mag": None if dc is None else {
                **{m: dc[m] for m in ("stabil_mag", "tobbertelmuseg", "legnagyobb_elteres")},
                "atfedes": _mean_ci(dc["atfedes"]), "ui_atfedes": _mean_ci(dc["ui_atfedes"]),
                "spearman": _mean_ci(dc["spearman"])},
            "teljesitmeny": {"lezart": {"pr_auc": float(average_precision_score(yte, ref_p[k])),
                                        "felso10": capture(yte, top_mask(ref_p[k], n_top))},
                             "bootstrap": {m: _mean_ci(v) for m, v in perf.items()}},
        }
    pairs = {}
    for a, c in HYPOTHESIS["pairs"] + HYPOTHESIS["nyitott"]:
        if a in out and c in out:
            d = np.asarray(out[a]["bootstrap"]["mintankent_atfedes"]) - np.asarray(out[c]["bootstrap"]["mintankent_atfedes"])
            pairs[f"{a}-{c}"] = {**_mean_ci(d), "elozetes_sejtes": "nagyobb" if (a, c) in HYPOTHESIS["pairs"] else "nincs"}
            pairs[f"{a}-{c}"]["olvasat"] = st.verdict(pairs[f"{a}-{c}"])

    return {
        "letrehozva": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kod_ujjlenyomat": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "beallitas": {"bootstrap": n_boot, "bootstrap_mag": st.BOOT_SEED, "kontroll_magok": list(control_seeds),
                      "modell_mag": seed, "felso_hanyad": TOP_SHARE, "felso_n": int(n_top), "felulet_lista": UI_LIST,
                      "teszt_rendelesek": int(len(te)), "teszt_kesesi_arany": float(yte.mean()),
                      "ci_mag": CI_SEED, "B": B, "modellek": list(kinds)},
        "adat": {k: v for k, v in b.info.items() if k in ("adatforras", "tarhaz_epitve", "lightgbm_fak")},
        "modellek": out,
        "parok_atfedes": pairs,
        "ido_mp": round(time.time() - t_start, 1),
    }


# ------------------------------------------------------------------ jelentés
def _n(x: float, d: int = 2) -> str:
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def _pct(x: float, d: int = 1) -> str:
    return _n(100 * x, d) + "%"


def _ci(m: dict, pct: bool = True) -> str:
    f = _pct if pct else (lambda v: _n(v, 3))
    return f"{f(m['ertek'])} [{f(m['ci95'][0])}; {f(m['ci95'][1])}]"


def report(res: dict, k3: dict | None = None) -> str:
    s = res["beallitas"]
    L = ["# A döntés stabilitása — mennyire marad ugyanaz a legkockázatosabb 10%?", "",
         f"Készült: {res['letrehozva']} · kód-ujjlenyomat `{res['kod_ujjlenyomat'][:16]}…` · {res['ido_mp']:.0f} mp. "
         f"Az előre rögzített beállítások: döntési napló.", "",
         f"Az időbeli teszt {s['teszt_rendelesek']} rendelése (késési arány {_pct(s['teszt_kesesi_arany'])}); a felső 10% = "
         f"{s['felso_n']} rendelés. {s['bootstrap']} bootstrap-újratanítás (mag {s['bootstrap_mag']} + i) és "
         f"{len(s['kontroll_magok'])} kontroll-mag — ugyanazok a modellek, mint a K3-ban. Szögletes zárójelben 95%-os "
         f"intervallum a minták felett.", "",
         "## Új tanítóadaton (bootstrap)", "",
         "| modell | a felső 10% átfedése | legkisebb | stabil mag | többértelműség | legnagyobb eltérés | "
         "a 200-as lista átfedése | Spearman |", "|---|---|---|---|---|---|---|---|"]
    for k, m in res["modellek"].items():
        bt = m["bootstrap"]
        L.append(f"| {m['nev']} | {_ci(bt['atfedes'])} | {_pct(bt['atfedes']['min'])} | {_pct(bt['stabil_mag'])} | "
                 f"{_pct(bt['tobbertelmuseg'])} | {_pct(bt['legnagyobb_elteres'])} | {_ci(bt['ui_atfedes'])} | "
                 f"{_n(bt['spearman']['ertek'], 3)} |")
    L += ["", "*Stabil mag:* a lezárt felső 10% mekkora része van minden újratanított modellnél is a felső 10%-ban. "
          "*Többértelműség:* a teszt-rendelések mekkora részének a besorolása (felső 10% vagy sem) tér el legalább egy "
          "modellnél. *Legnagyobb eltérés:* egyetlen modellnél a legtöbb átsorolás.", "",
          "## Viszonyítás: ugyanaz az adat, más tanítási mag", "",
          "| modell | a felső 10% átfedése | stabil mag | többértelműség | a 200-as lista átfedése |", "|---|---|---|---|---|"]
    for k, m in res["modellek"].items():
        c = m["kontroll_mag"]
        if c:
            L.append(f"| {m['nev']} | {_ci(c['atfedes'])} | {_pct(c['stabil_mag'])} | {_pct(c['tobbertelmuseg'])} | "
                     f"{_ci(c['ui_atfedes'])} |")
    L += ["", "## A modellek teljesítménye ugyanezeken az újratanításokon (leíró)", "",
          "| modell | PR-AUC (lezárt) | PR-AUC (újratanítva; legkisebb – legnagyobb) | felső 10% fogása (lezárt) | "
          "felső 10% fogása (újratanítva; legkisebb – legnagyobb) |", "|---|---|---|---|---|"]
    for k, m in res["modellek"].items():
        t = m["teljesitmeny"]
        L.append(f"| {m['nev']} | {_n(t['lezart']['pr_auc'], 3)} | {_n(t['bootstrap']['pr_auc']['ertek'], 3)} "
                 f"({_n(t['bootstrap']['pr_auc']['min'], 3)} – {_n(t['bootstrap']['pr_auc']['max'], 3)}) | "
                 f"{_pct(t['lezart']['felso10'])} | {_pct(t['bootstrap']['felso10']['ertek'])} "
                 f"({_pct(t['bootstrap']['felso10']['min'])} – {_pct(t['bootstrap']['felso10']['max'])}) |")
    L += ["", "## Páros összevetés: a felső 10% átfedése (A − B, mintánként párosítva)", "",
          "| pár | különbség | előzetes sejtés | olvasat |", "|---|---|---|---|"]
    for key, p in res["parok_atfedes"].items():
        a, c = key.split("-")
        L.append(f"| {NAMES[a]} − {NAMES[c]} | {_n(100 * p['ertek'], 1)} pp [{_n(100 * p['ci95'][0], 1)}; "
                 f"{_n(100 * p['ci95'][1], 1)}] | {'A stabilabb' if p['elozetes_sejtes'] == 'nagyobb' else 'nincs'} | "
                 f"{p['olvasat']} |")
    if k3:
        L += ["", "## Mellette: a magyarázat stabilitása (K3, ugyanezeken a modelleken)", "",
              "| modell | a felső 10% átfedése | a magyarázat RBO-ja (K3) |", "|---|---|---|"]
        for k, m in res["modellek"].items():
            if k in k3.get("modellek", {}):
                L.append(f"| {m['nev']} | {_pct(m['bootstrap']['atfedes']['ertek'])} | "
                         f"{_n(k3['modellek'][k]['bootstrap']['rbo']['atlag'], 2)} |")
    L.append("")
    return "\n".join(L)


def _k3():
    p = ROOT / "docs" / "stabilitas_eredmeny.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main(argv: list[str] | None = None) -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="A döntés stabilitása a K3 újratanított modelljein.")
    ap.add_argument("--bootstrap", type=int, default=st.N_BOOT)
    ap.add_argument("--magok", type=int, default=len(st.CONTROL_SEEDS))
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--kimenet", type=Path, default=ROOT / "docs" / "dontesi_stabilitas.json")
    ap.add_argument("--jelentes", type=Path, default=None, help="csak a .md újraírása egy meglévő JSON-ból")
    a = ap.parse_args(argv)
    if a.jelentes:
        res = json.loads(a.jelentes.read_text(encoding="utf-8"))
        a.jelentes.with_suffix(".md").write_text(report(res, _k3()), encoding="utf-8")
        return
    full = a.bootstrap == st.N_BOOT and a.magok == len(st.CONTROL_SEEDS)
    if not full and a.kimenet.resolve().parent == (ROOT / "docs").resolve():
        sys.exit("Próbafutás (nem az előre rögzített beállítás) nem írhat a docs/ mappába — adj meg --kimenet-et.")
    b = load_bundle(a.db, verbose=True)
    res = run(b, n_boot=a.bootstrap, control_seeds=st.CONTROL_SEEDS[:a.magok])
    a.kimenet.parent.mkdir(parents=True, exist_ok=True)
    a.kimenet.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    a.kimenet.with_suffix(".md").write_text(report(res, _k3()), encoding="utf-8")
    print(f"Eredmény: {a.kimenet} (és {a.kimenet.with_suffix('.md').name}); {res['ido_mp']} mp")


if __name__ == "__main__":
    main()
