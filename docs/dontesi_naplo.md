# Döntési napló

Minden módszertani döntés ide kerül: mikor, mi, miért, és **látta-e már a döntés a
teszthalmazt**. A teszthalmaz (2018. jún.–aug.) a végső mérésre szolgál; ha egy
döntés a teszteredmény ismeretében született, azt a dolgozatban korlátként kell
közölni („forking paths").

A valódi Olist-adat tesztjét először **2026. szeptember 29-én** láttuk; előtte csak
szintetikus adaton futott a rendszer.

| Dátum | Döntés | Látta a tesztet? | Elvetett alternatíva | Indok / bizonyíték |
|---|---|---|---|---|
| 2026-09-22 | Eladói előzmény as-of illesztéssel, a kimenet ismertté válásának időpontjára | nem (szintetikus) | csak „korábban leadott" szűrés | az első változatban a rendelések kb. 53%-a még ismeretlen kimenetet látott; nyers erős teszt őrzi |
| 2026-09-22 | Korai leállítás kizárólag PR-AUC-ra | nem (szintetikus) | logloss + PR-AUC | a súlyozott ágon a logloss 7 fánál megállította a tanítást |
| 2026-09-22 | Dátumok ISO 8601 szerint, számolt értelmezési hibákkal | nem (szintetikus) | `errors="coerce"` | vegyes formátumnál csendes sorvesztés |
| 2026-09-29 | Valódi adat, időbeli vágás: tanító –2018-02, validáció 2018-03–05, teszt 2018-06– | igen (első valódi futás) | véletlen vágás | a valóságban múltból jósolunk; a vágás dátumai a rendszertervből jönnek, nem a teszt alapján |
| 2026-10-02 | **Súlyozás nélküli tanítás, utólagos kalibrátor nélkül** (témavezetői H1) | **igen** | `balanced` + izotonikus kalibrátor | 5 magon: nyers ECE 0,008 vs 0,279; az izotonikus kalibrátor rontott (0,038). Teszttől független indok: a validáción belül éles a törés (március 19,0% → április 4,5%), egy validáción illesztett kalibrátor ezt tanulja meg |
| 2026-10-02 | Hónap-jellemzők maradnak, „időszaki hatásként" közölve | **igen** | kivenni őket | az ablációban csak a teszten látszik a hasznuk (PR-AUC 0,093 vs 0,058); a validáción fordított, a tanítón belüli CV-n nincs különbség → korlátként közöljük |
| 2026-10-02 | Két ténytábla (tétel- és rendelésszint), fő tétel = legdrágább, súly/térfogat összeg, +2 jellemző | nem (témavezetői H2, H4) | első tétel | a rendelés egy sora ne függjön a tételek sorrendjétől |
| 2026-10-02 | Geolokáció: medián + Brazília-keret | nem (témavezetői H6) | átlag | 31 pont Brazílián kívül; 229 előtagnál > 10 km eltolódás az átlaghoz képest |
| 2026-10-08 | Fő kohorsz: csak kézbesített rendelések (v2); a lejárt határidejű, úton lévő rendelések csak érzékenységi változatban (B) | nem (adatminőségi jelek) | B változat fő címkének | a B-többlet a tanító időszakban a legnagyobb (2017-es, egy év után is „feladva" állapotú rendelések) → inkább nem-kézbesítés / adatminőség, mint késés |
| 2026-10-08 | Kalibrációs diagnosztika: ECE két sávolással, CORP-felbontás, Brier-készség | igen (diagnosztika, nem választás) | csak egyenlő szélességű ECE | az előrejelzések 98%-a 10% alatt van; az egyenlő szélességű ECE főleg az átlagot méri |
| 2026-10-08 | Python 3.14 rögzítve | nem | 3.11–3.13 | a 3.14.8-on a teljes projekt bitre azonos számokat adott; a 3.15-höz még nincs duckdb és pyarrow |
| 2026-10-08 | A v3 adatmodell 5 magon lefuttatva (teszt PR-AUC 0,090 ± 0,005) | **igen** | — | **nem választottunk ennek alapján**: a változtatások témavezetői kérésre készültek; a teljesítmény a zajon belül változatlan (korábban 0,093 ± 0,006) |

## Következő, még nyitott döntések

* **Modellválasztás:** bővülő ablakos CV a tanító időszakon, a végső fa-szám a hajtások
  legjobb iterációinak mediánja, alsó korláttal. Ez után készül a **lezárt v3 alapfutás**,
  amelyet egyszer futtatunk a teszten.
* **Kontrafaktuális magyarázat:** a dice-ml helyett saját rácskeresés a vállalt határidőre
  (egyetlen akcionálható jellemző) — témavezetői jóváhagyásra vár.
* **Szakértői átnézés (3–5 fő):** a kutatási terv 5. hónapja miatt a minimum — témavezetői
  döntésre vár.
