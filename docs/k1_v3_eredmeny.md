# K1 mérés v3 — a v4 és a v5 nyelvi réteg ugyanazon a kérdéssoron

Géppel készült (`tools/k1_v3_osszevetes.py`), a futások mappáiból, modell nélkül. Protokoll: `docs/k1_protokoll_v3.json` (SHA256 `c704d15f619c5659…`, jóváhagyta: Baranyi Viola, 2026-10-22); kérdéssor: `eval/meresi_kerdessor_v3.toml` (SHA256 `4ceea2657461afdb…`, 50 kérdés: 39 megválaszolandó, 11 csapda; Viola kérdései, a v5 lezárása után).

## Futások

| futás | mappa | kezdés | modell | kód (commit · ujjlenyomat) |
|---|---|---|---|---|
| v5 · 4B | `20261022_1902_qwen3.5-4b` | 2026-10-22T19:02:29 | qwen3.5:4b (`d8b0f5e9760c`) | `98a4bc5` · `9295c1cdc88d360b` |
| v4 · 4B | `20261022_1911_qwen3.5-4b` | 2026-10-22T19:11:08 | qwen3.5:4b (`d8b0f5e9760c`) | `e8c8bdd` · `7a3a5e94fe9efe50` |
| v5 · 9B | `20261022_1919_qwen3.5-9b` | 2026-10-22T19:19:45 | qwen3.5:9b (`56671c2ab938`) | `98a4bc5` · `9295c1cdc88d360b` |

Ellenőrzés: minden futás a jóváhagyott protokoll szerint ment (kérdéssor, kód, modell, ismétlés).
- a tárolt ítéletek újraszámolva: mind egyezik.
- az újrapontozás önellenőrzése (a v5 futás saját szövegei a v5 kapujával): mind egyezik a tárolt ítélettel.
- a v4 szövegeinek nézete a v5-ével összevetve (az időszak-sor nélkül): jelolo_mas_jelolok: 0, jelolo_mas_nezet: 38, szabad_mas_jelolok: 0, szabad_mas_nezet: 38

## Fő mutató: helyes válasz a feltett kérdésre (4B)

Teljes egyezés (mérőszám, bontás, szűrő, időablak, rendezés) a megválaszolandó kérdéseken, kérdésenként párosítva; a különbség 95%-os intervalluma bootstrap a kérdések újramintavételével (B = 2000, mag 20261023). A négy szám: mindkettő helyes / csak a v5 / csak a v4 / egyik sem.

| mutató | kérdés | v4 | v5 | v5 − v4 (95%) | ✓✓ / csak v5 / csak v4 / ✗✗ |
|---|---|---|---|---|---|
| **teljes egyezés** | 39 | 23/39 = **59,0%** (95%: 43,4% – 72,9%) | 25/39 = **64,1%** (95%: 48,4% – 77,3%) | **+5,1 pp** (−5,1 pp – +15,4 pp) | 22 / 3 / 1 / 13 |
| F-1 (mérőszám és bontás) | 39 | 28/39 = **71,8%** (95%: 56,2% – 83,5%) | 31/39 = **79,5%** (95%: 64,5% – 89,2%) | **+7,7 pp** (−2,6 pp – +20,5 pp) | 27 / 4 / 1 / 7 |
| F-2 (a csapdát elutasítja) | 11 | 7/11 = **63,6%** (95%: 35,4% – 84,8%) | 6/11 = **54,5%** (95%: 28,0% – 78,7%) | **−9,1 pp** (−36,4 pp – +18,2 pp) | 5 / 1 / 2 / 3 |
| F-2, az elvárt indokkal | 11 | 7/11 = **63,6%** (95%: 35,4% – 84,8%) | 6/11 = **54,5%** (95%: 28,0% – 78,7%) | **−9,1 pp** (−36,4 pp – +18,2 pp) | 5 / 1 / 2 / 3 |

### A kód tiszta hatása

A v4 és a v5 promptja azonos. 50 kérdésből 49-nél ugyanazt a nyers űrlapot adta a modell a két futásban (javító kör nélkül): itt az ítélet különbsége csak a kódé — javult 4, romlott 3. A többi 1 kérdésnél a modell válasza is más volt (a gép számolási eltérése, ill. javító kör: v5 1, v4 1) — javult 0, romlott 0.

### Kérdéstípusonként (helyes értelmezés / helyes elutasítás)

| | kérdés | v4 | v5 |
|---|---|---|---|
| csapda | 11 | 7 | 6 |
| idosor | 5 | 4 | 4 |
| idoszak | 2 | 0 | 2 |
| kombinalt | 17 | 8 | 7 |
| osszesito | 6 | 5 | 6 |
| rangsor | 7 | 4 | 4 |
| szures | 2 | 2 | 2 |

### Szerepkártyánként (helyes értelmezés / helyes elutasítás)

| | kérdés | v4 | v5 |
|---|---|---|---|
| Kategóriamenedzser | 7 | 4 | 5 |
| Logisztikai vezető | 9 | 8 | 8 |
| Pénzügyi elemző | 6 | 2 | 3 |
| Regionális értékesítési vezető | 10 | 5 | 5 |
| Ügyfélszolgálati vezető | 9 | 6 | 5 |
| Ügyvezető | 9 | 5 | 5 |

## K1: alá nem támasztott állítás a modell szövegében (4B, megválaszolandó kérdések)

A v4 szövegei a saját (v4) kapujukkal, és a v5 kapujával újrapontozva — az utóbbi a két kód szövegeit ugyanazzal a mércével méri. „Eljut”: a megjelölt szöveg a felhasználóhoz kerül (a fő ágon a megjelölt szöveg helyett sablon megy ki).

| ág | v4 szöveg, v4 kapu | v4 szöveg, v5 kapu | v5 szöveg, v5 kapu | v5 − v4 (v5 kapuval, párosítva) | eljut: v4 / v5 | sablonra vált: v4 / v5 |
|---|---|---|---|---|---|---|
| fő ág (jelölők) | 15/38 = **39,5%** (95%: 25,6% – 55,3%) | 14/38 = **36,8%** (95%: 23,4% – 52,7%) | 14/37 = **37,8%** (95%: 24,1% – 53,9%) | 0,0 pp (−10,8 pp – +10,8 pp; 37 kérdés) | 0,0% / 0,0% | 39,5% / 37,8% |
| kontrollág (szabad) | 7/38 = **18,4%** (95%: 9,2% – 33,4%) | 7/38 = **18,4%** (95%: 9,2% – 33,4%) | 9/37 = **24,3%** (95%: 13,4% – 40,1%) | +5,4 pp (−5,4 pp – +16,2 pp; 37 kérdés) | 18,4% / 24,3% | 0,0% / 0,0% |

A megjelölések fajtái (a v5 kapujával): fő ág (jelölők) — v4: rossz csoporthoz kötött érték 8, kitalált jelölő 5, vissza nem vezethető szám 5, hamis felsőfok 1, v5: rossz csoporthoz kötött érték 9, kitalált jelölő 5, vissza nem vezethető szám 4; kontrollág (szabad) — v4: vissza nem vezethető szám 5, rossz csoporthoz kötött érték 3, hamis felsőfok 1, v5: vissza nem vezethető szám 6, hamis felsőfok 2, rossz csoporthoz kötött érték 2

## A 9B a v5-tel (leíró)

| mutató | eredmény |
|---|---|
| teljes egyezés | 25/39 = **64,1%** (95%: 48,4% – 77,3%) |
| F-1 | 28/39 = **71,8%** (95%: 56,2% – 83,5%) |
| F-2 | 7/11 = **63,6%** (95%: 35,4% – 84,8%) |
| K1, fő ág (jelölők): megjelölt / eljut | 5/34 = **14,7%** (95%: 6,4% – 30,1%) / 0,0% |
| K1, kontrollág (szabad): megjelölt / eljut | 7/34 = **20,6%** (95%: 10,3% – 36,8%) / 20,6% |

## Idő (medián)

| futás | ① (értelmezés) | ② fő ág | ② kontrollág | összesen |
|---|---|---|---|---|
| v5 · 4B | 3,4 mp | 3,6 mp | 3,7 mp | 8 perc |
| v4 · 4B | 3,6 mp | 3,8 mp | 3,8 mp | 9 perc |
| v5 · 9B | 4,8 mp | 5,0 mp | 5,5 mp | 11 perc |

## Kérdésenként (4B)

✓ helyes (vagy helyes elutasítás) · ✗ hibás értelmezés · ⊘ téves elutasítás · ! hiányzó elutasítás · ≈ más indokú elutasítás · = a modell nyers űrlapja a két futásban azonos

| # | típus | kérdés | v4 | v5 | a v5 eltérése az elvárttól |
|---|---|---|---|---|---|
| k301 = | osszesito | mennyi most az atlagos kiszallitasi ido osszessegeben? | ✓ | ✓ |  |
| k302 = | szures | mekkora a kesesi arany az eszaki regioban? ott jon a legtobb panasz | ✓ | ✓ |  |
| k303 = | rangsor | melyik 5 allamba erunk ki a leglassabban? | ✓ | ✓ |  |
| k304 = | idosor | kerek egy havi bontast a kesett rendelesek szamarol 2018-ra | ✓ | ✓ |  |
| k305 = | csapda | mennyi idot tolt egy csomag a raktarban amig a futar elviszi? | ✓ | ✓ |  |
| k306 = | kombinalt | hasonlitsd ossze a vallalt es a tenyleges szallitasi idot regionkent… | ✓ | ✓ |  |
| k307 = | idosor | javult a teljesites az elmult egy evben honaprol honapra? a vallalt … | ✓ | ✓ |  |
| k308 = | kombinalt | SP-i eladoknal mennyi az atlagos szallitasi ido a vevo allama szerin… | ✗ | ✗ | bontás: [] (elvárt: ['vevo_allam']); szűrő: {'elado_allam': ['SP']} (elvárt: {'elado_allam': ['SP'], 'kesett': ['kesett']}) |
| k310 = | kombinalt | a median kiszallitasi ido mennyi a delkeleti regioban idén? | ✓ | ✓ |  |
| k311 = | rangsor | top 10 kategoria forgalom szerint? | ✓ | ✓ |  |
| k314 = | osszesito | mennyi az atlagos kosarertek osszessegeben, kene egy referencia amih… | ✗ | ✓ ↑ |  |
| k315 = | kombinalt | butor vs lakastextil: melyikbol megy tobb rendeles, es forgalomban m… | ✗ | ✗ | szűrő: {} (elvárt: {'kategoria': ['bed_bath_table', 'furniture_decor']}) |
| k317 = | kombinalt | bontsd le a szepsegapolas forgalmat regiokra. hol megy a legjobban? | ✓ | ✓ |  |
| k318 = | csapda | mennyi keszlet van most a jatekokbol? nem szeretnem ha karacsony elo… | ✓ | ✓ |  |
| k319 = | rangsor | mi az a 10 kategoria amibol szinte semmi nem megy? kivezetnem oket | ✗ | ✗ | rendezes: ertek_csokkeno (elvárt: ertek_novekvo) |
| k320 = | kombinalt | 2017 nov-dec-ben melyik 5 kategoria porgott a legjobban bevetel alap… | ✓ | ✓ |  |
| k321 = | idoszak | mennyi volt a teljes forgalom 2017-ben es 2018-ban? egymas mellett k… | ✗ | ✓ ↑ |  |
| k322 = | idosor | negyedeves bontasban kerem a forgalmat 2017 elejetol | ✓ | ✓ |  |
| k325 = | rangsor | melyik 5 allam adja a forgalom legnagyobb reszet? szazalekosan is ke… | ✗ | ✗ | bontás: [] (elvárt: ['vevo_allam']) |
| k328 = | csapda | a bevetel mekkora resze jott bankkartyaval es mennyi reszletre? a ca… | ✓ | ✓ |  |
| k329 = | kombinalt | a szallitasi dij atlaga a kosarertek mekkora reszet teszi ki? | ⊘ | ⊘ | nem_elerheto: Ezt nem tudom kiszámolni: az adathalmaz nem tartalmaz beszerzési árat, ezért haszon vagy árrés nem számolható. Ami közel áll hozzá: átlagos kosáré |
| k330 = | kombinalt | allamonkent az atlagos kosarertek 2018-ban, es hogy viszonyul ez az … | ✗ | ✗ | bontás: ['elado_allam'] (elvárt: ['vevo_allam']) |
| k331 = | kombinalt | hogy all a delkelet forgalomban az osszeshez kepest? | ✗ | ✗ | bontás: [] (elvárt: ['vevo_regio']); szűrő: {'vevo_regio': ['SE']} (elvárt: {}) |
| k332 = | rangsor | top 5 allam rendelesszam szerint | ✓ | ✓ |  |
| k333 = | kombinalt | allamonkent kerem a rendeleseket 2018-ra | ✓ | ✓ |  |
| k334 = | csapda | melyik kampanybol jottek a legtobbet vasarlo vevok? oda tolnam a kol… | ✓ | ✓ |  |
| k335 = | idosor | hogy alakult az eszakkeleti regio forgalma negyedevente? | ✗ | ✗ | tól: 2018-04-01 (elvárt: az adat eleje); ig: 2018-06-30 (elvárt: az adat vége) |
| k336 = | kombinalt | RJ vs MG, melyik hoz tobb bevetelt, es melyikben nagyobb az atlagos … | ✗ | ✗ | szűrő: {} (elvárt: {'vevo_allam': ['MG', 'RJ']}) |
| k337 = | kombinalt | mennyi rendeles jott be Bahiabol tavaly | ✓ | ✗ ↓ | szűrő: {'elado_allam': ['BA']} (elvárt: {'vevo_allam': ['BA']}) |
| k338 = | kombinalt | a Del regioban melyik kategoriak mennek a legjobban bevetel szerint? | ✓ | ✓ |  |
| k339 = | csapda | mennyi forgalomra szamithatok a kovetkezo negyedevben a regiomban? t… | ! | ✓ ↑ |  |
| k340 = | kombinalt | a het melyik napjan rendelnek a legtobbet a deli regioban? oda idozn… | ✗ | ✗ | bontás: ['vevo_regio'] (elvárt: ['het_napja']); szűrő: {} (elvárt: {'vevo_regio': ['S']}) |
| k341 = | osszesito | mennyi a kesesi arany osszessegeben? | ✓ | ✓ |  |
| k342 = | rangsor | melyik 5 allamban a legrosszabb a kesesi arany? oda kene tobb ember … | ✓ | ✓ |  |
| k343 = | osszesito | ha egy csomag kesik, atlagosan mennyit kesik? | ✓ | ✓ |  |
| k344 = | csapda | a kesesek miatt mennyivel rosszabb ertekelest kapunk? latszik a csil… | ✓ | ✓ |  |
| k346 = | szures | a lakastextilnel mennyi a kesesi arany | ✓ | ✓ |  |
| k347 = | csapda | hany rendelest mondtak le vagy kuldtek vissza tavaly? | ✓ | ! ↓ | elfogadva: {"bontas": [], "idoablak": {"ig": "2017-12-31", "tol": "2017-01-01"}, "limit": 10, "metrika": "rendelesek_szama", "rendezes": "ertek_csokkeno", "szur |
| k348 = | csapda | hol nagyobb a keses, ha a vevo es az elado ugyanabban az allamban va… | ! | ! | elfogadva: {"bontas": ["vevo_allam"], "limit": 10, "metrika": "kesesi_arany", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k349 = | kombinalt | 2017 novemberben allamonkent hany csomag kesett? black friday utan a… | ✗ | ✗ | szűrő: {'kategoria': ['telephony']} (elvárt: {}) |
| k350 = | kombinalt | a hetvegen leadott rendelesek jobban kesnek mint a hetkozbeniek? | ✗ | ✗ | bontás: [] (elvárt: ['het_napja']); szűrő: {'het_napja': ['7']} (elvárt: {}) |
| k351 = | osszesito | mennyi a teljes bevetel es a rendelesszam a kezdetek ota? | ✓ | ✓ |  |
| k352 = | idosor | no a ceg? eves bontasban kerem a forgalmat | ✓ | ✓ |  |
| k353 = | rangsor | mi az 5 legnagyobb kategoria es az 5 legnagyobb allam bevetel szerint? | ✗ | ⊘ | tul_sok_bontas: Egyszerre legfeljebb 1 bontás lehet (a kérdésben 2 van). |
| k354 = | csapda | a 2015-es evhez kepest hogy allunk? kerek egy osszehasonlitast 2015 … | ! | ! | elfogadva: {"bontas": ["ev"], "idoablak": {"ig": "2017-12-31"}, "limit": 100, "metrika": "forgalom", "rendezes": "bontas", "szuro": {}} |
| k355 = | idoszak | 2017 es 2018 elso 8 honapja hogy all egymashoz forgalomban? | ✗ | ✓ ↑ |  |
| k356 = | kombinalt | regios bontasban a forgalom es a rendelesszam, szazalekokkal. ezt vi… | ✓ | ✓ |  |
| k357 = | osszesito | atlagos szallitasi ido es kesesi arany osszessegeben, ezt a kettot k… | ✓ | ✓ |  |
| k359 = | csapda | a 3 legnagyobb regioban hogy alakult a kesesi arany az elmult evben?… | ! | ! | elfogadva: {"bontas": ["vevo_regio"], "idoablak": {"tol": "2017-09-01"}, "limit": 3, "metrika": "kesesi_arany", "rendezes": "ertek_csokkeno", "szuro": {"vevo_re |
| k360 = | csapda | a delkelet reszaranya a bevetelbol novekszik vagy csokken eves szint… | ✓ | ! ↓ | elfogadva: {"bontas": ["ev"], "limit": 100, "metrika": "forgalom", "rendezes": "bontas", "szuro": {"vevo_regio": ["SE"]}} |
