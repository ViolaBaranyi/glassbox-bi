# K1 mérés — qwen3.5:4b

Kezdés: 2026-10-22T10:40:23 · ismétlés: 1 · értelmezés és mindkét ág

- modell: `qwen3.5:4b` (`d8b0f5e9760cd168`)
- protokoll: `docs/k1_protokoll_v2.json` · SHA256 `04ceaec1b26cb199d88f343f7d18c80a41c189399979d483cbc63450fd0c903b`
- kérdéssor: `eval/meresi_kerdessor_v2.toml` · SHA256 `1c41464d69438a9ceb47fcdb25c3dcf48fed676eb63cbb92e82101d1c08e5dd9` · 56 kérdés
- promptok: to_spec = `prompts/to_spec.v3.md` (`9266f3285311`), to_text = `prompts/to_text.v3.md` (`401ad3d593d2`), to_text_szabad = `prompts/to_text_szabad.v3.md` (`4070fbfeeb31`)
- kód: commit `69aa58113b4135d6ed03d4f57090e13f8936aaf9` · ujjlenyomat `7a3a5e94fe9efe50`
- mért egységek (kérdés × ismétlés): 56

## Értelmezés (F-1) és elutasítás (F-2)

| mutató | eredmény | ismétlésenként | cél |
|---|---|---|---|
| F-1 — helyes mérőszám és bontás | 34/45 = **75,6%** (95%: 61,3% – 85,8%) | 75,6% (ismétlésenként: 75,6%) | ≥ 85% |
| teljes egyezés (szűrő, időablak, rendezés is) | 26/45 = **57,8%** (95%: 43,3% – 71,0%) | | |
| F-2 — a csapdát elutasítja | 8/11 = **72,7%** (95%: 43,4% – 90,3%) | 72,7% (ismétlésenként: 72,7%) | ≥ 90% |
| … az elvárt indokkal | 6/11 = **54,5%** (95%: 28,0% – 78,7%) | | |
| ugyanaz a gépi alak minden ismétlésben | 56/56 kérdés | | |

| kérdéstípus | egység | F-1 | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| csapda | 11 | — | 6 |
| idosor | 8 | 5 | 4 |
| idoszak | 2 | 2 | 2 |
| kombinalt | 13 | 10 | 6 |
| nyelvi | 11 | 7 | 4 |
| osszesito | 1 | 1 | 1 |
| rangsor | 6 | 5 | 5 |
| szures | 4 | 4 | 4 |

| szerző | egység | F-1 (megválaszolandó) | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| viola | 56 | 34 | 32 |

| csapda-fajta | egység | elutasítva | az elvárt indokkal |
|---|---|---|---|
| adaton_kivul | 2 | 2 | 1 |
| jovo | 1 | 1 | 0 |
| katalogus_kivul | 1 | 1 | 1 |
| korlat | 3 | 0 | 0 |
| nincs_adat | 4 | 4 | 4 |

## K1 — alá nem támasztott állítás a modell szövegében

A 2. kapu által talált állítások: ez **alsó becslés** (amit a kapu nem lát, azt a kézi ellenőrzés becsli — `kezi_ellenorzes.csv`).

| | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| modellszöveg | 45 | 45 |
| **van benne alá nem támasztott állítás** | 21/45 = **46,7%** (95%: 32,9% – 60,9%) | 19/45 = **42,2%** (95%: 29,0% – 56,7%) |
| … ismétlésenként | 46,7% (ismétlésenként: 46,7%) | 42,2% (ismétlésenként: 42,2%) |
| … és el is jut a felhasználóhoz | 0/45 = **0,0%** (95%: 0,0% – 7,9%) | 19/45 = **42,2%** (95%: 29,0% – 56,7%) |
| a sablonos válasz látszik helyette | 21/45 = **46,7%** (95%: 32,9% – 60,9%) | — (a kontrollág nem vált) |
| leírt számok közül vissza nem vezethető | 10/44 | 23/136 |
| üres / értelmezhetetlen válasz | 0 | 0 |

Páros összevetés (45 kérdés, kérdésenként az ismétlések átlaga): a kontrollág és a fő ág különbsége **−4,4 százalékpont** (95%-os bootstrap-intervallum: −15,6 – 8,9).

| állítás fajtája | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| kitalált jelölő | 12 | 0 |
| vissza nem vezethető szám | 10 | 23 |
| rossz csoporthoz kötött érték | 10 | 5 |
| hamis felsőfok | 6 | 5 |
| a tartomány hamis szerepe | 0 | 1 |
| a szűrés tagadása | 1 | 0 |

## Idő

| | medián |
|---|---|
| ① kérdés → gépi alak | 3,6 mp |
| … ebből betöltés | 0,0 mp |
| … ebből a prompt beolvasása | 0,4 mp |
| … ebből generálás | 1,1 mp |
| ② fő ág (jelölők) | 3,5 mp |
| ② kontrollág (szabad) | 3,7 mp |
| a mérés összesen | 0,3 óra |

## Ahol az értelmezés nem az elvárt

| # | kérdés | hányszor | ítélet és eltérés (első eset) |
|---|---|---|---|
| k207 | sorold fel a legjobb öt eladói régiót bevétel szerint! | 1 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: ['elado_allam']) |
| k210 | mennyi volt a forgalom minas gerais-ban 2018 Q2-ben? | 1 | hibás értelmezés: szűrő: {'elado_allam': ['MG']} (elvárt: {'vevo_allam': ['MG']}) |
| k222 | atlagos tavolsag a vevohoz a delkeleti regioban tavaly nyaron? | 1 | hibás értelmezés: tól: 2017-01-01 (elvárt: 2017-06-01); ig: 2017-12-31 (elvárt: 2017-08-31) |
| k223 | SP-ből északra mennyi a fuvardíj mediánja mostanság? | 1 | hibás értelmezés: szűrő: {'vevo_allam': ['SP']} (elvárt: {'elado_allam': ['SP'], 'vevo_regio': ['N']}) |
| k224 | 2017 utolso 4 honapjaban mi volt a legpörgősebb 3 kategória bevétel alapján? | 1 | hibás értelmezés: tól: 2018-05-01 (elvárt: 2017-09-01); ig: az adat vége (elvárt: 2017-12-31) |
| k225 | az 5 legforgalmasabb allam atlagos szallitasi ideje miben ter el egymastol 2018-ban? | 1 | hibás értelmezés: szűrő: {} (elvárt: {'vevo_allam': ['MG', 'PR', 'RJ', 'RS', 'SP']}) |
| k226 | mibe kerul a szallitas atlagosan a jatekoknal ha pénteken veszik meg oket? | 1 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: atlagos_szallitasi_dij) |
| k229 | volt e olyan ev amikor az egeszsegügyi termekekbol tobb fogyott mint a szamitogepekbol? | 1 | hiányzó elutasítás: elfogadva: {"bontas": ["kategoria"], "limit": 2, "metrika": "forgalom", "rendezes": "ertek_novekvo", "szuro": {"kategoria": ["computers", "health_beauty"]}} |
| k230 | csokkent a vallalt szallitasi ido 2017 ota? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); tól: 2017-09-15 (elvárt: 2017-01-01); rendezes: ertek_csokkeno (elvárt: bontas) |
| k231 | melyik honapban fognak melle a legnagyobbat a vallalt szallitasi idovel a deli regioban? | 1 | hibás értelmezés: metrika: atlagos_vallalt_ido (elvárt: atlagos_keses vagy kesesi_arany); bontás: [] (elvárt: ['honap']) |
| k232 | honnan hova a legmagasabb a fuvar atlag dija idén (régiók között)? | 1 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_regio"], "idoablak": {"tol": "2018-01-01"}, "limit": 10, "metrika": "atlagos_szallitasi_dij", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k233 | mi a legforgalmasabb honap a lakberendezes kategoria eseteben? | 1 | hibás értelmezés: szűrő: {} (elvárt: {'kategoria': ['furniture_decor']}) |
| k236 | az 5 legnagyobb forgalmu allamban mibol adtak el a legkevesebbet tavaly? | 1 | hibás értelmezés: metrika: atlagos_kosarertek (elvárt: rendelesek_szama vagy forgalom); bontás: ['vevo_allam'] (elvárt: ['kategoria']); szűrő: {} (elvárt: {'vevo_allam': ['MG', 'PR', 'RJ', 'RS', 'SP']}) |
| k239 | mikor volt a legalacsonyabb a csuszasok szazaleka az egesz idoszakot nezve? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']) |
| k240 | 2018 Q1 vs Q2 hogy viszonyul egymashoz atlag kosar ertekben? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); ig: 2018-03-31 (elvárt: 2018-06-30); rendezes: ertek_csokkeno (elvárt: bontas) |
| k241 | hova kuldjuk a legtob butort rio-bol? | 1 | hibás értelmezés: metrika: forgalom (elvárt: rendelesek_szama) |
| k242 | az elektronika kategoria mediam szallitasi ideje 2017 vs 2018? | 1 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: median_szallitasi_ido); bontás: [] (elvárt: ['ev']); tól: az adat eleje (elvárt: 2017-01-01) |
| k243 | a 3 legnagyobb regió bevétele negyedévente 2017-től? | 1 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_regio"], "idoablak": {"tol": "2017-01-01"}, "limit": 3, "metrika": "forgalom", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k244 | hanyadik a sorban sao paulo ha a fuvar dijakat nezzuk legolcsóbbtol? | 1 | hibás értelmezés: bontás: [] (elvárt: ['vevo_allam']); szűrő: {'vevo_allam': ['SP']} (elvárt: {}) |
| k246 | szamitogepeknel mizu a szallitasi atlaggal a 2 legutolso honapban? | 1 | hibás értelmezés: szűrő: {} (elvárt: {'kategoria': ['computers']}); tól: az adat eleje (elvárt: 2018-07-01) |
| k247 | elado es vevo kozti atlagos km honaprol honapra tavaly elottrol? | 1 | hibás értelmezés: tól: 2017-01-01 (elvárt: az adat eleje); ig: 2017-12-31 (elvárt: 2016-12-31) |
| k248 | az év melyik hónapjában a legmagasabb a fuvardíj mediánja az északkeleti régiónál? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); rendezes: ertek_novekvo (elvárt: ertek_csokkeno vagy bontas) |
| k254 | Melyik kategória fog a legnagyobbat nőni a következő évben? | 1 | más elutasítás: elvárt: nem_elerheto vagy adaton_kivuli_idoablak, kapott: ismeretlen_metrika |
| k255 | Mi volt a top 3 állam 2014-ben bevétel alapján? | 1 | más elutasítás: elvárt: adaton_kivuli_idoablak, kapott: ismeretlen_metrika |
