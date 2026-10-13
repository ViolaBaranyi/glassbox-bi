"""A modell — mennyire jó, mennyire megbízható, és mi számít neki."""

import re

import streamlit as st

from pipeline.features import BOOLEAN_FEATURES, CATEGORICAL_FEATURES
from ui import backend as d
from ui import charts, common
from xai import labels
from xai import narrative as nv
from xai.models import KINDS, NAMES

common.page_header(
    "A modell",
    "Mennyire jó a modell, mennyire lehet hinni a becsült százaléknak, és mire figyel?")
common.require_warehouse()
res = common.locked()
chk = common.integrity()
test_period = common.window_period("teszt")

common.intro(
    "**Mit látsz ezen az oldalon?** A *modell* egy számítógépes módszer, amely a múltbeli "
    "rendelésekből megtanulta, milyen rendelések szoktak késni, és ez alapján minden új "
    "rendelésre megbecsüli a késés esélyét. Itt azt nézzük meg, mennyire jól csinálja: a modellt "
    f"a **teszt-időszak** ({test_period}) rendelésein mértük le, amelyeket tanulás közben sosem "
    "látott. Fent egy rövid összefoglaló, lejjebb a részletek ábrákkal; a legszakmaibb részek a "
    "lenyitható „Szakmai részletek” dobozokban vannak.")


def _setting(text: str) -> str:
    """A lezárt eredmény beállítás-szövege magyarul, tizedesvesszővel: „C = 0.1" → „C = 0,1",
    „max_depth = 10" → „legfeljebb 10 szint mély", „min_samples_leaf = 10" → „levélméret ≥ 10"."""
    text = str(text)
    m = re.fullmatch(r"max_depth = (\d+)", text)
    if m:
        return f"legfeljebb {m.group(1)} szint mély"
    text = text.replace("min_samples_leaf = ", "levélméret ≥ ")
    return re.sub(r"(\d)\.(\d)", r"\1,\2", text)


# ------------------------------------------------------------- ellenőrzés
if chk["statusz"] == "egyezik":
    st.success("**Ellenőrizve:** a felület pontosan azokat a modelleket használja, amelyeket a "
               "hivatalos (lezárt) mérésben kiértékeltünk — ugyanabból az adatból, ugyanazokkal a "
               "beállításokkal, ugyanazzal az eredménnyel.", icon=":material/verified:")
elif chk["statusz"] == "elter":
    st.warning("**Figyelem:** a felület modelljei eltérnek a hivatalosan kiértékelt modellektől "
               "(más adatból vagy más programkódból tanultak). A lenti hivatalos eredmények ezért "
               "nem ezekre a modellekre vonatkoznak.", icon=":material/warning:")
elif chk["statusz"] == "szintetikus":
    st.info("Szintetikus (kitalált) próbaadaton fut: a lenti hivatalos eredmények a valódi "
            "adatra vonatkoznak, a felület modelljei ezekkel nem vethetők össze.",
            icon=":material/science:")
else:
    st.info("Még nincs hivatalos (lezárt) eredmény a docs/ mappában.")

tab = d.results_table(res)
kres = d.kernel_arm_results()
bt_lgbm = common.bands("lightgbm", "test")

# ----------------------------------------------------------------- röviden
st.subheader("Röviden: mennyire lehet megbízni a modellben?")
cap = common.capture(0.10)
bullets = [
    f"**Jól rangsorol.** Ha a modell szerint legkockázatosabb 10% rendelést nézzük "
    f"({nv.fmt_num(cap['felso_rendelesek'], 0)} rendelés), közöttük van az összes késés "
    f"**{nv.fmt_pct(cap['kesesek_aranya_a_felsoben'], 0)}-a** — vaktában választva csak 10% lenne. "
    f"Közülük {nv.fmt_pct(cap['kesesi_arany_felso'])} késett — az összes rendelésnél ez az arány "
    f"{nv.fmt_pct(cap['kesesi_arany'])}."]
if tab is not None:
    roc = float(tab.set_index("kulcs").loc["lightgbm", "roc_auc"])
    bullets.append(
        f"**Megkülönbözteti a későket.** Ha kiveszünk egy késett és egy időben megérkezett "
        f"rendelést, a modell az esetek **{nv.fmt_pct(roc, 0)}-ában** a késettet tartja "
        "kockázatosabbnak (vaktában 50% lenne).")
# A becsült százalék pontossága három tartományban — a lenti sávtáblából összevonva, hogy az
# összefoglaló mondata minden adaton (és minden időszakban) egyezzen a táblázattal.
groups = d.band_groups(bt_lgbm).set_index("csoport")
_VERB = {"összhangban": "a becslés jól egyezik a valósággal",
         "túlbecsült": "a modell többet mond, mint ami történt",
         "alábecsült": "a modell kevesebbet mond, mint ami történt"}


def _said(g) -> str:
    return (f"átlagosan {nv.fmt_pct(g['atlag_becsles'])}-ot mondott, "
            f"{nv.fmt_pct(g['tenyleges_arany'])} késett")


hi_g, mid_g, lo_g = groups.loc["magas"], groups.loc["közepes"], groups.loc["alacsony"]
judged = [g["itelet"] for g in (hi_g, mid_g, lo_g) if g["itelet"] in _VERB]   # 20 rendelés alatt nincs ítélet
all_ok = bool(judged) and set(judged) == {"összhangban"}
parts = []
if hi_g["itelet"] == "túlbecsült" and hi_g["atlag_becsles"] > 1.25 * hi_g["tenyleges_arany"]:
    lead = "**A magas százalékok túlzók.**"
    parts.append(f"Ahol a modell 20%-nál többet mondott ({nv.fmt_num(hi_g['rendelesek'], 0)} "
                 f"rendelés), átlagosan {nv.fmt_pct(hi_g['atlag_becsles'], 0)} kockázatot becsült, "
                 f"de csak {nv.fmt_pct(hi_g['tenyleges_arany'], 0)} késett.")
else:
    lead = "**A becsült százalék hihető.**" if all_ok else "**A becsült százalék nem mindenhol pontos.**"
    if hi_g["itelet"] in _VERB:
        parts.append(f"20% fölött {_VERB[hi_g['itelet']]} ({_said(hi_g)}).")
side = [f"{label} {_VERB[g['itelet']]} ({_said(g)})"
        for label, g in (("5 és 20% között", mid_g), ("5% alatt", lo_g)) if g["itelet"] in _VERB]
if side:
    parts.append("; ".join(side) + ".")
if parts:
    closing = ("A *Rendelés kockázata* oldal minden becslés mellett azt is mutatja, mi történt a "
               "hasonló rendelésekkel." if all_ok else
               "Ezért a *Rendelés kockázata* oldal a becslés mellett azt is mutatja, mi történt a "
               "hasonló rendelésekkel.")
    bullets.append(" ".join([lead, *parts, closing]))
pair = d.paired_table(res)
if pair is not None and len(pair):
    lr = pair[(pair["referencia"] == NAMES["logreg"]) & (pair["mutato"] == "pr_auc")]
    if len(lr):
        if lr["itelet"].iloc[0] == "nem kimutatható":
            bullets.append("**Az egyszerűbb módszer majdnem ugyanolyan jó.** A négy kipróbált módszer "
                           "közül a LightGBM rangsorol a legjobban, de az egyszerű logisztikus "
                           "regresszió alig marad el tőle — a különbség a mérés bizonytalanságán "
                           "belül van.")
        else:
            bullets.append(f"**A LightGBM és a logisztikus regresszió összevetése:** "
                           f"{lr['itelet'].iloc[0]}.")
if kres is not None:
    sign = float(kres["atvaltas"]["lightgbm"]["felulet"]["elojel3"]["atlag"])
    bullets.append(f"**A magyarázatokat ellenőriztük.** Egy független módszerrel (KernelSHAP) is "
                   f"kiszámoltuk őket: a három legfontosabb tényező iránya (növeli vagy csökkenti) "
                   f"az esetek {nv.fmt_pct(sign, 0)}-ában egyezett.")
with st.container(border=True):
    st.markdown("\n".join(f"- {x}" for x in bullets))
    st.caption("Ezek a számok a teszt-időszak rendelésein készültek, amelyeket a modell tanulás "
               "közben nem látott. Egy rendelés kimenetéből nem lehet a modellt megítélni — csak "
               "sok rendelésből.")

# ---------------------------------------------------------------- jóság
st.subheader("Mennyire jó? — négy módszer összevetése")
if tab is None:
    st.info("A négy módszer összevetésének eredménye még nincs meg (docs/v3_referencia_eredmeny.json).")
else:
    base_rate = float(res["referencia"]["teszt_bazisrata"])
    st.caption(
        "Négy módszert tanítottunk be ugyanarra az adatra: "
        + "; ".join(f"**{NAMES[k]}** — {labels.MODEL_PLAIN[k]}" for k in KINDS) + ".")
    st.altair_chart(charts.pr_auc_forest(tab, base_rate, ink=common.ink()), width="stretch")
    st.caption(
        "**Hogyan olvasd?** Minden sor egy módszer. A pont azt mutatja, mennyire jól teszi előre "
        "a valóban késő rendeléseket, ha kockázat szerint sorba rendezi őket (a mérőszám neve "
        "PR-AUC: minél nagyobb, annál jobb). A vízszintes vonal a bizonytalansága: ha két vonal "
        "nagyon átfedi egymást, a két módszer között nincs biztos különbség. A szaggatott vonal a "
        f"vaktában rangsorolás szintje ({nv.fmt_pct(base_rate)}, ennyi a késések aránya); minden "
        "módszer jóval fölötte van.")
    with common.details("Szakmai részletek: minden mérőszám és a páros összevetés"):
        show = tab[["modell", "beallitas"]].copy()
        show["beallitas"] = [_setting(v) for v in show["beallitas"]]
        for metric, label, digits in [("pr_auc", "PR-AUC", 3), ("roc_auc", "ROC-AUC", 3),
                                      ("brier", "Brier", 4), ("ece", "ECE", 4)]:
            show[label] = [f"{nv.fmt_num(v, digits)} [{nv.fmt_num(a, digits)}; {nv.fmt_num(b, digits)}]"
                           for v, a, b in zip(tab[metric], tab[f"{metric}_also"], tab[f"{metric}_felso"])]
        st.dataframe(show, hide_index=True, column_config={"modell": "modell", "beallitas": "beállítás"})
        st.markdown(
            "Pont és 95%-os intervallum (heti blokk-bootstrap, 2000 húzás).\n"
            "- **PR-AUC:** ha a modell kockázat szerint sorba rendezi a rendeléseket, mennyire "
            f"kerülnek előre a valóban késők; egy találomra rangsoroló modell értéke a késési arány "
            f"({nv.fmt_pct(base_rate)}).\n"
            "- **ROC-AUC:** egy késő és egy időben érkező rendelés közül milyen eséllyel ad a "
            "későnek nagyobb kockázatot (0,5 = véletlen).\n"
            "- **Brier-pontszám:** a becsült valószínűségek átlagos négyzetes hibája — a kisebb a jobb.\n"
            "- **ECE:** a becsült és a tényleges arány átlagos eltérése sávonként (kalibrálatlanság) "
            "— a kisebb a jobb.")
        if pair is not None and len(pair):
            ps = pair.copy()
            ps["különbség [95% CI]"] = [f"{nv.fmt_num(v, 4)} [{nv.fmt_num(a, 4)}; {nv.fmt_num(b, 4)}]"
                                        for v, a, b in zip(ps["kulonbseg"], ps["also"], ps["felso"])]
            ps["mutato"] = ps["mutato"].map({"pr_auc": "PR-AUC", "roc_auc": "ROC-AUC", "brier": "Brier"})
            st.markdown("**Páros összevetés: LightGBM − a másik módszer, ugyanazokon a heteken**")
            st.dataframe(ps[["referencia", "mutato", "különbség [95% CI]", "itelet"]], hide_index=True,
                         column_config={"referencia": "a másik módszer", "mutato": "mutató",
                                        "itelet": "ítélet"})
            st.caption("„Nem kimutatható”: a 95%-os intervallum tartalmazza a 0-t. Korrekció nélküli "
                       "intervallumok (3 összevetés × 3 mutató) — a határeseteket óvatosan kell olvasni.")

# ------------------------------------------------------------ kalibráció
st.subheader("Mennyire lehet hinni a becsült százaléknak?")
st.caption("Ha a modell egy csoport rendelésre 10%-ot mond, akkor jó esetben a csoport kb. 10%-a "
           "késik. Ezt hívják *kalibrációnak*. Itt azt nézzük meg, mennyire teljesül.")
kind = st.segmented_control("Melyik módszert nézzük?", list(KINDS), default="lightgbm",
                            format_func=NAMES.get, key="kal_modell", required=True)
cal = common.calibration(kind)
st.altair_chart(charts.reliability_chart(cal, ink=common.ink()), width="stretch")
st.caption(
    "**Hogyan olvasd?** A rendeléseket a becslés szerint tíz egyforma csoportba osztottuk "
    f"(kb. {nv.fmt_num(cal['rendelesek'].median(), 0)} rendelés csoportonként). Minden pont egy "
    "csoport: vízszintesen az, amit a modell átlagosan mondott, függőlegesen az, ami valóban "
    "történt. Ha a pont a szaggatott átlón van, a modell pontos; ha alatta, túloz; ha fölötte, "
    f"alábecsül. A legfelső csoport nagyon széles ({cal['sav'].iloc[-1]}), ezért az átlaga elfedi, "
    "mi történik a legmagasabb becsléseknél — ezt mutatja a lenti táblázat.")

st.markdown("##### Amit a modell mondott, és ami történt — becslési sávonként")
bt, bv = common.bands(kind, "test"), common.bands(kind, "valid")


def _said_vs_happened(r) -> str:
    if r.rendelesek == 0:
        return "—"
    return (f"{nv.fmt_pct(r.atlag_becsles)} → {nv.fmt_pct(r.tenyleges_arany)} "
            f"({nv.fmt_num(100 * r.ci_also, 1)}–{nv.fmt_pct(r.ci_felso)})")


for title, tb in zip((f"Teszt-időszak ({test_period}) — utólag",
                       f"Ellenőrző időszak ({common.window_period('validációs')}) — a teszt előtt"),
                      (bt, bv)):
    st.markdown(f"**{title}**")
    st.dataframe({"becslési sáv": list(tb["sav"]), "rendelések": list(tb["rendelesek"]),
                   "mondott → történt (valószínű tartomány)": [_said_vs_happened(r)
                                                                 for r in tb.itertuples()],
                   "ítélet": list(tb["itelet"])}, hide_index=True)
rate_t = bt["kesett"].sum() / max(1, bt["rendelesek"].sum())
rate_v = bv["kesett"].sum() / max(1, bv["rendelesek"].sum())
st.caption(
    "**Hogyan olvasd?** Minden sor azokat a rendeléseket gyűjti össze, amelyekre a modell az adott "
    "sávba eső kockázatot mondott (pl. 20–30%). A nyíl bal oldalán az átlagos becslés, jobb oldalán "
    "az, hogy valójában hány százalékuk késett; zárójelben a valószínű tartomány. **Ítélet:** "
    "*túlbecsült*, ha a modell többet mondott, mint ami a tartomány teteje; *alábecsült*, ha "
    f"kevesebbet, mint az alja; {d.MIN_BAND_N}-nál kevesebb rendelésnél nem ítélünk. A késési arány "
    f"a teszt-időszakban {nv.fmt_pct(rate_t)}, az ellenőrző időszakban {nv.fmt_pct(rate_v)} volt: "
    "ugyanaz a becslés más időszakban mást jelenthet, mert a modell nem követi, ha a késések "
    "általános szintje megváltozik. A **sorrend** (melyik rendelés kockázatosabb) ezért "
    "megbízhatóbb, mint a pontos százalék.")

# -------------------------------------------------- globális magyarázat
st.subheader("Mire figyelnek a modellek általában?")
with_rf = st.toggle("A random forest is (lassú: első alkalommal kb. fél perc)", key="rf_globalis")
kinds = tuple(k for k in KINDS if with_rf or k != "random_forest")
sample, expl = common.sample_explanations(kinds)
gi = d.global_importance_table(expl)
st.altair_chart(charts.importance_heatmap(gi, [NAMES[k] for k in kinds]), width="stretch")
st.caption(
    f"**Hogyan olvasd?** Minden sor egy tényező, minden oszlop egy módszer. A szám azt mutatja, "
    f"átlagosan hány százalékponttal mozdítja el az adott tényező a becslést "
    f"{nv.fmt_num(len(sample), 0)} véletlenszerűen kiválasztott teszt-rendelésen (a random forestnél "
    f"{d.SLOW_N}-on) — irány nélkül, csak a nagyság. Minél sötétebb, annál fontosabb. A sorrend a "
    "fő modell (LightGBM) szerinti. Ha a módszerek más tényezőket tartanak fontosnak, ugyanazt az "
    "adatot többféleképpen is jól lehet magyarázni.")

st.subheader("Hogyan hat egy-egy tényező? — a fő modellben")
feats = list(nv.DISPLAY_FEATURES)
key = st.selectbox("Melyik tényezőt nézzük?", feats, index=feats.index("vallalt_ido_nap"),
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
elif key in ("vevo_allam", "elado_allam"):
    dep["ertek"] = [labels.state_name(v) for v in dep["ertek"]]
elif key == "kategoria":
    dep["ertek"] = [labels.category_name(v) for v in dep["ertek"]]
categorical = order is not None or key in CATEGORICAL_FEATURES or key in BOOLEAN_FEATURES
if not categorical:
    dep["ertek_szoveg"] = [nv.format_value(key, v) for v in dep["ertek"]]
st.altair_chart(charts.dependence_chart(dep, nv.axis_title(key), categorical, order=order,
                                        ink=common.ink(), percent=nv.is_percent(key)),
                width="stretch")
st.caption(
    f"**{nv.display_name(key).capitalize()}:** {nv.display_info(key)} **Hogyan olvasd?** "
    + ("Minden doboz egy érték; a doboz azt mutatja, hogy az ilyen rendeléseknél mennyivel "
       "mozdította el a becslést ez a tényező." if categorical else
       "Minden pont egy rendelés: vízszintesen a tényező értéke, függőlegesen az, hogy mennyivel "
       "mozdította el a becslést.")
    + " A 0 fölött növeli a kockázatot, alatta csökkenti. Ugyanannál az értéknél is lehet szórás, "
      "mert a hatás a többi adattól is függ.")

# ------------------------------------------------ a magyarázatok hűsége (K2)
st.subheader("Mennyire hűek a magyarázatok a modellhez?")
fres = d.faithfulness_results()
if fres is None:
    st.info("A hűségmérés eredménye még nincs meg. Futtatás: `python -m xai.faithfulness` "
            "(kb. fél–egy óra; a random forest a lassú).", icon=":material/science:")
else:
    tb, pl = fres["torles_beszuras"], fres["beultetett"]
    st.caption(
        "A magyarázat akkor hű, ha tényleg azt mutatja, amire a modell figyel. Ezt két próbával "
        "ellenőriztük. Mindkettő a modell működését vizsgálja, nem azt, hogy mi történt a "
        "valóságban — a rendelések tényleges kimenetét egyik sem használja.")
    st.markdown("##### 1. próba: ha kivesszük a legfontosabb tényezőket, sokat változik-e a becslés?")
    st.caption(
        f"{nv.fmt_num(tb['rendelesek'], 0)} teszt-rendelésnél „kivettük” a felület szerint "
        "legjobban növelő 3 tényezőt — az értéküket a tanulási időszak átlagos rendeléseiből vettük —, "
        "és megnéztük, mennyit esik a becslés. Ha a magyarázat hű, sokkal többet esik, mint 3 "
        "véletlenszerűen választott tényezőnél. A harmadik sáv a legjobb elérhető érték: egy olyan "
        "magyarázaté (KernelSHAP), amelyet pontosan erre a próbára számoltunk ki.")
    st.altair_chart(charts.faith_drop_chart(d.faith_drop_table(fres), [NAMES[k] for k in KINDS],
                                            ink=common.ink()), width="stretch")
    lg = tb["modellek"].get("lightgbm")
    if lg:
        m = lg["mertekek"]
        best = (f"; a legjobb elérhető {nv.fmt_num(m['kernel']['top3_eses']['atlag'], 1)} százalékpont"
                if "kernel" in m else "")
        rnd = m["veletlen"]["top3_eses"]["atlag"]
        rnd_text = ("3 véletlen tényező kivétele viszont gyakorlatilag nem változtatott rajta"
                    if abs(rnd) < 0.05 else
                    f"3 véletlen tényezőé {nv.fmt_num(rnd, 1)} százalékpontot")
        st.caption(
            f"**Hogyan olvasd?** A fő modellnél (LightGBM) a felület szerinti 3 tényező kivétele "
            f"átlagosan {nv.fmt_num(m['felulet']['top3_eses']['atlag'], 1)} százalékponttal "
            f"csökkentette a becslést, {rnd_text}{best}. A rendelések "
            f"{nv.fmt_pct(lg['jobb_mint_veletlen'], 0)}-ában a felület sorrendje jobb volt a véletlennél. "
            "A vékony vonal a bizonytalanság (95%-os tartomány). A véletlen sáv néha negatív: egy "
            "átlagos tényező „kivétele” a tanulási időszak (kicsit magasabb) átlagához húzza a becslést.")
    st.markdown("##### 2. próba: megtalálja-e a magyarázat a beültetett jelet?")
    st.caption(
        "Az adatba két kitalált jellemzőt tettünk. A **jel** a rendelések 20%-ánál bekapcsol, és "
        f"növeli a késés esélyét (a tanulási időszakban {nv.fmt_pct(pl['tanito_keses_jel0'])} helyett "
        f"{nv.fmt_pct(pl['tanito_keses_jel1'])} késett); a **zaj** semmire nem hat. Utána a négy "
        f"módszert újratanítottuk, és megnéztük a magyarázatukat {nv.fmt_num(pl['rendelesek'], 0)} "
        "teszt-rendelésen. A jó magyarázat a jelet a legfontosabbak közé sorolja, a zajt pedig "
        "nullának mutatja.")
    planted_tab = d.faith_planted_table(fres)
    st.dataframe(planted_tab[["modell", "megfelelt", "jel_top3", "jel_irany", "zaj_top3", "zaj_arany",
                              "zaj_valodi", "nem_teljesult"]], hide_index=True, column_config={
        "modell": "módszer",
        "megfelelt": "megfelelt?",
        "jel_top3": st.column_config.TextColumn(
            "jel a top-3-ban",
            help="A jel a 3 legfontosabb tényező között — azoknál a rendeléseknél, ahol a jel "
                 "bekapcsolt. Elvárás: legalább 90%."),
        "jel_irany": st.column_config.TextColumn(
            "jel iránya jó", help="A jel növeli a kockázatot ugyanezeknél a rendeléseknél. "
                                  "Elvárás: legalább 95%."),
        "zaj_top3": st.column_config.TextColumn(
            "zaj a top-3-ban", help="A zaj a 3 legfontosabb tényező között, az összes rendelésen. "
                                    "Elvárás: legfeljebb 1%."),
        "zaj_arany": st.column_config.TextColumn(
            "zaj ereje / jelé",
            help="A zaj és a jel átlagos hatásának aránya (előjel nélkül). Elvárás: legfeljebb 5%."),
        "zaj_valodi": st.column_config.TextColumn(
            "a zaj hatása a modellre",
            help="Ha CSAK a zajt változtatjuk, a modell becslése átlagosan ennyit mozdul — vagyis "
                 "mennyire épít maga a modell a zajra (utólagos ellenőrzés, nem előre rögzített)."),
        "nem_teljesult": st.column_config.TextColumn("ami nem teljesült", width="medium"),
    })
    notes = ["Az elvárásokat a mérés előtt rögzítettük (döntési napló), hogy az eredmény ismeretében "
             "ne lehessen őket utólag igazítani."]
    planted_models = pl["modellek"].values()
    real = {r["nev"]: r.get("zaj_valodi_hatas_pp") for r in planted_models}
    for r in planted_models:
        rv = r.get("zaj_valodi_hatas_pp")
        if r["megfelelt"] or rv is None:
            continue
        most = " — a négy módszer közül a legtöbbet" if rv >= max(v for v in real.values() if v is not None) else ""
        verdict = ("A magyarázat tehát nem eltúlozza a zaj szerepét, hanem jelzi, hogy a modell a "
                   "véletlen ingadozást is megtanulta." if rv >= r["zaj_atlag_abs_pp"] else
                   "Itt a magyarázat a valódinál erősebbnek mutatja a zajt.")
        notes.append(f"**{r['nev'].capitalize()}:** a zaj ereje a jelhez képest {nv.fmt_pct(r['zaj_arany'], 1)}, "
                     f"kicsit több a megengedett {nv.fmt_pct(fres['beallitas']['kuszobok']['zaj_arany'], 0)}-nál. "
                     f"Ha csak a zajt változtatjuk, a becslése átlagosan {nv.fmt_num(rv, 2)} százalékponttal "
                     f"mozdul{most}; a magyarázat {nv.fmt_num(r['zaj_atlag_abs_pp'], 2)} százalékpontot "
                     f"tulajdonít neki. {verdict}")
    st.caption(" ".join(notes))
    with common.details("Szakmai részletek: törlési és beszúrási görbe, AOPC"):
        kinds_f = [k for k in KINDS if k in tb["modellek"]]
        kf = st.selectbox("Melyik módszer görbéje?", kinds_f, format_func=NAMES.get, key="huseg_modell")
        st.altair_chart(charts.faith_curve_chart(d.faith_curve_table(fres, kf), ink=common.ink()),
                        width="stretch")
        st.caption("A törlési görbe: a tényezőket a sorrend szerint egyenként „kivesszük” (a közös "
                   "háttér értékeire cseréljük), és a becslés esését átlagoljuk a rendeléseken. "
                   "Ahol a görbe a csúcson van, ott a növelő tényezők már kint vannak, a csökkentők "
                   "még bent; a végén minden tényező a háttérből jön.")
        st.dataframe(d.faith_details_table(fres), hide_index=True, column_config={
            "modell": "modell", "sorrend": "sorrend",
            "torles_aopc": "törlési AOPC (pp) [95% CI]",
            "beszuras_aopc": "beszúrási AOPC (pp) [95% CI]",
            "top3_eses": "top-3 esés (pp) [95% CI]"})
        s_ = fres["beallitas"]
        st.markdown(
            f"Interventional maszkolás a {len(s_['jatekosok'])} tényezőn (a hónap egyben), közös háttér: "
            f"{s_['hatter']} tisztított tanító rendelés (mag {s_['hatter_mag']}), valószínűség-tér, a "
            f"KernelSHAP-kontrollkar {s_['rendelesek']} teszt-rendelése. Sorrend: a magyarázat szerint "
            "a legjobban növelő tényező előre (előjelesen). **AOPC** — a törlésnél a becslés esésének, "
            "a beszúrásnál (üres rendelésből visszatéve) az emelkedésének átlaga a 22 lépésen. "
            f"Véletlen: {s_['veletlen_sorrendek']} sorrend átlaga rendelésenként. A KernelSHAP pontosan "
            "erre az értékfüggvényre illeszt, ezért ezen a próbán előnyben van: ez a felső viszonyítás. "
            f"Beültetett jellemző: a jel a „{nv.display_name(s_['beultetett']['jel_helye'])}”, a zaj a "
            f"„{nv.display_name(s_['beultetett']['zaj_helye'])}” helyére került (a két leggyengébb valódi "
            "jellemző), a négy modell a lezárt beállításokkal tanult újra. Részletek: "
            "`docs/huseg_eredmeny.md`.")

# -------------------------------------------- kontrollkar (szakmai rész)
with common.details("Szakmai részletek: a magyarázatok ellenőrzése (KernelSHAP-kontrollkar)"):
    if kres is None:
        st.info("A kontrollkar eredménye még nincs meg. Futtatás: `python -m xai.kernel_arm` "
                "(200 rendelés, kb. 20–40 perc; a random forest a lassú).", icon=":material/science:")
    else:
        ks = kres["beallitas"]
        st.markdown(
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
            "Az első két oszlop a mérés saját zaja: ugyanaz a modell, ugyanazok a rendelések, csak "
            "más véletlen mintavétel, ill. más háttér. Ha két modell egyezése ennél nem rosszabb, "
            "a különbség nem a modellekből jön. A második táblázat utolsó három oszlopa azt mutatja, "
            "mennyire követi a felületen látható magyarázat (saját magyarázó + százalékpontra "
            "átváltás) a valószínűség-tér interventional Shapley-értékeit. Részletek: "
            "`docs/kernel_kar_eredmeny.md`.")

# ----------------------------------------------------------------- eredet
with common.details("Szakmai részletek: honnan jönnek a számok? (eredet)"):
    if chk.get("modellek") is not None:
        mt = chk["modellek"].copy()
        mt["most"] = [nv.fmt_num(v, 5) for v in mt["most"]]
        mt["lezart"] = [nv.fmt_num(v, 5) for v in mt["lezart"]]
        st.dataframe(mt, hide_index=True, column_config={
            "modell": "modell", "most": "PR-AUC most (a felületen)",
            "lezart": "PR-AUC a lezárt mérésben",
            "egyezik": st.column_config.CheckboxColumn("egyezik")})
        st.caption(f"Forrásfájlok ujjlenyomata egyezik: "
                   f"{'igen' if chk['forrasok_egyeznek'] else 'NEM'}.")
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
               f"C = {nv.fmt_num(info['referencia']['logreg'], 1)}; döntési fa mélység "
               f"{info['referencia']['dontesi_fa']}; "
               f"random forest levélméret {info['referencia']['random_forest']} — mind a címke-tisztított "
               f"tanító ablakon ({nv.fmt_num(info['tanito_sorok'], 0)} rendelés), mag {info['mag']}.")
