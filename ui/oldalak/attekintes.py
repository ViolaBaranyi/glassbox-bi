"""Áttekintés — a késések alakulása, tisztán az adatokból (SQL), a modelltől függetlenül."""

import streamlit as st

from ui import backend as d
from ui import charts, common
from xai import labels
from xai import narrative as nv

common.page_header(
    "Áttekintés",
    "Hány rendelés késett, mikor és hol? Ezek a számok közvetlenül az adatokból jönnek — a "
    "modelltől függetlenül.")
ov = common.require_warehouse()

common.intro(
    "**Mit látsz ezen az oldalon?** Egy brazil online piactér (Olist) valódi rendeléseit "
    f"{nv.fmt_date(ov['elso'])} és {nv.fmt_date(ov['utolso'])} között. Minden rendelésnél a "
    "webáruház a vásárláskor megígért egy kézbesítési napot; ha a csomag ennél később érkezett "
    "meg, a rendelés **késett**. Fent az összesítés, középen a havi alakulás, lent pedig az, hogy "
    "hol késnek a legtöbbször.",
    "- **Késési arány:** a rendelések hány százaléka érkezett meg az ígért nap után. Ha 100 "
    "rendelésből 7 késett, a késési arány 7%.\n"
    "- **A halvány sáv és a vékony vonalak** a bizonytalanságot mutatják: ahol kevés rendelés volt, "
    "ott a valódi arány messzebb is lehet a mért értéktől. A sáv azt a tartományt jelöli, amelyben "
    "a valódi arány 95%-os valószínűséggel benne van.\n"
    "- **A kétbetűs kódok** a brazil szövetségi államok rövidítései (pl. SP = São Paulo). Az "
    "ábrákon a teljes nevet is kiírjuk; a teljes listát a *Súgó* oldalon találod.\n"
    "- **Minden számot ellenőrizhetsz:** a „Hogyan számoltuk?” részben ott van a pontos "
    "adatbázis-lekérdezés.")

c = st.columns(4)
c[0].metric("Kézbesített rendelések", nv.fmt_num(ov["rendelesek"], 0), border=True,
            help="Ennyi rendelés érkezett meg a vevőhöz a vizsgált időszakban. Csak ezeknél tudjuk "
                 "biztosan, hogy késtek-e.")
c[1].metric("Késési arány", nv.fmt_pct(ov["kesesi_arany"]), border=True,
            help="A rendelések ennyi százaléka érkezett meg a webáruház által ígért nap után. "
                 f"Kb. 100 rendelésből {round(100 * ov['kesesi_arany'])} késett.")
c[2].metric("Időszak", f"{ov['elso'][:4]}–{ov['utolso'][:4]}", border=True,
            help=f"Az első rendelés: {nv.fmt_date(ov['elso'])}, az utolsó: "
                 f"{nv.fmt_date(ov['utolso'])}. Az adat állapota (az utolsó ismert esemény): "
                 f"{nv.fmt_date(ov['zarnap'])}.")
c[3].metric("Kihagyott rendelések", nv.fmt_num(ov["kizart"], 0), border=True,
            help="Törölt, elveszett vagy még úton lévő rendelések. Ezeknél nem tudjuk, késtek-e "
                 "volna, ezért a fenti számokban nincsenek benne.")

# ----------------------------------------------------------------- havi trend
st.subheader("Hogyan alakult a késés hónapról hónapra?")
m, win = common.monthly(), common.windows()
rate_chart, volume_chart = charts.monthly_chart(m, win)
st.altair_chart(rate_chart, width="stretch")
st.altair_chart(volume_chart, width="stretch")
dropped = m[~m["megbizhato"]]
note = ""
if len(dropped):
    months = ", ".join(f"{t.year}. {nv.MONTHS[t.month - 1]} ({n} rendelés)"
                       for t, n in zip(dropped["honap"], dropped["rendelesek"]))
    note = (f" Azokat a hónapokat, amelyekben {d.MIN_MONTH_ORDERS}-nál kevesebb rendelés volt, "
            f"kihagytuk, mert ott az arány a véletlenen múlik: {months}.")
def _window(key: str) -> str:
    text = labels.WINDOW_PLAIN[key].rstrip(".")
    return f"{labels.WINDOW_LABELS[key]} ({text[0].lower() + text[1:]})"


st.caption(
    "**Hogyan olvasd?** A piros vonal a havi késési arány, a halvány piros sáv a "
    "bizonytalansága. Alatta a szürke oszlopok a havi rendelésszámot mutatják. A háttérszínek azt "
    f"jelzik, melyik időszak mire szolgált: **kék** — {_window('tanító')}; **narancs** — "
    f"{_window('validációs')}; **zöld** — {_window('teszt')}. Vidd az egeret egy pont fölé a "
    "pontos számokért." + note)
with st.expander("Hogyan számoltuk? (az adatbázis-lekérdezés)"):
    st.code(d.SQL_MONTHLY, language="sql")

# ------------------------------------------------------------------ bontás
st.subheader("Hol késnek a legtöbbször?")
c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
dim = c1.segmented_control("Mi szerint bontsuk?", options=list(d.DIMENSIONS), default="vevo_allam",
                           format_func=lambda k: d.DIMENSIONS[k][0], key="dimenzio",
                           required=True,
                           help="A vevő állama: hová megy a csomag. Az eladó állama: honnan "
                                "indul. A fő termék kategóriája: a rendelés legdrágább termékének "
                                "fajtája.")
min_n = c2.slider("Csak ahol legalább ennyi rendelés volt", 50, 3000, 300, step=50, key="min_n",
                  help="A kevés rendelésből számolt arány megbízhatatlan (pár rendelésnél egyetlen "
                       "késés is nagy arányt adna). A csúszkával kiszűrheted ezeket.")
label = d.DIMENSIONS[dim][0]
df = common.by_dimension(dim, min_n)
is_state = dim in ("vevo_allam", "elado_allam")
unit, unit_in = ("állam", "egy államban") if is_state else ("kategória", "egy kategóriában")
if df.empty:
    st.info("Ennyi rendelés egyik értéknél sincs — csökkentsd a küszöböt a csúszkával.")
else:
    bar_chart = charts.dimension_chart(df, ov["kesesi_arany"], label, ink=common.ink())
    if is_state:
        left, right = st.columns([3, 2], gap="large")
        left.altair_chart(bar_chart, width="stretch")
        with right:
            where = "ahová a csomag ment" if dim == "vevo_allam" else "ahonnan a csomag indult"
            st.markdown("**Hol vannak ezek az államok?**")
            st.altair_chart(charts.state_tile_map(
                df, ov["kesesi_arany"],
                count_title="rendelések (ide ment)" if dim == "vevo_allam" else
                "rendelések (innen indult)"), width="content")
            st.caption(
                "Egyszerűsített térkép: minden állam egy egyforma négyzet, nagyjából a valódi helyén "
                f"(fent az észak, balra a nyugat). A szín az állam ({where}) késési aránya: **piros**, "
                "ha az átlagnál gyakrabban késtek, **kék**, ha ritkábban; **szürke**, ha a küszöbnél "
                "kevesebb rendelés volt. Vidd az egeret egy négyzet fölé a teljes névért és a "
                "számokért.")
    else:
        st.altair_chart(bar_chart, width="stretch")
    top = df.iloc[0]
    st.caption(
        f"**Hogyan olvasd?** Minden sáv egy {unit} késési "
        f"aránya; a szaggatott függőleges vonal az összes rendelés átlaga "
        f"({nv.fmt_pct(ov['kesesi_arany'])}). A vékony vízszintes vonal a bizonytalansági sáv: ha két "
        "érték sávja nem fedi egymást, a különbség nem a véletlen műve; ha átfedik, nem lehet "
        f"biztosan megmondani, melyik a rosszabb. A legmagasabb most: **{top['megnevezes']}** "
        f"({nv.fmt_pct(top['kesesi_arany'])}, {nv.fmt_num(top['rendelesek'], 0)} rendelésből "
        f"{nv.fmt_num(top['kesett'], 0)} késett). Ez együttjárás, nem ok: abból, hogy {unit_in} "
        "több a késés, még nem tudjuk, miért.")
with st.expander("Táblázat és a pontos számítás (lekérdezés)"):
    cols = ["megnevezes"] + (["regio"] if "regio" in df else []) + \
        ["ertek", "rendelesek", "kesett", "kesesi_arany", "ci_also", "ci_felso"]
    view = df[cols].copy()
    for c_ in ("kesesi_arany", "ci_also", "ci_felso"):
        view[c_] = [nv.fmt_pct(v) for v in view[c_]]
    st.dataframe(view, hide_index=True, column_config={
        "megnevezes": st.column_config.TextColumn(label, width="large"),
        "regio": st.column_config.TextColumn("régió (Brazílián belül)"),
        "ertek": st.column_config.TextColumn("kód az adatban"),
        "rendelesek": st.column_config.NumberColumn("rendelések"),
        "kesett": st.column_config.NumberColumn("ebből késett"),
        "kesesi_arany": st.column_config.TextColumn("késési arány"),
        "ci_also": st.column_config.TextColumn(
            "tartomány alja", help="A valószínű tartomány (95%-os intervallum) alja: a valódi "
                                   "késési arány nagy valószínűséggel e fölött van."),
        "ci_felso": st.column_config.TextColumn(
            "tartomány teteje", help="A valószínű tartomány (95%-os intervallum) teteje: a valódi "
                                     "késési arány nagy valószínűséggel e alatt van."),
    })
    st.code(d.sql_by_dimension(dim).replace("?", str(int(min_n))), language="sql")
