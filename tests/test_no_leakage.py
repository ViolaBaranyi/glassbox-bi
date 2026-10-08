"""
BLOKKOLÓ tesztek: adatszivárgás.

Ez nem "minőségbiztosítás", hanem előfeltétel. Ha szivárgás van, az összes
többi mérés hazug számokat hitelesít. Ezért ezeknek minden betanítás előtt
és minden push-ra le kell futniuk.

A tesztek három dolgot ellenőriznek:
  1. a névszűrő — tiltott oszlop nem kerülhet a jellemzők közé;
  2. a point-in-time korrektség — nyers erővel újraszámolva, nem a pandasnak
     elhíve: az előzmény-jellemzők csak a rendelés pillanatában MÁR ISMERT
     kimeneteket láthatják;
  3. az AUC-őr — az ártatlan nevű, de a jövőből származó jellemzőt is elkapja.

Futtatás:
    python -m pytest tests/ -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data.db import DB_PATH, connect
from pipeline.features import (
    FEATURES,
    LeakageError,
    assert_no_leakage,
    build_features,
    suspicious_features,
)
from pipeline.split import temporal_split


@pytest.fixture(scope="module")
def data():
    if not DB_PATH.exists():
        pytest.skip(
            "Nincs tárház. Futtasd előbb (vagy: python demo.py):\n"
            "  python -m data.fetch_olist\n"
            "  python -m data.build_warehouse"
        )
    con = connect()
    X, y, meta = build_features(con)
    raw = con.execute(
        "SELECT order_key, seller_key, rendeles_idopont, feladas_datuma, "
        "kezbesites_datuma, vallalt_hatarido, kesett FROM fact_orders"
    ).df()
    con.close()
    for c in ["rendeles_idopont", "feladas_datuma", "kezbesites_datuma", "vallalt_hatarido"]:
        raw[c] = pd.to_datetime(raw[c])
    # A nyers sorokat a jellemzőmátrix sorrendjébe rendezzük.
    raw = raw.set_index("order_key").loc[meta["order_key"]].reset_index()
    return X, y, meta, raw


# ======================================================== 1. névszűrő
def test_csak_feherlistas_oszlopok(data):
    """A jellemzőmátrix pontosan a FEATURES szerződést követi."""
    X, *_ = data
    assert list(X.columns) == FEATURES


def test_minden_jellemzonek_van_leirasa():
    """A jellemzőtáblázat (FEATURE_INFO) a szerződéssel együtt mozog — a
    dolgozat és a README ebből készül, nem csúszhat el a kódtól."""
    from pipeline.features import FEATURE_INFO
    assert set(FEATURE_INFO) == set(FEATURES)
    assert len(FEATURES) == 22


def test_tiltott_oszlop_nincs_bent(data):
    X, *_ = data
    assert_no_leakage(X.columns)  # nem dobhat kivételt


@pytest.mark.parametrize("rossz_oszlop", [
    "kezbesites_datuma",
    "review_score",
    "kesett",
    "order_delivered_customer_date",
    "feladas_datuma",
])
def test_a_nevszuro_tenyleg_fog(rossz_oszlop):
    """Ha az őr nem szól egy nyilvánvalóan tiltott oszlopra, akkor hasztalan."""
    with pytest.raises(LeakageError):
        assert_no_leakage(list(FEATURES) + [rossz_oszlop])


# ============================================== 2. point-in-time korrektség
def _check_asof(X, raw, rows, known_at, value_of, feature):
    """Nyers erővel: minden vizsgált sorra kézzel újraszámolja az előzményt."""
    for i in rows:
        r = raw.iloc[i]
        same = raw[raw["seller_key"] == r["seller_key"]]
        known = same[same[known_at] < r["rendeles_idopont"]]   # SZIGORÚAN korábban ismert
        vals = value_of(known).dropna()
        expected = float(vals.mean()) if len(vals) else np.nan
        got = X[feature].iloc[i]
        if np.isnan(expected):
            assert pd.isna(got), (
                f"{feature}: a {i}. sornál még nem lehetett ismert előzmény, "
                f"mégis {got} jött ki.")
        else:
            assert abs(got - expected) < 1e-9, (
                f"{feature}: point-in-time hiba a {i}. sornál — "
                f"várt {expected:.6f}, kapott {got:.6f}.")


def _sample_rows(raw, n_random=300, top_sellers=3, seed=0):
    top = raw["seller_key"].value_counts().head(top_sellers).index
    rows = set(np.flatnonzero(raw["seller_key"].isin(top)))
    rng = np.random.default_rng(seed)
    rows |= set(rng.choice(len(raw), size=min(n_random, len(raw)), replace=False))
    return sorted(rows)


def test_keses_arany_csak_mar_ismert_kimenetekbol(data):
    """
    A kulcsteszt. Az eladó korábbi késési aránya csak olyan rendelésekből
    számolódhat, amelyek a mostani rendelés PILLANATÁBAN már kézbesítve voltak.
    Egy tegnap leadott, még úton lévő rendelés kimenete ma még ismeretlen.
    """
    X, _, _, raw = data
    _check_asof(X, raw, _sample_rows(raw), "kezbesites_datuma",
                lambda k: k["kesett"].astype(float), "elado_korabbi_keses_arany")


def test_feladasi_ido_csak_mar_ismert_kimenetekbol(data):
    """Ugyanez a feladási időre: csak a már futárnak átadott rendelésekből."""
    X, _, _, raw = data

    def handling(k):
        d = (k["feladas_datuma"] - k["rendeles_idopont"]).dt.total_seconds() / 86400.0
        return d.where(d >= 0)

    _check_asof(X, raw, _sample_rows(raw, n_random=150), "feladas_datuma",
                handling, "elado_atlagos_feladas_nap")


def test_elso_rendelesnel_nincs_elozmeny(data):
    """Egy eladó legelső rendelésénél semmilyen kimenet nem lehet még ismert."""
    X, *_ = data
    elsok = X["elado_korabbi_rendelesek"] == 0
    assert elsok.any(), "Nincs egyetlen 'első rendelés' sem — gyanús."
    assert X.loc[elsok, "elado_korabbi_keses_arany"].isna().all()
    assert X.loc[elsok, "elado_atlagos_feladas_nap"].isna().all()


# ================================================================= 3. AUC-őr
def test_egyetlen_jellemzo_sem_gyanusan_jos(data):
    X, y, *_ = data
    assert suspicious_features(X, y) == []


def test_az_auc_or_elkapja_a_rejtett_szivargot(data):
    """
    Egy ártatlan nevű, de a jövőből származó jellemző: hány nappal a vállalt
    határidő után érkezett a csomag. A névszűrőn átcsúszik — az AUC-őrnek
    kell elkapnia. Ez adatfüggetlen: a címke szinte közvetlenül ebből áll elő.
    """
    X, y, _, raw = data
    X2 = X.copy()
    X2["logisztikai_mutato"] = (
        (raw["kezbesites_datuma"].dt.normalize() - raw["vallalt_hatarido"]).dt.days
    ).to_numpy()
    assert_no_leakage([c for c in X2.columns if c != "logisztikai_mutato"])
    talalatok = dict(suspicious_features(X2, y))
    assert "logisztikai_mutato" in talalatok, (
        "Az AUC-őr nem fogta meg a rejtett szivárgót.")


# ================================================================ szétvágás
def test_a_szetvagas_idoben_tortenik(data):
    _, _, meta, _ = data
    sp = temporal_split(meta["rendeles_idopont"])
    ts = pd.to_datetime(meta["rendeles_idopont"])
    assert ts.loc[sp.train].max() < ts.loc[sp.valid].min(), \
        "A tanító és a validációs halmaz időben átfed."
    assert ts.loc[sp.valid].max() < ts.loc[sp.test].min(), \
        "A validációs és a teszthalmaz időben átfed."
    assert not set(sp.train) & set(sp.test), "Átfedő indexek."
