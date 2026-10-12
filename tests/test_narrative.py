"""
A megjelenítés és a sablonos szöveg tesztjei (xai.narrative) — adat nélkül.

  * minden jellemzőnek van rövid neve; a megjelenítési tényezők listája 21 elemű
    (a hónap két kódoló oszlopa egy tényező);
  * az értékek magyar alakja (tizedesvessző, mértékegység, hónap, nap, hiány);
  * a hónap visszafejtése a körkódolásból mind a 12 hónapra;
  * az összevonás után is additív: a tényezők összege = a 22 hozzájárulás összege;
  * a szöveg a megadott számokat írja ki, és csak a küszöb feletti tényezőket.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from pipeline.features import FEATURES
from xai import narrative as nv

NBSP = " "


def test_minden_jellemzonek_van_rovid_neve():
    assert set(nv.SHORT) == set(FEATURES)
    assert len(nv.DISPLAY_FEATURES) == 21
    assert nv.MONTH in nv.DISPLAY_FEATURES
    assert "honap_sin" not in nv.DISPLAY_FEATURES and "honap_cos" not in nv.DISPLAY_FEATURES
    for key in nv.DISPLAY_FEATURES:
        assert nv.display_name(key) and nv.display_info(key)
        assert not nv.display_name(key).startswith(("a ", "az "))   # a névelőt a szöveg teszi elé


def test_szamformatum():
    assert nv.fmt_num(1234567.891, 2) == f"1{NBSP}234{NBSP}567,89"
    assert nv.fmt_pct(0.0677) == "6,8%"
    assert nv.fmt_pct(0.5765, 2) == "57,65%"
    assert nv.fmt_pp(3.14159, 2) == "+3,14"
    assert nv.fmt_pp(-1.75, 1) == "−1,8"          # valódi mínuszjel (U+2212)
    assert nv.fmt_pp(0.0) == "+0,0"


@pytest.mark.parametrize("month", range(1, 13))
def test_honap_visszafejtese(month):
    s, c = math.sin(2 * math.pi * month / 12), math.cos(2 * math.pi * month / 12)
    assert nv.month_number(s, c) == month


def _row(**over) -> pd.Series:
    base = {f: 0 for f in FEATURES}
    base.update({"honap_sin": math.sin(2 * math.pi * 7 / 12), "honap_cos": math.cos(2 * math.pi * 7 / 12),
                 "kategoria": "bed_bath_table", "elado_allam": "SP", "vevo_allam": "RJ",
                 "azonos_allam": False, "unnep_kozeli": False})
    base.update(over)
    return pd.Series(base)


def test_ertekek_emberi_alakban():
    r = _row()
    assert nv.format_value("vallalt_ido_nap", 8) == "8 nap"
    assert nv.format_value("tavolsag_km", 1234.4) == f"1{NBSP}234 km"
    assert nv.format_value("kosar_ertek", 129.9) == "129,90 BRL"
    assert nv.format_value("dij_arany", 0.1234) == "12,3%"
    assert nv.format_value("elado_korabbi_keses_arany", 0.25) == "25,0%"
    assert nv.format_value("elado_korabbi_keses_arany", np.nan) == "nincs előzmény"
    assert nv.format_value("elado_atlagos_feladas_nap", None) == "nincs előzmény"
    assert nv.format_value("tavolsag_km", np.nan) == "nincs koordináta"
    assert nv.format_value("kategoria", np.nan) == "ismeretlen"
    assert nv.format_value("kategoria", "toys") == "toys"
    assert nv.format_value("het_napja", 5) == "szombat"
    assert nv.format_value("azonos_allam", True) == "igen"
    assert nv.format_value("unnep_kozeli", False) == "nem"
    assert nv.format_value(nv.MONTH, None, r) == "július"
    assert nv.format_value("honap_sin", r["honap_sin"], r) == "július"
    with pytest.raises(ValueError):
        nv.format_value(nv.MONTH, None)


def _pp(**over) -> pd.Series:
    v = {f: 0.0 for f in FEATURES}
    v.update(over)
    return pd.Series(v)


def test_megjelenitesi_tenyezok_additivak_es_rendezettek():
    pp = _pp(vallalt_ido_nap=-2.5, vevo_allam=4.0, honap_sin=0.75, honap_cos=0.5, tavolsag_km=-0.25)
    fr = nv.display_frame(pp, _row(vallalt_ido_nap=30, tavolsag_km=812.0))
    assert len(fr) == 21 and set(fr["tenyezo"]) == set(nv.DISPLAY_FEATURES)
    assert fr["hatas_pp"].sum() == pytest.approx(pp.sum(), abs=1e-12)
    assert list(fr["tenyezo"][:4]) == ["vevo_allam", "vallalt_ido_nap", nv.MONTH, "tavolsag_km"]
    month = fr.set_index("tenyezo").loc[nv.MONTH]
    assert month["hatas_pp"] == pytest.approx(1.25) and month["ertek"] == "július"
    assert fr.set_index("tenyezo").loc["vallalt_ido_nap", "ertek"] == "30 nap"
    many = nv.merge_display(pd.DataFrame([pp, pp * 2]))
    assert list(many.columns) == nv.DISPLAY_FEATURES
    assert np.allclose(many.sum(axis=1), [pp.sum(), 2 * pp.sum()])


def test_szoveg_a_magyarazat_szamait_irja():
    pp = _pp(vevo_allam=12.0, vallalt_ido_nap=5.0, tavolsag_km=2.0, elado_szam=1.0,
             het_napja=-1.5, kategoria=0.01)
    fr = nv.display_frame(pp, _row(vallalt_ido_nap=8, tavolsag_km=1969.0, het_napja=5))
    text = nv.narrative(0.225, 0.04, 0.044, fr, k=3)
    assert "22,5% eséllyel késik" in text
    assert "időszak átlagos becslésének (4,4%) 5,1-szerese" in text
    # múltbeli adat nélkül a gyakoriság csak feltételesen igaz
    assert text.endswith("Ha a modell ebben a tartományban jól kalibrált, 100 ilyen becsült "
                         "kockázatú rendelésből kb. 22 késik.")
    assert "kiindulópontja 4,0%" in text
    assert ("a vevő állama (RJ; +12,0 százalékpont), a vállalt szállítási idő (8 nap; +5,0 százalékpont) "
            "és a távolság (1 969 km; +2,0 százalékpont) növeli") in text
    assert "a hét napja (szombat; −1,5 százalékpont) csökkenti" in text
    assert "eladók száma" not in text           # csak a legerősebb k
    assert "termékkategória" not in text        # a küszöb alatti tényező nem kerül a szövegbe


def test_szoveg_kis_kockazatnal_es_iranyok_hianyaban():
    fr = nv.display_frame(_pp(vallalt_ido_nap=-1.0), _row(vallalt_ido_nap=50))
    text = nv.narrative(0.004, 0.038, 0.044, fr)
    assert "csak 9%-a" in text
    assert "1000 ilyen becsült kockázatú rendelésből kb. 4 késik" in text
    assert "növeli" not in text and "csökkenti" in text
    flat = nv.display_frame(_pp(), _row())
    t2 = nv.narrative(0.044, 0.044, 0.044, flat)
    assert "nagyjából az időszak átlagos becslése" in t2
    assert "egyik tényező sem mozdítja el számottevően" in t2


# ------------------------------------------------- a becslés hitelessége
def _rec(**over) -> dict:
    """A ui.backend.similar_orders kimenetének alakja (kézzel, adat nélkül)."""
    r = {"ablak": "test", "sav": 6, "sav_nev": "30% fölött", "sav_szoveg": "30% feletti",
         "rendelesek": 39, "kesett": 4, "tenyleges_arany": 4 / 39, "ci_also": 0.0406,
         "ci_felso": 0.2357, "atlag_becsles": 0.368, "idoszak_arany": 0.0361,
         "relativ_tenyleges": (4 / 39) / 0.0361, "itelet": "túlbecsült", "onmaga_kihagyva": True}
    r.update(over)
    return r


def test_termeszetes_gyakorisag():
    assert nv.natural_frequency(0.103) == (10, 100)
    assert nv.natural_frequency(0.004) == (4, 1000)
    assert nv.natural_frequency(0.0049) == (5, 1000)      # 100-ból 0 helyett 1000-ből 5
    assert nv.per_base(100) == "100-ból" and nv.per_base(1000) == "1000-ből"


def test_multbeli_pontossag_mondata():
    s = nv.record_phrase(_rec())
    assert s.startswith("A teszt-időszakban a hasonló, 30% feletti becslésű rendelések közül "
                        "100-ból kb. 10 késett ténylegesen (39 másik rendelésből 4)")
    assert s.endswith("— ebben a sávban a modell túlbecsült (átlagosan 36,8%-ot mondott).")

    ok = nv.record_phrase(_rec(sav_szoveg="5–10%-os", rendelesek=3453, kesett=256,
                               tenyleges_arany=256 / 3453, atlag_becsles=0.071,
                               itelet="összhangban", onmaga_kihagyva=False))
    assert f"(3{NBSP}453 rendelésből 256)" in ok and "másik" not in ok
    assert ok.endswith("— ez összhangban van a modell becslésével.")

    low = nv.record_phrase(_rec(ablak="valid", itelet="alábecsült", atlag_becsles=0.029))
    assert low.startswith("A validációs időszakban (a teszt előtti három hónapban)")
    assert "a modell alábecsült (átlagosan 2,9%-ot mondott)" in low
    assert "nem lehet ítélni" in nv.record_phrase(_rec(rendelesek=12, kesett=1, itelet="kevés adat"))
    assert "nem volt más" in nv.record_phrase(_rec(rendelesek=0, kesett=0))


def test_szoveg_a_multbeli_pontossaggal_zarul():
    fr = nv.display_frame(_pp(vevo_allam=30.0), _row())
    text = nv.narrative(0.577, 0.038, 0.044, fr, record=_rec())
    assert "Ha a modell" not in text                      # nem a feltételes gyakoriság
    assert text.endswith(nv.record_phrase(_rec()))
    assert text.index("növeli") < text.index("A teszt-időszakban")   # előbb a miért, aztán a hitelesség


def test_hitelessegi_megjegyzes():
    kind, text = nv.credibility_note(_rec())
    assert kind == "figyelmeztetes"
    assert text.startswith("**A teszt-időszakban ebben a sávban a modell túlbecsült.**")
    assert "39 másik rendelésből 4 késett (10,3%; 95%-os intervallum: 4,1% – 23,6%)" in text
    assert "átlagosan 36,8%-ot mondott" in text
    assert "kb. 2,8-szer olyan gyakran késtek, mint az időszak átlaga (3,6%)" in text

    # túlbecslés, és a sáv nem is késik gyakrabban az átlagnál: nincs „a sorrend használható"
    kind, text = nv.credibility_note(_rec(relativ_tenyleges=0.9))
    assert kind == "figyelmeztetes" and "félrevezető" in text and "sorrend" not in text

    kind, text = nv.credibility_note(_rec(itelet="alábecsült", atlag_becsles=0.029))
    assert kind == "figyelmeztetes" and "rosszabb volt a becslésnél" in text

    kind, text = nv.credibility_note(_rec(itelet="összhangban", atlag_becsles=0.1,
                                          onmaga_kihagyva=False))
    assert kind == "megjegyzes"
    assert text.startswith("A teszt-időszakban a hasonló (30% feletti) becslésű 39 rendelésből")
    assert text.endswith("összhangban a modell átlagos 10,0%-os becslésével.")

    kind, text = nv.credibility_note(_rec(itelet="kevés adat", rendelesek=12))
    assert kind == "megjegyzes" and "nem lehet ítélni" in text
