"""
A határidő-görbe (xai/deadline.py) — szintetikus adaton.

  * a rendelés saját értékénél a görbe pontosan a modell becslése, mind a négy modellnél;
  * csak a vállalt idő változik (a többi oszlop és a típusok maradnak); a logisztikus
    regresszió görbéje a logit-térben egyenes (egyetlen lineáris tag változik);
  * a tanult tartomány a tanítóadat 1–99%-a; a rácson kívüli saját érték is bekerül;
  * a felület mondatához kellő számok, az ábra és a backend.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from xai import deadline as dl
from xai.models import KINDS


def _row(b, n: int = 0) -> pd.DataFrame:
    return b.X.loc[b.split.test].iloc[[n]]


def test_a_sajat_ertek_pontosan_a_becsles(synth_bundle):
    b = synth_bundle
    for n in (0, 7):
        row = _row(b, n)
        cv = dl.curve(b, row, KINDS)
        for kind in KINDS:
            now = cv[(cv["kulcs"] == kind) & cv["jelenlegi"]]
            assert len(now) == 1 and int(now["nap"].iloc[0]) == int(row[dl.FEATURE].iloc[0])
            assert now["valoszinuseg"].iloc[0] == pytest.approx(b.models[kind].predict_proba(row)[0, 1], abs=1e-12)


def test_csak_a_vallalt_ido_valtozik(synth_bundle):
    b = synth_bundle
    row = _row(b)
    rows = dl.variants(row, [3, 10, 40])
    assert list(rows[dl.FEATURE]) == [3, 10, 40] and rows[dl.FEATURE].dtype == row[dl.FEATURE].dtype
    rest = [c for c in row.columns if c != dl.FEATURE]
    for i in range(3):
        pd.testing.assert_series_equal(rows[rest].iloc[i], row[rest].iloc[0], check_names=False)
    assert (rows.dtypes == row.dtypes).all()
    # a logisztikus regresszió logitja a napok szerint egyenes
    cv = dl.curve(b, row, ("logreg",))
    p = cv["valoszinuseg"].to_numpy()
    logit = np.log(p / (1 - p))
    assert np.allclose(np.diff(logit, 2), 0, atol=1e-9)


def test_a_tanult_tartomany_es_a_racson_kivuli_ertek(synth_bundle):
    b = synth_bundle
    rng = dl.training_range(b)
    v = b.X.loc[b.train_idx, dl.FEATURE].astype(float)
    assert rng["also"] == pytest.approx(v.quantile(0.01)) and rng["felso"] == pytest.approx(v.quantile(0.99))
    assert rng["min"] <= rng["also"] <= rng["median"] <= rng["felso"] <= rng["max"]
    row = _row(b).copy()
    row[dl.FEATURE] = 147
    cv = dl.curve(b, row)
    assert cv["nap"].max() == 147 and cv.loc[cv["jelenlegi"], "nap"].tolist() == [147]
    assert list(cv["nap"]) == sorted(cv["nap"]) and len(cv) == len(dl.DAYS) + 1
    inside = cv["nap"].between(rng["also"], rng["felso"])
    assert (cv["tartomanyban"] == inside).all()
    share = dl.outside_share(b, b.split.test)
    assert 0 <= share <= 1


def test_osszegzes_abra_es_backend(synth_bundle):
    from ui import backend as be
    from ui import charts
    b = synth_bundle
    row = _row(b).copy()
    row[dl.FEATURE] = 5
    cv = dl.curve(b, row)
    sm = dl.summary(cv, b)
    assert sm["nap"] == 5 and sm["rovidebb"] is None and sm["hosszabb"] == pytest.approx(dl.at(cv, "lightgbm", 12))
    for kinds in (("lightgbm",), KINDS):
        charts.deadline_chart(dl.curve(b, _row(b), kinds), dl.training_range(b)).to_dict()
    key = str(b.meta.loc[b.split.test[0], "order_key"])
    out = be.deadline(b, key, all_models=True)
    assert set(out["gorbe"]["kulcs"]) == set(KINDS) and out["osszegzes"]["nap"] is not None
    with pytest.raises(ValueError):
        be.deadline(b, "nincs-ilyen")
