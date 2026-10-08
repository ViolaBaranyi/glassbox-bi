"""
Bizonytalanság heti blokk-bootstrappal (útiterv T5; témavezetői kérés:
„bootstrap a magok helyett").

Miért blokk? A késések hétről hétre együtt mozognak (szállítási csúcsok,
sztrájk, ünnepek). Ha rendelésenként mintavételeznénk újra, úgy tennénk,
mintha a teszt 18 603 egymástól független megfigyelés lenne, és a
konfidencia-intervallum hamisan szűk lenne. Ezért EGÉSZ HETEKET húzunk
visszatevéssel: egy újramintavétel ugyanannyi hétből áll, mint az eredeti
ablak, és minden húzott hét összes rendelése bekerül.

Páros változat: két előrejelzést (pl. a modellt és a tanító időszak arányát
mondó konstans előrejelzést) UGYANAZOKON a húzott heteken hasonlítunk össze.
A különbség intervallumából így kiesik az, ami mindkettőt egyformán érinti
(egy nehéz hét mindkettőnek nehéz).

Az intervallum percentilis módszerrel készül (95%: a 2,5. és a 97,5. percentilis).
A tanítási véletlent (a modell magja) ez NEM méri — azt külön, több maggal
jelentjük.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from pipeline.train import expected_calibration_error

B_DEFAULT = 2000
SEED_DEFAULT = 20261008


def _brier(y, p):
    return float(np.mean((np.asarray(p, dtype=float) - y) ** 2))


METRICS = {
    "pr_auc": lambda y, p: float(average_precision_score(y, p)),
    "roc_auc": lambda y, p: float(roc_auc_score(y, p)),
    "brier": _brier,
    "ece": lambda y, p: expected_calibration_error(y, p, strategy="uniform"),
    "ece_egyenlo_elemszam": lambda y, p: expected_calibration_error(y, p, strategy="quantile"),
}
# az osztálytól függő mérőszámok egy osztályú mintán nem értelmezettek
_NEEDS_BOTH_CLASSES = {"pr_auc", "roc_auc"}


def week_blocks(timestamps) -> np.ndarray:
    """ISO-hét azonosító (év*100 + hét) — a hét hétfőn kezdődik."""
    iso = pd.to_datetime(pd.Series(np.asarray(timestamps))).dt.isocalendar()
    return (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()


def _members(blocks) -> list[np.ndarray]:
    blocks = np.asarray(blocks)
    uniq, inv = np.unique(blocks, return_inverse=True)
    if len(uniq) < 2:
        raise ValueError("A blokk-bootstraphoz legalább két blokk (hét) kell.")
    return [np.flatnonzero(inv == k) for k in range(len(uniq))]


def resample_indices(blocks, B: int = B_DEFAULT, seed: int = SEED_DEFAULT):
    """B darab újramintavétel sorindexei; mindegyik egész blokkokból áll."""
    members = _members(blocks)
    rng = np.random.default_rng(seed)
    k = len(members)
    for _ in range(B):
        draw = rng.integers(0, k, k)
        yield np.concatenate([members[j] for j in draw])


def _point(metrics, y, p) -> dict:
    return {name: fn(y, p) for name, fn in metrics.items()}


def _summary(point: float, draws: np.ndarray, alpha: float) -> dict:
    ok = draws[~np.isnan(draws)]
    lo, hi = np.quantile(ok, [alpha / 2, 1 - alpha / 2]) if len(ok) else (np.nan, np.nan)
    return {"ertek": round(float(point), 5),
            "ci95": [round(float(lo), 5), round(float(hi), 5)],
            "se": round(float(np.std(ok, ddof=1)), 5) if len(ok) > 1 else None,
            "ervenyes_huzasok": int(len(ok))}


def block_bootstrap(y, p, blocks, metrics=None, B: int = B_DEFAULT,
                    seed: int = SEED_DEFAULT, alpha: float = 0.05) -> dict:
    """Mérőszámonként: pontbecslés, 95%-os percentilis-intervallum, szórás."""
    metrics = metrics or METRICS
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    draws = {name: [] for name in metrics}
    for idx in resample_indices(blocks, B, seed):
        yy, pp = y[idx], p[idx]
        both = 0 < yy.sum() < len(yy)
        for name, fn in metrics.items():
            draws[name].append(fn(yy, pp) if both or name not in _NEEDS_BOTH_CLASSES
                               else np.nan)
    point = _point(metrics, y, p)
    out = {name: _summary(point[name], np.asarray(draws[name], dtype=float), alpha)
           for name in metrics}
    out["_beallitas"] = {"B": B, "mag": seed, "blokkok": len(np.unique(np.asarray(blocks))),
                         "intervallum": f"percentilis, {1 - alpha:.0%}"}
    return out


def paired_block_bootstrap(y, p_a, p_b, blocks, metrics=None, B: int = B_DEFAULT,
                           seed: int = SEED_DEFAULT, alpha: float = 0.05) -> dict:
    """
    A − B különbség mérőszámonként, ugyanazokon a húzott heteken.
    PR-AUC, ROC-AUC: a nagyobb a jobb; Brier, ECE: a kisebb a jobb.
    """
    metrics = metrics or METRICS
    y = np.asarray(y, dtype=int)
    p_a = np.asarray(p_a, dtype=float)
    p_b = np.asarray(p_b, dtype=float)
    diffs = {name: [] for name in metrics}
    for idx in resample_indices(blocks, B, seed):
        yy = y[idx]
        both = 0 < yy.sum() < len(yy)
        for name, fn in metrics.items():
            if not both and name in _NEEDS_BOTH_CLASSES:
                diffs[name].append(np.nan)
            else:
                diffs[name].append(fn(yy, p_a[idx]) - fn(yy, p_b[idx]))
    pa, pb = _point(metrics, y, p_a), _point(metrics, y, p_b)
    out = {}
    for name in metrics:
        s = _summary(pa[name] - pb[name], np.asarray(diffs[name], dtype=float), alpha)
        out[name] = {"a": round(float(pa[name]), 5), "b": round(float(pb[name]), 5),
                     "kulonbseg": s["ertek"], "ci95": s["ci95"], "se": s["se"],
                     "ervenyes_huzasok": s["ervenyes_huzasok"]}
    out["_beallitas"] = {"B": B, "mag": seed, "blokkok": len(np.unique(np.asarray(blocks))),
                         "intervallum": f"percentilis, {1 - alpha:.0%}"}
    return out
