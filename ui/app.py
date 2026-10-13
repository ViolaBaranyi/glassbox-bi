"""
Üvegdoboz BI — a felület belépési pontja (Streamlit).

Indítás:  python -m ui     (vagy: streamlit run ui/app.py)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:           # a `streamlit run` csak a ui/ mappát teszi a keresési útra
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from ui import common  # noqa: E402

st.set_page_config(page_title="Üvegdoboz BI", page_icon=":material/insights:", layout="wide")

pages = [
    st.Page("oldalak/attekintes.py", title="Áttekintés", icon=":material/dashboard:", default=True),
    st.Page("oldalak/rendeles.py", title="Rendelés kockázata", icon=":material/local_shipping:"),
    st.Page("oldalak/modell.py", title="A modell", icon=":material/fact_check:"),
    st.Page("oldalak/kerdezz.py", title="Kérdezz", icon=":material/forum:"),
    st.Page("oldalak/sugo.py", title="Súgó és fogalmak", icon=":material/help:"),
]
page = st.navigation(pages)
common.sidebar()
page.run()
