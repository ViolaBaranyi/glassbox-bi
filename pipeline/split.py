"""
M2 — Időbeli szétvágás.

Véletlen szétvágás itt hamis eredményt adna: a valóságban mindig múltból
jósolunk jövőre. Ezért a három részt IDŐBEN vágjuk el egymástól.

    train       a legkorábbi ~70%   -> tanítás + bővülő ablakos keresztvalidáció
                                       (ez választja a fák számát, lásd model_selection)
    validation  a következő ~15%    -> korai leállítás (régi út), ill. időn kívüli
                                       ellenőrzés (a bővülő ablakos útnál)
    test        a legutolsó ~15%    -> ehhez egyszer nyúlunk (lezárt alapfutás)

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


@dataclass
class CVFold:
    """Egy hajtás: a vágás ELŐTTI időszakon tanul, a rákövetkező szakaszon értékel."""
    train: pd.Index
    valid: pd.Index
    cut: pd.Timestamp        # a tanítás vége = az értékelés kezdete (éjfél)
    valid_end: pd.Timestamp  # az értékelő szakasz vége (kizárólagos, éjfél)


def expanding_cv_folds(timestamps: pd.Series, index: pd.Index,
                       n_folds: int = 4) -> list[CVFold]:
    """
    Bővülő ablakos keresztvalidáció a tanító részen belül.

    Nem sima KFold: minden hajtás egy korábbi időszakon tanul, és a
    RÁKÖVETKEZŐN értékel — így utánozza azt, ahogy a modell élesben működne.
    A vágások a rendelések kvantilisein vannak (egyforma méretű értékelő
    szakaszok), napra kerekítve: egy vágás mindig éjfélkor van, így egy nap
    rendelései nem kerülhetnek két oldalra.
    """
    ts = pd.to_datetime(timestamps).loc[index].sort_values()
    cuts = sorted({ts.quantile((i + 1) / (n_folds + 1)).normalize()
                   for i in range(n_folds)})
    end = ts.max().normalize() + pd.Timedelta(days=1)

    folds = []
    for i, cut in enumerate(cuts):
        nxt = cuts[i + 1] if i + 1 < len(cuts) else end
        tr = ts.index[ts < cut]
        va = ts.index[(ts >= cut) & (ts < nxt)]
        if len(tr) and len(va):
            folds.append(CVFold(tr, va, cut, nxt))
    if not folds:
        raise ValueError("Nem sikerült bővülő ablakos hajtásokat képezni.")
    return folds


def settled_before(index: pd.Index, promised: pd.Series, cut: pd.Timestamp) -> pd.Index:
    """
    A tanító sorok közül azok, amelyeknek a KIMENETE a vágás pillanatában már
    biztosan eldőlt: a vállalt határidejük napja a vágás előtt véget ért.

    Miért kell? A jellemzőknél már érvényes a point-in-time szabály (csak a
    leadáskor ismert információ). A CÍMKÉRE ugyanez igaz: egy február végén
    leadott rendelésről március 1-jén még nem tudjuk, késik-e. Ha mégis
    tanítunk rajta, a modell a vágás UTÁNI időszak szállítási viszonyait is
    látja (a valódi adatban a 2018-03-01-i vágásnál a tanító sorok 6,2%-a ilyen,
    és ezek 26,6%-a késett — a márciusi válság).

    Miért a vállalt határidő, és nem az, hogy „kézbesítették-e már"?
    Ha a már kézbesítetteket megtartanánk, a vágás közelében csak a GYORSAN
    (tehát időben) megérkezett rendelések maradnának bent — a kimenet szerinti
    válogatás torzítaná a címkét. A vállalt határidő a leadáskor ismert, ezért
    az e szerinti szűrés a kimenettől független: aminek a határideje lejárt,
    annak a sorsa eldőlt (időben megjött, vagy késett).
    """
    pr = pd.to_datetime(promised).loc[index]
    keep = (pr + pd.Timedelta(days=1)) <= cut      # a határidő NAPJA is véget ért
    return index[keep.fillna(False).to_numpy(dtype=bool)]
