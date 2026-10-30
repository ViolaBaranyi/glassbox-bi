# K1 mérés — qwen3.5:2b

Kezdés: 2026-10-20T14:04:14 · ismétlés: 1 · értelmezés és mindkét ág

- modell: `qwen3.5:2b` (`0689d44085e06d16`)
- protokoll: `docs/k1_protokoll_v2.json` · SHA256 `04ceaec1b26cb199d88f343f7d18c80a41c189399979d483cbc63450fd0c903b`
- kérdéssor: `eval/meresi_kerdessor_v2.toml` · SHA256 `1c41464d69438a9ceb47fcdb25c3dcf48fed676eb63cbb92e82101d1c08e5dd9` · 56 kérdés
- promptok: to_spec = `prompts/to_spec.v3.md` (`9266f3285311`), to_text = `prompts/to_text.v3.md` (`401ad3d593d2`), to_text_szabad = `prompts/to_text_szabad.v3.md` (`4070fbfeeb31`)
- kód: commit `d809a66d4ca4238ac15c34865bdcbbcaefb2cdd8` · ujjlenyomat `7a3a5e94fe9efe50`
- mért egységek (kérdés × ismétlés): 56

## Értelmezés (F-1) és elutasítás (F-2)

| mutató | eredmény | ismétlésenként | cél |
|---|---|---|---|
| F-1 — helyes mérőszám és bontás | 16/45 = **35,6%** (95%: 23,2% – 50,2%) | 35,6% (ismétlésenként: 35,6%) | ≥ 85% |
| teljes egyezés (szűrő, időablak, rendezés is) | 9/45 = **20,0%** (95%: 10,9% – 33,8%) | | |
| F-2 — a csapdát elutasítja | 11/11 = **100,0%** (95%: 74,1% – 100,0%) | 100,0% (ismétlésenként: 100,0%) | ≥ 90% |
| … az elvárt indokkal | 10/11 = **90,9%** (95%: 62,3% – 98,4%) | | |
| ugyanaz a gépi alak minden ismétlésben | 56/56 kérdés | | |

| kérdéstípus | egység | F-1 | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| csapda | 11 | — | 10 |
| idosor | 8 | 3 | 2 |
| idoszak | 2 | 1 | 1 |
| kombinalt | 13 | 6 | 2 |
| nyelvi | 11 | 3 | 1 |
| osszesito | 1 | 1 | 1 |
| rangsor | 6 | 1 | 1 |
| szures | 4 | 1 | 1 |

| szerző | egység | F-1 (megválaszolandó) | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| viola | 56 | 16 | 19 |

| csapda-fajta | egység | elutasítva | az elvárt indokkal |
|---|---|---|---|
| adaton_kivul | 2 | 2 | 1 |
| jovo | 1 | 1 | 1 |
| katalogus_kivul | 1 | 1 | 1 |
| korlat | 3 | 3 | 3 |
| nincs_adat | 4 | 4 | 4 |

## K1 — alá nem támasztott állítás a modell szövegében

A 2. kapu által talált állítások: ez **alsó becslés** (amit a kapu nem lát, azt a kézi ellenőrzés becsli — `kezi_ellenorzes.csv`).

| | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| modellszöveg | 30 | 30 |
| **van benne alá nem támasztott állítás** | 18/30 = **60,0%** (95%: 42,3% – 75,4%) | 16/30 = **53,3%** (95%: 36,1% – 69,8%) |
| … ismétlésenként | 60,0% (ismétlésenként: 60,0%) | 53,3% (ismétlésenként: 53,3%) |
| … és el is jut a felhasználóhoz | 0/30 = **0,0%** (95%: 0,0% – 11,4%) | 16/30 = **53,3%** (95%: 36,1% – 69,8%) |
| a sablonos válasz látszik helyette | 18/30 = **60,0%** (95%: 42,3% – 75,4%) | — (a kontrollág nem vált) |
| leírt számok közül vissza nem vezethető | 9/49 | 5/71 |
| üres / értelmezhetetlen válasz | 0 | 0 |

Páros összevetés (30 kérdés, kérdésenként az ismétlések átlaga): a kontrollág és a fő ág különbsége **−6,7 százalékpont** (95%-os bootstrap-intervallum: −23,3 – 10,0).

| állítás fajtája | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| kitalált jelölő | 5 | 0 |
| vissza nem vezethető szám | 9 | 5 |
| rossz csoporthoz kötött érték | 15 | 3 |
| hamis felsőfok | 14 | 12 |
| a tartomány hamis szerepe | 1 | 1 |
| a szűrés tagadása | 0 | 2 |

## Idő

| | medián |
|---|---|
| ① kérdés → gépi alak | 22,0 mp |
| … ebből betöltés | 0,0 mp |
| … ebből a prompt beolvasása | 11,5 mp |
| … ebből generálás | 10,2 mp |
| ② fő ág (jelölők) | 18,6 mp |
| ② kontrollág (szabad) | 18,7 mp |
| a mérés összesen | 0,8 óra |

## Ahol az értelmezés nem az elvárt

| # | kérdés | hányszor | ítélet és eltérés (első eset) |
|---|---|---|---|
| k203 | az elmult félévben mennyi volt a cég teljes bevétele? | 1 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „teljes bevétele” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k204 | mi az atlagos rendelesi ertek szombatonkent? | 1 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: atlagos_kosarertek); szűrő: {} (elvárt: {'het_napja': ['6']}) |
| k207 | sorold fel a legjobb öt eladói régiót bevétel szerint! | 1 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „bevétel” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k208 | melyik az a kategória amit a legtöbbször vesznek hétfőn? | 1 | téves elutasítás: ertelmezhetetlen: A nyelvi modell válaszából nem lett érvényes kérdés-specifikáció, ezért nem mondok számot. Fogalmazd meg másképp, vagy állítsd össze a kérdést a kérdésépítővel. |
| k209 | mi a top 5 legdrágább szállítási díjú termékcsoportunk? | 1 | téves elutasítás: ertelmezhetetlen: A nyelvi modell válaszából nem lett érvényes kérdés-specifikáció, ezért nem mondok számot. Fogalmazd meg másképp, vagy állítsd össze a kérdést a kérdésépítővel. |
| k210 | mennyi volt a forgalom minas gerais-ban 2018 Q2-ben? | 1 | hibás értelmezés: szűrő: {} (elvárt: {'vevo_allam': ['MG']}) |
| k211 | csak a szépségápolást nézve mennyi a szállítási idő átlaga az idén? | 1 | hibás értelmezés: szűrő: {} (elvárt: {'kategoria': ['health_beauty']}) |
| k212 | északi régiós vevőknél hány nap a medián kiszállítás? | 1 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: median_szallitasi_ido) |
| k214 | vasarnaponkent tobb a bevétel mint szerdán? | 1 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „bevétel” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k215 | hány csomagot vittek ki késve RJ államba tavaly decemberben? | 1 | téves elutasítás: ertelmezhetetlen: A nyelvi modell válaszából nem lett érvényes kérdés-specifikáció, ezért nem mondok számot. Fogalmazd meg másképp, vagy állítsd össze a kérdést a kérdésépítővel. |
| k217 | éves szinten növekszik a kosárérték? | 1 | hibás értelmezés: bontás: [] (elvárt: ['ev']); rendezes: ertek_csokkeno (elvárt: bontas) |
| k218 | mutasd a késett rendelések számának havi alakulását 2017 elejétől! | 1 | hibás értelmezés: ig: 2017-12-31 (elvárt: az adat vége) |
| k221 | ha csak a butorokat meg a sport cuccokat nezem, hol volt a legkisebb a keses aranya az elmult 3 honapban? | 1 | hibás értelmezés: bontás: [] (elvárt: ['kategoria']); szűrő: {'kategoria': ['fashion_sport']} (elvárt: {'kategoria': ['furniture_decor', 'sports_leisure']}); rendezes: ertek_csokkeno (elvárt: ertek_novekvo) |
| k222 | atlagos tavolsag a vevohoz a delkeleti regioban tavaly nyaron? | 1 | hibás értelmezés: tól: 2017-01-01 (elvárt: 2017-06-01); ig: 2017-12-31 (elvárt: 2017-08-31) |
| k223 | SP-ből északra mennyi a fuvardíj mediánja mostanság? | 1 | téves elutasítás: ertelmezhetetlen: A nyelvi modell válaszából nem lett érvényes kérdés-specifikáció, ezért nem mondok számot. Fogalmazd meg másképp, vagy állítsd össze a kérdést a kérdésépítővel. |
| k224 | 2017 utolso 4 honapjaban mi volt a legpörgősebb 3 kategória bevétel alapján? | 1 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „bevétel” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k225 | az 5 legforgalmasabb allam atlagos szallitasi ideje miben ter el egymastol 2018-ban? | 1 | hibás értelmezés: szűrő: {} (elvárt: {'vevo_allam': ['MG', 'PR', 'RJ', 'RS', 'SP']}) |
| k226 | mibe kerul a szallitas atlagosan a jatekoknal ha pénteken veszik meg oket? | 1 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: atlagos_szallitasi_dij) |
| k227 | mennyi a késés napokban mérve a top 5 legrosszabb államban? | 1 | hibás értelmezés: metrika: kesesi_arany (elvárt: atlagos_keses) |
| k228 | hany rendelest hozott a 3 legkisebb regio osszesen 2017 masodik feleben? | 1 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: []); szűrő: {} (elvárt: {'vevo_regio': ['CO', 'N', 'NE']}) |
| k230 | csokkent a vallalt szallitasi ido 2017 ota? | 1 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: atlagos_vallalt_ido); ig: 2017-09-30 (elvárt: az adat vége) |
| k231 | melyik honapban fognak melle a legnagyobbat a vallalt szallitasi idovel a deli regioban? | 1 | téves elutasítás: nem_elerheto: Ezt nem tudom kiszámolni: a metrikakatalógus a múltról szól; egy rendelés késési kockázatát a „Rendelés kockázata” oldal becsli, havi előrejelzést a rendszer nem ad. Ami közel áll hozzá: késési arány. |
| k233 | mi a legforgalmasabb honap a lakberendezes kategoria eseteben? | 1 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: forgalom vagy rendelesek_szama); szűrő: {} (elvárt: {'kategoria': ['furniture_decor']}) |
| k234 | top 10 kategoria elado-vevo tavolsag szerint (melyiknel utazik a legtobbet a csomag)? | 1 | téves elutasítás: ertelmezhetetlen: A nyelvi modell válaszából nem lett érvényes kérdés-specifikáció, ezért nem mondok számot. Fogalmazd meg másképp, vagy állítsd össze a kérdést a kérdésépítővel. |
| k235 | hány nap a csúszás átlaga, ha vasárnap jön be a rendelés? | 1 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „csúszás” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k236 | az 5 legnagyobb forgalmu allamban mibol adtak el a legkevesebbet tavaly? | 1 | hibás értelmezés: bontás: ['vevo_allam'] (elvárt: ['kategoria']); szűrő: {} (elvárt: {'vevo_allam': ['MG', 'PR', 'RJ', 'RS', 'SP']}); rendezes: ertek_csokkeno (elvárt: ertek_novekvo) |
| k237 | menyni vót a legkisebb forgalmu honapunk tavaly? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); rendezes: ertek_csokkeno (elvárt: ertek_novekvo vagy bontas) |
| k239 | mikor volt a legalacsonyabb a csuszasok szazaleka az egesz idoszakot nezve? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); rendezes: ertek_csokkeno (elvárt: ertek_novekvo vagy bontas) |
| k240 | 2018 Q1 vs Q2 hogy viszonyul egymashoz atlag kosar ertekben? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); ig: 2018-03-31 (elvárt: 2018-06-30); rendezes: ertek_csokkeno (elvárt: bontas) |
| k241 | hova kuldjuk a legtob butort rio-bol? | 1 | téves elutasítás: nem_elerheto: Ezt nem tudom kiszámolni: az adathalmaz nem tartalmaz beszerzési árat, ezért haszon vagy árrés nem számolható. Ami közel áll hozzá: átlagos kosárérték és átlagos szállítási díj. |
| k242 | az elektronika kategoria mediam szallitasi ideje 2017 vs 2018? | 1 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: median_szallitasi_ido); bontás: [] (elvárt: ['ev']); tól: 2017-09-01 (elvárt: 2017-01-01); rendezes: ertek_csokkeno (elvárt: bontas) |
| k244 | hanyadik a sorban sao paulo ha a fuvar dijakat nezzuk legolcsóbbtol? | 1 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „fuvar díjak” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k245 | hany nap a diff a vallalt es a tenyleges kiszallitas kozott atlagosan 2018 tavaszan? | 1 | hibás értelmezés: bontás: ['honap'] (elvárt: []); ig: 2018-03-31 (elvárt: 2018-05-31) |
| k246 | szamitogepeknel mizu a szallitasi atlaggal a 2 legutolso honapban? | 1 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „szallitasi atlag” nincs a metrikakatalógusban. Ami közel áll hozzá: szállítási idő mediánja. |
| k247 | elado es vevo kozti atlagos km honaprol honapra tavaly elottrol? | 1 | hibás értelmezés: tól: 2017-01-01 (elvárt: az adat eleje); ig: 2017-12-31 (elvárt: 2016-12-31) |
| k248 | az év melyik hónapjában a legmagasabb a fuvardíj mediánja az északkeleti régiónál? | 1 | téves elutasítás: nem_elerheto: Ezt nem tudom kiszámolni: a metrikakatalógus a múltról szól; egy rendelés késési kockázatát a „Rendelés kockázata” oldal becsli, havi előrejelzést a rendszer nem ad. Ami közel áll hozzá: késési arány. |
| k255 | Mi volt a top 3 állam 2014-ben bevétel alapján? | 1 | más elutasítás: elvárt: adaton_kivuli_idoablak, kapott: ismeretlen_metrika |
