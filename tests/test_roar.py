"""
ROAR (tools/roar.py) — szintetikus adaton.

  * a kivétel csak a megadott tényezők oszlopait írja át (a hónap a szinuszt és a koszinuszt is),
    minden sorban ugyanarra az értékre, a kategóriák listája megmarad;
  * a véletlen készletek determinisztikusak, ismétlés nélküliek;
  * egy kis futás: kivétel nélkül az újratanítás a lezárt modellt adja vissza, az összegzés és a
    jelentés elkészül; próbafutás nem írhat a docs/ mappába.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from pipeline.features import CATEGORICAL_FEATURES
from xai import narrative as nv

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def roar():
    spec = importlib.util.spec_from_file_location("roar", ROOT / "tools" / "roar.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_kivetel(roar, synth_bundle):
    b = synth_bundle
    X = b.X.loc[b.split.test].head(50)
    vals = roar.neutral_values(b)
    cat = CATEGORICAL_FEATURES[0]
    out = roar.neutralize(X, [nv.MONTH, cat, "tavolsag_km"], vals)
    for c in ("honap_sin", "honap_cos", "tavolsag_km", cat):
        assert out[c].nunique(dropna=False) == 1
    assert list(out[cat].cat.categories) == list(X[cat].cat.categories)
    assert out["tavolsag_km"].iloc[0] == pytest.approx(vals["tavolsag_km"])
    rest = [c for c in X.columns if c not in ("honap_sin", "honap_cos", "tavolsag_km", cat)]
    pd.testing.assert_frame_equal(out[rest], X[rest])
    assert roar.factor_columns(nv.MONTH) == ["honap_sin", "honap_cos"]


def test_veletlen_keszletek(roar):
    f = list(nv.DISPLAY_FEATURES)
    a, b = roar.random_sets(f, (1, 3), 4), roar.random_sets(f, (1, 3), 4)
    assert a == b and len(a[3]) == 4
    assert all(len(set(s)) == 3 and set(s) <= set(f) for s in a[3])


def test_kis_futas(roar, synth_bundle):
    res = roar.run(synth_bundle, kinds=("lightgbm", "logreg"), k_values=(1, 2), n_random=2, verbose=False)
    for k in ("lightgbm", "logreg"):
        r = res["modellek"][k]
        assert r["egyezik_a_lezarttal"]
        assert len(r["rangsor"]) == len(nv.DISPLAY_FEATURES)
        assert len(r["k"]["2"]["eses_veletlen"]) == 2 and r["k"]["2"]["legfontosabb"] == r["rangsor"][:2]
    s = res["osszegzes"]
    assert set(s["R1"]) == {"lightgbm|1", "lightgbm|2", "logreg|1", "logreg|2"}
    md = roar.report(res)
    assert "## LightGBM" in md and "Sejtések" in md
    with pytest.raises(SystemExit):
        roar.main(["--veletlen", "2"])
