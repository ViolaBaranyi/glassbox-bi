# Glassbox BI

**XAI és LLM integrálása self-service Business Intelligence rendszerbe.**
EKÖP-26-I-1 kutatási prototípus — Baranyi Viola, Eszterházy Károly Katolikus Egyetem.
Témavezető: dr. Király Sándor.

A rendszerben a számokat determinisztikus réteg állítja elő, a nyelvi modell csak
megfogalmaz, az XAI réteg pedig megindokol. Két kapu zárja ki, hogy nem alátámasztott
szám jusson a döntéshozó elé. A név ezt jelöli: **üvegdoboz**, a fekete doboz ellentéte
— a rendszerterv magyar címe „Üvegdoboz BI".

Ez a tároló a megvalósítás; a teljes rendszerterv külön dokumentum.

---

## Gyorsindítás

**Egy parancs, bármely gépen.** A parancsfájl telepíti a [uv](https://docs.astral.sh/uv/)-t,
ha még nincs; a uv a rögzített változatokból (`uv.lock`) előállítja a Python 3.14-et és a
csomagokat; az `inditas.py` pedig előkészíti, ami hiányzik (adat, tárház, modellek), és
megnyitja a felületet a böngészőben (**http://localhost:8501**).

| Gép | Parancs (a projekt mappájában) |
|---|---|
| Windows | `indit_felulet.bat` — dupla kattintás is jó |
| macOS, Linux | `sh indit_felulet.sh` — terminálban |
| bármelyik, ha a uv már megvan | `uv run python inditas.py` |

Kapcsolók, mindhárom formánál ugyanazok (pl. `sh indit_felulet.sh --ellenorzes`):

| Kapcsoló | Mit csinál |
|---|---|
| `--ellenorzes` | csak megnézi, mi van meg és mi hiányzik; adatot nem tölt le, a tárházhoz és a modellekhez nem nyúl |
| `--szintetikus` | internet nélkül: generált, Olist-alakú adattal (nem a valóság, csak a gépezet kipróbálására) |
| `--modell` | ha fut az Ollama, de a nyelvi modell nincs letöltve, kérdés nélkül letölti (kb. 3,4 GB) |
| `--tesztek` | indítás előtt lefuttatja a teljes tesztsort is (néhány perc) |
| `--port 8502` | másik port (ha a megadott foglalt, magától a következő szabadot keresi) |
| `--nincs-bongeszo` | nem nyitja meg a böngészőt (pl. távoli gépen) |
| `--ujraepites` | a tárházat akkor is újraépíti, ha rendben van |

Az első indítás a letöltésekkel együtt néhány perc; utána fél percen belül nyílik a felület.
Leállítás: Ctrl+C a terminálban, vagy zárd be az ablakot.

### Mi kell a futtatáshoz

| Mi | Kötelező? | Méret, forrás | Ki telepíti |
|---|---|---|---|
| Gép | igen | Windows 10/11 (x64); macOS 12 vagy újabb (Apple Silicon és Intel); Linux (x64). Linux ARM-on a csomagok elérhetők, de nem próbáltuk; Windows ARM-on nem fut. | — |
| Szabad hely | igen | kb. 1,2 GB (környezet 0,65 GB, a uv saját Pythonja 0,1 GB, adat 0,12 GB, tárház és modellek 0,06 GB) | — |
| uv | igen | kb. 60 MB, a felhasználó saját mappájába (rendszergazda nem kell) | a parancsfájl |
| Python 3.14 és a csomagok | igen | a `uv.lock` szerint, pontos változatokkal; a gép saját Pythonjához nem nyúl | a uv |
| libomp (csak macOS) | igen | a LightGBM-hez: `brew install libomp` ([Homebrew](https://brew.sh)) | kézzel, egyszer |
| libgomp (csak Linux) | igen | az asztali disztribúciókon általában megvan; ha nincs: `sudo apt install libgomp1` | kézzel, egyszer |
| Olist-adat | igen | kb. 45 MB letöltés a Kaggle-ről, Kaggle-fiók nélkül ([Az adat](#az-adat)) | az indító |
| Internet | az első indításkor | a uv, a Python, a csomagok és az adat letöltéséhez; utána nem kell | — |
| Böngésző | igen | bármelyik mai böngésző | — |
| Ollama és a `qwen3.5:4b` | **nem** | 3,4 GB, 8 GB RAM ajánlott; csak a *Kérdezz* oldal szabad szöveges füléhez ([Szabad szöveges kérdés](#szabad-szöveges-kérdés-helyi-nyelvi-modell)) | kézzel: https://ollama.com/download, utána `--modell` |

Git sem kell: a tároló ZIP-ként is letölthető (GitHub: *Code → Download ZIP*).

### Lépésenként, kézzel

Az indító ugyanezt csinálja; így is futtatható, ha a uv már megvan:

```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windowson egyszer; utána új ablak
uv sync                              # Python 3.14 + a rögzített csomagok
uv run demo.py                       # adat, tárház, tesztek, betanítás, összegzés
uv run python -m ui                  # a BI-felület a böngészőben
```

(macOS-en és Linuxon a uv telepítése: `curl -LsSf https://astral.sh/uv/install.sh | sh`.)

Windowson a **`frissit.bat`** (dupla kattintás) telepíti a uv-t, ha még nincs, lefuttatja a
`uv sync`-et és a teljes tesztsort, a kimenetet pedig a `logs\frissites.log`-ba írja. Egy
`git pull` után is ezt érdemes futtatni; utána a felület: `indit_felulet.bat`.

A környezet a `.venv` mappába kerül. **Ne szerkeszd, ne másold, ne commitold** (a
`.gitignore` kizárja): gépenként épül, és mint minden Python-környezet, az adott gép
abszolút útvonalaira mutat (hol van a Python, hol a projekt). Ha bármi gond van vele,
töröld — a következő `uv run` újraépíti. A projekt saját fájljaiban nincs gépfüggő
útvonal; ezt teszt őrzi.

A `uv.lock` minden csomagot pontos verzióval rögzít Windowsra és Linuxra — ezzel
jönnek ki bitre ugyanazok a számok. A közvetlen függőségek a `pyproject.toml`-ban
vannak; a `requirements.txt` és a `requirements.lock` ugyanezek pip-nek (CI, uv nélküli
gép — lásd [Másik gépre](#másik-gépre)).

Első indításkor a `demo.py` letölti a valódi Olist-adatot a Kaggle-ről (kb. 45 MB,
Kaggle-fiók nem kell), utána egy-két perc alatt végigfuttatja a teljes pipeline-t,
és a végén összegzést ír ki. A további indítások a már letöltött adatot használják.
Fejlesztőkörnyezetben (PyCharm, VS Code) interpreternek a projekt `.venv` mappáját
válaszd — a `uv sync` után ott van, és mindkettő magától felismeri.

## Mit csinál a demó

| # | Lépés | Mit bizonyít |
|---|---|---|
| 1 | Környezet | a verziók rögzítve vannak a kimenetben |
| 2 | Adat | a valódi Olist-adat; ha még nincs meg, letölti a Kaggle-ről |
| 3 | Tárház | 9 CSV → csillagséma DuckDB-ben, **V-1 validációval** |
| 4 | Tesztek | 489 teszt: szivárgásvédelem, V-1, adatmodell, abláció, betanítás, kohorsz, modellválasztás, bootstrap, lezárt futás, referencia-modellek, magyarázatok, szemantikus réteg, nyelvi réteg, mérés, felület; ha bármelyik bukik, **a demó megáll** |
| 5 | Betanítás | a **lezárt v3 protokoll** szerint: LightGBM súlyozás nélkül, a fák száma bővülő ablakos CV-vel, címke-tisztítással; érintetlen, legkésőbbi időszakon mérve; a kalibráció csak diagnosztika |
| 6 | Összegzés | rangsorolás, kalibráció, kizárt rendelések, artefaktumok helye |

**Valódi adat nélkül:** `uv run demo.py --synthetic` azonos szerkezetű, generált
adaton futtatja végig a gépezetet. Erre a CI-nek és a teszteknek van szüksége, mert
a valódi adat nem kerülhet a tárolóba. A szintetikus adat nem a valóság: a kimenet
ilyenkor minden lépésben jelzi, hogy a számok csak a gépezet működését mutatják.

## A BI-felület

```bash
uv run python -m ui                 # vagy az indítóval: indit_felulet.bat / sh indit_felulet.sh
```

A böngészőben nyílik meg: **http://localhost:8501**. Csak ezen a gépen érhető el (a
hálózatról nem), használati statisztikát nem küld; leállítás: Ctrl+C a terminálban. Az
első indításkor a négy modellt a lezárt beállításokkal betanítja (kb. egy perc), és az
`artifacts\v3_modellek.joblib`-ba menti; utána pár másodperc alatt indul. Ha a tárházat
újraépíted, a felület magától frissül.

| Oldal | Mit mutat | Honnan jön a szám |
|---|---|---|
| Áttekintés | a késési arány havonta (a tanító / validációs / teszt ablakkal) és a vevő állama, az eladó állama, ill. a kategória szerint, 95%-os Wilson-intervallummal; az államoknál egyszerűsített (négyzetrácsos) Brazília-térképpel; a 2016 végi adathiány (november: 0, december: 1 rendelés) szürke „kevés adat” sávval jelölve | SQL a tárházból — a lekérdezés szövege is megnézhető |
| Rendelés kockázata | egy rendelés becsült kockázata, relatív kockázata, és hogy a hasonló becslésű rendelések közül ténylegesen hány késett („100-ból N” — a becslés hitelessége); *miért* (SHAP-tényezők és sablonból írt szöveg); **határidő-görbe**: mit becsülne a modell más vállalt szállítási idő mellett (a tanítóadatban ritka tartomány szürkével); ugyanez a négy modellel | a lezárt modellek + `xai/` |
| A modell | a lezárt teszt-kiértékelés (PR-AUC, ROC-AUC, Brier, ECE, páros összevetés), kalibráció tizedekben és rögzített becslési sávokban (teszt és validáció), mi számít a modelleknek, hogyan hat egy tényező, mennyire hűek a magyarázatok (két próba), mennyire stabilak (K3) | `docs/*.json` + a modellek |
| Kérdezz | kérdés a rendelésekről két fülön: **szabad szöveggel** (helyi nyelvi modell, két kapu) vagy **kérdésépítővel** — mit mérjünk (11 mérőszám), milyen bontásban (8), milyen szűréssel, melyik időszakra → szöveges válasz, ábra, táblázat; ha a kérdésre nincs adat (pl. haszonkulcs), indokolt elutasítás, szám nélkül; a lefuttatott SQL és a PostgreSQL-változata is megnézhető | SQL a tárházból, a metrikakatalógus alapján (`semantic/`) — a válasz minden száma a lekérdezés eredményéből |
| Súgó és fogalmak | használati útmutató, fogalomtár hétköznapi nyelven, a 21 tényező, a 27 brazil állam (kód, teljes név, régió, térképen is), a termékkategóriák magyarul, mire nem alkalmas a felület | `xai/labels.py` + SQL |

*A modell* oldal ellenőrzi, hogy a felület modelljei pontosan a lezárt futások modelljei:
ugyanaz a 9 forrásfájl-ujjlenyomat, és mind a négy modell teszt PR-AUC-je egyezik a lezárt
értékkel (zöld jelzés). Egy rendelés magyarázata linkkel megosztható (`?rendeles=<order_key>`).
A felület **informatikai előismeretek nélkül is érthető**: minden oldal tetején „Mit látsz ezen az
oldalon?” leírás, minden ábra alatt „Hogyan olvasd?”, a számok mellett súgó; az államkódok teljes
névvel (pl. AL = Alagoas, Északkelet) és egyszerűsített térképen, a termékkategóriák magyarul
jelennek meg; a számok magyar alakban (tizedesvessző, ezres tagolás szóközzel); *A modell* oldal
„Röviden” összefoglalóval kezd (pl. a 10% legkockázatosabbnak ítélt rendelés között a késések kb.
harmada van), a szakmai részletek pedig lenyitható dobozokban vannak.
Az oldalsávon kikapcsolható a valós kimenet („késett / időben”): így a felület úgy
viselkedik, mint élesben, amikor a kimenet még nem ismert.

### A Kérdezz oldal és a szemantikus réteg

A *Kérdezz* oldalon a kérdést most egy kérdésépítő állítja össze (mit mérjünk, milyen
bontásban, milyen szűréssel, melyik időszakra); később ugyanezt a gépi alakot egy helyi
nyelvi modell állítja elő a szabad szöveges kérdésből. Az út mindkét esetben ugyanaz:

1. **Metrikakatalógus** (`semantic/katalogus.toml`): mit lehet egyáltalán kiszámolni —
   11 mérőszám SQL-definícióval, mértékegységgel és a „kevés adat” küszöbével; 8 bontás
   (állam, régió, kategória, hónap, év, a hét napja …); és amit az adat nem tud (haszon,
   értékelés, fizetés, készlet, lemondás, előrejelzés), indokkal és javaslattal.
2. **KAPU ①** (`semantic/spec.py`): a kérdés gépi alakját a katalógushoz és az adatból
   generált fehérlistához méri. Az írásmódokat a kanonikus kódra fordítja („Sao Paulo”,
   „sp” → SP; „délkelet” → SE); ami nem felel meg, arra indokolt elutasítást ad (kód,
   magyar üzenet, javaslat) — **szám nélkül**.
3. **SQL-építő** (`semantic/builder.py`): az SQL a katalógus töredékeiből és a fehérlistás
   értékekből áll össze, szintaxisfán (sqlglot), nem szövegösszefűzéssel; ugyanabból a
   fából PostgreSQL-változat is készül. Lefutás előtt egy őr újra elemzi: egyetlen SELECT
   lehet, csak a katalógus tábláival, adatmódosítás és allekérdezés nélkül.
4. **Eredmény** (`semantic/engine.py`): a számok a lefuttatott SQL-lel együtt; aránynál
   95%-os Wilson-tartomány, a kevés rendelésből számolt csoportok megjelölve. Ugyanarra a
   kérdésre bitre azonos.
5. **Válasz**: a kérdésépítőnél sablon írja (`semantic/answer.py`), a szabad szöveges
   kérdésnél a nyelvi modell fogalmazza (`narrative/`) — de a számokat egyik sem írja le: a
   gép illeszti be őket, és minden szám mellé feljegyzi, az eredmény melyik mezőjéből jön.
   A KAPU ② megnézi, maradt-e a szövegben vissza nem vezethető szám.

Ellenőrzés: a katalógus minden mérőszáma minden bontással egyezik egy független
pandas-számolással (teszt), és a PostgreSQL-változat a valódi adaton 354 lekérdezésben,
8195 cellában ugyanazt adja, mint a DuckDB (`docs/pg_ellenorzes.md`).

### Szabad szöveges kérdés (helyi nyelvi modell)

A *Kérdezz* oldal **Szabad szöveggel** fülén magyarul lehet kérdezni („Melyik régióban
késnek a legtöbbet 2018-ban?”). Ehhez egy helyi nyelvi modell kell — így az adat nem
hagyja el a gépet, és internet nélkül is működik:

1. Telepítsd az **Ollamát**: https://ollama.com/download (Windowson telepítő; utána a
   háttérben fut).
2. Töltsd le a modellt (egyszer, kb. 3,4 GB):

   ```powershell
   ollama pull qwen3.5:4b
   ```

3. Indítsd újra a felületet. Ha a modell nem érhető el, a fül megmondja, mi hiányzik — a
   **Kérdésépítővel** fül addig is működik.

Mi történik egy kérdéssel (rendszerterv 14.):

1. **① hívás** (`narrative/to_spec.py`): a modell a kérdésből kitölti a kérdés gépi
   alakját — JSON-sémához kötve, és csak a metrikakatalógus kivonatát látja, adatot nem.
   Ha a kérdés olyat kér, ami nincs a katalógusban, ezt jelzi, és nem választ helyette mást.
   Az államot kóddal, a többi szűrőt a kérdés szavával írja; a ragozott alakot („São
   Paulóban”, „Északkeleten”, „hétfőn”) a kód oldja fel — ha egy szó több értékre is illik
   („bútor”), nem talál, hanem a javító kör kapja meg a jelölteket.
2. **KAPU ①** — ugyanaz, mint a kérdésépítőnél. Formai hibára (pl. elírt állam) egy javító
   kör jár a kapu üzenetével; ha az sem jó: elutasítás, szám nélkül.
3. **SQL és eredmény** — a determinisztikus réteg, nyelvi modell nélkül.
4. **② hívás** (`narrative/to_text.py`): a válasz első mondatát (hány rendelés, melyik
   időszak, milyen szűrés) és a korlátokat a kód írja; a modell a közbülső részt
   fogalmazza — legfeljebb három mondatot, ami közvetlenül felel a kérdésre. A számok
   helyére jelölőt ír (`{O}`, `{S1}` …); a behelyettesítést a gép végzi.
5. **KAPU ②** (`narrative/verifier.py`): a szöveg minden száma visszavezethető-e az
   eredményre, minden érték a saját csoportja mellett áll-e (a felcserélt érték a
   hallucináció egyik tipikus alakja: a szám maga létezik, csak rossz helyen), a
   „legmagasabb / legalacsonyabb” tényleg az-e, a 95%-os tartomány határai tartományként
   szerepelnek-e, és nincs-e benne oksági állítás. Ha nem megy át, a sablonos válasz látszik.

Amiben a kód biztosabban dönt, ott a kód dönt, és a felület megmutatja, mit írt át a modell
űrlapján: az időkifejezést („tavaly”, „2018 első felében”, „az elmúlt három hónapban”) a kód
számolja (`narrative/idoszak.py`); a kérdés felsőfoka („leglassabb”) adja a sorrend irányát;
egy értékre szűrve nincs bontás ugyanarra; a jövőbeli időszak előrejelzés, erre indokolt
elutasítás jön.

Minden hívás egy sor a `logs/llm_calls.jsonl`-ban (modell és ujjlenyomata, idő, tokenek, a
kapuk ítélete) — ez a mérőpad nyersanyaga. Helyi modellnél az idő részekre bontva is: a
modell betöltése, a prompt beolvasása, a válasz generálása. Az első valódi futásban
(okt. 15., `qwen3.5:4b`, laptop, videókártya nélkül) egy kérdés 93 mp volt; a napló 2050
bemeneti tokent mutatott, holott a v1 prompt kb. 4300 token — **a gép alapértelmezett, 2048
tokenes kontextusán csonkolódott**, a modell a prompt nagy részét nem is látta. Ezért a
kontextusméret most rögzített (`kontextus = 4096`; ha egy hívás a határig ér, a napló jelzi),
és a v2 prompt fele akkora (2057 token, mérve). A fejlesztői próbán (okt. 16.) egy kérdés
mediánja 37 mp volt (① 19 mp, ② 19 mp): a második kérdéstől a prompt eleje a modell
gyorsítótárából jön (34 mp helyett ~11 mp beolvasás). A modell a hívás után 30 percig a
memóriában marad (`tartas`), és a *Kérdezz* oldal megnyitásakor a háttérben betöltődik,
amíg a kérdést gépeled.

**Fejlesztői próbasor.** A `uv run python -m narrative.proba` 19 kérdést futtat végig
(`eval/fejlesztoi_kerdessor.toml`, köztük 6 csapdát, amelyre elutasítás a helyes válasz),
és kérdésenként megmondja, jól értette-e a modell, átment-e a válasz a 2. kapun, és mennyi
ideig tartott; a jelentés a `logs/` mappába kerül. Ez hangolásra való — a dolgozat mérése a
későbbi, lezárt kérdéssoron megy, amelyben ezek a kérdések nem szerepelhetnek. Az első
futás (okt. 16., v2): 10/13 helyes értelmezés, 5/6 helyes elutasítás, a 2. kapun 6/13 szöveg
ment át — a bukások többsége a kapu hibája volt (a sima szóközzel írt ezres tagolás, a
csoportnévbe vágó mondathatár, a rövidített dátum), kettő valódi (kitalált jelölők; a 95%-os
tartomány „mélypontként” és „csúcsként”). A v3-mal (okt. 16. 11:07): 12/13 értelmezés, 6/6
elutasítás, a 2. kapun 10/13, medián 32 mp/kérdés. A kapu ezután még szigorúbb lett (havi
bontásnál a hónapnév évszám nélkül is, a „csúcs” és a „mélypont” is felsőfok, a szűrés
tagadása hiba): ugyanazokon a szövegeken 8/13 megy át, és mind az öt elakadó valódi hiba
(rossz csúcshónap, rossz kategórianév, kitalált szám, „kb. 60%” az 59,1% helyett, a szűrés
tagadása). A harmadik futás (11:33) a szigorúbb kapuval: 12/13 értelmezés (új hiba: a modell
a mintapéldából egy hétfő-szűrőt vett át — azóta a hét napjára, régióra és államra csak akkor
szűr, ha a kérdés említi), 6/6 elutasítás, a 2. kapun 9/13 (mind a négy elakadó valódi
hiba), medián 29 mp/kérdés. A modell a jelölő mellé gyakran a számot is leírja („15,3 nap
(15,3 nap)”) — a megjelenítés az ismétlést egyszer mutatja. A beállítás a `configs/llm.toml`-ban van; más
modellt vagy OpenAI-kompatibilis API-t a `.env`-ben lehet megadni (`LLM_MODEL`,
`LLM_PROVIDER=api`, `LLM_BASE_URL`, `LLM_API_KEY`). A modellválasztás még mérés előtt áll:
a `qwen3.5:4b` javaslat (kicsi, többnyelvű); a végleges a 120 kérdéses készleten dől el,
egy kisebb és egy erősebb modell összevetésével (rendszerterv M-4).

**Mérés a lezárt kérdéssoron (K1, F-1, F-2).** A dolgozat számai a `uv run python -m
narrative.meres` parancsból jönnek, egy 130 kérdéses kérdéssoron (`eval/meresi_kerdessor.toml`,
olvasható változata `eval/meresi_kerdessor.md`: 102 megválaszolandó kérdés és 28 csapda; 80
kérdést Claude írt, 50-et Viola a saját szavaival, mielőtt a többit látta volna). A kérdéssor a lezáráskor ujjlenyomatot kap (SHA256), ez bekerül
a protokollba (`docs/k1_protokoll.json`), és a mérés csak jóváhagyott protokollal és változatlan
kérdéssorral indul el. Lezárás előtt egyetlen kérdés sem fut valódi modellen — különben a kódot
hozzájuk igazítanánk. Egy kérdés egy ismétlésében az ① hívás egyszer fut, és **ugyanabból az
eredményből** készül a fő ág (jelölőkkel, a 2. kapu után) és a kontrollág (a modell maga írja a
számokat, a kapu csak mér) szövege; így a két ág között egyetlen különbség van. Három ismétlés,
két modell ugyanabból a családból: `qwen3.5:4b` és `qwen3.5:2b` (M-4: a méret a kísérleti
változó; API-kulcs nem kell — a második modellt előtte le kell tölteni: `ollama pull qwen3.5:2b`). A jelentés (`logs/meres/<dátum>_<modell>/jelentes.md`): F-1 (helyes
mérőszám és bontás, cél ≥ 85%), F-2 (elutasított csapda, cél ≥ 90%), és a K1: a modell
szövegeinek hány százalékában talál a 2. kapu alá nem támasztott állítást, ágonként, Wilson-
intervallummal, kérdésenként párosított bootstrap-különbséggel. Ez alsó becslés: a kapu
tévesztéseit egy 60 szöveges, vak kézi ellenőrzés becsli (`kezi_ellenorzes.csv`, a kulcs külön
fájlban). A megszakadt mérés folytatható (`--folytat`), ha a kód és a promptok nem változtak.
A rossz csoporthoz kötött érték a számjeggyel leírt számnál is hiba (a kontrollágon minden szám
ilyen), hogy a két ág ugyanazzal a mércével mérődjön.

**v4 (okt. 20.).** A v3 mérésén látott hibákból a nyelvi réteg javított változata: időkifejezések
(„félév”, „tavaly negyedik negyedévben”, „Q3”), a kérdésben nem említett kategória, „késett”
szűrő és időablak elmarad, idősor időrendben, elutasítás vevőszámra, nem elérhető adatra és két
bontásra, a 2. kapu kevesebb téves riasztással. Mivel a v1 kérdésein hangolódott, ott mérve
optimista lenne: a mérése új, Viola által írt, lezárt kérdéssoron megy, a v3-mal párosítva
(`docs/k1_protokoll_v2.json`; a v3 kód egy git-munkamappában változatlanul fut:
`tools\v3_futtatas.bat`). A protokoll rögzíti a v4 kód ujjlenyomatát — más kóddal a mérés nem
indul el.

**A v2 mérés eredménye (okt. 20., `docs/k1_v2_eredmeny.md`).** Viola 56 új kérdésén (45
megválaszolandó + 11 csapda), a qwen3.5:4b-vel, kérdésenként párosítva: teljes egyezés v3 40,0% →
v4 48,9% (+8,9 pp, 95%: −2,2 – +20,0 pp; 5 kérdésen csak a v4, 1-en csak a v3 helyes), F-1
64,4% → 66,7%, F-2 mindkettőnél 63,6% (a csillagos csapdákból 7/8; a csillag nélküli, két
bontást kívánó 3 kérdést egyik kód sem utasította el). A v1 kérdésein látott javulás (+21,6 pp)
tehát nagyrészt a hangolásé volt: új kérdéseken kisebb, és az intervallum a nullát is
tartalmazza. K1 a fő ágon ugyanazzal (a v4) kapuval: a v4 szövegeinek 36,4%-a megjelölt, a v3-éinak
52,4%-a (párosítva −19,0 pp, 95%: −35,7 – −2,4); a felhasználóhoz a fő ágon egyik sem jut el
(sablon), a kontrollágon 36,4% igen. A 2B a v4-gyel: teljes egyezés 20,0%, F-1 35,6%, a
megválaszolandó kérdések harmadát (15/45) tévesen elutasítja. Az új kérdések nehezebbek: a v4 fő
hibája, hogy a „mikor / melyik hónapban / hogy változott / 2017 vs 2018” kérdésből nem csinál
idősort (7 kérdés), és az évszakos, „utolsó N hónap” időszakokat rosszul fordítja. Az összevetés
kódja (`tools/k1_v2_osszevetes.py`) a futások előtt készült, ujjlenyomata a protokollban.

**Gépváltás és nagyobb modell (okt. 22., `docs/k1_v2_gepvaltas.md`, `docs/k1_9b_eredmeny.md`).**
Ugyanaz a 4B modellfájl, kód és kérdéssor Viola asztali gépének videókártyáján (RTX 4060 Laptop,
8 GB): a modell nyers válasza a kérdések kb. 40%-ánál más, mint a laptop processzorán, a teljes
egyezés 48,9% helyett 57,8% (párosítva +8,9 pp, 95%: 0 – +20) — az abszolút arányok gépenként
ennyit mozoghatnak; a fő eredmény az előre rögzítettek szerint a laptopos marad. A futás 52 helyett
19 perc. A nagyobb modell (qwen3.5:9b) ugyanazon a gépen, a 4B-vel párosítva (előre rögzített
kiegészítő protokoll: `docs/k1_protokoll_v2_9b.json`): teljes egyezés 57,8% → 53,3% (−4,4 pp, 95%:
−13,3 – +4,4), F-1 75,6% → 68,9%, F-2 72,7% → 81,8% (az elvárt indokkal 54,5% → 81,8%); a K1 a fő
ágon 46,7% → 32,6%, a kontrollágon 42,2% → 30,2% (párosítva −14 pp mindkettő, a nullát épp érintő
intervallummal). A nagyobb modell tehát nem érti jobban a kérdéseket — a fő hibák (a „mikor / vs”
kérdésből nem lesz idősor, az évszakos időszakok) mindkettőnél ugyanazok, vagyis a rendszer
kialakításából, nem a modell méretéből jönnek —, a csapdákat viszont jobban utasítja el, és
kevesebb alá nem támasztott állítást ír; a 9B szövegeinek is kb. harmadát megjelöli a kapu, tehát
a kapu nagyobb modellnél is kell.

**v5 (okt. 22., lezárva, ujjlenyomat `9295c1cd…` — még nem mért).** Mivel a hibák a modell méretétől függetlenek,
a javítás a kódban van: a nyelvi réteg a v2 mérésén látott hibaosztályokat determinisztikusan,
átlátható szólistákkal kezeli, és a felület minden átírást kimond (`narrative/szotar.py`,
`narrative/idoszak.py`, `narrative/to_spec.py`). Új: évszakok, „az év első / utolsó N hónapja”,
„tavalyelőtt”, „… óta”, két év vagy két negyedév összevetése, „mostanság” (rögzítve: az elmúlt 3
hónap); „mikor / melyik hónapban / hogy változott” → idősor; köznyelvi kategória-, régió- és
mérőszámnevek („lakberendezés”, „északra”, „mibe kerül a szállítás”, „mellé fognak a határidővel”);
„hova / honnan”, „hányadik a sorban”, „X és Y közül hol volt a legkisebb”; „az 5 legforgalmasabb
államban …” két lépésben (előbb a rangsor egy külön lekérdezéssel, aztán a kérdés az első ötre
szűrve — a felület kiírja, melyik az öt); a 2. kapu elfogadja a kerekített számot, ha a modell jelzi
(„kb. 59%”, az eredményben 59,1%); a kódban elutasított
kérések: a rendszert becsapni próbáló, a két egymásra épülő lépést kívánó („azokban a hónapokban,
amikor …”), a „honnan hova” párokat és a jövőt kérdező. A már lefutott mérések tárolt ① válaszai a
v5 kódon (`tools/visszajatszas.py`, modell nélkül): a v2 kérdéssoron a 4B teljes egyezése 48,9% →
100%, a 9B-é 53,3% → 100%, a 2B-é 20,0% → 60,0%, romlás nélkül. **Ez nem eredmény, hanem a
hangolás tükre:** a szabályok épp ezekhez a kérdésekhez készültek, a 100% csak azt mutatja, hogy
minden látott hibát lefedtek (a v4-nél a hangolás +21,6 pontja új kérdéseken +8,9 lett). A
fejlesztői próbasor élő futása a videókártyán (okt. 22.): értelmezés 13/13, csapda 6/6, 2. kapu
9/13 (3 valódi hibát fogott meg, 1 téves riasztás — a kerekítés, azóta javítva), 6,9 mp/kérdés. A mérés egy harmadik, friss kérdéssoron lesz: Viola írja,
munkakörönkénti szerepkártyák szerint (`eval/v3_kerdesiras_utmutato.md`); a fejlesztés a kérdéseket a
v5 lezárásáig nem látja, és senki nem futtatja őket a rendszeren.

**A v3 mérés eredménye (okt. 22., `docs/k1_v3_eredmeny.md`).** Viola 50 új kérdésén (39
megválaszolandó + 11 csapda, hat munkakör szerepkártyája szerint, a v5 lezárása után), a
videókártyán, a 4B-vel, kérdésenként párosítva: teljes egyezés v4 59,0% → v5 64,1% (+5,1 pp, 95%:
−5,1 – +15,4; 3 kérdésen csak a v5, 1-en csak a v4 helyes), F-1 71,8% → 79,5%, F-2 63,6% → 54,5%.
A modell nyers válasza a két futásban 49/50 kérdésnél azonos volt, így a különbség tisztán a kódé:
4 javulás, 3 romlás. A v2 kérdésein a visszajátszás 100%-ot adott — új kérdéseken a javulás kicsi,
és az intervallum a nullát is tartalmazza: a látott hibákból írt szabályok egy része általánosít
(időkifejezések, két év összevetése, a kérdésben kimondott mérőszám, a jövő), más része túl
általános (a „-ból / -ből” mindig eladót jelent: „Bahiából jött be” a vevőé; a modell jogos
„nem elérhető” elutasítását a kód egy mérőszám-szó alapján felülírta — 2 csapda). A K1 a fő ágon
nem változott (a modell szövegeinek kb. 37%-át jelöli meg a kapu, a felhasználóhoz 0% jut), a
kontrollágon 18% → 24%. A 9B a v5-tel: teljes egyezés 64,1% (mint a 4B), F-2 63,6%, de a fő ágon
csak 14,7% szövegét kell megjelölni (a 4B-nél 37,8%). Egy futás 8–11 perc.

**A második kapu véletlen átcsúszása (okt. 22., `docs/kapu_atcsuszas.md`).** Ha a modell egy számot
kitalál, és az véletlenül egyezik az eredmény egy megjelenített értékével, a kapu átengedi. A valódi
tárházon, a lezárt kapuval, modell nélkül (`tools/kapu_atcsuszas.py`, előre rögzítve): a három
mérési kérdéssor 186 eredményén, a helyes nagyságrendből húzott 200–200 kitalált számmal a
megjelenítés pontosságával írt szám a fő ágon 0,8%-ban [0,5; 1,1], a kontrollágon 1,2%-ban csúszik
át (százalékos mérőszámnál 3,6–3,9%); eggyel kevesebb tizedessel jelzés nélkül 0,0% / 0,6%; „kb.”
előtaggal viszont 5,3% / 5,2%, sok értéket mutató nézetnél 11%. A rendszerterv korai 9,8%-os
becslése a mostani, pontos alakot megkövetelő kapura nem áll; a v5 „kb.”-szabálya (kevesebb téves
riasztás) cserébe nagyobb átcsúszási esélyt ad. A kapu tehát a második védelmi vonal, a fő a
hely-kitöltés.

---

## Mi van kész

| Modul | Állapot |
|---|---|
| M0 — adattárház, V-1 validáció, adateredet (SHA256) | **kész** |
| M0 — két ténytábla (tétel- és rendelésszint), fő tétel, medián geolokáció | **kész** |
| M0 — megfigyelési zárónap, kizárt rendelések, kohorsz-érzékenységi jelentés | **kész** |
| M0 — a valódi adat automatikus letöltése (`data/fetch_olist.py`) | **kész** |
| M2 — 22 jellemző, point-in-time korrekt (as-of illesztés), jellemzőtáblázat | **kész** |
| M2 — időbeli szétvágás, bővülő ablakos CV | **kész** |
| M2 — LightGBM súlyozás nélkül, kalibrációs diagnosztika (CORP), determinisztikus futás | **kész** |
| M2 — abláció (`--drop`), validációs mérőszámok a `metrics.json`-ban | **kész** |
| M2 — modellválasztás bővülő ablakos CV-n, rögzített fa-szám, címke-tisztítás (`--trees cv`, `--purge`) | **kész** |
| M2 — heti blokk-bootstrap, lezárt v3 alapfutás protokollal (`pipeline/v3_baseline.py`) | **kész — lefutott okt. 9.** (`docs/v3_lezart_eredmeny.md`) |
| M2 — referencia-modellek: logisztikus regresszió, döntési fa, random forest (`pipeline/reference_models.py`), lezárt összevetés (`pipeline/v3_reference.py`) | **kész — lefutott okt. 9.** (`docs/v3_referencia_eredmeny.md`) |
| M3 — SHAP-magyarázatok a négy modellre (pontos TreeSHAP, ill. lineáris SHAP, a 22 jellemzőre összevonva), additivitás-ellenőrzés, sablonos magyarázó szöveg (`xai/`) | **kész (v1)** |
| M5 — Streamlit BI-felület: áttekintés (SQL), rendelés-magyarázat négy modellel, modell-oldal, egyezés-ellenőrzés a lezárt futással (`ui/`, `python -m ui`) | **kész (v1)** |
| Tesztek — szivárgás (14), V-1 és adatmodell (10), abláció (6), betanítás (6), kohorsz (2), modellválasztás (8), bootstrap (6), lezárt futás (14), referencia-modellek (9), magyarázatok (12), szöveg és megjelenítés (22), felület (22), egyezési mértékek (5), kontrollkar (5), nevek és feliratok (5), a magyarázatok hűsége (8), a magyarázatok stabilitása (6), határidő-görbe (4), a kapu átcsúszása (3), időbeli vagy véletlen felosztás (3), a döntés stabilitása (3), ROAR (3), gazdasági forgatókönyvek (4), README-parancsok (2), környezet (8), szemantikus réteg (99), nyelvi réteg (81), nyelvi réteg v4 (22), nyelvi réteg v5 (62), mérés és mérési kérdéssor (18), K1 v2 összevetés (3), két futás összevetése (3), K1 v3 összevetés (4), indító (7) | **kész, 489/489** (egy csak Node.js-szel fut, nélküle kihagyja) |
| Tároló — MIT licenc, CI (Ubuntu + Windows), uv-környezet (`uv.lock`; pip-nek `requirements.lock`), döntési napló | **kész** |
| M2 — 40 futásos sweep, hiperparaméter-hangolás | következő |
| M3 — KernelSHAP-kontrollkar: mind a négy modell ugyanazzal a magyarázóval (valószínűség-tér, közös háttér, 200 rögzített teszt-rendelés), a kar saját zajával (`xai/kernel_arm.py`, `xai/agreement.py`) | **kész** (`docs/kernel_kar_eredmeny.md`) |
| M3 — a magyarázatok hűsége (K2): törlési és beszúrási görbe (interventional maszkolás, a KernelSHAP-karral és véletlen sorrenddel összevetve), beültetett jel- és zaj-jellemző, előre rögzített küszöbökkel (`xai/faithfulness.py`) | **kész** (`docs/huseg_eredmeny.md`) |
| M3 — a magyarázatok stabilitása (K3): 20 bootstrap-újratanítás és 5 kontroll-mag, RBO, súlyozott Kendall-tau, top-3 és iránya, CIES (bemeneti zaj, α = 0,01/0,03/0,05), előre rögzített sejtéssel; utólagos, feltáró ellenőrzés a CIES-hez (`xai/stability.py`) | **kész** (`docs/stabilitas_eredmeny.md`) |
| M3 — határidő-görbe az ellenpélda (DiCE) helyett (Viola döntése, okt. 22.): egy rendelés becslése a vállalt szállítási idő függvényében, minden más változatlan, a tanítóadat tartományával (`xai/deadline.py`, Rendelés oldal) | **kész** |
| M1 — szemantikus réteg: metrikakatalógus (11 mérőszám, 8 bontás), az adatból generált fehérlista, KAPU ① indokolt elutasítással, SQL-építő szintaxisfából (sqlglot) utólagos SQL-őrrel, MetricResult a lefuttatott SQL-lel, sablonos válasz számhivatkozásokkal (`semantic/`) | **kész (v1)** |
| M1 — a PostgreSQL-változat ellenőrzése: a valódi adaton 354 lekérdezés DuckDB-ben és PostgreSQL 17-ben, cellánként összevetve (`semantic/pg_ellenorzes.py`) | **kész — 0 eltérés** (`docs/pg_ellenorzes.md`) |
| M5 — *Kérdezz* oldal: kérdésépítő, példakérdések, válasz + ábra + táblázat, „Próbáld ki az 1. kaput” | **kész (v1)** |
| M4 — nyelvi réteg: szabad szöveges kérdés → ugyanaz a gépi alak (helyi Ollama vagy OpenAI-kompatibilis API, JSON-sémához kötött kimenet, egy javító kör, ragozott szűrőértékek feloldása, időkifejezés és sorrend a kódtól), a modell fogalmazta válaszmag hely-kitöltéssel, a hatókör és a korlát a kódtól, KAPU ② (számok, csoport–érték kötés, „legmagasabb”, a tartomány szerepe, oksági állítás), sablon tartaléknak, napló időbontással; kontrollág a K1-hez; fejlesztői próbasor (`narrative/`, `eval/`) | **kész (v3)** — valódi modellel: okt. 15. (v1, 93 mp), okt. 16. fejlesztői próba (v2: 10/13, 5/6, medián 37 mp; v3: 12/13, 6/6, medián 29–32 mp) |
| M6 — a második kapu véletlen átcsúszása: kitalált számok a valódi eredményeken, a lezárt kapuval, modell nélkül, előre rögzítve (`tools/kapu_atcsuszas.py`) | **kész** (`docs/kapu_atcsuszas.md`) |
| M3 — a döntés stabilitása: a legkockázatosabb 10% a K3 újratanított modelljein (átfedés, stabil mag, többértelműség), előre rögzítve (`tools/dontesi_stabilitas.py`) | **kész** (`docs/dontesi_stabilitas.md`) |
| M2 — időbeli vagy véletlen felosztás: ugyanazok a modellek véletlen és időn belüli ellenőrzésen, előre rögzítve (`tools/felosztas_osszevetes.py`) | **kész** (`docs/felosztas_osszevetes.md`) |
| M3 — ROAR: a magyarázat szerinti fontos tényezők kivétele és újratanítás, véletlen és legkevésbé fontos készletekkel összevetve, előre rögzítve (`tools/roar.py`) | **kész** (`docs/roar_eredmeny.md`) |
| M5 — gazdasági forgatókönyvek (kapacitás- és küszöbszabály, költség- és hatásarányok, blokk-bootstrap) és kalkulátor *A modell* oldalon (`tools/gazdasagi_forgatokonyv.py`) | **kész** (`docs/gazdasagi_forgatokonyv.md`) |
| M6 — mérőpad: 120 kérdéses lezárt készlet (csapdakérdésekkel), K1 a fő ágon és a kontrollágon, két modellel | **kész, a kézi ellenőrzéssel együtt** — a kérdéssor lezárva, a protokoll jóváhagyva (okt. 16.); `qwen3.5:4b` (okt. 19.): F-1 85%, F-2 89%, K1 a modell szövegében 29% / 30% (fő ág / kontrollág), a felhasználóhoz eljut 0% / 30%; `qwen3.5:2b` (okt. 19.): F-1 44%, F-2 86%, K1 40% / 46%, eljut 0% / 46% (`docs/k1_eredmeny_qwen3.5-4b.md`, `docs/k1_eredmeny_qwen3.5-2b.md`); a kapu tévesztéseinek vak kézi becslése mindhárom mérésen (5 minta, 46–60 szöveg; `docs/k1_kezi_ellenorzes.md`): a fő ágon a felhasználóhoz eljutó, a kapu által nem látott hiba 4B 14,2% / 9,5% / 9,3%, 2B 18,1% / 10,0% — kapu nélkül 31–63%; a kapu a hibás szövegek arányát kb. harmadára csökkenti, nem nullára |

---

## A lezárt v3 alapfutás eredménye (2026. október 9.)

A teszthalmaz (2018. június–augusztus, 18 603 rendelés, késési arány 3,6%) egyetlen,
előre rögzített mérése. Protokoll: `docs/v3_protokoll.json` (SHA256 `9407febe…`),
git `6f1b792`, tiszta munkapéldány. Részletek: `docs/v3_lezart_eredmeny.md`.

| mérőszám | teszt [95% CI, heti blokk-bootstrap] | 5 mag (átlag ± szórás) |
|---|---|---|
| PR-AUC | 0,098 [0,055; 0,127] | 0,101 ± 0,003 |
| ROC-AUC | 0,764 [0,723; 0,788] | 0,767 ± 0,004 |
| Brier | 0,0339 [0,0188; 0,0495] | 0,0337 ± 0,0001 |
| ECE (tizedek) | 0,010 [0,008; 0,020] | 0,009 ± 0,001 |

* A modell kimutathatóan jobb a konstans előrejelzésnél (a tanító időszak 5,6%-os
  aránya): PR-AUC +0,062 [+0,035; +0,078], Brier −0,0013 [−0,0019; −0,0007]. A
  Brier-készség viszont csak 3,8%: az érték a **rangsorolásban** van, nem a pontos százalékban.
* A bizonytalanság nagyobbik része a teszt heteiből jön (14 hét); a tanítási véletlen
  (a mag) ehhez képest kicsi.
* A validációs ablakon (2018. márc.–máj., időn kívüli ellenőrzés) gyengébb: PR-AUC 0,179
  (alapráta 10,1%), ROC-AUC 0,650, ECE 0,049 — az ablak eleji márciusi válságot (19% késés)
  a vágás előtti adatból nem lehetett előre látni.
* Windowson és Linuxon bitre azonos.

### Referencia-modellek — lezárt összevetés (2026. október 9.)

Ugyanaz a teszt, ugyanaz az adat-protokoll; minden modell beállítását a tanító időszak
keresztvalidációja választotta. Protokoll: `docs/v3_referencia_protokoll.json`
(`6ea464ac…`), git `76934b1`, tiszta munkapéldány. Részletek: `docs/v3_referencia_eredmeny.md`.

| modell | teszt PR-AUC [95% CI] | teszt ROC-AUC [95% CI] | LightGBM − referencia, PR-AUC [95% CI] |
|---|---|---|---|
| LightGBM (lezárt) | 0,098 [0,055; 0,127] | 0,764 [0,723; 0,788] | — |
| logisztikus regresszió | 0,084 [0,060; 0,103] | 0,740 [0,692; 0,781] | +0,014 [−0,010; +0,029] — nem kimutatható |
| random forest | 0,088 [0,050; 0,118] | 0,739 [0,696; 0,762] | +0,010 [+0,000; +0,018] — határeset |
| döntési fa | 0,061 [0,037; 0,084] | 0,597 [0,573; 0,634] | +0,037 [+0,002; +0,053] |

* A LightGBM minden mutatóban a legjobb pontbecslés, de **a logisztikus regressziótól a
  különbség ezen a teszten nem kimutatható** (a PR-AUC, a ROC-AUC és a Brier különbségének
  intervalluma is tartalmazza a nullát).
* A random forest ellen a ROC-AUC-előny kimutatható (+0,026 [+0,013; +0,039]); a PR-AUC-előny
  határeset — a random forest magok szerinti szórása (0,093 ± 0,004) ekkora különbséget elmos.
* Egyetlen döntési fa minden mutatóban egyértelműen gyengébb.
* Feltáró megfigyelés (nem előre tervezett összevetés): a validációs ablakon — a márciusi
  válság idején — a logisztikus regresszió jóval jobb volt (PR-AUC 0,267 vs 0,179, ROC-AUC
  0,755 vs 0,650): az eltolódott időszakban az egyszerűbb modell robusztusabbnak tűnik.
* Három összevetés × három mutató: az intervallumok egyenként 95%-osak, a határeseteket
  ezért óvatosan kell kezelni. Windowson és Linuxon bitre azonos.

## A legfontosabb módszertani döntések

**Időbeli szétvágás, nem véletlen.** A valóságban mindig múltból jósolunk jövőre.
Tanítás 2018 márciusáig, validáció 2018 május végéig, teszt utána — a teszthez
egyszer nyúlunk. → `pipeline/split.py`

**Point-in-time korrektség, két feltétellel.** Az eladó előzmény-jellemzői
(korábbi késési arány, átlagos feladási idő) csak

1. korábban leadott rendelésekből számolhatók, **és**
2. azoknak is csak a **már ismert** kimenetéből.

A második a kényes: egy tegnap leadott, még úton lévő rendelésről ma nem tudjuk,
késni fog-e. Ezért as-of illesztés a kézbesítés időpontjára. → `pipeline/features.py`

**Rögzített tanulási ütem (0,05).** Nem hangoljuk: ha futásonként változna,
confounding változó lenne a komplexitás és a magyarázat-stabilitás vizsgálatában.

**Korai leállítás kizárólag PR-AUC-ra.** Az összehasonlító `--balance balanced` ág
mellett az alapértelmezett logloss azonnal romlik a validáción, és pár fa után
megállítaná a tanítást. → `pipeline/train.py`, `PARAMS`

**Súlyozás nélkül, utólagos kalibrátor nélkül.** A felületen valószínűséget mutatunk,
tehát a „7%" jelentsen 7%-ot. A súlyozás nélküli modell nyers kimenete *átlagosan* jól
kalibrált (teszt ECE 0,008); egy validáción illesztett izotonikus kalibrátor viszont az
időbeli alapráta-eltolódás miatt (validáció 10,1%, teszt 3,6%) rontana rajta. Ezért nincs
kalibrátor, és a SHAP pontosan a megjelenített számot bontja fel. **A farokban viszont nem
kalibrált:** a teszt-időszakban a 20% feletti becslésű 201 rendelés átlagos becslése 26%,
ténylegesen 12%-uk késett (a 30% felettiek közül 40-ből 4). A tizedekre bontott ábra ezt
elrejti, mert a legfelső tized 9%-tól 58%-ig tart. Ezért a felület a becslés mellé a
hasonló becslésű rendelések tényleges kimenetét is kiírja (döntési napló, okt. 12.). A kalibráció csak
**diagnosztika**: ECE egyenlő szélességű és egyenlő elemszámú sávokkal, a Brier-pontszám
CORP-felbontása (Dimitriadis, Gneiting és Jordan, 2021: MCB − DSC + UNC), Brier-készség
a tanító időszak arányához, és a megbízhatósági táblázat tizedekben.

**Determinisztikus futás.** `deterministic=True`, `force_row_wise=True`:
azonos adat + mag → bitre azonos modell.

**A fák számát a tanító időszakon belül választjuk.** Eddig a korai leállítás a
validációs ablakon döntött, de abban éles rendszerváltás van (március 19,0% késés →
április 4,5%), és egyetlen ablak alapján választani kockázatos (10. lelet). Az új út:
bővülő ablakos keresztvalidáció a tanító időszakon (4 hajtás × 3 mag, korai leállítás
PR-AUC-ra), a végső fa-szám `N_fix = max(50, medián)`, a végső modell pontosan ennyi
fával tanul — a validációs ablak semmit nem befolyásol. Ez az alapbeállítás; a régi út
összehasonlításhoz: `--trees korai`. → `pipeline/model_selection.py`

**A címke is point-in-time (jóváhagyva okt. 9.).** A jellemzőkre már érvényes,
hogy csak a leadáskor ismert információt látják. A tanító *címkékre* ugyanez igaz: egy
február végén leadott rendelésről március 1-jén még nem tudjuk, késik-e. A valódi
adatban a 2018-03-01-i vágásnál a tanító sorok 6,2%-ának a kimenete még ismeretlen volt,
és ezek 26,6%-a késett (a márciusi válság). A `--purge` csak azokon tanul, amelyeknek a
vállalt határideje a vágás előtt lejárt — a leadáskor ismert határidő szerint szűr, nem
a kimenet szerint, így nem torzít. A keresztvalidáció mutatja, hogy számít: a
2017. november 22-én kezdődő (Black Friday-t is tartalmazó) hajtásban tisztítás nélkül
a PR-AUC 0,246, tisztítással 0,17 — azonos fa-számmal is. A nyugodt időszakok hajtásaiban
nincs különbség: a még ismeretlen címkék épp a zavarok kezdetét árulták el.
→ `split.settled_before`

**Referencia-modellek ugyanazon a mércén.** Logisztikus regresszió, döntési fa és random
forest — ugyanazzal az adat-protokollal, mint a LightGBM, és mindegyik egyetlen, a
bonyolultságát szabályozó hiperparaméterrel (C, mélység, levélméret), amelyet ugyanaz a
bővülő ablakos CV választ. A tanító időszakon a logisztikus regresszió szinte eléri a
LightGBM-et (PR-AUC 0,124 vs 0,126); hogy a teszten kimutatható-e a különbség, azt a
lezárt, páros összevetés dönti el. → `pipeline/reference_models.py`, `docs/v3_referencia_protokoll.md`

**Bizonytalanság heti blokk-bootstrappal, a tanítási véletlen külön.** A késések hétről
hétre együtt mozognak, ezért egész heteket húzunk visszatevéssel (B = 2000, percentilis
95%); a rendelésenkénti újramintavétel hamisan szűk intervallumot adna. A modell
magjából eredő szórást öt maggal, külön jelentjük. → `pipeline/bootstrap.py`

**A magyarázat a lezárt modellt bontja — pontosan.** A LightGBM-et a saját, pontos
TreeSHAP-ja bontja (`pred_contrib`, log-odds térben; egyezik a `shap.TreeExplainer`-rel), a
logisztikus regressziót a pontos lineáris SHAP (háttér: 500 rendelés a tisztított tanító
ablakból), a döntési fát és a random forestet a `shap.TreeExplainer` (valószínűség-térben);
a one-hot és a hiány-jelző oszlopok hatása az eredeti jellemzőhöz adódik. A korábban
tervezett „B” beállítás (one-hot + interventional + valószínűség-tér) egy one-hot
jellemzőkön újratanított modellt magyarázna, nem a lezárt, kiértékelt modellt — ezért a
lezárt modellnél az „A” beállítás marad (témavezetői megerősítésre vár). A felület
százalékpontban mutat: a log-odds hozzájárulásokat arányosan osztjuk szét,
Δp_i = φ_i·(p − p₀)/(logit p − logit p₀). Ez additív (a tényezők összege p − p₀),
előjel- és sorrendtartó, de nem a valószínűség-tér pontos Shapley-értéke — az eltérést a
KernelSHAP-kontrollkar méri. Minden modellnél teszt őrzi az additivitást (1e-6 alatt).
→ `xai/explain.py`

**KernelSHAP-kontrollkar: a négy modell ugyanazzal a mércével.** A felület modellenként a
saját, pontos magyarázót használja, más-más térben — a modellek magyarázatának
összevetésébe így a magyarázó típusa is belekeveredhet. A kontrollkar mind a négy modellt
ugyanazzal bontja: KernelSHAP, interventional értékfüggvény, valószínűség-tér, közös
háttér (100 tisztított tanító rendelés), 21 játékos (a hónap egy játékos), 200 rögzített
teszt-rendelés; `l1_reg=False`, mert a shap 0.53 alapból csendben 10 tényezőre szűkít.
Eredmény (`docs/kernel_kar_eredmeny.md`, rangsor-egyezés RBO-val, p = 0,9):
(1) **a felület magyarázata ugyanazt mondja, mint a kar** — a kar 3 legfontosabb
tényezőjének iránya minden rendelésnél egyezik, a rangsor-egyezés 0,88–0,93, akkora, mint
a kar saját háttér-zaja (0,87–0,94); a nagyságok 19–35%-kal térnek el;
(2) **a modellek közti eltérés valódi** — a modellpárok egyezése a karon 0,62–0,77, a saját
magyarázókkal 0,61–0,74: a magyarázó típusa alig számít, és az eltérés jóval nagyobb a mérés
zajánál; a döntési fa magyarázata tér el a legjobban (0,62–0,65), a LightGBM és a random
forest egyezik a legjobban (0,77);
(3) **a kar zaja** — más mintavételi maggal 0,96–0,99 (2090 koalíció elég), más háttérrel
0,87–0,94: a háttér a fő zajforrás. → `xai/kernel_arm.py`, `xai/agreement.py`

**A magyarázatok hűsége a modellhez (K2).** Két, előre rögzített próba (küszöbökkel, a döntési
naplóban); egyik sem használja a valódi teszt-címkéket. (1) **Törlési és beszúrási görbe** — a
kontrollkar 200 teszt-rendelésén a tényezőket a magyarázat sorrendjében egyenként „kivesszük”
(az értéküket a közös háttérből vesszük, interventional maszkolás). A felület szerinti 3
legerősebb növelő tényező kivétele átlagosan 2,8 (LightGBM) · 2,4 (LR) · 2,0 (fa) · 2,5 (RF)
százalékponttal csökkenti a becslést, 3 véletlen tényezőé −0,5…0,0-val; a felület sorrendje
mind a négy modellnél a rendelések 100%-ában jobb a véletlennél, és gyakorlatilag eléri a
KernelSHAP-ot, amely pontosan erre a maszkolásra illeszt (a törlési AOPC-k eltérése ≤ 0,03 pp;
a beszúrásinál a LightGBM-nél 5,0 vs 5,3 pp). (2) **Beültetett jellemző** — a két leggyengébb
valódi jellemző helyére egy ismert hatású „jel” (20%-ban bekapcsol; a tanító ablakban 5,7%
helyett 15,1% késés) és egy hatás nélküli „zaj” került, a négy modellt újratanítottuk. A jel
mind a négy modellnél a jel = 1 rendelések 100%-ában a 3 legfontosabb között van, iránya 100%-ban
helyes; a zaj a rendelések 0–0,6%-ában kerül a top-3-ba. A zaj és a jel átlagos hatásának
aránya 1,1–3,1% (LightGBM, LR, fa), a random forestnél 5,4% — ez az előre rögzített 5%-os
küszöböt kissé átlépi. Feltáró ellenőrzés: maga az erdő épít a zajra (ha csak a zajt cseréljük,
a becslése átlagosan 0,19 pp-tal mozdul, a négy közül a legtöbbet; a magyarázat 0,12 pp-t
tulajdonít neki) → a K4-hez: a kis levélméretű erdő a véletlen ingadozást is megtanulja, és a
magyarázat ezt jelzi. → `xai/faithfulness.py`, `docs/huseg_eredmeny.md`

**A magyarázatok stabilitása (K3).** Előre rögzítve (döntési napló, a futás előtt), a valódi
teszt-címkék nélkül. (1) **Új tanítóadat** — a tisztított tanító ablakból 20 bootstrap-minta, a
négy modell a lezárt beállításokkal újratanítva; a felület magyarázata a kontrollkar 200
rendelésén, rendelésenként a lezárt modellhez mérve. RBO (p = 0,9): logisztikus regresszió
0,93 · random forest 0,86 · LightGBM 0,83 · döntési fa 0,75 (a súlyozott tau és a többi mérték
ugyanígy rendez). Az előre rögzített sejtés (az LR a legstabilabb, a fa a legkevésbé) mind az 5
párra teljesült; a nyitott párban az RF kissé stabilabb a LightGBM-nél (−0,028 [−0,035; −0,022]).
A top-3 tényező iránya 99–100%-ban marad (a fánál 92%), a sorrendjük mozog (a LightGBM
top-3-jából átlagosan 2,3 marad). Kontroll (ugyanaz az adat, más mag): LR 1,00 · fa 0,97 · RF
0,91 · LightGBM 0,89 — a LightGBM és az RF eltérésének nagyobbik fele a tanítás véletlene; a
fa a maggal stabil, az adattal a legkevésbé, és a becslése átlagosan 4,1 pp-t mozdul (a teszt
késési aránya 3,6%). (2) **CIES** (Văduva és mtsai., a bemenet zaja, α = 0,03, M = 10): RF 0,96
· LR 0,95 · fa 0,94 · LightGBM 0,87; α = 0,01 és 0,05 mellett a sorrend ugyanez. **Utólagos,
feltáró ellenőrzés** (ugyanazok a zajos szomszédok): az egész értékű jellemzők kerekítése nem
változtat (0,87); a LightGBM értékét a hónap kódolása húzza le — április és augusztus
koszinusza a gépben −0,4999999999999998, illetve −0,5000000000000004, a LightGBM ezen vág, és a
200-ból 69 augusztusi rendelés a vágáson ül. A hónap zaja nélkül a LightGBM 0,95, a négy modell
0,94–0,97. → a K4-hez: a stabilitás nem a bonyolultsággal, hanem a modell varianciájával nő
vagy csökken (az egyetlen fa a legkevésbé stabil, az átlagolás és a regularizáció stabilizál).
→ `xai/stability.py`, `docs/stabilitas_eredmeny.md`

**A döntés stabilitása (okt. 25., `docs/dontesi_stabilitas.md`).** Ugyanazokon a modelleken (20
bootstrap + 5 kontroll-mag), a teszt mind a 18 603 rendelésén: a lezárt modell legkockázatosabb
10%-ából (1860 rendelés) egy újratanított modellnél átlagosan ennyi marad a felső 10%-ban: LR
87% · RF 66% · LightGBM 61% · fa 31%; a LightGBM listájának csak 5%-a marad bent mind a húsz
modellnél, és a teszt-rendelések 31%-ának a besorolása legalább egyszer változik — miközben az
újratanított modellek PR-AUC-ja 0,076–0,116 (a lezárt 0,098). A felület 200-as listájából 44%
marad. Az előre rögzített sejtés (a K3 sorrendje) mind az 5 párra teljesült; a nyitott párban az
RF stabilabb. → a Rashomon-hatás a döntés szintjén; a kockázati lista rangsor, nem végleges
kiválasztás (a felület ki is írja). → `tools/dontesi_stabilitas.py`

**Időbeli vagy véletlen felosztás (okt. 25., `docs/felosztas_osszevetes.md`).** Ugyanazok a
modellek és beállítások, véletlen felosztással (10 ismétlés): a LightGBM PR-AUC-ja 0,279 a
valódi, időbeli 0,098 helyett, az emelés 4,1× a 2,7× helyett, a felső 10% a késések 41%-át fogja
a 32% helyett (a tanító időszak véletlen 20%-án ugyanígy: 0,240, miközben ugyanazok a modellek
időn kívül 0,101-et tudnak). Az előre rögzített sejtésekből kettő részben nem teljesült (időn
belül a ROC-AUC csak 7/10-szer jobb; a LightGBM kalibrációs eltérése az időbeli teszten +0,78 pp,
az 1 pp-s határ alatt). Nem várt: a tanító időszak időben utolsó 20%-án (2017. dec. – 2018. febr.)
a LightGBM ROC-AUC-ja 0,600, és ott az LR a jobb — a teszt-időszak jósága nem vihető át minden
jövőbeli időszakra. → `tools/felosztas_osszevetes.py`

**ROAR — a fontos tényezők kivétele és újratanítás (okt. 25., `docs/roar_eredmeny.md`).** A K2
törlési görbéje a kész modellen maszkol; itt a magyarázat szerinti k legfontosabb tényező
(k = 1, 2, 3, 5) minden rendelésnél állandó értéket kap a tanításban és a tesztben is, és a modell
újratanul (Hooker és mtsai, 2019). Mind a négy modellnél a vállalt szállítási idő az első;
nélküle a LightGBM ROC-AUC-ja 0,764 → 0,601 (véletlen egy tényező: ±0,005), 3 tényezőnél az esés
LightGBM 0,183 · LR 0,278 · RF 0,246 · fa 0,069. Sejtések: R1 16/16, R3 16/16, R2 10/12 (a döntési
fánál k = 2 és 3 nem — a fa újratanítva maga is ingadozik). → a hűség nem a maszkolás mellékterméke.
→ `tools/roar.py`

**Gazdasági forgatókönyvek (okt. 26., `docs/gazdasagi_forgatokonyv.md`).** Költségadat nincs, ezért
az érték egysége egy elkerült késés értéke (B), a beavatkozás ára c = C/B (1–10%), hatása e (30 és
60%); nettó érték = e · (megjelölt és késett) − c · (megjelölt), a teszt valódi kimenetén. A LightGBM
a felső 1–20%-ban 2,7–3,5-ször annyi késést jelöl meg, mint a véletlen, a pontossága 10–12%; a
beavatkozás csak akkor éri meg, ha c/e e alatt van (pl. e = 0,6, c = 0,02: a 20%-os kapacitás
+7,9 B / 1000 rendelés [2,3; 12,1]; e = 0,3, c = 0,05: minden kapacitás veszteséges). A becsült
valószínűségre épülő küszöb a túlbecsült sávban előjelet fordít (e = 0,6, c = 0,10: várt +12,6,
elért −8,8). LightGBM − LR a 10%-nál nem kimutatható. *A modell* oldalon kalkulátor: a felhasználó
adja meg az árat és a hatást. → `tools/gazdasagi_forgatokonyv.py`

**A felület nem számol fejben.** Minden szám SQL-lekérdezésből vagy a lezárt modellekből
jön, a magyarázó szöveg sablonból készül ugyanezekből a mezőkből (ez lesz a nyelvi réteg
viszonyítási alapja és tartaléka). A kockázatot valószínűségként és relatív kockázatként
(a teszt-időszak átlagos becsléséhez) mutatja, a természetes gyakoriság („100-ból N”)
pedig nem a modell állítását ismétli, hanem azt mondja meg, hogy a **hasonló becslésű
rendelések közül ténylegesen hány késett** (a rendelés saját kimenete nélkül, 95%-os
Wilson-intervallummal). Ha a modell átlagos becslése a sávban ezen az intervallumon kívül
esik, a felület figyelmeztet („ebben a sávban a modell túlbecsült”). Rejtett kimenetnél
ugyanezt a validációs időszakból mutatja — azt egy éles bevezetéskor már ismerni lehetett
volna. A magyarázat a modell döntését bontja tényezőkre — a felület kiírja, hogy ez nem
ok-okozati állítás. → `ui/`, `xai/narrative.py`

**Lezárt alapfutás.** A teszthalmazt eddig sokszor láttuk (döntési napló). A végleges
mérés előtt minden döntés a `docs/v3_protokoll.json`-ban rögzül; a
`python -m pipeline.v3_baseline` csak jóváhagyott, hiánytalan, a kóddal egyező és
commitolt protokollal indul, elmenti a protokoll ujjlenyomatát (SHA256), és csak egyszer fut.
→ `docs/v3_protokoll.md`

---

## Szivárgásvédelem — három szint

| Szint | Mit fog meg | Hol |
|---|---|---|
| Névszűrő | a nyilvánvaló tiltott oszlopokat (`kezbesites`, `review`, `kesett` …) | `assert_no_leakage` |
| As-of illesztés | a még ismeretlen korábbi kimeneteket | `asof_history` |
| AUC-őr | az ártatlan nevű szivárgót: egyetlen jellemző sem adhat önmagában 0,95 fölötti AUC-t | `suspicious_features` |

Mindhármat teszt őrzi. A point-in-time tesztek **nyers erővel újraszámolják**
az előzményt, nem hisznek a pandasnak — és a régi, szivárgó változaton ellenőrzötten elbuknak.

## V-1 validáció — két szigorúsági szint

* **Szerkezeti hiba** (duplikált azonosító, hiányzó fájl, vegyes forrású adat) → azonnali leállás.
* **Sorszintű hiba** (pl. kézbesítés a rendelés előtt) → karantén, ha legfeljebb 0,1%;
  efölött leállás. A karantén a tárház `meta_quarantine` táblájába kerül.

A tárház rögzíti az eredetét is: forrásfájlonként SHA256 és sorszám (`meta_sources`),
valamint hogy szintetikus vagy valós adatból épült (`meta_build`).

---

## Az adat

**Forrás:** *Brazilian E-Commerce Public Dataset by Olist* — Kaggle,
[`olistbr/brazilian-ecommerce`](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
Kb. 99 ezer rendelés 2016 és 2018 között, 9 CSV-fájlban.
**Licenc:** CC BY-NC-SA 4.0 — nem kereskedelmi felhasználás, forrásmegjelöléssel;
a dolgozatban hivatkozni kell rá.

**Letöltés:** automatikus. A `uv run demo.py` első indításkor letölti a `kagglehub`
csomaggal, és a 9 CSV-t a `data\raw\` mappába másolja. Külön is futtatható:

```bash
uv run python -m data.fetch_olist            # letölti, ha még nincs meg
uv run python -m data.fetch_olist --force    # akkor is újra letölti, ha megvan
```

A `kagglehub` a saját gyorsítótárába tölt (`%USERPROFILE%\.cache\kagglehub`), ezért
egy új klónban már nem kell újra letölteni.

**Kézi letöltés** (ha a gépről nem érhető el a Kaggle): a fenti oldalon
**Download**, a ZIP-ből mind a 9 CSV-t a `data\raw\` mappába, majd `uv run demo.py`.

**Védelmek.** A valódi adat soha nem kerül a tárolóba (`.gitignore`). A szintetikus
generátor nem írja felül a valódi adatot. Ha a `data\raw\` mappában valódi és
generált fájlok keverednek, a tárház **vegyes forrású adatot** jelez, és leáll.

## Adatmodell

| Tábla | Egy sor | Mire való |
|---|---|---|
| `fact_order_items` | egy rendelési tétel (egy darab) | minden rendelésszintű összeg forrása |
| `fact_orders` | egy rendelés | a címke, a jellemzők és minden arány |
| `dim_customer`, `dim_seller`, `dim_product`, `dim_date` | dimenziók | állam, koordináta, kategória, méretek, naptár |
| `kizart_rendelesek` | egy nem kézbesített rendelés | státusz, vállalt határidő, lejárt-e a zárónapig |
| `meta_build`, `meta_sources`, `meta_quarantine` | eredet | építés ideje, zárónap, SHA256, karantén |

* **Számlálási szabály:** minden arány és darabszám **rendelést** számol, soha nem tételt.
* **Fő tétel:** a legnagyobb értékű tétel (egyezésnél a legkisebb sorszámú); ebből jön a
  rendelés kategóriája és eladója. A súly és a térfogat az összes tétel összege.
* **Távolság — közelítés:** irányítószám-előtagonként a koordináták **mediánja**, a
  Brazílián kívüli pontok karanténba kerülnek (a valódi adatban 31 pont). A távolság a két
  előtag-pont légvonalbeli távolsága; ha valamelyikhez nincs koordináta (477 rendelés),
  a távolság hiányzó, és a LightGBM ezt natívan kezeli.
* **Megfigyelési zárónap és kizárt rendelések:** a zárónap a nyers adat utolsó eseménye
  (2018-10-17). A fő elemzés csak a kézbesített rendeléseket használja; a többi a
  `kizart_rendelesek` táblába kerül. Az érzékenységi jelentés megmutatja, mi változna,
  ha a lejárt határidejű, még úton lévő rendeléseket (1 729 db) késésnek tekintenénk:

```bash
uv run python -m pipeline.cohort_report      # ablakonként és havonta, 95%-os Wilson-intervallummal
```

| Ablak | A: csak kézbesített | B: + lejárt, még úton lévő = késett |
|---|---|---|
| tanító (–2018-02) | 6,60% | 8,47% |
| validációs (2018-03–05) | 10,11% | 11,70% |
| teszt (2018-06–08) | 3,61% | 4,59% |

A többlet a tanító időszakban a legnagyobb (2017-es rendelések, amelyek a zárónapon is
„feladva" állapotúak) — ez inkább elveszett vagy nem frissített rendelés, mint késés,
ezért a fő elemzés az A változat. A 2018. májusi késési arány 6,56%; az ígért nap szerint
a kamionos-sztrájk ablakába (május 21. – június 10.) eső rendeléseknél 8,08%.

## Jellemzők (22)

Mind a rendelés **leadásakor** ismert. A táblázat a `pipeline/features.py`
`FEATURE_INFO` szótárából készül; egy teszt őrzi, hogy minden jellemzőnek legyen leírása.

| # | Jellemző | Csoport | Mit mér | Forrás |
|---|---|---|---|---|
| 1 | `tetel_szam` | kosár | a rendelés tételeinek száma (darab) | fact_order_items |
| 2 | `elado_szam` | kosár | hány különböző eladótól jön a rendelés | fact_order_items |
| 3 | `kategoria_szam` | kosár | hány különböző termékkategória van a rendelésben | fact_order_items + dim_product |
| 4 | `kosar_ertek` | kosár | a tételek árának összege (BRL) | fact_order_items |
| 5 | `szallitasi_dij` | kosár | a szállítási díjak összege (BRL) | fact_order_items |
| 6 | `dij_arany` | kosár | szállítási díj / kosárérték | számított |
| 7 | `tavolsag_km` | földrajz | eladó–vevő légvonalbeli távolság az irányítószám-előtagok mediánpontja között (közelítés) | geolokáció |
| 8 | `suly_g` | termék | az összes tétel súlyának összege (g) | fact_order_items + dim_product |
| 9 | `terfogat_cm3` | termék | az összes tétel térfogatának összege (cm³) | fact_order_items + dim_product |
| 10 | `vallalt_ido_nap` | ígéret | a platform (Olist) által vállalt szállítási idő (nap) | orders |
| 11 | `honap_sin` | naptár | a rendelés hónapja körön kódolva (szinusz) | orders |
| 12 | `honap_cos` | naptár | a rendelés hónapja körön kódolva (koszinusz) | orders |
| 13 | `het_napja` | naptár | a hét napja (0 = hétfő) | orders |
| 14 | `elado_korabbi_keses_arany` | előzmény | a fő eladó korábbi, MÁR KÉZBESÍTETT rendeléseinek késési aránya (as-of) | fact_orders |
| 15 | `elado_korabbi_rendelesek` | előzmény | a fő eladó korábban leadott rendeléseinek száma | fact_orders |
| 16 | `elado_atlagos_feladas_nap` | előzmény | a fő eladó átlagos feladási ideje a MÁR futárnak átadott korábbi rendelésein (nap, as-of) | fact_orders |
| 17 | `vevo_korabbi_rendelesek` | előzmény | a vevő (customer_unique_id) korábbi rendeléseinek száma | fact_orders |
| 18 | `azonos_allam` | földrajz | az eladó és a vevő ugyanabban az államban van-e | számított |
| 19 | `unnep_kozeli` | naptár | november 20. és december 31. közötti rendelés | dim_date |
| 20 | `kategoria` | termék | a fő tétel (legdrágább tétel) kategóriája | dim_product |
| 21 | `elado_allam` | földrajz | a fő eladó állama | dim_seller |
| 22 | `vevo_allam` | földrajz | a vevő állama | dim_customer |

## Egyenként futtatható lépések

Ez egy lista, nem kell mindet lefuttatni: a mindennapokhoz az első két sor elég. A
parancsokat a projekt gyökeréből futtasd; a `uv run` előbb ellenőrzi (és ha kell,
helyrehozza) a környezetet, aktiválni nem kell. A lezárt futások csak egyszer
indulnak; a hosszú kutatási futások a `docs\` eredményfájljait írják felül — ezek a
felület forrásai.

```bash
uv run python -m pytest -q                    # tesztek (néhány perc)
uv run python -m ui                           # a BI-felület (http://localhost:8501)
uv run python inditas.py --ellenorzes         # mi van meg a futtatáshoz, és mi hiányzik

uv run python -m data.fetch_olist             # valódi adat letöltése (ha még nincs meg)
uv run python -m data.build_warehouse         # tárház + V-1
uv run python -m data.describe_warehouse      # mi van a tárházban (eredet, séma, minta)
uv run python -m pipeline.train               # betanítás a lezárt protokoll szerint
uv run python -m pipeline.train --balance balanced   # súlyozott ág, csak összehasonlításhoz
uv run python -m pipeline.train --drop honap  # abláció: hónap-jellemzők nélkül
uv run python -m pipeline.train --trees korai --no-purge   # a régi út, összehasonlításhoz
uv run python -m pipeline.cohort_report       # kohorsz-érzékenységi jelentés
uv run python -m pipeline.model_selection     # fa-szám bővülő ablakos CV-n (csak a tanító időszak)
uv run python -m pipeline.model_selection --purge    # ugyanez címke-tisztítással
uv run python -m pipeline.reference_models    # a 4 modell összevetése CV-n (csak a tanító időszak)
uv run python -m xai.explain                  # SHAP-összegzés a négy modellre (300 teszt-rendelés)
uv run python -m xai.explain --rendeles RENDELES_KULCS   # egy rendelés a négy modellel (a kulcs a felület Rendelés oldalán: „azonosító”)

# szemantikus réteg (ugyanaz, mint a Kérdezz oldal, felület nélkül)
uv run python -m semantic --katalogus         # a mérőszámok és a bontások listája
uv run python -m semantic --metrika kesesi_arany --bontas vevo_allam --limit 5
uv run python -m semantic --metrika atlagos_szallitasi_ido --bontas honap --szuro vevo_allam=SP --tol 2018-01-01 --ig 2018-06-30 --sql
uv run python -m semantic --metrika haszonkulcs   # a KAPU ① indokolt elutasítása
uv run python -m semantic.pg_ellenorzes       # DuckDB és PostgreSQL eredménye cellánként (Node.js kell; kb. 1 perc)

# nyelvi réteg (helyi nyelvi modellel — lásd: Szabad szöveges kérdés)
uv run python -m narrative --allapot          # elérhető-e a nyelvi modell
uv run python -m narrative "Melyik régióban késnek a legtöbbet?"
uv run python -m narrative "Mekkora volt a forgalom tavaly?" --reszletek   # a modell nyers válaszai és a nézet is
uv run python -m narrative "Mekkora volt a forgalom tavaly?" --modell gemma3:4b   # másik helyi modellel
uv run python -m narrative.proba              # fejlesztői próbasor: 19 kérdés, ítélet és idő kérdésenként (laptopon ~15 perc)
uv run python -m narrative.proba --csak-ertelmezes   # csak az ① hívás (gyorsabb)

# mérés a lezárt kérdéssoron (K1, F-1, F-2) — lásd: Mérés a lezárt kérdéssoron
uv run python -m narrative.meres --ellenoriz  # a kérdéssor és a protokoll állapota (modell nélkül)
uv run python -m narrative.meres --lezar      # a kérdéssor lezárása (egyszer, Viola kérdései után)
uv run python -m narrative.meres --jovahagy "Baranyi Viola"   # a protokoll jóváhagyása
uv run python -m narrative.meres --olvashato  # a kérdéssor olvasható változata (eval\meresi_kerdessor.md)
uv run python -m narrative.meres              # a mérés a qwen3.5:4b-vel (kb. 4–5 óra a laptopon)
uv run python -m narrative.meres --modell qwen3.5:2b   # ugyanez a kisebb modellel
uv run python -m narrative.meres --protokoll docs\k1_protokoll_v2.json   # v2: a v4 az új kérdéssoron
tools\v3_futtatas.bat                         # v2: a v3 ugyanazon (külön munkamappában, v3_kod\)
uv run python tools\k1_v2_osszevetes.py --v4 logs\meres\MAPPA --v3 v3_kod\logs\meres\MAPPA --v4-2b logs\meres\MAPPA   # v2: összevetés → docs\k1_v2_eredmeny.md
uv run python -m narrative.meres --protokoll docs\k1_protokoll_v2_9b.json   # kiegészítés: a qwen3.5:9b ugyanazon a kérdéssoron
uv run python tools\k1_futas_osszevetes.py --a logs\meres\A --b logs\meres\B --cimke-a "9B (GPU)" --cimke-b "4B (GPU)" --protokoll docs\k1_protokoll_v2_9b.json --kimenet docs\k1_9b_eredmeny.md   # két futás párosítva
uv run python -m narrative.meres --protokoll docs\k1_protokoll_v3.json   # v3: a v5 az új kérdéssoron (4B)
tools\v4_futtatas.bat                         # v3: a v4 ugyanazon (külön munkamappában, v4_kod\)
uv run python tools\k1_v3_osszevetes.py --v5 logs\meres\MAPPA --v4 v4_kod\logs\meres\MAPPA [--v5-9b logs\meres\MAPPA]   # v3: összevetés → docs\k1_v3_eredmeny.md
tools\gep_ellenorzes.bat                     # a gép adatai (videókártya, Ollama, modellek) → logs\gep_ellenorzes.txt
uv run python tools\visszajatszas.py logs\meres\MAPPA [MAPPA2 …] --reszletes   # fejlesztés: a tárolt ① válaszok a mostani kódon (optimista, nem mérés)
uv run python tools\kezi_minta.py minta logs\meres\MAPPA       # a kézi ellenőrzés mintája a hatókörrel
uv run python tools\kezi_minta.py kiertekel logs\meres\MAPPA   # a kitöltött minta: a kapu pontossága, K1 korrigálva
uv run python tools\kezi_minta.py osszesit                    # minden kiértékelt minta → docs\k1_kezi_ellenorzes.md
uv run python tools\kapu_atcsuszas.py        # a második kapu véletlen átcsúszása (modell nélkül, kb. 2 perc) → docs\kapu_atcsuszas.*
uv run python tools\felosztas_osszevetes.py  # időbeli vagy véletlen felosztás (kb. 7 perc) → docs\felosztas_osszevetes.*
uv run python tools\dontesi_stabilitas.py    # a legkockázatosabb 10% stabilitása a K3 modelljein (kb. 7 perc) → docs\dontesi_stabilitas.*
uv run python tools\roar.py                  # ROAR: fontos tényezők kivétele és újratanítás (kb. 12 perc) → docs\roar_eredmeny.*
uv run python tools\gazdasagi_forgatokonyv.py  # gazdasági forgatókönyvek (kb. 1 perc) → docs\gazdasagi_forgatokonyv.*
uv run python -m narrative.meres --folytat logs\meres\MAPPA    # megszakadt mérés folytatása (a mappát a mérés kiírja)

# lezárt futások — okt. 9-én lefutottak; újra csak --ismetles kapcsolóval indulnak
uv run python -m pipeline.v3_baseline         # lezárt alapfutás
uv run python -m pipeline.v3_reference        # a referencia-modellek lezárt összevetése a teszten

# hosszú kutatási futások (gépenként kb. fél–egy óra) — a docs\ eredményfájljait írják felül
uv run python -m xai.kernel_arm               # KernelSHAP-kontrollkar (200 rendelés)
uv run python -m xai.faithfulness             # a magyarázatok hűsége: törlési görbe + beültetett jellemző
uv run python -m xai.stability                # a magyarázatok stabilitása: bootstrap-újratanítás + CIES (kb. egy óra)
uv run python -m xai.kernel_arm --rendelesek 20 --zaj 10 --nsamples 512   # gyors próba (pár perc) → artifacts\, a docs\-ot nem írja felül
```

**Abláció.** A `--drop` jellemzőket zár ki a betanításból: csoportnevet (`honap` =
`honap_sin`, `honap_cos`; `naptar` = ezek + `unnep_kozeli`) vagy jellemzőneveket
fogad, vesszővel elválasztva. Elgépelt névre hibát ad — különben a „nélküle" futás
csendben a teljes modell lenne. A jellemzőszerződés (`FEATURES`) nem változik; a
kizárt jellemzők a `metrics.json`-ban, a model cardban és a mappanévben
(`..._minus-honap_seed1`) is látszanak. Több seedes összevetés PowerShellben:

```powershell
foreach ($d in "", "honap") { foreach ($s in 1..5) { uv run python -m pipeline.train --seed $s --tag ablacio --drop "$d" | Out-Null } }
```

A `metrics.json` a teszt mellett a validáció mérőszámait is rögzíti (`validacio`), a
`--trees cv` futásé a keresztvalidáció hajtásait is (`modellvalasztas`). Konfigurációk
között a keresztvalidáción válasszunk, ne a teszten.

A legutóbbi futás artefaktumainak mappanevét az `artifacts\LATEST.txt` tartalmazza.

## Projektstruktúra

```
glassbox-bi/
├── demo.py                  teljes pipeline egy paranccsal
├── inditas.py               indító bármely gépen: előkészíti, ami hiányzik, és megnyitja a felületet
├── indit_felulet.bat        az indító Windowson (dupla kattintással; a uv-t is telepíti)
├── indit_felulet.sh         az indító macOS-en és Linuxon: sh indit_felulet.sh
├── frissit.bat              uv (ha kell) + uv sync + tesztek Windowson; napló: logs\frissites.log
├── data/
│   ├── fetch_olist.py       a valódi Olist-adat letöltése (kagglehub)
│   ├── make_synthetic.py    szintetikus adat a CI-hez és a tesztekhez
│   ├── build_warehouse.py   CSV → csillagséma, V-1 validáció, eredet
│   ├── describe_warehouse.py  a tárház tartalma
│   └── db.py                kapcsolat, érthető hibaüzenetek
├── pipeline/
│   ├── features.py          22 jellemző + jellemzőtáblázat, as-of előzmények, szivárgásvédelem
│   ├── split.py             időbeli szétvágás, bővülő ablakos CV, címke-tisztítás
│   ├── train.py             LightGBM, kalibrációs diagnosztika, model card
│   ├── model_selection.py   fa-szám a tanító időszakon belül (bővülő ablakos CV)
│   ├── bootstrap.py         heti blokk-bootstrap (egyes és páros)
│   ├── v3_baseline.py       a lezárt v3 alapfutás (csak jóváhagyott protokollal)
│   ├── reference_models.py  logisztikus regresszió, döntési fa, random forest + CV-választás
│   ├── v3_reference.py      a referencia-modellek lezárt összevetése (páros bootstrap)
│   └── cohort_report.py     kohorsz-érzékenységi jelentés (kizárt rendelések)
├── xai/
│   ├── models.py            a négy végső modell a lezárt beállításokkal (gyorsítótárazva)
│   ├── explain.py           SHAP a négy modellre, a 22 jellemzőre összevonva; százalékpont
│   ├── kernel_arm.py        KernelSHAP-kontrollkar: a négy modell ugyanazzal a magyarázóval
│   ├── agreement.py         két magyarázat egyezése: top-k, RBO, súlyozott Kendall-tau
│   ├── faithfulness.py      a magyarázatok hűsége: törlési/beszúrási görbe, beültetett jel és zaj
│   ├── stability.py         a magyarázatok stabilitása: bootstrap-újratanítás, kontroll-mag, CIES
│   ├── deadline.py          határidő-görbe: a becslés a vállalt szállítási idő függvényében (a DiCE helyett)
│   ├── labels.py            brazil államok (+ térképrács), magyar kategórianevek, a tényezők és modellek hétköznapi leírása
│   └── narrative.py         rövid nevek, magyar számalak, sablonos magyarázó szöveg
├── semantic/
│   ├── katalogus.toml       a metrikakatalógus: mérőszámok, bontások, kapcsolatok, amit az adat nem tud
│   ├── catalog.py           a katalógus betöltése és ellenőrzése, fehérlista az adatból, értékek nevei
│   ├── spec.py              a kérdés gépi alakja (QuerySpec) és a KAPU ①
│   ├── builder.py           SQL a szintaxisfából (DuckDB + PostgreSQL), utólagos SQL-őr
│   ├── engine.py            futtatás, MetricResult (a lefuttatott SQL-lel, Wilson-tartománnyal)
│   ├── answer.py            sablonos válasz: minden szám hivatkozással a payloadra
│   ├── pg_ellenorzes.py     a PostgreSQL-változat ellenőrzése (tools/pg futtatja)
│   └── __main__.py          python -m semantic: ugyanez parancssorból
├── tools/pg/                a PostgreSQL-ellenőrzés futtatója (Node.js + PGlite, rögzített verzió)
├── narrative/               nyelvi réteg (M4): kliens, ① kérdés → gépi alak, ② eredmény → mondat, KAPU ②, próba (proba.py), mérés (meres.py), időkifejezések (idoszak.py), köznyelvi szótár (szotar.py)
├── prompts/                 a hívások promptja, verziózva (v1 és v2; a ② kontrollágának külön prompt: to_text_szabad)
├── eval/                    fejlesztői próbasor (hangolásra) és a mérési kérdéssor (lezárva; K1)
├── configs/llm.toml         a nyelvi modell beállítása (helyi Ollama vagy API; a kulcs a .env-ben)
├── ui/
│   ├── app.py               a felület belépési pontja (oldalsáv, navigáció)
│   ├── __main__.py          python -m ui: indítás localhoston, statisztika nélkül
│   ├── oldalak/             Áttekintés, Rendelés kockázata, A modell, Kérdezz, Súgó és fogalmak
│   ├── backend.py           adatréteg: SQL + modellek (Streamlit nélkül is tesztelhető)
│   ├── charts.py            grafikonok (Altair)
│   └── common.py            gyorsítótárazott betöltők, oldalsáv
├── docs/
│   ├── dontesi_naplo.md     minden módszertani döntés: mikor, miért, látta-e már a tesztet
│   ├── v3_protokoll.json    a lezárt futás protokollja (gépi, ezt ellenőrzi a futás)
│   ├── v3_protokoll.md      ugyanez magyarázattal és a döntésekkel
│   ├── k1_protokoll.json    a nyelvi réteg mérésének protokollja (jóváhagyva okt. 16.; a lezárt kérdéssor ujjlenyomatával)
│   ├── k1_eredmeny_*.md     a K1 mérés jelentése modellenként (és .json)
│   ├── v3_lezart_eredmeny.json  a lezárt futás teljes eredménye (ujjlenyomattal)
│   ├── v3_lezart_eredmeny.md    ugyanez röviden, táblázattal
│   ├── v3_referencia_protokoll.json  a referencia-összevetés protokollja
│   ├── v3_referencia_protokoll.md    ugyanez magyarázattal és a CV-eredménnyel
│   ├── v3_referencia_eredmeny.json   a referencia-összevetés teljes eredménye
│   ├── v3_referencia_eredmeny.md     ugyanez röviden, táblázattal
│   ├── kernel_kar_eredmeny.json      a KernelSHAP-kontrollkar eredménye (a 200 rendelés helyett a részhalmaz ujjlenyomatával)
│   ├── kernel_kar_eredmeny.md        ugyanez táblázatokkal
│   ├── huseg_eredmeny.json           a hűségmérés eredménye (rendelés-azonosítók nélkül)
│   ├── huseg_eredmeny.md             ugyanez táblázatokkal
│   ├── stabilitas_eredmeny.json      a stabilitásmérés eredménye (rendelés-azonosítók nélkül)
│   ├── stabilitas_eredmeny.md        ugyanez táblázatokkal
│   ├── kapu_atcsuszas.json           a második kapu véletlen átcsúszása (kérdésenként)
│   ├── kapu_atcsuszas.md             ugyanez táblázatokkal
│   ├── dontesi_stabilitas.json       a legkockázatosabb 10% stabilitása (rendelés-azonosítók nélkül)
│   ├── dontesi_stabilitas.md         ugyanez táblázatokkal
│   ├── felosztas_osszevetes.json     időbeli vagy véletlen felosztás
│   ├── felosztas_osszevetes.md       ugyanez táblázatokkal
│   ├── roar_eredmeny.json            ROAR: kivétel és újratanítás (modellenként, k-nként, a véletlen készletekkel)
│   ├── roar_eredmeny.md              ugyanez táblázatokkal
│   ├── gazdasagi_forgatokonyv.json   gazdasági forgatókönyvek (kapacitás, küszöb, bizonytalanság)
│   ├── gazdasagi_forgatokonyv.md     ugyanez táblázatokkal
│   ├── pg_ellenorzes.json            DuckDB és PostgreSQL összevetése (a katalógus ujjlenyomatával)
│   └── pg_ellenorzes.md              ugyanez röviden
├── .github/workflows/       CI: minden push lefuttatja a teljes pipeline-t (szintetikus adaton)
├── LICENSE                  MIT (a kódra; az adat saját licenc alatt áll)
├── pyproject.toml           a projekt: Python 3.14, közvetlen függőségek, uv- és pytest-beállítások
├── uv.lock                  minden csomag pontos verzióval (Windows + Linux) — ebből épít a uv
├── requirements.txt         a közvetlen függőségek pip-nek (= a pyproject.toml listája)
├── requirements.lock        a pontos változatok pip-nek (a uv.lock-ból exportálva; a CI ezt telepíti)
├── .python-version          3.14
├── CITATION.cff             hogyan hivatkozzanak a munkára
├── .env.example             minta a későbbi LLM-kulcsokhoz (a .env sosem kerül be)
├── .streamlit/config.toml   a felület beállításai (csak localhost, statisztika nélkül)
└── tests/
    ├── test_no_leakage.py   14 teszt (szivárgás, point-in-time, jellemzőtáblázat)
    ├── test_warehouse.py    10 teszt (V-1, két ténytábla, fő tétel, geolokáció, zárónap)
    ├── test_ablation.py     6 teszt (az abláció tényleg kizár-e)
    ├── test_train.py        6 teszt (alapbeállítás = a lezárt protokoll, nincs kalibrátor, diagnosztika)
    ├── test_cohort.py       2 teszt (Wilson-intervallum, érzékenységi változat)
    ├── test_model_selection.py  8 teszt (hajtások, fa-szám szabály, címke-tisztítás, a validáció nem hat)
    ├── test_bootstrap.py    6 teszt (egész hetek, reprodukálhatóság, páros összevetés)
    ├── test_v3_baseline.py  14 teszt (protokoll-kapu, ujjlenyomat, commit-ellenőrzés, egyszeri futás)
    ├── test_reference_models.py  9 teszt (modellek, rácsok, a választás csak a tanító ablakot látja, lezárt összevetés)
    ├── test_explain.py      12 teszt (additivitás, egyezés a shap könyvtárral, oszlopcsoportok, gyorsítótár)
    ├── test_narrative.py    22 teszt (magyar számalak, hónap-visszafejtés, összevonás, sablonos szöveg, a becslés hitelessége)
    ├── test_ui.py           22 teszt (adatréteg, a gazdasági kalkulátor, a döntés stabilitásának, a felosztásnak és a ROAR-nak a táblái, becslési sávok és csoportjaik, grafikonok világos/sötét témában, térkép, magyar számalak a tengelyeken, magyar súgó minden ábrarétegen, „kevés adat” sáv, minden oldal lefut — Streamlit AppTest)
    ├── test_agreement.py    5 teszt (RBO a definíció szerint, top-k, előjel, súlyozott tau, bootstrap)
    ├── test_labels.py       5 teszt (mind a 27 állam, minden valódi kategóriának van magyar neve, leírások, térképrács)
    ├── test_kernel_arm.py   5 teszt (a 21 játékos tere bitre visszaalakítható, additív modellre pontos, additivitás, nincs csendes szűkítés, a próbafutás nem írja felül a lezárt eredményt)
    ├── test_faithfulness.py 8 teszt (maszkok, additív modellen pontos görbe és a Shapley-sorrend a legjobb, beültetés, erős jel megtalálása, kis futás, felületi táblák, a próbafutás nem írja felül a lezárt eredményt)
    ├── test_stability.py    6 teszt (a CIES kézzel számolt példán, a zaj csak a számszerű jellemzőket éri, a bootstrap-minta, kis teljes futás a felület tábláival és ábrájával és a két feltáró változattal — ugyanazok a húzások, az egész értékű jellemzők egészek maradnak —, a páros különbség olvasata, a próbafutás nem ír a docs\-ba)
    ├── test_deadline.py     4 teszt (a saját értéknél pontosan a becslés mind a négy modellnél, csak a vállalt idő változik és a logisztikus regresszió logitja egyenes, a tanult tartomány és a rácson kívüli érték, összegzés, ábra, backend)
    ├── test_kapu_atcsuszas.py 3 teszt (a kitalált szám alakja és tartománya, a kapu a valódi értéket átengedi, a távolit nem, kis futás determinisztikusan, jelentés)
    ├── test_felosztas_osszevetes.py 3 teszt (a felső 10% és a mérőszámok kézzel számolt példán, a felosztások mérete, diszjunktsága, determinizmusa, az időrendi belső ellenőrzés csak eldőlt címkén tanul, kis futás, jelentés, a próbafutás nem ír a docs\-ba)
    ├── test_dontesi_stabilitas.py 3 teszt (holtverseny és azonos becslés, ismert csere kézzel számolva, kis futás: a mag-független LR kontrollja pontosan 1, jelentés)
    ├── test_gazdasagi_forgatokonyv.py 4 teszt (nettó érték és kapacitás kézzel számolva, küszöbszabály: várt és elért, heti blokk-bootstrap, kis futás, jelentés)
    ├── test_roar.py         3 teszt (a kivétel csak a megadott oszlopokat írja át, a hónapnál mindkettőt, a kategóriák listája megmarad; determinisztikus véletlen készletek; kis futás: kivétel nélkül a lezárt modell jön vissza, összegzés, jelentés)
    ├── test_readme.py       2 teszt (a README parancsai PowerShellben is bemásolhatók: nincs <…> helyőrző)
    ├── test_kornyezet.py    8 teszt (a tároló mappájában lévő külön munkamappák (v3_kod\, v4_kod\) és virtuális környezetek kimaradnak; a uv.lock és a requirements.lock ugyanazt rögzíti, Python 3.14 mindenhol, nincs gépfüggő útvonal a tárolóban, a két Windows-parancsfájl CRLF-es és nem hivatkozik virtuális környezetre)
    ├── test_semantic.py     99 teszt (a katalógus és a hibás katalógusok, fehérlista és írásmódok, a KAPU ① minden elutasítási kódja, SQL-őr, idézés, minden szám egyezik egy független pandas-számolással, Wilson-tartomány, kevés adat, determinizmus, a válasz minden száma visszavezethető, ábrák magyar súgóval, a Kérdezz oldal végigkattintva, PostgreSQL-összevetés)
    ├── test_nyelvi_reteg.py 81 teszt (időkifejezések, a kód javításai a modell űrlapján — a valódi modell okt. 16-i három futásának válaszain is (`tests/adat`), az állam szerepe, a kérdésben nem említett szűrő, előrejelzés-elutasítás, minimális nézet, ezres tagolás sima szóközzel, mondathatár, tartomány-szerep, rövid dátum, csúcs és hónapnév, többes számú felsőfok, a szűrés tagadása, ismételt érték; a kliens kérése az Ollamának és az API-nak, tartás, kontextusméret, időbontás, előtöltés, újrapróbálás, állapot, napló; ① séma és prompt a katalógusból mindkét változatban, a v2 rövidebb és nem nő az adattal, a régi prompt is fut, a példák érvényesek, ragozott értékek feloldása, kétértelmű szónál nincs találgatás, a hosszú lista csak a javító körbe kerül, javító kör csak formai hibára, elutasítás akkor is, ha a modell „közeli” mérőszámot választana, a kérdés adat, nem utasítás; ② keret a kódtól, jelölők, a KAPU ② elkapja a kitalált számot, jelölőt, a felcserélt csoportértéket, a hamis „legmagasabb”-at akkor is, ha a név előtte áll, az oksági állítást; ragozott nevek; kontrollág saját prompttal; a fejlesztői próbasor és parancsa; a teljes út; a szabad szöveges fül — Streamlit AppTest)
    └── conftest.py          közös szintetikus tárház és modellek a fenti tesztekhez
```

## A tároló közzététele

A mappa készen áll: `.gitignore`, licenc, hivatkozási adatok és CI-beállítás már
benne van. A GitHubra kerüléshez a mappa gyökeréből:

```bash
git init
git add .
git status          # csak forrásfájlok jelenhetnek meg — adat és artefaktum nem
git commit -m "Glassbox BI - adattarhaz, jellemzok, baseline, tesztek"
git branch -M main
git remote add origin https://github.com/ViolaBaranyi/glassbox-bi.git
git push -u origin main
```

A GitHubon **Private** tárolóként kezdd, üres inicializálással (ne kérj README-t,
`.gitignore`-t vagy licencet — mind megvan). A TDK előtt egy kattintással
átállítható publikusra: Settings → General → Change visibility.

### Folyamatos ellenőrzés (CI)

Az első push után a `.github/workflows/tests.yml` minden feltöltésnél lefuttatja a
teljes pipeline-t Python 3.14-en, Ubuntun és Windowson, **szintetikus adaton**
(`python demo.py --synthetic`), mert a valódi adat nem kerülhet a tárolóba:
adatgenerálás, tárházépítés V-1 validációval, a teljes tesztsor, betanítás, kohorsz-jelentés.
A csomagokat a `requirements.lock` rögzíti (a `uv.lock` pip-nek exportált párja,
ugyanazokkal a változatokkal). Ha egy teszt
elbukik, a futás pirosra vált, és a GitHub e-mailt küld. Ez a szivárgásvédelem
hálója: egy elrontott jellemző nem maradhat észrevétlen.

## Másik gépre

**Csak a forrást kell átvinni** (gittel). Az adat, a tárház, az artefaktumok és a
virtuális környezet mind újraépülnek; a `.gitignore` pontosan ezeket zárja ki.

| Átvinni | NEM átvinni | Miért |
|---|---|---|
| minden, ami a tárolóban van | `.venv\` | gépfüggő (az adott gép Pythonjára és mappájára mutat) — a uv gépenként újraépíti |
| | `data\raw\`, `data\*.duckdb` | a demó első indításkor újra letölti az adatot, a tárházat minden futás újraépíti |
| | `artifacts\` | a betanítás újra előállítja |

Az új gépen (Windowson, PowerShellben):

```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # egyszer; utána új ablak
git clone https://github.com/ViolaBaranyi/glassbox-bi.git
cd glassbox-bi
uv sync
uv run demo.py
```

Pythont külön telepíteni nem kell: ha a gépen nincs 3.14-es, a uv letölti a saját
mappájába (a rendszer Pythonjához nem nyúl).

**uv nélkül, pip-pel** (a CI így fut): Python 3.14 kell a python.org-ról („Add
python.exe to PATH”), utána:

```powershell
py -3.14 -m venv --clear .venv       # a --clear egy régi .venv-et előbb kiürít
.venv\Scripts\Activate.ps1
pip install -r requirements.lock     # ugyanazok a változatok, mint a uv.lock-ban
python demo.py
```

Ilyenkor a parancsok `uv run` nélkül, a bekapcsolt környezetben futnak.

### Ellenőrzés: egyeznek-e a számok?

A pipeline determinisztikus, tehát az új gépen a `uv run demo.py` összegzésében
**ugyanezeket** kell látnod (Windowson és Linuxon is így jött ki):

```
Tárház         96,470 rendelés, 2016-09-15 .. 2018-08-29
V-1 validáció  rendben, karantén: Brazílián kívüli koordináta: 31
Kizárva        2,971 nem kézbesített rendelés (zárónap 2018-10-17; ...)
Tesztek        mind átment
Modell         LightGBM, 22 jellemző, 119 fa (bővülő ablakos CV, címke-tisztítással), súlyozás: none
Rangsorolás    PR-AUC 0.098  (bázisráta 0.036, 2.7x)  ROC-AUC 0.764
Kalibráció     ECE 0.008 (egyenlő elemszámú sávokkal 0.010)   Brier 0.0339, készség 3.8%
```

Ez a lezárt v3 alapfutás elsődleges modellje (mag 42) — a számok egyeznek a
`docs/v3_lezart_eredmeny.md`-vel. A modellválasztás önmagában (csak a tanító időszakot
olvassa): `uv run python -m pipeline.model_selection --purge` → medián 118,5 → **119 fa**
(címke-tisztítás nélkül: 66,5 → 67 fa).

A `--synthetic` futás (és a CI) összegzése: 38,857 rendelés, 22 jellemző, 50 fa (itt az
alsó korlát dönt), PR-AUC 0.202, ROC-AUC 0.726.

A felületen (`uv run python -m ui`) *A modell* oldal tetején zöld jelzésnek kell lennie: a
felület modelljei a lezárt futásokéi (LightGBM teszt PR-AUC 0,09782, logisztikus
regresszió 0,08363, döntési fa 0,06088, random forest 0,08796).

Ha egyeznek, az átvitel hibátlan. Ha nem, a demó 1. lépése kiírja a Python- és
csomagverziókat — azzal kezdd a keresést.

## Licenc és hivatkozás

A kód MIT licenc alatt áll (`LICENSE`). Az Olist adathalmaz **nem** része a
tárolónak, és a saját licence alatt áll (CC BY-NC-SA 4.0, lásd [Az adat](#az-adat));
a dolgozatban hivatkozni kell rá.

A munkára való hivatkozás adatait a `CITATION.cff` tartalmazza; a GitHub ebből
„Cite this repository" gombot tesz a tároló oldalára.

## Hibaelhárítás

Először az indító ellenőrző módja: `indit_felulet.bat --ellenorzes` (macOS, Linux: `sh indit_felulet.sh --ellenorzes`) sorra veszi, mi van meg és mi hiányzik.

### Windows

**„Importing the numpy C-extensions failed” (az üzenetben `cp313`), „No module named
'_duckdb'”, „No module named streamlit”** — a parancs nem a rögzített környezetben fut,
hanem egy régi, kézzel készült `.venv`-ben (egy korábbi Python csomagjaival) vagy a gép
saját Pythonjában. Megoldás a projekt gyökeréből:

```powershell
deactivate                           # ha a sor elején (.venv) vagy (.venv-1) látszik
Remove-Item -Recurse -Force .venv    # a régi környezet; a uv újat épít
uv sync
uv run python -m pytest -q
```

**„uv: The term 'uv' is not recognized”** — az ablak a uv telepítése előtt nyílt meg:
nyiss újat (a telepítő a PATH-hoz adja a uv-t).

**„No module named data"** — a parancsokat a projekt gyökeréből futtasd
(a `demo.py`-ra ez nem vonatkozik).

**„A tárházfájlt egy másik program zárolja"** — zárd be a kapcsolatot a DBeaverben
vagy a PyCharm adatbázis-paneljén.

**„A projekt a Python 3.14-re van rögzítve"** — a demó más Python-verzióval is fut, de
figyelmeztet: a bitre azonos számok csak a rögzített környezetben garantáltak
(`uv run demo.py`).

**„Port 8501 is already in use"** — már fut egy felület (egy másik ablakban), vagy más
program foglalja a portot: `uv run python -m ui --server.port 8502`.

**„Az Olist adathalmaz letöltése nem sikerült"** — nincs internet, vagy a hálózat
(pl. egyetemi proxy) nem engedi a Kaggle-t. A hibaüzenet leírja a kézi letöltést;
lásd [Az adat](#az-adat).

### macOS, Linux

**„Library not loaded: @rpath/libomp.dylib”** (macOS) — a LightGBM-hez kell az OpenMP:
`brew install libomp` (ha nincs Homebrew: https://brew.sh). Az indító ezt fel is ismeri, és
ugyanezt írja ki.

**„libgomp.so.1: cannot open shared object file”** (Linux) — `sudo apt install libgomp1`
(Fedorán: `sudo dnf install libgomp`).

**„Permission denied”** a `./indit_felulet.sh`-ra — futtasd így: `sh indit_felulet.sh` (ehhez
nem kell futtatási jog).

**„$'\r': command not found”** — a parancsfájl Windowsos sorvégekkel került a gépre (pl.
OneDrive-on vagy pendrive-on át másolva). Gittel klónozva ez nem fordul elő
(`.gitattributes`); másolat esetén: `sed -i.bak 's/\r$//' indit_felulet.sh`.

**„curl: … 403” vagy a uv telepítése nem sikerül** — a hálózat nem engedi az astral.sh-t; a
kézi telepítés: https://docs.astral.sh/uv/getting-started/installation/ (pl. `brew install uv`
vagy `pipx install uv`), utána `uv run python inditas.py`.
