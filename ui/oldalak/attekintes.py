"""Áttekintés — a késések alakulása, tisztán SQL-ből (a modelltől független)."""

import streamlit as st

from ui import backend as d
from ui import charts, common
from xai import narrative as nv

common.page_header(
    "Áttekintés",
    "Hány rendelés késett, mikor és hol? Minden szám egy SQL-lekérdezés eredménye a tárházból — "
    "determinisztikus, a modelltől független.")
ov = common.require_warehouse()

c = st.columns(4)
c[0].metric("Kézbesített rendelések", nv.fmt_num(ov["rendelesek"], 0), border=True)
c[1].metric("Késési arány", nv.fmt_pct(ov["kesesi_arany"]), border=True,
            help="A vállalt határidő után kézbesített rendelések aránya.")
c[2].metric("Időszak", f"{ov['elso'][:4]}–{ov['utolso'][:4]}", border=True,
            help=f"A rendelések leadása: {ov['elso']} – {ov['utolso']}. "
                 f"Megfigyelési zárónap: {ov['zarnap']}.")
c[3].metric("Kizárt rendelések", nv.fmt_num(ov["kizart"], 0), border=True,
            help="Nem kézbesített (törölt, elveszett, úton lévő) rendelések: a kimenetük nem "
                 "ismert, ezért a fenti számokban nincsenek benne (érzékenységi jelentés: "
                 "python -m pipeline.cohort_report).")

# ----------------------------------------------------------------- havi trend
st.subheader("Havi késési arány")
m, win = common.monthly(), common.windows()
rate_chart, volume_chart = charts.monthly_chart(m, win)
st.altair_chart(rate_chart, width="stretch")
st.altair_chart(volume_chart, width="stretch")
dropped = m[~m["megbizhato"]]
note = ""
if len(dropped):
    months = ", ".join(f"{t:%Y-%m} ({n} rendelés)" for t, n in zip(dropped["honap"], dropped["rendelesek"]))
    note = (f" A {d.MIN_MONTH_ORDERS}-nál kevesebb rendeléses hónapok aránya csak zaj, ezért "
            f"kimaradtak: {months}.")
st.caption("A sáv a havi arány 95%-os Wilson-intervalluma. A háttérszín a modellek ablakait "
           "jelöli: a modellek a tanító ablakon tanultak, a teszt-ablakot csak a lezárt "
           "kiértékelés látta." + note)
with st.expander("A lekérdezés (SQL)"):
    st.code(d.SQL_MONTHLY, language="sql")

# ------------------------------------------------------------------ bontás
st.subheader("Hol késnek a legtöbbször?")
c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
dim = c1.segmented_control("Bontás", options=list(d.DIMENSIONS), default="vevo_allam",
                           format_func=lambda k: d.DIMENSIONS[k][0], key="dimenzio",
                           required=True)
min_n = c2.slider("Csak ahol legalább ennyi rendelés volt", 50, 3000, 300, step=50, key="min_n")
label = d.DIMENSIONS[dim][0]
df = common.by_dimension(dim, min_n)
if df.empty:
    st.info("Ennyi rendelés egyik értéknél sincs — csökkentsd a küszöböt.")
else:
    st.altair_chart(charts.dimension_chart(df, ov["kesesi_arany"], label, ink=common.ink()),
                    width="stretch")
    st.caption("A vékony vonal a 95%-os Wilson-intervallum. Ha két érték intervalluma nem fedi "
               "egymást, a különbség nem a véletlen műve; ha átfednek, abból még nem következik, "
               "hogy nincs különbség. Kevés rendelésnél az intervallum széles.")
with st.expander("Táblázat és lekérdezés"):
    st.dataframe(df, hide_index=True, column_config={
        "ertek": st.column_config.TextColumn(label),
        "rendelesek": st.column_config.NumberColumn("rendelések"),
        "kesett": st.column_config.NumberColumn("késett"),
        "kesesi_arany": st.column_config.NumberColumn("késési arány", format="percent"),
        "ci_also": st.column_config.NumberColumn("95% alsó", format="percent"),
        "ci_felso": st.column_config.NumberColumn("95% felső", format="percent"),
    })
    st.code(d.sql_by_dimension(dim).replace("?", str(int(min_n))), language="sql")
