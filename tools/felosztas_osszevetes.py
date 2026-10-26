"""
Időbeli vagy véletlen felosztás: mennyivel mutatna jobb eredményt ugyanez a modell, ha a
rendeléseket NEM időrendben osztanánk tanító- és tesztrészre?

A dolgozat modelljei a múltból tanulnak, és a rákövetkező, sosem látott időszakon (2018. jún.–aug.)
mérődnek (pipeline/split.py). A szakirodalomban és a nyilvános Olist-elemzésekben gyakori a
véletlen felosztás; ez az eszköz megméri, mekkora különbséget okoz ez UGYANAZON az adaton, a
lezárt beállításokkal (LightGBM 119 fa, logisztikus regresszió C = 0,1, döntési fa mélység 10,
random forest levélméret 10, mag 42). A beállításokat a futás előtt a döntési napló rögzíti.

  I.   Időbeli teszt (viszonyítás): a lezárt modellek a teszt-időszakon.
  II.  Véletlen felosztás a teljes időszakon: a címkézett rendelésekből véletlenül annyi tanító
       sor, ahány a tisztított tanító ablakban van, és tőlük diszjunkt, annyi teszt-sor, ahány az
       időbeli tesztben; R ismétlés (az r. ismétlés magja SEED + r).
  III. Időn belüli véletlen ellenőrzés: a tisztított tanító ablak véletlen 80/20 felosztása; a
       80%-on tanult modell a 20%-on (időn belül) ÉS az időbeli teszten (időn kívül) — párosítva.
  III/b. Időrendi ellenőrzés a tanító ablakon belül: az ablak utolsó 20%-a (időben) az értékelő
       rész, a tanítás csak az addig eldőlt címkéken (mint a lezárt futásban) — egy futás.

Mérőszámok: PR-AUC, ROC-AUC, a késési arány (bázis), PR-AUC / bázis (emelés — a bázistól kevésbé
függő), a legkockázatosabb 10% a késések hányadát fogja (véletlennél 10%), és az átlagos becslés
mínusz a tényleges arány százalékpontban (kalibráció egészében).

    uv run python tools/felosztas_osszevetes.py                 # → docs/felosztas_osszevetes.json és .md
    uv run python tools/felosztas_osszevetes.py --ismetlesek 2 --kimenet artifacts/felosztas_proba.json
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
from pipeline.split import settled_before  # noqa: E402
from xai.models import KINDS, NAMES, Bundle, load_bundle  # noqa: E402
from xai.stability import fit_models  # noqa: E402

R = 10
SEED = 20261101
INNER_FRAC = 0.20
TOP_SHARE = 0.10
METRICS = ("pr_auc", "roc_auc", "bazis", "emeles", "felso10", "kalibracio_pp")
METRIC_NAMES = {"pr_auc": "PR-AUC", "roc_auc": "ROC-AUC", "bazis": "késési arány",
                "emeles": "PR-AUC / késési arány", "felso10": "a felső 10% a késések ennyiedét fogja",
                "kalibracio_pp": "átlagos becslés − tényleges arány (pp)"}
VARIANTS = {"I": "időbeli teszt (2018. jún.–aug.)", "II": "véletlen felosztás a teljes időszakon",
            "III_ben": "időn belül: véletlen 20% a tanító ablakból",
            "III_kivul": "ugyanazok a modellek az időbeli teszten",
            "IIIb": "időrendi ellenőrzés a tanító ablak utolsó 20%-án"}
# Előre rögzített sejtések (a döntési naplóban, a futás előtt) — leíró, küszöb nélkül:
#  E1: a LightGBM ROC-AUC-ja, emelése és felső-10%-a véletlen felosztásnál (II) minden ismétlésben
#      nagyobb, mint az időbeli teszten (I); időn belül (III) minden ismétlésben nagyobb, mint
#      ugyanazon modell időn kívül.
#  E2: a LightGBM ROC-AUC-előnye a logisztikus regresszióval szemben véletlen felosztásnál (II)
#      nagyobb, mint az időbeli teszten.
#  E3: véletlen felosztásnál a kalibráció egészében közel 0 (|·| < 1 pp), az időbeli teszten nem.
E1_METRICS = ("roc_auc", "emeles", "felso10")


# ------------------------------------------------------------------ mérőszámok
def top_share_capture(y: np.ndarray, p: np.ndarray, share: float = TOP_SHARE) -> float:
    """A legnagyobb becslésű `share` hányad a késések mekkora részét tartalmazza (holtversenyben a
    sorrend az eredeti, rendezett sorrend — determinisztikus)."""
    n_top = max(1, int(round(share * len(y))))
    top = np.argsort(-p, kind="stable")[:n_top]
    return float(y[top].sum() / y.sum()) if y.sum() else float("nan")


def metrics(y, p) -> dict:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    base = float(y.mean())
    pr = float(average_precision_score(y, p))
    return {"pr_auc": pr, "roc_auc": float(roc_auc_score(y, p)), "bazis": base,
            "emeles": pr / base if base else float("nan"), "felso10": top_share_capture(y, p),
            "kalibracio_pp": (float(p.mean()) - base) * 100.0, "n": int(len(y))}


def _proba(model, X: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(X)[:, 1]


def summary(values: list[float]) -> dict:
    a = np.asarray(values, dtype=float)
    return {"atlag": float(a.mean()), "szoras": float(a.std(ddof=1)) if len(a) > 1 else 0.0,
            "min": float(a.min()), "max": float(a.max())}


# ------------------------------------------------------------------ felosztások
def random_full_split(b: Bundle, r: int, seed: int = SEED) -> tuple[pd.Index, pd.Index]:
    """II: a címkézett rendelésekből a tisztított tanító ablak méretű tanító- és az időbeli teszt
    méretű, tőle diszjunkt teszt-rész, véletlenül."""
    pool = b.X.index.sort_values()
    n_tr, n_te = len(b.train_idx), len(b.split.test)
    if n_tr + n_te > len(pool):
        raise ValueError("A véletlen felosztáshoz kevés a címkézett rendelés.")
    perm = np.random.default_rng(seed + r).permutation(len(pool))
    return pool[np.sort(perm[:n_tr])], pool[np.sort(perm[n_tr:n_tr + n_te])]


def random_inner_split(b: Bundle, r: int, seed: int = SEED, frac: float = INNER_FRAC) -> tuple[pd.Index, pd.Index]:
    """III: a tisztított tanító ablak véletlen (1 − frac) / frac felosztása."""
    pool = b.train_idx.sort_values()
    n_ev = int(round(frac * len(pool)))
    perm = np.random.default_rng(seed + 1000 + r).permutation(len(pool))
    return pool[np.sort(perm[n_ev:])], pool[np.sort(perm[:n_ev])]


def chrono_inner_split(b: Bundle, frac: float = INNER_FRAC) -> tuple[pd.Index, pd.Index, pd.Timestamp]:
    """III/b: a tisztított tanító ablak utolsó `frac` része (a leadás ideje szerint, éjfélre
    kerekített vágással) az értékelő rész; tanítás az addig eldőlt címkéken."""
    ts = pd.to_datetime(b.meta["rendeles_idopont"]).loc[b.train_idx]
    cut = ts.quantile(1.0 - frac).normalize()
    before = ts.index[ts < cut]
    train = settled_before(before, b.meta["vallalt_hatarido"], cut).sort_values()
    evaluate = ts.index[ts >= cut].sort_values()
    return train, evaluate, cut


# ------------------------------------------------------------------ futás
def run(b: Bundle, kinds=KINDS, r: int = R, verbose: bool = True) -> dict:
    t_start = time.time()
    kinds = tuple(kinds)

    def log(msg):
        if verbose:
            print(f"[{time.time() - t_start:6.0f} mp] {msg}", flush=True)

    seed = int(b.info.get("mag", 42))
    X, y, te = b.X, b.y, b.split.test
    out = {"I": {}, "II": {k: [] for k in kinds}, "III_ben": {k: [] for k in kinds},
           "III_kivul": {k: [] for k in kinds}, "IIIb": {}}
    for k in kinds:
        out["I"][k] = metrics(y.loc[te], _proba(b.models[k], X.loc[te]))
    log("I. időbeli teszt: kész")

    for i in range(r):
        tr, ev = random_full_split(b, i)
        models = fit_models(b, tr, seed, kinds)
        for k in kinds:
            out["II"][k].append(metrics(y.loc[ev], _proba(models[k], X.loc[ev])))
        log(f"II. véletlen felosztás {i + 1}/{r}")

    for i in range(r):
        tr, ev = random_inner_split(b, i)
        models = fit_models(b, tr, seed, kinds)
        for k in kinds:
            out["III_ben"][k].append(metrics(y.loc[ev], _proba(models[k], X.loc[ev])))
            out["III_kivul"][k].append(metrics(y.loc[te], _proba(models[k], X.loc[te])))
        log(f"III. időn belüli ellenőrzés {i + 1}/{r}")

    tr, ev, cut = chrono_inner_split(b)
    models = fit_models(b, tr, seed, kinds)
    for k in kinds:
        out["IIIb"][k] = metrics(y.loc[ev], _proba(models[k], X.loc[ev]))
    log("III/b. időrendi ellenőrzés: kész")

    return {
        "letrehozva": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kod_ujjlenyomat": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "beallitas": {"ismetlesek": r, "mag": SEED, "belso_hanyad": INNER_FRAC, "felso_hanyad": TOP_SHARE,
                      "modell_mag": seed, "modellek": list(kinds),
                      "tanito_sorok": int(len(b.train_idx)), "teszt_sorok": int(len(te)),
                      "cimkezett_rendelesek": int(len(b.X)),
                      "idorendi_vagas": str(cut.date()), "idorendi_tanito": int(len(tr)),
                      "idorendi_ertekelo": int(len(ev))},
        "adat": {k: v for k, v in b.info.items() if k in ("adatforras", "tarhaz_epitve", "lightgbm_fak")},
        "valtozatok": VARIANTS,
        "eredmenyek": out,
        "osszegzes": summarize(out, kinds),
        "ido_mp": round(time.time() - t_start, 1),
    }


def summarize(out: dict, kinds) -> dict:
    s = {"II": {}, "III_ben": {}, "III_kivul": {}, "III_kulonbseg": {}}
    for k in kinds:
        for v in ("II", "III_ben", "III_kivul"):
            s[v][k] = {m: summary([x[m] for x in out[v][k]]) for m in METRICS}
        s["III_kulonbseg"][k] = {m: summary([a[m] - c[m] for a, c in zip(out["III_ben"][k], out["III_kivul"][k])])
                                 for m in METRICS}
    lg = "lightgbm"
    e = {}
    if lg in kinds:
        e["E1_II"] = {m: int(sum(x[m] > out["I"][lg][m] for x in out["II"][lg])) for m in E1_METRICS}
        e["E1_III"] = {m: int(sum(a[m] > c[m] for a, c in zip(out["III_ben"][lg], out["III_kivul"][lg])))
                       for m in E1_METRICS}
        if "logreg" in kinds:
            gap_i = out["I"][lg]["roc_auc"] - out["I"]["logreg"]["roc_auc"]
            gaps = [a["roc_auc"] - c["roc_auc"] for a, c in zip(out["II"][lg], out["II"]["logreg"])]
            e["E2"] = {"idobeli": gap_i, "veletlen": summary(gaps), "nagyobb": int(sum(g > gap_i for g in gaps))}
        e["E3"] = {"II_max_abs_pp": float(max(abs(x["kalibracio_pp"]) for x in out["II"][lg])),
                   "I_pp": out["I"][lg]["kalibracio_pp"]}
        e["ismetlesek"] = len(out["II"][lg])
    s["sejtesek"] = e
    return s


# ------------------------------------------------------------------ jelentés
def _n(x: float, d: int = 3) -> str:
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def _fmt(m: str, x: float) -> str:
    if m in ("bazis", "felso10"):
        return _n(100 * x, 1) + "%"
    if m == "emeles":
        return _n(x, 2) + "×"
    if m == "kalibracio_pp":
        return ("+" if x >= 0 else "") + _n(x, 2)
    return _n(x, 3)


def _rng(m: str, s: dict) -> str:
    return f"{_fmt(m, s['atlag'])} ({_fmt(m, s['min'])} – {_fmt(m, s['max'])})"


def report(res: dict) -> str:
    out, s, st = res["eredmenyek"], res["osszegzes"], res["beallitas"]
    kinds = st["modellek"]
    L = ["# Időbeli vagy véletlen felosztás — ugyanaz az adat, ugyanazok a beállítások", "",
         f"Készült: {res['letrehozva']} · kód-ujjlenyomat `{res['kod_ujjlenyomat'][:16]}…` · "
         f"{res['ido_mp']:.0f} mp. Az előre rögzített beállítások: döntési napló.", "",
         f"Címkézett rendelés: {st['cimkezett_rendelesek']}; a tisztított tanító ablak {st['tanito_sorok']} sor, "
         f"az időbeli teszt {st['teszt_sorok']} sor. Véletlen felosztás: {st['ismetlesek']} ismétlés "
         f"(mag {st['mag']} + r); zárójelben a legkisebb és a legnagyobb érték. Az időrendi belső "
         f"ellenőrzés vágása {st['idorendi_vagas']} ({st['idorendi_tanito']} tanító, "
         f"{st['idorendi_ertekelo']} értékelő sor).", ""]
    for k in kinds:
        L += [f"## {NAMES[k]}", "", "| mérőszám | " + " | ".join(VARIANTS[v] for v in ("I", "II", "III_ben", "III_kivul", "IIIb")) + " |",
              "|---|" + "---|" * 5]
        for m in METRICS:
            L.append(f"| {METRIC_NAMES[m]} | {_fmt(m, out['I'][k][m])} | {_rng(m, s['II'][k][m])} | "
                     f"{_rng(m, s['III_ben'][k][m])} | {_rng(m, s['III_kivul'][k][m])} | {_fmt(m, out['IIIb'][k][m])} |")
        L.append("")
    e = s.get("sejtesek") or {}
    if e:
        n = e["ismetlesek"]
        L += ["## Az előre rögzített sejtések", "",
              "E1 (LightGBM) — hány ismétlésben nagyobb a mérőszám:", "",
              "| mérőszám | véletlen felosztás > időbeli teszt | időn belül > időn kívül (ugyanaz a modell) |",
              "|---|---|---|"]
        for m in E1_METRICS:
            L.append(f"| {METRIC_NAMES[m]} | {e['E1_II'][m]}/{n} | {e['E1_III'][m]}/{n} |")
        L.append("")
        if "E2" in e:
            L += [f"E2 — a LightGBM ROC-AUC-előnye a logisztikus regresszióval szemben: az időbeli teszten "
                  f"{_n(e['E2']['idobeli'], 3)}, véletlen felosztásnál átlagosan {_n(e['E2']['veletlen']['atlag'], 3)} "
                  f"({_n(e['E2']['veletlen']['min'], 3)} – {_n(e['E2']['veletlen']['max'], 3)}); nagyobb "
                  f"{e['E2']['nagyobb']}/{n} ismétlésben.", ""]
        L += [f"E3 — kalibráció egészében: véletlen felosztásnál a legnagyobb eltérés "
              f"{_n(e['E3']['II_max_abs_pp'], 2)} pp, az időbeli teszten {_fmt('kalibracio_pp', e['E3']['I_pp'])} pp.", ""]
    L += ["## Olvasat", "",
          "A „véletlen felosztás” és az „időn belül” oszlop azt mutatja, amit egy időrendet figyelmen kívül hagyó "
          "értékelés jelentene; az „időbeli teszt” azt, amit a modell élesben, a jövőre nézve tud. A PR-AUC a "
          "késési aránytól függ (az időbeli teszten kisebb a késés), ezért mellette az emelés és a felső 10% is "
          "szerepel. A tanítóadat mindhárom esetben ugyanakkora vagy kisebb, mint a lezárt modelleké, a "
          "beállítások azonosak — a különbség a felosztásé.", ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="Időbeli vagy véletlen felosztás összevetése (lezárt beállítások).")
    ap.add_argument("--ismetlesek", type=int, default=R)
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--kimenet", type=Path, default=ROOT / "docs" / "felosztas_osszevetes.json")
    ap.add_argument("--jelentes", type=Path, default=None, help="csak a .md újraírása egy meglévő JSON-ból")
    a = ap.parse_args(argv)
    if a.jelentes:
        res = json.loads(a.jelentes.read_text(encoding="utf-8"))
        a.jelentes.with_suffix(".md").write_text(report(res), encoding="utf-8")
        return
    if a.ismetlesek != R and a.kimenet.resolve().parent == (ROOT / "docs").resolve():
        sys.exit("Próbafutás (nem az előre rögzített ismétlésszám) nem írhat a docs/ mappába — adj meg --kimenet-et.")
    b = load_bundle(a.db, verbose=True)
    res = run(b, r=a.ismetlesek)
    a.kimenet.parent.mkdir(parents=True, exist_ok=True)
    a.kimenet.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    a.kimenet.with_suffix(".md").write_text(report(res), encoding="utf-8")
    print(f"Eredmény: {a.kimenet} (és {a.kimenet.with_suffix('.md').name}); {res['ido_mp']} mp")


if __name__ == "__main__":
    main()
