# K1 mérés — qwen3.5:9b

Kezdés: 2026-10-22T11:15:34 · ismétlés: 1 · értelmezés és mindkét ág

- modell: `qwen3.5:9b` (`56671c2ab9385f9c`)
- protokoll: `docs/k1_protokoll_v2_9b.json` · SHA256 `c5e8d37d12a367f26ba5d73a4f3a0ed8cd3db53a36d277f36204ce4d68a739d5`
- kérdéssor: `eval/meresi_kerdessor_v2.toml` · SHA256 `1c41464d69438a9ceb47fcdb25c3dcf48fed676eb63cbb92e82101d1c08e5dd9` · 56 kérdés
- promptok: to_spec = `prompts/to_spec.v3.md` (`9266f3285311`), to_text = `prompts/to_text.v3.md` (`401ad3d593d2`), to_text_szabad = `prompts/to_text_szabad.v3.md` (`4070fbfeeb31`)
- kód: commit `c81ccaa6e7a1b9039830afde5e230150d933c800` · ujjlenyomat `7a3a5e94fe9efe50`
- mért egységek (kérdés × ismétlés): 56

## Értelmezés (F-1) és elutasítás (F-2)

| mutató | eredmény | ismétlésenként | cél |
|---|---|---|---|
| F-1 — helyes mérőszám és bontás | 31/45 = **68,9%** (95%: 54,3% – 80,5%) | 68,9% (ismétlésenként: 68,9%) | ≥ 85% |
| teljes egyezés (szűrő, időablak, rendezés is) | 24/45 = **53,3%** (95%: 39,1% – 67,1%) | | |
| F-2 — a csapdát elutasítja | 9/11 = **81,8%** (95%: 52,3% – 94,9%) | 81,8% (ismétlésenként: 81,8%) | ≥ 90% |
| … az elvárt indokkal | 9/11 = **81,8%** (95%: 52,3% – 94,9%) | | |
| ugyanaz a gépi alak minden ismétlésben | 56/56 kérdés | | |

| kérdéstípus | egység | F-1 | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| csapda | 11 | — | 9 |
| idosor | 8 | 4 | 3 |
| idoszak | 2 | 1 | 1 |
| kombinalt | 13 | 9 | 7 |
| nyelvi | 11 | 7 | 3 |
| osszesito | 1 | 1 | 1 |
| rangsor | 6 | 5 | 5 |
| szures | 4 | 4 | 4 |

| szerző | egység | F-1 (megválaszolandó) | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| viola | 56 | 31 | 33 |

| csapda-fajta | egység | elutasítva | az elvárt indokkal |
|---|---|---|---|
| adaton_kivul | 2 | 2 | 2 |
| jovo | 1 | 1 | 1 |
| katalogus_kivul | 1 | 1 | 1 |
| korlat | 3 | 1 | 1 |
| nincs_adat | 4 | 4 | 4 |

## K1 — alá nem támasztott állítás a modell szövegében

A 2. kapu által talált állítások: ez **alsó becslés** (amit a kapu nem lát, azt a kézi ellenőrzés becsli — `kezi_ellenorzes.csv`).

| | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| modellszöveg | 43 | 43 |
| **van benne alá nem támasztott állítás** | 14/43 = **32,6%** (95%: 20,5% – 47,5%) | 13/43 = **30,2%** (95%: 18,6% – 45,1%) |
| … ismétlésenként | 32,6% (ismétlésenként: 32,6%) | 30,2% (ismétlésenként: 30,2%) |
| … és el is jut a felhasználóhoz | 0/43 = **0,0%** (95%: 0,0% – 8,2%) | 13/43 = **30,2%** (95%: 18,6% – 45,1%) |
| a sablonos válasz látszik helyette | 14/43 = **32,6%** (95%: 20,5% – 47,5%) | — (a kontrollág nem vált) |
| leírt számok közül vissza nem vezethető | 2/13 | 5/129 |
| üres / értelmezhetetlen válasz | 0 | 0 |

Páros összevetés (43 kérdés, kérdésenként az ismétlések átlaga): a kontrollág és a fő ág különbsége **−2,3 százalékpont** (95%-os bootstrap-intervallum: −14,0 – 9,3).

| állítás fajtája | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| kitalált jelölő | 1 | 0 |
| vissza nem vezethető szám | 2 | 5 |
| rossz csoporthoz kötött érték | 7 | 3 |
| hamis felsőfok | 10 | 6 |
| a szűrés tagadása | 0 | 1 |

## Idő

| | medián |
|---|---|
| ① kérdés → gépi alak | 4,4 mp |
| … ebből betöltés | 0,0 mp |
| … ebből a prompt beolvasása | 0,5 mp |
| … ebből generálás | 1,8 mp |
| ② fő ág (jelölők) | 4,2 mp |
| ② kontrollág (szabad) | 4,5 mp |
| a mérés összesen | 0,2 óra |

## Ahol az értelmezés nem az elvárt

| # | kérdés | hányszor | ítélet és eltérés (első eset) |
|---|---|---|---|
| k203 | az elmult félévben mennyi volt a cég teljes bevétele? | 1 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „bevetel” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k207 | sorold fel a legjobb öt eladói régiót bevétel szerint! | 1 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: ['elado_allam']) |
| k219 | szallitasi dijak hogy valtoztak negyedevenkent a tavalyi ev folyaman? | 1 | hibás értelmezés: bontás: ['ev'] (elvárt: ['honap']) |
| k222 | atlagos tavolsag a vevohoz a delkeleti regioban tavaly nyaron? | 1 | hibás értelmezés: tól: 2017-01-01 (elvárt: 2017-06-01); ig: 2017-12-31 (elvárt: 2017-08-31) |
| k223 | SP-ből északra mennyi a fuvardíj mediánja mostanság? | 1 | téves elutasítás: nem_elerheto: Ezt nem tudom kiszámolni: a metrikakatalógus a múltról szól; egy rendelés késési kockázatát a „Rendelés kockázata” oldal becsli, havi előrejelzést a rendszer nem ad. Ami közel áll hozzá: késési arány. |
| k224 | 2017 utolso 4 honapjaban mi volt a legpörgősebb 3 kategória bevétel alapján? | 1 | hibás értelmezés: tól: 2018-05-01 (elvárt: 2017-09-01); ig: az adat vége (elvárt: 2017-12-31) |
| k225 | az 5 legforgalmasabb allam atlagos szallitasi ideje miben ter el egymastol 2018-ban? | 1 | hibás értelmezés: szűrő: {} (elvárt: {'vevo_allam': ['MG', 'PR', 'RJ', 'RS', 'SP']}) |
| k226 | mibe kerul a szallitas atlagosan a jatekoknal ha pénteken veszik meg oket? | 1 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: atlagos_szallitasi_dij) |
| k229 | volt e olyan ev amikor az egeszsegügyi termekekbol tobb fogyott mint a szamitogepekbol? | 1 | hiányzó elutasítás: elfogadva: {"bontas": [], "limit": 10, "metrika": "forgalom", "rendezes": "ertek_novekvo", "szuro": {"kategoria": ["health_beauty"]}} |
| k230 | csokkent a vallalt szallitasi ido 2017 ota? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); rendezes: ertek_novekvo (elvárt: bontas) |
| k231 | melyik honapban fognak melle a legnagyobbat a vallalt szallitasi idovel a deli regioban? | 1 | hibás értelmezés: metrika: atlagos_vallalt_ido (elvárt: atlagos_keses vagy kesesi_arany); bontás: ['vevo_regio'] (elvárt: ['honap']); szűrő: {} (elvárt: {'vevo_regio': ['S']}) |
| k233 | mi a legforgalmasabb honap a lakberendezes kategoria eseteben? | 1 | hibás értelmezés: szűrő: {} (elvárt: {'kategoria': ['furniture_decor']}) |
| k236 | az 5 legnagyobb forgalmu allamban mibol adtak el a legkevesebbet tavaly? | 1 | hibás értelmezés: bontás: ['vevo_allam'] (elvárt: ['kategoria']); szűrő: {} (elvárt: {'vevo_allam': ['MG', 'PR', 'RJ', 'RS', 'SP']}) |
| k239 | mikor volt a legalacsonyabb a csuszasok szazaleka az egesz idoszakot nezve? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']) |
| k240 | 2018 Q1 vs Q2 hogy viszonyul egymashoz atlag kosar ertekben? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); ig: 2018-03-31 (elvárt: 2018-06-30); rendezes: ertek_csokkeno (elvárt: bontas) |
| k241 | hova kuldjuk a legtob butort rio-bol? | 1 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: rendelesek_szama); szűrő: {'elado_allam': ['RJ']} (elvárt: {'elado_allam': ['RJ'], 'kategoria': ['furniture_decor']}); rendezes: ertek_novekvo (elvárt: ertek_csokkeno) |
| k242 | az elektronika kategoria mediam szallitasi ideje 2017 vs 2018? | 1 | hibás értelmezés: bontás: [] (elvárt: ['ev']); rendezes: ertek_csokkeno (elvárt: bontas) |
| k243 | a 3 legnagyobb regió bevétele negyedévente 2017-től? | 1 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_regio"], "idoablak": {"tol": "2017-01-01"}, "limit": 3, "metrika": "forgalom", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k244 | hanyadik a sorban sao paulo ha a fuvar dijakat nezzuk legolcsóbbtol? | 1 | hibás értelmezés: bontás: [] (elvárt: ['vevo_allam']); szűrő: {'vevo_allam': ['SP']} (elvárt: {}) |
| k245 | hany nap a diff a vallalt es a tenyleges kiszallitas kozott atlagosan 2018 tavaszan? | 1 | hibás értelmezés: tól: 2018-04-01 (elvárt: 2018-03-01); ig: 2018-06-30 (elvárt: 2018-05-31) |
| k246 | szamitogepeknel mizu a szallitasi atlaggal a 2 legutolso honapban? | 1 | hibás értelmezés: tól: az adat eleje (elvárt: 2018-07-01) |
| k247 | elado es vevo kozti atlagos km honaprol honapra tavaly elottrol? | 1 | hibás értelmezés: tól: 2017-01-01 (elvárt: az adat eleje); ig: 2017-12-31 (elvárt: 2016-12-31) |
| k248 | az év melyik hónapjában a legmagasabb a fuvardíj mediánja az északkeleti régiónál? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']) |
