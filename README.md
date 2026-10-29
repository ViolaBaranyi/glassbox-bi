# Üvegdoboz BI (Glassbox BI)

**Megmagyarázható MI és nyelvi modell egy önkiszolgáló BI-rendszerben.**
Kutatási prototípus (EKÖP-26-I-1), Eszterházy Károly Katolikus Egyetem.

A rendszer egy brazil webáruház (Olist) rendeléseiről mutatja meg, mennyi késik, hol és
miért, és előre jelzi, mely rendelések késhetnek. A számokat mindig determinisztikus réteg
(SQL és a lezárt modellek) állítja elő; a nyelvi modell csak megfogalmaz, a magyarázó réteg
megindokol, és két kapu ellenőrzi, hogy a szövegbe ne kerüljön az eredmény által alá nem
támasztott szám.

## Gyorsindítás

Egy parancs, bármely gépen. A parancsfájl telepíti a [uv](https://docs.astral.sh/uv/)-t, ha még
nincs; a uv a rögzített változatokból (`uv.lock`) előállítja a Python 3.14-et és a csomagokat;
az `inditas.py` előkészíti, ami hiányzik (adat, tárház, modellek), és megnyitja a felületet a
böngészőben (**http://localhost:8501**).

| Gép | Parancs (a projekt mappájában) |
|---|---|
| Windows | `indit_felulet.bat` (dupla kattintás is jó) |
| macOS, Linux | `sh indit_felulet.sh` |
| bármelyik, ha a uv már megvan | `uv run python inditas.py` |

Hasznos kapcsolók: `--ellenorzes` (csak megnézi, mi van meg és mi hiányzik), `--szintetikus`
(internet nélkül, generált adattal), `--modell` (letölti a nyelvi modellt, ha fut az Ollama),
`--port 8502`, `--help`. Az első indítás a letöltésekkel együtt néhány perc, utána fél percen
belül nyílik a felület. Leállítás: Ctrl+C, vagy zárd be az ablakot.

A uv kézi telepítése (ha a parancsfájl nem tudja; utána új ablak kell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows
curl -LsSf https://astral.sh/uv/install.sh | sh                                      # macOS, Linux
```

### Mi kell a futtatáshoz

| Mi | Kötelező? | Megjegyzés |
|---|---|---|
| Gép | igen | Windows 10/11 (x64), macOS 12+ (Apple Silicon és Intel), Linux (x64); Windows ARM-on nem fut |
| Szabad hely | igen | kb. 1,2 GB |
| uv, Python 3.14, csomagok | igen | a parancsfájl és a uv telepíti, rendszergazda nélkül |
| libomp (csak macOS) | igen | `brew install libomp` (a LightGBM-hez) |
| libgomp (csak Linux) | általában megvan | ha nincs: `sudo apt install libgomp1` |
| Internet | első indításkor | a csomagokhoz és az adathoz (kb. 45 MB, Kaggle-fiók nem kell) |
| Ollama + `qwen3.5:4b` | nem | csak a szabad szöveges kérdéshez (3,4 GB); nélküle a bemutató mód működik |

## A felület

| Oldal | Mit mutat |
|---|---|
| Áttekintés | a késési arány havonta, államonként és kategóriánként, bizonytalansági sávval és térképen |
| Rendelés kockázata | egy rendelés becsült kockázata, a hasonló becslésűek tényleges kimenete, a tényezők (SHAP) és a határidő-görbe, négy modellel |
| A modell | a teszt-kiértékelés, kalibráció, mi számít a modelleknek, mennyire hűek és stabilak a magyarázatok, gazdasági kalkulátor |
| Kérdezz | kérdés a rendelésekről kérdésépítővel vagy szabad szöveggel; válasz, ábra, táblázat és a lefuttatott SQL |
| Súgó és fogalmak | fogalomtár, a tényezők, az államok és a kategóriák magyarul, mire nem alkalmas |

Minden szám mellett megnézhető, honnan jön (a lekérdezés vagy a lezárt eredményfájl). A felület
csak ezen a gépen érhető el, és használati statisztikát nem küld.

### Szabad szöveges kérdés (helyi nyelvi modell)

A *Kérdezz* oldal *Szabad szöveggel* fülén magyarul lehet kérdezni. A kérdést egy helyi nyelvi
modell fordítja gépi alakra; az **1. kapu** a metrikakatalógushoz és az adatból készült
fehérlistához méri (amit nem lehet kiszámolni, arra indokolt elutasítás jön, szám nélkül); a
számokat SQL adja; a modell a válaszba jelölőket ír, a számokat a gép illeszti be; a **2. kapu**
ellenőrzi, hogy a szöveg minden száma visszavezethető-e az eredményre. Az adat nem hagyja el a
gépet.

1. Telepítsd az Ollamát: https://ollama.com/download
2. Töltsd le a modellt (egyszer, kb. 3,4 GB): `ollama pull qwen3.5:4b`
3. Indítsd újra a felületet.

**Nyelvi modell nélkül — bemutató mód.** A fülön a „Bemutató mód” kapcsolóval a harmadik mérés
50 kérdése választható: a nyelvi modell kimenete a mérésből jön (`docs/bemutato_valaszok.json`),
minden más — a kapuk, a lekérdezés, a számok beillesztése — most fut le. Ha nincs modell, a
kapcsoló alapból be van kapcsolva.

## Eredmények röviden

| Kérdés | Eredmény | Részletek |
|---|---|---|
| Mennyire jó a késés-előrejelzés? | a lezárt teszten (2018. jún.–aug., 3,6% késés) PR-AUC 0,098 [0,055; 0,127], ROC-AUC 0,764; a rangsorolás hasznos, a pontos valószínűség a farokban nem | `docs/v3_lezart_eredmeny.md` |
| Kell-e a bonyolult modell? | a logisztikus regresszió nem kimutathatóan rosszabb (PR-AUC 0,084) | `docs/v3_referencia_eredmeny.md` |
| Hű-e a magyarázat a modellhez? (K2) | igen: a törlési próbán 100%-ban jobb a véletlennél, a KernelSHAP-pal egyenértékű, a beültetett jelet mind a négy modellnél megtalálja | `docs/huseg_eredmeny.md`, `docs/roar_eredmeny.md` |
| Stabil-e a magyarázat? (K3) | az iránya igen (92–100%), a sorrendje közepesen (RBO 0,75–0,93) | `docs/stabilitas_eredmeny.md` |
| Véd-e a kapu? (K1) | a kapu által felismert hibás szöveg nem jut el a felhasználóhoz; a kapu által nem látott hibákkal együtt a fő modellnél a válaszok kb. 9–14%-a alátámasztatlan (kapu nélkül 31–48%), a legkisebb modell első változatánál 42% | `docs/k1_kezi_ellenorzes.md` |

A mérések előre rögzített protokoll szerint készültek; minden módszertani döntés, és hogy a
döntés látta-e már a teszthalmazt, a `docs/dontesi_naplo.md`-ben van.

## Az adat

*Brazilian E-Commerce Public Dataset by Olist* — Kaggle,
[`olistbr/brazilian-ecommerce`](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce):
kb. 99 ezer rendelés 2016 és 2018 között, 9 CSV-fájlban. Licenc: CC BY-NC-SA 4.0 (nem
kereskedelmi felhasználás, forrásmegjelöléssel). Az adat nem része a tárolónak.

Az indító (vagy a `uv run demo.py`) első indításkor letölti a `data/raw/` mappába. Ha a gépről
nem érhető el a Kaggle: a fenti oldalon **Download**, és a ZIP-ből mind a 9 CSV-t a
`data/raw/` mappába kell másolni.

## Hasznos parancsok

A projekt mappájából; a `uv run` előbb rendbe teszi a környezetet, aktiválni nem kell.

```bash
uv run python inditas.py                      # előkészítés és a felület
uv run python -m pytest -q                    # a teljes tesztsor (néhány perc)
uv run demo.py                                # adat, tárház, tesztek, betanítás, összegzés
uv run demo.py --synthetic                    # ugyanez generált adaton (valódi adat nélkül)
uv run python -m semantic --metrika kesesi_arany --bontas vevo_allam --limit 5   # egy kérdés felület nélkül
uv run python -m narrative "Melyik régióban késnek a legtöbbet?"                 # szabad szöveges kérdés (Ollama kell)
```

A mérések és elemzések futtatói a `tools/`, `pipeline/` és `xai/` mappában vannak, az
eredményük a `docs/` mappában (ezekből olvas a felület is).

### Egyeznek-e a számok?

A futás determinisztikus. A `uv run demo.py` összegzésében a valódi adaton ezt kell látni
(Windowson és Linuxon is így jön ki): 96 470 rendelés, 22 jellemző, 119 fa, PR-AUC 0,098,
ROC-AUC 0,764. Generált adaton (`--synthetic`): 38 857 rendelés, 50 fa, PR-AUC 0,202,
ROC-AUC 0,726. A felületen *A modell* oldal tetején zöld jelzés mutatja, hogy a felület
modelljei a lezárt futáséi.

## A tároló felépítése

```
data/        letöltés, szintetikus adat, DuckDB-tárház (csillagséma) és validáció
pipeline/    jellemzők, időbeli felosztás, betanítás, modellválasztás, referencia-modellek
xai/         a négy modell magyarázata (SHAP), hűség, stabilitás, határidő-görbe, magyar feliratok
semantic/    metrikakatalógus, 1. kapu, SQL-építő (DuckDB és PostgreSQL), sablonos válasz
narrative/   nyelvi réteg: kérdés → gépi alak, eredmény → szöveg, 2. kapu, mérőpad
ui/          Streamlit-felület
tools/       az előre rögzített mérések és elemzések futtatói
docs/        protokollok, eredmények, döntési napló
eval/        a fejlesztői és a lezárt mérési kérdéssorok
tests/       automatikus tesztek
```

A környezetet a `pyproject.toml` és a `uv.lock` rögzíti (pip-nek: `requirements.lock`). A
GitHub minden feltöltésnél lefuttatja a teljes folyamatot generált adaton, Ubuntun és
Windowson (`.github/workflows/`).

## Licenc és hivatkozás

A kód MIT licenc alatt áll (`LICENSE`). Az Olist-adat a saját licence alatt áll (CC BY-NC-SA
4.0). A hivatkozás adatai a `CITATION.cff`-ben vannak.

## Hibaelhárítás

Először: `uv run python inditas.py --ellenorzes` sorra veszi, mi van meg és mi hiányzik.

- **„uv: The term 'uv' is not recognized”** — az ablak a uv telepítése előtt nyílt meg: nyiss újat.
- **„No module named …”, „numpy C-extensions failed”** — a parancs nem a projekt környezetében
  fut. A projekt mappájában: `Remove-Item -Recurse -Force .venv` (macOS/Linux: `rm -rf .venv`),
  majd `uv sync`.
- **„Port 8501 is already in use”** — már fut egy felület; az indító magától a következő szabad
  portot választja.
- **„A tárházfájlt egy másik program zárolja”** — zárd be a DBeavert vagy az IDE adatbázis-paneljét.
- **„Library not loaded: @rpath/libomp.dylib”** (macOS) — `brew install libomp`.
- **„libgomp.so.1: cannot open shared object file”** (Linux) — `sudo apt install libgomp1`.
- **„$'\r': command not found”** (macOS/Linux) — a parancsfájl Windowsos sorvégekkel került a
  gépre (pl. pendrive-on át): `sed -i.bak 's/\r$//' indit_felulet.sh`.
- **Az Olist-adat letöltése nem sikerül** — nincs internet, vagy a hálózat nem engedi a Kaggle-t:
  kézi letöltés ([Az adat](#az-adat)), vagy `--szintetikus`.
