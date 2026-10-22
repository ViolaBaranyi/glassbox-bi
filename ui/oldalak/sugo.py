"""Súgó és fogalmak — használati útmutató, fogalomtár, rövidítések, korlátok."""

import pandas as pd
import streamlit as st

import unicodedata

from ui import charts, common
from xai import labels
from xai import narrative as nv
from xai.models import KINDS, NAMES

common.page_header("Súgó és fogalmak",
                   "Minden, ami a felület használatához kell — informatikai előismeretek nélkül.")
ov = common.require_warehouse()
periods = {k: common.window_period(k) for k in ("tanító", "validációs", "teszt")}


def _sort_key(text: str) -> str:
    """Ábécérend ékezetek nélkül (á ≈ a), hogy az ékezetes szavak ne a lista végére kerüljenek."""
    plain = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in plain if not unicodedata.combining(ch)).lower()

tabs = st.tabs(["Kezdés", "Fogalmak", "A 21 tényező", "Brazil államok", "Termékkategóriák",
                "Mire nem alkalmas?"])

# -------------------------------------------------------------------- kezdés
with tabs[0]:
    st.markdown(
        "#### Mi ez a felület?\n"
        "Az **Üvegdoboz BI** egy kutatási prototípus. Egy brazil online piactér (**Olist**) "
        f"{nv.fmt_num(ov['rendelesek'], 0)} valódi, névtelenített rendelésén "
        f"({nv.fmt_date(ov['elso'])} – {nv.fmt_date(ov['utolso'])}) mutatja meg:\n"
        "1. **mikor és hol késtek** a csomagok;\n"
        "2. egy tanuló számítógépes módszer (a **modell**) **mekkora eséllyel** jósol késést egy "
        "rendelésre;\n"
        "3. **miért** gondolja ezt — érthető tényezőkre bontva.\n\n"
        "Az „üvegdoboz” név arra utal, hogy a modell nem „fekete doboz”: minden szám mögé be "
        "lehet nézni, és minden számot ellenőrizni lehet.\n\n"
        "#### Mit jelent az, hogy egy rendelés késett?\n"
        "Vásárláskor a webáruház megígér egy kézbesítési napot. Ha a csomag **ennél később** "
        "érkezik meg, a rendelés **késett** — akkor is, ha csak egy nappal. A felület csak a már "
        "kézbesített rendeléseket elemzi; a törölt vagy el nem jutott rendeléseknél nem tudjuk, "
        "késtek-e volna.\n\n"
        "#### Hogyan használd? — lépésről lépésre\n"
        "1. **Áttekintés** — kezdd itt. Megmutatja, mennyi rendelés késett, hogyan változott ez "
        "hónapról hónapra, és melyik államokban vagy termékeknél késnek a legtöbbet. Ezek tények, "
        "a modelltől függetlenül.\n"
        "2. **Rendelés kockázata** — válassz egy rendelést. Látod a becsült késési esélyt, hogy "
        "mennyire hihető ez a szám, és hogy melyik adat mennyivel növelte vagy csökkentette. A "
        "határidő-görbe azt mutatja, mit becsülne a modell, ha a webáruház más szállítási időt ígérne.\n"
        "3. **A modell** — itt derül ki, mennyire lehet megbízni a modellben. Kezdd a "
        "„Röviden” résszel.\n"
        "4. **Kérdezz** — tegyél fel kérdést a rendelésekről: írd le magyarul (ehhez helyi nyelvi "
        "modell kell), vagy állítsd össze a kérdésépítővel — mit mérjünk (pl. késési arány), milyen "
        "bontásban (pl. államonként) és milyen szűréssel. A válasz szövegben, ábrán és táblázatban "
        "jön; ha a kérdésre nincs adat (pl. haszon), a rendszer megmondja, miért nem — és nem mond "
        "számot.\n"
        "5. **Súgó** — ez az oldal: fogalmak, rövidítések, korlátok.\n\n"
        "#### Hasznos tudnivalók\n"
        "- Ha egy szám vagy cím mellett **kis kérdőjelet** látsz, vidd fölé az egeret: rövid "
        "magyarázat jelenik meg.\n"
        "- Az ábrákon is **rámutathatsz egy pontra vagy sávra** — megjelennek a pontos számok.\n"
        "- A **„Hogyan olvasd?”** szövegek minden ábra alatt elmagyarázzák, mit látsz.\n"
        "- A **„Szakmai részletek”** dobozok a szakembereknek szólnak — nyugodtan átugorhatod őket.\n"
        "- Az oldalsávon a **„Mutassa, mi történt valójában”** kapcsolóval eldöntheted, hogy a "
        "felület mutassa-e, késett-e ténylegesen egy rendelés (kikapcsolva úgy viselkedik, mintha "
        "a csomag még úton lenne).\n"
        "- A felület **csak a saját gépeden fut**; az adat nem megy ki az internetre.")

# ------------------------------------------------------------------ fogalmak
with tabs[1]:
    st.caption("A felületen előforduló fogalmak, hétköznapi nyelven. A zárójelben lévő szakszavakat "
               "a dolgozat és a szakmai részletek használják.")

    def section(title: str, items: list[tuple[str, str]]) -> None:
        st.markdown(f"#### {title}")
        st.markdown("\n".join(f"- **{t}** — {x}" for t, x in items))

    section("A rendelésről", [
        ("Rendelés", "egy vásárlás a webáruházban; több terméket, akár több eladótól is "
                     "tartalmazhat."),
        ("Ígért határidő (vállalt határidő)", "az a nap, amelyre a webáruház a vásárláskor "
         "megígérte a kézbesítést. Az „ígért szállítási idő” az, hogy ez hány nappal van a "
         "rendelés után."),
        ("Késés", "a csomag az ígért nap után érkezett meg."),
        ("Határidő-görbe", "a Rendelés kockázata oldalon: a modell becslése ugyanarra a rendelésre, "
                           "ha az ígért szállítási idő más lenne. A modell viselkedését mutatja, nem azt, "
                           "mi történne a valóságban; és mivel a késést az ígért naphoz mérjük, hosszabb "
                           "ígéretnél ugyanaz a szállítás ritkábban számít késésnek."),
        ("Késési arány", "a rendelések hány százaléka késett. Ha 100 rendelésből 7 késett, a "
                         "késési arány 7%."),
        ("Kihagyott rendelések", "törölt, elveszett vagy még úton lévő rendelések. Nem tudjuk, "
                                 "késtek-e volna, ezért kimaradnak a számításokból."),
        ("Vevő állama, eladó állama", "a brazil szövetségi állam, ahová a csomag megy, illetve "
         "ahonnan indul. A kétbetűs kódok jelentése a „Brazil államok” fülön van."),
        ("BRL", "brazil reál, Brazília pénzneme."),
        ("Rendelésazonosító", "a rendelés egyedi, hosszú „neve” betűkből és számokból; a "
                              "személyes adatokat az adat közzétevője eltávolította."),
    ])
    section("Az időszakok", [
        (f"Tanulási időszak (tanító ablak) — {periods['tanító']}", labels.WINDOW_PLAIN["tanító"]),
        (f"Ellenőrző időszak (validációs ablak) — {periods['validációs']}",
         labels.WINDOW_PLAIN["validációs"]),
        (f"Teszt-időszak (teszt ablak) — {periods['teszt']}",
         labels.WINDOW_PLAIN["teszt"] + " A *Rendelés kockázata* oldal ezeket a rendeléseket "
         "mutatja."),
    ])
    section("A kockázat", [
        ("Modell", "számítógépes módszer, amely múltbeli példákból szabályszerűségeket tanul meg, "
                   "és ezekkel becsül új esetekre — itt azt, hogy egy rendelés késni fog-e."),
        ("Becsült kockázat (valószínűség)", "a modell szerint mekkora az esélye a késésnek. 10% "
         "azt jelenti: 10 ilyen rendelésből kb. 1 késne."),
        ("Százalék és százalékpont (pp)", "ha a kockázat 4%-ról 6%-ra nő, az 2 százalékpontos "
         "növekedés (pedig a kockázat másfélszeresére nőtt). A tényezők hatását százalékpontban "
         "adjuk meg, mert így összeadhatók."),
        ("Hányszor az átlag (relatív kockázat)", "a becslés egy átlagos rendeléséhez képest: 3× "
         "azt jelenti, hogy háromszor akkora az esély, mint egy átlagos rendelésnél."),
        ("„100-ból N”", "ugyanaz a kockázat gyakoriságként: „100 ilyen rendelésből N késik” — "
                        "sokaknak ez könnyebben elképzelhető, mint a százalék."),
        ("Hasonló becslésűekből késett", "azok a rendelések, amelyekre a modell ugyanakkora "
         "kockázatot mondott (ugyanabba a sávba esik, pl. 20–30%), és közülük hány késett "
         "valójában. Ebből látszik, mennyire lehet hinni a becsült számnak."),
    ])
    section("A magyarázat", [
        ("Tényező", "egy adat a rendelésről, amelyet a modell figyelembe vesz (pl. a távolság "
                    "vagy az ígért szállítási idő). 21 ilyen van — az „A 21 tényező” fülön."),
        ("Kiindulópont", "a modell becslése egy „átlagos” rendelésre. Innen indul, és a tényezők "
                         "ehhez adnak hozzá, vagy ebből vonnak le."),
        ("Hatás", "hány százalékponttal tolta el egy tényező a becslést a kiindulóponthoz képest. "
                  "Piros (pozitív): növeli a kockázatot; kék (negatív): csökkenti. A kiindulópont "
                  "és az összes hatás összege pontosan a becslés."),
        ("SHAP (Shapley-érték)", "a hatások kiszámításának módszere a játékelméletből: "
         "igazságosan szétosztja a becslést a tényezők között, ahogy egy közös nyereményt a "
         "csapattagok között."),
        ("Nem ok-okozat", "a magyarázat azt mutatja, mire figyel a modell, nem azt, hogy mi okozza "
                          "a késést. Ha egy állam sokat növel a kockázaton, abból nem következik, "
                          "hogy egy másik államba küldve a csomag biztosan időben érne oda."),
    ])
    section("A négy módszer", [(NAMES[k], labels.MODEL_PLAIN[k] + ".") for k in KINDS])
    section("A megbízhatóság mérése", [
        ("Bizonytalansági sáv, valószínű tartomány (95%-os intervallum)", "kevés adatból "
         "számolt szám bizonytalan. A sáv azt a tartományt mutatja, amelyben a valódi érték 95%-os "
         "valószínűséggel benne van. Ha két érték sávja nem fedi egymást, a különbség nem a "
         "véletlen műve. (Szakszavak: Wilson-intervallum, bootstrap.)"),
        ("Rangsorolás", "mennyire jól állítja sorba a modell a rendeléseket kockázat szerint — "
                        "azaz melyik rendelést érdemes előbb figyelni."),
        ("Kalibráció", "mennyire egyezik a becsült százalék azzal, ami valóban történik. Jó "
                       "kalibrációnál a 10%-os becslésű rendelések kb. 10%-a késik."),
        ("Túlbecsült, alábecsült, összhangban", "a modell többet mondott, mint ami történt; "
         "kevesebbet; illetve a bizonytalansági sávon belül egyezett."),
        ("PR-AUC", "rangsorolási mérőszám: ha a modell kockázat szerint sorba rendezi a "
                   "rendeléseket, mennyire kerülnek előre a valóban késők. Minél nagyobb, annál "
                   "jobb; vaktában a késési arány értékét érné el."),
        ("ROC-AUC", "ha kiveszünk egy késett és egy időben megérkezett rendelést, a modell milyen "
                    "eséllyel tartja a késettet kockázatosabbnak (0,5 = találgatás, 1 = tökéletes)."),
        ("Brier-pontszám", "a becsült valószínűségek átlagos hibája — a kisebb a jobb."),
        ("ECE", "a becsült és a tényleges arány átlagos eltérése — a kisebb a jobb."),
        ("Lezárt mérés (protokoll)", "a mérés minden beállítását előre leírtuk és jóváhagytuk, "
         "és csak egyszer futtattuk le, így az eredményt utólag nem lehetett „szépíteni”."),
    ])
    section("A magyarázatok ellenőrzése", [
        ("KernelSHAP-kontrollkar", "a magyarázatokat egy másik, minden módszerre egyformán "
         "használható eljárással is kiszámoltuk, hogy a módszerek tisztességesen összevethetők "
         "legyenek, és lássuk, mennyire pontos a felület magyarázata."),
        ("RBO", "két fontossági sorrend egyezése 0 és 1 között; a lista elejét erősebben súlyozza "
                "(1 = azonos sorrend)."),
        ("Top-3 egyezés", "a három legfontosabb tényezőből hány közös két magyarázatban."),
    ])
    section("A Kérdezz oldal", [
        ("Mérőszám", "amit a kérdés mér: pl. késési arány, átlagos szállítási idő, forgalom. A "
                     "rendszer csak a *metrikakatalógusban* felsorolt mérőszámokat számolja — "
                     "mindegyiknek rögzített, ellenőrizhető definíciója van."),
        ("Bontás", "milyen csoportokra bontsuk az eredményt: államonként, régiónként, "
                   "kategóriánként, havonta, a hét napjai szerint …"),
        ("Szűrés, időszak", "melyik rendelésekre vonatkozzon a kérdés (pl. csak São Paulo, csak "
                            "2018 első fele). Az időszak a rendelés leadásának napja szerint szűr."),
        ("1. kapu", "ellenőrző lépés a lekérdezés előtt: a mérőszám, a bontás és a szűrő benne "
         "van-e a katalógusban, és a szűrő értékei (államok, kategóriák, napok) tényleg "
         "előfordulnak-e az adatban. Ha nem, a kérdésre indokolt elutasítás jön, szám nélkül."),
        ("Kevés adat", "ha egy csoportban kevés a rendelés (aránynál 100-nál, átlagnál 30-nál "
                       "kevesebb), az értéke a véletlentől erősen ingadozik. A szöveg és az ábra "
                       "ezekre nem épít, a táblázat megjelöli őket."),
        ("Nyelvi modell", "szöveget értő és író program (itt a saját gépeden fut). A Kérdezz "
                          "oldalon két dolgot csinál: a kérdésedből kitölti a kérdés gépi alakját, "
                          "és megfogalmazza a válasz közepét. Számot nem számol és nem ír le."),
        ("Jelölő", "a nyelvi modell a számok helyére jelölőt ír (pl. {O}), a valódi értéket a "
                   "rendszer illeszti be a lekérdezés eredményéből — így a modell nem tud "
                   "számot kitalálni."),
        ("2. kapu", "ellenőrző lépés a nyelvi modell szövegén: minden szám visszavezethető-e az "
                    "eredményre, minden érték a saját csoportja mellett áll-e, a „legmagasabb” "
                    "tényleg az-e, és nincs-e benne ok-okozati állítás. Ha nem megy át, a "
                    "rögzített sablon szövege látszik."),
    ])
    section("Egyéb", [
        ("Olist", "brazil online piactér, amelyen keresztül sok kisebb bolt árul; a rendelési "
                  "adatait névtelenítve, nyilvánosan közzétette (licenc: CC BY-NC-SA 4.0 — nem "
                  "kereskedelmi felhasználás, forrásmegjelöléssel)."),
        ("Adatbázis (tárház)", "az a rendezett adatgyűjtemény a gépeden, amelyből a felület "
                               "minden számot kiszámol."),
        ("SQL", "adatbázis-lekérdező nyelv. Az *Áttekintés* és a *Kérdezz* oldalon minden szám "
                "mellett ott a pontos lekérdezés, így bárki ellenőrizheti."),
        ("Localhost", "a felület csak a saját gépeden fut, az internetről nem érhető el."),
    ])

# ------------------------------------------------------------------ tényezők
with tabs[2]:
    st.caption("A modell ezt a 21 adatot látja minden rendelésről — mind a rendelés leadásakor "
               "ismert, a jövőről semmit nem tud.")
    st.markdown("\n".join(f"- **{nv.display_name(k)}** — {nv.display_info(k)}"
                           for k in nv.DISPLAY_FEATURES))

# ------------------------------------------------------------- brazil államok
with tabs[3]:
    cust = common.by_dimension("vevo_allam", 1).set_index("ertek")
    sell = common.by_dimension("elado_allam", 1).set_index("ertek")
    seller_share = (sell.loc["SP", "rendelesek"] / sell["rendelesek"].sum()
                    if "SP" in sell.index and sell["rendelesek"].sum() else None)
    text_col, map_col = st.columns([3, 2], gap="large")
    with text_col:
        st.markdown(
            "Az adat Brazíliából származik. A kétbetűs kódok **nem országok**, hanem a brazil "
            "**szövetségi államok** hivatalos rövidítései (pl. **SP** = São Paulo, **RJ** = Rio de "
            "Janeiro) — hasonlóan ahhoz, ahogy az amerikai államokat is két betűvel rövidítik "
            "(pl. CA = Kalifornia). Brazília 26 államból és a fővárost (Brasília) magában foglaló "
            "Szövetségi Kerületből (**DF**) áll.\n\n"
            "Az államokat öt nagy **régióba** sorolják:\n"
            "- **Észak** — az Amazonas-vidék: nagy területű, ritkán lakott államok, messze a "
            "legtöbb eladótól;\n"
            "- **Északkelet** — az ország északkeleti része, kilenc állam (pl. Bahia, Alagoas, "
            "Ceará);\n"
            "- **Közép-Nyugat** — az ország közepe, itt van a főváros, Brasília is;\n"
            "- **Délkelet** — São Paulo, Rio de Janeiro, Minas Gerais, Espírito Santo: itt él a "
            "legtöbb vevő, és itt van a legtöbb eladó;\n"
            "- **Dél** — Paraná, Santa Catarina, Rio Grande do Sul.\n\n"
            + (f"A csomagok {nv.fmt_pct(seller_share, 0)}-a São Paulo államból indul, ezért a "
               "messzebbi, északi és északkeleti államokba tartó csomagok útja általában hosszabb."
               if seller_share is not None else ""))
    with map_col:
        st.markdown("**Hol vannak az államok?**")
        st.altair_chart(charts.state_tile_map(), width="content")
        st.caption("Egyszerűsített térkép: minden állam egy egyforma négyzet, nagyjából a valódi "
                   "helyén (fent az észak, balra a nyugat); a szín a régió. Vidd az egeret egy "
                   "négyzet fölé a teljes névért.")
    table = []
    for code, (name, region) in sorted(labels.STATES.items()):          # kód szerint: így könnyű kikeresni
        c = cust.loc[code] if code in cust.index else None
        s = sell.loc[code] if code in sell.index else None
        table.append({
            "rövidítés": code, "állam": name, "régió": labels.REGIONS[region],
            "rendelések (ide ment)": int(c["rendelesek"]) if c is not None else 0,
            "késési arány (ide ment)": nv.fmt_pct(c["kesesi_arany"]) if c is not None else "—",
            "rendelések (innen indult)": int(s["rendelesek"]) if s is not None else 0,
        })
    st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch", height=980,
                 column_config={"állam": st.column_config.TextColumn("állam", width="medium")})
    st.caption("A táblázat a rövidítés szerint ábécérendben van; bármelyik oszlop fejlécére "
               "kattintva átrendezheted. A „rendelések (ide ment)” a vevő állama szerinti, az "
               "„innen indult” az eladó állama szerinti rendelésszám. Ahol kevés a rendelés, ott a "
               "késési arány bizonytalan.")

# ---------------------------------------------------------- termékkategóriák
with tabs[4]:
    st.markdown("A termékkategóriák az adatban angol rövid nevekkel szerepelnek (pl. "
                "*health_beauty*); a felület mindenhol a magyar nevüket mutatja. Egy rendelés "
                "kategóriája a rendelés **legdrágább** termékének kategóriája. Az **ismeretlen "
                "kategória** azokat a rendeléseket jelöli, amelyek legdrágább termékénél az adatban "
                "nincs megadva kategória (vagy csak portugálul, fordítás nélkül).")
    cat = common.by_dimension("kategoria", 1)
    cat = cat.assign(_kulcs=[_sort_key(v) for v in cat["megnevezes"]]).sort_values("_kulcs")
    st.dataframe(pd.DataFrame({
        "kategória (magyarul)": cat["megnevezes"].to_list(),
        "eredeti név az adatban": cat["ertek"].to_list(),
        "rendelések": cat["rendelesek"].astype(int).to_list(),
        "késési arány": [nv.fmt_pct(v) for v in cat["kesesi_arany"]],
    }), hide_index=True, width="stretch", height=560)
    st.caption("A táblázatban kereshetsz is: vidd fölé az egeret, és kattints a jobb felső "
               "sarokban megjelenő nagyítóra. Kevés rendelésnél a késési arány bizonytalan.")

# ------------------------------------------------------------------- korlátok
with tabs[5]:
    st.markdown(
        "A felület egy **kutatási prototípus**, nem kész, éles döntéstámogató rendszer. Amit "
        "érdemes szem előtt tartani:\n\n"
        "- **Nem az okokat mutatja.** A magyarázat azt mondja meg, mire figyel a modell — nem azt, "
        "hogy mi okozza a késést.\n"
        "- **Régi és egyetlen forrásból származó adat.** 2016–2018-as brazil rendelések egyetlen "
        "piactérről. Más országra, más időszakra vagy más webáruházra a modellt újra kellene "
        "tanítani és mérni.\n"
        "- **A magas százalékok túlzók lehetnek.** A legmagasabb becsléseknél a modell többet "
        "mond, mint ami a valóságban történt (lásd: *A modell* oldal). A sorrend — melyik rendelés "
        "kockázatosabb — megbízhatóbb, mint a pontos szám.\n"
        "- **A hónap hatását óvatosan kell kezelni.** Csak két évnyi adat van, ezért a hónap "
        "inkább az adott időszak eseményeit tükrözi, mint egy minden évben ismétlődő hatást.\n"
        "- **A távolság közelítő.** Irányítószám-körzetek középpontjából számoljuk, nem pontos "
        "címekből.\n"
        "- **Egyetlen rendelésből nem lehet ítélni.** Ha egy 50%-os kockázatú rendelés időben "
        "megjött, attól a modell még lehet jó — a megbízhatóság csak sok rendelésen mérhető.\n"
        "- **A nyelvi modell félreértheti a kérdést.** Ezért a válasz első mondata mindig "
        "megmondja, mire vonatkozik (hány rendelés, melyik időszak, milyen szűrés), és a „Hogyan "
        "értette a nyelvi modell a kérdést?” részben látszik az értelmezése; a kérdésépítőbe át is "
        "veheted, és ott javíthatod. A számokat sosem a modell adja, hanem a lekérdezés.\n"
        "- **A szabad szöveges kérdés lassú lehet.** A modell a saját gépeden fut; videókártya "
        "nélkül egy kérdés fél–egy perc is lehet. A kérdésépítő azonnal válaszol.\n"
        "- **Csak az kérdezhető, ami az adatban van.** Haszon, vásárlói értékelés, fizetés, "
        "készlet vagy előrejelzés nincs benne — ezekre a Kérdezz oldal indokolt elutasítást ad.")
