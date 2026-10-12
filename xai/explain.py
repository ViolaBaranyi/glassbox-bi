"""
Magyarázatok (SHAP) a négy modellre, a 22 eredeti jellemzőre összevonva.

Melyik modellhez melyik magyarázó — és miért:

  LightGBM          a LightGBM saját, pontos TreeSHAP-ja (pred_contrib), LOG-ODDS
                    térben. A lezárt modell natív kategóriakezeléssel tanult, ehhez a
                    SHAP nem ad „interventional + valószínűség-tér" magyarázatot
                    (4. lelet) — ezért a pontos, log-odds térbeli felbontást használjuk.
                    Ellenőrizve: bitre egyezik a shap.TreeExplainer eredményével.
  log. regresszió   pontos lineáris SHAP: β · (z − E[z]) a transzformált térben,
                    LOG-ODDS; a hiány-jelző és a one-hot oszlopok az eredeti
                    jellemzőhöz összevonva.
  döntési fa,       shap.TreeExplainer (tree_path_dependent) a transzformált (one-hot)
  random forest     téren, VALÓSZÍNŰSÉG-térben (a sklearn-fák kimenete valószínűség).

Mindegyiknél: alapérték + Σ hozzájárulás = a modell kimenete a saját terében
(`additivity_error` ellenőrzi; a tesztek 1e-6 alatt követelik meg).

Megjelenítés százalékpontban: a log-odds hozzájárulásokat arányosan osztjuk szét
    Δp_i = φ_i · (p − p₀) / (logit p − logit p₀),    p₀ = σ(alapérték)
Ez additív (Σ Δp_i = p − p₀), előjel- és sorrendtartó, de NEM a valószínűség-tér
pontos Shapley-értéke — azt a KernelSHAP-kontrollkar méri (következő lépés).

Futtatás:
    python -m xai.explain                    # összegzés a teszt-időszak rendeléseire
    python -m xai.explain --rendeles <order_key>
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

from data.db import DB_PATH, WarehouseUnavailable, use_utf8_console
from pipeline.features import CATEGORICAL_FEATURES, FEATURE_INFO, FEATURES
from xai.models import KINDS, NAMES, Bundle, load_bundle


@dataclass
class Explanation:
    kind: str
    space: str               # "log-odds" vagy "valószínűség"
    base: np.ndarray         # soronként (n,)
    contrib: pd.DataFrame    # n × 22, a modell saját terében
    output: np.ndarray       # a modell kimenete a saját terében (logit vagy valószínűség)
    proba: np.ndarray        # a késés valószínűsége

    @property
    def p0(self) -> np.ndarray:
        return _sigmoid(self.base) if self.space == "log-odds" else self.base


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.asarray(z, dtype=float)))


def column_groups(names) -> list[str]:
    """A transzformált oszlopnevek → az eredeti jellemző neve (one-hot, hiány-jelző összevonva)."""
    out = []
    for n in names:
        if n.startswith("szam__"):
            rest = n[len("szam__"):]
            out.append(rest[len("missingindicator_"):] if rest.startswith("missingindicator_")
                       else rest)
        elif n.startswith("kat__"):
            rest = n[len("kat__"):]
            hits = [c for c in CATEGORICAL_FEATURES if rest.startswith(c + "_")]
            if not hits:
                raise ValueError(f"Ismeretlen kategória-oszlop: {n}")
            out.append(max(hits, key=len))
        else:
            raise ValueError(f"Ismeretlen transzformált oszlop: {n}")
    unknown = set(out) - set(FEATURES)
    if unknown:
        raise ValueError(f"Nem jellemzőre képződő oszlop(ok): {sorted(unknown)}")
    return out


def _grouped(values: np.ndarray, groups: list[str], index) -> pd.DataFrame:
    df = pd.DataFrame(values, columns=range(values.shape[1]), index=index)
    g = df.T.groupby(np.asarray(groups)).sum().T
    return g.reindex(columns=FEATURES, fill_value=0.0)


def explain(kind: str, model, X_rows: pd.DataFrame,
            background: pd.DataFrame | None = None) -> Explanation:
    """A `kind` modell magyarázata az X_rows soraira (a háttér csak a lineáris modellhez kell)."""
    if kind == "lightgbm":
        c = model.booster_.predict(X_rows, pred_contrib=True)
        base = c[:, -1]
        contrib = pd.DataFrame(c[:, :-1], columns=list(model.booster_.feature_name()),
                               index=X_rows.index).reindex(columns=FEATURES, fill_value=0.0)
        out = c.sum(axis=1)
        return Explanation(kind, "log-odds", base, contrib, out, _sigmoid(out))

    pre, clf = model[:-1], model.named_steps["modell"]
    names = model.named_steps["elofeldolgozas"].get_feature_names_out()
    groups = column_groups(names)
    Z = np.asarray(pre.transform(X_rows), dtype=float)

    if kind == "logreg":
        if background is None:
            raise ValueError("A lineáris magyarázathoz háttérminta kell (Bundle.background()).")
        Zb = np.asarray(pre.transform(background), dtype=float)
        beta, b0 = clf.coef_[0], float(clf.intercept_[0])
        mu = Zb.mean(axis=0)
        phi = (Z - mu) * beta
        base = np.full(len(Z), b0 + float(mu @ beta))
        out = b0 + Z @ beta
        return Explanation(kind, "log-odds", base, _grouped(phi, groups, X_rows.index),
                           out, _sigmoid(out))

    if kind in ("dontesi_fa", "random_forest"):
        import shap
        te = shap.TreeExplainer(clf)                       # tree_path_dependent
        sv = np.asarray(te.shap_values(Z))
        phi = sv[:, :, 1] if sv.ndim == 3 else sv
        ev = np.atleast_1d(te.expected_value)
        base = np.full(len(Z), float(ev[1] if len(ev) > 1 else ev[0]))
        proba = clf.predict_proba(Z)[:, 1]
        return Explanation(kind, "valószínűség", base, _grouped(phi, groups, X_rows.index),
                           proba, proba)

    raise ValueError(f"Ismeretlen modell: {kind!r}")


def additivity_error(e: Explanation) -> float:
    """max |alapérték + Σ hozzájárulás − kimenet| a modell saját terében."""
    return float(np.max(np.abs(e.base + e.contrib.to_numpy().sum(axis=1) - e.output)))


def percentage_points(e: Explanation) -> pd.DataFrame:
    """Hozzájárulás százalékpontban (soronként Σ = p − p₀)."""
    if e.space == "valószínűség":
        return e.contrib * 100.0
    total = e.contrib.to_numpy().sum(axis=1)
    p, p0 = e.proba, e.p0
    with np.errstate(divide="ignore", invalid="ignore"):
        factor = np.where(np.abs(total) > 1e-12, (p - p0) / total, p0 * (1 - p0))
    return e.contrib.mul(factor * 100.0, axis=0)


def global_importance(e: Explanation) -> pd.Series:
    """Átlagos abszolút hozzájárulás százalékpontban, csökkenő sorrendben."""
    return percentage_points(e).abs().mean().sort_values(ascending=False)


def top_reasons(e: Explanation, X_rows: pd.DataFrame, row: int = 0, k: int = 5) -> pd.DataFrame:
    """Egy rendelés legfontosabb okai: jellemző, értéke, hatása százalékpontban."""
    pp = percentage_points(e).iloc[row]
    order = pp.abs().sort_values(ascending=False).index[:k]
    x = X_rows.iloc[row]
    return pd.DataFrame({
        "jellemzo": order,
        "leiras": [FEATURE_INFO[f][1] for f in order],
        "ertek": [x[f] for f in order],
        "hatas_szazalekpont": [round(float(pp[f]), 2) for f in order],
    })


# ---------------------------------------------------------------- parancssor
def _summary(bundle: Bundle, n_rows: int = 300, seed: int = 0) -> None:
    test = bundle.X.loc[bundle.split.test]
    sample = test.sample(min(n_rows, len(test)), random_state=seed)
    bg = bundle.background()
    print(f"Magyarázatok {len(sample)} teszt-időszaki rendelésen "
          f"(a random forest lassú: soronként kb. 0,3 mp).\n")
    imp = {}
    for kind in KINDS:
        e = explain(kind, bundle.models[kind], sample, bg)
        imp[NAMES[kind]] = global_importance(e)
        print(f"  {NAMES[kind]:<24} tér: {e.space:<13} additivitási hiba: {additivity_error(e):.1e}")
    tab = pd.DataFrame(imp).fillna(0.0)
    tab = tab.loc[tab.max(axis=1).sort_values(ascending=False).index]
    print("\nÁTLAGOS HATÁS (százalékpont, abszolút) — a 10 legfontosabb jellemző:")
    print(tab.head(10).round(2).to_string())


def _one(bundle: Bundle, order_key) -> None:
    hit = bundle.meta.index[bundle.meta["order_key"].astype(str) == str(order_key)]
    if len(hit) == 0:
        raise ValueError(f"Nincs ilyen rendelés: {order_key}")
    row = bundle.X.loc[hit]
    bg = bundle.background()
    print(f"Rendelés: {order_key} · leadva {bundle.meta.loc[hit[0], 'rendeles_idopont']}")
    for kind in KINDS:
        e = explain(kind, bundle.models[kind], row, bg)
        print(f"\n  {NAMES[kind]} — késés valószínűsége {e.proba[0]:.1%} "
              f"(alap: {e.p0[0]:.1%})")
        for r in top_reasons(e, row).itertuples():
            print(f"    {r.hatas_szazalekpont:+6.2f} pp   {r.leiras} = {r.ertek}")


def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="SHAP-magyarázatok a négy modellre")
    ap.add_argument("--rendeles", type=str, default=None, help="egy rendelés kulcsa (order_key)")
    ap.add_argument("--sorok", type=int, default=300, help="összegzéshez ennyi teszt-rendelés")
    a = ap.parse_args()
    try:
        bundle = load_bundle(DB_PATH, verbose=True)
        _one(bundle, a.rendeles) if a.rendeles else _summary(bundle, a.sorok)
    except (WarehouseUnavailable, ValueError) as exc:
        print(f"\nHIBA:\n{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
