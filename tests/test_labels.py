"""
A felület emberi nevei (xai.labels) — adat nélkül.

  * mind a 27 brazil szövetségi egység (26 állam + DF) megvan, régióval;
  * a valódi Olist-adat MINDEN kategóriájának (és a szintetikus adaténak) van magyar neve;
  * minden megjelenítési tényezőnek van hétköznapi leírása, minden modellnek és időszaknak neve;
  * ismeretlen értéknél sem hiba, hanem olvasható szöveg.
"""

from __future__ import annotations

import numpy as np

from data.make_synthetic import CATEGORIES as SYNTH_CATEGORIES
from data.make_synthetic import STATES as SYNTH_STATES
from ui.backend import WINDOW_NAMES
from xai import labels
from xai import narrative as nv
from xai.models import KINDS

# A valódi adat fő-tétel kategóriái (2026. okt. 12., 96 470 rendelés; a tárház az
# angol nevet használja, a fordítás nélkülieket „ismeretlen"-nek jelöli).
REAL_CATEGORIES = """
bed_bath_table health_beauty sports_leisure computers_accessories furniture_decor housewares
watches_gifts telephony auto toys cool_stuff garden_tools perfumery baby electronics stationery
fashion_bags_accessories pet_shop ismeretlen office_furniture consoles_games luggage_accessories
home_appliances construction_tools_construction musical_instruments small_appliances
books_general_interest home_construction food furniture_living_room home_confort audio drinks
market_place books_technical air_conditioning kitchen_dining_laundry_garden_furniture
fashion_shoes construction_tools_lights industry_commerce_and_business home_appliances_2
food_drink fixed_telephony art costruction_tools_garden agro_industry_and_commerce computers
construction_tools_safety signaling_and_security christmas_supplies fashion_underwear_beach
fashion_male_clothing costruction_tools_tools furniture_bedroom tablets_printing_image
small_appliances_home_oven_and_coffee cine_photo dvds_blu_ray books_imported
furniture_mattress_and_upholstery party_supplies music fashio_female_clothing flowers
diapers_and_hygiene fashion_sport home_comfort_2 arts_and_craftmanship la_cuisine
cds_dvds_musicals fashion_childrens_clothes security_and_services
""".split()

REAL_STATES = ("SP RJ MG RS PR SC BA DF ES GO PE CE PA MT MA MS PB PI RN AL SE TO RO AM AC AP "
               "RR").split()


def test_allamok():
    assert len(labels.STATES) == 27 and set(REAL_STATES) == set(labels.STATES)
    assert set(SYNTH_STATES) <= set(labels.STATES)
    assert {r for _, r in labels.STATES.values()} == set(labels.REGIONS)
    assert labels.state_label("AL") == "Alagoas (AL)"
    assert labels.state_name("sp") == "São Paulo"
    assert labels.state_region("RS") == "Dél"
    assert labels.state_label("XX") == "XX"                      # ismeretlen kód: maga a kód
    assert labels.state_label(None) == "ismeretlen állam"
    assert labels.state_label(np.nan) == "ismeretlen állam"
    assert labels.state_region(None) == ""


def test_minden_kategorianak_van_magyar_neve():
    assert len(REAL_CATEGORIES) == 72
    missing = [c for c in REAL_CATEGORIES if c not in labels.CATEGORIES]
    assert not missing, missing
    assert {en for _, en in SYNTH_CATEGORIES} <= set(labels.CATEGORIES)
    names = [labels.CATEGORIES[c] for c in REAL_CATEGORIES]
    assert len(set(names)) == len(names)                         # két kategória ne kapja ugyanazt
    assert all(n and "_" not in n for n in names)
    assert labels.category_name("health_beauty") == "egészség és szépségápolás"
    assert labels.category_name("valami_uj_kategoria") == "valami uj kategoria"
    assert labels.category_name(None) == labels.category_name("(ismeretlen)") == "ismeretlen kategória"


def test_tenyezok_modellek_idoszakok():
    assert set(labels.PLAIN_INFO) == set(nv.DISPLAY_FEATURES)
    for key in nv.DISPLAY_FEATURES:
        text = labels.PLAIN_INFO[key]
        assert text.endswith(".") and len(text) > 20, key
        assert nv.display_info(key) == text                     # a felület ezt mutatja
        assert nv.technical_info(key)                           # a szakmai leírás megmaradt
    assert set(labels.MODEL_PLAIN) == set(KINDS)
    assert set(labels.WINDOW_LABELS) == set(WINDOW_NAMES.values()) == set(labels.WINDOW_PLAIN)


def test_ertekek_a_szovegben():
    assert nv.format_value("vevo_allam", "AL") == "Alagoas (AL)"
    assert nv.format_value("elado_allam", "SP") == "São Paulo (SP)"
    assert nv.format_value("kategoria", "toys") == "játékok"
    assert nv.fmt_date("2018-08-09 18:27:00") == "2018. aug. 9."
    assert nv.fmt_datetime("2018-08-09 18:27:00") == "2018. aug. 9. 18:27"


def test_negyzetracs_minden_allammal():
    assert set(labels.TILE_GRID) == set(labels.STATES)
    cells = list(labels.TILE_GRID.values())
    assert len(set(cells)) == len(cells)                                  # nincs két állam egy helyen
    assert all(0 <= c <= 5 and 0 <= r <= 7 for c, r in cells)
    # nagyjából a valódi helyük: észak fent, dél lent, nyugat balra
    col, row = zip(*(labels.TILE_GRID[k] for k in ("RR", "RS")))
    assert row[0] < row[1]                                                  # Roraima Rio Grande do Sul fölött
    assert labels.TILE_GRID["AC"][0] < labels.TILE_GRID["PE"][0]            # Acre nyugatra Pernambucótól
