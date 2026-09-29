"""
Az abláció (python -m pipeline.train --drop ...) tesztjei.

Egy ablációs összehasonlítás csak akkor ér valamit, ha a „nélküle" futás
tényleg nélküle fut. Két csendes hibát zárunk ki:

  * elgépelt név  -> nem zár ki semmit, a „nélküle" futás valójában a teljes
                     modell lenne; ezért hibát kell adnia
  * a kizárás nem ér el a modellig -> a modell által ténylegesen látott
                     jellemzőneveken ellenőrizzük, nem a kérésen

A jellemzőszerződés (FEATURES) az ablációtól független marad.
"""

from __future__ import annotations

import pytest

from data.build_warehouse import build
from data.make_synthetic import generate
from pipeline.features import FEATURE_GROUPS, FEATURES, resolve_drop


def test_csoportok_kibontasa_es_ures_ablacio():
    assert resolve_drop(["honap"]) == ["honap_sin", "honap_cos"]
    assert resolve_drop(["naptar"]) == ["honap_sin", "honap_cos", "unnep_kozeli"]
    # csoport + egyedi név: nincs duplikáció, a sorrend a FEATURES szerinti
    assert resolve_drop(["het_napja", "honap"]) == ["honap_sin", "honap_cos", "het_napja"]
    # a parancssor üres --drop esetén [""]-t ad: ez a teljes modell
    assert resolve_drop([""]) == [] and resolve_drop(None) == []
    # minden csoport csak létező jellemzőre hivatkozhat
    for name, cols in FEATURE_GROUPS.items():
        assert set(cols) <= set(FEATURES), f"a(z) {name} csoport ismeretlen jellemzőt tartalmaz"


@pytest.mark.parametrize("rossz", ["honap_szin", "Honap", "naptár"])
def test_elgepelt_nev_hibat_ad(rossz):
    with pytest.raises(ValueError, match="Ismeretlen"):
        resolve_drop([rossz])


def test_mindent_kizarni_nem_lehet():
    with pytest.raises(ValueError):
        resolve_drop(list(FEATURES))


def test_a_modell_tenyleg_nem_latja_a_kizart_jellemzot(tmp_path):
    from pipeline.train import run

    raw = tmp_path / "raw"
    generate(n_orders=3000, seed=7, out_dir=raw, verbose=False)
    db = tmp_path / "w.duckdb"
    build(raw, db, verbose=False)

    n_features_before = len(FEATURES)
    res = run(db, seed=1, balance="none", drop=["naptar"], write_artifacts=False)

    kizart = set(FEATURE_GROUPS["naptar"])
    assert set(res["kizart_jellemzok"]) == kizart
    assert not kizart & set(res["jellemzo_nevek"]), "a modell látta a kizárt jellemzőt"
    assert len(res["jellemzo_nevek"]) == n_features_before - len(kizart)
    assert res["jellemzok"] == len(res["jellemzo_nevek"])
    # a szerződés érintetlen
    assert len(FEATURES) == n_features_before
