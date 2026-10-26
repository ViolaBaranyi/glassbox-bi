"""
ROAR — „vedd ki és tanítsd újra” (Hooker, Erhan, Kindermans és Kim, 2019), táblázatos változat:
ha a magyarázat szerint legfontosabb tényezőket a modell elől elvesszük, és ÚJRATANÍTUNK, többet
romlik-e, mint ha ugyanannyi véletlenül választott tényezőt vennénk el?

A K2 törlési görbéje (xai/faithfulness.py) a lezárt modellen, újratanítás nélkül maszkol — ezt
gyakran éri az a kritika, hogy a maszkolt bemenet a tanítóadat eloszlásán kívül esik. A ROAR ezt
megkerüli: a „kivett” tényező minden rendelésnél ugyanazt az értéket kapja (számnál a tisztított
tanító ablak mediánja, kategóriánál és logikai értéknél a leggyakoribb érték — a hiányzó érték
is), a tanításban és a tesztben egyaránt, és a modell a lezárt beállításokkal újratanul.

  * Rangsor: modellenként a felület magyarázata (21 megjelenítési tényező; a hónap = szinusz +
    koszinusz) a kontrollkar 200 teszt-rendelésén, átlagos |hatás| szerint — ugyanaz, mint a K3
    globális rangsora (a top-5 egyezését a futás ellenőrzi).
  * Kivétel: a k legfontosabb (k = 1, 2, 3, 5), a k legkevésbé fontos, és N_RANDOM véletlen
    k-as készlet (a véletlen készletek mind a négy modellnél ugyanazok).
  * Mérés az időbeli teszten: a PR-AUC és a ROC-AUC esése a lezárt modellhez képest (pozitív =
    romlott). Az újratanítás kivétel nélkül a lezárt modellt adja vissza (a futás ellenőrzi).
A beállítások a futás előtt a döntési naplóban.

    uv run python tools/roar.py                 # → docs/roar_eredmeny.json és .md
    uv run python tools/roar.py --veletlen 2 --kimenet artifacts/roar_proba.json
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
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.db import DB_PATH, use_utf8_console  # noqa: E402
from pipeline import reference_models as rm  # noqa: E402
from pipeline.features import BOOLEAN_FEATURES, CATEGORICAL_FEATURES, NUMERIC_FEATURES  # noqa: E402
from pipeline.model_selection import fit_fixed, model_params  # noqa: E402
from xai import kernel_arm as ka  # noqa: E402
from xai import narrative as nv  # noqa: E402
from xai import stability as st  # noqa: E402
from xai.models import KINDS, NAMES, Bundle, load_bundle  # noqa: E402

K_VALUES = (1, 2, 3, 5)
N_RANDOM = 10
SEED = 20261103
# Előre rögzített sejtések (a döntési naplóban, a futás előtt):
#  R1: minden modellnél és minden k-nál a magyarázat k legfontosabb tényezőjének kivétele jobban
#      rontja a ROC-AUC-t, mint a véletlen k-as készletek esésének mediánja;
#  R2: k ≤ 3-nál a magyarázat szerinti kivétel a 10 véletlen készletből legalább 9-nél jobban ront;
#  R3 (leíró): a k legkevésbé fontos tényező kivétele kevésbé ront, mint a k legfontosabbé.


# ------------------------------------------------------------------ kivétel
def neutral_values(b: Bundle) -> dict:
    """A „kivett” tényező állandó értéke a tisztított tanító ablakból."""
    Xtr = b.X.loc[b.train_idx]
    out = {}
    for c in NUMERIC_FEATURES:
        out[c] = float(Xtr[c].median())
    for c in BOOLEAN_FEATURES:
        out[c] = bool(Xtr[c].mode().iloc[0])
    for c in CATEGORICAL_FEATURES:
        out[c] = Xtr[c].value_counts(sort=True).index[0]
    return out


def factor_columns(factor: str) -> list:
    return list(nv.DISPLAY_GROUPS.get(factor, [factor]))


def neutralize(X: pd.DataFrame, factors, values: dict) -> pd.DataFrame:
    """A megadott megjelenítési tényezők oszlopai minden sorban az állandó értéket kapják."""
    out = X.copy()
    for f in factors:
        for c in factor_columns(f):
            if c in CATEGORICAL_FEATURES:
                out[c] = pd.Categorical([values[c]] * len(out), categories=X[c].cat.categories)
            elif c in BOOLEAN_FEATURES:
                out[c] = np.full(len(out), values[c], dtype=bool)
            else:
                out[c] = np.full(len(out), values[c], dtype=float)
    return out


def fit_one(b: Bundle, kind: str, Xtr: pd.DataFrame, ytr: pd.Series, seed: int):
    """Egy modell a lezárt beállításokkal (ugyanaz, mint a xai.stability.fit_models)."""
    if kind == "lightgbm":
        return fit_fixed(model_params(seed), Xtr, ytr, int(b.info["lightgbm_fak"]))
    return rm.make_model(kind, b.info["referencia"][kind], seed).fit(Xtr, ytr)


def score(model, X: pd.DataFrame, y: pd.Series) -> dict:
    p = model.predict_proba(X)[:, 1]
    return {"pr_auc": float(average_precision_score(y, p)), "roc_auc": float(roc_auc_score(y, p))}


def random_sets(factors: list, k_values=K_VALUES, n: int = N_RANDOM, seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    return {k: [sorted(rng.choice(factors, size=k, replace=False).tolist()) for _ in range(n)] for k in k_values}


def ranking(b: Bundle, kind: str, rows: pd.DataFrame, bg: pd.DataFrame) -> list:
    return st.global_ranking(st.ui_explanation(kind, b.models[kind], rows, bg))


# ------------------------------------------------------------------ futás
def run(b: Bundle, kinds=KINDS, k_values=K_VALUES, n_random: int = N_RANDOM, verbose: bool = True,
        k3: dict | None = None) -> dict:
    t_start = time.time()
    kinds = tuple(kinds)

    def log(msg):
        if verbose:
            print(f"[{time.time() - t_start:6.0f} mp] {msg}", flush=True)

    seed = int(b.info.get("mag", 42))
    tr, te = b.train_idx, b.split.test
    ytr, yte = b.y.loc[tr], b.y.loc[te]
    values = neutral_values(b)
    rows, bg = ka.order_subset(b), b.background()
    rsets = random_sets(list(nv.DISPLAY_FEATURES), k_values, n_random)

    def removed(kind, factors):
        Xn = neutralize(b.X.loc[tr.append(te)], factors, values)
        m = fit_one(b, kind, Xn.loc[tr], ytr, seed)
        return score(m, Xn.loc[te], yte)

    out = {}
    for kind in kinds:
        t0 = time.time()
        rank = ranking(b, kind, rows, bg)
        base = score(b.models[kind], b.X.loc[te], yte)
        refit = removed(kind, [])
        res = {"nev": NAMES[kind], "rangsor": rank, "alap": base,
               "ujratanitva_kivetel_nelkul": refit,
               "egyezik_a_lezarttal": bool(abs(refit["pr_auc"] - base["pr_auc"]) < 1e-9
                                            and abs(refit["roc_auc"] - base["roc_auc"]) < 1e-9),
               "k3_top5_egyezik": None if not k3 else rank[:5] == k3["modellek"][kind]["globalis"]["referencia_top5"],
               "k": {}}
        for k in k_values:
            top, bottom = rank[:k], rank[-k:]
            s_top, s_bot = removed(kind, top), removed(kind, bottom)
            s_rand = [removed(kind, rs) for rs in rsets[k]]
            drop = lambda s: {m: base[m] - s[m] for m in ("pr_auc", "roc_auc")}  # noqa: E731
            res["k"][str(k)] = {"legfontosabb": top, "legkevesbe": bottom,
                                "eses_legfontosabb": drop(s_top), "eses_legkevesbe": drop(s_bot),
                                "eses_veletlen": [drop(s) for s in s_rand], "veletlen_keszletek": rsets[k]}
            log(f"{NAMES[kind]}: k = {k}")
        res["ido_mp"] = round(time.time() - t0, 1)
        out[kind] = res

    return {
        "letrehozva": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kod_ujjlenyomat": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "beallitas": {"k": list(k_values), "veletlen": n_random, "mag": SEED, "modell_mag": seed,
                      "rendelesek": int(len(rows)), "rendeles_mag": ka.ORDER_SEED, "hatter": int(len(bg)),
                      "tanito_sorok": int(len(tr)), "teszt_sorok": int(len(te)), "modellek": list(kinds),
                      "allando_ertekek": {c: (v if isinstance(v, (bool, float)) else str(v)) for c, v in values.items()}},
        "adat": {k: v for k, v in b.info.items() if k in ("adatforras", "tarhaz_epitve", "lightgbm_fak")},
        "modellek": out,
        "osszegzes": summarize(out, k_values),
        "ido_mp": round(time.time() - t_start, 1),
    }


def summarize(out: dict, k_values=K_VALUES) -> dict:
    s = {"R1": {}, "R2": {}, "R3": {}, "tablazat": {}}
    for kind, res in out.items():
        for k in k_values:
            r = res["k"][str(k)]
            for m in ("roc_auc", "pr_auc"):
                top = r["eses_legfontosabb"][m]
                rand = np.array([d[m] for d in r["eses_veletlen"]])
                s["tablazat"][f"{kind}|{k}|{m}"] = {
                    "legfontosabb": top, "legkevesbe": r["eses_legkevesbe"][m],
                    "veletlen_median": float(np.median(rand)), "veletlen_min": float(rand.min()),
                    "veletlen_max": float(rand.max()), "kisebb_veletlen": int((rand < top).sum()), "n": int(len(rand))}
            t = s["tablazat"][f"{kind}|{k}|roc_auc"]
            s["R1"][f"{kind}|{k}"] = bool(t["legfontosabb"] > t["veletlen_median"])
            if k <= 3:
                s["R2"][f"{kind}|{k}"] = bool(t["kisebb_veletlen"] >= t["n"] - 1)
            s["R3"][f"{kind}|{k}"] = bool(t["legkevesbe"] < t["legfontosabb"])
    s["R1_teljesult"] = f"{sum(s['R1'].values())}/{len(s['R1'])}"
    s["R2_teljesult"] = f"{sum(s['R2'].values())}/{len(s['R2'])}"
    s["R3_teljesult"] = f"{sum(s['R3'].values())}/{len(s['R3'])}"
    return s


# ------------------------------------------------------------------ jelentés
def _n(x: float, d: int = 3) -> str:
    return f"{x:+.{d}f}".replace(".", ",").replace("-", "−")


def report(res: dict) -> str:
    s, bt = res["osszegzes"], res["beallitas"]
    L = ["# ROAR — a fontosnak mutatott tényezők kivétele és újratanítás", "",
         f"Készült: {res['letrehozva']} · kód-ujjlenyomat `{res['kod_ujjlenyomat'][:16]}…` · {res['ido_mp']:.0f} mp. "
         f"Az előre rögzített beállítások: döntési napló.", "",
         f"A rangsor a felület magyarázata a kontrollkar {bt['rendelesek']} teszt-rendelésén; a kivett tényező minden "
         f"rendelésnél a tisztított tanító ablak mediánját / leggyakoribb értékét kapja, a tanításban és a tesztben is; "
         f"a modell a lezárt beállításokkal újratanul ({bt['tanito_sorok']} sor), mérés az időbeli teszten "
         f"({bt['teszt_sorok']} rendelés). Véletlen készletek: {bt['veletlen']} darab k-nként (mag {bt['mag']}), mind "
         f"a négy modellnél ugyanazok. **Esés** = a lezárt modell értéke − az újratanítotté (pozitív: romlott).", "",
         f"Sejtések: R1 (a legfontosabbak kivétele > a véletlenek mediánja, ROC-AUC) {s['R1_teljesult']}; "
         f"R2 (k ≤ 3: legalább 9 véletlen készletnél jobban ront) {s['R2_teljesult']}; "
         f"R3 (a legkevésbé fontosak kivétele kevésbé ront) {s['R3_teljesult']}.", ""]
    for kind, r in res["modellek"].items():
        ok = "igen" if r["egyezik_a_lezarttal"] else "**NEM**"
        L += [f"## {r['nev']}", "",
              f"Alap (lezárt): PR-AUC {_n(r['alap']['pr_auc']).lstrip('+')}, ROC-AUC {_n(r['alap']['roc_auc']).lstrip('+')}; az újratanítás "
              f"kivétel nélkül a lezártat adja: {ok}. A rangsor eleje: "
              + ", ".join(nv.display_name(f) for f in r["rangsor"][:5]) + ".", "",
              "| k | kivett (legfontosabbak) | ROC-AUC esés | véletlen: medián (legkisebb – legnagyobb) | "
              "hány véletlennél ront jobban | a legkevésbé fontosak kivétele | PR-AUC esés | véletlen PR-AUC medián |",
              "|---|---|---|---|---|---|---|---|"]
        for k in bt["k"]:
            t = s["tablazat"][f"{kind}|{k}|roc_auc"]
            tp = s["tablazat"][f"{kind}|{k}|pr_auc"]
            names = ", ".join(nv.display_name(f) for f in r["k"][str(k)]["legfontosabb"])
            L.append(f"| {k} | {names} | {_n(t['legfontosabb'])} | {_n(t['veletlen_median'])} "
                     f"({_n(t['veletlen_min'])} – {_n(t['veletlen_max'])}) | {t['kisebb_veletlen']}/{t['n']} | "
                     f"{_n(t['legkevesbe'])} | {_n(tp['legfontosabb'])} | {_n(tp['veletlen_median'])} |")
        L.append("")
    L += ["## Olvasat", "",
          "Ha a magyarázat szerinti kivétel alig ront, annak két oka lehet: a magyarázat túlbecsüli a tényezőt, vagy "
          "a tényező információja más tényezőkben is megvan, és az újratanított modell onnan pótolja (Hooker és mtsai "
          "is ezt a korlátot írják). A ROAR ezért a K2 törlési görbéjét és beültetett jelét kiegészíti, nem helyettesíti.", ""]
    return "\n".join(L)


def _k3():
    p = ROOT / "docs" / "stabilitas_eredmeny.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main(argv: list[str] | None = None) -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="ROAR: a fontos tényezők kivétele és újratanítás (lezárt beállítások).")
    ap.add_argument("--veletlen", type=int, default=N_RANDOM)
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--kimenet", type=Path, default=ROOT / "docs" / "roar_eredmeny.json")
    ap.add_argument("--jelentes", type=Path, default=None, help="csak a .md újraírása egy meglévő JSON-ból")
    a = ap.parse_args(argv)
    if a.jelentes:
        res = json.loads(a.jelentes.read_text(encoding="utf-8"))
        a.jelentes.with_suffix(".md").write_text(report(res), encoding="utf-8")
        return
    if a.veletlen != N_RANDOM and a.kimenet.resolve().parent == (ROOT / "docs").resolve():
        sys.exit("Próbafutás (nem az előre rögzített beállítás) nem írhat a docs/ mappába — adj meg --kimenet-et.")
    b = load_bundle(a.db, verbose=True)
    res = run(b, n_random=a.veletlen, k3=_k3() if b.info.get("adatforras") == "valós" else None)
    a.kimenet.parent.mkdir(parents=True, exist_ok=True)
    a.kimenet.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    a.kimenet.with_suffix(".md").write_text(report(res), encoding="utf-8")
    print(f"Eredmény: {a.kimenet} (és {a.kimenet.with_suffix('.md').name}); {res['ido_mp']} mp")


if __name__ == "__main__":
    main()
