"""
Közös tesztkellékek: EGY szintetikus tárház és a rajta tanított négy modell a
teljes tesztfutásra (a magyarázó réteg és a felület tesztjei ezt használják).
"""

from __future__ import annotations

import pytest

from data.build_warehouse import build
from data.make_synthetic import generate


@pytest.fixture(scope="session")
def synth_db(tmp_path_factory):
    d = tmp_path_factory.mktemp("szintetikus_tarhaz")
    generate(n_orders=3000, seed=11, out_dir=d / "raw", verbose=False)
    build(d / "raw", d / "w.duckdb", verbose=False)
    return d / "w.duckdb"


@pytest.fixture(scope="session")
def synth_cache(tmp_path_factory):
    return tmp_path_factory.mktemp("modell_gyorsitotar") / "modellek.joblib"


@pytest.fixture(scope="session")
def synth_bundle(synth_db, synth_cache):
    from xai.models import load_bundle
    return load_bundle(synth_db, cache_path=synth_cache)
