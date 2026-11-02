# K1 mérés — qwen3.5:4b

Kezdés: 2026-11-02T02:49:12 · ismétlés: 1 · értelmezés és mindkét ág

- modell: `qwen3.5:4b` (`d8b0f5e9760cd168`)
- protokoll: `docs/k1_protokoll.json` · SHA256 `04ceaec1b26cb199d88f343f7d18c80a41c189399979d483cbc63450fd0c903b`
- kérdéssor: `eval/meresi_kerdessor_v2.toml` · SHA256 `1c41464d69438a9ceb47fcdb25c3dcf48fed676eb63cbb92e82101d1c08e5dd9` · 56 kérdés
- promptok: to_spec = `prompts/to_spec.v3.md` (`9266f3285311`), to_text = `prompts/to_text.v3.md` (`401ad3d593d2`), to_text_szabad = `prompts/to_text_szabad.v3.md` (`4070fbfeeb31`)
- kód: commit `f5db16915e45a111ac7b1c4adb6665c505b8352d` · ujjlenyomat `db97e252c9902346`
- mért egységek (kérdés × ismétlés): 56

## Értelmezés (F-1) és elutasítás (F-2)

| mutató | eredmény | ismétlésenként | cél |
|---|---|---|---|
| F-1 — helyes mérőszám és bontás | 31/45 = **68,9%** (95%: 54,3% – 80,5%) | 68,9% (ismétlésenként: 68,9%) | ≥ 85% |
| teljes egyezés (szűrő, időablak, rendezés is) | 20/45 = **44,4%** (95%: 30,9% – 58,8%) | | |
| F-2 — a csapdát elutasítja | 8/11 = **72,7%** (95%: 43,4% – 90,3%) | 72,7% (ismétlésenként: 72,7%) | ≥ 90% |
| … az elvárt indokkal | 7/11 = **63,6%** (95%: 35,4% – 84,8%) | | |
| ugyanaz a gépi alak minden ismétlésben | 56/56 kérdés | | |

| kérdéstípus | egység | F-1 | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| csapda | 11 | — | 7 |
| idosor | 8 | 5 | 2 |
| idoszak | 2 | 2 | 1 |
| kombinalt | 13 | 9 | 6 |
| nyelvi | 11 | 6 | 2 |
| osszesito | 1 | 1 | 1 |
| rangsor | 6 | 4 | 4 |
| szures | 4 | 4 | 4 |

| szerző | egység | F-1 (megválaszolandó) | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| viola | 56 | 31 | 27 |

| csapda-fajta | egység | elutasítva | az elvárt indokkal |
|---|---|---|---|
| adaton_kivul | 2 | 2 | 1 |
| jovo | 1 | 1 | 1 |
| katalogus_kivul | 1 | 1 | 1 |
| korlat | 3 | 0 | 0 |
| nincs_adat | 4 | 4 | 4 |

## K1 — alá nem támasztott állítás a modell szövegében

A 2. kapu által talált állítások: ez **alsó becslés** (amit a kapu nem lát, azt a kézi ellenőrzés becsli — `kezi_ellenorzes.csv`).

| | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| modellszöveg | 43 | 43 |
| **van benne alá nem támasztott állítás** | 26/43 = **60,5%** (95%: 45,6% – 73,6%) | 21/43 = **48,8%** (95%: 34,6% – 63,2%) |
| … ismétlésenként | 60,5% (ismétlésenként: 60,5%) | 48,8% (ismétlésenként: 48,8%) |
| … és el is jut a felhasználóhoz | 0/43 = **0,0%** (95%: 0,0% – 8,2%) | 21/43 = **48,8%** (95%: 34,6% – 63,2%) |
| a sablonos válasz látszik helyette | 26/43 = **60,5%** (95%: 45,6% – 73,6%) | — (a kontrollág nem vált) |
| leírt számok közül vissza nem vezethető | 9/36 | 20/129 |
| üres / értelmezhetetlen válasz | 0 | 0 |

Páros összevetés (43 kérdés, kérdésenként az ismétlések átlaga): a kontrollág és a fő ág különbsége **−11,6 százalékpont** (95%-os bootstrap-intervallum: −27,9 – 2,3).

| állítás fajtája | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| kitalált jelölő | 13 | 0 |
| vissza nem vezethető szám | 9 | 20 |
| rossz csoporthoz kötött érték | 15 | 7 |
| hamis felsőfok | 7 | 8 |
| a tartomány hamis szerepe | 0 | 1 |
| a szűrés tagadása | 3 | 1 |

## Idő

| | medián |
|---|---|
| ① kérdés → gépi alak | 3,6 mp |
| … ebből betöltés | 0,0 mp |
| … ebből a prompt beolvasása | 0,4 mp |
| … ebből generálás | 1,1 mp |
| ② fő ág (jelölők) | 3,5 mp |
| ② kontrollág (szabad) | 3,5 mp |
| a mérés összesen | 0,1 óra |

## Ahol az értelmezés nem az elvárt

| # | kérdés | hányszor | ítélet és eltérés (első eset) |
|---|---|---|---|
| k203 | az elmult félévben mennyi volt a cég teljes bevétele? | 1 | hibás értelmezés: tól: 2018-04-01 (elvárt: 2018-03-01) |
| k207 | sorold fel a legjobb öt eladói régiót bevétel szerint! | 1 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: ['elado_allam']) |
| k214 | vasarnaponkent tobb a bevétel mint szerdán? | 1 | hibás értelmezés: bontás: [] (elvárt: ['het_napja']); szűrő: {'het_napja': ['3', '7']} (elvárt: {}) |
| k215 | hány csomagot vittek ki késve RJ államba tavaly decemberben? | 1 | téves elutasítás: tiltott_kombinacio: A késett rendelések száma a késésből számolódik, ezért nem szűrhető aszerint, hogy a rendelés késett-e (az eredmény definíció szerint 0 vagy 100% lenne). |
| k216 | hogy nez ki a 2018-as forgalom honaprol honapra? | 1 | hibás értelmezés: rendezes: ertek_csokkeno (elvárt: bontas) |
| k217 | éves szinten növekszik a kosárérték? | 1 | hibás értelmezés: tól: 2017-01-01 (elvárt: az adat eleje); rendezes: ertek_novekvo (elvárt: bontas) |
| k218 | mutasd a késett rendelések számának havi alakulását 2017 elejétől! | 1 | hibás értelmezés: ig: 2017-12-31 (elvárt: az adat vége); rendezes: ertek_csokkeno (elvárt: bontas) |
| k221 | ha csak a butorokat meg a sport cuccokat nezem, hol volt a legkisebb a keses aranya az elmult 3 honapban? | 1 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: ['kategoria']); szűrő: {'kategoria': ['kitchen_dining_laundry_garden_furniture', 'office_furniture']} (elvárt: {'kategoria': ['furniture_decor', 'sports_leisure']}); tól: 2018-06-03 (elvárt: 2018-06-01) |
| k222 | atlagos tavolsag a vevohoz a delkeleti regioban tavaly nyaron? | 1 | hibás értelmezés: tól: 2017-01-01 (elvárt: 2017-06-01); ig: 2017-12-31 (elvárt: 2017-08-31) |
| k223 | SP-ből északra mennyi a fuvardíj mediánja mostanság? | 1 | hibás értelmezés: szűrő: {'vevo_allam': ['SP']} (elvárt: {'elado_allam': ['SP'], 'vevo_regio': ['N']}) |
| k224 | 2017 utolso 4 honapjaban mi volt a legpörgősebb 3 kategória bevétel alapján? | 1 | hibás értelmezés: tól: 2017-07-01 (elvárt: 2017-09-01); ig: 2017-10-31 (elvárt: 2017-12-31) |
| k225 | az 5 legforgalmasabb allam atlagos szallitasi ideje miben ter el egymastol 2018-ban? | 1 | hibás értelmezés: szűrő: {} (elvárt: {'vevo_allam': ['MG', 'PR', 'RJ', 'RS', 'SP']}) |
| k226 | mibe kerul a szallitas atlagosan a jatekoknal ha pénteken veszik meg oket? | 1 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: atlagos_szallitasi_dij) |
| k229 | volt e olyan ev amikor az egeszsegügyi termekekbol tobb fogyott mint a szamitogepekbol? | 1 | hiányzó elutasítás: elfogadva: {"bontas": [], "limit": 10, "metrika": "forgalom", "rendezes": "ertek_novekvo", "szuro": {"kategoria": ["computers", "health_beauty"]}} |
| k230 | csokkent a vallalt szallitasi ido 2017 ota? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); tól: 2017-09-15 (elvárt: 2017-01-01); rendezes: ertek_csokkeno (elvárt: bontas) |
| k231 | melyik honapban fognak melle a legnagyobbat a vallalt szallitasi idovel a deli regioban? | 1 | hibás értelmezés: metrika: atlagos_vallalt_ido (elvárt: atlagos_keses vagy kesesi_arany); bontás: [] (elvárt: ['honap']) |
| k232 | honnan hova a legmagasabb a fuvar atlag dija idén (régiók között)? | 1 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_regio"], "idoablak": {"tol": "2018-01-01"}, "limit": 10, "metrika": "atlagos_szallitasi_dij", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k236 | az 5 legnagyobb forgalmu allamban mibol adtak el a legkevesebbet tavaly? | 1 | hibás értelmezés: metrika: atlagos_kosarertek (elvárt: rendelesek_szama vagy forgalom); bontás: ['vevo_allam'] (elvárt: ['kategoria']); szűrő: {} (elvárt: {'vevo_allam': ['MG', 'PR', 'RJ', 'RS', 'SP']}) |
| k239 | mikor volt a legalacsonyabb a csuszasok szazaleka az egesz idoszakot nezve? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']) |
| k240 | 2018 Q1 vs Q2 hogy viszonyul egymashoz atlag kosar ertekben? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); tól: 2018-03-01 (elvárt: 2018-01-01); rendezes: ertek_csokkeno (elvárt: bontas) |
| k241 | hova kuldjuk a legtob butort rio-bol? | 1 | hibás értelmezés: metrika: forgalom (elvárt: rendelesek_szama); szűrő: {'elado_allam': ['RJ']} (elvárt: {'elado_allam': ['RJ'], 'kategoria': ['furniture_decor']}) |
| k242 | az elektronika kategoria mediam szallitasi ideje 2017 vs 2018? | 1 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: median_szallitasi_ido); bontás: [] (elvárt: ['ev']); tól: az adat eleje (elvárt: 2017-01-01) |
| k243 | a 3 legnagyobb regió bevétele negyedévente 2017-től? | 1 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_regio"], "idoablak": {"tol": "2017-01-01"}, "limit": 3, "metrika": "forgalom", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k244 | hanyadik a sorban sao paulo ha a fuvar dijakat nezzuk legolcsóbbtol? | 1 | hibás értelmezés: bontás: [] (elvárt: ['vevo_allam']); szűrő: {'vevo_allam': ['SP']} (elvárt: {}) |
| k245 | hany nap a diff a vallalt es a tenyleges kiszallitas kozott atlagosan 2018 tavaszan? | 1 | téves elutasítás: ismeretlen_ertek: „ipar és kereskedelem” nem szerepel az adatban (a fő termék kategóriája). Talán: ipar, kereskedelem, üzlet és mezőgazdaság, ipar és kereskedelem. |
| k246 | szamitogepeknel mizu a szallitasi atlaggal a 2 legutolso honapban? | 1 | hibás értelmezés: szűrő: {'kesett': ['idoben']} (elvárt: {'kategoria': ['computers']}) |
| k247 | elado es vevo kozti atlagos km honaprol honapra tavaly elottrol? | 1 | hibás értelmezés: tól: 2017-01-01 (elvárt: az adat eleje); ig: 2017-12-31 (elvárt: 2016-12-31) |
| k248 | az év melyik hónapjában a legmagasabb a fuvardíj mediánja az északkeleti régiónál? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); rendezes: ertek_novekvo (elvárt: ertek_csokkeno vagy bontas) |
| k255 | Mi volt a top 3 állam 2014-ben bevétel alapján? | 1 | más elutasítás: elvárt: adaton_kivuli_idoablak, kapott: ismeretlen_metrika |
