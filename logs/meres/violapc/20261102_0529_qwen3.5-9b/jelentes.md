# K1 mérés — qwen3.5:9b

Kezdés: 2026-11-02T05:29:10 · ismétlés: 3 · értelmezés és mindkét ág

- modell: `qwen3.5:9b` (`56671c2ab9385f9c`)
- protokoll: `docs/k1_protokoll.json` · SHA256 `ff0dd6b79df38c89991cfee2bf4ddd8ed69bea6e420d53e02e9fb38374a8b1e6`
- kérdéssor: `eval/meresi_kerdessor.toml` · SHA256 `ce87d85fd44038c96f107f6474b4c6cdf1a5978afb88b3bfa6629784a69bc01f` · 130 kérdés
- promptok: to_spec = `prompts/to_spec.v3.md` (`9266f3285311`), to_text = `prompts/to_text.v3.md` (`401ad3d593d2`), to_text_szabad = `prompts/to_text_szabad.v3.md` (`4070fbfeeb31`)
- kód: commit `f5db16915e45a111ac7b1c4adb6665c505b8352d` · ujjlenyomat `db97e252c9902346`
- mért egységek (kérdés × ismétlés): 390

## Értelmezés (F-1) és elutasítás (F-2)

| mutató | eredmény | ismétlésenként | cél |
|---|---|---|---|
| F-1 — helyes mérőszám és bontás | 255/306 = **83,3%** (95%: 78,7% – 87,1%) | 83,3% ± 0,0% (ismétlésenként: 83,3%, 83,3%, 83,3%) | ≥ 85% |
| teljes egyezés (szűrő, időablak, rendezés is) | 224/306 = **73,2%** (95%: 68,0% – 77,9%) | | |
| F-2 — a csapdát elutasítja | 72/84 = **85,7%** (95%: 76,7% – 91,6%) | 85,7% ± 0,0% (ismétlésenként: 85,7%, 85,7%, 85,7%) | ≥ 90% |
| … az elvárt indokkal | 69/84 = **82,1%** (95%: 72,6% – 88,9%) | | |
| ugyanaz a gépi alak minden ismétlésben | 128/130 kérdés | | |

| kérdéstípus | egység | F-1 | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| csapda | 84 | — | 69 |
| idosor | 39 | 38 | 35 |
| idoszak | 48 | 42 | 36 |
| kombinalt | 75 | 66 | 54 |
| nyelvi | 33 | 18 | 12 |
| osszesito | 18 | 18 | 18 |
| rangsor | 51 | 45 | 42 |
| szures | 42 | 28 | 27 |

| szerző | egység | F-1 (megválaszolandó) | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| claude | 240 | 171 | 206 |
| viola | 150 | 84 | 87 |

| csapda-fajta | egység | elutasítva | az elvárt indokkal |
|---|---|---|---|
| adaton_kivul | 6 | 6 | 6 |
| atveres | 6 | 6 | 6 |
| jovo | 9 | 9 | 9 |
| katalogus_kivul | 15 | 12 | 12 |
| ketertelmu | 3 | 0 | 0 |
| korlat | 3 | 0 | 0 |
| nem_adat | 3 | 3 | 3 |
| nincs_adat | 33 | 33 | 33 |
| tiltott | 3 | 3 | 0 |
| tobblepeses | 3 | 0 | 0 |

## K1 — alá nem támasztott állítás a modell szövegében

A 2. kapu által talált állítások: ez **alsó becslés** (amit a kapu nem lát, azt a kézi ellenőrzés becsli — `kezi_ellenorzes.csv`).

| | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| modellszöveg | 292 | 292 |
| **van benne alá nem támasztott állítás** | 57/292 = **19,5%** (95%: 15,4% – 24,5%) | 45/292 = **15,4%** (95%: 11,7% – 20,0%) |
| … ismétlésenként | 19,5% ± 0,1% (ismétlésenként: 19,4%, 19,6%, 19,6%) | 15,4% ± 0,1% (ismétlésenként: 15,3%, 15,5%, 15,5%) |
| … és el is jut a felhasználóhoz | 0/292 = **0,0%** (95%: 0,0% – 1,3%) | 45/292 = **15,4%** (95%: 11,7% – 20,0%) |
| a sablonos válasz látszik helyette | 57/292 = **19,5%** (95%: 15,4% – 24,5%) | — (a kontrollág nem vált) |
| leírt számok közül vissza nem vezethető | 9/30 | 9/890 |
| üres / értelmezhetetlen válasz | 0 | 0 |

Páros összevetés (98 kérdés, kérdésenként az ismétlések átlaga): a kontrollág és a fő ág különbsége **−4,1 százalékpont** (95%-os bootstrap-intervallum: −11,6 – 3,7).

| állítás fajtája | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| kitalált jelölő | 6 | 0 |
| vissza nem vezethető szám | 9 | 9 |
| rossz csoporthoz kötött érték | 58 | 15 |
| hamis felsőfok | 21 | 21 |
| a szűrés tagadása | 1 | 6 |

## Idő

| | medián |
|---|---|
| ① kérdés → gépi alak | 4,3 mp |
| … ebből betöltés | 0,0 mp |
| … ebből a prompt beolvasása | 0,5 mp |
| … ebből generálás | 1,7 mp |
| ② fő ág (jelölők) | 4,0 mp |
| ② kontrollág (szabad) | 4,2 mp |
| a mérés összesen | 1,2 óra |

## Ahol az értelmezés nem az elvárt

| # | kérdés | hányszor | ítélet és eltérés (első eset) |
|---|---|---|---|
| k011 | Mely termékkategóriák csomagjai utaznak a legtovább? | 3 | hibás értelmezés: metrika: atlagos_tavolsag (elvárt: atlagos_szallitasi_ido vagy median_szallitasi_ido); rendezes: ertek_novekvo (elvárt: ertek_csokkeno) |
| k012 | Melyik eladói államban késik a legtöbb rendelés darabszámra? | 3 | hibás értelmezés: metrika: kesesi_arany (elvárt: kesett_rendelesek) |
| k017 | Melyik eladói államokból utaznak a legmesszebbre a csomagok? | 3 | hibás értelmezés: rendezes: ertek_novekvo (elvárt: ertek_csokkeno) |
| k023 | Átlagosan mennyibe kerül a szállítás a déli régióban? | 3 | hibás értelmezés: szűrő: {'kategoria': ['toys'], 'vevo_regio': ['S']} (elvárt: {'vevo_regio': ['S']}); tól: 2018-07-01 (elvárt: az adat eleje) |
| k024 | Hány rendelést adtak le hétvégén? | 3 | hibás értelmezés: bontás: ['het_napja'] (elvárt: []) |
| k028 | Mekkora az átlagos kosárérték az órák és ajándékok kategóriájában? | 3 | hibás értelmezés: bontás: ['kategoria'] (elvárt: []); szűrő: {} (elvárt: {'kategoria': ['watches_gifts']}) |
| k033 | Mennyi volt a forgalom 2017 novemberében? | 3 | hibás értelmezés: bontás: ['honap'] (elvárt: []) |
| k043 | Hogyan alakult havonta a késett rendelések száma a délkeleti régióban? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']) |
| k054 | Mennyit csúsztak átlagosan a késett szállítások a közép-nyugati régióban tavaly? | 3 | téves elutasítás: tiltott_kombinacio: Az átlagos késés a késésből számolódik, ezért nem szűrhető aszerint, hogy a rendelés késett-e (az eredmény definíció szerint 0 vagy 100% lenne). |
| k064 | Szóval mennyi ideig tart nagyjából, amíg egy Pernambucóba küldött csomag megérkezik? | 3 | hibás értelmezés: tól: 2018-01-01 (elvárt: az adat eleje) |
| k077 | Mekkora az átlagos késés az időben kézbesített rendeléseknél? | 3 | más elutasítás: elvárt: tiltott_kombinacio, kapott: ismeretlen_metrika |
| k078 | Bontsd le a forgalmat egyszerre régiók és termékkategóriák szerint! | 3 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_regio"], "limit": 10, "metrika": "forgalom", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k082 | átlagos kosárérték mennyi volt az elmult 3 honapban? | 3 | hibás értelmezés: tól: 2018-07-01 (elvárt: 2018-06-01) |
| k085 | Melyik államban vannak a vevőink a legtöbben? | 3 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_allam"], "limit": 10, "metrika": "rendelesek_szama", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k087 | bútor kategóriában mennyi volt a szállítási díj átlagosan? | 3 | hibás értelmezés: bontás: ['kategoria'] (elvárt: []); szűrő: {'kategoria': ['furniture_decor', 'furniture_mattress_and_upholstery', 'kitchen_dining_laundry_garden_furniture']} (elvárt: {'kategoria': ['furniture_decor']}) |
| k090 | tavaly negyedik negyedévben mennyi volt a bevétel? | 3 | hibás értelmezés: tól: 2017-01-01 (elvárt: 2017-10-01) |
| k098 | mennyi a bevétel az elektronikai cuccokból hétvégente? | 3 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „bevetel” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k099 | tavalyi év Q3-ban melyik eladói állam küldte a legtöbb csomagot? | 3 | hibás értelmezés: tól: 2017-01-01 (elvárt: 2017-07-01); ig: 2017-12-31 (elvárt: 2017-09-30) |
| k101 | Átlagos késés napokban az idei első negyedévben Rio de Janeiro-ba? | 3 | hibás értelmezés: ig: az adat vége (elvárt: 2018-03-31) |
| k102 | mennyi az átlag kosárérték keddenként az északi régióban? | 3 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: []); szűrő: {'het_napja': ['2']} (elvárt: {'het_napja': ['2'], 'vevo_regio': ['N']}) |
| k104 | van olyan hónap 2018ban amikor több volt a késett rendelés mint 2017 azonos hónapjában? | 3 | hibás értelmezés: rendezes: ertek_csokkeno (elvárt: bontas) |
| k106 | mennyi a vállalt szállítási idő átlaga ha a vevő és eladó is déli régiós? | 3 | hibás értelmezés: szűrő: {'vevo_regio': ['S']} (elvárt: {'vevo_regio': ['S'], 'elado_allam': ['PR', 'RS', 'SC']}) |
| k109 | tavaly augusztusban mennyi volt az átl szállítási költség a sport termékeknél? | 3 | hibás értelmezés: tól: 2017-01-01 (elvárt: 2017-08-01); ig: 2017-12-31 (elvárt: 2017-08-31) |
| k111 | mennyi az átlagos távolság a vevő és eladó között a bútoroknál? | 3 | hibás értelmezés: bontás: ['kategoria'] (elvárt: []); szűrő: {'kategoria': ['furniture_bedroom', 'furniture_decor', 'furniture_living_room', 'furniture_mattress_and_upholstery', 'kitchen_dining_laundry_garden_furniture', 'office_furniture']} (elvárt: {'kategoria': ['furniture_decor']}) |
| k118 | mutasd a 2015-ös és 2016-os év teljes forgalmát egymás mellett | 3 | hibás értelmezés: bontás: [] (elvárt: ['ev']) |
| k121 | menniy vót a redneles összesen rioban a tavaj? | 3 | hibás értelmezés: tól: 2017-09-01 (elvárt: 2017-01-01); ig: az adat vége (elvárt: 2017-12-31) |
| k122 | melyik volt a legjobb kategoria amibol a legtöbb pézt csináltuk mostanában? | 3 | téves elutasítás: nem_elerheto: Ezt nem tudom kiszámolni: a metrikakatalógus a múltról szól; egy rendelés késési kockázatát a „Rendelés kockázata” oldal becsli, havi előrejelzést a rendszer nem ad. Ami közel áll hozzá: késési arány. |
| k124 | mult évbe hányan késtek a kiszálitással a butoroknál? | 3 | téves elutasítás: tiltott_kombinacio: A késett rendelések száma a késésből számolódik, ezért nem szűrhető aszerint, hogy a rendelés késett-e (az eredmény definíció szerint 0 vagy 100% lenne). |
| k125 | hogy alalkult a dolog azokba a honapokba amikor sok volt a csuszás? | 3 | hiányzó elutasítás: elfogadva: {"bontas": ["honap"], "limit": 10, "metrika": "atlagos_keses", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k126 | sp ba mibe kerult a fuvar atlagba 2018 elejen? | 3 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: atlagos_szallitasi_dij); bontás: ['vevo_allam'] (elvárt: []); szűrő: {} (elvárt: {'vevo_allam': ['SP']}) |
| k127 | mi a top 5 legroszabb dolog amiket a leglassabban visznek ki? | 3 | hibás értelmezés: bontás: [] (elvárt: ['kategoria']); rendezes: ertek_novekvo (elvárt: ertek_csokkeno) |
| k128 | honnan jött a legtob vásárlo amikor a legnagyob volt a forgalom? | 3 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_allam"], "limit": 10, "metrika": "forgalom", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k130 | rio meg sp kozott mi volt a difi eladasban 17 nyaran? | 3 | hibás értelmezés: metrika: atlagos_szallitasi_dij (elvárt: forgalom vagy rendelesek_szama); bontás: [] (elvárt: ['vevo_allam']); szűrő: {'vevo_allam': ['RJ']} (elvárt: {'vevo_allam': ['RJ', 'SP']}); tól: 2017-07-01 (elvárt: 2017-06-01); ig: 2017-09-30 (elvárt: 2017-08-31) |
