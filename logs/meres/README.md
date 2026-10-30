# A nyelvi réteg méréseinek (K1) naplói

Itt van a dolgozat mind a tíz K1-futása, változatlanul, ahogy a mérőprogram
(`narrative/meres.py`) kiírta. A `docs/k1_*` eredményfájlok ezekből készültek, és ezekből
modell nélkül újraszámolhatók (lásd lent). A mappa neve a futás kezdete és a modell.

## Mi van egy futás mappájában

| Fájl | Tartalom |
|---|---|
| `fej.json` | a futás fejléce: modell és modellfájl-azonosító (digest), hőmérsékletek, a protokoll, a kérdéssor és a promptok SHA-256-ja, a kód commitja és ujjlenyomata, ismétlések száma |
| `sorok.jsonl` | egy sor = egy kérdés egy ismétlése: a modell nyers űrlapja, a kód javításai, az 1. kapu döntése, a lekérdezés, és mindkét ág (fő ág jelölőkkel, kontrollág jelölők nélkül) szövege a 2. kapu ítéletével és az időkkel |
| `osszegzes.json`, `jelentes.md` | a mérőprogram összesítése és olvasható jelentése |
| `kezi_ellenorzes.csv` | a vak kézi ellenőrzés mintája, a szerző kitöltésével (van-e alá nem támasztott állítás, melyik, megjegyzés) |
| `kezi_ellenorzes_kulcs.csv` | a minta kulcsa (melyik ág, megjelölte-e a kapu); a kitöltés alatt külön fájlban volt |
| `kezi_ellenorzes_utmutato.txt` | az értékelési útmutató, ahogy a kitöltéskor szólt |
| `kezi_ellenorzes_eredmeny.json` | a kitöltött minta kiértékelése (`tools/kezi_minta.py kiertekel`) |

## A futások

| Mappa | Mérés | Nyelvi réteg | Modell | Gép | Kézi minta | Eredmény |
|---|---|---|---|---|---|---|
| `20261016_1426_qwen3.5-4b` | 1. | v3 | 4B | laptop, processzor | van | `docs/k1_eredmeny_qwen3.5-4b.md` |
| `20261019_0910_qwen3.5-2b` | 1. | v3 | 2B | laptop, processzor | van | `docs/k1_eredmeny_qwen3.5-2b.md` |
| `20261020_1300_qwen3.5-4b` | 2. | v4 | 4B | laptop, processzor | van | `docs/k1_v2_eredmeny.md` |
| `20261020_1400_qwen3.5-4b` | 2. | v3¹ | 4B | laptop, processzor | — | `docs/k1_v2_eredmeny.md` |
| `20261020_1404_qwen3.5-2b` | 2. | v4 | 2B | laptop, processzor | van | `docs/k1_v2_eredmeny.md` |
| `20261022_1040_qwen3.5-4b` | 2., ismétlés | v4 | 4B | videókártya | — | `docs/k1_v2_gepvaltas.md`, `docs/k1_9b_eredmeny.md` |
| `20261022_1115_qwen3.5-9b` | 2., kiegészítő | v4 | 9B | videókártya | — | `docs/k1_9b_eredmeny.md` |
| `20261022_1902_qwen3.5-4b` | 3. | v5 | 4B | videókártya | van | `docs/k1_v3_eredmeny.md` |
| `20261022_1911_qwen3.5-4b` | 3. | v4¹ | 4B | videókártya | — | `docs/k1_v3_eredmeny.md` |
| `20261022_1919_qwen3.5-9b` | 3., kiegészítő | v5 | 9B | videókártya | — | `docs/k1_v3_eredmeny.md` |

¹ A korábbi kódváltozat külön munkamappában futott (`v3_kod/`, `v4_kod/`, git worktree); a
naplót onnan, változatlanul másoltuk ide. Melyik kód futott, a `fej.json` commitja és
ujjlenyomata mutatja.

A kézi minták összesítése: `docs/k1_kezi_ellenorzes.md`. A harmadik mérés 4B-futásából készül
a felület bemutató módja is (`docs/bemutato_valaszok.json`).

**Hibajegyzék, `20261019_0910_qwen3.5-2b`.** A `kezi_ellenorzes_elcserelt.csv` az a kitöltött
fájl, amely először e futás mintájaként szerepelt, de valójában az első mérés 4B-mintájának 60
szövegét tartalmazza (mind a 60 egyezik a `20261016_1426` minta azonos kódú sorával, e futás
naplójával egy sem). A helyes minta a `kezi_ellenorzes.csv`; a szerző vakon értékelte újra.
Részletek: `docs/dontesi_naplo.md`, 2026-10-29.

## Újraszámolás (modell nélkül)

Az összevető eszközök a tárházat is használják (`uv run python inditas.py` vagy
`uv run demo.py` építi fel). Alapból a `docs/` fájljait írják felül; ha csak össze akarod
vetni, adj meg más helyet a `--kimenet` kapcsolóval.

```bash
uv run python tools/kezi_minta.py osszesit
uv run python tools/k1_v2_osszevetes.py --v4 logs/meres/20261020_1300_qwen3.5-4b --v3 logs/meres/20261020_1400_qwen3.5-4b --v4-2b logs/meres/20261020_1404_qwen3.5-2b
uv run python tools/k1_futas_osszevetes.py --a logs/meres/20261022_1040_qwen3.5-4b --b logs/meres/20261020_1300_qwen3.5-4b --cimke-a "4B (videókártya)" --cimke-b "4B (laptop, processzor)" --protokoll docs/k1_protokoll_v2.json --kimenet docs/k1_v2_gepvaltas.md --cim "Gépváltás: a v4 4B a laptop processzorán és a videókártyán (ugyanaz a modellfájl, kód és kérdéssor)"
uv run python tools/k1_futas_osszevetes.py --a logs/meres/20261022_1115_qwen3.5-9b --b logs/meres/20261022_1040_qwen3.5-4b --cimke-a "9B (GPU)" --cimke-b "4B (GPU)" --protokoll docs/k1_protokoll_v2_9b.json --kimenet docs/k1_9b_eredmeny.md --cim "K1 v2 kiegészítés: a qwen3.5:9b és a qwen3.5:4b ugyanazon a gépen, kérdésenként párosítva"
uv run python tools/k1_v3_osszevetes.py --v5 logs/meres/20261022_1902_qwen3.5-4b --v4 logs/meres/20261022_1911_qwen3.5-4b --v5-9b logs/meres/20261022_1919_qwen3.5-9b
```

Az első mérés jelentései (`docs/k1_eredmeny_qwen3.5-*.md`) a két futás `jelentes.md`-jének
másolatai. **Ezeken a mappákon ne futtasd** a `narrative.meres --jelentes` parancsot: az a
jelentéssel együtt a kézi mintát is újraírja, üresen (ha mégis megtörtént: `git checkout -- logs/meres`).

Az eszközök a tárolt ítéleteket újra is számolják, és jelzik, ha a naplóban lévő ítélet
eltér attól, amit a kód most mond (mindegyiknél 0 eltérés). A fájlok sorvégeit a git nem
alakítja át (`.gitattributes`: `logs/meres/** -text`), így a naplók bájtra azonosak a mért
állapottal.
