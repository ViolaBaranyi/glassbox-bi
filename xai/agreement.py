"""
Két magyarázat egyezése — rangsor- és halmazmértékek (a kontrollkarhoz és a stabilitáshoz).

Egy magyarázat itt egy hozzájárulás-vektor ugyanazokon a tényezőkön. A rangsor a
tényezők sorrendje |hatás| szerint csökkenően (egyezésnél a tényezők rögzített
sorrendje dönt, így a rangsor determinisztikus).

    top_k_overlap   |top-k(a) ∩ top-k(b)| / k — „ugyanaz-e a 3 legfontosabb tényező?"
    rbo             rank-biased overlap (Webber, Moffat és Zobel, 2010), p = 0,9:
                    a rangsor elejét súlyozza; 1 = azonos rangsor. A p = 0,9 mellett az
                    első 10 hely viszi a súly kb. 86%-át (a témavezetői pontosítás szerint)
    weighted_tau    súlyozott Kendall-tau (Vigna, 2015; scipy.stats.weightedtau) |hatás|-on:
                    a rangsor elején lévő cserék többet számítanak
    sign_agreement  a top-k tényezők közül hánynak egyezik az iránya (növeli / csökkenti)
    rel_l1          Σ|a − b| / Σ|b| — mekkora a teljes eltérés a b-hez (a viszonyítási
                    magyarázathoz) képest

A mértékek egy rendelésre (két vektorra) vonatkoznak; a `summary` sok rendelés
átlagát adja percentilis bootstrap-intervallummal (a rendelések újramintavételével).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ranking(values, names=None) -> list:
    """A tényezők |érték| szerint csökkenő sorrendben (egyezésnél a megadott sorrend)."""
    v = np.abs(np.asarray(values, dtype=float))
    names = list(range(len(v))) if names is None else list(names)
    order = np.argsort(-v, kind="stable")
    return [names[i] for i in order]


def top_k_overlap(a, b, k: int = 3) -> float:
    ra, rb = ranking(a), ranking(b)
    return len(set(ra[:k]) & set(rb[:k])) / float(k)


def rbo(r1: list, r2: list, p: float = 0.9) -> float:
    """
    Kiterjesztett RBO két, ugyanazokat az elemeket tartalmazó, azonos hosszú rangsorra
    (Webber és mtsai., 2010, 32. képlet):
        RBO = (X_k / k) · p^k + (1 − p)/p · Σ_{d=1..k} (X_d / d) · p^d
    ahol X_d az első d elem közös része. Azonos rangsorra pontosan 1.
    """
    if len(r1) != len(r2):
        raise ValueError("Az RBO itt azonos hosszú rangsorokat vár.")
    if not 0 < p < 1:
        raise ValueError("p a (0, 1) intervallumban legyen.")
    k = len(r1)
    if k == 0:
        return 1.0
    seen1, seen2, overlap, acc = set(), set(), 0, 0.0
    for d in range(1, k + 1):
        x, y = r1[d - 1], r2[d - 1]
        if x == y:
            overlap += 1
        else:
            overlap += (x in seen2) + (y in seen1)
        seen1.add(x)
        seen2.add(y)
        acc += (overlap / d) * p ** d
    return float((overlap / k) * p ** k + (1 - p) / p * acc)


def rbo_values(a, b, p: float = 0.9) -> float:
    """RBO két hozzájárulás-vektor |érték| szerinti rangsorán."""
    return rbo(ranking(a), ranking(b), p)


def weighted_tau(a, b) -> float:
    """Súlyozott Kendall-tau |a| és |b| között (hiperbolikus súly a rangsor elején)."""
    from scipy.stats import weightedtau
    x, y = np.abs(np.asarray(a, dtype=float)), np.abs(np.asarray(b, dtype=float))
    if np.allclose(x, x[0]) or np.allclose(y, y[0]):
        return float("nan")               # konstans vektornak nincs rangsora
    return float(weightedtau(x, y).statistic)


def sign_agreement(a, b, k: int = 3) -> float:
    """Az a szerinti top-k tényezők közül hánynak azonos az előjele b-ben."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    top = ranking(a)[:k]
    return float(np.mean([np.sign(a[i]) == np.sign(b[i]) for i in top]))


def rel_l1(a, b) -> float:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    den = np.abs(b).sum()
    return float(np.abs(a - b).sum() / den) if den > 0 else float("nan")


METRICS = {
    "top3": lambda a, b: top_k_overlap(a, b, 3),
    "rbo": rbo_values,
    "wtau": weighted_tau,
    "elojel3": lambda a, b: sign_agreement(b, a, 3),   # a viszonyítás (b) top-3-ja szerint
    "rel_l1": rel_l1,
}


def compare_frames(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """
    Soronként (rendelésenként) minden mérték két magyarázat-tábla között
    (azonos index és oszlopok; b a viszonyítási alap).
    """
    if list(a.columns) != list(b.columns):
        raise ValueError("A két magyarázat más tényezőkön van.")
    common = a.index.intersection(b.index)
    rows = []
    for i in common:
        x, y = a.loc[i].to_numpy(), b.loc[i].to_numpy()
        rows.append({name: f(x, y) for name, f in METRICS.items()})
    return pd.DataFrame(rows, index=common)


def mean_ci(values, n_boot: int = 2000, seed: int = 0) -> dict:
    """Átlag és 95%-os percentilis bootstrap-intervallum (a rendelések újramintavételével)."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return {"atlag": float("nan"), "ci95": [float("nan"), float("nan")], "n": 0}
    rng = np.random.default_rng(seed)
    boots = v[rng.integers(0, len(v), size=(n_boot, len(v)))].mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"atlag": float(v.mean()), "ci95": [float(lo), float(hi)], "n": int(len(v))}


def summary(table: pd.DataFrame, n_boot: int = 2000, seed: int = 0) -> dict:
    """Mértékenként átlag + 95% CI egy compare_frames-táblán."""
    return {m: mean_ci(table[m], n_boot, seed) for m in table.columns}
