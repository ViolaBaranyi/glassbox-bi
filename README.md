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

Ajánlott: **Python 3.11, 3.12 vagy 3.13**.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (PowerShellben: .venv\Scripts\Activate.ps1)
pip install -r requirements.txt
python demo.py
```

Első indításkor a `demo.py` letölti a valódi Olist-adatot a Kaggle-ről (kb. 45 MB,
Kaggle-fiók nem kell), utána kb. egy perc alatt végigfuttatja a teljes pipeline-t,
és a végén összegzést ír ki. A további indítások a már letöltött adatot használják.
PyCharmban a zöld **Run** gombbal is indítható.

## Mit csinál a demó

| # | Lépés | Mit bizonyít |
|---|---|---|
| 1 | Környezet | a verziók rögzítve vannak a kimenetben |
| 2 | Adat | a valódi Olist-adat; ha még nincs meg, letölti a Kaggle-ről |
| 3 | Tárház | 9 CSV → csillagséma DuckDB-ben, **V-1 validációval** |
| 4 | Tesztek | 26 teszt: szivárgásvédelem, V-1 és abláció; ha bármelyik bukik, **a demó megáll** |
| 5 | Betanítás | LightGBM + izotonikus kalibráció, érintetlen, legkésőbbi időszakon mérve |
| 6 | Összegzés | rangsorolás, kalibráció, artefaktumok helye |

**Valódi adat nélkül:** `python demo.py --synthetic` azonos szerkezetű, generált
adaton futtatja végig a gépezetet. Erre a CI-nek és a teszteknek van szüksége, mert
a valódi adat nem kerülhet a tárolóba. A szintetikus adat nem a valóság: a kimenet
ilyenkor minden lépésben jelzi, hogy a számok csak a gépezet működését mutatják.

---

## Mi van kész

| Modul | Állapot |
|---|---|
| M0 — adattárház, V-1 validáció, adateredet (SHA256) | **kész** |
| M0 — a valódi adat automatikus letöltése (`data/fetch_olist.py`) | **kész** |
| M2 — jellemzők, point-in-time korrekt (as-of illesztés) | **kész** |
| M2 — időbeli szétvágás, bővülő ablakos CV | **kész** |
| M2 — LightGBM baseline, kalibráció, determinisztikus futás | **kész** |
| M2 — abláció (`--drop`), validációs mérőszámok a `metrics.json`-ban | **kész** |
| Tesztek — szivárgás (13), V-1 (7), abláció (6) | **kész, 26/26** |
| M2 — 40 futásos sweep, hiperparaméter-hangolás | következő |
| M3 — SHAP, ellenpélda, stabilitás | következő |
| M1 — szemantikus réteg (KAPU ①) | tervezett |
| M4 — nyelvi réteg és ellenőrző (KAPU ②) | tervezett |
| M5 — Streamlit felület | tervezett |

---

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

**Korai leállítás kizárólag PR-AUC-ra.** A `class_weight="balanced"` mellett az
alapértelmezett logloss azonnal romlik a validáción, és pár fa után megállítaná
a tanítást. → `pipeline/train.py`, `PARAMS`

**Kalibráció.** A felületen valószínűséget mutatunk, tehát a „72%" jelentsen
72%-ot. Izotonikus regresszió a validáción, ECE és megbízhatósági táblázat a teszten.

**Determinisztikus futás.** `deterministic=True`, `force_row_wise=True`:
azonos adat + mag → bitre azonos modell.

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

**Letöltés:** automatikus. A `python demo.py` első indításkor letölti a `kagglehub`
csomaggal, és a 9 CSV-t a `data\raw\` mappába másolja. Külön is futtatható:

```bash
python -m data.fetch_olist            # letölti, ha még nincs meg
python -m data.fetch_olist --force    # akkor is újra letölti, ha megvan
```

A `kagglehub` a saját gyorsítótárába tölt (`%USERPROFILE%\.cache\kagglehub`), ezért
egy új klónban már nem kell újra letölteni.

**Kézi letöltés** (ha a gépről nem érhető el a Kaggle): a fenti oldalon
**Download**, a ZIP-ből mind a 9 CSV-t a `data\raw\` mappába, majd `python demo.py`.

**Védelmek.** A valódi adat soha nem kerül a tárolóba (`.gitignore`). A szintetikus
generátor nem írja felül a valódi adatot. Ha a `data\raw\` mappában valódi és
generált fájlok keverednek, a tárház **vegyes forrású adatot** jelez, és leáll.

## Egyenként futtatható lépések

```bash
python -m data.fetch_olist             # valódi adat letöltése (ha még nincs meg)
python -m data.build_warehouse         # tárház + V-1
python -m data.describe_warehouse      # mi van a tárházban (eredet, séma, minta)
python -m pytest tests/ -v             # tesztek
python -m pipeline.train               # betanítás
python -m pipeline.train --balance none  # súlyozás nélkül (összehasonlításhoz)
python -m pipeline.train --balance none --drop honap   # abláció: hónap-jellemzők nélkül
```

**Abláció.** A `--drop` jellemzőket zár ki a betanításból: csoportnevet (`honap` =
`honap_sin`, `honap_cos`; `naptar` = ezek + `unnep_kozeli`) vagy jellemzőneveket
fogad, vesszővel elválasztva. Elgépelt névre hibát ad — különben a „nélküle" futás
csendben a teljes modell lenne. A jellemzőszerződés (`FEATURES`) nem változik; a
kizárt jellemzők a `metrics.json`-ban, a model cardban és a mappanévben
(`..._minus-honap_seed1`) is látszanak. Több seedes összevetés PowerShellben:

```powershell
foreach ($d in "", "honap") { foreach ($s in 1..5) { python -m pipeline.train --balance none --seed $s --tag ablacio --drop "$d" | Out-Null } }
```

A `metrics.json` a teszt mellett a validáció mérőszámait is rögzíti
(`validacio_kalibralatlan`): konfigurációk közti választás ezen történjen, ne a teszten.

A legutóbbi futás artefaktumainak mappanevét az `artifacts\LATEST.txt` tartalmazza.

## Projektstruktúra

```
glassbox-bi/
├── demo.py                  teljes pipeline egy paranccsal
├── data/
│   ├── fetch_olist.py       a valódi Olist-adat letöltése (kagglehub)
│   ├── make_synthetic.py    szintetikus adat a CI-hez és a tesztekhez
│   ├── build_warehouse.py   CSV → csillagséma, V-1 validáció, eredet
│   ├── describe_warehouse.py  a tárház tartalma
│   └── db.py                kapcsolat, érthető hibaüzenetek
├── pipeline/
│   ├── features.py          jellemzők, as-of előzmények, szivárgásvédelem
│   ├── split.py             időbeli szétvágás, bővülő ablakos CV
│   └── train.py             LightGBM, kalibráció, model card
├── .github/workflows/       CI: minden push lefuttatja a teljes pipeline-t
├── LICENSE                  MIT (a kódra; az adat saját licenc alatt áll)
├── CITATION.cff             hogyan hivatkozzanak a munkára
├── .env.example             minta a későbbi LLM-kulcsokhoz (a .env sosem kerül be)
├── pyproject.toml           pytest-beállítások
└── tests/
    ├── test_no_leakage.py   13 teszt
    ├── test_warehouse.py    7 teszt
    └── test_ablation.py     6 teszt (az abláció tényleg kizár-e)
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
git remote add origin https://github.com/<felhasznalonev>/glassbox-bi.git
git push -u origin main
```

A GitHubon **Private** tárolóként kezdd, üres inicializálással (ne kérj README-t,
`.gitignore`-t vagy licencet — mind megvan). A TDK előtt egy kattintással
átállítható publikusra: Settings → General → Change visibility.

### Folyamatos ellenőrzés (CI)

Az első push után a `.github/workflows/tests.yml` minden feltöltésnél lefuttatja a
teljes pipeline-t Python 3.11-en és 3.12-n, **szintetikus adaton**
(`python demo.py --synthetic`), mert a valódi adat nem kerülhet a tárolóba:
adatgenerálás, tárházépítés V-1 validációval, 26 teszt, betanítás. Ha egy teszt
elbukik, a futás pirosra vált, és a GitHub e-mailt küld. Ez a szivárgásvédelem
hálója: egy elrontott jellemző nem maradhat észrevétlen.

## Másik gépre

**Csak a forrást kell átvinni.** Az adat, a tárház, az artefaktumok és a virtuális
környezet mind újraépülnek; a `.gitignore` pontosan ezeket zárja ki.

| Átvinni | NEM átvinni | Miért |
|---|---|---|
| minden, ami a tárolóban van | `.venv\` | gépfüggő, abszolút útvonalakkal |
| | `data\raw\`, `data\*.duckdb` | a demó első indításkor újra letölti az adatot, a tárházat minden futás újraépíti |
| | `artifacts\` | a betanítás újra előállítja |

Az új gépen:

1. **Python 3.11, 3.12 vagy 3.13** a python.org-ról — telepítéskor pipáld be az
   *„Add python.exe to PATH"* dobozt.
2. Ezután:

```bash
git clone https://github.com/<felhasznalonev>/glassbox-bi.git
cd glassbox-bi
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python demo.py
```

PyCharmban: File → Project from Version Control → beilleszted a linket; a PyCharm
felajánlja a virtuális környezet létrehozását a `requirements.txt` alapján.

### Ellenőrzés: egyeznek-e a számok?

A pipeline determinisztikus, tehát az új gépen a `python demo.py` összegzésében
**ugyanezeket** kell látnod (Windowson és Linuxon is így jött ki):

```
Tárház         96,470 rendelés, 2016-09-15 .. 2018-08-29
V-1 validáció  rendben, karanténban 0 sor
Tesztek        mind átment                     (26 teszt)
Modell         LightGBM, 20 jellemző, 56 fa, súlyozás: balanced
Rangsorolás    PR-AUC 0.083  (bázisráta 0.036, 2.3x)  ROC-AUC 0.744
Kalibráció     ECE 0.278 -> 0.035   Brier 0.118 -> 0.036
```

A `--synthetic` futás (és a CI) összegzése: 38,857 rendelés, 27 fa,
PR-AUC 0.211, ROC-AUC 0.728.

Ha egyeznek, az átvitel hibátlan. Ha nem, a demó 1. lépése kiírja a Python- és
csomagverziókat — azzal kezdd a keresést.

## Licenc és hivatkozás

A kód MIT licenc alatt áll (`LICENSE`). Az Olist adathalmaz **nem** része a
tárolónak, és a saját licence alatt áll (CC BY-NC-SA 4.0, lásd [Az adat](#az-adat));
a dolgozatban hivatkozni kell rá.

A munkára való hivatkozás adatait a `CITATION.cff` tartalmazza; a GitHub ebből
„Cite this repository" gombot tesz a tároló oldalára.

## Hibaelhárítás (Windows)

**„No module named data"** — a parancsokat a projekt gyökeréből futtasd
(a `demo.py`-ra ez nem vonatkozik).

**„A tárházfájlt egy másik program zárolja"** — zárd be a kapcsolatot a DBeaverben
vagy a PyCharm adatbázis-paneljén.

**„Az Olist adathalmaz letöltése nem sikerült"** — nincs internet, vagy a hálózat
(pl. egyetemi proxy) nem engedi a Kaggle-t. A hibaüzenet leírja a kézi letöltést;
lásd [Az adat](#az-adat).
