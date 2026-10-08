"""
A modellválasztás (útiterv T5) tesztjei.

  * a hajtások időben egymást követik, és nem lépnek ki a tanító ablakból;
  * a fa-szám szabálya: N_fix = max(N_MIN, medián), ,5-nél felfelé kerekítve;
  * a címke-tisztítás a VÁLLALT HATÁRIDŐ szerint szűr, nem a kimenet szerint;
  * cv módban a végső modell pontosan N_fix fával tanul, és a validációs
    ablak semmit nem befolyásol — ezt a validációs címkék megfordításával
    ellenőrizzük (korai módban ugyanez a beavatkozás megváltoztatja a modellt).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data.build_warehouse import build
from data.make_synthetic import generate
from pipeline import model_selection as ms
from pipeline import train
from pipeline.split import expanding_cv_folds, settled_before, temporal_split


# ------------------------------------------------------------------ szabály
def test_fa_szam_szabaly():
    assert ms.fixed_tree_count([10, 20, 30]) == ms.N_MIN          # az alsó korlát dönt
    assert ms.fixed_tree_count([60, 70, 80, 90]) == 75
    assert ms.fixed_tree_count([60, 71]) == 66                     # 65,5 → 66
    assert ms.fixed_tree_count([3, 200, 201], n_min=10) == 200     # a medián a kiugrótól véd
    with pytest.raises(ValueError):
        ms.fixed_tree_count([])


def test_ervenytelen_fa_szam_meg_a_betoltes_elott_hibat_ad(tmp_path):
    for rossz in ("sok", 0, -5):
        with pytest.raises(ValueError):
            train.run(tmp_path / "nincs.duckdb", trees=rossz, write_artifacts=False)


# ------------------------------------------------------------------ hajtások
def test_hajtasok_idoben_es_a_tanito_ablakon_belul():
    rng = np.random.default_rng(3)
    nap = np.sort(rng.uniform(0, 420, 5000))
    ts = pd.Series(pd.Timestamp("2017-01-01") + pd.to_timedelta(nap, unit="D"))
    train_idx = ts.index[ts < pd.Timestamp("2018-01-01")]
    folds = expanding_cv_folds(ts, train_idx, 4)
    assert len(folds) == 4
    elozo_vege = None
    for f in folds:
        assert f.cut == f.cut.normalize() and f.valid_end == f.valid_end.normalize()
        assert ts.loc[f.train].max() < f.cut <= ts.loc[f.valid].min()
        assert ts.loc[f.valid].max() < f.valid_end
        assert set(f.train) | set(f.valid) <= set(train_idx), "kilépett a tanító ablakból"
        assert not set(f.train) & set(f.valid)
        if elozo_vege is not None:
            assert f.cut == elozo_vege, "a szakaszok nem követik egymást"
        elozo_vege = f.valid_end
    meretek = [len(f.train) for f in folds]
    assert meretek == sorted(meretek) and len(set(meretek)) == 4   # bővülő ablak


# ---------------------------------------------------------- címke-tisztítás
def test_cimke_tisztitas_a_hatarido_napjaval():
    cut = pd.Timestamp("2018-03-01")
    hatarido = pd.Series(pd.to_datetime(
        ["2018-02-27", "2018-02-28", "2018-03-01", "2018-03-15", None]))
    # a febr. 28-i határidő napja márc. 1. éjfélkor véget ért → eldőlt;
    # a márc. 1-jei még nem; hiányzó határidővel sem marad bent
    assert list(settled_before(hatarido.index, hatarido, cut)) == [0, 1]


def test_cimke_tisztitas_nem_a_kimenet_szerint_valogat():
    """A függvény meg sem kapja a kimenetet: csak a leadáskor ismert határidőt."""
    import inspect
    assert list(inspect.signature(settled_before).parameters) == ["index", "promised", "cut"]
    cut = pd.Timestamp("2018-03-01")
    hatarido = pd.Series(pd.to_datetime(["2018-03-05"] * 2 + ["2018-02-20"] * 2))
    assert list(settled_before(hatarido.index, hatarido, cut)) == [2, 3]


# ------------------------------------------------------- szintetikus tárház
@pytest.fixture(scope="module")
def synth_db(tmp_path_factory):
    d = tmp_path_factory.mktemp("ms")
    generate(n_orders=4000, seed=11, out_dir=d / "raw", verbose=False)
    build(d / "raw", d / "w.duckdb", verbose=False)
    return d / "w.duckdb"


def test_cv_mod_pontosan_n_fix_faval_tanul(synth_db):
    res = train.run(synth_db, seed=1, trees="cv", write_artifacts=False)
    cv = res["modellvalasztas"]
    assert res["fa_szam_mod"] == "cv"
    assert res["fak_szama"] == cv["n_fix"] == ms.fixed_tree_count(cv["legjobb_iteraciok"])
    assert cv["n_fix"] >= ms.N_MIN
    assert len(cv["legjobb_iteraciok"]) <= ms.CV_FOLDS * len(ms.CV_SEEDS)
    assert all(h["ertekeles"][1] < "2018-03-01" for h in cv["hajtasok"])


def _forditott_validacio(eredeti):
    def build_features(con):
        X, y, meta = eredeti(con)
        sp = temporal_split(meta["rendeles_idopont"])
        y = y.copy()
        y.loc[sp.valid] = 1 - y.loc[sp.valid]
        return X, y, meta
    return build_features


def test_a_validacios_ablak_nem_befolyasolja_a_cv_modellt(synth_db, monkeypatch):
    def preds(mode):
        r = train.run(synth_db, seed=2, trees=mode, write_artifacts=False,
                      return_predictions=True)
        return r["fak_szama"], r["elorejelzesek"]["teszt"]["p"]

    n_cv, p_cv = preds("cv")
    n_korai, p_korai = preds("korai")
    monkeypatch.setattr(train, "build_features", _forditott_validacio(train.build_features))
    n_cv2, p_cv2 = preds("cv")
    n_korai2, p_korai2 = preds("korai")

    assert n_cv == n_cv2
    np.testing.assert_array_equal(p_cv, p_cv2)
    # kontroll: korai módban ugyanez a beavatkozás megváltoztatja a modellt
    assert n_korai != n_korai2 or not np.array_equal(p_korai, p_korai2)


def test_cimke_tisztitas_a_vegso_tanitasban(synth_db):
    res = train.run(synth_db, seed=1, trees=60, purge=True, write_artifacts=False)
    ct = res["cimke_tisztitas"]
    assert res["fa_szam_mod"] == "rogzitett" and res["fak_szama"] == 60
    assert ct["be"] and ct["kizart_tanito_sorok"] > 0

    from data.db import connect
    from pipeline.features import build_features
    con = connect(synth_db, read_only=True)
    _, _, meta = build_features(con)
    con.close()
    sp = temporal_split(meta["rendeles_idopont"])
    hatarido = pd.to_datetime(meta.loc[sp.train, "vallalt_hatarido"])
    lezart = (hatarido + pd.Timedelta(days=1)) <= sp.train_end
    assert ct["kizart_tanito_sorok"] == int((~lezart).sum())
    assert ct["tanito_sorok"] == int(lezart.sum())
