# K1 mérés — qwen3.5:4b

Kezdés: 2026-10-20T13:00:11 · ismétlés: 1 · értelmezés és mindkét ág

- modell: `qwen3.5:4b` (`d8b0f5e9760cd168`)
- protokoll: `docs/k1_protokoll_v2.json` · SHA256 `04ceaec1b26cb199d88f343f7d18c80a41c189399979d483cbc63450fd0c903b`
- kérdéssor: `eval/meresi_kerdessor_v2.toml` · SHA256 `1c41464d69438a9ceb47fcdb25c3dcf48fed676eb63cbb92e82101d1c08e5dd9` · 56 kérdés
- promptok: to_spec = `prompts/to_spec.v3.md` (`9266f3285311`), to_text = `prompts/to_text.v3.md` (`401ad3d593d2`), to_text_szabad = `prompts/to_text_szabad.v3.md` (`4070fbfeeb31`)
- kód: commit `d809a66d4ca4238ac15c34865bdcbbcaefb2cdd8` · ujjlenyomat `7a3a5e94fe9efe50`
- mért egységek (kérdés × ismétlés): 56

## Értelmezés (F-1) és elutasítás (F-2)

| mutató | eredmény | ismétlésenként | cél |
|---|---|---|---|
| F-1 — helyes mérőszám és bontás | 30/45 = **66,7%** (95%: 52,1% – 78,6%) | 66,7% (ismétlésenként: 66,7%) | ≥ 85% |
| teljes egyezés (szűrő, időablak, rendezés is) | 22/45 = **48,9%** (95%: 35,0% – 63,0%) | | |
| F-2 — a csapdát elutasítja | 7/11 = **63,6%** (95%: 35,4% – 84,8%) | 63,6% (ismétlésenként: 63,6%) | ≥ 90% |
| … az elvárt indokkal | 6/11 = **54,5%** (95%: 28,0% – 78,7%) | | |
| ugyanaz a gépi alak minden ismétlésben | 56/56 kérdés | | |

| kérdéstípus | egység | F-1 | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| csapda | 11 | — | 6 |
| idosor | 8 | 4 | 2 |
| idoszak | 2 | 1 | 1 |
| kombinalt | 13 | 10 | 7 |
| nyelvi | 11 | 5 | 2 |
| osszesito | 1 | 1 | 1 |
| rangsor | 6 | 5 | 5 |
| szures | 4 | 4 | 4 |

| szerző | egység | F-1 (megválaszolandó) | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| viola | 56 | 30 | 28 |

| csapda-fajta | egység | elutasítva | az elvárt indokkal |
|---|---|---|---|
| adaton_kivul | 2 | 2 | 1 |
| jovo | 1 | 1 | 1 |
| katalogus_kivul | 1 | 0 | 0 |
| korlat | 3 | 0 | 0 |
| nincs_adat | 4 | 4 | 4 |

## K1 — alá nem támasztott állítás a modell szövegében

A 2. kapu által talált állítások: ez **alsó becslés** (amit a kapu nem lát, azt a kézi ellenőrzés becsli — `kezi_ellenorzes.csv`).

| | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| modellszöveg | 44 | 44 |
| **van benne alá nem támasztott állítás** | 16/44 = **36,4%** (95%: 23,8% – 51,1%) | 16/44 = **36,4%** (95%: 23,8% – 51,1%) |
| … ismétlésenként | 36,4% (ismétlésenként: 36,4%) | 36,4% (ismétlésenként: 36,4%) |
| … és el is jut a felhasználóhoz | 0/44 = **0,0%** (95%: 0,0% – 8,0%) | 16/44 = **36,4%** (95%: 23,8% – 51,1%) |
| a sablonos válasz látszik helyette | 16/44 = **36,4%** (95%: 23,8% – 51,1%) | — (a kontrollág nem vált) |
| leírt számok közül vissza nem vezethető | 5/38 | 21/130 |
| üres / értelmezhetetlen válasz | 0 | 0 |

Páros összevetés (44 kérdés, kérdésenként az ismétlések átlaga): a kontrollág és a fő ág különbsége **0,0 százalékpont** (95%-os bootstrap-intervallum: −15,9 – 18,2).

| állítás fajtája | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| kitalált jelölő | 18 | 0 |
| vissza nem vezethető szám | 5 | 21 |
| rossz csoporthoz kötött érték | 4 | 5 |
| hamis felsőfok | 3 | 3 |
| a tartomány hamis szerepe | 0 | 1 |

## Idő

| | medián |
|---|---|
| ① kérdés → gépi alak | 21,2 mp |
| … ebből betöltés | 0,0 mp |
| … ebből a prompt beolvasása | 11,5 mp |
| … ebből generálás | 9,5 mp |
| ② fő ág (jelölők) | 16,5 mp |
| ② kontrollág (szabad) | 17,5 mp |
| a mérés összesen | 0,9 óra |

## Ahol az értelmezés nem az elvárt

| # | kérdés | hányszor | ítélet és eltérés (első eset) |
|---|---|---|---|
| k201 | mennyi lett a végösszeg az egész 2017-es évre nézve? | 1 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „végösszeg” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k207 | sorold fel a legjobb öt eladói régiót bevétel szerint! | 1 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: ['elado_allam']) |
| k218 | mutasd a késett rendelések számának havi alakulását 2017 elejétől! | 1 | hibás értelmezés: ig: 2017-12-31 (elvárt: az adat vége) |
| k219 | szallitasi dijak hogy valtoztak negyedevenkent a tavalyi ev folyaman? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); rendezes: ertek_csokkeno (elvárt: bontas) |
| k221 | ha csak a butorokat meg a sport cuccokat nezem, hol volt a legkisebb a keses aranya az elmult 3 honapban? | 1 | hibás értelmezés: bontás: [] (elvárt: ['kategoria']) |
| k222 | atlagos tavolsag a vevohoz a delkeleti regioban tavaly nyaron? | 1 | hibás értelmezés: tól: 2017-01-01 (elvárt: 2017-06-01); ig: 2017-12-31 (elvárt: 2017-08-31) |
| k223 | SP-ből északra mennyi a fuvardíj mediánja mostanság? | 1 | hibás értelmezés: szűrő: {'vevo_allam': ['SP']} (elvárt: {'elado_allam': ['SP'], 'vevo_regio': ['N']}) |
| k224 | 2017 utolso 4 honapjaban mi volt a legpörgősebb 3 kategória bevétel alapján? | 1 | hibás értelmezés: tól: 2018-05-01 (elvárt: 2017-09-01); ig: az adat vége (elvárt: 2017-12-31) |
| k225 | az 5 legforgalmasabb allam atlagos szallitasi ideje miben ter el egymastol 2018-ban? | 1 | hibás értelmezés: szűrő: {} (elvárt: {'vevo_allam': ['MG', 'PR', 'RJ', 'RS', 'SP']}) |
| k226 | mibe kerul a szallitas atlagosan a jatekoknal ha pénteken veszik meg oket? | 1 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: atlagos_szallitasi_dij) |
| k229 | volt e olyan ev amikor az egeszsegügyi termekekbol tobb fogyott mint a szamitogepekbol? | 1 | hiányzó elutasítás: elfogadva: {"bontas": ["kategoria"], "limit": 10, "metrika": "forgalom", "rendezes": "ertek_novekvo", "szuro": {}} |
| k230 | csokkent a vallalt szallitasi ido 2017 ota? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); tól: 2017-09-01 (elvárt: 2017-01-01); rendezes: ertek_csokkeno (elvárt: bontas) |
| k231 | melyik honapban fognak melle a legnagyobbat a vallalt szallitasi idovel a deli regioban? | 1 | hibás értelmezés: metrika: atlagos_vallalt_ido (elvárt: atlagos_keses vagy kesesi_arany); bontás: [] (elvárt: ['honap']) |
| k232 | honnan hova a legmagasabb a fuvar atlag dija idén (régiók között)? | 1 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_regio"], "idoablak": {"tol": "2018-01-01"}, "limit": 10, "metrika": "atlagos_szallitasi_dij", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k233 | mi a legforgalmasabb honap a lakberendezes kategoria eseteben? | 1 | hibás értelmezés: szűrő: {} (elvárt: {'kategoria': ['furniture_decor']}) |
| k236 | az 5 legnagyobb forgalmu allamban mibol adtak el a legkevesebbet tavaly? | 1 | hibás értelmezés: metrika: atlagos_kosarertek (elvárt: rendelesek_szama vagy forgalom); bontás: ['vevo_allam'] (elvárt: ['kategoria']); szűrő: {} (elvárt: {'vevo_allam': ['MG', 'PR', 'RJ', 'RS', 'SP']}) |
| k239 | mikor volt a legalacsonyabb a csuszasok szazaleka az egesz idoszakot nezve? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']) |
| k240 | 2018 Q1 vs Q2 hogy viszonyul egymashoz atlag kosar ertekben? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); ig: 2018-03-31 (elvárt: 2018-06-30); rendezes: ertek_csokkeno (elvárt: bontas) |
| k241 | hova kuldjuk a legtob butort rio-bol? | 1 | hibás értelmezés: metrika: forgalom (elvárt: rendelesek_szama); bontás: [] (elvárt: ['vevo_allam']) |
| k242 | az elektronika kategoria mediam szallitasi ideje 2017 vs 2018? | 1 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: median_szallitasi_ido); bontás: [] (elvárt: ['ev']); tól: az adat eleje (elvárt: 2017-01-01) |
| k243 | a 3 legnagyobb regió bevétele negyedévente 2017-től? | 1 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_regio"], "idoablak": {"tol": "2017-01-01"}, "limit": 3, "metrika": "forgalom", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k244 | hanyadik a sorban sao paulo ha a fuvar dijakat nezzuk legolcsóbbtol? | 1 | hibás értelmezés: bontás: [] (elvárt: ['vevo_allam']); szűrő: {'vevo_allam': ['SP']} (elvárt: {}) |
| k245 | hany nap a diff a vallalt es a tenyleges kiszallitas kozott atlagosan 2018 tavaszan? | 1 | hibás értelmezés: tól: 2018-04-01 (elvárt: 2018-03-01); ig: 2018-06-30 (elvárt: 2018-05-31) |
| k246 | szamitogepeknel mizu a szallitasi atlaggal a 2 legutolso honapban? | 1 | hibás értelmezés: szűrő: {} (elvárt: {'kategoria': ['computers']}); tól: az adat eleje (elvárt: 2018-07-01) |
| k247 | elado es vevo kozti atlagos km honaprol honapra tavaly elottrol? | 1 | hibás értelmezés: bontás: ['vevo_allam'] (elvárt: ['honap']); tól: 2017-01-01 (elvárt: az adat eleje); ig: 2017-12-31 (elvárt: 2016-12-31); rendezes: ertek_csokkeno (elvárt: bontas) |
| k248 | az év melyik hónapjában a legmagasabb a fuvardíj mediánja az északkeleti régiónál? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); rendezes: ertek_novekvo (elvárt: ertek_csokkeno vagy bontas) |
| k255 | Mi volt a top 3 állam 2014-ben bevétel alapján? | 1 | más elutasítás: elvárt: adaton_kivuli_idoablak, kapott: ismeretlen_metrika |
| k260 | Melyik futárcég hozta össze a legtöbb késést idén? | 1 | hiányzó elutasítás: elfogadva: {"bontas": [], "idoablak": {"tol": "2018-01-01"}, "limit": 10, "metrika": "atlagos_keses", "rendezes": "ertek_csokkeno", "szuro": {}} |
