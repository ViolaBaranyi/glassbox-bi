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
| 2026-10-09 | **LEZÁRT v3 ALAPFUTÁS** — protokoll `9407febe…`, git `6f1b792` (tiszta munkapéldány), Windows 11, Python 3.14.3; Linuxon bitre azonos | **igen — ez a lezárt mérés** | — | teszt: PR-AUC 0,098 [0,055; 0,127], ROC-AUC 0,764 [0,723; 0,788], Brier 0,0339, ECE 0,008 (tizedek 0,010); jobb a konstans előrejelzésnél (PR-AUC +0,062 [+0,035; +0,078], Brier −0,0013 [−0,0019; −0,0007]); 5 mag: PR-AUC 0,101 ± 0,003. Validáció: PR-AUC 0,179, ROC 0,650, ECE 0,049. **Innentől a protokoll változatlan: minden eltérés új, külön jelölt futás** |
| 2026-10-09 | A demó és a `pipeline.train` alapbeállítása a lezárt protokollra vált (`--trees cv`, címke-tisztítás) | igen (a lezárt futás után) | korai leállítás a validáción | a bemutatott szám = a lezárt mérés; a régi út `--trees korai --no-purge`-dzsal elérhető összehasonlításra |
| 2026-10-09 | **Referencia-modellek:** logisztikus regresszió (C), döntési fa (max_depth; levél ≥ 50), random forest (min_samples_leaf; 300 fa) — közös előfeldolgozás (medián + hiány-jelző, one-hot), választás ugyanazon a bővülő ablakos CV-n (4 tisztított hajtás, legnagyobb átlagos PR-AUC, egyezésnél az egyszerűbb) | nem (csak a tanító ablak) | a validációs ablakon hangolni; több hiperparaméter | tisztességes összevetés: mindegyik modell egy bonyolultsági paramétert kap, mint a LightGBM (fák száma) |
| 2026-10-09 | A döntési fa és a random forest rácsának kibővítése (fa: 12, 15, 20; erdő: 5, 2) | nem (csak a tanító ablak) | az eredeti rács | az első futásban a rács szélén volt a legjobb érték; a kibővítettben belül van, a választás nem változott |
| 2026-10-09 | **A referencia-összevetés protokollja jóváhagyva** (`docs/v3_referencia_protokoll.json`; jóváhagyta: Baranyi Viola) | nem | — | a rácsok, a választási szabály és a CV-ből várt beállítások a futás előtt rögzülnek; a futás a teszt előtt megáll, ha a CV mást választana |
| 2026-10-09 | **REFERENCIA-MODELLEK LEZÁRT ÖSSZEVETÉSE** — protokoll `6ea464ac…`, git `76934b1` (tiszta munkapéldány), Windows 11, Python 3.14.3; Linuxon bitre azonos | **igen — ez a lezárt mérés** | — | LightGBM − LR: PR-AUC +0,014 [−0,010; +0,029], ROC +0,024 [−0,018; +0,057], Brier −0,0002 [−0,0010; +0,0006] → nem kimutatható; − RF: PR-AUC +0,010 [+0,000; +0,018], ROC +0,026 [+0,013; +0,039]; − fa: PR-AUC +0,037 [+0,002; +0,053], ROC +0,167 [+0,105; +0,201]. Feltáró megfigyelés (nem előre tervezett): a validációs ablakon az LR jobb (PR-AUC 0,267 vs 0,179; ROC 0,755 vs 0,650) |
| 2026-10-09 | CV-eredmény (tanító ablak): LightGBM PR-AUC 0,126 / ROC 0,639 · logisztikus regresszió (C = 0,1) 0,124 / 0,634 · random forest (levél 10) 0,113 / 0,624 · döntési fa (mélység 10) 0,093 / 0,571 | nem | — | a teszten a páros, lezárt összevetés dönti el, kimutatható-e a különbség (`docs/v3_referencia_protokoll.md`) |

## Következő, még nyitott döntések


* **Kontrafaktuális magyarázat:** a dice-ml helyett saját rácskeresés a vállalt határidőre
  (egyetlen akcionálható jellemző) — témavezetői jóváhagyásra vár.
* **Szakértői átnézés (3–5 fő):** a kutatási terv 5. hónapja miatt a minimum — témavezetői
  döntésre vár.
