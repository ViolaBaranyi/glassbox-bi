"""
A KernelSHAP-kontrollkar tesztjei — szintetikus tárházon, kis beállításokkal.

  * a 21 játékos tere oda-vissza bitre azonos jellemzőtáblát ad (a modell kimenete
    sem változik), a hónap egy játékos;
  * additív modellre a kar a pontos interventional Shapley-értékeket adja
    (g_j(x_j) − átlag g_j(háttér)) — a hónap és a kategória is helyesen maszkolódik;
  * mind a négy modellnél additív (alapérték + Σ = kimenet), determinisztikus a
    maggal, és nem szűkít csendben 10 tényezőre (`l1_reg=False`);
  * a teljes futás szerkezete és a jelentés.
"""

from __future__ import annotations

import numpy as np
import pytest

from xai import kernel_arm as ka
from xai import narrative as nv
from xai.models import KINDS


def test_a_ter_oda_vissza_bitre_azonos(synth_bundle):
    b = synth_bundle
    space = ka.Space.from_frame(b.X)
    X = b.X.iloc[:500]
    Z = space.encode(X)
    assert Z.shape == (500, len(ka.PLAYERS)) == (500, 21)
    back = space.decode(Z)
    back.index = X.index
    assert back.equals(X) and (back.dtypes == X.dtypes).all()
    for kind in KINDS:
        p1 = b.models[kind].predict_proba(X)[:, 1]
        p2 = b.models[kind].predict_proba(back)[:, 1]
        assert np.max(np.abs(p1 - p2)) < 1e-12, kind
    month = Z[:, ka.PLAYERS.index(nv.MONTH)]
    assert set(np.unique(month)) <= set(range(1, 13))
    with pytest.raises(ValueError, match="Hiányzó"):
        ka.Space.from_frame(X.drop(columns=["kategoria"]))


class _Additive:
    """Additív „modell" a jellemzőtáblán: a pontos Shapley-érték ismert."""
    def terms(self, X):
        return {
            "vallalt_ido_nap": 0.001 * X["vallalt_ido_nap"].to_numpy(dtype=float),
            nv.MONTH: 0.01 * X["honap_sin"].to_numpy() + 0.005 * X["honap_cos"].to_numpy(),
            "vevo_allam": 0.02 * (X["vevo_allam"].astype(str) == "SP").to_numpy(dtype=float),
            "unnep_kozeli": 0.03 * X["unnep_kozeli"].to_numpy(dtype=float),
        }

    def predict_proba(self, X):
        g = 0.05 + sum(self.terms(X).values())
        return np.column_stack([1 - g, g])


def test_additiv_modellre_pontos_shapley(synth_bundle):
    b = synth_bundle
    space = ka.Space.from_frame(b.X)
    rows = b.X.loc[b.split.test].iloc[:5]
    bg = b.background(n=40, seed=0)
    model = _Additive()
    e = ka.kernel_explain(model, rows, bg, space, nsamples=300, seed=3)
    t_x, t_bg = model.terms(rows), model.terms(bg)
    for p in ka.PLAYERS:
        expected = (t_x[p] - t_bg[p].mean()) if p in t_x else np.zeros(len(rows))
        assert np.allclose(e.phi[p].to_numpy(), expected, atol=1e-10), p
    assert e.base == pytest.approx(model.predict_proba(bg)[:, 1].mean())
    assert ka.kernel_additivity_error(e) < 1e-12


def test_negy_modell_additiv_determinisztikus_es_nem_szukit(synth_bundle):
    b = synth_bundle
    space = ka.Space.from_frame(b.X)
    rows = b.X.loc[b.split.test].iloc[:3]
    bg = b.background(n=25, seed=0)
    for kind in KINDS:
        e1 = ka.kernel_explain(b.models[kind], rows, bg, space, nsamples=400, seed=1)
        assert e1.background_rows == 25
        assert ka.kernel_additivity_error(e1) < 1e-9, kind
        assert np.allclose(e1.output, b.models[kind].predict_proba(rows)[:, 1]), kind
        e1b = ka.kernel_explain(b.models[kind], rows, bg, space, nsamples=400, seed=1)
        # a random forest több szálon az utolsó biten eltérhet (döntési napló, okt. 9.)
        assert np.allclose(e1.phi.to_numpy(), e1b.phi.to_numpy(), rtol=0, atol=1e-12), kind
        if kind == "lightgbm":
            assert (e1.phi.to_numpy() != 0).sum(axis=1).max() > 10      # nem 10 tényezős
            e2 = ka.kernel_explain(b.models[kind], rows, bg, space, nsamples=400, seed=2)
            assert not np.array_equal(e1.phi.to_numpy(), e2.phi.to_numpy())
    state = np.random.get_state()[1][:5].copy()
    ka.kernel_explain(b.models["logreg"], rows, bg, space, nsamples=100, seed=7)
    assert np.array_equal(np.random.get_state()[1][:5], state)          # a globális RNG érintetlen


def test_teljes_futas_kis_beallitassal(synth_bundle):
    res = ka.run(synth_bundle, kinds=KINDS, n_orders=6, n_noise=3, n_background=15, nsamples=150,
                 verbose=False)
    assert res["beallitas"]["rendelesek"] == 6
    assert "rendelesek" not in res                     # a rendelés-azonosítók nem kerülnek a fájlba
    assert set(res["modellparok"]) == {f"{a}|{c}" for i, a in enumerate(KINDS) for c in KINDS[i + 1:]}
    assert "kozos_hatter" in res["atvaltas"]["logreg"]
    for kind in KINDS:
        assert res["modellek"][kind]["additivitasi_hiba"] < 1e-9
        assert 0 <= res["zaj"][kind]["mintavetel"]["rbo"]["atlag"] <= 1
        assert len(res["globalis"][kind]) == 21
    text = ka.report(res)
    assert "## 1. A felület arányos átváltása" in text and "## 3. A kar saját zaja" in text
    # a felület táblái ugyanebből az eredményből
    from ui import backend as be
    pairs, checks = be.kernel_pairs_table(res), be.kernel_checks_table(res)
    assert len(pairs) == 6 and len(checks) == 4
    assert all("," in v for v in pairs["top3_kar"])              # magyar tizedesvessző
    assert all(v.endswith("%") for v in checks["felulet_elojel3"])
    # ugyanaz a részhalmaz minden futásban (az ujjlenyomat igazolja)
    again = ka.order_subset(synth_bundle, 6)
    assert ka.subset_fingerprint(synth_bundle, again.index) == res["rendeles_ujjlenyomat"]
    assert ka.subset_fingerprint(synth_bundle, ka.order_subset(synth_bundle, 5).index) != \
        res["rendeles_ujjlenyomat"]
