"""
A döntés stabilitása (tools/dontesi_stabilitas.py) — kézzel számolt példán és szintetikus adaton.

  * a felső lista holtversenyben determinisztikus; azonos becslésnél az átfedés 1, a többértelműség 0;
  * egy ismert cserénél az átfedés, a stabil mag, a többértelműség és a legnagyobb eltérés;
  * egy kis futás: a logisztikus regresszió kontroll-magja (mag-független) pontosan 1, a jelentés
    elkészül, próbafutás nem írhat a docs/ mappába.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def ds():
    spec = importlib.util.spec_from_file_location("dontesi_stabilitas", ROOT / "tools" / "dontesi_stabilitas.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_azonos_becsles_es_holtverseny(ds):
    p = np.array([0.5, 0.5, 0.5, 0.1, 0.9, 0.2, 0.3, 0.4, 0.05, 0.6])
    assert ds.top_mask(p, 3).nonzero()[0].tolist() == [0, 4, 9]           # holtversenyben az első 0,5
    m = ds.decision_metrics(p, [p.copy(), p.copy()], share=0.3, ui_list=2)
    assert m["atfedes"] == [1.0, 1.0] and m["stabil_mag"] == 1.0
    assert m["tobbertelmuseg"] == 0.0 and m["legnagyobb_elteres"] == 0.0 and m["ui_atfedes"] == [1.0, 1.0]


def test_ismert_csere(ds):
    ref = np.arange(10, 0, -1) / 10.0                  # a felső 20%: 0 és 1
    swap = ref.copy()
    swap[[1, 2]] = swap[[2, 1]]                         # 1 kiesik, 2 bekerül
    m = ds.decision_metrics(ref, [ref.copy(), swap], share=0.2, ui_list=10)
    assert m["atfedes"] == [1.0, 0.5]
    assert m["stabil_mag"] == 0.5                       # csak a 0 van mindkettőben
    assert m["tobbertelmuseg"] == pytest.approx(0.2)    # az 1 és a 2 tagsága változott
    assert m["legnagyobb_elteres"] == pytest.approx(0.2)
    y = np.array([1, 0, 1, 0, 0, 0, 0, 0, 0, 0], dtype=float)
    assert ds.capture(y, ds.top_mask(ref, 2)) == 0.5 and ds.capture(y, ds.top_mask(swap, 2)) == 1.0


def test_kis_futas(ds, synth_bundle):
    res = ds.run(synth_bundle, kinds=("lightgbm", "logreg"), n_boot=2, control_seeds=(1,), verbose=False)
    lr = res["modellek"]["logreg"]
    assert lr["kontroll_mag"]["atfedes"]["ertek"] == 1.0 and lr["kontroll_mag"]["tobbertelmuseg"] == 0.0
    for k in ("lightgbm", "logreg"):
        bt = res["modellek"][k]["bootstrap"]
        assert 0.0 <= bt["atfedes"]["min"] <= bt["atfedes"]["ertek"] <= 1.0 and 0.0 <= bt["stabil_mag"] <= 1.0
        assert len(bt["mintankent_atfedes"]) == 2
    assert "logreg-lightgbm" in res["parok_atfedes"]
    md = ds.report(res, {"modellek": {"logreg": {"bootstrap": {"rbo": {"atlag": 0.9}}}}})
    assert "## Új tanítóadaton" in md and "K3" in md and "0,90" in md
    with pytest.raises(SystemExit):
        ds.main(["--bootstrap", "2"])
