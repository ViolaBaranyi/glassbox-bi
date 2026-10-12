"""
A magyarázó réteg (xai/) tesztjei — szintetikus adaton.

  * additivitás: alapérték + Σ hozzájárulás = a modell kimenete, mind a négy
    modellnél (1e-6 alatt), és a százalékpontos alak összege = p − p₀;
  * a LightGBM saját TreeSHAP-ja (pred_contrib) = shap.TreeExplainer;
  * a kézi lineáris SHAP = shap.LinearExplainer (ugyanazzal a háttérrel);
  * a transzformált oszlopok mind a 22 eredeti jellemző valamelyikére képződnek;
  * a modell-gyorsítótár: találat esetén nem tanít újra, rossz kulcsnál igen,
    és a kulcs a protokollfájlok tartalmától is függ.
"""

from __future__ import annotations

import json
import shutil

import joblib
import numpy as np
import pandas as pd
import pytest

from pipeline.features import FEATURES
from xai import models as xm
from xai.explain import (_grouped, additivity_error, column_groups, explain, global_importance,
                         percentage_points, top_reasons)
from xai.models import KINDS, load_bundle, locked_settings


@pytest.fixture(scope="module")
def rows(synth_bundle):
    test = synth_bundle.X.loc[synth_bundle.split.test]
    return test.sample(min(80, len(test)), random_state=1)


@pytest.fixture(scope="module")
def expl(synth_bundle, rows):
    bg = synth_bundle.background()
    return {k: explain(k, synth_bundle.models[k], rows, bg) for k in KINDS}


def test_additivitas_mind_a_negy_modellnel(expl):
    for kind, e in expl.items():
        assert additivity_error(e) < 1e-6, kind
        assert list(e.contrib.columns) == FEATURES, kind
        assert e.contrib.shape == (len(e.base), 22), kind


def test_a_valoszinuseg_a_modell_sajat_becslese(synth_bundle, rows, expl):
    for kind, e in expl.items():
        p = synth_bundle.models[kind].predict_proba(rows)[:, 1]
        assert np.allclose(e.proba, p, atol=1e-9), kind


def test_szazalekpontok_osszege_p_minusz_p0(expl):
    for kind, e in expl.items():
        pp = percentage_points(e).to_numpy().sum(axis=1)
        assert np.allclose(pp, 100 * (e.proba - e.p0), atol=1e-8), kind


@pytest.mark.filterwarnings("ignore:LightGBM binary classifier:UserWarning")
def test_lightgbm_pred_contrib_egyezik_a_shap_treeexplainerrel(synth_bundle, rows, expl):
    import shap
    model = synth_bundle.models["lightgbm"]
    te = shap.TreeExplainer(model)                      # tree_path_dependent, log-odds
    sv = te.shap_values(rows)
    sv = np.asarray(sv[1] if isinstance(sv, list) else sv)
    ours = expl["lightgbm"].contrib[list(model.booster_.feature_name())].to_numpy()
    assert np.max(np.abs(sv - ours)) < 1e-8
    ev = np.atleast_1d(te.expected_value)
    assert abs(float(ev[-1]) - float(expl["lightgbm"].base[0])) < 1e-8


def test_kezi_linearis_shap_egyezik_a_shap_linearexplainerrel(synth_bundle, rows, expl):
    import shap
    model = synth_bundle.models["logreg"]
    pre, clf = model[:-1], model.named_steps["modell"]
    bg = synth_bundle.background()
    Zb = np.asarray(pre.transform(bg), dtype=float)
    Z = np.asarray(pre.transform(rows), dtype=float)
    le = shap.LinearExplainer(clf, shap.maskers.Independent(Zb, max_samples=len(Zb)))
    sv = np.asarray(le.shap_values(Z))
    groups = column_groups(model.named_steps["elofeldolgozas"].get_feature_names_out())
    theirs = _grouped(sv, groups, rows.index).to_numpy()
    assert np.max(np.abs(theirs - expl["logreg"].contrib.to_numpy())) < 1e-10
    assert abs(float(np.atleast_1d(le.expected_value)[0]) - float(expl["logreg"].base[0])) < 1e-10


def test_oszlopcsoportok_a_22_jellemzore_kepeznek(synth_bundle):
    for kind in ("logreg", "dontesi_fa", "random_forest"):
        names = synth_bundle.models[kind].named_steps["elofeldolgozas"].get_feature_names_out()
        groups = column_groups(names)
        assert len(groups) == len(names)
        assert set(groups) == set(FEATURES), kind      # mindegyik jellemző megjelenik
    assert column_groups(["szam__missingindicator_tavolsag_km", "kat__vevo_allam_SP",
                          "kat__kategoria_infrequent_sklearn"]) == ["tavolsag_km", "vevo_allam", "kategoria"]
    with pytest.raises(ValueError):
        column_groups(["valami__x"])
    with pytest.raises(ValueError):
        column_groups(["kat__nemletezo_A"])


def test_okok_es_globalis_fontossag(expl, rows):
    e = expl["lightgbm"]
    r = top_reasons(e, rows, 0, k=5)
    assert len(r) == 5
    assert list(r.columns) == ["jellemzo", "leiras", "ertek", "hatas_szazalekpont"]
    assert r["hatas_szazalekpont"].abs().is_monotonic_decreasing
    g = global_importance(e)
    assert g.is_monotonic_decreasing and set(g.index) == set(FEATURES)


def test_linearis_magyarazathoz_hatter_kell(synth_bundle, rows):
    with pytest.raises(ValueError, match="háttér"):
        explain("logreg", synth_bundle.models["logreg"], rows, None)
    with pytest.raises(ValueError, match="Ismeretlen"):
        explain("svm", synth_bundle.models["logreg"], rows, None)


# ------------------------------------------------------------ gyorsítótár
def test_lezart_beallitasok():
    real = locked_settings("valós")
    assert real["lightgbm_fak"] == 119 and real["mag"] == 42 and real["cimke_tisztitas"] is True
    assert real["referencia"] == {"logreg": 0.1, "dontesi_fa": 10, "random_forest": 10}
    assert locked_settings("szintetikus")["lightgbm_fak"] is None


def test_gyorsitotar_talalat_es_ujratanitas(synth_db, tmp_path, monkeypatch):
    cache = tmp_path / "m.joblib"
    first = load_bundle(synth_db, cache_path=cache)
    assert cache.exists()
    key = joblib.load(cache)["kulcs"]

    # találat: semmit nem tanít újra
    import pipeline.model_selection as ms
    import pipeline.reference_models as rm

    def tilos(*a, **k):
        raise AssertionError("a gyorsítótár-találatnál nem szabad tanítani")
    with monkeypatch.context() as mp:
        mp.setattr(ms, "fit_fixed", tilos)
        mp.setattr(ms, "cross_validate", tilos)
        mp.setattr(rm, "make_model", tilos)
        again = load_bundle(synth_db, cache_path=cache)
    rows = first.X.loc[first.split.test].head(50)
    # (a random forest több szálon összegez: a valószínűség utolsó bitje futásonként eltérhet)
    for kind in KINDS:
        assert np.allclose(first.models[kind].predict_proba(rows), again.models[kind].predict_proba(rows),
                           rtol=0, atol=1e-12), kind

    # rossz kulcs: újratanít, és a helyes kulcsot írja vissza
    stored = joblib.load(cache)
    stored["kulcs"] = "elavult"
    joblib.dump(stored, cache)
    third = load_bundle(synth_db, cache_path=cache)
    assert joblib.load(cache)["kulcs"] == key
    for kind in KINDS:     # determinisztikus: ugyanazt a modellt kapjuk
        assert np.allclose(first.models[kind].predict_proba(rows), third.models[kind].predict_proba(rows),
                           rtol=0, atol=1e-12), kind


def test_a_kulcs_a_protokolltol_is_fugg(tmp_path, monkeypatch):
    for f in ("v3_protokoll.json", "v3_referencia_protokoll.json"):
        shutil.copy(xm.DOCS / f, tmp_path / f)
    monkeypatch.setattr(xm, "DOCS", tmp_path)
    settings = {"mag": 42}
    k1 = xm._key("2026-10-09 10:00:00 UTC", settings)
    assert k1 == xm._key("2026-10-09 10:00:00 UTC", settings)
    assert k1 != xm._key("2026-10-09 11:00:00 UTC", settings)          # újraépített tárház
    assert k1 != xm._key("2026-10-09 10:00:00 UTC", {"mag": 1})        # más beállítás
    p = tmp_path / "v3_protokoll.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["megjegyzes_teszt"] = "módosítva"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    assert k1 != xm._key("2026-10-09 10:00:00 UTC", settings)          # más protokoll
    # a sorvég nem számít (Windows-klón)
    raw = p.read_bytes()
    k2 = xm._key("2026-10-09 10:00:00 UTC", settings)
    p.write_bytes(raw.replace(b"\n", b"\r\n"))
    assert k2 == xm._key("2026-10-09 10:00:00 UTC", settings)


def test_hattermintak_a_tisztitott_tanito_ablakbol(synth_bundle):
    bg = synth_bundle.background(n=100, seed=3)
    assert len(bg) == min(100, len(synth_bundle.train_idx))
    assert set(bg.index) <= set(synth_bundle.train_idx)
    assert bg.index.equals(synth_bundle.background(n=100, seed=3).index)   # determinisztikus
    assert isinstance(bg, pd.DataFrame) and list(bg.columns) == FEATURES
