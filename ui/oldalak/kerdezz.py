"""Kérdezz — a nyelvi réteg helye (fejlesztés alatt)."""

import streamlit as st

from ui import common

common.page_header("Kérdezz", "Természetes nyelvű kérdések a késésekről — a nyelvi réteg fejlesztés alatt.")
common.require_warehouse()

st.info("Ez a rész még nem működik. Az alábbi a terv: a nyelvi modell nem számol és nem talál ki "
        "számot — csak eligazít a meglévő, ellenőrzött motorhoz, és a választ abból fogalmazza meg.",
        icon=":material/construction:")

st.markdown(
    "1. **Szándék.** A kérdésből a nyelvi modell egy rögzített listából választ szándékot és "
    "paramétereket (pl. „késési arány a vevő állama szerint”, „egy rendelés magyarázata”). "
    "**1. kapu:** csak fehérlistás szándék és az adatban ténylegesen előforduló érték (pl. "
    "államkód, kategória) megy tovább.\n"
    "2. **Számítás.** A számokat ugyanaz a determinisztikus motor adja, mint ezeken az oldalakon: "
    "SQL a tárházból, a lezárt modellek és a SHAP-magyarázatok.\n"
    "3. **Válasz.** A nyelvi modell hely-kitöltéssel ír: mezőkre hivatkozik, a számokat a motor "
    "illeszti be. **2. kapu:** minden szám, irány és tényezőnév egyezik-e a motor kimenetével — ha "
    "nem, a felület a sablonos szöveget mutatja (mint most a Rendelés kockázata oldalon).")

st.markdown("**Amire ma is van válasz:**")
c = st.columns(3)
c[0].page_link("oldalak/attekintes.py", label="Hol késnek a legtöbbször?", icon=":material/map:")
c[1].page_link("oldalak/rendeles.py", label="Miért kockázatos ez a rendelés?",
               icon=":material/local_shipping:")
c[2].page_link("oldalak/modell.py", label="Mennyire bízhatok a modellben?", icon=":material/fact_check:")

st.chat_input("Hamarosan: kérdezz a késésekről…", disabled=True)
