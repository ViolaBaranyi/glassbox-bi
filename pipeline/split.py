"""
M2 — Időbeli szétvágás.

Véletlen szétvágás itt hamis eredményt adna: a valóságban mindig múltból
jósolunk jövőre. Ezért a három részt IDŐBEN vágjuk el egymástól.

    train       a legkorábbi ~70%   -> tanítás + belső keresztvalidáció
    validation  a következő ~15%    -> korai leállítás, hangolás, kalibráció
    test        a legutolsó ~15%    -> ehhez egyszer nyúlunk

A rendszerterv fix dátumokat ad meg. Ez a modul azokat használja, ha az adat
lefedi őket; ha nem (pl. szintetikus vagy szűkített adat), kvantilis alapján
számol határokat, és kiírja, mit használt.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# A rendszertervben rögzített határok (a valódi Olist adathoz).
PLANNED = {
    "train_end": pd.Timestamp("2018-03-01"),
    "valid_end": pd.Timestamp("2018-06-01"),
}
FRACTIONS = (0.70, 0.85)  # train vége, validáció vége


@dataclass
class Split:
    train: pd.Index
    valid: pd.Index
    test: pd.Index
    train_end: pd.Timestamp
    valid_end: pd.Timestamp
    source: str  # "tervezett" vagy "kvantilis"

    def describe(self, ts: pd.Series) -> str:
        rows = []
        for name, idx in [("train", self.train), ("valid", self.valid), ("test", self.test)]:
            if len(idx) == 0:
                rows.append(f"  {name:<6} ÜRES")
                continue
            sub = ts.loc[idx]
            rows.append(
                f"  {name:<6} {len(idx):>7,} sor   "
                f"{sub.min().date()} .. {sub.max().date()}"
            )
        return "\n".join(rows)


def temporal_split(timestamps: pd.Series) -> Split:
    ts = pd.to_datetime(timestamps)

    train_end, valid_end = PLANNED["train_end"], PLANNED["valid_end"]
    source = "tervezett"

    ok = (ts < train_end).any() and ((ts >= train_end) & (ts < valid_end)).any() \
        and (ts >= valid_end).any()
    if not ok:
        train_end = ts.quantile(FRACTIONS[0]).normalize()
        valid_end = ts.quantile(FRACTIONS[1]).normalize()
        source = "kvantilis"

    train = ts.index[ts < train_end]
    valid = ts.index[(ts >= train_end) & (ts < valid_end)]
    test = ts.index[ts >= valid_end]

    if min(len(train), len(valid), len(test)) == 0:
        raise ValueError(
            "Az időbeli szétvágás üres részt adott. Túl rövid az adat időszaka?"
        )
    return Split(train, valid, test, train_end, valid_end, source)


def expanding_cv_folds(timestamps: pd.Series, index: pd.Index, n_folds: int = 4):
    """
    Bővülő ablakos keresztvalidáció a tanító részen belül.

    Nem sima KFold: minden fold egy korábbi időszakon tanul, és a
    RÁKÖVETKEZŐN értékel — így utánozza azt, ahogy a modell élesben működne.
    Visszaad: [(train_idx, valid_idx), ...]
    """
    ts = pd.to_datetime(timestamps).loc[index].sort_values()
    cuts = [ts.quantile(q) for q in
            [(i + 1) / (n_folds + 1) for i in range(n_folds)]]

    folds = []
    for i, cut in enumerate(cuts):
        nxt = cuts[i + 1] if i + 1 < len(cuts) else ts.max() + pd.Timedelta(days=1)
        tr = ts.index[ts < cut]
        va = ts.index[(ts >= cut) & (ts < nxt)]
        if len(tr) and len(va):
            folds.append((tr, va))
    if not folds:
        raise ValueError("Nem sikerült bővülő ablakos foldokat képezni.")
    return folds
