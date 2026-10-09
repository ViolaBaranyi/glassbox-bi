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
| 2026-10-08 | **Fa-szám a tanító időszakon belül:** bővülő ablakos CV (4 hajtás, napra kerekített kvantilis-vágás × 3 mag, korai leállítás PR-AUC-ra), `N_fix = max(50, medián)`; a végső modell pontosan N_fix fával, a validáció csak időn kívüli ellenőrzés (`--trees cv`) | nem (csak a tanító ablak) | korai leállítás a validációs ablakon | a validációs ablakban éles rendszerváltás (márc. 19,0% → ápr. 4,5%); egyetlen ablakon választani kockázatos (10. lelet). Valódi adaton: medián 66,5 → 67 fa (a legjobb iterációk szórása nagy: 16–151) |
| 2026-10-08 | **Végső modell a tanító ablakon** (nem újratanítás tanító + validáción) | nem | újratanítás a validációs ablakkal együtt | a v2 ablakai változatlanok maradnak; a validáció így tiszta, időn kívüli ellenőrzés |
| 2026-10-08 | **Bizonytalanság: heti blokk-bootstrap** (ISO-hét, B = 2000, percentilis 95%); tanítási véletlen külön, 5 maggal (`pipeline/bootstrap.py`) | nem | rendelésenkénti bootstrap; csak magok | a késések hetente együtt mozognak → rendelésenkénti újramintavétel hamisan szűk CI-t adna; témavezetői kérés: bootstrap a magok helyett |
| 2026-10-08 | **Lezárt alapfutás protokoll-kapuval** (`docs/v3_protokoll.json`, SHA256, egyszeri futás; `pipeline/v3_baseline.py`) | nem | — | a tesztet eddig sokszor láttuk (fent); innentől a döntések a futás ELŐTT rögzülnek |
| 2026-10-08 | **Új lelet — címke-szivárgás a vágásnál** (még NEM döntés, lásd lent) | nem (csak a tanító ablak) | — | a 2018-03-01-i vágásnál a tanító sorok 6,2%-ának a kimenete még ismeretlen volt (26,6%-uk késett). CV-n, azonos fa-számmal: a Black Friday-s hajtásban PR-AUC 0,246 tisztítás nélkül vs 0,17 tisztítással; a nyugodt hajtásokban nincs különbség |
| 2026-10-09 | **Címke-tisztítás: IGEN** — csak a vágás előtt lejárt határidejű tanító sorok, a CV-hajtásokban és a végső modellnél is (döntött: Baranyi Viola) | nem (csak a tanító ablak) | tisztítás nélkül (a v2 eredeti vágása) | point-in-time elv a címkékre is; CV-n azonos fa-számmal a Black Friday-s hajtás PR-AUC-ja 0,246 → 0,17, a nyugodt hajtásokban nincs különbség; a határidő szerinti szűrés a kimenettől független. Ára: a tanító ablak 11,7%-a; a fa-szám 119 |
| 2026-10-09 | A fa-szám alsó korlátja: 50 (változatlan) | nem | — | a valódi adaton nem ez dönt (medián 118,5) |
| 2026-10-09 | **A lezárt v3 alapfutás protokollja jóváhagyva** (`docs/v3_protokoll.json`) | nem | — | a futás csak a protokoll és a kód commitja után indul (a git időbélyege bizonyítja a sorrendet); az ujjlenyomat sorvégfüggetlen |

## Következő, még nyitott döntések

* **Lezárt v3 alapfutás:** a protokoll jóváhagyva (okt. 9.) → commit + push, majd
  `python -m pipeline.v3_baseline`, végül az eredményfájlok
  (`docs/v3_lezart_eredmeny.json`, `.md`) commitja. Utána a demó alapbeállítása a
  protokollra vált (`--trees cv --purge`).
* **Kontrafaktuális magyarázat:** a dice-ml helyett saját rácskeresés a vállalt határidőre
  (egyetlen akcionálható jellemző) — témavezetői jóváhagyásra vár.
* **Szakértői átnézés (3–5 fő):** a kutatási terv 5. hónapja miatt a minimum — témavezetői
  döntésre vár.
