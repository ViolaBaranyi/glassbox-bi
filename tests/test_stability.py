"""
A magyarázatok stabilitásának mérése (xai/stability.py, K3) — szintetikus adaton.

  * a CIES súlyozott távolsága kézzel számolt példán, azonos magyarázatra pontosan 1, nagy
    eltérésre 0 (alulról vágva);
  * a CIES zaja csak a számszerű jellemzőket érinti, nullánál σ = α, a hiányzó érték hiányzó marad;
  * a bootstrap-minta a tisztított tanító sorokból jön, determinisztikus;
  * egy kis teljes futás: a mag-független logisztikus regresszió kontrollja pontosan 1, a jelentés
    elkészül, a kimenetben nincs rendelés-azonosító; próbafutás nem írhat a docs/-ba.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from pipeline.features import BOOLEAN_FEATURES, CATEGORICAL_FEATURES, NUMERIC_FEATURES
from xai import stability as st


def test_cies_kezzel_szamolt_peldan():
    ref = pd.DataFrame([[3.0, -1.0, 0.5]], columns=list("abc"))
    other = pd.DataFrame([[2.0, -1.0, 0.5]], columns=list("abc"))
    # helyezések 1, 2, 3 → w = (6, 3, 2)/11; d = 6/11; ‖φ‖_w = (18 + 3 + 1)/11 = 2 → 1 − 3/11
    assert st.cies(ref, [other]).iloc[0] == pytest.approx(8 / 11)
    assert st.cies(ref, [ref]).iloc[0] == pytest.approx(1.0)
    assert st.cies(ref, [ref * -5]).iloc[0] == 0.0                         # alulról 0-ra vágva
    # több szomszéd: a távolságok átlaga
    assert st.cies(ref, [other, ref]).iloc[0] == pytest.approx(1 - (6 / 11 / 2) / 2)


def test_a_zaj_csak_a_szamszeru_jellemzoket_erinti(synth_bundle):
    rows = synth_bundle.X.loc[synth_bundle.split.test].head(30).copy()
    rows.iloc[0, rows.columns.get_loc(NUMERIC_FEATURES[0])] = 0
    rows.iloc[1, rows.columns.get_loc(NUMERIC_FEATURES[1])] = np.nan
    p1 = st.perturb(rows, 0.03, np.random.default_rng(1))
    p2 = st.perturb(rows, 0.03, np.random.default_rng(1))
    pd.testing.assert_frame_equal(p1, p2)
    pd.testing.assert_frame_equal(p1[CATEGORICAL_FEATURES + BOOLEAN_FEATURES], rows[CATEGORICAL_FEATURES + BOOLEAN_FEATURES])
    assert p1.iloc[0][NUMERIC_FEATURES[0]] != 0                            # nullánál σ = α
    assert np.isnan(p1.iloc[1][NUMERIC_FEATURES[1]])
    rel = (p1[NUMERIC_FEATURES] - rows[NUMERIC_FEATURES].astype(float)).abs() / rows[NUMERIC_FEATURES].astype(float).abs()
    assert np.nanmedian(rel.to_numpy()) < 0.1                              # kb. α nagyságrend


def test_a_bootstrap_minta(synth_bundle):
    b = synth_bundle
    i0, i0b, i1 = st.bootstrap_index(b, 0), st.bootstrap_index(b, 0), st.bootstrap_index(b, 1)
    assert len(i0) == len(b.train_idx) and set(i0) <= set(b.train_idx)
    assert (i0 == i0b).all() and not (i0 == i1).all()
    assert i0.has_duplicates                                                 # visszatevéses


def test_kis_teljes_futas(synth_bundle, tmp_path):
    b = synth_bundle
    kinds = ("lightgbm", "logreg", "dontesi_fa")
    res = st.run(b, kinds, n_boot=2, control_seeds=(1,), n_orders=15, cies_m=2, cies_sens={}, verbose=False)
    lr = res["modellek"]["logreg"]
    assert lr["kontroll_mag"]["rbo"]["atlag"] == pytest.approx(1.0)        # a mag nem számít
    assert lr["kontroll_mag"]["cies"]["atlag"] == pytest.approx(1.0)
    assert lr["becsles_valtozas_pp"]["kontroll_mag"] == pytest.approx(0.0, abs=1e-9)
    for k in kinds:
        bt = res["modellek"][k]["bootstrap"]
        assert 0 <= bt["rbo"]["atlag"] <= 1 and len(bt["mintankent"]["rbo"]) == 2
        assert 0 <= res["cies_bemeneti_zaj"]["0.03"]["modellek"][k]["atlag"] <= 1
    assert "logreg-dontesi_fa" in res["parok_rbo"] and "lightgbm-random_forest" not in res["parok_rbo"]
    md = st.report(res)
    assert "## 1. A tanítóadat újramintázása" in md and "## 2. A CIES" in md
    text = json.dumps(res, ensure_ascii=False)
    keys = b.meta.loc[b.split.test, "order_key"].astype(str).head(200)
    assert not any(k in text for k in keys)                                 # rendelés-azonosító nincs benne

    # a felület táblái és ábrája ugyanebből az eredményből
    from ui import backend as be
    from ui import charts
    res = json.loads(text)                                                  # ahogy a felület olvassa
    assert len(be.stability_table(res)) == 3 and len(be.stability_pairs_table(res)) == 3
    assert set(be.stability_chart_table(res)["kulcs"]) == {"bootstrap", "kontroll"}
    assert list(be.stability_cies_table(res).columns) == ["modell", "alfa_0.03"]
    assert len(be.stability_global_table(res)) == 3
    charts.stability_chart(be.stability_chart_table(res), ["LightGBM"]).to_dict()
    out = tmp_path / "e.json"
    out.write_text(text, encoding="utf-8")
    st.main(["--jelentes", str(out)])                                       # csak a jelentés újraírása
    assert out.with_suffix(".md").read_text(encoding="utf-8") == md

    # utólagos, feltáró változatok: ugyanazok a húzások (a kerekítetlen LightGBM pontosan visszajön)
    fx = st.exploratory_rounded_cies(b, kinds, n_orders=15, m=2, verbose=False)
    fh = st.exploratory_rounded_cies(b, kinds, n_orders=15, m=2, keep_cols=st.MONTH_FEATURES, verbose=False)
    main_lgbm = res["cies_bemeneti_zaj"]["0.03"]["modellek"]["lightgbm"]["atlag"]
    assert fx["ellenorzes_lightgbm_kerekitetlen"] == pytest.approx(main_lgbm)
    assert fh["zaj_nelkuli_jellemzok"] == list(st.MONTH_FEATURES) and set(fx["modellek"]) == set(kinds)
    rows = b.X.loc[b.split.test].head(20)
    nb = st.perturb(rows, 0.03, np.random.default_rng(3), round_cols=st.integer_features(b))
    for c in st.integer_features(b):
        assert np.allclose(nb[c].dropna() % 1, 0)                           # egész maradt
    res.update(feltaro_kerekitett_cies=fx, feltaro_kerekitett_honap_nelkul=fh)
    md2 = st.report(res)
    assert "## 3. Utólagos, feltáró" in md2 and "(b) kerekítve, hónap zaja nélkül" in md2
    assert list(be.stability_cies_table(res).columns)[-2:] == list(be.STABILITY_EXPLORATORY)


def test_a_paros_kulonbseg_olvasata():
    s = {"elozetes_sejtes": "nagyobb"}
    assert st.verdict({**s, "ci95": [0.01, 0.05]}) == "teljesült"
    assert st.verdict({**s, "ci95": [-0.05, -0.01]}) == "fordított"
    assert st.verdict({**s, "ci95": [-0.01, 0.05]}) == "nem dönthető el"
    n = {"elozetes_sejtes": "nincs"}
    assert st.verdict({**n, "ci95": [0.01, 0.05]}) == "A stabilabb"
    assert st.verdict({**n, "ci95": [-0.05, -0.01]}) == "B stabilabb"
    assert st.verdict({**n, "ci95": [-0.01, 0.01]}) == "nincs kimutatható különbség"


def test_proba_nem_ir_a_docsba():
    full = st.parser().parse_args([])
    assert st.output_path(full).parent.name == "docs"
    for argv in (["--bootstrap", "2"], ["--rendelesek", "20"], ["--cies-m", "2"], ["--magok", "1"],
                 ["--cies-erzekenyseg-nelkul"], ["--modellek", "logreg"]):
        assert st.output_path(st.parser().parse_args(argv)).parent.name == "artifacts"
