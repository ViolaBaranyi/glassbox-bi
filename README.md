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

**Python 3.14** (rögzítve: `pyproject.toml`, `.python-version`).

```bash
py -3.14 -m venv .venv               # Windows; Linuxon: python3.14 -m venv .venv
.venv\Scripts\activate               # PowerShellben: .venv\Scripts\Activate.ps1
pip install -r requirements.lock     # pontosan a kipróbált változatok
python demo.py
```

A `requirements.lock` minden csomagot pontos verzióval rögzít (Windowsra és Linuxra
is) — ezzel jönnek ki bitre ugyanazok a számok. A `requirements.txt` csak a közvetlen
függőségeket sorolja fel, alsó korláttal.

Első indításkor a `demo.py` letölti a valódi Olist-adatot a Kaggle-ről (kb. 45 MB,
Kaggle-fiók nem kell), utána egy-két perc alatt végigfuttatja a teljes pipeline-t,
és a végén összegzést ír ki. A további indítások a már letöltött adatot használják.
PyCharmban a zöld **Run** gombbal is indítható.

## Mit csinál a demó

| # | Lépés | Mit bizonyít |
|---|---|---|
| 1 | Környezet | a verziók rögzítve vannak a kimenetben |
| 2 | Adat | a valódi Olist-adat; ha még nincs meg, letölti a Kaggle-ről |
| 3 | Tárház | 9 CSV → csillagséma DuckDB-ben, **V-1 validációval** |
| 4 | Tesztek | 66 teszt: szivárgásvédelem, V-1, adatmodell, abláció, betanítás, kohorsz, modellválasztás, bootstrap, lezárt futás; ha bármelyik bukik, **a demó megáll** |
| 5 | Betanítás | a **lezárt v3 protokoll** szerint: LightGBM súlyozás nélkül, a fák száma bővülő ablakos CV-vel, címke-tisztítással; érintetlen, legkésőbbi időszakon mérve; a kalibráció csak diagnosztika |
| 6 | Összegzés | rangsorolás, kalibráció, kizárt rendelések, artefaktumok helye |

**Valódi adat nélkül:** `python demo.py --synthetic` azonos szerkezetű, generált
adaton futtatja végig a gépezetet. Erre a CI-nek és a teszteknek van szüksége, mert
a valódi adat nem kerülhet a tárolóba. A szintetikus adat nem a valóság: a kimenet
ilyenkor minden lépésben jelzi, hogy a számok csak a gépezet működését mutatják.

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
| Tesztek — szivárgás (14), V-1 és adatmodell (10), abláció (6), betanítás (6), kohorsz (2), modellválasztás (8), bootstrap (6), lezárt futás (14) | **kész, 66/66** |
| Tároló — MIT licenc, CI (Ubuntu + Windows), `requirements.lock`, döntési napló | **kész** |
| M2 — 40 futásos sweep, hiperparaméter-hangolás | következő |
| M3 — SHAP, ellenpélda, stabilitás | következő |
| M1 — szemantikus réteg (KAPU ①) | tervezett |
| M4 — nyelvi réteg és ellenőrző (KAPU ②) | tervezett |
| M5 — Streamlit felület | tervezett |

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
tehát a „7%" jelentsen 7%-ot. A súlyozás nélküli modell nyers kimenete magától is jól
kalibrált; egy validáción illesztett izotonikus kalibrátor viszont az időbeli
alapráta-eltolódás miatt (validáció 10,1%, teszt 3,6%) rontana rajta. Ezért nincs
kalibrátor, és a SHAP pontosan a megjelenített számot bontja fel. A kalibráció csak
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

**Bizonytalanság heti blokk-bootstrappal, a tanítási véletlen külön.** A késések hétről
hétre együtt mozognak, ezért egész heteket húzunk visszatevéssel (B = 2000, percentilis
95%); a rendelésenkénti újramintavétel hamisan szűk intervallumot adna. A modell
magjából eredő szórást öt maggal, külön jelentjük. → `pipeline/bootstrap.py`

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
python -m pipeline.cohort_report      # ablakonként és havonta, 95%-os Wilson-intervallummal
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

```bash
python -m data.fetch_olist             # valódi adat letöltése (ha még nincs meg)
python -m data.build_warehouse         # tárház + V-1
python -m data.describe_warehouse      # mi van a tárházban (eredet, séma, minta)
python -m pytest tests/ -v             # tesztek
python -m pipeline.train               # betanítás a lezárt protokoll szerint
python -m pipeline.train --balance balanced   # súlyozott ág, csak összehasonlításhoz
python -m pipeline.train --drop honap  # abláció: hónap-jellemzők nélkül
python -m pipeline.cohort_report       # kohorsz-érzékenységi jelentés
python -m pipeline.model_selection     # fa-szám bővülő ablakos CV-n (csak a tanító időszak)
python -m pipeline.model_selection --purge    # ugyanez címke-tisztítással
python -m pipeline.train --trees korai --no-purge   # a régi út, összehasonlításhoz
python -m pipeline.v3_baseline         # lezárt alapfutás (okt. 9-én lefutott; újra csak --ismetles)
```

**Abláció.** A `--drop` jellemzőket zár ki a betanításból: csoportnevet (`honap` =
`honap_sin`, `honap_cos`; `naptar` = ezek + `unnep_kozeli`) vagy jellemzőneveket
fogad, vesszővel elválasztva. Elgépelt névre hibát ad — különben a „nélküle" futás
csendben a teljes modell lenne. A jellemzőszerződés (`FEATURES`) nem változik; a
kizárt jellemzők a `metrics.json`-ban, a model cardban és a mappanévben
(`..._minus-honap_seed1`) is látszanak. Több seedes összevetés PowerShellben:

```powershell
foreach ($d in "", "honap") { foreach ($s in 1..5) { python -m pipeline.train --seed $s --tag ablacio --drop "$d" | Out-Null } }
```

A `metrics.json` a teszt mellett a validáció mérőszámait is rögzíti (`validacio`), a
`--trees cv` futásé a keresztvalidáció hajtásait is (`modellvalasztas`). Konfigurációk
között a keresztvalidáción válasszunk, ne a teszten.

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
│   ├── features.py          22 jellemző + jellemzőtáblázat, as-of előzmények, szivárgásvédelem
│   ├── split.py             időbeli szétvágás, bővülő ablakos CV, címke-tisztítás
│   ├── train.py             LightGBM, kalibrációs diagnosztika, model card
│   ├── model_selection.py   fa-szám a tanító időszakon belül (bővülő ablakos CV)
│   ├── bootstrap.py         heti blokk-bootstrap (egyes és páros)
│   ├── v3_baseline.py       a lezárt v3 alapfutás (csak jóváhagyott protokollal)
│   └── cohort_report.py     kohorsz-érzékenységi jelentés (kizárt rendelések)
├── docs/
│   ├── dontesi_naplo.md     minden módszertani döntés: mikor, miért, látta-e már a tesztet
│   ├── v3_protokoll.json    a lezárt futás protokollja (gépi, ezt ellenőrzi a futás)
│   ├── v3_protokoll.md      ugyanez magyarázattal és a döntésekkel
│   ├── v3_lezart_eredmeny.json  a lezárt futás teljes eredménye (ujjlenyomattal)
│   └── v3_lezart_eredmeny.md    ugyanez röviden, táblázattal
├── .github/workflows/       CI: minden push lefuttatja a teljes pipeline-t (szintetikus adaton)
├── LICENSE                  MIT (a kódra; az adat saját licenc alatt áll)
├── requirements.txt         közvetlen függőségek, alsó korláttal
├── requirements.lock        minden csomag pontos verzióval (Python 3.14, Windows + Linux)
├── .python-version          3.14
├── CITATION.cff             hogyan hivatkozzanak a munkára
├── .env.example             minta a későbbi LLM-kulcsokhoz (a .env sosem kerül be)
├── pyproject.toml           pytest-beállítások
└── tests/
    ├── test_no_leakage.py   14 teszt (szivárgás, point-in-time, jellemzőtáblázat)
    ├── test_warehouse.py    10 teszt (V-1, két ténytábla, fő tétel, geolokáció, zárónap)
    ├── test_ablation.py     6 teszt (az abláció tényleg kizár-e)
    ├── test_train.py        6 teszt (alapbeállítás = a lezárt protokoll, nincs kalibrátor, diagnosztika)
    ├── test_cohort.py       2 teszt (Wilson-intervallum, érzékenységi változat)
    ├── test_model_selection.py  8 teszt (hajtások, fa-szám szabály, címke-tisztítás, a validáció nem hat)
    ├── test_bootstrap.py    6 teszt (egész hetek, reprodukálhatóság, páros összevetés)
    └── test_v3_baseline.py  14 teszt (protokoll-kapu, ujjlenyomat, commit-ellenőrzés, egyszeri futás)
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
teljes pipeline-t Python 3.14-en, Ubuntun és Windowson, **szintetikus adaton**
(`python demo.py --synthetic`), mert a valódi adat nem kerülhet a tárolóba:
adatgenerálás, tárházépítés V-1 validációval, 37 teszt, betanítás, kohorsz-jelentés.
A csomagokat a `requirements.lock` rögzíti. Ha egy teszt
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

1. **Python 3.14** a python.org-ról — telepítéskor pipáld be az
   *„Add python.exe to PATH"* dobozt.
2. Ezután:

```bash
git clone https://github.com/<felhasznalonev>/glassbox-bi.git
cd glassbox-bi
py -3.14 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.lock
python demo.py
```

PyCharmban: File → Project from Version Control → beilleszted a linket; a PyCharm
felajánlja a virtuális környezet létrehozását a `requirements.txt` alapján.

### Ellenőrzés: egyeznek-e a számok?

A pipeline determinisztikus, tehát az új gépen a `python demo.py` összegzésében
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
olvassa): `python -m pipeline.model_selection --purge` → medián 118,5 → **119 fa**
(címke-tisztítás nélkül: 66,5 → 67 fa).

A `--synthetic` futás (és a CI) összegzése: 38,857 rendelés, 22 jellemző, 50 fa (itt az
alsó korlát dönt), PR-AUC 0.202, ROC-AUC 0.726.

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

**„A projekt a Python 3.14-re van rögzítve"** — a demó más Python-verzióval is fut, de
figyelmeztet: a bitre azonos számok csak a rögzített környezetben garantáltak
(`py -3.14 -m venv .venv`, `pip install -r requirements.lock`).

**„Az Olist adathalmaz letöltése nem sikerült"** — nincs internet, vagy a hálózat
(pl. egyetemi proxy) nem engedi a Kaggle-t. A hibaüzenet leírja a kézi letöltést;
lásd [Az adat](#az-adat).
