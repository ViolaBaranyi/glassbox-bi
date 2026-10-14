"""
A magyarázatok hűségének mérése (xai/faithfulness.py) — szintetikus adaton.

  * a maszkok és a sorrend: törlésnél az első k tényező a háttérből, beszúrásnál csak az
    első k a rendelésé; előjeles sorrend (a legjobban növelő előre);
  * additív modellen a törlési görbe pontosan a Shapley-értékek halmozott összege, és
    a Shapley-sorrend AOPC-je minden más sorrendénél nagyobb vagy egyenlő;
  * a beültetett jellemző: csak a két kijelölt oszlop és a jel = 1 sorok címkéje változik,
    erős jelnél a magyarázat megtalálja a jelet;
  * a teljes futás (kicsiben) jelentést ad, és nem ment rendelés-azonosítót;
  * egy próbafutás nem írhatja felül a docs/-beli lezárt eredményt (a felületét).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from xai import faithfulness as fa
from xai import kernel_arm as ka
from xai.models import KINDS


def test_maszkok_es_sorrend():
    d = fa.deletion_masks([2, 0, 1])
    assert d.tolist() == [[True, True, True], [True, True, False], [False, True, False],
                          [False, False, False]]
    assert (fa.insertion_masks([2, 0, 1]) == ~d).all()
    assert fa.signed_order([0.5, -1.0, 2.0, 0.0]).tolist() == [2, 0, 3, 1]
    assert fa.signed_order([1.0, 1.0, 1.0]).tolist() == [0, 1, 2]          # egyezésnél stabil


class _Additive:
    """f(z) = c + z·w a 21 játékos terében — interventional Shapley-értéke pontosan w·(x − E[háttér])."""
    def __init__(self, space, w, c=0.1):
        self.space, self.w, self.c = space, np.asarray(w), c

    def predict_proba(self, X):
        p = self.c + self.space.encode(X) @ self.w
        return np.column_stack([1 - p, p])


def test_additiv_modellen_a_gorbe_pontos_es_a_shapley_sorrend_a_legjobb(synth_bundle):
    b = synth_bundle
    space = ka.Space.from_frame(b.X)
    rows = b.X.loc[b.split.test].head(4)
    bg = b.background(n=40, seed=3)
    X_z, bg_z = space.encode(rows), space.encode(bg)
    rng = np.random.default_rng(0)
    model = _Additive(space, rng.normal(0, 1e-3, len(fa.PLAYERS)))
    for i in range(len(rows)):
        phi = model.w * (X_z[i] - bg_z.mean(axis=0))
        full, empty = fa.value_function(model, space, X_z[i], bg_z,
                                        np.array([[True] * 21, [False] * 21]))
        assert full == pytest.approx(model.predict_proba(rows.iloc[[i]])[0, 1], abs=1e-12)
        assert empty == pytest.approx(model.predict_proba(bg)[:, 1].mean(), abs=1e-12)
        order = fa.signed_order(phi)
        d, s = fa.order_curves(model, space, X_z[i], bg_z, {"shap": order})["shap"]
        assert np.allclose(d, full - np.concatenate([[0.0], np.cumsum(phi[order])]), atol=1e-12)
        assert np.allclose(s, empty + np.concatenate([[0.0], np.cumsum(phi[order])]), atol=1e-12)
        best = fa.curve_metrics(d, s)
        for _ in range(20):                       # a Shapley-sorrendnél jobb sorrend nincs
            perm = rng.permutation(len(fa.PLAYERS))
            d2, s2 = fa.order_curves(model, space, X_z[i], bg_z, {"p": perm})["p"]
            other = fa.curve_metrics(d2, s2)
            assert best["torles_aopc"] >= other["torles_aopc"] - 1e-9
            assert best["beszuras_aopc"] >= other["beszuras_aopc"] - 1e-9
            assert best["top3_eses"] >= other["top3_eses"] - 1e-9


def test_beultetes_csak_a_ket_oszlopot_es_a_jel_cimket_valtoztatja(synth_bundle):
    b = synth_bundle
    X2, y2, jel = fa.plant(b)
    other = [c for c in b.X.columns if c not in (fa.SIGNAL_SLOT, fa.NOISE_SLOT)]
    pd.testing.assert_frame_equal(X2[other], b.X[other])
    assert set(X2[fa.SIGNAL_SLOT].unique()) <= {0, 1}
    assert (X2[fa.SIGNAL_SLOT].astype(bool) == jel).all()
    assert X2[fa.NOISE_SLOT].between(0, fa.NOISE_LEVELS - 1).all()
    assert X2[fa.SIGNAL_SLOT].dtype == b.X[fa.SIGNAL_SLOT].dtype
    assert X2[fa.NOISE_SLOT].dtype == b.X[fa.NOISE_SLOT].dtype
    assert abs(jel.mean() - fa.P_SIGNAL) < 0.03
    assert (y2 >= b.y).all() and (y2[~jel] == b.y[~jel]).all()      # csak jel = 1 sor válthat
    switched = ((y2 == 1) & (b.y == 0) & jel).sum() / ((b.y == 0) & jel).sum()
    assert abs(switched - fa.FLIP) < 0.05
    X3, y3, jel3 = fa.plant(b)                                        # determinisztikus
    pd.testing.assert_frame_equal(X2, X3)
    assert (y2 == y3).all() and (jel == jel3).all()


def test_beultetett_ellenorzes_szamai():
    pp = pd.DataFrame(0.05, index=range(4), columns=fa.PLAYERS)       # a többi tényező kicsi, de nem 0
    pp.loc[:, "vallalt_ido_nap"] = [5.0, 4.0, 3.0, 2.0]                # egy erős valódi tényező
    pp.loc[[0, 1], fa.SIGNAL_SLOT] = [9.0, 0.5]                        # jel = 1: az egyiknél gyenge
    pp.loc[[2, 3], fa.SIGNAL_SLOT] = [-1.0, -2.0]
    pp.loc[:, fa.NOISE_SLOT] = [0.01, -0.02, 0.0, 0.03]
    pp.loc[1, "tavolsag_km"], pp.loc[1, "kosar_ertek"] = 1.0, 0.8      # a 2. rendelésnél kiszorul
    jel = pd.Series([True, True, False, False], index=pp.index)
    r = fa.planted_check(pp, jel)
    assert r["jel_top3"] == 0.5 and r["jel_irany"] == 1.0 and r["jel0_irany"] == 1.0
    assert r["zaj_top3"] == 0.0 and r["jel_helyezes"] == 2
    assert r["zaj_arany"] == pytest.approx(0.015 / 3.125)
    assert r["itelet"] == {"jel_top3": False, "jel_irany": True, "zaj_top3": True, "zaj_arany": True}
    assert not r["megfelelt"]


@pytest.mark.filterwarnings("ignore:X does not have valid feature names")
def test_eros_jelet_a_magyarazat_megtalalja(synth_bundle):
    res = fa.planted_feature(synth_bundle, kinds=("lightgbm", "logreg"), n_rows=150, flip=0.6,
                             log=lambda *a: None)
    assert res["tanito_keses_jel1"] > res["tanito_keses_jel0"] + 0.4
    for kind, r in res["modellek"].items():
        assert r["jel_helyezes"] == 1, kind
        assert r["jel_irany"] >= 0.95, kind
        assert r["zaj_helyezes"] > 3, kind
        assert r["modell_tanulta"]["atlag_becsles_jel1"] > r["modell_tanulta"]["atlag_becsles_jel0"]
        assert r["zaj_valodi_hatas_pp"] >= 0.0


@pytest.fixture(scope="module")
def kis_eredmeny(synth_bundle):
    return fa.run(synth_bundle, kinds=("lightgbm", "logreg"), n_orders=6, n_random=2, n_plant=60,
                  nsamples=256, verbose=False)


def test_kis_futas_es_jelentes(synth_bundle, kis_eredmeny):
    b, res = synth_bundle, kis_eredmeny
    tb = res["torles_beszuras"]["modellek"]
    for kind in ("lightgbm", "logreg"):
        m = tb[kind]["mertekek"]
        assert set(m) == {"felulet", "kernel", "veletlen"}
        assert set(m["felulet"]) == {"torles_aopc", "beszuras_aopc", "top3_eses"}
        assert len(tb[kind]["gorbek"]["felulet"]["torles"]) == len(fa.PLAYERS) + 1
        assert tb[kind]["gorbek"]["felulet"]["torles"][0] == 0.0           # a görbe 0-ból indul
        assert 0.0 <= tb[kind]["jobb_mint_veletlen"] <= 1.0
    text = fa.report(res)
    assert "## 1. Törlési és beszúrási görbe" in text and "## 2. Beültetett jellemző" in text
    dumped = json.dumps(res, ensure_ascii=False)
    keys = b.meta["order_key"].astype(str)
    assert not any(k in dumped for k in keys.head(200))                     # nincs rendelés-azonosító


def test_feluleti_tablak_es_abrak(kis_eredmeny):
    from ui import backend as be
    from ui import charts
    from xai.models import NAMES
    res = json.loads(json.dumps(kis_eredmeny))                        # ahogy a fájlból jön vissza
    drop = be.faith_drop_table(res)
    assert set(drop["kulcs"]) == {"veletlen", "felulet", "kernel"} and len(drop) == 6
    assert ((drop["also"] <= drop["eses_pp"]) & (drop["eses_pp"] <= drop["felso"])).all()
    curve = be.faith_curve_table(res, "lightgbm")
    assert len(curve) == 3 * (len(fa.PLAYERS) + 1) and (curve.loc[curve["k"] == 0, "eses_pp"] == 0).all()
    planted = be.faith_planted_table(res)
    assert list(planted["modell"]) == [NAMES["lightgbm"], NAMES["logreg"]]
    assert planted["jel_top3"].str.endswith("%").all() and set(planted["megfelelt"]) <= {"igen", "nem"}
    details = be.faith_details_table(res)
    assert (details["sorrend"] == "különbség: felület − véletlen").sum() == 2
    for ch in (charts.faith_drop_chart(drop, [NAMES["lightgbm"], NAMES["logreg"]]),
               charts.faith_curve_chart(curve, ink=charts.DARK)):
        spec = ch.to_dict()
        assert "$schema" in spec
        layers = spec.get("layer", [spec])
        for layer in layers:                                          # magyar súgó minden rétegen
            mark = layer["mark"] if isinstance(layer["mark"], dict) else {"type": layer["mark"]}
            assert "tooltip" in layer.get("encoding", {}) or mark.get("tooltip") is False


def test_a_probafutas_nem_irja_felul_a_lezart_eredmenyt():
    """A felület a docs/-beli eredményt mutatja: oda csak a teljes, rögzített futás írhat."""
    p = fa.parser()
    assert fa.output_path(p.parse_args([])) == fa.DOCS / "huseg_eredmeny"
    assert fa.output_path(p.parse_args(["--modellek", ",".join(KINDS)])) == fa.DOCS / "huseg_eredmeny"
    for args in (["--rendelesek", "20", "--veletlen", "2", "--beultetett", "100", "--nsamples", "512"],
                 ["--kernel-nelkul"], ["--modellek", "lightgbm,logreg"]):
        assert fa.output_path(p.parse_args(args)) == fa.ARTIFACTS / "huseg_proba", args
    assert fa.output_path(p.parse_args(["--kimenet", "valahol/mas"])) == Path("valahol/mas")
