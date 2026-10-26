"""Rendelés kockázata — egy rendelés becslése és magyarázata (SHAP), négy modellel."""

import numpy as np
import streamlit as st

from ui import backend as d
from ui import charts, common
from xai import labels
from xai import narrative as nv
from xai.models import KINDS, NAMES

common.page_header(
    "Rendelés kockázata",
    "Mekkora eséllyel késik egy rendelés, és miért gondolja ezt a modell?")
common.require_warehouse()
b = common.bundle()
rt = common.risk_table()
avg = float(rt["valoszinuseg"].mean())        # a teszt-időszak átlagos becslése

common.intro(
    "**Mit látsz ezen az oldalon?** Válassz egy rendelést a listából, vagy kérj egy véletlent. "
    "Megmutatjuk, mekkora eséllyel érkezik késve a modell szerint, mennyire lehet ebben a számban "
    "megbízni, és melyik adat mennyivel növelte vagy csökkentette a kockázatot. A lista a "
    f"**teszt-időszak** ({common.window_period('teszt')}) rendeléseit tartalmazza: ezeket a modell tanulás közben sosem "
    "látta, vagyis valódi előrejelzést mutatunk.",
    "1. **Becsült kockázat:** a modell szerint ennyi az esélye, hogy a csomag az ígért nap után "
    "érkezik. 10% azt jelenti: 10 ilyen rendelésből kb. 1 késne.\n"
    "2. **Hányszor az átlag:** a becslés az időszak átlagos rendeléséhez képest. Egy 8%-os "
    "kockázat kicsinek tűnik, de ha az átlag 4%, akkor kétszer akkora.\n"
    "3. **Hasonló becslésűekből késett:** a modell száma önmagában nem garancia. Ez a kártya azt "
    "mutatja, hogy azok közül a rendelések közül, amelyekre a modell hasonló kockázatot mondott, "
    "100-ból hány késett **ténylegesen**. Ha ez nagyon eltér a becsléstől, sárga figyelmeztetés "
    "jelenik meg.\n"
    "4. **Miért?** A kiindulópont egy átlagos rendelés kockázata. Minden adat (pl. a távolság "
    "vagy a vevő állama) ehhez hozzáad (piros sáv) vagy levon belőle (kék sáv); a számok "
    "százalékpontban vannak, és összeadva pontosan kiadják a becslést.\n"
    "5. **Fontos:** a magyarázat azt mutatja, mire figyel a *modell* — nem azt, hogy mi *okozza* a "
    "késést. Ha a vevő állama sokat növel, az nem jelenti, hogy egy másik államba küldve "
    "biztosan időben érne oda.")

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


top = rt.head(200)
option_labels = {r.order_key: f"{r.rang}. · {nv.fmt_date(r.leadva)} · {nv.fmt_pct(r.valoszinuseg)} · "
                              f"{r.kategoria_nev} · {labels.state_name(r.vevo_allam)}"
                 for r in top.itertuples()}
options = list(top["order_key"])
current = st.session_state["rendeles"]
st.session_state["lista"] = current if current in option_labels else None

c1, c2, c3 = st.columns([5, 4, 2], vertical_alignment="bottom")
c1.selectbox("A 200 legkockázatosabb rendelés (sorszám · leadás · becslés · termék · hová megy)",
             options, index=None, format_func=lambda k: option_labels.get(k, k), key="lista",
             on_change=_from_list, placeholder="válassz a listából…")
c2.text_input("…vagy írd be egy rendelés azonosítóját", key="kulcs_be", on_change=_from_key,
              placeholder="pl. " + rt["order_key"].iloc[0][:12] + "…",
              help="Minden rendelésnek van egy hosszú, egyedi azonosítója (betűk és számok). "
                   "Ha egy rendelés oldalát linkként megosztod, ez kerül a címbe.")
c3.button("Véletlen rendelés", on_click=_random, icon=":material/casino:", width="stretch",
          help="Egy véletlenszerűen kiválasztott rendelés a teszt-időszakból — a legtöbb rendelés "
               "kis kockázatú.")
_dres = d.decision_stability_results()
if _dres is not None and "lightgbm" in _dres["modellek"]:
    _ui = _dres["modellek"]["lightgbm"]["bootstrap"]["ui_atfedes"]["ertek"]
    st.caption(f"A lista a becslés sorrendje, nem végleges kiválasztás: ha a modellt kicsit más adaton "
               f"tanítanánk, a 200 rendelésből átlagosan kb. {nv.fmt_pct(_ui, 0)} maradna a listán (részletek: "
               "*A modell* oldal, „Mennyire stabilak a magyarázatok?”).")

with st.expander(f"A teljes kockázati lista — a teszt-időszak mind a {nv.fmt_num(len(rt), 0)} "
                 "rendelése, a legkockázatosabbtól kezdve (kattints egy sorra a kiválasztáshoz)"):
    cols = ["rang", "leadva", "valoszinuseg", "relativ_szoveg", "kategoria_nev", "vevo_nev", "elado_nev",
            "vallalt_ido_nap"] + (["kesett"] if common.show_outcome() else [])
    st.dataframe(rt[cols], hide_index=True, on_select=_from_table, selection_mode="single-row",
                 key="tabla", height=320, column_config={
                     "rang": st.column_config.NumberColumn("sorszám"),
                     "leadva": st.column_config.DatetimeColumn("leadva", format="YYYY. MM. DD. HH:mm"),
                     "valoszinuseg": st.column_config.ProgressColumn(
                         "becsült kockázat", format="percent", min_value=0.0,
                         max_value=float(rt["valoszinuseg"].max())),
                     "relativ_szoveg": st.column_config.TextColumn(
                         "hányszor az átlag",
                         help="A becslés az időszak átlagos becsléséhez képest (pl. 2,0× = "
                              "kétszer akkora esély, mint egy átlagos rendelésnél)."),
                     "kategoria_nev": "termékkategória", "vevo_nev": "hová megy (vevő állama)",
                     "elado_nev": "honnan indul (eladó állama)",
                     "vallalt_ido_nap": st.column_config.NumberColumn(
                         "ígért szállítási idő (nap)"),
                     "kesett": st.column_config.CheckboxColumn("valóban késett?"),
                 })

key = st.session_state["rendeles"]
if d.find_order(b, key) is None:
    st.warning(f"Nincs ilyen rendelés az adatbázisban: `{key}`. Válassz a listából, vagy "
               "ellenőrizd az azonosítót (elírás, hiányzó karakter).")
    st.stop()
st.query_params["rendeles"] = key
det = common.order_detail(key, avg)

# ----------------------------------------------------------------- fejléc
st.divider()
window_label = labels.WINDOW_LABELS.get(det["ablak"], det["ablak"])
st.markdown("#### A kiválasztott rendelés")
st.caption(f"azonosító: `{det['order_key']}` · leadva: {nv.fmt_datetime(det['leadva'])} · "
           f"ígért kézbesítés: {nv.fmt_date(det['vallalt_hatarido'])} · {window_label}")
if det["ablak"] == "tanító":
    st.warning("Ez a rendelés a **tanulási időszakból** való: a modell ebből (is) tanult, ezért "
               "a becslése itt nem igazi előrejelzés. A magyarázat ettől még pontosan megmutatja, "
               "mire figyel a modell.", icon=":material/school:")
elif det["ablak"] == "validációs":
    st.info(f"Ez a rendelés az **ellenőrző időszakból** való ({common.window_period('validációs')}): "
            "a modell nem tanult belőle, de a hivatalos mérés a teszt-időszakra "
            f"({common.window_period('teszt')}) szól.")

p, p0 = det["valoszinuseg"], det["alap"]
rec = det["hasonlok"]
m = st.columns(4)
n_claim, base_claim = nv.natural_frequency(p)
m[0].metric("Becsült kockázat", nv.fmt_pct(p), border=True,
            help=f"A modell szerint ennyi az esélye, hogy a csomag az ígért nap után érkezik "
                 f"(kb. {base_claim} ilyen rendelésből {n_claim}). Hogy ez a szám mennyire hihető, "
                 "azt a harmadik kártya mutatja.")
m[1].metric("Hányszor az átlag", f"{nv.fmt_num(det['relativ_kockazat'], 1)}×", border=True,
            help=f"Egy átlagos rendelés becsült kockázata ebben az időszakban {nv.fmt_pct(avg)}. "
                 f"Ennek a rendelésnek a becslése ennél {nv.fmt_num(det['relativ_kockazat'], 1)}-szer "
                 "nagyobb (ha 1 alatti, akkor kisebb).")
# Természetes gyakoriság — de nem a modell állításáé, hanem a hasonló becslésűek tényleges
# kimenetéé: a modell valószínűsége a farokban nem kalibrált (lásd A modell oldal sávtábláját).
where = nv.RECORD_WHERE[rec["ablak"]].lower()
if rec["rendelesek"]:
    n_obs, base = nv.natural_frequency(rec["tenyleges_arany"])
    m[2].metric("Hasonló becslésűekből késett", f"{nv.per_base(base)} {n_obs}", border=True,
                help=f"Ennyi késett ténylegesen {where} azok közül a rendelések közül, amelyekre a "
                     f"modell szintén {rec['sav_szoveg']} kockázatot becsült: "
                     f"{nv.fmt_num(rec['rendelesek'], 0)} rendelésből {nv.fmt_num(rec['kesett'], 0)} "
                     f"({nv.fmt_pct(rec['tenyleges_arany'])}; a valószínű tartomány "
                     f"{nv.fmt_pct(rec['ci_also'])} – {nv.fmt_pct(rec['ci_felso'])}). Ez mutatja, "
                     "mennyire hihető a becsült szám."
                     + (" A rendelés saját kimenete nem számít bele." if rec["onmaga_kihagyva"] else ""))
else:
    m[2].metric("Hasonló becslésűekből késett", "nincs adat", border=True)
if common.show_outcome():
    m[3].metric("Mi történt valójában?", "késett" if det["kesett"] else "időben jött",
                border=True,
                help="Ezt ma már tudjuk, de a rendelés pillanatában még nem lehetett tudni. Egyetlen "
                     "rendelés kimenetéből nem lehet megítélni, jó-e a modell — azt az *A modell* "
                     "oldal mutatja sok rendelésen.")
else:
    m[3].metric("Mi történt valójában?", "rejtve", border=True,
                help="Az oldalsávon bekapcsolható. Rejtett kimenetnél a harmadik kártya az ellenőrző "
                     f"időszakból ({common.window_period('validációs')}) számol — azt egy valódi bevezetéskor már "
                     "ismerni lehetett volna.")

kind_of_note, note = nv.credibility_note(rec)
if kind_of_note == "figyelmeztetes":
    st.warning(note, icon=":material/balance:")
else:
    st.caption(note)

# ------------------------------------------------------------- magyarázat
st.markdown("##### Miért gondolja ezt a modell?")
with st.container(border=True):
    st.markdown(det["narrativa"])
    st.caption("A szöveget a gép rögzített minta alapján írja: minden szám a lenti ábrából jön, "
               "semmit nem talál ki.")

k = st.slider("Hány tényezőt mutassunk?", 3, 12, 8, key="tenyezok_szama",
              help="A tényezők a hatásuk nagysága szerint vannak sorba rendezve.")
st.altair_chart(charts.reasons_chart(det["tenyezok"].head(k), ink=common.ink()), width="stretch")
total = det["tenyezok"]["hatas_pp"].sum()
st.caption(
    f"**Hogyan olvasd?** A modell egy átlagos rendelésnél {nv.fmt_pct(p0)}-ból indul ki. A piros "
    "sávok ehhez hozzáadnak, a kékek levonnak belőle; a szám a sáv végén a hatás százalékpontban "
    f"(**pp**; 1 százalékpont = 1%-nyi esély). Az összes tényező hatása együtt {nv.fmt_pp(total, 1)} "
    f"százalékpont, így jön ki a {nv.fmt_pct(p)} becslés. A tényezők jelentését lent, a „Mind a 21 "
    "tényező” részben találod.")

with st.expander("Mind a 21 tényező — értékkel, hatással és magyarázattal"):
    rows = ["| tényező | értéke ennél a rendelésnél | hatás (százalékpont) | mit jelent |",
            "|---|---|---|---|"]
    for r in det["tenyezok"].itertuples():
        rows.append(f"| {r.nev} | {r.ertek} | {nv.fmt_pp(r.hatas_pp, 2)} | {r.leiras} |")
    st.markdown("\n".join(rows))
    st.caption("Pozitív hatás: növeli a kockázatot; negatív: csökkenti. A tényezők a hatásuk "
               "nagysága szerint vannak sorba rendezve.")

with common.details("Szakmai részletek a magyarázatról"):
    gap = det["additivitasi_elteres_pp"]
    gap_text = "< 0,000001 pp" if gap < 1e-6 else f"{nv.fmt_num(gap, 6)} pp"
    st.markdown(
        f"- A tényezők SHAP-értékek: a lezárt LightGBM saját, pontos TreeSHAP-felbontása "
        f"(`pred_contrib`) log-odds térben, százalékpontra arányosan átváltva. Kiindulópont "
        f"{nv.fmt_pct(p0)} + a tényezők összege {nv.fmt_pp(total, 2)} pp = {nv.fmt_pct(p)} "
        f"(eltérés: {gap_text}).\n"
        "- A kiindulópont a modell átlaga a tanulási időszakon, log-odds térben átlagolva — ezért "
        "kisebb a tényleges 5–6%-os aránynál.\n"
        "- A hónap két kódoló oszlopa (szinusz, koszinusz) egy tényezőként szerepel (a két hatás "
        "összege), így 22 jellemzőből 21 tényező lesz.\n"
        "- Az arányos átváltás eltérését a valószínűség-tér Shapley-értékeitől a KernelSHAP-"
        "kontrollkar méri (*A modell* oldal).")

# ------------------------------------------------------ határidő-görbe
st.markdown("##### Mi lenne, ha más határidőt vállalnánk?")
st.caption("A platform a rendeléskor megígér egy kézbesítési napot. A tényezők közül ez az egyetlen, "
           "amelyről a cég maga dönt. Az ábra azt mutatja, mit becsülne a modell **ugyanerre a "
           "rendelésre**, ha az ígért szállítási idő más lenne — minden más adat változatlan.")
four = st.toggle("Mind a négy módszer görbéje", key="hatarido_negy",
                 help="Alapból a fő modellé (LightGBM). Bekapcsolva a három másik módszeré is.")
dd = d.deadline(b, key, all_models=four)
sm, rng = dd["osszegzes"], dd["tartomany"]
st.altair_chart(charts.deadline_chart(dd["gorbe"], rng, ink=common.ink()), width="stretch")
if sm["nap"] is not None:
    parts = [f"Most **{sm['nap']} nap** van vállalva: a fő modell becslése {nv.fmt_pct(sm['most'])}."]
    if sm["hosszabb"] is not None:
        parts.append(f"{sm['hosszabb_nap']} nap vállalásával {nv.fmt_pct(sm['hosszabb'])} lenne")
        parts[-1] += (f", {sm['rovidebb_nap']} nappal {nv.fmt_pct(sm['rovidebb'])}." if sm["rovidebb"] is not None
                      else ".")
    st.markdown(" ".join(parts))
    if not sm["tanitoban_elofordult"]:
        st.warning(
            f"Ennél a rendelésnél a vállalt idő ({sm['nap']} nap) "
            + ("rövidebb" if sm["nap"] < rng["min"] else "hosszabb")
            + f", mint a tanulási időszak bármelyik rendelésénél (ott {nv.fmt_num(rng['min'], 0)} és "
            f"{nv.fmt_num(rng['max'], 0)} nap között volt). Ilyet a modell nem látott, ezért a becslés itt "
            "különösen bizonytalan."
            + (f" A teszt-időszak rendeléseinek {nv.fmt_pct(dd['teszt_kivul'], 1)}-ánál rövidebb a vállalt idő "
               "a tanulási időszak legrövidebbjénél: a platform 2018 nyarán rövidebb határidőket is vállalt."
               if sm["nap"] < rng["min"] else ""), icon=":material/warning:")
    elif not sm["tanult_savban"]:
        st.caption(f"A {sm['nap']} napos vállalás a tanulási időszakban ritka volt (a rendelések 1%-ánál is "
                   "ritkább): a becslés itt bizonytalanabb.")
st.caption(
    "**Hogyan olvasd — és mire vigyázz?** (1) Ez a *modell* viselkedése, nem ígéret arra, mi "
    "történne a valóságban, ha a platform mást vállalna. (2) A késést az ígért naphoz mérjük: hosszabb "
    "ígéretnél ugyanaz a szállítás ritkábban számít késésnek. A görbe esése ezt is tartalmazza, nem azt, "
    "hogy a csomag gyorsabban érne oda. (3) A szürke sávban a modell keveset vagy semmit nem tanult: a "
    f"tanulási időszakban a vállalt idő {nv.fmt_num(rng['min'], 0)} és {nv.fmt_num(rng['max'], 0)} nap "
    f"között volt, a rendelések 98%-ánál {nv.fmt_num(rng['also'], 0)} és {nv.fmt_num(rng['felso'], 0)} "
    "nap között.")
with common.details("Szakmai részletek a határidő-görbéről"):
    st.markdown(
        "- Egyetlen jellemző változik (`vallalt_ido_nap` = a vállalt határidő napja − a rendelés napja), "
        "1 és 60 nap között; a többi — az ünnep közelsége és a hónap is, amelyek a rendelés napjából "
        "jönnek — változatlan. A pont a rendelés saját értéke: ott a görbe pontosan a fenti becslés.\n"
        "- A szürke sávon kívül sem oksági a görbe: egy jellemző „elmozdítása” olyan rendelést is "
        "előállíthat, amilyen a valóságban ritka (például távoli államba nagyon rövid ígéret).\n"
        "- A tanult tartományon kívül a fa-alapú modellek (LightGBM, döntési fa, random forest) laposak — "
        "a legszélső tanult értéket viszik tovább —, a logisztikus regresszió egyenesen folytatja a "
        "vonalat. Egyik sem megbízható ott.\n"
        "- Az ellenpéldás magyarázatok (például a DiCE) helyett azért ez a görbe, mert a többi tényezőt "
        "(állam, kategória, távolság, hónap) a döntéshozó nem tudja megváltoztatni; egyetlen jellemzőre "
        "szűkítve az ellenpélda ugyanezt a görbét adná, csak véletlen kereséssel.")

# --------------------------------------------------------- négy modell
st.markdown("##### Mit mondana ugyanerről a rendelésről három másik módszer?")
st.caption("Ugyanebből az adatból négy különböző módszert tanítottunk be. Ha hasonló tényezőket "
           "tartanak fontosnak, a magyarázat megbízhatóbb; ha nem, óvatosan kell kezelni — "
           "ugyanazt az adatot többféleképpen is jól lehet magyarázni.")
st.markdown("\n".join(f"- **{NAMES[k]}:** {labels.MODEL_PLAIN[k]}" for k in KINDS))
ag = d.agreement(det)
shown = ag.assign(
    becsles=[nv.fmt_pct(v) for v in ag["becsles"]],
    kiindulopont=[nv.fmt_pct(v) for v in ag["kiindulopont"]])
st.dataframe(shown[["modell", "becsles", "legerosebb_tenyezok", "kozos_a_lightgbm_mel"]],
             hide_index=True, column_config={
                 "modell": "módszer",
                 "becsles": "becsült kockázat",
                 "legerosebb_tenyezok": st.column_config.TextColumn(
                     "a 3 legerősebb tényező (▲ növeli, ▼ csökkenti)", width="large"),
                 "kozos_a_lightgbm_mel": st.column_config.TextColumn(
                     "közös a fő modellel",
                     help="A három legerősebb tényezőből hány egyezik a LightGBM (a fő modell) "
                          "három legerősebb tényezőjével."),
             })
st.altair_chart(charts.comparison_heatmap(d.model_comparison(det), [r for r in ag["modell"]]),
                width="stretch")
st.caption("**Hogyan olvasd?** Minden sor egy tényező, minden oszlop egy módszer; a cellában a "
           "tényező hatása százalékpontban. Piros: növeli a kockázatot, kék: csökkenti; minél "
           "sötétebb, annál erősebb. Ha egy sor mindenhol azonos színű, abban a módszerek egyetértenek.")
with common.details("Szakmai részletek a négy módszerről"):
    st.dataframe(shown[["modell", "becsles", "kiindulopont", "magyarazo_ter"]], hide_index=True,
                 column_config={"modell": "modell", "becsles": "becslés",
                                "kiindulopont": "kiindulópont", "magyarazo_ter": "a magyarázat tere"})
    st.markdown("A LightGBM és a logisztikus regresszió magyarázata log-odds térben pontos, "
                "százalékpontra arányosan átváltva; a döntési fáé és a random foresté közvetlenül "
                "valószínűség-térben (TreeSHAP, path-dependent) — a kiindulópontok ezért is eltérnek.")
