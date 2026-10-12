"""
M5 — a BI-felület (Streamlit). Indítás a projekt gyökeréből:

    python -m ui                  # megnyílik a böngészőben: http://localhost:8501
    indit_felulet.bat             # Windowson dupla kattintással is

    ui/app.py        belépési pont: oldalsáv + navigáció
    ui/oldalak/      az oldalak (áttekintés, rendelés, modell, kérdezz)
    ui/backend.py    adatréteg (SQL + modellek) — Streamlit nélkül is tesztelhető
    ui/charts.py     grafikonok (Altair)
    ui/common.py     gyorsítótárazott betöltők, oldalsáv
"""
