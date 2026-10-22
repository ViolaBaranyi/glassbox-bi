"""
Határidő-görbe: mit becsülne a modell ugyanarra a rendelésre, ha a platform más szállítási
időt vállalna? (Az ellenpéldás magyarázat — DiCE — helyett; Viola döntése, 2026-10-22.)

Egyetlen jellemző változik: a vállalt szállítási idő (`vallalt_ido_nap` = a vállalt határidő
napja − a rendelés napja). A többi jellemző — az ünnep közelsége és a hónap is, amelyek a rendelés
napjából jönnek — változatlan. A görbe a lezárt modellek becslését mutatja 1 és 60 nap között
(és a rendelés saját értékénél, ha az ezen kívül esik).

Három korlát, amelyet a felület is kimond:
  1. a görbe a MODELL viselkedése, nem oksági állítás: nem azt mondja meg, mi történne, ha a
     platform tényleg mást ígérne;
  2. a késést a vállalt határidőhöz mérjük — hosszabb határidőnél ugyanaz a szállítás ritkábban
     számít késésnek, így a görbe esése ezt is tartalmazza, nem a szállítás gyorsulását;
  3. a tanítóadatban a vállalt idő legalább 8 nap volt (1–99%: 11–51 nap); ezen kívül a modell nem
     tanult. A fa-alapú modellek ott laposak (a legszélső tanult értéket viszik tovább), a
     logisztikus regresszió egyenesen folytatja a vonalat — egyik sem megbízható.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from xai.models import NAMES, Bundle

FEATURE = "vallalt_ido_nap"
DAYS = tuple(range(1, 61))
RANGE_Q = (0.01, 0.99)


def training_range(b: Bundle) -> dict:
    """A vállalt idő a (tisztított) tanítóadatban: legkisebb, legnagyobb, 1. és 99. percentilis."""
    v = b.X.loc[b.train_idx, FEATURE].dropna().astype(float)
    lo, hi = (float(v.quantile(q)) for q in RANGE_Q)
    return {"min": float(v.min()), "max": float(v.max()), "also": lo, "felso": hi,
            "median": float(v.median()), "sorok": int(len(v))}


def variants(row: pd.DataFrame, grid) -> pd.DataFrame:
    """A rendelés másolatai, csak a vállalt idő más (a rács értékei); minden más oszlop és típus marad."""
    rows = pd.concat([row] * len(grid), ignore_index=True)
    rows[FEATURE] = np.asarray(list(grid), dtype=row[FEATURE].dtype)
    return rows


def outside_share(b: Bundle, idx) -> float:
    """Az adott rendelések hány százalékánál rövidebb a vállalt idő a tanítóadat legrövidebbjénél."""
    v = b.X.loc[idx, FEATURE].dropna()
    return float((v < training_range(b)["min"]).mean()) if len(v) else float("nan")


def curve(b: Bundle, row: pd.DataFrame, kinds=("lightgbm",), days=DAYS) -> pd.DataFrame:
    """Egy rendelés (egysoros X-tábla) becslése a vállalt idő függvényében, modellenként.

    Oszlopok: modell, kulcs, nap, valoszinuseg (0–1), jelenlegi (a rendelés saját értéke),
    tartomanyban (a tanítóadat 1–99%-os sávjában van-e)."""
    if len(row) != 1:
        raise ValueError("A határidő-görbe egyetlen rendelésre készül.")
    current = row[FEATURE].iloc[0]
    grid = sorted(set(int(d) for d in days) | ({int(current)} if pd.notna(current) else set()))
    rows = variants(row, grid)
    rng = training_range(b)
    out = []
    for kind in kinds:
        p = b.models[kind].predict_proba(rows)[:, 1]
        out.append(pd.DataFrame({
            "modell": NAMES[kind], "kulcs": kind, "nap": grid, "valoszinuseg": p.astype(float),
            "jelenlegi": [pd.notna(current) and d == int(current) for d in grid],
            "tartomanyban": [rng["also"] <= d <= rng["felso"] for d in grid]}))
    return pd.concat(out, ignore_index=True)


def at(cv: pd.DataFrame, kind: str, day: int) -> float | None:
    """A görbe értéke egy napnál (None, ha a nap nincs a rácson)."""
    hit = cv[(cv["kulcs"] == kind) & (cv["nap"] == int(day))]
    return float(hit["valoszinuseg"].iloc[0]) if len(hit) else None


def summary(cv: pd.DataFrame, b: Bundle, kind: str = "lightgbm", step: int = 7) -> dict:
    """A felület mondatához: a mostani érték, ±step nap, és hogy a mostani érték a tanult sávban van-e."""
    now = cv[(cv["kulcs"] == kind) & cv["jelenlegi"]]
    if now.empty:
        return {"nap": None}
    d0, p0 = int(now["nap"].iloc[0]), float(now["valoszinuseg"].iloc[0])
    rng = training_range(b)
    return {"nap": d0, "most": p0,
            "hosszabb_nap": d0 + step, "hosszabb": at(cv, kind, d0 + step),
            "rovidebb_nap": d0 - step, "rovidebb": at(cv, kind, d0 - step) if d0 - step >= 1 else None,
            "tanult_savban": rng["also"] <= d0 <= rng["felso"],
            "tanitoban_elofordult": rng["min"] <= d0 <= rng["max"], "tartomany": rng}

