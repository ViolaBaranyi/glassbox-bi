"""Kérdezz — kérdések a rendelésekről, ellenőrzött számokkal: szabad szöveggel (nyelvi modell,
két kapu) vagy a kérdésépítővel (KAPU ①). A számokat mindkét úton az adatbázis adja."""

import json
from datetime import date

import streamlit as st

from semantic.catalog import value_label
from ui import backend as d
from ui import bemutato, charts, common
from xai import narrative as nv

common.page_header("Kérdezz", "Kérdések a rendelésekről és a késésekről — minden szám az adatbázisból, "
                              "ellenőrzött úton.")
common.require_warehouse()
cat = common.semantic_catalog()
wl = common.semantic_whitelist()

K_METRIC, K_DIM, K_RANGE, K_ORDER, K_LIMIT = ("kerdezz_metrika", "kerdezz_bontas", "kerdezz_idoszak",
                                              "kerdezz_rendezes", "kerdezz_limit")
K_GATE = "kerdezz_kapu_json"
K_FREE, K_FREE_ASKED = "kerdezz_szabad", "kerdezz_szabad_kerdes"
K_DEMO, K_DEMO_Q = "kerdezz_bemutato", "kerdezz_bemutato_kerdes"
TIME_LIKE = ("honap", "ev", "het_napja")
ORDER_NAMES = {"ertek_csokkeno": "a legnagyobb elöl", "ertek_novekvo": "a legkisebb elöl",
               "bontas": "a bontás sorrendjében"}
EXAMPLES = [
    ("Melyik államban késnek a legtöbbet?", {"metrika": "kesesi_arany", "bontas": "vevo_allam", "limit": 5}),
    ("Hogyan alakult a késési arány havonta?", {"metrika": "kesesi_arany", "bontas": "honap"}),
    ("Mennyi ideig tart a szállítás kategóriánként?",
     {"metrika": "atlagos_szallitasi_ido", "bontas": "kategoria", "limit": 5}),
    ("Mennyit késnek a késett rendelések régiónként?", {"metrika": "atlagos_keses", "bontas": "vevo_regio"}),
    ("Mekkora volt a forgalom évente?", {"metrika": "forgalom", "bontas": "ev"}),
    ("Számít-e, a hét melyik napján rendelnek?", {"metrika": "kesesi_arany", "bontas": "het_napja"}),
]
FREE_EXAMPLES = [
    "Melyik régióban késnek a legtöbbet?",
    "Mennyi volt az átlagos szállítási idő São Paulóban 2018 első felében?",
    "Melyik öt kategóriában a leglassabb a szállítás?",
    "Melyik eladónak a legmagasabb a haszonkulcsa?",
]
GATE_TRIES = [   # (gomb, súgó, a próba gépi alakja)
    ("nem létező mérőszám", "haszonkulcs eladónként — az adatban nincs beszerzési ár",
     {"metrika": "haszonkulcs", "bontas": ["elado_allam"]}),
    ("elírt állam", "„Sao Pablo” — a kapu nem talál ilyet, de javasol",
     {"metrika": "kesesi_arany", "szuro": {"vevo_allam": ["Sao Pablo"]}}),
    ("adaton kívüli időszak", "2019-től — az adat korábban véget ér",
     {"metrika": "kesesi_arany", "idoablak": {"tol": "2019-01-01"}}),
    ("értelmetlen bontás", "a késési arány aszerint bontva, hogy késett-e (mindig 0% vagy 100%)",
     {"metrika": "kesesi_arany", "bontas": ["kesett"]}),
]


def k_filter(dim_id: str) -> str:
    return f"kerdezz_szuro_{dim_id}"


filter_dims = [dim for dim in cat.dimensions.values() if dim.szurheto]


def default_order(dim_id: str) -> str:
    return "bontas" if dim_id in TIME_LIKE else "ertek_csokkeno"


def apply_example(spec: dict) -> None:
    st.session_state[K_METRIC] = spec["metrika"]
    st.session_state[K_DIM] = spec.get("bontas", "")
    for dim in filter_dims:
        st.session_state[k_filter(dim.id)] = []
    st.session_state[K_RANGE] = (wl.date_min, wl.date_max)
    st.session_state[K_ORDER] = default_order(spec.get("bontas", ""))
    st.session_state[K_LIMIT] = spec.get("limit", cat.settings["alap_limit"])


def adopt_spec(spec: dict) -> None:
    """A nyelvi modell értelmezését átveszi a kérdésépítőbe (ott tovább lehet állítani)."""
    dims = spec.get("bontas") or []
    apply_example({"metrika": spec["metrika"], "bontas": dims[0] if dims else "",
                   "limit": spec.get("limit", cat.settings["alap_limit"])})
    for dim_id, values in (spec.get("szuro") or {}).items():
        st.session_state[k_filter(dim_id)] = list(values)
    window = spec.get("idoablak") or {}
    if window:
        st.session_state[K_RANGE] = (date.fromisoformat(window.get("tol", wl.date_min.isoformat())),
                                     date.fromisoformat(window.get("ig", wl.date_max.isoformat())))
    if dims:
        st.session_state[K_ORDER] = spec.get("rendezes", default_order(dims[0]))


def ask_free_example(question: str) -> None:
    st.session_state[K_FREE] = question
    st.session_state[K_FREE_ASKED] = question


def dim_changed() -> None:
    st.session_state[K_ORDER] = default_order(st.session_state.get(K_DIM) or "")


def time_parts(times: list[dict]) -> str:
    """„ (betöltés 0,1 + prompt 18,2 + generálás 5,0 mp)” — ha a szolgáltató megadja."""
    total: dict[str, int] = {}
    for t in times:
        for k, v in (t or {}).items():
            total[k] = total.get(k, 0) + v
    names = (("betoltes_ms", "betöltés"), ("prompt_ms", "beolvasás"), ("generalas_ms", "generálás"))
    parts = [f"{name} {nv.fmt_num(total[k] / 1000, 1)}" for k, name in names if k in total]
    return f" (ebből {' + '.join(parts)} mp)" if parts else ""


# ------------------------------------------------------- a válasz megjelenítése
def show_answer(text: str, caption: str, result) -> None:
    """A válasz szövege a kapuk ítéletével, alatta az ábra és a táblázat."""
    with st.container(border=True):
        st.markdown(f"**Válasz.** {text}")
        st.caption(caption)
    chart = charts.answer_chart(result, common.ink())
    if chart is not None:
        st.altair_chart(chart, width="stretch")
        rate = result.metrika["egyseg"] == "arany"
        st.caption("**Hogyan olvasd?** "
                   + ("A vékony vonal (illetve a halvány sáv) a 95%-os tartomány: a valódi érték nagy "
                      "valószínűséggel ezen belül van. " if rate else "")
                   + ("A szaggatott vonal az egész szűrt kör értéke. "
                      if not result.metrika.get("osszeadhato") and result.bontas["id"] != "honap" else "")
                   + "Az ábrán csak az elég rendelésből számolt csoportok szerepelnek; a többit a "
                     "táblázat mutatja, „kevés adat” jelöléssel.")
    if result.sorok:
        st.dataframe(d.answer_table(result), hide_index=True, width="stretch", column_config={
            "megnevezes": st.column_config.TextColumn(result.bontas["rovid"], width="large"),
            "ertek": st.column_config.TextColumn(result.metrika["nev"]),
            "rendelesek": st.column_config.NumberColumn("rendelések", format="localized"),
            "alap": st.column_config.NumberColumn(f"ebből {result.metrika['alap_nev']}", format="localized"),
            "tartomany": st.column_config.TextColumn("95%-os tartomány"),
            "viszony": st.column_config.TextColumn(
                "részesedés" if result.metrika.get("osszeadhato") else "az összesítetthez",
                help="Összeadható mérőszámnál (darab, összeg) a csoport részesedése az egészből; egyébként "
                     "hányszorosa az egész szűrt kör értékének."),
            "keves_adat": st.column_config.CheckboxColumn(
                "kevés adat", help=f"{result.metrika['min_csoport']}-nál kevesebb rendelésből számolt érték"),
        })


def show_sql(result, spec) -> None:
    with common.details("Honnan jönnek a számok? — a lefuttatott lekérdezés"):
        st.markdown("Az egész szűrt kör (ebből jön az összesített érték):")
        st.code(result.sql["osszesen"], language="sql")
        if result.sql["bontas"]:
            st.markdown("Csoportonként (ebből jön a bontás):")
            st.code(result.sql["bontas"], language="sql")
        st.caption(f"A két lekérdezés {result.ido_ms:.0f} ms alatt futott le, csak olvasási joggal. "
                   "A számokat a megjelenítés kerekíti (az SQL nem). Adat: "
                   f"{'valódi Olist-rendelések' if wl.source == 'valós' else 'szintetikus próbaadat'}; "
                   f"a metrikakatalógus ujjlenyomata: `{cat.sha256[:12]}…`.")
    with common.details("A kérdés gépi alakja (QuerySpec) és a PostgreSQL-változat"):
        st.markdown("Ezt a gépi alakot ellenőrzi az 1. kapu — a kérdésépítő és a nyelvi modell is "
                    "ilyet állít elő:")
        st.json(spec.to_dict())
        st.markdown("Ugyanez a lekérdezés PostgreSQL-ben (a sqlglot fordítja ugyanabból a szintaxisfából):")
        st.code(result.sql_postgres["bontas"] or result.sql_postgres["osszesen"], language="sql")
        pg = d.pg_check()
        if pg:
            system = pg["postgresql"].split(" (")[0]
            note = (f"**Ellenőrizve** ({pg['futtatva'][:10]}): a valódi adaton {pg['lekerdezesek']} ilyen "
                    f"lekérdezés futott le DuckDB-ben és {system}-ben is; az eredmény "
                    + ("cellára azonos." if pg["elteres"] == 0 else f"{pg['elteres']} cellában eltér.")
                    + " Részletek: `docs/pg_ellenorzes.md`.")
            if pg["katalogus_sha256"] != cat.sha256:
                note += (" A metrikakatalógus azóta változott — az ellenőrzést újra kell futtatni "
                         "(`uv run python -m semantic.pg_ellenorzes`).")
            st.caption(note)


def show_free_answer(fa) -> None:
    s = fa.spec
    if not fa.ok:
        st.error(f"**A kérdésre nem adható válasz.** {s.gate.elutasitas.uzenet}", icon=":material/block:")
        why = ("a kérdés olyat kér, amit az adatból nem lehet kiszámolni"
               if s.gate.elutasitas.kod == "nem_elerheto" else
               "a nyelvi modell értelmezéséből nem lett elfogadható kérdés")
        st.caption(f":material/block: **1. kapu: elutasítva** ({s.gate.elutasitas.kod}) — {why}, ezért a "
                   "rendszer nem mond számot.")
    else:
        t = fa.szoveg
        if t.sablon:
            who = "A szöveget a rögzített sablon írta (a nyelvi modellé nem ment át a 2. kapun)" \
                if t.verdict else "A szöveget a rögzített sablon írta"
            gate2 = ""
        else:
            who = (f"A válasz magját a nyelvi modell ({t.modell}) fogalmazta, a hatókört és a korlátot a "
                   "rendszer írta, a számokat a gép illesztette be" if t.keret else
                   f"A szöveget a nyelvi modell ({t.modell}) fogalmazta, a számokat a gép illesztette be")
            gate2 = (f" · **2. kapu: átment** — a szöveg minden száma ({t.verdict.szamok}) "
                     "visszavezethető az eredményre"
                     + (", és minden érték a saját csoportja mellett áll" if fa.eredmeny.bontas else "")
                     + " (a számok közötti viszonyokat, például egy trendet vagy a ki nem írt sorokra tett "
                     "állítást a kapu csak részben ellenőrzi — ezeket a táblázatban nézd meg)")
        show_answer(t.szoveg, f":material/verified: {who}. **1. kapu: elfogadva**{gate2}.", fa.eredmeny)
        if t.sablon and t.verdict:
            st.warning(f"A nyelvi modell szövege nem ment át a 2. kapun ({'; '.join(t.verdict.problemak)}), "
                       "ezért a sablonos válasz látszik.", icon=":material/rule:")
        show_sql(fa.eredmeny, s.gate.spec)
    with common.details("Hogyan értette a nyelvi modell a kérdést? (1. hívás)"):
        st.markdown(f"A modell ({s.modell or 'nem válaszolt'}) a kérdésből ezt az űrlapot töltötte ki"
                    + (" — az első változatát a kapu visszaküldte javításra:" if s.javito_kor else ":"))
        if s.urlap:
            st.json(s.urlap)
        else:
            st.caption("Nincs értelmezhető űrlap." + (f" ({s.hiba})" if s.hiba else ""))
        if s.feloldasok:
            st.markdown("A szűrők írásmódját a rendszer így oldotta fel (a kapu csak az adatban "
                        "ténylegesen előforduló értéket fogad el):\n"
                        + "\n".join(f"- „{n.beirt}” → " + (value_label(cat, n.dimenzio, n.kulcs) if n.kulcs else
                                                            "nem egyértelmű: " + ", ".join(
                                                                value_label(cat, n.dimenzio, k) for k in n.jeloltek[:5]))
                                     for n in s.feloldasok))
        if s.javitasok:
            names = {"idoablak": "időszak", "rendezes": "sorrend", "bontas": "bontás", "elutasitas": "elutasítás"}
            st.markdown("Amit a rendszer a modell űrlapján átírt (ezekben a kód biztosabban dönt):\n"
                        + "\n".join(f"- **{names.get(f.mezo, f.mezo)}**: {f.ok}" for f in s.javitasok))
        st.caption(f"Idő: {nv.fmt_num(s.ido_ms / 1000, 1)} mp{time_parts(s.idok)}"
                   + (f" · prompt: `{s.prompt}`" if s.prompt else "")
                   + (f" · modell-ujjlenyomat: `{s.digest[:12]}`" if s.digest else "")
                   + ". A modell csak a metrikakatalógus kivonatát és a kérdést látta — adatot nem.")
    if fa.ok and fa.szoveg.verdict is not None:
        t = fa.szoveg
        with common.details("Hogyan fogalmazott a nyelvi modell? (2. hívás és 2. kapu)"):
            st.markdown(("A válasz első mondatát (a hatókört) és a végét (a korlátokat) a rendszer írja; "
                         "a modell a közbülső részt fogalmazta. " if t.keret else "")
                        + "A modell szövege — a számok helyén jelölők, ezeket a gép tölti ki:")
            st.code(t.modell_szoveg or "", language=None, wrap_lines=True)
            st.markdown("Ennyit látott a modell az eredményből:")
            st.code(t.nezet, language=None, wrap_lines=True)
            v = t.verdict
            st.caption(f"2. kapu: {v.fedett}/{v.szamok} szám visszavezethető"
                       + (f"; ebből {v.kozvetlen_szamok}-t a modell jelölő helyett maga írt le"
                          if v.kozvetlen_szamok else "")
                       + (f". Problémák: {'; '.join(v.problemak)}" if v.problemak else "")
                       + f". Idő: {nv.fmt_num(t.ido_ms / 1000, 1)} mp{time_parts([t.idok])}"
                       + (f" · prompt: `{t.prompt}`" if t.prompt else "") + ".")
    if fa.ok:
        st.button("Átveszem a kérdésépítőbe", key="kerdezz_atvetel", on_click=adopt_spec,
                  args=(s.gate.spec.to_dict(),), icon=":material/tune:",
                  help="A kérdés a „Kérdésépítő” fülre kerül, ott tovább állíthatod.")


# ------------------------------------------------------------- bevezető
common.intro(
    "Kérdezz **szabad szöveggel** (ehhez helyi nyelvi modell kell), vagy állítsd össze a kérdést a "
    "**kérdésépítővel**: mit mérjünk, milyen bontásban és milyen szűréssel. A számokat mindkét úton "
    "egy ellenőrzött lekérdezés adja, és minden szám mellé ott van, honnan jön.",
    "**Miért lehet megbízni a válaszban?** A kérdésből először egy gépi alak (*kérdés-specifikáció*) "
    "lesz — a kérdésépítő vagy a nyelvi modell állítja elő. Ezt egy ellenőrző — az **1. kapu** — "
    "összeveti a rögzített *metrikakatalógussal* (mit lehet egyáltalán kiszámolni) és az adatból "
    "készült *engedélylistával* (milyen államok, kategóriák, időszakok léteznek). Csak ami átmegy "
    "rajta, abból lesz lekérdezés; amit az adat nem tud (például haszonkulcs), arra a rendszer "
    "megmondja, miért nem, és **nem mond számot**.\n\n"
    "A szöveges választ vagy egy rögzített sablon írja, vagy a nyelvi modell fogalmazza — de a "
    "számokat a modell sem írja le: a helyükre jelölőt tesz, és a gép illeszti be az értékeket. "
    "Utána a **2. kapu** ellenőrzi, hogy a szöveg minden száma visszavezethető-e az eredményre; ha "
    "nem, a sablonos válasz látszik.\n\n"
    "**Amit a kapu nem fog meg mindig:** a számok közötti viszonyokat. A mérések vak kézi ellenőrzése "
    "szerint az alapbeállítású modellel (qwen3.5:4b) a válaszok kb. 9–14%-ában jutott el a "
    "felhasználóhoz olyan állítás, amelyet az eredmény nem támaszt alá — jellemzően helyes számokhoz "
    "kötött hamis viszony (például egy nagyság szerint rendezett listából kiolvasott „csökkenés”, vagy "
    "a ki nem írt sorokra tett állítás). Kapu nélkül a modell szövegeinek 31–48%-ában volt ilyen. A "
    "legkisebb modellel (qwen3.5:2b) az első változatban a válaszok 42%-ában, mert gyakran "
    "félreértette a kérdést. Döntés előtt ezért a táblázatot és az ábrát nézd: azok a lekérdezés "
    "közvetlen eredményei.\n\n"
    "**Kevés adat:** ha egy csoportban kevés rendelés van (aránynál 100-nál, átlagnál 30-nál "
    "kevesebb), az értéke a véletlentől erősen ingadozik — ezért a szöveg és az ábra nem épít "
    "rá, a táblázat jelölve mutatja.")

tab_free, tab_builder = st.tabs([":material/forum: Szabad szöveggel", ":material/tune: Kérdésépítővel"])

def show_demo(meta: dict) -> None:
    recs = {r["id"]: r for r in meta["valaszok"]}
    st.caption("A kérdéseket a szerző írta a harmadik méréshez, a mért kód lezárása után. A nyelvi modell "
               f"válaszát a mérés rögzítette ({bemutato.source_line(meta)}); minden más — az 1. kapu, a "
               "lekérdezés, a számok beillesztése és a 2. kapu — most fut le. A csapdakérdésekre a helyes "
               "válasz az indokolt elutasítás.")
    rid = st.selectbox("Kérdés a mérésből", list(recs), index=None, key=K_DEMO_Q,
                       format_func=lambda i: bemutato.label(recs[i]),
                       placeholder=f"Válassz a {len(recs)} rögzített kérdés közül…")
    if rid:
        free = common.ask_recorded(rid)
        st.info("**Bemutató mód:** a nyelvi modell (" + meta.get("modell", "") + ") szövegét a mérés "
                "rögzítette; az ellenőrzés és a számok most készültek.", icon=":material/replay:")
        st.markdown(f"**A kérdés:** {recs[rid]['kerdes']}")
        show_free_answer(free)


# ------------------------------------------------------ szabad szöveges kérdés
with tab_free:
    llm_ok, llm_msg = common.llm_status()
    recorded = common.recorded()
    if not llm_ok:
        st.info("**A szabad szöveges kérdéshez helyi nyelvi modell kell, és most nem érhető el.** "
                f"{llm_msg}\n\nAddig a **Kérdésépítővel** fülön ugyanígy kérdezhetsz"
                + (", itt pedig a bemutató módban a mérés rögzített válaszait nézheted meg" if recorded["valaszok"]
                   else "") +
                ". A beállítás a `configs/llm.toml`-ban van; a részletek a README-ben („Szabad szöveges "
                "kérdés”).", icon=":material/info:")
    demo = bool(recorded["valaszok"]) and st.toggle(
        "Bemutató mód: a mérés rögzített modellválaszai, azonnal, nyelvi modell nélkül",
        value=not llm_ok, key=K_DEMO,
        help="A nyelvi modell két hívása helyett a harmadik mérés rögzített kimenete jön; az 1. kapu, "
             "a lekérdezés, a számok beillesztése és a 2. kapu most fut le, a mostani kóddal és adattal.")
    if demo:
        show_demo(recorded)
    elif llm_ok:
        common.warm_llm()                    # betöltés a háttérben, amíg a kérdés készül
        st.caption(f"Nyelvi modell: **{llm_msg}**. Egy kérdés a gép teljesítményétől függően néhány "
                   "másodperctől egy percig is tarthat (videókártya nélkül a hosszabb).")
        st.markdown("###### Példák")
        ecols = st.columns(2)
        for i, q in enumerate(FREE_EXAMPLES):
            ecols[i % 2].button(q, key=f"kerdezz_szabad_pelda_{i}", width="stretch",
                                on_click=ask_free_example, args=(q,))
        with st.form("kerdezz_szabad_urlap", border=False):
            st.text_input("A kérdésed", key=K_FREE, max_chars=300,
                          placeholder="pl. Melyik régióban késnek a legtöbbet 2018-ban?")
            if st.form_submit_button("Kérdezem", type="primary", icon=":material/send:"):
                st.session_state[K_FREE_ASKED] = st.session_state.get(K_FREE, "")
        question = (st.session_state.get(K_FREE_ASKED) or "").strip()
        if question:
            with st.spinner("A nyelvi modell értelmezi a kérdést, a rendszer lefuttatja a lekérdezést, "
                            "a modell megfogalmazza a választ…"):
                free = common.ask_free(question)
            st.markdown(f"**A kérdés:** {question}")
            show_free_answer(free)

# ------------------------------------------------------------- kérdésépítő
with tab_builder:
    st.markdown("##### Példakérdések")
    for start in range(0, len(EXAMPLES), 3):       # soronként, hogy telefonon is sorrendben jöjjenek
        for col, (i, (label, spec)) in zip(st.columns(3), enumerate(EXAMPLES[start:start + 3], start)):
            col.button(label, key=f"kerdezz_pelda_{i}", on_click=apply_example, args=(spec,), width="stretch")

    st.markdown("##### A kérdés")
    metric_ids = list(cat.metrics)
    st.session_state.setdefault(K_METRIC, "kesesi_arany")
    c1, c2 = st.columns(2)
    metric_id = c1.selectbox("Mit mérjünk?", metric_ids, key=K_METRIC,
                             format_func=lambda i: cat.metrics[i].nev,
                             help="A metrikakatalógus mérőszámai — csak ezekre tud válaszolni a rendszer.")
    metric = cat.metrics[metric_id]
    c1.caption(metric.leiras)
    dim_options = [""] + [dim.id for dim in cat.dimensions.values() if dim.id not in metric.tiltott_dimenzio]
    if st.session_state.get(K_DIM, "") not in dim_options:
        st.session_state[K_DIM] = ""
    dim_id = c2.selectbox("Milyen bontásban?", dim_options, key=K_DIM, on_change=dim_changed,
                          format_func=lambda i: "nincs bontás (egy szám)" if not i else
                          cat.dimensions[i].rovid.capitalize())

    st.session_state.setdefault(K_RANGE, (wl.date_min, wl.date_max))
    c3, c4, c5 = st.columns([2, 2, 1])
    period = c3.date_input("Időszak (a rendelés leadásának napja)", key=K_RANGE, min_value=wl.date_min,
                           max_value=wl.date_max, format="YYYY.MM.DD")
    time_like = dim_id in TIME_LIKE
    order = limit = None
    if dim_id:
        orders = [o for o in ORDER_NAMES if o != "bontas" or cat.dimensions[dim_id].termeszetes_sorrend]
        if st.session_state.get(K_ORDER) not in orders:
            st.session_state[K_ORDER] = default_order(dim_id)
        order = c4.radio("Sorrend", orders, key=K_ORDER, format_func=ORDER_NAMES.get, horizontal=True)
        if not time_like:
            st.session_state.setdefault(K_LIMIT, cat.settings["alap_limit"])
            limit = c5.number_input("Hány csoport?", min_value=1, max_value=int(cat.settings["max_limit"]),
                                    key=K_LIMIT, help="Ennyi csoportot emel ki a válasz és az ábra; a "
                                                      "táblázat mindet mutatja.")

    allowed_filters = [dim for dim in filter_dims if dim.id not in metric.tiltott_dimenzio]
    active = sum(bool(st.session_state.get(k_filter(dim.id))) for dim in allowed_filters)
    with st.expander(f"Szűrés{f' ({active} aktív)' if active else ' (nem kötelező)'}"):
        fcols = st.columns(3)
        for i, dim in enumerate(allowed_filters):
            options = sorted(wl.values[dim.id], key=lambda k, dd=dim.id: value_label(cat, dd, k).lower()) \
                if dim.id in ("vevo_allam", "elado_allam", "kategoria") else list(wl.values[dim.id])
            fcols[i % 3].multiselect(dim.rovid.capitalize(), options, key=k_filter(dim.id),
                                     format_func=lambda k, dd=dim.id: value_label(cat, dd, k),
                                     placeholder="mind")

    raw: dict = {"metrika": metric_id}
    if dim_id:
        raw["bontas"] = [dim_id]
        raw["rendezes"] = order
        if limit is not None:
            raw["limit"] = int(limit)
    filters = {dim.id: list(st.session_state[k_filter(dim.id)]) for dim in allowed_filters
               if st.session_state.get(k_filter(dim.id))}
    if filters:
        raw["szuro"] = filters
    if isinstance(period, (tuple, list)) and period:
        tol = period[0]
        ig = period[1] if len(period) > 1 else wl.date_max
        if (tol, ig) != (wl.date_min, wl.date_max):
            raw["idoablak"] = {"tol": tol.isoformat(), "ig": ig.isoformat()}

    gate, result, answer = common.ask(raw)
    if not gate.ok:
        st.error(f"**A kérdésre nem adható válasz.** {gate.elutasitas.uzenet}", icon=":material/block:")
    else:
        show_answer(answer.text, ":material/verified: **1. kapu: elfogadva** — a mérőszám, a bontás és a "
                    "szűrők a katalógusban vannak, az értékek ténylegesen előfordulnak az adatban. A szöveg "
                    "minden száma a lekérdezés eredményéből jön (lent: *Honnan jönnek a számok?*).", result)
        show_sql(result, gate.spec)

    with common.details("Próbáld ki az 1. kaput"):
        st.markdown("Írd át a kérdés gépi alakját, és nézd meg, átengedi-e a kapu. Néhány próba:")
        tcols = st.columns(len(GATE_TRIES))
        for i, (label, tip, spec) in enumerate(GATE_TRIES):
            tcols[i].button(label, key=f"kerdezz_kapu_{i}", width="stretch", help=tip,
                            on_click=lambda s=spec: st.session_state.update(
                                {K_GATE: json.dumps(s, ensure_ascii=False, indent=1)}))
        st.session_state.setdefault(K_GATE, json.dumps(raw, ensure_ascii=False, indent=1))
        text = st.text_area("A kérdés gépi alakja (JSON)", key=K_GATE, height=180)
        try_gate = common.ask_gate(text)
        if try_gate.ok:
            st.success("**Elfogadva.** A normalizált alak (ebből épülne a lekérdezés):", icon=":material/check:")
            st.json(try_gate.spec.to_dict())
            if try_gate.megjegyzesek:
                st.caption("Megjegyzés: az időablakot az adat időtartományára szűkítettem.")
        else:
            st.error(f"**Elutasítva** ({try_gate.elutasitas.kod}). {try_gate.elutasitas.uzenet}",
                     icon=":material/block:")
