"""Kérdezz — a nyelvi réteg helye (fejlesztés alatt)."""

import streamlit as st

from ui import common

common.page_header("Kérdezz", "Kérdések hétköznapi nyelven a késésekről — ez a rész még fejlesztés alatt áll.")
common.require_warehouse()

st.info("**Ez a rész még nem működik.** Később ide írhatsz be egy kérdést magyarul, például: "
        "„Melyik államban késnek a legtöbbet?” vagy „Miért kockázatos ez a rendelés?”, és a "
        "felület szövegesen válaszol.", icon=":material/construction:")

st.markdown("##### Hogyan fog működni — és miért lehet majd megbízni benne?")
st.markdown(
    "A válaszokat egy nyelvi modell (egy szöveget értő és író mesterséges intelligencia) "
    "fogalmazza meg, de **egyetlen számot sem ő talál ki**. Három lépésben dolgozik:\n\n"
    "1. **Megérti a kérdést.** Egy előre rögzített listából kiválasztja, mire vagy kíváncsi "
    "(például „késési arány államonként” vagy „egy rendelés magyarázata”). "
    "**Első ellenőrzés:** csak a listán szereplő kérdéstípus és az adatban ténylegesen létező érték "
    "(például egy valódi államkód) mehet tovább — így nem tud nem létező dolgokról beszélni.\n"
    "2. **Kiszámolja a választ.** A számokat ugyanaz a megbízható gépezet adja, mint ezeken az "
    "oldalakon: az adatbázis és a modell.\n"
    "3. **Megfogalmazza a választ.** A nyelvi modell csak a mondatokat írja; a számokat a gép "
    "illeszti be a helyükre. **Második ellenőrzés:** minden számot, irányt (nő vagy csökken) és "
    "tényezőnevet összevetünk a gép eredményével — ha bármi eltér, a felület a nyelvi modell "
    "szövege helyett a biztonságos, sablonos szöveget mutatja.")

st.markdown("**Amire már most is van válasz:**")
c = st.columns(3)
c[0].page_link("oldalak/attekintes.py", label="Hol késnek a legtöbbször?", icon=":material/map:")
c[1].page_link("oldalak/rendeles.py", label="Miért kockázatos ez a rendelés?",
               icon=":material/local_shipping:")
c[2].page_link("oldalak/modell.py", label="Mennyire bízhatok a modellben?", icon=":material/fact_check:")

st.chat_input("Hamarosan: kérdezz a késésekről…", disabled=True)
