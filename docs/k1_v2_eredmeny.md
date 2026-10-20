# K1 mérés v2 — a v3 és a v4 nyelvi réteg ugyanazon a kérdéssoron

Géppel készült (`tools/k1_v2_osszevetes.py`), a futások mappáiból, modell nélkül. Protokoll: `docs/k1_protokoll_v2.json` (SHA256 `04ceaec1b26cb199…`, jóváhagyta: Baranyi Viola, 2026-10-20); kérdéssor: `eval/meresi_kerdessor_v2.toml` (SHA256 `1c41464d69438a9c…`, 56 kérdés: 45 megválaszolandó, 11 csapda).

## Futások

| futás | mappa | kezdés | modell | kód (commit · ujjlenyomat) |
|---|---|---|---|---|
| v4 · 4B | `20261020_1300_qwen3.5-4b` | 2026-10-20T13:00:11 | qwen3.5:4b (`d8b0f5e9760c`) | `d809a66` · `7a3a5e94fe9efe50` |
| v3 · 4B | `20261020_1400_qwen3.5-4b` | 2026-10-20T14:00:32 | qwen3.5:4b (`d8b0f5e9760c`) | `f5db169` · `db97e252c9902346` |
| v4 · 2B | `20261020_1404_qwen3.5-2b` | 2026-10-20T14:04:14 | qwen3.5:2b (`0689d44085e0`) | `d809a66` · `7a3a5e94fe9efe50` |

Ellenőrzés: minden futás a jóváhagyott protokoll szerint ment (kérdéssor, kód, modell, ismétlés).
- a tárolt ítéletek újraszámolva: mind egyezik.
- az újrapontozás önellenőrzése (a v4 futás saját szövegei a v4 kapujával): mind egyezik a tárolt ítélettel.
- a v3 szövegeinek nézete a v4-ével összevetve (az időszak-sor nélkül): jelolo_mas_jelolok: 0, jelolo_mas_nezet: 0, szabad_mas_jelolok: 0, szabad_mas_nezet: 0

## Fő mutató: helyes válasz a feltett kérdésre (4B)

Teljes egyezés (mérőszám, bontás, szűrő, időablak, rendezés) a megválaszolandó kérdéseken, kérdésenként párosítva; a különbség 95%-os intervalluma bootstrap a kérdések újramintavételével (B = 2000, mag 20261020). A négy szám: mindkettő helyes / csak a v4 / csak a v3 / egyik sem.

| mutató | kérdés | v3 | v4 | v4 − v3 (95%) | ✓✓ / csak v4 / csak v3 / ✗✗ |
|---|---|---|---|---|---|
| **teljes egyezés** | 45 | 18/45 = **40,0%** (95%: 27,0% – 54,5%) | 22/45 = **48,9%** (95%: 35,0% – 63,0%) | **+8,9 pp** (−2,2 pp – +20,0 pp) | 17 / 5 / 1 / 22 |
| F-1 (mérőszám és bontás) | 45 | 29/45 = **64,4%** (95%: 49,8% – 76,8%) | 30/45 = **66,7%** (95%: 52,1% – 78,6%) | **+2,2 pp** (0,0 pp – +6,7 pp) | 29 / 1 / 0 / 15 |
| F-2 (a csapdát elutasítja) | 11 | 7/11 = **63,6%** (95%: 35,4% – 84,8%) | 7/11 = **63,6%** (95%: 35,4% – 84,8%) | **0,0 pp** (0,0 pp – 0,0 pp) | 7 / 0 / 0 / 4 |
| F-2, az elvárt indokkal | 11 | 6/11 = **54,5%** (95%: 28,0% – 78,7%) | 6/11 = **54,5%** (95%: 28,0% – 78,7%) | **0,0 pp** (0,0 pp – 0,0 pp) | 6 / 0 / 0 / 5 |

### Kérdéstípusonként (helyes értelmezés / helyes elutasítás)

| típus | kérdés | v3 | v4 |
|---|---|---|---|
| csapda | 11 | 6 | 6 |
| idosor | 8 | 1 | 2 |
| idoszak | 2 | 0 | 1 |
| kombinalt | 13 | 6 | 7 |
| nyelvi | 11 | 2 | 2 |
| osszesito | 1 | 1 | 1 |
| rangsor | 6 | 4 | 5 |
| szures | 4 | 4 | 4 |

## K1: alá nem támasztott állítás a modell szövegében (4B, megválaszolandó kérdések)

A v3 szövegei a saját (v3) kapujukkal, és a v4 kapujával újrapontozva — az utóbbi a két kód szövegeit ugyanazzal a mércével méri. „Eljut”: a megjelölt szöveg a felhasználóhoz kerül (a fő ágon a megjelölt szöveg helyett sablon megy ki).

| ág | v3 szöveg, v3 kapu | v3 szöveg, v4 kapu | v4 szöveg, v4 kapu | v4 − v3 (v4 kapuval, párosítva) | eljut: v3 / v4 | sablonra vált: v3 / v4 |
|---|---|---|---|---|---|---|
| fő ág (jelölők) | 25/42 = **59,5%** (95%: 44,5% – 73,0%) | 22/42 = **52,4%** (95%: 37,7% – 66,6%) | 16/44 = **36,4%** (95%: 23,8% – 51,1%) | −19,0 pp (−35,7 pp – −2,4 pp; 42 kérdés) | 0,0% / 0,0% | 59,5% / 36,4% |
| kontrollág (szabad) | 18/42 = **42,9%** (95%: 29,1% – 57,8%) | 15/42 = **35,7%** (95%: 23,0% – 50,8%) | 16/44 = **36,4%** (95%: 23,8% – 51,1%) | +2,4 pp (−11,9 pp – +16,7 pp; 42 kérdés) | 42,9% / 36,4% | 0,0% / 0,0% |

A megjelölések fajtái (a v4 kapujával): fő ág (jelölők) — v3: kitalált jelölő 10, rossz csoporthoz kötött érték 9, vissza nem vezethető szám 6, hamis felsőfok 3, a szűrés tagadása 1, v4: kitalált jelölő 9, rossz csoporthoz kötött érték 4, vissza nem vezethető szám 4, hamis felsőfok 3; kontrollág (szabad) — v3: vissza nem vezethető szám 12, hamis felsőfok 4, rossz csoporthoz kötött érték 3, v4: vissza nem vezethető szám 11, rossz csoporthoz kötött érték 5, hamis felsőfok 3, a tartomány hamis szerepe 1

## A 2B a v4-gyel (leíró)

| mutató | eredmény |
|---|---|
| teljes egyezés | 9/45 = **20,0%** (95%: 10,9% – 33,8%) |
| F-1 | 16/45 = **35,6%** (95%: 23,2% – 50,2%) |
| F-2 | 11/11 = **100,0%** (95%: 74,1% – 100,0%) |
| K1, fő ág (jelölők): megjelölt / eljut | 18/30 = **60,0%** (95%: 42,3% – 75,4%) / 0,0% |
| K1, kontrollág (szabad): megjelölt / eljut | 16/30 = **53,3%** (95%: 36,1% – 69,8%) / 53,3% |

## Idő (medián)

| futás | ① (értelmezés) | ② fő ág | ② kontrollág | összesen |
|---|---|---|---|---|
| v4 · 4B | 21,2 mp | 16,5 mp | 17,5 mp | 52 perc |
| v3 · 4B | 32,5 mp | 18,2 mp | 19,5 mp | 66 perc |
| v4 · 2B | 22,0 mp | 18,6 mp | 18,7 mp | 49 perc |

## Kérdésenként (4B)

✓ helyes (vagy helyes elutasítás) · ✗ hibás értelmezés · ⊘ téves elutasítás · ! hiányzó elutasítás · ≈ más indokú elutasítás

| # | típus | kérdés | v3 | v4 | a v4 eltérése az elvárttól |
|---|---|---|---|---|---|
| k201 | idoszak | mennyi lett a végösszeg az egész 2017-es évre nézve? | ⊘ | ⊘ | ismeretlen_metrika: Ezt nem tudom kiszámolni: „végösszeg” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések s |
| k202 | osszesito | hany darab megrendelést kaptunk összesen a kezdettől fogva? | ✓ | ✓ |  |
| k203 | idoszak | az elmult félévben mennyi volt a cég teljes bevétele? | ✗ | ✓ ↑ |  |
| k204 | szures | mi az atlagos rendelesi ertek szombatonkent? | ✓ | ✓ |  |
| k205 | rangsor | top 10 legrosszabb kategória a csúszások százaléka alapján? | ✓ | ✓ |  |
| k206 | kombinalt | melyik 3 államba küldtük a legkevesebb csomagot idén? | ✓ | ✓ |  |
| k207 | rangsor | sorold fel a legjobb öt eladói régiót bevétel szerint! | ✗ | ✗ | bontás: ['vevo_regio'] (elvárt: ['elado_allam']) |
| k208 | kombinalt | melyik az a kategória amit a legtöbbször vesznek hétfőn? | ✓ | ✓ |  |
| k209 | rangsor | mi a top 5 legdrágább szállítási díjú termékcsoportunk? | ✓ | ✓ |  |
| k210 | kombinalt | mennyi volt a forgalom minas gerais-ban 2018 Q2-ben? | ✓ | ✓ |  |
| k211 | kombinalt | csak a szépségápolást nézve mennyi a szállítási idő átlaga az idén? | ✓ | ✓ |  |
| k212 | szures | északi régiós vevőknél hány nap a medián kiszállítás? | ✓ | ✓ |  |
| k213 | szures | mennyi idő alatt ér oda egy csomag átlagosan ha a vevő és az eladó i… | ✓ | ✓ |  |
| k214 | rangsor | vasarnaponkent tobb a bevétel mint szerdán? | ✗ | ✓ ↑ |  |
| k215 | kombinalt | hány csomagot vittek ki késve RJ államba tavaly decemberben? | ✗ | ✓ ↑ |  |
| k216 | idosor | hogy nez ki a 2018-as forgalom honaprol honapra? | ✗ | ✓ ↑ |  |
| k217 | idosor | éves szinten növekszik a kosárérték? | ✗ | ✓ ↑ |  |
| k218 | idosor | mutasd a késett rendelések számának havi alakulását 2017 elejétől! | ✗ | ✗ | ig: 2017-12-31 (elvárt: az adat vége) |
| k219 | idosor | szallitasi dijak hogy valtoztak negyedevenkent a tavalyi ev folyaman? | ✗ | ✗ | bontás: [] (elvárt: ['honap']); rendezes: ertek_csokkeno (elvárt: bontas) |
| k220 | kombinalt | a hét napjai szerint hogy oszlik el a rendelések száma idén? | ✓ | ✓ |  |
| k221 | nyelvi | ha csak a butorokat meg a sport cuccokat nezem, hol volt a legkisebb… | ⊘ | ✗ | bontás: [] (elvárt: ['kategoria']) |
| k222 | nyelvi | atlagos tavolsag a vevohoz a delkeleti regioban tavaly nyaron? | ✗ | ✗ | tól: 2017-01-01 (elvárt: 2017-06-01); ig: 2017-12-31 (elvárt: 2017-08-31) |
| k223 | kombinalt | SP-ből északra mennyi a fuvardíj mediánja mostanság? | ✗ | ✗ | szűrő: {'vevo_allam': ['SP']} (elvárt: {'elado_allam': ['SP'], 'vevo_regio': ['N']}) |
| k224 | kombinalt | 2017 utolso 4 honapjaban mi volt a legpörgősebb 3 kategória bevétel … | ✗ | ✗ | tól: 2018-05-01 (elvárt: 2017-09-01); ig: az adat vége (elvárt: 2017-12-31) |
| k225 | kombinalt | az 5 legforgalmasabb allam atlagos szallitasi ideje miben ter el egy… | ✗ | ✗ | szűrő: {} (elvárt: {'vevo_allam': ['MG', 'PR', 'RJ', 'RS', 'SP']}) |
| k226 | nyelvi | mibe kerul a szallitas atlagosan a jatekoknal ha pénteken veszik meg… | ✗ | ✗ | metrika: atlagos_szallitasi_ido (elvárt: atlagos_szallitasi_dij) |
| k227 | rangsor | mennyi a késés napokban mérve a top 5 legrosszabb államban? | ✓ | ✓ |  |
| k228 | kombinalt | hany rendelest hozott a 3 legkisebb regio osszesen 2017 masodik fele… | ✓ | ✓ |  |
| k229 | csapda | volt e olyan ev amikor az egeszsegügyi termekekbol tobb fogyott mint… | ! | ! | elfogadva: {"bontas": ["kategoria"], "limit": 10, "metrika": "forgalom", "rendezes": "ertek_novekvo", "szuro": {}} |
| k230 | idosor | csokkent a vallalt szallitasi ido 2017 ota? | ✗ | ✗ | bontás: [] (elvárt: ['honap']); tól: 2017-09-01 (elvárt: 2017-01-01); rendezes: ertek_csokkeno (elvárt: bontas) |
| k231 | nyelvi | melyik honapban fognak melle a legnagyobbat a vallalt szallitasi ido… | ✗ | ✗ | metrika: atlagos_vallalt_ido (elvárt: atlagos_keses vagy kesesi_arany); bontás: [] (elvárt: ['honap']) |
| k232 | csapda | honnan hova a legmagasabb a fuvar atlag dija idén (régiók között)? | ! | ! | elfogadva: {"bontas": ["vevo_regio"], "idoablak": {"tol": "2018-01-01"}, "limit": 10, "metrika": "atlagos_szallitasi_dij", "rendezes": "ertek_csokkeno", "szuro" |
| k233 | idosor | mi a legforgalmasabb honap a lakberendezes kategoria eseteben? | ✓ | ✗ ↓ | szűrő: {} (elvárt: {'kategoria': ['furniture_decor']}) |
| k234 | rangsor | top 10 kategoria elado-vevo tavolsag szerint (melyiknel utazik a leg… | ✓ | ✓ |  |
| k235 | szures | hány nap a csúszás átlaga, ha vasárnap jön be a rendelés? | ✓ | ✓ |  |
| k236 | kombinalt | az 5 legnagyobb forgalmu allamban mibol adtak el a legkevesebbet tav… | ✗ | ✗ | metrika: atlagos_kosarertek (elvárt: rendelesek_szama vagy forgalom); bontás: ['vevo_allam'] (elvárt: ['kategoria']); szűrő: {} (elvárt: {'vevo_allam': ['MG', ' |
| k237 | nyelvi | menyni vót a legkisebb forgalmu honapunk tavaly? | ✓ | ✓ |  |
| k238 | nyelvi | havi bontas 2017 re az atlag szallitasra? | ✓ | ✓ |  |
| k239 | idosor | mikor volt a legalacsonyabb a csuszasok szazaleka az egesz idoszakot… | ✗ | ✗ | bontás: [] (elvárt: ['honap']) |
| k240 | idosor | 2018 Q1 vs Q2 hogy viszonyul egymashoz atlag kosar ertekben? | ✗ | ✗ | bontás: [] (elvárt: ['honap']); ig: 2018-03-31 (elvárt: 2018-06-30); rendezes: ertek_csokkeno (elvárt: bontas) |
| k241 | nyelvi | hova kuldjuk a legtob butort rio-bol? | ⊘ | ✗ | metrika: forgalom (elvárt: rendelesek_szama); bontás: [] (elvárt: ['vevo_allam']) |
| k242 | kombinalt | az elektronika kategoria mediam szallitasi ideje 2017 vs 2018? | ✗ | ✗ | metrika: atlagos_szallitasi_ido (elvárt: median_szallitasi_ido); bontás: [] (elvárt: ['ev']); tól: az adat eleje (elvárt: 2017-01-01) |
| k243 | csapda | a 3 legnagyobb regió bevétele negyedévente 2017-től? | ! | ! | elfogadva: {"bontas": ["vevo_regio"], "idoablak": {"tol": "2017-01-01"}, "limit": 3, "metrika": "forgalom", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k244 | nyelvi | hanyadik a sorban sao paulo ha a fuvar dijakat nezzuk legolcsóbbtol? | ✗ | ✗ | bontás: [] (elvárt: ['vevo_allam']); szűrő: {'vevo_allam': ['SP']} (elvárt: {}) |
| k245 | nyelvi | hany nap a diff a vallalt es a tenyleges kiszallitas kozott atlagosa… | ✗ | ✗ | tól: 2018-04-01 (elvárt: 2018-03-01); ig: 2018-06-30 (elvárt: 2018-05-31) |
| k246 | nyelvi | szamitogepeknel mizu a szallitasi atlaggal a 2 legutolso honapban? | ✗ | ✗ | szűrő: {} (elvárt: {'kategoria': ['computers']}); tól: az adat eleje (elvárt: 2018-07-01) |
| k247 | nyelvi | elado es vevo kozti atlagos km honaprol honapra tavaly elottrol? | ✗ | ✗ | bontás: ['vevo_allam'] (elvárt: ['honap']); tól: 2017-01-01 (elvárt: az adat eleje); ig: 2017-12-31 (elvárt: 2016-12-31); rendezes: ertek_csokkeno (elvárt: bont |
| k248 | kombinalt | az év melyik hónapjában a legmagasabb a fuvardíj mediánja az északke… | ✗ | ✗ | bontás: [] (elvárt: ['honap']); rendezes: ertek_novekvo (elvárt: ertek_csokkeno vagy bontas) |
| k250 | csapda | Mennyi volt az adózott eredményünk az utolsó félévben? | ✓ | ✓ |  |
| k251 | csapda | Melyik a legrosszabbul értékelt termék a játékok közül? | ✓ | ✓ |  |
| k252 | csapda | Hány százaléka lett lemondva a csomagoknak karácsonykor? | ✓ | ✓ |  |
| k254 | csapda | Melyik kategória fog a legnagyobbat nőni a következő évben? | ✓ | ✓ |  |
| k255 | csapda | Mi volt a top 3 állam 2014-ben bevétel alapján? | ≈ | ≈ | elvárt: adaton_kivuli_idoablak, kapott: ismeretlen_metrika |
| k256 | csapda | Hogyan zártuk a 2019-es évet forgalom szempontjából? | ✓ | ✓ |  |
| k259 | csapda | Mekkora a haszonkulcs a bútorokon, ha levonjuk a marketinget? | ✓ | ✓ |  |
| k260 | csapda | Melyik futárcég hozta össze a legtöbb késést idén? | ! | ! | elfogadva: {"bontas": [], "idoablak": {"tol": "2018-01-01"}, "limit": 10, "metrika": "atlagos_keses", "rendezes": "ertek_csokkeno", "szuro": {}} |
