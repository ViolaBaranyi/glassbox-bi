"""A modell — mennyire jó, mennyire megbízható, és mi számít neki."""

import streamlit as st

from pipeline.features import BOOLEAN_FEATURES, CATEGORICAL_FEATURES
from ui import backend as d
from ui import charts, common
from xai import narrative as nv
from xai.models import KINDS, NAMES

common.page_header(
    "A modell",
    "Mennyire jó, mennyire megbízható a valószínűsége, és mi számít neki? A lezárt "
    "kiértékelés eredményei és a magyarázatok összegzése.")
common.require_warehouse()
res = common.locked()
chk = common.integrity()

# ------------------------------------------------------------- ellenőrzés
if chk["statusz"] == "egyezik":
    st.success("**A felület modelljei pontosan a lezárt futások modelljei:** ugyanaz az adat "
               "(a forrásfájlok ujjlenyomata egyezik), és mind a négy modell teszt PR-AUC-je "
               "egyezik a lezárt értékkel.", icon=":material/verified:")
elif chk["statusz"] == "elter":
    st.warning("**A felület modelljei eltérnek a lezárt futásoktól** — más adatból vagy más "
               "kódból tanultak. A lenti lezárt eredmények nem ezekre a modellekre vonatkoznak.",
               icon=":material/warning:")
elif chk["statusz"] == "szintetikus":
    st.info("Szintetikus adaton fut: a lenti lezárt eredmények a valós Olist-adatra vonatkoznak, "
            "a felület modelljei ezekkel nem vethetők össze.", icon=":material/science:")
else:
    st.info("Még nincs lezárt eredmény a docs/ mappában.")
if chk.get("modellek") is not None:
    with st.expander("Az ellenőrzés részletei"):
        st.dataframe(chk["modellek"], hide_index=True, column_config={
            "most": st.column_config.NumberColumn("PR-AUC most", format="%.5f"),
            "lezart": st.column_config.NumberColumn("PR-AUC lezárt", format="%.5f"),
            "egyezik": st.column_config.CheckboxColumn("egyezik")})
        st.caption(f"Forrásfájlok ujjlenyomata egyezik: {'igen' if chk['forrasok_egyeznek'] else 'NEM'}.")

# ---------------------------------------------------------------- jóság
st.subheader("Mennyire jó? — a lezárt teszt-kiértékelés (2018. jún.–aug.)")
tab = d.results_table(res)
if tab is None:
    st.info("A referencia-összevetés eredménye még nincs meg (docs/v3_referencia_eredmeny.json).")
else:
    base_rate = float(res["referencia"]["teszt_bazisrata"])
    st.altair_chart(charts.pr_auc_forest(tab, base_rate, ink=common.ink()), width="stretch")
    show = tab[["modell", "beallitas"]].copy()
    for metric, label, digits in [("pr_auc", "PR-AUC", 3), ("roc_auc", "ROC-AUC", 3),
                                  ("brier", "Brier", 4), ("ece", "ECE", 4)]:
        show[label] = [f"{nv.fmt_num(v, digits)} [{nv.fmt_num(a, digits)}; {nv.fmt_num(b, digits)}]"
                       for v, a, b in zip(tab[metric], tab[f"{metric}_also"], tab[f"{metric}_felso"])]
    st.dataframe(show, hide_index=True, column_config={"modell": "modell", "beallitas": "beállítás"})
    st.caption(
        f"Pont és 95%-os intervallum (heti blokk-bootstrap, 2000 húzás). **PR-AUC:** ha a modell "
        f"kockázat szerint sorba rendezi a rendeléseket, mennyire kerülnek előre a valóban késők; "
        f"egy találomra rangsoroló modell értéke a késési arány ({nv.fmt_pct(base_rate)}). "
        f"**ROC-AUC:** egy késő és egy időben érkező rendelés közül milyen eséllyel ad a későnek "
        f"nagyobb kockázatot (0,5 = véletlen). **Brier, ECE:** a valószínűségek hibája, ill. "
        f"kalibrálatlansága — a kisebb a jobb.")
    pair = d.paired_table(res)
    if pair is not None and len(pair):
        with st.expander("Páros összevetés: LightGBM − referencia, ugyanazokon a heteken"):
            ps = pair.copy()
            ps["különbség [95% CI]"] = [f"{nv.fmt_num(v, 4)} [{nv.fmt_num(a, 4)}; {nv.fmt_num(b, 4)}]"
                                        for v, a, b in zip(ps["kulonbseg"], ps["also"], ps["felso"])]
            ps["mutato"] = ps["mutato"].map({"pr_auc": "PR-AUC", "roc_auc": "ROC-AUC", "brier": "Brier"})
            st.dataframe(ps[["referencia", "mutato", "különbség [95% CI]", "itelet"]], hide_index=True,
                         column_config={"referencia": "referencia", "mutato": "mutató",
                                        "itelet": "ítélet"})
            st.caption("„Nem kimutatható”: a 95%-os intervallum tartalmazza a 0-t. Korrekció nélküli "
                       "intervallumok (3 összevetés × 3 mutató) — a határeseteket óvatosan kell olvasni.")

# ------------------------------------------------------------ kalibráció
st.subheader("Megbízható-e a valószínűség? — kalibráció")
kind = st.segmented_control("Modell", list(KINDS), default="lightgbm", format_func=NAMES.get,
                            key="kal_modell", required=True)
cal = common.calibration(kind)
st.altair_chart(charts.reliability_chart(cal, ink=common.ink()), width="stretch")
st.caption("Minden pont a teszt-rendelések egy tizede (a becslés szerint sorba rendezve, "
           f"tizedenként kb. {nv.fmt_num(cal['rendelesek'].median(), 0)} rendelés). Ha a pont az "
           "átlón van, a modell annyit mond, amennyi a valóság: a 10%-os becslésű rendelések "
           "10%-a késik. Az átló fölött alábecsül, alatta túlbecsül. A függőleges vonal a tényleges "
           f"arány 95%-os intervalluma. A legfelső tized széles ({cal['sav'].iloc[-1]}): az átlaga "
           "elfedi, mi történik a legmagasabb becsléseknél — ezt mutatja a lenti táblázat.")

st.markdown("##### Becslési sávok: amit a modell mond, és ami történt")
bt, bv = common.bands(kind, "test"), common.bands(kind, "valid")


def _said_vs_happened(r) -> str:
    if r.rendelesek == 0:
        return "—"
    return (f"{nv.fmt_pct(r.atlag_becsles)} → {nv.fmt_pct(r.tenyleges_arany)} "
            f"({nv.fmt_num(100 * r.ci_also, 1)}–{nv.fmt_pct(r.ci_felso)})")


for col, title, tb in zip(st.columns(2), ("Teszt-időszak (utólag)", "Validációs időszak (a teszt előtt)"),
                          (bt, bv)):
    col.markdown(f"**{title}**")
    col.dataframe({"sáv": list(tb["sav"]), "rendelések": list(tb["rendelesek"]),
                   "becsült → tényleges (95% CI)": [_said_vs_happened(r) for r in tb.itertuples()],
                   "ítélet": list(tb["itelet"])}, hide_index=True)
rate_t = bt["kesett"].sum() / max(1, bt["rendelesek"].sum())
rate_v = bv["kesett"].sum() / max(1, bv["rendelesek"].sum())
st.caption(
    "Rögzített sávok a becslés szerint; minden sorban a sáv rendeléseinek átlagos becslése és "
    "tényleges késési aránya. **Ítélet:** túlbecsült vagy alábecsült, ha az átlagos becslés a "
    f"tényleges arány 95%-os intervallumán kívül esik ({d.MIN_BAND_N}-nál kevesebb rendelésnél "
    f"nem ítélünk). A késési arány a teszt-időszakban {nv.fmt_pct(rate_t)}, a validációs "
    f"időszakban (a teszt előtti három hónapban) {nv.fmt_pct(rate_v)} volt: ugyanaz a becslés más "
    "időszakban mást jelenthet, mert a modell valószínűsége nem követi a késési arány változását. "
    "A sorrend (melyik rendelés kockázatosabb) átvihetőbb, mint a pontos szám — ezért a Rendelés "
    "kockázata oldal a becslés mellett a hasonló becslésűek tényleges kimenetét is mutatja.")

# -------------------------------------------------- globális magyarázat
st.subheader("Mi számít a modelleknek? — a magyarázatok összegzése")
with_rf = st.toggle("A random forest is (lassú: első alkalommal kb. fél perc)", key="rf_globalis")
kinds = tuple(k for k in KINDS if with_rf or k != "random_forest")
sample, expl = common.sample_explanations(kinds)
gi = d.global_importance_table(expl)
st.altair_chart(charts.importance_heatmap(gi, [NAMES[k] for k in kinds]), width="stretch")
st.caption(f"Átlagos abszolút hatás százalékpontban, {nv.fmt_num(len(sample), 0)} véletlen "
           f"teszt-rendelésen (a random forestnél {d.SLOW_N}-on). A sorrend a LightGBM rangsora. "
           "Ha a modellek rangsora eltér, ugyanaz az adat többféleképpen is magyarázható — a "
           "magyarázatok stabilitását a kutatás külön méri.")

st.markdown("##### Ugyanazzal a magyarázóval — KernelSHAP-kontrollkar")
kres = d.kernel_arm_results()
if kres is None:
    st.info("A kontrollkar eredménye még nincs meg. Futtatás: `python -m xai.kernel_arm` "
            "(200 rendelés, kb. 20–40 perc; a random forest a lassú).", icon=":material/science:")
else:
    ks = kres["beallitas"]
    st.caption(
        "A fenti összegzés modellenként a saját, pontos magyarázót használja — más-más térben "
        "(a LightGBM és a logisztikus regresszió log-odds, a fa és az erdő valószínűség-térben). "
        "Ha a modellek magyarázata eltér, abban a magyarázó típusa is benne lehet. A kontrollkar "
        f"mind a négy modellt ugyanazzal bontja: KernelSHAP, valószínűség-tér, közös háttér "
        f"({ks['hatter']} tanító rendelés), {ks['rendelesek']} rögzített teszt-rendelésen. "
        "**RBO** (p = 0,9): mennyire egyezik a tényezők fontossági sorrendje, a rangsor elejét "
        "súlyozva (1 = azonos); **top-3**: a három legfontosabb tényezőből átlagosan hány közös.")
    st.dataframe(d.kernel_pairs_table(kres), hide_index=True, column_config={
        "modellpar": "modellpár",
        "rbo_kar": "RBO a karon [95% CI]",
        "rbo_sajat": "RBO a saját magyarázókkal [95% CI]",
        "top3_kar": "közös top-3 (kar)",
        "top3_sajat": "közös top-3 (saját)"})
    st.dataframe(d.kernel_checks_table(kres), hide_index=True, column_config={
        "modell": "modell",
        "zaj_mag_rbo": "a kar zaja: más mag (RBO)",
        "zaj_hatter_rbo": "a kar zaja: más háttér (RBO)",
        "felulet_rbo": "a felület magyarázata vs a kar (RBO)",
        "felulet_top3": "közös top-3",
        "felulet_elojel3": "azonos irány (top-3)"})
    st.caption(
        "Az első két oszlop a mérés saját zaja: ugyanaz a modell, ugyanazok a rendelések, csak más "
        "véletlen mintavétel, ill. más háttér. Ha két modell egyezése ennél nem rosszabb, a "
        "különbség nem a modellekből jön. A második táblázat utolsó három oszlopa azt mutatja, "
        "mennyire követi a felületen látható magyarázat (saját magyarázó + százalékpontra "
        "átváltás) a valószínűség-tér interventional Shapley-értékeit. Részletek: "
        "`docs/kernel_kar_eredmeny.md`.")

st.subheader("Hogyan hat egy tényező? — LightGBM")
feats = list(nv.DISPLAY_FEATURES)
key = st.selectbox("Tényező", feats, index=feats.index("vallalt_ido_nap"),
                   format_func=nv.display_name, key="fuggoseg")
dep = d.dependence(sample, expl["lightgbm"], key)
order = None
if key == nv.MONTH:
    dep["ertek"] = [nv.MONTHS[int(v) - 1] for v in dep["ertek"]]
    order = nv.MONTHS
elif key == "het_napja":
    dep["ertek"] = [nv.DAYS[int(v)] for v in dep["ertek"]]
    order = nv.DAYS
elif key in BOOLEAN_FEATURES:
    dep["ertek"] = ["igen" if bool(v) else "nem" for v in dep["ertek"]]
categorical = order is not None or key in CATEGORICAL_FEATURES or key in BOOLEAN_FEATURES
st.altair_chart(charts.dependence_chart(dep, nv.display_name(key), categorical, order=order,
                                        ink=common.ink()), width="stretch")
st.caption(f"{nv.display_info(key).capitalize()}. Minden pont (doboz) a mintabeli rendelések "
           "hatása: a 0 fölött növeli a becsült kockázatot, alatta csökkenti. A szórás a többi "
           "tényezővel való kölcsönhatásból jön.")

# ----------------------------------------------------------------- eredet
st.subheader("Eredet")
prov = d.provenance(res)
if prov:
    st.dataframe(prov, hide_index=True, column_config={
        "futas": "futás", "protokoll_sha256": "protokoll (SHA-256)", "jovahagyta": "jóváhagyta",
        "git": "commit", "idopont_utc": "időpont (UTC)", "gep": "gép",
        "tiszta_munkapeldany": st.column_config.CheckboxColumn("tiszta munkapéldány")})
    st.caption("A teljes eredmény és a protokoll: docs/v3_lezart_eredmeny.md, "
               "docs/v3_referencia_eredmeny.md, docs/v3_protokoll.md, docs/dontesi_naplo.md.")
info = common.bundle().info
st.caption(f"A felület modelljei: LightGBM {info['lightgbm_fak']} fa; logisztikus regresszió "
           f"C = {info['referencia']['logreg']}; döntési fa mélység {info['referencia']['dontesi_fa']}; "
           f"random forest levélméret {info['referencia']['random_forest']} — mind a címke-tisztított "
           f"tanító ablakon ({nv.fmt_num(info['tanito_sorok'], 0)} rendelés), mag {info['mag']}.")
