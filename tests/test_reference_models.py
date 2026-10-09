"""
A referencia-modellek és a lezárt összevetés tesztjei.

  * mindhárom modell valószínűséget ad, hiányzó értékkel és új kategóriával is;
  * a rácsok az egyszerűtől a bonyolult felé haladnak, és egyezésnél az
    egyszerűbb nyer;
  * a hiperparaméter-választás CSAK a tanító ablakot látja (a validációs és a
    teszt címkék megfordítása nem változtat rajta);
  * a lezárt összevetés csak jóváhagyott, a kóddal és a lezárt v3 alapfutással
    egyező protokollal indul, és csak egyszer.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from data.build_warehouse import build
from data.db import connect
from data.make_synthetic import generate
from pipeline import reference_models as rm
from pipeline import train
from pipeline import v3_baseline as vb
from pipeline import v3_reference as vr
from pipeline.features import build_features
from pipeline.split import temporal_split

DOCS = Path(__file__).resolve().parent.parent / "docs"


@pytest.fixture(scope="module")
def synth(tmp_path_factory):
    d = tmp_path_factory.mktemp("ref")
    generate(n_orders=3000, seed=9, out_dir=d / "raw", verbose=False)
    build(d / "raw", d / "w.duckdb", verbose=False)
    con = connect(d / "w.duckdb", read_only=True)
    X, y, meta = build_features(con)
    con.close()
    return d / "w.duckdb", X, y, meta


# ------------------------------------------------------------------ modellek
def test_ismeretlen_modell_hibat_ad():
    with pytest.raises(ValueError, match="Ismeretlen"):
        rm.make_model("svm", 1)


def test_racsok_egyszerutol_a_bonyolult_fele():
    assert rm.MODELS["logreg"]["racs"] == sorted(rm.MODELS["logreg"]["racs"])          # kis C = erős regularizáció
    assert rm.MODELS["dontesi_fa"]["racs"] == sorted(rm.MODELS["dontesi_fa"]["racs"])  # sekély fa elöl
    assert rm.MODELS["random_forest"]["racs"] == sorted(rm.MODELS["random_forest"]["racs"],
                                                        reverse=True)                  # nagy levél elöl


def test_valoszinuseget_adnak_hianyzo_ertekkel_es_uj_kategoriaval(synth):
    _, X, y, meta = synth
    sp = temporal_split(meta["rendeles_idopont"])
    Xt = X.loc[sp.test].head(50).copy()
    Xt.iloc[0, Xt.columns.get_loc("tavolsag_km")] = np.nan
    Xt["kategoria"] = Xt["kategoria"].cat.add_categories(["sosem_latott"])
    Xt.iloc[1, Xt.columns.get_loc("kategoria")] = "sosem_latott"
    for kind, spec in rm.MODELS.items():
        m = rm.make_model(kind, spec["racs"][0]).fit(X.loc[sp.train], y.loc[sp.train])
        p = m.predict_proba(Xt)[:, 1]
        assert np.all((p >= 0) & (p <= 1)) and np.isfinite(p).all(), kind


def test_dontetlennel_az_egyszerubb_nyer(synth, monkeypatch):
    _, X, y, meta = synth
    sp = temporal_split(meta["rendeles_idopont"])
    monkeypatch.setattr(rm, "evaluate", lambda yy, pp: {"pr_auc": 0.1, "roc_auc": 0.6,
                                                         "brier": 0.05, "ece": 0.01,
                                                         "ece_egyenlo_elemszam": 0.01})
    r = rm.select("dontesi_fa", X, y, meta, sp.train)
    assert r["valasztott"] == rm.MODELS["dontesi_fa"]["racs"][0]


def test_a_valasztas_csak_a_tanito_ablakot_latja(synth):
    _, X, y, meta = synth
    sp = temporal_split(meta["rendeles_idopont"])
    a = rm.select("logreg", X, y, meta, sp.train)
    y2 = y.copy()
    kivul = sp.valid.append(sp.test)
    y2.loc[kivul] = 1 - y2.loc[kivul]
    b = rm.select("logreg", X, y2, meta, sp.train)
    assert a == b


# -------------------------------------------------------- lezárt összevetés
def _draft():
    return json.loads((DOCS / "v3_referencia_protokoll.json").read_text(encoding="utf-8"))


def test_a_tarolt_referencia_protokoll_tervezet_ezert_nem_fut():
    _, base_sha = vb.load_protocol(DOCS / "v3_protokoll.json")
    locked = json.loads((DOCS / "v3_lezart_eredmeny.json").read_text(encoding="utf-8"))
    with pytest.raises(vb.ProtocolError, match="jovahagyva"):
        vr.check_reference_protocol(_draft(), base_sha, locked)


def test_a_tarolt_referencia_protokoll_egyezik_a_koddal_es_a_lezart_futassal():
    """Csak a jóváhagyás hiányzik belőle; a rácsok, a mag és az alap ujjlenyomata rendben."""
    _, base_sha = vb.load_protocol(DOCS / "v3_protokoll.json")
    locked = json.loads((DOCS / "v3_lezart_eredmeny.json").read_text(encoding="utf-8"))
    p = _draft()
    p.update(allapot="jovahagyva", jovahagyas={"ki": "x", "mikor": "y"})
    vr.check_reference_protocol(p, base_sha, locked)
    p["alap_protokoll"]["sha256"] = "0" * 64
    with pytest.raises(vb.ProtocolError, match="ujjlenyomata"):
        vr.check_reference_protocol(p, base_sha, locked)
    with pytest.raises(vb.ProtocolError, match="nincs lezárt"):
        vr.check_reference_protocol(_draft() | {"allapot": "jovahagyva"}, base_sha, None)


@pytest.fixture
def kis_racs(monkeypatch):
    """Gyors teszthez kisebb rácsok és erdő — a protokollt is ehhez igazítjuk."""
    kicsi = {"logreg": {**rm.MODELS["logreg"], "racs": [0.01, 0.1]},
             "dontesi_fa": {**rm.MODELS["dontesi_fa"], "racs": [3, 5]},
             "random_forest": {**rm.MODELS["random_forest"], "racs": [30, 10]}}
    monkeypatch.setattr(rm, "MODELS", kicsi)
    monkeypatch.setattr(rm, "RF_TREES", 40)
    return kicsi


def _protokollok(tmp_path, kicsi):
    base = json.loads((DOCS / "v3_protokoll.json").read_text(encoding="utf-8"))
    base["adat"]["forras"] = "szintetikus"
    base["bizonytalansag"]["B"] = 100
    base["tanitasi_veletlen"]["magok"] = [1, 2]
    bp = tmp_path / "alap.json"
    bp.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    ref = _draft()
    ref.update(allapot="jovahagyva", jovahagyas={"ki": "teszt", "mikor": "2026-10-09"})
    ref["alap_protokoll"]["sha256"] = vb.load_protocol(bp)[1]
    for k, spec in kicsi.items():
        ref["modellek"][k]["racs"] = spec["racs"]
    ref["modellek"]["random_forest"]["n_estimators"] = 40
    ref.pop("cv_valasztas_elvart")
    ref["bizonytalansag"]["B"] = 100
    ref["tanitasi_veletlen"]["magok"] = [1, 2]
    rp = tmp_path / "ref.json"
    rp.write_text(json.dumps(ref, ensure_ascii=False), encoding="utf-8")
    return bp, rp, ref


def test_lezart_osszevetes_szintetikus_adaton(synth, tmp_path, monkeypatch, kis_racs):
    db = synth[0]
    monkeypatch.setattr(train, "ARTIFACTS", tmp_path / "artifacts")
    bp, rp, ref = _protokollok(tmp_path, kis_racs)
    locked = tmp_path / "lezart.json"
    vb.run_locked(db, bp, locked, tmp_path / "lezart.md", require_committed=False)

    out, md = tmp_path / "ref_eredmeny.json", tmp_path / "ref_eredmeny.md"
    # a tervezettől eltérő CV-választás a teszt ELŐTT megállítja
    rossz = ref | {"cv_valasztas_elvart": {"logreg": 999}}
    rp_rossz = tmp_path / "ref_rossz.json"
    rp_rossz.write_text(json.dumps(rossz, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(vb.ProtocolError, match="teszt előtt"):
        vr.run_reference(db, rp_rossz, bp, locked, out, md, require_committed=False)
    assert not out.exists()

    r = vr.run_reference(db, rp, bp, locked, out, md, require_committed=False)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert set(saved["modellek"]) == {"lightgbm", "logreg", "dontesi_fa", "random_forest"}
    for k in kis_racs:
        d = saved["modellek"][k]["paros_lightgbm_minusz_referencia"]
        assert d["pr_auc"]["ci95"][0] <= d["pr_auc"]["kulonbseg"] <= d["pr_auc"]["ci95"][1]
    lezart = json.loads(locked.read_text(encoding="utf-8"))
    assert saved["modellek"]["lightgbm"]["teszt"]["pr_auc"] == lezart["teszt"]["bootstrap"]["pr_auc"]
    assert len(saved["random_forest_magok"]["futasok"]) == 2
    assert "Páros összevetés" in md.read_text(encoding="utf-8")
    assert r["futas"]["ismetles"] is False
    with pytest.raises(vb.LockedRunExists):
        vr.run_reference(db, rp, bp, locked, out, md, require_committed=False)


def test_kodtol_eltero_racs_nem_fut(synth, tmp_path, kis_racs):
    bp, rp, ref = _protokollok(tmp_path, kis_racs)
    ref["modellek"]["dontesi_fa"]["racs"] = [3, 4, 5]
    _, base_sha = vb.load_protocol(bp)
    with pytest.raises(vb.ProtocolError, match="dontesi_fa"):
        vr.check_reference_protocol(ref, base_sha, {"protokoll_sha256": base_sha})
