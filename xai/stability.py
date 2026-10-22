"""
A magyarázatok stabilitása (K3): mennyire marad ugyanaz a felület magyarázata, ha a tanítóadat
kicsit változik — és (a CIES-szel való kapcsolatként) ha a rendelés számadatai kicsit változnak.

1. Fő mérés — a tanítóadat újramintázása (bootstrap-újratanítás)
   A tisztított tanító ablakból N_BOOT-szor húzunk ugyanakkora mintát visszatevéssel (sorok
   szerint; az i. minta magja BOOT_SEED + i), és a négy modellt a lezárt beállításokkal
   (LightGBM 119 fa, C = 0,1, mélység 10, levélméret 10, mag 42) újratanítjuk. Mindegyik
   magyarázatát — pontosan a felületé: a modell saját magyarázója, százalékpontra átváltva, 21
   megjelenítési tényező — a kontrollkar 200 rögzített teszt-rendelésén vesszük (a felület
   500 soros háttere), és a lezárt modell magyarázatához mérjük rendelésenként:
     rbo (p = 0,9) · súlyozott Kendall-tau · top-3 egyezés · a top-3 iránya ·
     cies-súlyozott egyezés (1 − Σ w·|Δ| / Σ w·|φ|, harmonikus rangsúly — a CIES távolsága)
   Rendelésenként a minták átlaga, majd a rendelések átlaga 95%-os bootstrap-intervallummal
   (a rendelések újramintavételével). Mellé: a globális rangsor (a 200 rendelés átlagos
   |hatása|) egyezése, és mennyit mozdul a becslés (százalékpont) — címke nélkül.
   Viszonyítás (a tanítás saját zaja): ugyanaz az adat, más tanítási mag (CONTROL_SEEDS).
   A modellek páronkénti különbsége rendelésenként párosítva (K4).

2. Kiegészítés — a CIES eredeti meghatározása (Văduva, Oprea és Bâra, 2026, előzetes közlemény)
   A lezárt modellek, ugyanaz a 200 rendelés; minden rendeléshez M szomszéd: a számszerű
   jellemzők x_j + N(0, (α·|x_j|)²) zajjal (nullánál σ = α), a kategóriák és a logikai
   jellemzők változatlanok. CIES(x) = max(0, 1 − átlag_m d_w(φ(x), φ(x'_m)) / ‖φ(x)‖_w),
   d_w = Σ w_j |φ_j − φ'_j|, w_j = (1/r_j) / Σ(1/r_k), r_j a |φ_j(x)| szerinti helyezés.
   Fő beállítás α = 0,03, M = 10; érzékenység: α = 0,01 és 0,05 (M = 5). Ugyanazok a zajos
   szomszédok mind a négy modellnél.

A paraméterek a futás előtt a döntési naplóba kerültek. A valódi teszt-címkét egyik mérés sem
használja; a kimenet rendelés-azonosítót nem tartalmaz (a részhalmaz ujjlenyomatát igen).

    python -m xai.stability                       # a teljes, rögzített futás → docs/stabilitas_eredmeny.*
    python -m xai.stability --bootstrap 2 --magok 1 --rendelesek 20 --cies-m 2   # gyors próba → artifacts/
    python -m xai.stability --jelentes docs/stabilitas_eredmeny.json             # csak a .md újraírása
    python -m xai.stability --feltaro-kerekites docs/stabilitas_eredmeny.json    # utólagos, feltáró (kb. 13 perc)
    python -m xai.stability --feltaro-honap docs/stabilitas_eredmeny.json        # utólagos, feltáró (kb. 13 perc)
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from data.db import DB_PATH, WarehouseUnavailable, use_utf8_console
from pipeline import reference_models as rm
from pipeline.features import NUMERIC_FEATURES
from pipeline.model_selection import fit_fixed, model_params
from xai import agreement as ag
from xai import kernel_arm as ka
from xai import narrative as nv
from xai.explain import explain, percentage_points
from xai.models import KINDS, NAMES, Bundle, load_bundle

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ARTIFACTS = ROOT / "artifacts"

N_BOOT = 20
BOOT_SEED = 20261023
CONTROL_SEEDS = (1, 2, 3, 4, 5)
CIES_ALPHA = 0.03
CIES_M = 10
CIES_SENS = {0.01: 5, 0.05: 5}
CIES_SEED = 20261024
CI_SEED = 20261025
METRICS = ("rbo", "wtau", "top3", "elojel3", "cies")
# Előre rögzített sejtés (K4): a legstabilabbtól a legkevésbé stabilig; a LightGBM és a random
# forest sorrendjéről nincs előzetes állítás.
HYPOTHESIS = {"pairs": [("logreg", "lightgbm"), ("logreg", "random_forest"), ("lightgbm", "dontesi_fa"),
                        ("random_forest", "dontesi_fa"), ("logreg", "dontesi_fa")],
              "nyitott": [("lightgbm", "random_forest")]}


# ------------------------------------------------------------------ mértékek
def _weights(phi: np.ndarray) -> np.ndarray:
    """Harmonikus rangsúly a |φ| szerinti helyezésből (1 = a legnagyobb), soronként 1-re normálva."""
    ranks = np.argsort(np.argsort(-np.abs(phi), axis=1, kind="stable"), axis=1) + 1
    w = 1.0 / ranks
    return w / w.sum(axis=1, keepdims=True)


def cies(ref: pd.DataFrame, others: list[pd.DataFrame]) -> pd.Series:
    """CIES soronként: max(0, 1 − átlag_m Σ w·|φ − φ'_m| / Σ w·|φ|) — a w a ref rangsorából."""
    a = ref.to_numpy(dtype=float)
    w = _weights(a)
    d = np.mean([(w * np.abs(a - o.loc[ref.index, ref.columns].to_numpy(dtype=float))).sum(axis=1)
                 for o in others], axis=0)
    norm = (w * np.abs(a)).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        score = np.where(norm > 0, np.maximum(0.0, 1.0 - d / norm), np.nan)
    return pd.Series(score, index=ref.index)


def compare(ref: pd.DataFrame, other: pd.DataFrame) -> pd.DataFrame:
    """Rendelésenként a mértékek: other a ref-hez mérve (a ref a viszonyítási alap)."""
    t = ag.compare_frames(other[ref.columns], ref)
    t["cies"] = cies(ref, [other])
    return t[list(METRICS) + ["rel_l1"]]


def global_ranking(pp: pd.DataFrame) -> list:
    return list(pp.abs().mean().sort_values(ascending=False, kind="stable").index)


# ------------------------------------------------------------------ modellek és magyarázat
def fit_models(b: Bundle, idx, seed: int, kinds=KINDS) -> dict:
    """A négy modell a lezárt beállításokkal a megadott (akár ismétlődő) tanító sorokon."""
    Xtr, ytr = b.X.loc[idx], b.y.loc[idx]
    models = {}
    for kind in kinds:
        if kind == "lightgbm":
            models[kind] = fit_fixed(model_params(seed), Xtr, ytr, int(b.info["lightgbm_fak"]))
        else:
            models[kind] = rm.make_model(kind, b.info["referencia"][kind], seed).fit(Xtr, ytr)
    return models


def ui_explanation(kind: str, model, rows: pd.DataFrame, bg: pd.DataFrame) -> pd.DataFrame:
    """Pontosan a felület magyarázata: 21 megjelenítési tényező, százalékpontban."""
    return nv.merge_display(percentage_points(explain(kind, model, rows, bg)))


def bootstrap_index(b: Bundle, i: int, seed: int = BOOT_SEED) -> pd.Index:
    rng = np.random.default_rng(seed + i)
    n = len(b.train_idx)
    return b.train_idx[rng.integers(0, n, n)]


def perturb(rows: pd.DataFrame, alpha: float, rng: np.random.Generator, round_cols=()) -> pd.DataFrame:
    """A CIES zaja: a számszerű jellemzők x + N(0, (α·|x|)²) (nullánál σ = α); a többi változatlan.

    round_cols: a zaj UTÁN egészre kerekített oszlopok (a feltáró, „valószerű” változat); a
    véletlen húzások ettől nem változnak, így a kerekített és a kerekítetlen szomszéd párosítható."""
    out = rows.copy()
    for col in NUMERIC_FEATURES:
        x = out[col].to_numpy(dtype=float)
        sigma = np.where(x == 0, alpha, alpha * np.abs(x))
        out[col] = x + rng.standard_normal(len(x)) * sigma
    for col in round_cols:
        out[col] = np.round(out[col].to_numpy(dtype=float)) + 0.0          # −0,0 → 0,0
    return out


def integer_features(b: Bundle) -> list:
    """A számszerű jellemzők közül azok, amelyek a tanítóadatban mindig egész értékűek (darab, nap…)."""
    Xtr = b.X.loc[b.train_idx]
    return [c for c in NUMERIC_FEATURES
            if np.all(np.isclose(Xtr[c].dropna().to_numpy(dtype=float) % 1, 0))]


# ------------------------------------------------------------------ összegzés
def summarize(tables: list[pd.DataFrame], n_boot: int = 2000, seed: int = CI_SEED) -> dict:
    """Minták × rendelések: rendelésenként a minták átlaga, majd a rendelések átlaga 95% CI-vel;
    mellé a mintánkénti átlagok (a minták közötti szórás látszik)."""
    stacked = pd.concat(tables, keys=range(len(tables)), names=["minta", "rendeles"])
    per_order = stacked.groupby(level="rendeles").mean()
    out = {m: ag.mean_ci(per_order[m], n_boot, seed) for m in METRICS}
    out["mintankent"] = {m: [float(t[m].mean()) for t in tables] for m in METRICS}
    out["rel_l1"] = ag.mean_ci(per_order["rel_l1"], n_boot, seed)
    return out, per_order


def paired_diff(a: pd.Series, b: pd.Series, n_boot: int = 2000, seed: int = CI_SEED) -> dict:
    common = a.index.intersection(b.index)
    return ag.mean_ci((a.loc[common] - b.loc[common]).to_numpy(), n_boot, seed)


def verdict(pair: dict) -> str:
    """A páros különbség olvasata a 95%-os intervallumból (A − B > 0: A stabilabb).

    Sejtésnél: „teljesült” (az intervallum 0 fölött), „fordított” (0 alatt), „nem dönthető el”
    (tartalmazza a 0-t). Nyitott párnál: „A stabilabb”, „B stabilabb” vagy „nincs kimutatható
    különbség”."""
    lo, hi = pair["ci95"]
    if pair.get("elozetes_sejtes") == "nagyobb":
        return "teljesült" if lo > 0 else "fordított" if hi < 0 else "nem dönthető el"
    return "A stabilabb" if lo > 0 else "B stabilabb" if hi < 0 else "nincs kimutatható különbség"


# ------------------------------------------------------------------ futás
def run(b: Bundle, kinds=KINDS, n_boot: int = N_BOOT, control_seeds=CONTROL_SEEDS, n_orders: int = ka.N_ORDERS,
        cies_m: int = CIES_M, cies_sens: dict | None = None, verbose: bool = True) -> dict:
    t_start = time.time()
    kinds = tuple(kinds)
    cies_sens = CIES_SENS if cies_sens is None else cies_sens

    def log(msg):
        if verbose:
            print(f"[{time.time() - t_start:6.0f} mp] {msg}", flush=True)

    rows = ka.order_subset(b, n_orders)
    bg = b.background()
    ref = {k: ui_explanation(k, b.models[k], rows, bg) for k in kinds}
    ref_p = {k: b.models[k].predict_proba(rows)[:, 1] for k in kinds}
    boot_tables = {k: [] for k in kinds}
    boot_global = {k: [] for k in kinds}
    boot_dp = {k: [] for k in kinds}
    for i in range(n_boot):
        t0 = time.time()
        models = fit_models(b, bootstrap_index(b, i), int(b.info.get("mag", 42)), kinds)
        for k in kinds:
            pp = ui_explanation(k, models[k], rows, bg)
            boot_tables[k].append(compare(ref[k], pp))
            boot_global[k].append(global_ranking(pp))
            boot_dp[k].append(float(np.mean(np.abs(models[k].predict_proba(rows)[:, 1] - ref_p[k])) * 100.0))
        log(f"bootstrap {i + 1}/{n_boot}: {time.time() - t0:.0f} mp")
    ctrl_tables = {k: [] for k in kinds}
    ctrl_dp = {k: [] for k in kinds}
    for s in control_seeds:
        t0 = time.time()
        models = fit_models(b, b.train_idx, int(s), kinds)
        for k in kinds:
            ctrl_tables[k].append(compare(ref[k], ui_explanation(k, models[k], rows, bg)))
            ctrl_dp[k].append(float(np.mean(np.abs(models[k].predict_proba(rows)[:, 1] - ref_p[k])) * 100.0))
        log(f"kontroll (mag {s}): {time.time() - t0:.0f} mp")

    out_models, per_order_rbo = {}, {}
    for k in kinds:
        boot, per_order = summarize(boot_tables[k])
        ctrl, _ = summarize(ctrl_tables[k]) if ctrl_tables[k] else ({}, None)
        g_ref = global_ranking(ref[k])
        out_models[k] = {
            "nev": NAMES[k],
            "bootstrap": boot,
            "kontroll_mag": ctrl,
            "globalis": {
                "referencia_top5": g_ref[:5],
                "rbo": ag.mean_ci([ag.rbo(g, g_ref, 0.9) for g in boot_global[k]], 2000, CI_SEED),
                "rbo_min": float(min(ag.rbo(g, g_ref, 0.9) for g in boot_global[k])) if boot_global[k] else None,
                "top3_azonos": float(np.mean([set(g[:3]) == set(g_ref[:3]) for g in boot_global[k]]))
                if boot_global[k] else None,
                "elso_azonos": float(np.mean([g[0] == g_ref[0] for g in boot_global[k]])) if boot_global[k] else None,
            },
            "becsles_valtozas_pp": {"bootstrap": float(np.mean(boot_dp[k])) if boot_dp[k] else None,
                                    "kontroll_mag": float(np.mean(ctrl_dp[k])) if ctrl_dp[k] else None},
        }
        per_order_rbo[k] = per_order["rbo"]
    pairs = {}
    for a, c in HYPOTHESIS["pairs"] + HYPOTHESIS["nyitott"]:
        if a in per_order_rbo and c in per_order_rbo:
            pairs[f"{a}-{c}"] = {**paired_diff(per_order_rbo[a], per_order_rbo[c]),
                                 "elozetes_sejtes": "nagyobb" if (a, c) in HYPOTHESIS["pairs"] else "nincs"}

    # 2. a CIES eredeti meghatározása (bemeneti zaj)
    cies_out = {}
    rng = np.random.default_rng(CIES_SEED)
    for alpha, m in [(CIES_ALPHA, cies_m)] + [(a, n) for a, n in cies_sens.items()]:
        t0 = time.time()
        neighbors = [perturb(rows, alpha, rng) for _ in range(m)]
        res = {}
        for k in kinds:
            score = cies(ref[k], [ui_explanation(k, b.models[k], nb, bg) for nb in neighbors])
            res[k] = {**ag.mean_ci(score.to_numpy(), 2000, CI_SEED), "szoras": float(np.nanstd(score.to_numpy()))}
        cies_out[f"{alpha:g}"] = {"alpha": alpha, "M": m, "modellek": res}
        log(f"CIES α = {alpha:g}, M = {m}: {time.time() - t0:.0f} mp")

    return {
        "letrehozva": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "beallitasok": {
            "bootstrap": n_boot, "bootstrap_mag": BOOT_SEED, "kontroll_magok": list(control_seeds),
            "rendelesek": int(len(rows)), "rendeles_mag": ka.ORDER_SEED,
            "rendeles_ujjlenyomat": ka.subset_fingerprint(b, rows.index),
            "hatter": int(len(bg)), "tanito_sorok": int(len(b.train_idx)),
            "modell_mag": int(b.info.get("mag", 42)), "rbo_p": 0.9,
            "cies": {"alpha": CIES_ALPHA, "M": cies_m, "erzekenyseg": {f"{a:g}": n for a, n in cies_sens.items()},
                     "mag": CIES_SEED},
            "ci_mag": CI_SEED,
        },
        "adat": {k: v for k, v in b.info.items() if k in ("adatforras", "tarhaz_epitve", "lightgbm_fak")},
        "modellek": out_models,
        "parok_rbo": pairs,
        "cies_bemeneti_zaj": cies_out,
        "kornyezet": {"python": platform.python_version(), "gep": platform.platform()},
        "ido_mp": round(time.time() - t_start, 1),
    }


MONTH_FEATURES = ("honap_sin", "honap_cos")


def exploratory_rounded_cies(b: Bundle, kinds=KINDS, n_orders: int = ka.N_ORDERS, m: int = CIES_M,
                             alpha: float = CIES_ALPHA, keep_cols=(), verbose: bool = True) -> dict:
    """UTÓLAGOS, FELTÁRÓ ellenőrzés (nem előre rögzített): a fő CIES-futás α = 0,03-as szomszédjai
    (ugyanaz a mag, ugyanazok a húzások), de az egész értékű jellemzők a zaj után egészre kerekítve
    — így nincs „1,02 tétel” vagy „0,03 korábbi rendelés”. A kérdés: mennyi a CIES-ből a valóságban
    nem előforduló bemenetek hatása. keep_cols: ezek az oszlopok egyáltalán nem kapnak zajt (a
    húzások ettől sem változnak; pl. a hónap körkódolása, amely a valóságban nem „zajos”).
    Ellenőrzésként a kerekítetlen LightGBM-értéket is újraszámolja (egyeznie kell a fő futáséval)."""
    t0 = time.time()
    rows = ka.order_subset(b, n_orders)
    bg = b.background()
    ints = integer_features(b)
    rng = np.random.default_rng(CIES_SEED)                    # a fő futás első zajszintje is így indult
    raw = [perturb(rows, alpha, rng) for _ in range(m)]
    rounded = [nb.copy() for nb in raw]
    for nb in rounded:
        for col in ints:
            nb[col] = np.round(nb[col].to_numpy(dtype=float)) + 0.0
        for col in keep_cols:
            nb[col] = rows[col]
    res = {}
    for k in kinds:
        ref = ui_explanation(k, b.models[k], rows, bg)
        score = cies(ref, [ui_explanation(k, b.models[k], nb, bg) for nb in rounded])
        res[k] = {**ag.mean_ci(score.to_numpy(), 2000, CI_SEED), "szoras": float(np.nanstd(score.to_numpy()))}
        if verbose:
            print(f"[{time.time() - t0:6.0f} mp] kerekített CIES: {k}", flush=True)
    check = None
    if "lightgbm" in kinds:
        ref = ui_explanation("lightgbm", b.models["lightgbm"], rows, bg)
        check = float(np.nanmean(cies(ref, [ui_explanation("lightgbm", b.models["lightgbm"], nb, bg)
                                              for nb in raw]).to_numpy()))
    return {"jelleg": "utólagos, feltáró (nem előre rögzített)", "alpha": alpha, "M": m,
            "kerekitett_jellemzok": ints, "zaj_nelkuli_jellemzok": list(keep_cols), "modellek": res, "ellenorzes_lightgbm_kerekitetlen": check,
            "ido_mp": round(time.time() - t0, 1)}


# ------------------------------------------------------------------ jelentés
def _f(x, d: int = 2) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x:.{d}f}".replace(".", ",").replace("-", "\u2212")


def _name(f: str) -> str:
    return nv.DISPLAY_SHORT.get(f) or nv.SHORT.get(f, f)


def _ci(m: dict, d: int = 2) -> str:
    if not m or m.get("n", 0) == 0:
        return "—"
    return f"{_f(m['atlag'], d)} [{_f(m['ci95'][0], d)}; {_f(m['ci95'][1], d)}]"


def report(res: dict) -> str:
    s = res["beallitasok"]
    L = ["# A magyarázatok stabilitása (K3)", "",
         f"Géppel készült (`python -m xai.stability`), {res['letrehozva']}. {s['bootstrap']} bootstrap-újratanítás "
         f"(mag {s['bootstrap_mag']} + i) és {len(s['kontroll_magok'])} kontroll-mag; {s['rendelesek']} teszt-rendelés "
         f"(a kontrollkaré, ujjlenyomat `{s['rendeles_ujjlenyomat'][:16]}…`), {s['hatter']} soros háttér, "
         f"{s['tanito_sorok']} tisztított tanító sor. A valódi teszt-címkét a mérés nem használja. "
         f"Idő: {res['ido_mp'] / 60:.0f} perc.", "",
         "## 1. A tanítóadat újramintázása", "",
         "Rendelésenként a lezárt modell magyarázatához mérve, a minták átlaga, majd a rendelések átlaga "
         "(95%-os bootstrap-intervallum a rendelések felett). Kontroll: ugyanaz az adat, más tanítási mag — "
         "a tanítás saját zaja.", "",
         "| modell | RBO | súlyozott tau | top-3 | top-3 iránya | CIES-súlyozott | RBO, kontroll-mag | becslés változása (pp): bootstrap / kontroll |",
         "|---|---|---|---|---|---|---|---|"]
    for k, m in res["modellek"].items():
        bt, ct = m["bootstrap"], m["kontroll_mag"]
        L.append(f"| {m['nev']} | {_ci(bt['rbo'])} | {_ci(bt['wtau'])} | {_ci(bt['top3'])} | {_ci(bt['elojel3'])} | "
                 f"{_ci(bt['cies'])} | {_ci(ct.get('rbo', {}))} | {_f(m['becsles_valtozas_pp']['bootstrap'])} / "
                 f"{_f(m['becsles_valtozas_pp']['kontroll_mag'])} |")
    L += ["", f"### A globális rangsor (a {s['rendelesek']} rendelés átlagos |hatása|)", "",
          "| modell | a lezárt modell top-5-je | RBO a lezárthoz (átlag [CI]; legkisebb) | azonos top-3 | azonos első |",
          "|---|---|---|---|---|"]
    for k, m in res["modellek"].items():
        g = m["globalis"]
        top = ", ".join(_name(t) for t in g["referencia_top5"])
        L.append(f"| {m['nev']} | {top} | {_ci(g['rbo'])}; {_f(g['rbo_min'])} | {_f(100 * g['top3_azonos'], 0)}% | "
                 f"{_f(100 * g['elso_azonos'], 0)}% |")
    L += ["", "### A modellek páronként (K4): rendelésenkénti RBO-különbség", "",
          "Előre rögzített sejtés: a logisztikus regresszió a legstabilabb, a döntési fa a legkevésbé; a LightGBM "
          "és a random forest a kettő között (egymáshoz képest nincs előzetes állítás).", "",
          "Olvasat: a sejtés teljesült, ha a különbség 95%-os intervalluma 0 fölött van; fordított, ha 0 "
          "alatt; ha a 0-t tartalmazza, nem dönthető el.", "",
          "| pár (A − B) | különbség [95%] | sejtés: A stabilabb? | olvasat |", "|---|---|---|---|"]
    for key, p in res["parok_rbo"].items():
        a, c = key.split("-")
        L.append(f"| {NAMES[a]} − {NAMES[c]} | {_ci(p, 3)} | "
                 f"{'igen' if p['elozetes_sejtes'] == 'nagyobb' else 'nincs sejtés'} | {verdict(p)} |")
    L += ["", "## 2. A CIES eredeti meghatározása (bemeneti zaj)", "",
          "A lezárt modellek; minden rendeléshez M zajos szomszéd (a számszerű jellemzők relatív α zajjal, a "
          "kategóriák és a logikai jellemzők változatlanok); CIES = max(0, 1 − átlagos súlyozott távolság / súlyozott "
          "nagyság). 1 = tökéletesen stabil.", ""]
    alphas = list(res["cies_bemeneti_zaj"].values())
    L.append("| modell | " + " | ".join(f"α = {_f(a['alpha'])} (M = {a['M']})" for a in alphas) + " |")
    L.append("|---|" + "---|" * len(alphas))
    for k in res["modellek"]:
        L.append(f"| {NAMES[k]} | " + " | ".join(
            f"{_ci(a['modellek'][k])} (szórás {_f(a['modellek'][k]['szoras'])})" for a in alphas) + " |")
    fx, fh = res.get("feltaro_kerekitett_cies"), res.get("feltaro_kerekitett_honap_nelkul")
    if fx:
        main = res["cies_bemeneti_zaj"][f"{fx['alpha']:g}"]["modellek"]
        L += ["", "## 3. Utólagos, feltáró ellenőrzés: mitől kisebb a LightGBM CIES-e?", "",
              "Nem előre rögzített; az eredmény ismeretében, a LightGBM alacsonyabb értéke miatt. Mindkét változat "
              f"ugyanazokat a zajos szomszédokat használja, mint a 2. rész α = {_f(fx['alpha'])}-as oszlopa (ugyanaz "
              "a mag, ugyanazok a húzások), így párosítva összevethető vele.", "",
              f"(a) **Kerekítve:** az egész értékű jellemzők ({', '.join(_name(c) for c in fx['kerekitett_jellemzok'])}) "
              "a zaj után egészre kerekítve — nincs például „0,03 korábbi rendelés”. Sejtés volt, hogy a LightGBM "
              "0-hoz tapadó vágásai miatt a nullából lett kis pozitív szám másik ágra visz."]
        if fh:
            L += ["", "(b) **Kerekítve, a hónap zaja nélkül:** ugyanez, de a hónap körkódolása (szinusz, koszinusz) nem "
                      "kap zajt. A hónap a valóságban nem „zajos” érték, és a kódolása lebegőpontosan sem egyértelmű: "
                      "április és augusztus koszinusza egyaránt −0,5, de gépi ábrázolásban −0,4999999999999998, illetve "
                      "−0,5000000000000004, és a LightGBM ezen a 6·10⁻¹⁶-os különbségen vág (küszöb −0,5). Az augusztusi "
                      "rendelések így pontosan a vágáson ülnek, és a legkisebb zaj is áttolja őket."]
        head = "| modell | 2. rész (α = 0,03, M = 10) | (a) kerekítve |" + (" (b) kerekítve, hónap zaja nélkül |" if fh else "")
        L += ["", head, "|---|---|---|" + ("---|" if fh else "")]
        for k, v in fx["modellek"].items():
            row = f"| {NAMES[k]} | {_ci(main[k])} (szórás {_f(main[k]['szoras'])}) | {_ci(v)} (szórás {_f(v['szoras'])}) |"
            if fh:
                w = fh["modellek"][k]
                row += f" {_ci(w)} (szórás {_f(w['szoras'])}) |"
            L.append(row)
        if fx.get("ellenorzes_lightgbm_kerekitetlen") is not None:
            L += ["", f"Ellenőrzés: a kerekítetlen szomszédokon a LightGBM CIES-e újraszámolva "
                      f"{_f(fx['ellenorzes_lightgbm_kerekitetlen'], 4)}, a 2. részben {_f(main['lightgbm']['atlag'], 4)} "
                      "(ugyanazok a húzások)."]
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ parancs
def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="A magyarázatok stabilitása (K3).")
    ap.add_argument("--bootstrap", type=int, default=N_BOOT, help="a bootstrap-újratanítások száma")
    ap.add_argument("--magok", default=",".join(map(str, CONTROL_SEEDS)), help="a kontroll-magok, vesszővel")
    ap.add_argument("--rendelesek", type=int, default=ka.N_ORDERS)
    ap.add_argument("--cies-m", type=int, default=CIES_M, dest="cies_m")
    ap.add_argument("--cies-erzekenyseg-nelkul", action="store_true", dest="no_sens")
    ap.add_argument("--modellek", default=",".join(KINDS))
    ap.add_argument("--kimenet", type=Path, help="a JSON helye (mellé .md); alapból a rögzített futás → docs/")
    ap.add_argument("--feltaro-kerekites", type=Path, metavar="JSON", dest="rounded",
                    help="utólagos, feltáró ellenőrzés: a kerekített szomszédok CIES-e egy meglévő eredményhez "
                         "(a JSON-ba külön kulccsal kerül, a .md újraíródik)")
    ap.add_argument("--feltaro-honap", type=Path, metavar="JSON", dest="no_month",
                    help="utólagos, feltáró: mint a --feltaro-kerekites, de a hónap körkódolása nem kap zajt")
    ap.add_argument("--jelentes", type=Path, metavar="JSON",
                    help="nem mér: egy meglévő eredmény-JSON-ból újraírja a mellette lévő .md jelentést")
    return ap


def _is_full(a) -> bool:
    return (a.bootstrap == N_BOOT and a.magok == ",".join(map(str, CONTROL_SEEDS)) and a.rendelesek == ka.N_ORDERS
            and a.cies_m == CIES_M and not a.no_sens and a.modellek == ",".join(KINDS))


def output_path(a) -> Path:
    if a.kimenet:
        return a.kimenet
    return DOCS / "stabilitas_eredmeny.json" if _is_full(a) else ARTIFACTS / "stabilitas_proba.json"


def main(argv: list[str] | None = None) -> None:
    use_utf8_console()
    a = parser().parse_args(argv)
    if a.rounded or a.no_month:
        path = a.rounded or a.no_month
        b = load_bundle(DB_PATH, verbose=True)
        res = json.loads(path.read_text(encoding="utf-8"))
        if a.rounded:
            res["feltaro_kerekitett_cies"] = exploratory_rounded_cies(b)
        else:
            res["feltaro_kerekitett_honap_nelkul"] = exploratory_rounded_cies(b, keep_cols=MONTH_FEATURES)
        path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        path.with_suffix(".md").write_text(report(res), encoding="utf-8")
        print(f"Feltáró ellenőrzés: {path} (és {path.with_suffix('.md').name})")
        return
    if a.jelentes:
        res = json.loads(a.jelentes.read_text(encoding="utf-8"))
        a.jelentes.with_suffix(".md").write_text(report(res), encoding="utf-8")
        print(f"Jelentés: {a.jelentes.with_suffix('.md')}")
        return
    try:
        b = load_bundle(DB_PATH, verbose=True)
    except WarehouseUnavailable as exc:
        sys.exit(str(exc))
    kinds = tuple(k for k in a.modellek.split(",") if k)
    seeds = tuple(int(s) for s in a.magok.split(",") if s)
    res = run(b, kinds, a.bootstrap, seeds, a.rendelesek, a.cies_m, {} if a.no_sens else None)
    out = output_path(a)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    out.with_suffix(".md").write_text(report(res), encoding="utf-8")
    print(f"Eredmény: {out} (és {out.with_suffix('.md').name})")


if __name__ == "__main__":
    main()
