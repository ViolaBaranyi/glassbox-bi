"""
Gazdasági forgatókönyvek (tools/gazdasagi_forgatokonyv.py) — kézzel számolt példán és szintetikus adaton.

  * a nettó érték e · L − c · N; a kapacitás-szabály a legnagyobb becsléseket jelöli meg;
  * a küszöbszabály: a várt nettó érték a becslésből, az elért a valódi kimenetből;
  * a heti blokk-bootstrap kulcsai és intervallumai; egy kis futás jelentéssel; próbafutás nem ír a docs/-ba.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def gf():
    spec = importlib.util.spec_from_file_location("gazdasagi_forgatokonyv", ROOT / "tools" / "gazdasagi_forgatokonyv.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_netto_es_kapacitas(gf):
    assert gf.net(3, 10, 0.05, 0.6) == pytest.approx(0.6 * 3 - 0.05 * 10)
    y = np.array([1, 0, 1, 0, 0, 0, 0, 0, 0, 0])
    p = np.array([0.9, 0.8, 0.1, 0.7, 0.2, 0.3, 0.05, 0.01, 0.02, 0.03])
    rows = gf.capacity_rows(y, p, shares=(0.2, 0.5))
    assert rows[0] == {"q": 0.2, "N": 2, "L": 1, "pontossag": 0.5, "fogas": 0.5}
    assert rows[1]["N"] == 5 and rows[1]["L"] == 1
    r = gf.random_rows(y, shares=(0.2,))[0]
    assert r["N"] == 2 and r["L"] == pytest.approx(0.4) and r["pontossag"] == pytest.approx(0.2)


def test_kuszob_szabaly(gf):
    y = np.array([1, 0, 0, 0])
    p = np.array([0.5, 0.4, 0.05, 0.01])
    t = gf.threshold_rows(y, p, costs=(0.06,), effects=(0.6,))[0]       # küszöb 0,1
    assert t["kuszob"] == pytest.approx(0.1) and t["N"] == 2 and t["L"] == 1
    assert t["vart_netto"] == pytest.approx(0.6 * 0.9 - 2 * 0.06)
    assert t["elert_netto"] == pytest.approx(0.6 * 1 - 2 * 0.06)


def test_blokk_bootstrap(gf):
    rng = np.random.default_rng(1)
    y = (rng.random(400) < 0.1).astype(int)
    p = {"lightgbm": y * 0.5 + rng.random(400) * 0.5, "logreg": rng.random(400)}
    blocks = np.repeat(np.arange(8), 50)
    out = gf.bootstrap_net(y, p, blocks, shares=(0.1,), costs=(0.05,), effects=(0.6,), B=50, seed=3)
    lo, hi = out["netto"]["lightgbm|0.1|0.05|0.6"]["ci95"]
    assert lo <= hi
    assert out["netto_minusz_veletlen"]["lightgbm|0.1|0.05|0.6"]["ci95"][0] > 0     # informatív becslés
    assert "0.1|0.05|0.6" in out["lightgbm_minusz_logreg"]


def test_kis_futas(gf, synth_bundle):
    res = gf.run(synth_bundle, n_boot=1, B=20, verbose=False)
    assert set(res["kapacitas"]) == {"lightgbm", "logreg", "veletlen"}
    assert len(res["forgatokonyvek"]) == len(gf.COSTS) * len(gf.EFFECTS)
    assert len(res["kuszob_szabaly"]) == len(gf.COSTS) * len(gf.EFFECTS)
    md = gf.report(res)
    assert "## 2. Nettó érték" in md and "## 4. Küszöb" in md
    with pytest.raises(SystemExit):
        gf.main(["--bootstrap", "1"])
