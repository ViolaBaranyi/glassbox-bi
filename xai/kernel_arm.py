"""
KernelSHAP-kontrollkar: mind a négy modell UGYANAZZAL a magyarázóval, ugyanabban a
térben, ugyanazzal a háttérrel.

Miért kell?
    A felület modellenként a saját, pontos magyarázóját használja: a LightGBM-nél
    TreeSHAP log-odds térben, a logisztikus regressziónál lineáris SHAP log-odds
    térben, a fánál és a random forestnél path-dependent TreeSHAP valószínűség-
    térben (xai/explain.py). Ha a modellek magyarázatát összevetjük (K4: a
    bonyolultság ára), a különbségben a magyarázó típusa is benne van. A kontrollkar
    ezt kiszűri: modellfüggetlen KernelSHAP, interventional értékfüggvény (a
    hiányzó tényezők egy közös háttérből jönnek, egymástól függetlenül),
    VALÓSZÍNŰSÉG-térben — itt a négy modell összemérhető.
    Emellett megmutatja, mennyire tér el a felület arányos átváltása (log-odds →
    százalékpont) a valószínűség-tér Shapley-értékeitől.

Játékosok
    A 21 megjelenítési tényező: a hónap szinusza és koszinusza EGY játékos (együtt
    kódolnak egy hónapot, ezért együtt maszkolódnak). A KernelSHAP egy 21 oszlopos
    számmátrixon dolgozik (`Space`): a kategóriák egész kódok, a hónap a sorszáma, a
    logikai értékek 0/1; a modell előtt visszaalakítjuk a 22 oszlopos jellemzőtáblává
    (bitre ugyanazzá, amit a modell tanuláskor látott).

Két csapda, amit kerülünk
    * a shap 0.53 KernelExplainer alapból `l1_reg="num_features(10)"`: a 21 tényezőből
      csendben csak 10 kap nem nulla értéket → itt `l1_reg=False`;
    * a háttér méretét mi rögzítjük és ellenőrizzük (a TreeExplainer DataFrame-háttérnél
      csendben 100 sorra mintavételez — a régi KernelExplainer nem, de ellenőrizzük).

A kar saját zaja
    Ugyanazon rendeléseken (a) ugyanaz a háttér, két mintavételi mag; (b) két
    különböző háttér. Ha a modellek közti eltérés nem nagyobb ennél, nem a modellek
    különböznek, hanem a mérés zajos.

Futtatás (valódi adaton kb. 15–25 perc; a random forest a lassú):
    python -m xai.kernel_arm                     # 200 teszt-rendelés, mind a négy modell
    python -m xai.kernel_arm --rendelesek 20 --zaj 10 --nsamples 512   # gyors próba
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from data.db import DB_PATH, WarehouseUnavailable, use_utf8_console
from pipeline.features import BOOLEAN_FEATURES, CATEGORICAL_FEATURES, FEATURES
from xai import agreement as ag
from xai import narrative as nv
from xai.explain import explain, percentage_points
from xai.models import KINDS, NAMES, Bundle, load_bundle

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

PLAYERS = list(nv.DISPLAY_FEATURES)        # 21 játékos, a hónap egyben
N_ORDERS = 200                             # rögzített rendelés-részhalmaz a teszt-időszakból
ORDER_SEED = 20261012
N_BACKGROUND = 100                         # közös háttér a tisztított tanító ablakból
BACKGROUND_SEEDS = (0, 1)                  # a második csak a háttér-zaj méréséhez
NSAMPLES = 2 * len(PLAYERS) + 2 ** 11      # a shap „auto" értéke 21 játékosra: 2090
KERNEL_SEEDS = (1, 2)                      # a második csak a mintavételi zaj méréséhez
N_NOISE = 50                               # ennyi rendelésen mérjük a kar saját zaját


# ------------------------------------------------------------------ a tér
@dataclass
class Space:
    """A 21 játékos számmátrixa ↔ a modell 22 oszlopos jellemzőtáblája."""
    dtypes: dict = field(default_factory=dict)

    @classmethod
    def from_frame(cls, X: pd.DataFrame) -> "Space":
        missing = set(FEATURES) - set(X.columns)
        if missing:
            raise ValueError(f"Hiányzó jellemzők: {sorted(missing)}")
        return cls({c: X[c].dtype for c in FEATURES})

    def encode(self, X: pd.DataFrame) -> np.ndarray:
        cols = []
        for p in PLAYERS:
            if p == nv.MONTH:
                m = [nv.month_number(s, c) for s, c in zip(X["honap_sin"], X["honap_cos"])]
                cols.append(np.asarray(m, dtype=float))
            elif p in CATEGORICAL_FEATURES:
                cat = X[p].astype(self.dtypes[p])
                cols.append(cat.cat.codes.to_numpy().astype(float))        # hiány: −1
            else:
                cols.append(X[p].to_numpy(dtype=float))
        return np.column_stack(cols)

    def decode(self, Z: np.ndarray) -> pd.DataFrame:
        Z = np.asarray(Z, dtype=float)
        out = {}
        for j, p in enumerate(PLAYERS):
            v = Z[:, j]
            if p == nv.MONTH:
                # ugyanaz a művelet-sorrend, mint a pipeline.features-ben → bitre azonos
                out["honap_sin"] = np.sin(2 * np.pi * v / 12)
                out["honap_cos"] = np.cos(2 * np.pi * v / 12)
            elif p in CATEGORICAL_FEATURES:
                out[p] = pd.Categorical.from_codes(np.rint(v).astype(int), dtype=self.dtypes[p])
            elif p in BOOLEAN_FEATURES:
                out[p] = v.astype(bool)
            elif np.issubdtype(self.dtypes[p], np.integer):
                out[p] = np.rint(v).astype(self.dtypes[p])
            else:
                out[p] = v
        return pd.DataFrame(out)[FEATURES]


# ------------------------------------------------------------ magyarázat
@dataclass
class KernelExplanation:
    base: float               # E[f(háttér)] — valószínűség
    phi: pd.DataFrame         # n × 21, valószínűség-térben (Σ = f(x) − base)
    output: np.ndarray        # f(x)
    background_rows: int


def predictor(model, space: Space):
    def f(Z):
        return model.predict_proba(space.decode(Z))[:, 1]
    return f


def kernel_explain(model, X_rows: pd.DataFrame, background: pd.DataFrame, space: Space,
                   nsamples: int = NSAMPLES, seed: int = KERNEL_SEEDS[0]) -> KernelExplanation:
    """KernelSHAP a 21 játékoson, valószínűség-térben, a megadott (teljes) háttérrel."""
    import logging

    import shap
    logging.getLogger("shap").setLevel(logging.ERROR)
    f = predictor(model, space)
    B = space.encode(background)
    ex = shap.KernelExplainer(f, B)                          # identitás-link: valószínűség
    if ex.data.data.shape[0] != len(background):             # nincs csendes mintavételezés
        raise RuntimeError("A KernelExplainer nem a teljes hátteret használja.")
    Z = space.encode(X_rows)
    state = np.random.get_state()                            # a shap a globális RNG-t használja
    try:
        np.random.seed(seed)
        phi = np.asarray(ex.shap_values(Z, nsamples=int(nsamples), l1_reg=False, silent=True),
                         dtype=float)
    finally:
        np.random.set_state(state)
    phi = phi.reshape(len(Z), len(PLAYERS))
    return KernelExplanation(float(np.ravel(ex.expected_value)[0]),
                             pd.DataFrame(phi, index=X_rows.index, columns=PLAYERS),
                             f(Z), len(background))


def kernel_additivity_error(e: KernelExplanation) -> float:
    return float(np.max(np.abs(e.base + e.phi.to_numpy().sum(axis=1) - e.output)))


def native_pp(kind: str, model, X_rows: pd.DataFrame, background: pd.DataFrame) -> pd.DataFrame:
    """A felület módszere: a modell saját magyarázója + arányos átváltás, 21 tényező (pp)."""
    return nv.merge_display(percentage_points(explain(kind, model, X_rows, background)))


# ------------------------------------------------------------- a futás
def order_subset(b: Bundle, n: int = N_ORDERS, seed: int = ORDER_SEED) -> pd.DataFrame:
    """Rögzített véletlen részhalmaz a teszt-időszakból (a címkét nem használja)."""
    test = b.X.loc[b.split.test]
    return test.sample(min(n, len(test)), random_state=seed).sort_index()


def subset_fingerprint(b: Bundle, index) -> str:
    """A rendelés-részhalmaz SHA256-ja (a kulcsok a tárház sorrendjében, soronként)."""
    import hashlib
    keys = "\n".join(str(k) for k in b.meta.loc[index, "order_key"])
    return hashlib.sha256(keys.encode("utf-8")).hexdigest()


def _pairs(kinds):
    return [(a, c) for i, a in enumerate(kinds) for c in kinds[i + 1:]]


def _summ(table: pd.DataFrame) -> dict:
    return ag.summary(table)


def run(b: Bundle, kinds=KINDS, n_orders: int = N_ORDERS, n_noise: int = N_NOISE,
        n_background: int = N_BACKGROUND, nsamples: int = NSAMPLES, verbose: bool = True) -> dict:
    t_start = time.time()
    kinds = tuple(kinds)
    space = Space.from_frame(b.X)
    rows = order_subset(b, n_orders)
    noise_rows = rows.iloc[:min(n_noise, len(rows))]
    bg = b.background(n=n_background, seed=BACKGROUND_SEEDS[0])
    bg2 = b.background(n=n_background, seed=BACKGROUND_SEEDS[1])
    ui_bg = b.background()                                    # a felület hátterének mérete (500)

    def log(msg):
        if verbose:
            print(f"  [{time.time() - t_start:6.0f} mp] {msg}", flush=True)

    kernel, native, timing, additivity = {}, {}, {}, {}
    for kind in kinds:
        t0 = time.time()
        e = kernel_explain(b.models[kind], rows, bg, space, nsamples, KERNEL_SEEDS[0])
        timing[kind] = time.time() - t0
        additivity[kind] = kernel_additivity_error(e)
        kernel[kind] = e
        native[kind] = native_pp(kind, b.models[kind], rows, ui_bg)
        log(f"{NAMES[kind]:<24} KernelSHAP {len(rows)} rendelés: {timing[kind]:.0f} mp, "
            f"additivitási hiba {additivity[kind]:.1e}")

    kpp = {k: e.phi * 100.0 for k, e in kernel.items()}      # százalékpont

    # 1. A felület arányos átváltása vs a valószínűség-tér Shapley-értékei
    conversion = {}
    for kind in kinds:
        conversion[kind] = {"felulet": _summ(ag.compare_frames(native[kind], kpp[kind]))}
    if "logreg" in kinds:      # közös háttérrel: csak a tér (és a kar zaja) különbözik
        same_bg = native_pp("logreg", b.models["logreg"], rows, bg)
        conversion["logreg"]["kozos_hatter"] = _summ(ag.compare_frames(same_bg, kpp["logreg"]))

    # 2. A modellek egyezése: ugyanazzal a magyarázóval vs a saját magyarázóikkal
    pairs = {}
    for a, c in _pairs(kinds):
        pairs[f"{a}|{c}"] = {
            "kontrollkar": _summ(ag.compare_frames(kpp[a], kpp[c])),
            "sajat_magyarazok": _summ(ag.compare_frames(native[a], native[c])),
        }

    # 3. A kar saját zaja
    noise = {}
    for kind in kinds:
        ref = kpp[kind].loc[noise_rows.index]
        e_seed = kernel_explain(b.models[kind], noise_rows, bg, space, nsamples, KERNEL_SEEDS[1])
        e_bg = kernel_explain(b.models[kind], noise_rows, bg2, space, nsamples, KERNEL_SEEDS[0])
        noise[kind] = {
            "mintavetel": _summ(ag.compare_frames(e_seed.phi * 100.0, ref)),
            "hatter": _summ(ag.compare_frames(e_bg.phi * 100.0, ref)),
            "hatter_alapertek_elteres_pp": 100.0 * abs(e_bg.base - kernel[kind].base),
        }
        log(f"{NAMES[kind]:<24} zajmérés {len(noise_rows)} rendelésen kész")

    # 4. Globális kép a karon: átlagos |hatás| (pp) és rangsor modellenként
    global_imp = {k: kpp[k].abs().mean().sort_values(ascending=False).round(4).to_dict()
                  for k in kinds}

    return {
        "nev": "KernelSHAP-kontrollkar",
        "beallitas": {
            "rendelesek": len(rows), "rendeles_mag": ORDER_SEED, "ablak": "teszt",
            "hatter": n_background, "hatter_mag": BACKGROUND_SEEDS[0],
            "hatter_forras": "tisztított tanító ablak",
            "nsamples": int(nsamples), "kernel_mag": KERNEL_SEEDS[0], "l1_reg": False,
            "jatekosok": PLAYERS, "ter": "valószínűség", "ertekfuggveny": "interventional",
            "zaj_rendelesek": len(noise_rows), "felulet_hattere": len(ui_bg),
        },
        "modellek": {k: {"nev": NAMES[k], "alapertek": kernel[k].base,
                         "additivitasi_hiba": additivity[k], "ido_mp": round(timing[k], 1)}
                     for k in kinds},
        "atvaltas": conversion,
        "modellparok": pairs,
        "zaj": noise,
        "globalis": global_imp,
        # a részhalmaz ujjlenyomata (a rendelés-azonosítók adatnak számítanak: nem mentjük őket)
        "rendeles_ujjlenyomat": subset_fingerprint(b, rows.index),
        "futas": {"idopont_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                  "os": platform.platform(), "python": platform.python_version(),
                  "adatforras": b.info.get("adatforras"), "ido_mp": round(time.time() - t_start, 1)},
    }


# ---------------------------------------------------------------- jelentés
def _fmt(ci: dict, digits: int = 2) -> str:
    lo, hi = ci["ci95"]
    return f"{nv.fmt_num(ci['atlag'], digits)} [{nv.fmt_num(lo, digits)}; {nv.fmt_num(hi, digits)}]"


def report(res: dict) -> str:
    s = res["beallitas"]
    L = ["# KernelSHAP-kontrollkar — eredmény", "",
         f"{s['rendelesek']} teszt-rendelés (mag {s['rendeles_mag']}), közös háttér: {s['hatter']} "
         f"rendelés a {s['hatter_forras']}ból, {s['nsamples']} koalíció rendelésenként, "
         f"`l1_reg=False`, {len(s['jatekosok'])} játékos (a hónap egyben), "
         f"valószínűség-tér, interventional. Futás: {res['futas']['idopont_utc']} UTC, "
         f"{res['futas']['os']}, Python {res['futas']['python']}, {res['futas']['ido_mp']:.0f} mp. "
         f"A rendelés-részhalmaz ujjlenyomata (SHA256): `{res['rendeles_ujjlenyomat'][:16]}…`", "",
         "Mértékek (rendelésenként, átlag [95% bootstrap-CI]): **top3** — a 3 legfontosabb "
         "tényező közös része; **RBO** (p = 0,9) — rangsor-egyezés, a rangsor elejét súlyozza; "
         "**wtau** — súlyozott Kendall-tau; **előjel3** — a viszonyítás top-3 tényezőjének "
         "iránya egyezik-e; **rel_L1** — Σ|eltérés| / Σ|viszonyítás|.", "",
         "## 1. A felület arányos átváltása vs a valószínűség-tér Shapley-értékei", "",
         "| modell | összevetés | top3 | RBO | wtau | előjel3 | rel_L1 |", "|---|---|---|---|---|---|---|"]
    for kind, d in res["atvaltas"].items():
        for label, key in (("a felület magyarázata", "felulet"), ("ugyanazzal a háttérrel", "kozos_hatter")):
            if key in d:
                m = d[key]
                L.append(f"| {res['modellek'][kind]['nev']} | {label} | {_fmt(m['top3'])} | "
                         f"{_fmt(m['rbo'])} | {_fmt(m['wtau'])} | {_fmt(m['elojel3'])} | {_fmt(m['rel_l1'])} |")
    L += ["", "## 2. A modellek egyezése (RBO, p = 0,9)", "",
          "| modellpár | kontrollkar (ugyanaz a magyarázó) | saját magyarázók (a felületé) | top3: kar / saját |",
          "|---|---|---|---|"]
    for key, d in res["modellparok"].items():
        a, c = key.split("|")
        L.append(f"| {res['modellek'][a]['nev']} – {res['modellek'][c]['nev']} | "
                 f"{_fmt(d['kontrollkar']['rbo'])} | {_fmt(d['sajat_magyarazok']['rbo'])} | "
                 f"{nv.fmt_num(d['kontrollkar']['top3']['atlag'], 2)} / "
                 f"{nv.fmt_num(d['sajat_magyarazok']['top3']['atlag'], 2)} |")
    L += ["", "## 3. A kar saját zaja", "",
          "| modell | mintavételi mag: RBO | top3 | rel_L1 | más háttér: RBO | top3 | rel_L1 | alapérték-eltérés (pp) |",
          "|---|---|---|---|---|---|---|---|"]
    for kind, d in res["zaj"].items():
        m, h = d["mintavetel"], d["hatter"]
        L.append(f"| {res['modellek'][kind]['nev']} | {_fmt(m['rbo'])} | {_fmt(m['top3'])} | "
                 f"{_fmt(m['rel_l1'])} | {_fmt(h['rbo'])} | {_fmt(h['top3'])} | {_fmt(h['rel_l1'])} | "
                 f"{nv.fmt_num(d['hatter_alapertek_elteres_pp'], 2)} |")
    L += ["", "## 4. Modellenként", "", "| modell | alapérték (E[f]) | additivitási hiba | idő (mp) | a 3 legfontosabb tényező a karon (átl. |pp|) |",
          "|---|---|---|---|---|"]
    for kind, m in res["modellek"].items():
        top = list(res["globalis"][kind].items())[:3]
        L.append(f"| {m['nev']} | {nv.fmt_pct(m['alapertek'], 2)} | {m['additivitasi_hiba']:.1e} | "
                 f"{m['ido_mp']:.0f} | " + " · ".join(f"{nv.display_name(t)} {nv.fmt_num(v, 2)}"
                                                       for t, v in top) + " |")
    return "\n".join(L) + "\n"


def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="KernelSHAP-kontrollkar a négy modellre")
    ap.add_argument("--rendelesek", type=int, default=N_ORDERS)
    ap.add_argument("--zaj", type=int, default=N_NOISE, help="ennyi rendelésen mérjük a kar zaját")
    ap.add_argument("--hatter", type=int, default=N_BACKGROUND)
    ap.add_argument("--nsamples", type=int, default=NSAMPLES)
    ap.add_argument("--modellek", type=str, default=",".join(KINDS))
    ap.add_argument("--kimenet", type=str, default=str(DOCS / "kernel_kar_eredmeny"),
                    help="a .json és a .md fájl útvonala kiterjesztés nélkül")
    a = ap.parse_args()
    try:
        b = load_bundle(DB_PATH, verbose=True)
        kinds = tuple(k.strip() for k in a.modellek.split(",") if k.strip())
        unknown = set(kinds) - set(KINDS)
        if unknown:
            raise ValueError(f"Ismeretlen modell: {sorted(unknown)}")
        print(f"KernelSHAP-kontrollkar: {a.rendelesek} rendelés, háttér {a.hatter}, "
              f"{a.nsamples} koalíció, zajmérés {a.zaj} rendelésen.")
        res = run(b, kinds, a.rendelesek, a.zaj, a.hatter, a.nsamples)
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
