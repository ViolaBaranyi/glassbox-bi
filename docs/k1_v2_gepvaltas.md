# Gépváltás: a v4 4B a laptop processzorán és a videókártyán (ugyanaz a modellfájl, kód és kérdéssor)

Géppel készült (`tools/k1_futas_osszevetes.py`), a futások mappáiból, modell nélkül. Protokoll: `k1_protokoll_v2.json` (SHA256 `04ceaec1b26cb199…`, jóváhagyta: Baranyi Viola, 2026-10-20); kérdéssor: `eval/meresi_kerdessor_v2.toml` (SHA256 `1c41464d69438a9c…`). A különbség mindig **A − B**: A = 4B (videókártya), B = 4B (laptop, processzor).

## Futások

| | futás | mappa | kezdés | modell | kód (commit · ujjlenyomat) | protokoll |
|---|---|---|---|---|---|---|
| A | 4B (videókártya) | `20261022_1040_qwen3.5-4b` | 2026-10-22T10:40:23 | qwen3.5:4b (`d8b0f5e9760c`) | `69aa581` · `7a3a5e94fe9efe50` | `docs/k1_protokoll_v2.json` |
| B | 4B (laptop, processzor) | `20261020_1300_qwen3.5-4b` | 2026-10-20T13:00:11 | qwen3.5:4b (`d8b0f5e9760c`) | `d809a66` · `7a3a5e94fe9efe50` | `docs/k1_protokoll_v2.json` |

Ellenőrzés: mindkét futás a protokoll kérdéssorán, a rögzített kóddal, teljes futásként ment.
- a tárolt ítéletek újraszámolva: mind egyezik.

## Fő mutató: helyes válasz a feltett kérdésre

Teljes egyezés (mérőszám, bontás, szűrő, időablak, rendezés) a megválaszolandó kérdéseken, kérdésenként párosítva; 95%-os bootstrap a kérdések újramintavételével (B = 2000, mag 20261020). A négy szám: mindkettő helyes / csak A / csak B / egyik sem.

| mutató | kérdés | B: 4B (laptop, processzor) | A: 4B (videókártya) | A − B (95%) | ✓✓ / csak A / csak B / ✗✗ |
|---|---|---|---|---|---|
| **teljes egyezés** | 45 | 22/45 = **48,9%** (95%: 35,0% – 63,0%) | 26/45 = **57,8%** (95%: 43,3% – 71,0%) | **+8,9 pp** (0,0 pp – +20,0 pp) | 21 / 5 / 1 / 18 |
| F-1 (mérőszám és bontás) | 45 | 30/45 = **66,7%** (95%: 52,1% – 78,6%) | 34/45 = **75,6%** (95%: 61,3% – 85,8%) | **+8,9 pp** (+2,2 pp – +17,8 pp) | 30 / 4 / 0 / 11 |
| F-2 (a csapdát elutasítja) | 11 | 7/11 = **63,6%** (95%: 35,4% – 84,8%) | 8/11 = **72,7%** (95%: 43,4% – 90,3%) | **+9,1 pp** (0,0 pp – +27,3 pp) | 7 / 1 / 0 / 3 |
| F-2, az elvárt indokkal | 11 | 6/11 = **54,5%** (95%: 28,0% – 78,7%) | 6/11 = **54,5%** (95%: 28,0% – 78,7%) | **0,0 pp** (−27,3 pp – +27,3 pp) | 5 / 1 / 1 / 4 |

Egyezés kérdésenként (56 kérdés): azonos ① értelmezés 44, azonos ítélet 48.

### Kérdéstípusonként (helyes értelmezés / helyes elutasítás)

| típus | kérdés | B: 4B (laptop, processzor) | A: 4B (videókártya) |
|---|---|---|---|
| csapda | 11 | 6 | 6 |
| idosor | 8 | 2 | 4 |
| idoszak | 2 | 1 | 2 |
| kombinalt | 13 | 7 | 6 |
| nyelvi | 11 | 2 | 4 |
| osszesito | 1 | 1 | 1 |
| rangsor | 6 | 5 | 5 |
| szures | 4 | 4 | 4 |

## K1: alá nem támasztott állítás a modell szövegében (megválaszolandó kérdések)

Mindkét futás ugyanazzal a kóddal, tehát ugyanazzal a 2. kapuval pontozott. „Eljut”: a megjelölt szöveg a felhasználóhoz kerül (a fő ágon a megjelölt helyett sablon megy ki).

| ág | B: 4B (laptop, processzor) | A: 4B (videókártya) | A − B (párosítva) | eljut: B / A | sablonra vált: B / A |
|---|---|---|---|---|---|
| fő ág (jelölők) | 16/44 = **36,4%** (95%: 23,8% – 51,1%) | 21/45 = **46,7%** (95%: 32,9% – 60,9%) | +11,4 pp (−6,8 pp – +29,5 pp; 44 kérdés) | 0,0% / 0,0% | 36,4% / 46,7% |
| kontrollág (szabad) | 16/44 = **36,4%** (95%: 23,8% – 51,1%) | 19/45 = **42,2%** (95%: 29,0% – 56,7%) | +6,8 pp (−6,8 pp – +20,5 pp; 44 kérdés) | 36,4% / 42,2% | 0,0% / 0,0% |

## Idő (medián)

| futás | ① (értelmezés) | ② fő ág | ② kontrollág | összesen |
|---|---|---|---|---|
| 4B (videókártya) | 3,6 mp | 3,5 mp | 3,7 mp | 19,1 perc |
| 4B (laptop, processzor) | 21,2 mp | 16,5 mp | 17,5 mp | 51,9 perc |

## Kérdésenként

✓ helyes (vagy helyes elutasítás) · ✗ hibás értelmezés · ⊘ téves elutasítás · ! hiányzó elutasítás · ≈ más indokú elutasítás · „=”: azonos ① értelmezés

| # | típus | kérdés | B: 4B (laptop, processzor) | A: 4B (videókártya) | = | A eltérése az elvárttól |
|---|---|---|---|---|---|---|
| k201 | idoszak | mennyi lett a végösszeg az egész 2017-es évre nézve? | ⊘ | ✓ ↑ | ≠ |  |
| k202 | osszesito | hany darab megrendelést kaptunk összesen a kezdettől fogva? | ✓ | ✓ | = |  |
| k203 | idoszak | az elmult félévben mennyi volt a cég teljes bevétele? | ✓ | ✓ | = |  |
| k204 | szures | mi az atlagos rendelesi ertek szombatonkent? | ✓ | ✓ | = |  |
| k205 | rangsor | top 10 legrosszabb kategória a csúszások százaléka alapján? | ✓ | ✓ | = |  |
| k206 | kombinalt | melyik 3 államba küldtük a legkevesebb csomagot idén? | ✓ | ✓ | = |  |
| k207 | rangsor | sorold fel a legjobb öt eladói régiót bevétel szerint! | ✗ | ✗ | = | bontás: ['vevo_regio'] (elvárt: ['elado_allam']) |
| k208 | kombinalt | melyik az a kategória amit a legtöbbször vesznek hétfőn? | ✓ | ✓ | = |  |
| k209 | rangsor | mi a top 5 legdrágább szállítási díjú termékcsoportunk? | ✓ | ✓ | = |  |
| k210 | kombinalt | mennyi volt a forgalom minas gerais-ban 2018 Q2-ben? | ✓ | ✗ ↓ | ≠ | szűrő: {'elado_allam': ['MG']} (elvárt: {'vevo_allam': ['MG']}) |
| k211 | kombinalt | csak a szépségápolást nézve mennyi a szállítási idő átlaga az idén? | ✓ | ✓ | = |  |
| k212 | szures | északi régiós vevőknél hány nap a medián kiszállítás? | ✓ | ✓ | = |  |
| k213 | szures | mennyi idő alatt ér oda egy csomag átlagosan ha a vevő és az eladó i… | ✓ | ✓ | = |  |
| k214 | rangsor | vasarnaponkent tobb a bevétel mint szerdán? | ✓ | ✓ | = |  |
| k215 | kombinalt | hány csomagot vittek ki késve RJ államba tavaly decemberben? | ✓ | ✓ | = |  |
| k216 | idosor | hogy nez ki a 2018-as forgalom honaprol honapra? | ✓ | ✓ | = |  |
| k217 | idosor | éves szinten növekszik a kosárérték? | ✓ | ✓ | = |  |
| k218 | idosor | mutasd a késett rendelések számának havi alakulását 2017 elejétől! | ✗ | ✓ ↑ | ≠ |  |
| k219 | idosor | szallitasi dijak hogy valtoztak negyedevenkent a tavalyi ev folyaman? | ✗ | ✓ ↑ | ≠ |  |
| k220 | kombinalt | a hét napjai szerint hogy oszlik el a rendelések száma idén? | ✓ | ✓ | = |  |
| k221 | nyelvi | ha csak a butorokat meg a sport cuccokat nezem, hol volt a legkisebb… | ✗ | ✓ ↑ | ≠ |  |
| k222 | nyelvi | atlagos tavolsag a vevohoz a delkeleti regioban tavaly nyaron? | ✗ | ✗ | = | tól: 2017-01-01 (elvárt: 2017-06-01); ig: 2017-12-31 (elvárt: 2017-08-31) |
| k223 | kombinalt | SP-ből északra mennyi a fuvardíj mediánja mostanság? | ✗ | ✗ | = | szűrő: {'vevo_allam': ['SP']} (elvárt: {'elado_allam': ['SP'], 'vevo_regio': ['N']}) |
| k224 | kombinalt | 2017 utolso 4 honapjaban mi volt a legpörgősebb 3 kategória bevétel … | ✗ | ✗ | = | tól: 2018-05-01 (elvárt: 2017-09-01); ig: az adat vége (elvárt: 2017-12-31) |
| k225 | kombinalt | az 5 legforgalmasabb allam atlagos szallitasi ideje miben ter el egy… | ✗ | ✗ | = | szűrő: {} (elvárt: {'vevo_allam': ['MG', 'PR', 'RJ', 'RS', 'SP']}) |
| k226 | nyelvi | mibe kerul a szallitas atlagosan a jatekoknal ha pénteken veszik meg… | ✗ | ✗ | = | metrika: atlagos_szallitasi_ido (elvárt: atlagos_szallitasi_dij) |
| k227 | rangsor | mennyi a késés napokban mérve a top 5 legrosszabb államban? | ✓ | ✓ | = |  |
| k228 | kombinalt | hany rendelest hozott a 3 legkisebb regio osszesen 2017 masodik fele… | ✓ | ✓ | = |  |
| k229 | csapda | volt e olyan ev amikor az egeszsegügyi termekekbol tobb fogyott mint… | ! | ! | ≠ | elfogadva: {"bontas": ["kategoria"], "limit": 2, "metrika": "forgalom", "rendezes": "ertek_novekvo", "szuro": {"kategoria": ["computers", "health_beauty"]}} |
| k230 | idosor | csokkent a vallalt szallitasi ido 2017 ota? | ✗ | ✗ | ≠ | bontás: [] (elvárt: ['honap']); tól: 2017-09-15 (elvárt: 2017-01-01); rendezes: ertek_csokkeno (elvárt: bontas) |
| k231 | nyelvi | melyik honapban fognak melle a legnagyobbat a vallalt szallitasi ido… | ✗ | ✗ | = | metrika: atlagos_vallalt_ido (elvárt: atlagos_keses vagy kesesi_arany); bontás: [] (elvárt: ['honap']) |
| k232 | csapda | honnan hova a legmagasabb a fuvar atlag dija idén (régiók között)? | ! | ! | = | elfogadva: {"bontas": ["vevo_regio"], "idoablak": {"tol": "2018-01-01"}, "limit": 10, "metrika": "atlagos_szallitasi_dij", "rendezes": "ertek_csokkeno", "szuro" |
| k233 | idosor | mi a legforgalmasabb honap a lakberendezes kategoria eseteben? | ✗ | ✗ | = | szűrő: {} (elvárt: {'kategoria': ['furniture_decor']}) |
| k234 | rangsor | top 10 kategoria elado-vevo tavolsag szerint (melyiknel utazik a leg… | ✓ | ✓ | = |  |
| k235 | szures | hány nap a csúszás átlaga, ha vasárnap jön be a rendelés? | ✓ | ✓ | = |  |
| k236 | kombinalt | az 5 legnagyobb forgalmu allamban mibol adtak el a legkevesebbet tav… | ✗ | ✗ | = | metrika: atlagos_kosarertek (elvárt: rendelesek_szama vagy forgalom); bontás: ['vevo_allam'] (elvárt: ['kategoria']); szűrő: {} (elvárt: {'vevo_allam': ['MG', ' |
| k237 | nyelvi | menyni vót a legkisebb forgalmu honapunk tavaly? | ✓ | ✓ | = |  |
| k238 | nyelvi | havi bontas 2017 re az atlag szallitasra? | ✓ | ✓ | = |  |
| k239 | idosor | mikor volt a legalacsonyabb a csuszasok szazaleka az egesz idoszakot… | ✗ | ✗ | = | bontás: [] (elvárt: ['honap']) |
| k240 | idosor | 2018 Q1 vs Q2 hogy viszonyul egymashoz atlag kosar ertekben? | ✗ | ✗ | = | bontás: [] (elvárt: ['honap']); ig: 2018-03-31 (elvárt: 2018-06-30); rendezes: ertek_csokkeno (elvárt: bontas) |
| k241 | nyelvi | hova kuldjuk a legtob butort rio-bol? | ✗ | ✗ | ≠ | metrika: forgalom (elvárt: rendelesek_szama) |
| k242 | kombinalt | az elektronika kategoria mediam szallitasi ideje 2017 vs 2018? | ✗ | ✗ | = | metrika: atlagos_szallitasi_ido (elvárt: median_szallitasi_ido); bontás: [] (elvárt: ['ev']); tól: az adat eleje (elvárt: 2017-01-01) |
| k243 | csapda | a 3 legnagyobb regió bevétele negyedévente 2017-től? | ! | ! | = | elfogadva: {"bontas": ["vevo_regio"], "idoablak": {"tol": "2017-01-01"}, "limit": 3, "metrika": "forgalom", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k244 | nyelvi | hanyadik a sorban sao paulo ha a fuvar dijakat nezzuk legolcsóbbtol? | ✗ | ✗ | = | bontás: [] (elvárt: ['vevo_allam']); szűrő: {'vevo_allam': ['SP']} (elvárt: {}) |
| k245 | nyelvi | hany nap a diff a vallalt es a tenyleges kiszallitas kozott atlagosa… | ✗ | ✓ ↑ | ≠ |  |
| k246 | nyelvi | szamitogepeknel mizu a szallitasi atlaggal a 2 legutolso honapban? | ✗ | ✗ | = | szűrő: {} (elvárt: {'kategoria': ['computers']}); tól: az adat eleje (elvárt: 2018-07-01) |
| k247 | nyelvi | elado es vevo kozti atlagos km honaprol honapra tavaly elottrol? | ✗ | ✗ | ≠ | tól: 2017-01-01 (elvárt: az adat eleje); ig: 2017-12-31 (elvárt: 2016-12-31) |
| k248 | kombinalt | az év melyik hónapjában a legmagasabb a fuvardíj mediánja az északke… | ✗ | ✗ | = | bontás: [] (elvárt: ['honap']); rendezes: ertek_novekvo (elvárt: ertek_csokkeno vagy bontas) |
| k250 | csapda | Mennyi volt az adózott eredményünk az utolsó félévben? | ✓ | ✓ | = |  |
| k251 | csapda | Melyik a legrosszabbul értékelt termék a játékok közül? | ✓ | ✓ | = |  |
| k252 | csapda | Hány százaléka lett lemondva a csomagoknak karácsonykor? | ✓ | ✓ | = |  |
| k254 | csapda | Melyik kategória fog a legnagyobbat nőni a következő évben? | ✓ | ≈ ↓ | ≠ | elvárt: nem_elerheto vagy adaton_kivuli_idoablak, kapott: ismeretlen_metrika |
| k255 | csapda | Mi volt a top 3 állam 2014-ben bevétel alapján? | ≈ | ≈ | = | elvárt: adaton_kivuli_idoablak, kapott: ismeretlen_metrika |
| k256 | csapda | Hogyan zártuk a 2019-es évet forgalom szempontjából? | ✓ | ✓ | = |  |
| k259 | csapda | Mekkora a haszonkulcs a bútorokon, ha levonjuk a marketinget? | ✓ | ✓ | = |  |
| k260 | csapda | Melyik futárcég hozta össze a legtöbb késést idén? | ! | ✓ ↑ | ≠ |  |
