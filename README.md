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

Ajánlott: **Python 3.11 vagy 3.12**.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (PowerShellben: .venv\Scripts\Activate.ps1)
pip install -r requirements.txt
python demo.py
```

A `demo.py` kb. 10 másodperc alatt végigfuttatja a teljes pipeline-t, és a végén
összegzést ír ki. PyCharmban a zöld **Run** gombbal is indítható.

## Mit csinál a demó

| # | Lépés | Mit bizonyít |
|---|---|---|
| 1 | Környezet | a verziók rögzítve vannak a kimenetben |
| 2 | Adat | ha nincs valódi adat, azonos alakú szintetikusat generál |
| 3 | Tárház | 9 CSV → csillagséma DuckDB-ben, **V-1 validációval** |
| 4 | Tesztek | 20 teszt: szivárgásvédelem és V-1; ha bármelyik bukik, **a demó megáll** |
| 5 | Betanítás | LightGBM + izotonikus kalibráció, érintetlen, legkésőbbi időszakon mérve |
| 6 | Összegzés | rangsorolás, kalibráció, artefaktumok helye |

> **A szintetikus adat nem a valóság.** A kapott számok a gépezet működését
> mutatják. Ahol szintetikus adat fut, azt a kimenet minden lépésben jelzi.

---

## Mi van kész

| Modul | Állapot |
|---|---|
| M0 — adattárház, V-1 validáció, adateredet (SHA256) | **kész** |
| M2 — jellemzők, point-in-time korrekt (as-of illesztés) | **kész** |
| M2 — időbeli szétvágás, bővülő ablakos CV | **kész** |
| M2 — LightGBM baseline, kalibráció, determinisztikus futás | **kész** |
| Tesztek — szivárgás (13) és V-1 (7) | **kész, 20/20** |
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

## Valódi adatra váltás

1. Töltsd le a *Brazilian E-Commerce Public Dataset by Olist* adathalmazt a Kaggle-ről.
   **Ellenőrizd a licencet**, és hivatkozz rá a dolgozatban.
2. Másold mind a 9 CSV-t a `data\raw\` mappába (a szintetikusak helyére).
3. Futtasd: `python demo.py`

A kód egy sorát sem kell átírni. Ha csak néhány fájlt cserélsz, a tárház
**vegyes forrású adatot** jelez, és leáll — szándékosan.

## Egyenként futtatható lépések

```bash
python -m data.make_synthetic          # szintetikus adat
python -m data.build_warehouse         # tárház + V-1
python -m data.describe_warehouse      # mi van a tárházban (eredet, séma, minta)
python -m pytest tests/ -v             # tesztek
python -m pipeline.train               # betanítás
python -m pipeline.train --balance none  # súlyozás nélkül (összehasonlításhoz)
```

A legutóbbi futás artefaktumainak mappanevét az `artifacts\LATEST.txt` tartalmazza.

## Projektstruktúra

```
glassbox-bi/
├── demo.py                  teljes pipeline egy paranccsal
├── data/
│   ├── make_synthetic.py    Olist-alakú szintetikus adat + ujjlenyomat
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
    └── test_warehouse.py    7 teszt
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
teljes pipeline-t Python 3.11-en és 3.12-n: adatgenerálás, tárházépítés V-1
validációval, 20 teszt, betanítás. Ha egy teszt elbukik, a futás pirosra vált, és
a GitHub e-mailt küld. Ez a szivárgásvédelem hálója: egy elrontott jellemző nem
maradhat észrevétlen.

## Másik gépre

**Csak a forrást kell átvinni.** Az adat, a tárház, az artefaktumok és a virtuális
környezet mind újraépülnek; a `.gitignore` pontosan ezeket zárja ki.

| Átvinni | NEM átvinni | Miért |
|---|---|---|
| minden, ami a tárolóban van | `.venv\` | gépfüggő, abszolút útvonalakkal |
| | `data\raw\`, `data\*.duckdb` | a generátor rögzített maggal dolgozik: ugyanaz jön ki |
| | `artifacts\` | a betanítás újra előállítja |

Az új gépen:

1. **Python 3.11 vagy 3.12** a python.org-ról — telepítéskor pipáld be az
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

A pipeline determinisztikus, tehát az új gépen **ugyanezeket** kell látnod:

```
Tárház         38,857 rendelés, 2017-01-01 .. 2018-08-30
Tesztek        mind átment                     (20 teszt)
Modell         LightGBM, 20 jellemző, 27 fa
Rangsorolás    PR-AUC 0.211  (bázisráta 0.077, 2.7x)  ROC-AUC 0.728
Kalibráció     ECE 0.371 -> 0.009   Brier 0.210 -> 0.067
```

Ha egyeznek, az átvitel hibátlan. Ha nem, a demó 1. lépése kiírja a Python- és
csomagverziókat — azzal kezdd a keresést.

## Licenc és hivatkozás

A kód MIT licenc alatt áll (`LICENSE`). Az Olist adathalmaz **nem** része a
tárolónak, és a saját feltételei alatt áll — azokat a forrásoldalon kell
ellenőrizni, és a dolgozatban hivatkozni rá.

A munkára való hivatkozás adatait a `CITATION.cff` tartalmazza; a GitHub ebből
„Cite this repository" gombot tesz a tároló oldalára.

## Hibaelhárítás (Windows)

**„No module named data"** — a parancsokat a projekt gyökeréből futtasd
(a `demo.py`-ra ez nem vonatkozik).

**„A tárházfájlt egy másik program zárolja"** — zárd be a kapcsolatot a DBeaverben
vagy a PyCharm adatbázis-paneljén.
