"""Rendelés kockázata — egy rendelés becslése és magyarázata (SHAP), négy modellel."""

import numpy as np
import streamlit as st

from ui import backend as d
from ui import charts, common
from xai import narrative as nv

common.page_header(
    "Rendelés kockázata",
    "Mekkora eséllyel késik egy rendelés, és miért gondolja ezt a modell? A magyarázat a modell "
    "döntését bontja tényezőkre — nem ok-okozati állítás a valóságról.")
common.require_warehouse()
b = common.bundle()
rt = common.risk_table()
avg = float(rt["valoszinuseg"].mean())        # a teszt-időszak átlagos becslése
top = rt.head(200)

# ------------------------------------------------------------- kiválasztás
# Az aktuális rendelés a munkamenetben él, és az URL-ben is (?rendeles=…),
# így egy rendelés magyarázata linkkel megosztható.
if "rendeles" not in st.session_state:
    st.session_state["rendeles"] = st.query_params.get("rendeles") or rt["order_key"].iloc[0]


def _from_list():
    if st.session_state.get("lista"):
        st.session_state["rendeles"] = st.session_state["lista"]
        st.session_state["kulcs_be"] = ""


def _from_key():
    v = (st.session_state.get("kulcs_be") or "").strip()
    if v:
        st.session_state["rendeles"] = v


def _random():
    st.session_state["veletlen"] = st.session_state.get("veletlen", 0) + 1
    rng = np.random.default_rng(st.session_state["veletlen"])
    st.session_state["rendeles"] = rt["order_key"].iloc[int(rng.integers(len(rt)))]
    st.session_state["kulcs_be"] = ""


def _from_table():
    rows = st.session_state["tabla"].selection.rows
    if rows:
        st.session_state["rendeles"] = rt["order_key"].iloc[rows[0]]
        st.session_state["kulcs_be"] = ""


labels = {r.order_key: f"#{r.rang} · {r.leadva:%Y-%m-%d} · {nv.fmt_pct(r.valoszinuseg)} · "
                       f"{r.kategoria} · {r.vevo_allam}" for r in top.itertuples()}
options = list(top["order_key"])
current = st.session_state["rendeles"]
st.session_state["lista"] = current if current in labels else None

c1, c2, c3 = st.columns([5, 4, 2], vertical_alignment="bottom")
c1.selectbox("A legkockázatosabb 200 rendelés a teszt-időszakban", options, index=None,
             format_func=lambda k: labels.get(k, k), key="lista", on_change=_from_list,
             placeholder="válassz a listából…")
c2.text_input("…vagy egy rendelés azonosítója (order_key)", key="kulcs_be", on_change=_from_key,
              placeholder="pl. " + rt["order_key"].iloc[0][:12] + "…")
c3.button("Véletlen rendelés", on_click=_random, icon=":material/casino:", width="stretch")

with st.expander(f"Kockázati lista — a teszt-időszak mind a {nv.fmt_num(len(rt), 0)} rendelése "
                 "(kattints egy sorra)"):
    cols = ["rang", "leadva", "valoszinuseg", "relativ", "kategoria", "vevo_allam", "elado_allam",
            "vallalt_ido_nap"] + (["kesett"] if common.show_outcome() else [])
    st.dataframe(rt[cols], hide_index=True, on_select=_from_table, selection_mode="single-row",
                 key="tabla", height=320, column_config={
                     "rang": st.column_config.NumberColumn("#"),
                     "leadva": st.column_config.DatetimeColumn("leadva", format="YYYY-MM-DD HH:mm"),
                     "valoszinuseg": st.column_config.ProgressColumn(
                         "becsült kockázat", format="percent", min_value=0.0,
                         max_value=float(rt["valoszinuseg"].max())),
                     "relativ": st.column_config.NumberColumn("× átlag", format="%.1f×"),
                     "kategoria": "kategória", "vevo_allam": "vevő állama",
                     "elado_allam": "eladó állama",
                     "vallalt_ido_nap": st.column_config.NumberColumn("vállalt idő (nap)"),
                     "kesett": st.column_config.CheckboxColumn("késett (utólag)"),
                 })

key = st.session_state["rendeles"]
if d.find_order(b, key) is None:
    st.warning(f"Nincs ilyen rendelés a tárházban: `{key}`. Válassz a listából, vagy ellenőrizd "
               "az azonosítót.")
    st.stop()
st.query_params["rendeles"] = key
det = common.order_detail(key, avg)

# ----------------------------------------------------------------- fejléc
st.divider()
st.markdown(f"#### Rendelés `{det['order_key']}`")
st.caption(f"leadva {det['leadva']} · vállalt határidő {det['vallalt_hatarido']} · "
           f"{det['ablak']} ablak")
if det["ablak"] == "tanító":
    st.warning("Ezen a rendelésen a modell tanult: a becslés nem független előrejelzés "
               "(a magyarázat ettől még pontosan a modellt írja le).")
elif det["ablak"] == "validációs":
    st.info("Validációs ablak: a modell nem tanult rajta, de a lezárt kiértékelés a teszt-ablakra szól.")

p, p0 = det["valoszinuseg"], det["alap"]
rec = det["hasonlok"]
m = st.columns(4)
m[0].metric("Becsült kockázat", nv.fmt_pct(p), border=True,
            help="A késés valószínűsége a lezárt v3 LightGBM-modell szerint (utólagos kalibrátor "
                 "nélkül). Hogy ez a szám mennyire hihető, azt a harmadik kártya mutatja.")
m[1].metric("Relatív kockázat", f"{nv.fmt_num(det['relativ_kockazat'], 1)}×", border=True,
            help=f"A becslés osztva a teszt-időszak átlagos becslésével ({nv.fmt_pct(avg)}).")
# Természetes gyakoriság — de nem a modell állításáé, hanem a hasonló becslésűek tényleges
# kimenetéé: a modell valószínűsége a farokban nem kalibrált (lásd A modell oldal sávtábláját).
where = nv.RECORD_WHERE[rec["ablak"]].lower()
if rec["rendelesek"]:
    n_obs, base = nv.natural_frequency(rec["tenyleges_arany"])
    m[2].metric("Hasonló becslésűekből késett", f"{nv.per_base(base)} {n_obs}", border=True,
                help=f"Ennyi késett ténylegesen {where} azok közül a rendelések közül, amelyekre a "
                     f"modell szintén {rec['sav_szoveg']} kockázatot becsült: "
                     f"{nv.fmt_num(rec['rendelesek'], 0)} rendelésből {nv.fmt_num(rec['kesett'], 0)} "
                     f"({nv.fmt_pct(rec['tenyleges_arany'])}; 95%-os intervallum: "
                     f"{nv.fmt_pct(rec['ci_also'])} – {nv.fmt_pct(rec['ci_felso'])}). Ez mutatja, "
                     "mennyire hihető a becsült szám."
                     + (" A rendelés saját kimenete nem számít bele." if rec["onmaga_kihagyva"] else ""))
else:
    m[2].metric("Hasonló becslésűekből késett", "nincs adat", border=True)
if common.show_outcome():
    m[3].metric("Valós kimenet", "késett" if det["kesett"] else "időben", border=True,
                help="Történeti adat: ez a becsléskor még nem volt ismert. Egy rendelés "
                     "kimenetéből nem lehet a modell jóságára következtetni — azt A modell oldal mutatja.")
else:
    m[3].metric("Valós kimenet", "rejtve", border=True,
                help="Bekapcsolható az oldalsávon. Rejtett kimenetnél a becslés hitelességét a "
                     "validációs időszak mutatja — azt egy éles bevezetéskor már ismerni lehetett volna.")

kind_of_note, note = nv.credibility_note(rec)
if kind_of_note == "figyelmeztetes":
    st.warning(note, icon=":material/balance:")
else:
    st.caption(note)

# ------------------------------------------------------------- magyarázat
st.markdown("##### Miért?")
with st.container(border=True):
    st.markdown(det["narrativa"])
    st.caption("Sablonból írt szöveg: minden szám a lenti magyarázatból jön.")

k = st.slider("Megjelenített tényezők", 3, 12, 8, key="tenyezok_szama")
st.altair_chart(charts.reasons_chart(det["tenyezok"].head(k), ink=common.ink()), width="stretch")
total = det["tenyezok"]["hatas_pp"].sum()
gap = det["additivitasi_elteres_pp"]
gap_text = "< 0,000001 pp" if gap < 1e-6 else f"{nv.fmt_num(gap, 6)} pp"
st.caption(f"Kiindulópont {nv.fmt_pct(p0)} + a 21 tényező hatásának összege {nv.fmt_pp(total, 2)} "
           f"százalékpont = {nv.fmt_pct(p)} (eltérés: {gap_text}). "
           "A kiindulópont a modell átlaga a tanító időszakon (log-odds térben átlagolva, ezért "
           "kisebb a tényleges 5–6%-os aránynál). A hónap két kódoló oszlopa egy tényezőként "
           "szerepel.")

with st.expander("Mind a 21 tényező"):
    st.dataframe(det["tenyezok"][["nev", "ertek", "hatas_pp", "leiras"]], hide_index=True,
                 column_config={
                     "nev": "tényező", "ertek": "érték",
                     "hatas_pp": st.column_config.NumberColumn("hatás (pp)", format="%+.2f"),
                     "leiras": "mit mér"})

# --------------------------------------------------------- négy modell
st.markdown("##### Ugyanez a rendelés négy modell szemével")
ag = d.agreement(det)
shown = ag.assign(becsles=[nv.fmt_pct(v) for v in ag["becsles"]],
                  kiindulopont=[nv.fmt_pct(v) for v in ag["kiindulopont"]])
st.dataframe(shown, hide_index=True, column_config={
    "modell": "modell",
    "becsles": "becslés",
    "kiindulopont": "kiindulópont",
    "legerosebb_tenyezok": "a 3 legerősebb tényező (▲ növeli, ▼ csökkenti)",
    "kozos_a_lightgbm_mel": st.column_config.TextColumn("közös a LightGBM top 3-mal"),
    "magyarazo_ter": "a magyarázat tere",
})
st.altair_chart(charts.comparison_heatmap(d.model_comparison(det), [r for r in ag["modell"]]),
                width="stretch")
st.caption("Hatás százalékpontban, a legerősebb 8 tényező. Ha a modellek más tényezőket tartanak "
           "fontosnak, az a magyarázat bizonytalanságát jelzi: ugyanazt az adatot többféleképpen "
           "is jól lehet magyarázni. A LightGBM és a logisztikus regresszió magyarázata log-odds "
           "térben pontos, százalékpontra arányosan átváltva; a döntési fáé és a random foresté "
           "közvetlenül valószínűség-térben — a kiindulópontok ezért is eltérnek.")

with st.expander("Hogyan olvasd?"):
    st.markdown(
        "- **A becslés** a lezárt LightGBM-modell valószínűsége arra, hogy a rendelés a vállalt "
        "határidő után érkezik. A modell csak a leadáskor ismert adatokat látja.\n"
        "- **A tényezők** (SHAP-értékek) azt mutatják, mennyivel tolta el az egyes adatok értéke "
        "a becslést a modell kiindulópontjához képest. Összegük pontosan a becslés és a "
        "kiindulópont különbsége.\n"
        "- **Nem ok-okozat:** ha a vevő állama +30 százalékpont, az azt jelenti, hogy a modell "
        "ebből az adatból következtet nagyobb kockázatra — nem azt, hogy az állam megváltoztatása "
        "csökkentené a késést.\n"
        "- **Relatív kockázat:** egy 8%-os becslés kicsinek tűnik, de az időszak átlagának "
        "kétszerese.\n"
        "- **Hasonló becslésűek:** a modell száma önmagában nem garancia. A harmadik kártya azt "
        "mutatja, hogy a hasonló becslésű rendelések közül ténylegesen hány késett („100-ból "
        "hány”). Ha ez a becsléstől eltér, a sárga megjegyzés jelzi — ilyenkor a sorrend (hogy a "
        "rendelés a kockázatosabbak közé tartozik) megbízhatóbb, mint a pontos szám.")
