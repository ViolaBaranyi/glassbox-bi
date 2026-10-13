"""
A magyarázatok hűsége a modellhez (K2 — témavezetői kérés): két mérés.

1. Törlési és beszúrási görbe
   Ha a magyarázat jó, akkor a szerinte legerősebb tényezők „kivétele" változtat a
   legtöbbet a modell becslésén. „Kivenni" egy tényezőt: az értékét a háttér
   rendeléseiből vesszük (interventional maszkolás, ugyanaz az értékfüggvény, mint a
   KernelSHAP-kontrollkarban):

       v(S) = átlag_háttér f(x_S, háttér_{−S})       (S = a rendelés saját értékei)

   A 21 megjelenítési tényező a játékos (a hónap szinusza + koszinusza egyben), a
   közös háttér 100 tisztított tanító rendelés, valószínűség-tér, a kontrollkar 200
   rögzített teszt-rendelése.
     * törlés: a teljes rendelésből indulva a tényezőket a magyarázat szerinti
       sorrendben (előjelesen: a legjobban NÖVELŐ előre) egyenként „kivesszük";
       ha a magyarázat hű, a becslés gyorsan esik → nagy AOPC (az esés átlaga);
     * beszúrás: a „semmiből" (minden tényező a háttérből) ugyanabban a sorrendben
       visszatesszük a tényezőket → gyors emelkedés, nagy AOPC.
   Viszonyítás: véletlen sorrend (alsó szint) és a KernelSHAP-kar magyarázata (felső
   szint — pontosan erre az értékfüggvényre illeszt, ezért előnyben van).

2. Beültetett jellemző (félszintetikus)
   A két leggyengébb valódi jellemző (kategóriák száma, vevő korábbi rendelései —
   átlagos |hatásuk| ≤ 0,02 százalékpont) helyére két kitalált jellemző kerül:
     * „jel"  — 20% eséllyel 1; a jel = 1 rendelések időben érkezettjeiből a címkében
                10% késettre vált (a tanító ablakban 5,6% helyett kb. 15% késik);
     * „zaj"  — egyenletes 0–9, semmihez nem kapcsolódik.
   A négy modellt a lezárt beállításokkal újratanítjuk a (tisztított) tanító ablakon,
   és a felület magyarázatát (a modell saját magyarázója + százalékpontra átváltás)
   500 teszt-rendelésen megnézzük: megtalálja-e a jelet, és ~0-nak mutatja-e a zajt.
   (A helyettesítés miatt a gépezet — 22 jellemző, előfeldolgozás, magyarázók —
   változatlan marad.) A küszöbök a futás előtt rögzítve (THRESHOLDS, döntési napló).

Egyik mérés sem használja a valódi teszt-címkéket.

Futtatás (valódi adaton kb. 30–40 perc; a KernelSHAP és a random forest a lassú):
    python -m xai.faithfulness
    python -m xai.faithfulness --rendelesek 20 --veletlen 2 --beultetett 100 --nsamples 512   # gyors próba
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
from sklearn.metrics import roc_auc_score

from data.db import DB_PATH, WarehouseUnavailable, use_utf8_console
from pipeline import reference_models as rm
from pipeline.model_selection import fit_fixed, model_params
from xai import agreement as ag
from xai import kernel_arm as ka
from xai import narrative as nv
from xai.explain import explain, percentage_points
from xai.models import KINDS, NAMES, Bundle, load_bundle

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

PLAYERS = ka.PLAYERS                     # 21 megjelenítési tényező
N_RANDOM = 5                             # véletlen sorrend rendelésenként
RANDOM_SEED = 20261013
TOP_K = 3                                # „a 3 legerősebb tényező kivétele"

# Beültetett jellemző
SIGNAL_SLOT = "kategoria_szam"           # ide kerül a „jel"
NOISE_SLOT = "vevo_korabbi_rendelesek"   # ide kerül a „zaj"
P_SIGNAL = 0.20
FLIP = 0.10                              # a jel = 1, időben érkezett rendelések ennyiszer válnak késetté
NOISE_LEVELS = 10                        # a zaj értékei: 0 … 9
PLANT_SEED = 20261013
N_PLANT = 500                            # ennyi teszt-rendelésen nézzük a magyarázatot
THRESHOLDS = {
    "jel_top3": 0.90,      # a jel = 1 rendelések legalább 90%-ában a jel a 3 legerősebb között
    "jel_irany": 0.95,     # … és legalább 95%-ukban növeli a kockázatot
    "zaj_top3": 0.01,      # a zaj legfeljebb a rendelések 1%-ában kerül a 3 legerősebb közé
    "zaj_arany": 0.05,     # a zaj átlagos |hatása| legfeljebb a jelé 5%-a
}


# ------------------------------------------------------- 1. törlés és beszúrás
def value_function(model, space: ka.Space, x_z: np.ndarray, bg_z: np.ndarray,
                   masks: np.ndarray) -> np.ndarray:
    """v(S) minden maszkra (m × 21, True = a rendelés saját értéke, False = a háttéré):
    a háttér soraival kitöltött rendelések becslésének átlaga. Egyetlen predikció."""
    masks = np.asarray(masks, dtype=bool)
    m, p = masks.shape
    nb = len(bg_z)
    Z = np.where(masks[:, None, :], x_z[None, None, :], bg_z[None, :, :]).reshape(m * nb, p)
    return model.predict_proba(space.decode(Z))[:, 1].reshape(m, nb).mean(axis=1)


def deletion_masks(order) -> np.ndarray:
    """(p + 1) × p: a k-adik sorban a sorrend első k tényezője „kivéve" (a háttérből)."""
    order = np.asarray(order)
    p = len(order)
    masks = np.ones((p + 1, p), dtype=bool)
    for k in range(1, p + 1):
        masks[k:, order[k - 1]] = False
    return masks


def insertion_masks(order) -> np.ndarray:
    """(p + 1) × p: a k-adik sorban csak a sorrend első k tényezője a rendelés sajátja."""
    return ~deletion_masks(order)


def signed_order(values) -> np.ndarray:
    """A legjobban NÖVELŐ tényező előre (előjelesen csökkenő); egyezésnél a tényezők sorrendje."""
    return np.argsort(-np.asarray(values, dtype=float), kind="stable")


def curve_metrics(del_curve: np.ndarray, ins_curve: np.ndarray, k: int = TOP_K) -> dict:
    """Százalékpontban: a törlési esés átlaga (AOPC), a beszúrási emelkedés átlaga, és az
    első k tényező kivétele okozta esés."""
    f0, empty = del_curve[0], ins_curve[0]
    return {"torles_aopc": float(np.mean(f0 - del_curve)) * 100.0,
            "beszuras_aopc": float(np.mean(ins_curve - empty)) * 100.0,
            "top3_eses": float(f0 - del_curve[k]) * 100.0}


def order_curves(model, space, x_z, bg_z, orders: dict) -> dict:
    """Minden sorrendre a törlési és a beszúrási görbe — egyetlen predikcióval."""
    names = list(orders)
    blocks = []
    for name in names:
        blocks += [deletion_masks(orders[name]), insertion_masks(orders[name])]
    values = value_function(model, space, x_z, bg_z, np.vstack(blocks))
    p1 = len(PLAYERS) + 1
    out = {}
    for i, name in enumerate(names):
        d = values[(2 * i) * p1:(2 * i + 1) * p1]
        s = values[(2 * i + 1) * p1:(2 * i + 2) * p1]
        out[name] = (d, s)
    return out


def deletion_insertion(b: Bundle, kinds=KINDS, n_orders: int = ka.N_ORDERS,
                       n_random: int = N_RANDOM, nsamples: int = ka.NSAMPLES,
                       with_kernel: bool = True, log=print) -> dict:
    space = ka.Space.from_frame(b.X)
    rows = ka.order_subset(b, n_orders)
    bg = b.background(n=ka.N_BACKGROUND, seed=ka.BACKGROUND_SEEDS[0])
    ui_bg = b.background()
    X_z, bg_z = space.encode(rows), space.encode(bg)
    out = {}
    for kind in kinds:
        t0 = time.time()
        model = b.models[kind]
        native = ka.native_pp(kind, model, rows, ui_bg)[PLAYERS].to_numpy()
        kernel = None
        if with_kernel:
            kernel = ka.kernel_explain(model, rows, bg, space, nsamples,
                                       ka.KERNEL_SEEDS[0]).phi[PLAYERS].to_numpy()
        rng = np.random.default_rng(RANDOM_SEED)
        per = {"felulet": [], "kernel": [], "veletlen": []}
        curves = {"felulet": [], "kernel": [], "veletlen": []}
        better = []
        for i in range(len(rows)):
            orders = {"felulet": signed_order(native[i])}
            if kernel is not None:
                orders["kernel"] = signed_order(kernel[i])
            rand = {f"veletlen_{j}": rng.permutation(len(PLAYERS)) for j in range(n_random)}
            res = order_curves(model, space, X_z[i], bg_z, {**orders, **rand})
            for name in orders:
                d, s = res[name]
                per[name].append(curve_metrics(d, s))
                curves[name].append(np.vstack([(d[0] - d) * 100.0, (s - s[0]) * 100.0]))
            rm_ = [curve_metrics(*res[n]) for n in rand]
            per["veletlen"].append({m: float(np.mean([r[m] for r in rm_])) for m in rm_[0]})
            curves["veletlen"].append(np.mean([np.vstack([(res[n][0][0] - res[n][0]) * 100.0,
                                                          (res[n][1] - res[n][1][0]) * 100.0])
                                               for n in rand], axis=0))
            better.append(per["felulet"][-1]["torles_aopc"] > per["veletlen"][-1]["torles_aopc"])
        tables = {n: pd.DataFrame(v) for n, v in per.items() if v}
        summ = {n: ag.summary(t) for n, t in tables.items()}
        paired = {"felulet_minusz_veletlen": ag.summary(tables["felulet"] - tables["veletlen"])}
        if "kernel" in tables:
            paired["felulet_minusz_kernel"] = ag.summary(tables["felulet"] - tables["kernel"])
        mean_curves = {n: {"torles": np.mean([c[0] for c in v], axis=0).round(4).tolist(),
                           "beszuras": np.mean([c[1] for c in v], axis=0).round(4).tolist()}
                       for n, v in curves.items() if v}
        out[kind] = {"nev": NAMES[kind], "mertekek": summ, "paros": paired,
                     "jobb_mint_veletlen": float(np.mean(better)),
                     "gorbek": mean_curves, "ido_mp": round(time.time() - t0, 1)}
        log(f"{NAMES[kind]:<24} törlési/beszúrási görbe {len(rows)} rendelésen: "
            f"{time.time() - t0:.0f} mp")
    return {"rendelesek": len(rows), "rendeles_ujjlenyomat": ka.subset_fingerprint(b, rows.index),
            "modellek": out}


# ------------------------------------------------------- 2. beültetett jellemző
def plant(b: Bundle, seed: int = PLANT_SEED, p_signal: float = P_SIGNAL,
          flip: float = FLIP) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """A „jel" és a „zaj" a két leggyengébb jellemző helyére; félszintetikus címke.
    Visszaad: (X', y', jel) — a valódi X és y változatlan."""
    rng = np.random.default_rng(seed)
    n = len(b.X)
    jel = rng.random(n) < p_signal
    zaj = rng.integers(0, NOISE_LEVELS, n)
    flips = rng.random(n) < flip
    X2 = b.X.copy()
    X2[SIGNAL_SLOT] = jel.astype(b.X[SIGNAL_SLOT].dtype)
    X2[NOISE_SLOT] = zaj.astype(b.X[NOISE_SLOT].dtype)
    y2 = pd.Series(np.where(jel & flips, 1, b.y.to_numpy()), index=b.y.index).astype(b.y.dtype)
    return X2, y2, pd.Series(jel, index=b.X.index)


def planted_models(b: Bundle, X2: pd.DataFrame, y2: pd.Series, kinds=KINDS) -> dict:
    """A négy modell a lezárt beállításokkal, a (tisztított) tanító ablakon, a beültetett adaton."""
    tr = b.train_idx
    seed = int(b.info.get("mag", 42))
    models = {}
    for kind in kinds:
        if kind == "lightgbm":
            models[kind] = fit_fixed(model_params(seed), X2.loc[tr], y2.loc[tr],
                                     int(b.info["lightgbm_fak"]))
        else:
            models[kind] = rm.make_model(kind, b.info["referencia"][kind], seed).fit(
                X2.loc[tr], y2.loc[tr])
    return models


def planted_check(pp: pd.DataFrame, jel: pd.Series) -> dict:
    """A felület magyarázata (n × 21, százalékpont) a beültetett jellemzőkre."""
    absval = pp.abs()
    rank = absval.rank(axis=1, ascending=False, method="first")
    on = jel.loc[pp.index].to_numpy(dtype=bool)
    mean_abs = absval.mean().sort_values(ascending=False, kind="stable")
    order = list(mean_abs.index)
    res = {
        "jel_top3": float((rank.loc[on, SIGNAL_SLOT] <= TOP_K).mean()) if on.any() else float("nan"),
        "jel_irany": float((pp.loc[on, SIGNAL_SLOT] > 0).mean()) if on.any() else float("nan"),
        "jel0_irany": float((pp.loc[~on, SIGNAL_SLOT] < 0).mean()) if (~on).any() else float("nan"),
        "zaj_top3": float((rank[NOISE_SLOT] <= TOP_K).mean()),
        "jel_atlag_abs_pp": float(mean_abs[SIGNAL_SLOT]),
        "zaj_atlag_abs_pp": float(mean_abs[NOISE_SLOT]),
        "zaj_arany": float(mean_abs[NOISE_SLOT] / mean_abs[SIGNAL_SLOT]) if mean_abs[SIGNAL_SLOT] > 0
        else float("nan"),
        "jel_helyezes": order.index(SIGNAL_SLOT) + 1,
        "zaj_helyezes": order.index(NOISE_SLOT) + 1,
        "jel1_atlag_pp": float(pp.loc[on, SIGNAL_SLOT].mean()) if on.any() else float("nan"),
        "rendelesek": int(len(pp)), "jel1_rendelesek": int(on.sum()),
    }
    res["itelet"] = {
        "jel_top3": res["jel_top3"] >= THRESHOLDS["jel_top3"],
        "jel_irany": res["jel_irany"] >= THRESHOLDS["jel_irany"],
        "zaj_top3": res["zaj_top3"] <= THRESHOLDS["zaj_top3"],
        "zaj_arany": res["zaj_arany"] <= THRESHOLDS["zaj_arany"],
    }
    res["megfelelt"] = all(res["itelet"].values())
    return res


def planted_feature(b: Bundle, kinds=KINDS, n_rows: int = N_PLANT, flip: float = FLIP,
                    log=print) -> dict:
    X2, y2, jel = plant(b, flip=flip)
    test = X2.loc[b.split.test]
    rows = test.sample(min(n_rows, len(test)), random_state=PLANT_SEED).sort_index()
    bg = X2.loc[b.background().index]                         # ugyanazok a sorok, mint a felületé
    tr = b.train_idx
    out = {}
    t0 = time.time()
    models = planted_models(b, X2, y2, kinds)
    log(f"a négy modell újratanítva a beültetett adaton: {time.time() - t0:.0f} mp")
    noise_values = bg[NOISE_SLOT].sample(min(50, len(bg)), random_state=1).to_numpy()
    for kind in kinds:
        t1 = time.time()
        pp = nv.merge_display(percentage_points(explain(kind, models[kind], rows, bg)))
        res = planted_check(pp, jel)
        # Feltáró (nem előre rögzített): használja-e maga a MODELL a zajt? Csak a zajt cserélve
        # a háttér értékeire, mennyit mozdul átlagosan a becslés (százalékpont).
        p_rows = models[kind].predict_proba(rows)[:, 1]
        moved = np.mean([models[kind].predict_proba(rows.assign(**{NOISE_SLOT: v}))[:, 1]
                         for v in noise_values], axis=0)
        res["zaj_valodi_hatas_pp"] = float(np.mean(np.abs(p_rows - moved)) * 100.0)
        p_test = models[kind].predict_proba(test)[:, 1]
        on_test = jel.loc[test.index].to_numpy()
        res["modell_tanulta"] = {
            "teszt_auc_felszintetikus": float(roc_auc_score(y2.loc[test.index], p_test)),
            "atlag_becsles_jel1": float(p_test[on_test].mean()),
            "atlag_becsles_jel0": float(p_test[~on_test].mean()),
        }
        res["nev"] = NAMES[kind]
        res["ido_mp"] = round(time.time() - t1, 1)
        out[kind] = res
        log(f"{NAMES[kind]:<24} beültetett jellemző: jel a top-3-ban {res['jel_top3']:.0%}, "
            f"zaj a top-3-ban {res['zaj_top3']:.1%} ({time.time() - t1:.0f} mp)")
    on_tr = jel.loc[tr].to_numpy()
    return {
        "rendelesek": int(len(rows)),
        "tanito_keses_jel1": float(y2.loc[tr][on_tr].mean()),
        "tanito_keses_jel0": float(y2.loc[tr][~on_tr].mean()),
        "tanito_keses_eredeti": float(b.y.loc[tr].mean()),
        "modellek": out,
    }


# ------------------------------------------------------------------- futás
def run(b: Bundle, kinds=KINDS, n_orders: int = ka.N_ORDERS, n_random: int = N_RANDOM,
        n_plant: int = N_PLANT, nsamples: int = ka.NSAMPLES, with_kernel: bool = True,
        verbose: bool = True) -> dict:
    t_start = time.time()
    kinds = tuple(kinds)

    def log(msg):
        if verbose:
            print(f"  [{time.time() - t_start:6.0f} mp] {msg}", flush=True)

    curves = deletion_insertion(b, kinds, n_orders, n_random, nsamples, with_kernel, log)
    planted = planted_feature(b, kinds, n_plant, log=log)
    return {
        "nev": "A magyarázatok hűsége a modellhez",
        "beallitas": {
            "jatekosok": PLAYERS, "maszkolas": "interventional (közös háttér)",
            "hatter": ka.N_BACKGROUND, "hatter_mag": ka.BACKGROUND_SEEDS[0],
            "rendelesek": curves["rendelesek"], "rendeles_mag": ka.ORDER_SEED,
            "veletlen_sorrendek": n_random, "veletlen_mag": RANDOM_SEED, "top_k": TOP_K,
            "kernel_viszonyitas": with_kernel, "nsamples": int(nsamples),
            "felulet_hattere": len(b.background()),
            "beultetett": {"jel_helye": SIGNAL_SLOT, "zaj_helye": NOISE_SLOT, "p_jel": P_SIGNAL,
                           "atvaltas": FLIP, "zaj_ertekek": NOISE_LEVELS, "mag": PLANT_SEED,
                           "rendelesek": planted["rendelesek"]},
            "kuszobok": THRESHOLDS,
        },
        "torles_beszuras": curves,
        "beultetett": planted,
        "futas": {"idopont_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                  "os": platform.platform(), "python": platform.python_version(),
                  "adatforras": b.info.get("adatforras"), "ido_mp": round(time.time() - t_start, 1)},
    }


# ---------------------------------------------------------------- jelentés
def _fmt(m: dict, digits: int = 2) -> str:
    lo, hi = m["ci95"]
    return f"{nv.fmt_num(m['atlag'], digits)} [{nv.fmt_num(lo, digits)}; {nv.fmt_num(hi, digits)}]"


def _ok(flag: bool) -> str:
    return "igen" if flag else "**nem**"


def report(res: dict) -> str:
    s, tb, pl = res["beallitas"], res["torles_beszuras"], res["beultetett"]
    L = ["# A magyarázatok hűsége a modellhez — eredmény", "",
         f"Futás: {res['futas']['idopont_utc']} UTC, {res['futas']['os']}, Python "
         f"{res['futas']['python']}, {res['futas']['ido_mp']:.0f} mp. A paraméterek a futás előtt "
         "rögzítve (döntési napló, 2026-10-13). A valódi teszt-címkéket egyik mérés sem használja.", "",
         "## 1. Törlési és beszúrási görbe", "",
         f"{tb['rendelesek']} teszt-rendelés (a KernelSHAP-kontrollkar részhalmaza, ujjlenyomat "
         f"`{tb['rendeles_ujjlenyomat'][:16]}…`), {len(s['jatekosok'])} tényező, interventional "
         f"maszkolás {s['hatter']} rendelésnyi közös háttérrel, valószínűség-tér. Sorrend: a "
         "magyarázat szerint a legjobban növelő tényező előre. **AOPC** — a törlésnél a becslés "
         "esésének, a beszúrásnál az emelkedésének átlaga a 22 lépésen (százalékpont, a nagyobb a "
         f"jobb); **top-{s['top_k']} esés** — az első {s['top_k']} tényező kivétele után. "
         f"Véletlen: {s['veletlen_sorrendek']} sorrend átlaga rendelésenként.", "",
         "| modell | sorrend | törlés AOPC | beszúrás AOPC | top-3 esés |", "|---|---|---|---|---|"]
    names = {"felulet": "a felület magyarázata", "kernel": "KernelSHAP (felső viszonyítás)",
             "veletlen": "véletlen (alsó viszonyítás)"}
    for kind, d in tb["modellek"].items():
        for key, label in names.items():
            if key in d["mertekek"]:
                m = d["mertekek"][key]
                L.append(f"| {d['nev']} | {label} | {_fmt(m['torles_aopc'])} | "
                         f"{_fmt(m['beszuras_aopc'])} | {_fmt(m['top3_eses'])} |")
    L += ["", "**Páros különbség (a felület − véletlen, ill. − KernelSHAP), rendelésenként:**", "",
          "| modell | törlés AOPC: − véletlen | − KernelSHAP | top-3 esés: − véletlen | a rendelések hány %-ában jobb a véletlennél |",
          "|---|---|---|---|---|"]
    for kind, d in tb["modellek"].items():
        pv = d["paros"]["felulet_minusz_veletlen"]
        pk = d["paros"].get("felulet_minusz_kernel")
        L.append(f"| {d['nev']} | {_fmt(pv['torles_aopc'])} | "
                 f"{_fmt(pk['torles_aopc']) if pk else '—'} | {_fmt(pv['top3_eses'])} | "
                 f"{nv.fmt_pct(d['jobb_mint_veletlen'], 0)} |")
    b = s["beultetett"]
    L += ["", "## 2. Beültetett jellemző", "",
          f"A „jel” a `{b['jel_helye']}`, a „zaj” a `{b['zaj_helye']}` helyén (a két leggyengébb "
          f"valódi jellemző). Jel: P = {nv.fmt_num(b['p_jel'], 2)}; a jel = 1, időben érkezett "
          f"rendelések {nv.fmt_pct(b['atvaltas'], 0)}-a késettre vált a címkében → a tanító ablakban "
          f"a késési arány jel = 1-nél {nv.fmt_pct(pl['tanito_keses_jel1'])}, jel = 0-nál "
          f"{nv.fmt_pct(pl['tanito_keses_jel0'])} (eredetileg {nv.fmt_pct(pl['tanito_keses_eredeti'])}). "
          f"Zaj: egyenletes 0–{b['zaj_ertekek'] - 1}. Mag {b['mag']}. A felület magyarázata "
          f"{pl['rendelesek']} teszt-rendelésen. Küszöbök (előre rögzítve): jel a top-3-ban "
          f"≥ {nv.fmt_pct(s['kuszobok']['jel_top3'], 0)}, iránya ≥ {nv.fmt_pct(s['kuszobok']['jel_irany'], 0)}; "
          f"zaj a top-3-ban ≤ {nv.fmt_pct(s['kuszobok']['zaj_top3'], 0)}, átlagos |hatása| ≤ a jelé "
          f"{nv.fmt_pct(s['kuszobok']['zaj_arany'], 0)}-a.", "",
          "| modell | jel a top-3-ban (jel = 1) | jel iránya helyes | jel helyezése | zaj a top-3-ban | zaj / jel átl. |hatás| | zaj helyezése | megfelelt? | teszt-AUC (félszint.) | a zaj valódi hatása a modellre* |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for kind, d in pl["modellek"].items():
        it = d["itelet"]
        L.append(f"| {d['nev']} | {nv.fmt_pct(d['jel_top3'], 1)} ({_ok(it['jel_top3'])}) | "
                 f"{nv.fmt_pct(d['jel_irany'], 1)} ({_ok(it['jel_irany'])}) | {d['jel_helyezes']}. | "
                 f"{nv.fmt_pct(d['zaj_top3'], 1)} ({_ok(it['zaj_top3'])}) | "
                 f"{nv.fmt_pct(d['zaj_arany'], 1)} ({_ok(it['zaj_arany'])}) | {d['zaj_helyezes']}. | "
                 f"{_ok(d['megfelelt'])} | {nv.fmt_num(d['modell_tanulta']['teszt_auc_felszintetikus'], 3)} | "
                 f"{nv.fmt_num(d['zaj_valodi_hatas_pp'], 3)} pp (magyarázat: {nv.fmt_num(d['zaj_atlag_abs_pp'], 3)} pp) |")
    L += ["", "\\* Feltáró, nem előre rögzített ellenőrzés: ha CSAK a zajt cseréljük a háttér 50 "
          "értékére, a modell becslése átlagosan ennyit mozdul (százalékpont) — vagyis mennyire "
          "használja maga a modell a zajt. Ha ez nagyobb, mint amit a magyarázat a zajnak tulajdonít, "
          "a magyarázat nem túlozza el a zaj szerepét: a modell épít rá."]
    return "\n".join(L) + "\n"


def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="A magyarázatok hűsége: törlési/beszúrási görbe és beültetett jellemző")
    ap.add_argument("--rendelesek", type=int, default=ka.N_ORDERS)
    ap.add_argument("--veletlen", type=int, default=N_RANDOM)
    ap.add_argument("--beultetett", type=int, default=N_PLANT)
    ap.add_argument("--nsamples", type=int, default=ka.NSAMPLES)
    ap.add_argument("--kernel-nelkul", action="store_true", help="a KernelSHAP-viszonyítás kihagyása (gyorsabb)")
    ap.add_argument("--modellek", type=str, default=",".join(KINDS))
    ap.add_argument("--kimenet", type=str, default=str(DOCS / "huseg_eredmeny"),
                    help="a .json és a .md fájl útvonala kiterjesztés nélkül")
    a = ap.parse_args()
    try:
        b = load_bundle(DB_PATH, verbose=True)
        kinds = tuple(k.strip() for k in a.modellek.split(",") if k.strip())
        unknown = set(kinds) - set(KINDS)
        if unknown:
            raise ValueError(f"Ismeretlen modell: {sorted(unknown)}")
        print(f"Hűségmérés: {a.rendelesek} rendelés, {a.veletlen} véletlen sorrend, "
              f"beültetett jellemző {a.beultetett} rendelésen.")
        res = run(b, kinds, a.rendelesek, a.veletlen, a.beultetett, a.nsamples, not a.kernel_nelkul)
    except (WarehouseUnavailable, ValueError) as exc:
        print(f"\nHIBA:\n{exc}", file=sys.stderr)
        sys.exit(1)
    out = Path(a.kimenet)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    text = report(res)
    out.with_suffix(".md").write_text(text, encoding="utf-8")
    print("\n" + text)
    print(f"Mentve: {out.with_suffix('.json')}, {out.with_suffix('.md')}")


if __name__ == "__main__":
    main()
