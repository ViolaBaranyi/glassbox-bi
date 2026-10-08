"""
A betanítás döntéseinek tesztjei (okt. 8., témavezetői H1 + a 9. lelet).

  * az alapértelmezés a SÚLYOZÁS NÉLKÜLI ág;
  * utólagos kalibrátor NEM kerül a szállított artefaktumok közé;
  * a kalibrációs diagnosztika (ECE két sávolással, CORP-felbontás) helyes.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from data.build_warehouse import build
from data.make_synthetic import generate
from pipeline import train
from pipeline.train import (PARAMS, brier_skill, corp_decomposition,
                            expected_calibration_error, reliability_table)


def test_az_alapertelmezes_a_sulyozatlan_ag():
    assert inspect.signature(train.run).parameters["balance"].default == "none"
    assert PARAMS["class_weight"] is None


def test_corp_felbontas_azonossaga_es_elojelei():
    rng = np.random.default_rng(0)
    p = rng.beta(1, 12, 5000)
    y = (rng.random(5000) < np.clip(p * 1.4, 0, 1)).astype(int)    # szándékosan alulbecsül
    d = corp_decomposition(y, p)
    assert abs(d["brier"] - (d["mcb"] - d["dsc"] + d["unc"])) < 1e-5
    assert d["mcb"] >= 0 and d["dsc"] >= 0
    # tökéletesen kalibrált előrejelzésnél a kalibrációs hiba elhanyagolható
    y2 = (rng.random(200_000) < (p2 := rng.beta(1, 12, 200_000))).astype(int)
    assert corp_decomposition(y2, p2)["mcb"] < 1e-4


def test_ece_ket_savolassal():
    rng = np.random.default_rng(1)
    p = rng.beta(1, 15, 20_000)
    y = (rng.random(20_000) < p).astype(int)
    assert expected_calibration_error(y, p, strategy="uniform") < 0.01
    assert expected_calibration_error(y, p, strategy="quantile") < 0.01
    tizedek = reliability_table(y, p, strategy="quantile")
    assert len(tizedek) == 10
    assert max(r["n"] for r in tizedek) - min(r["n"] for r in tizedek) <= 1
    with pytest.raises(ValueError):
        expected_calibration_error(y, p, strategy="valami")


def test_brier_keszseg():
    y = np.array([0, 0, 0, 1])
    assert brier_skill(y, np.full(4, 0.25), 0.25) == 0.0       # a referencia maga
    assert brier_skill(y, y.astype(float), 0.25) == 1.0        # tökéletes előrejelzés


def test_nincs_mentett_kalibrator(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    generate(n_orders=3000, seed=7, out_dir=raw, verbose=False)
    db = tmp_path / "w.duckdb"
    build(raw, db, verbose=False)
    monkeypatch.setattr(train, "ARTIFACTS", tmp_path / "artifacts")

    res = train.run(db, seed=1, write_artifacts=True)
    out = Path(res["artifacts"])
    assert (out / "model.joblib").exists()
    assert not (out / "calibrator.joblib").exists(), "Kalibrátor nem lehet a szállított artefaktum."
    m = json.loads((out / "metrics.json").read_text(encoding="utf-8"))
    assert m["kiegyensulyozas"] == "none"
    assert {"teszt", "teszt_diagnosztika", "validacio"} <= set(m)
    assert {"corp", "brier_keszseg", "izotonikus_validacion_illesztve"} <= set(m["teszt_diagnosztika"])
