# K1 mérés — qwen3.5:2b

Kezdés: 2026-10-19T09:10:42 · ismétlés: 3 · értelmezés és mindkét ág

- modell: `qwen3.5:2b` (`0689d44085e06d16`)
- protokoll: `docs/k1_protokoll.json` · SHA256 `7663856c9d3fdf65755d58a8718964f5aee7ac24ad6d57193cd67159e9cd79a6`
- kérdéssor: `eval/meresi_kerdessor.toml` · SHA256 `ce87d85fd44038c96f107f6474b4c6cdf1a5978afb88b3bfa6629784a69bc01f` · 130 kérdés
- promptok: to_spec = `prompts/to_spec.v3.md` (`9266f3285311`), to_text = `prompts/to_text.v3.md` (`401ad3d593d2`), to_text_szabad = `prompts/to_text_szabad.v3.md` (`4070fbfeeb31`)
- kód: commit `f5db16915e45a111ac7b1c4adb6665c505b8352d` · ujjlenyomat `db97e252c9902346`
- mért egységek (kérdés × ismétlés): 390

## Értelmezés (F-1) és elutasítás (F-2)

| mutató | eredmény | ismétlésenként | cél |
|---|---|---|---|
| F-1 — helyes mérőszám és bontás | 136/306 = **44,4%** (95%: 39,0% – 50,0%) | 44,4% ± 0,6% (ismétlésenként: 45,1%, 44,1%, 44,1%) | ≥ 85% |
| teljes egyezés (szűrő, időablak, rendezés is) | 76/306 = **24,8%** (95%: 20,3% – 30,0%) | | |
| F-2 — a csapdát elutasítja | 72/84 = **85,7%** (95%: 76,7% – 91,6%) | 85,7% ± 0,0% (ismétlésenként: 85,7%, 85,7%, 85,7%) | ≥ 90% |
| … az elvárt indokkal | 66/84 = **78,6%** (95%: 68,7% – 86,0%) | | |
| ugyanaz a gépi alak minden ismétlésben | 128/130 kérdés | | |

| kérdéstípus | egység | F-1 | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| csapda | 84 | — | 66 |
| idosor | 39 | 15 | 3 |
| idoszak | 48 | 36 | 24 |
| kombinalt | 75 | 30 | 3 |
| nyelvi | 33 | 3 | 3 |
| osszesito | 18 | 15 | 15 |
| rangsor | 51 | 15 | 15 |
| szures | 42 | 22 | 13 |

| szerző | egység | F-1 (megválaszolandó) | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| claude | 240 | 97 | 103 |
| viola | 150 | 39 | 39 |

| csapda-fajta | egység | elutasítva | az elvárt indokkal |
|---|---|---|---|
| adaton_kivul | 6 | 6 | 6 |
| atveres | 6 | 6 | 6 |
| jovo | 9 | 9 | 9 |
| katalogus_kivul | 15 | 12 | 12 |
| ketertelmu | 3 | 3 | 3 |
| korlat | 3 | 0 | 0 |
| nem_adat | 3 | 3 | 3 |
| nincs_adat | 33 | 30 | 27 |
| tiltott | 3 | 3 | 0 |
| tobblepeses | 3 | 0 | 0 |

## K1 — alá nem támasztott állítás a modell szövegében

A 2. kapu által talált állítások: ez **alsó becslés** (amit a kapu nem lát, azt a kézi ellenőrzés becsli — `kezi_ellenorzes.csv`).

| | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| modellszöveg | 239 | 239 |
| **van benne alá nem támasztott állítás** | 95/239 = **39,7%** (95%: 33,8% – 46,1%) | 109/239 = **45,6%** (95%: 39,4% – 51,9%) |
| … ismétlésenként | 39,7% ± 0,9% (ismétlésenként: 40,7%, 39,2%, 39,2%) | 45,6% ± 0,1% (ismétlésenként: 45,7%, 45,6%, 45,6%) |
| … és el is jut a felhasználóhoz | 0/239 = **0,0%** (95%: 0,0% – 1,6%) | 109/239 = **45,6%** (95%: 39,4% – 51,9%) |
| a sablonos válasz látszik helyette | 95/239 = **39,7%** (95%: 33,8% – 46,1%) | — (a kontrollág nem vált) |
| leírt számok közül vissza nem vezethető | 22/225 | 68/459 |
| üres / értelmezhetetlen válasz | 0 | 0 |

Páros összevetés (81 kérdés, kérdésenként az ismétlések átlaga): a kontrollág és a fő ág különbsége **5,8 százalékpont** (95%-os bootstrap-intervallum: −6,6 – 18,5).

| állítás fajtája | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| kitalált jelölő | 59 | 0 |
| vissza nem vezethető szám | 22 | 68 |
| rossz csoporthoz kötött érték | 29 | 12 |
| hamis felsőfok | 16 | 24 |
| a tartomány hamis szerepe | 3 | 6 |
| a szűrés tagadása | 20 | 48 |

## Idő

| | medián |
|---|---|
| ① kérdés → gépi alak | 13,6 mp |
| … ebből betöltés | 0,0 mp |
| … ebből a prompt beolvasása | 8,1 mp |
| … ebből generálás | 5,4 mp |
| ② fő ág (jelölők) | 6,7 mp |
| ② kontrollág (szabad) | 7,5 mp |
| a mérés összesen | 3,1 óra |

## Ahol az értelmezés nem az elvárt

| # | kérdés | hányszor | ítélet és eltérés (első eset) |
|---|---|---|---|
| k006 | Mi a szállítási idő mediánja? | 3 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: median_szallitasi_ido) |
| k007 | Melyik termékkategóriából rendelnek a legtöbbet? | 3 | hibás értelmezés: bontás: [] (elvárt: ['kategoria']) |
| k008 | Melyik három állam vevői hozzák a legnagyobb forgalmat? | 3 | téves elutasítás: ertelmezhetetlen: A nyelvi modell válaszából nem lett érvényes kérdés-specifikáció, ezért nem mondok számot. Fogalmazd meg másképp, vagy állítsd össze a kérdést a kérdésépítővel. |
| k009 | Mely régiókban a legalacsonyabb a késési arány? | 3 | hibás értelmezés: bontás: [] (elvárt: ['vevo_regio']); rendezes: ertek_csokkeno (elvárt: ertek_novekvo) |
| k011 | Mely termékkategóriák csomagjai utaznak a legtovább? | 3 | téves elutasítás: ertelmezhetetlen: A nyelvi modell válaszából nem lett érvényes kérdés-specifikáció, ezért nem mondok számot. Fogalmazd meg másképp, vagy állítsd össze a kérdést a kérdésépítővel. |
| k012 | Melyik eladói államban késik a legtöbb rendelés darabszámra? | 3 | hibás értelmezés: metrika: kesesi_arany (elvárt: kesett_rendelesek) |
| k013 | Melyik napon költenek a vásárlók rendelésenként a legtöbbet? | 3 | téves elutasítás: nem_elerheto: Ezt nem tudom kiszámolni: az adathalmaz nem tartalmaz beszerzési árat, ezért haszon vagy árrés nem számolható. Ami közel áll hozzá: átlagos kosárérték és átlagos szállítási díj. |
| k014 | A vevők államai közül hol a legnagyobb az átlagos késés? | 3 | hibás értelmezés: metrika: kesesi_arany (elvárt: atlagos_keses) |
| k015 | Melyik öt állam vevői várnak a legkevesebbet a csomagjukra? | 3 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „csomag várás ideje” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k017 | Melyik eladói államokból utaznak a legmesszebbre a csomagok? | 3 | téves elutasítás: nem_elerheto: Ezt nem tudom kiszámolni: az adathalmaz nem tartalmaz beszerzési árat, ezért haszon vagy árrés nem számolható. Ami közel áll hozzá: átlagos kosárérték és átlagos szállítási díj. |
| k019 | Melyik kategóriának a legkisebb a forgalma? | 3 | hibás értelmezés: metrika: atlagos_kosarertek (elvárt: forgalom); bontás: [] (elvárt: ['kategoria']); rendezes: ertek_csokkeno (elvárt: ertek_novekvo) |
| k022 | Mennyi a szállítási idő mediánja a sport és szabadidő kategóriában? | 3 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: median_szallitasi_ido); szűrő: {} (elvárt: {'kategoria': ['sports_leisure']}) |
| k024 | Hány rendelést adtak le hétvégén? | 3 | hibás értelmezés: bontás: ['het_napja'] (elvárt: []); szűrő: {} (elvárt: {'het_napja': ['6', '7']}) |
| k025 | Mennyi a szállítási idő mediánja Minas Geraisban? | 3 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: median_szallitasi_ido) |
| k026 | Milyen messze vannak átlagosan a São Pauló-i eladók a vevőiktől? | 3 | hibás értelmezés: szűrő: {'vevo_allam': ['SP']} (elvárt: {'elado_allam': ['SP']}) |
| k027 | Hány késett rendelés volt a parfümöknél? | 3 | hibás értelmezés: szűrő: {} (elvárt: {'kategoria': ['perfumery']}) |
| k028 | Mekkora az átlagos kosárérték az órák és ajándékok kategóriájában? | 2 | téves elutasítás: ertelmezhetetlen: A nyelvi modell válaszából nem lett érvényes kérdés-specifikáció, ezért nem mondok számot. Fogalmazd meg másképp, vagy állítsd össze a kérdést a kérdésépítővel. |
| k030 | Mennyi a késési arány a São Paulóban és Rio de Janeiróban élő vevőknél? | 3 | hibás értelmezés: bontás: ['vevo_allam'] (elvárt: []) |
| k037 | Mennyi szállítási díjat számoltak fel átlagosan 2017 utolsó negyedévében? | 3 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „szallitasi_dij” nincs a metrikakatalógusban. Ami közel áll hozzá: átlagos szállítási díj, szállítási idő mediánja és átlagos szállítási idő. |
| k038 | Hány rendelés késett 2017 októbere és 2018 márciusa között? | 3 | hibás értelmezés: metrika: rendelesek_szama (elvárt: kesett_rendelesek) |
| k039 | Hónapról hónapra hogyan változott az átlagos szállítási díj? | 3 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „átlagos szállítási díj” nincs a metrikakatalógusban. Ami közel áll hozzá: átlagos szállítási díj, átlagos szállítási idő és átlagos vállalt szállítási idő. |
| k040 | Mutasd évenkénti bontásban, hány rendelés érkezett! | 3 | hibás értelmezés: rendezes: ertek_csokkeno (elvárt: bontas) |
| k041 | Havi bontásban hogyan változott az átlagos szállítási idő 2018 első felében? | 3 | hibás értelmezés: rendezes: ertek_csokkeno (elvárt: bontas) |
| k042 | Évről évre nőtt vagy csökkent az átlagos kosárérték? | 3 | hibás értelmezés: bontás: [] (elvárt: ['ev']); rendezes: ertek_csokkeno (elvárt: bontas) |
| k043 | Hogyan alakult havonta a késett rendelések száma a délkeleti régióban? | 3 | téves elutasítás: tiltott_kombinacio: A késett rendelések száma a késésből számolódik, ezért nem szűrhető aszerint, hogy a rendelés késett-e (az eredmény definíció szerint 0 vagy 100% lenne). |
| k044 | Mutasd havonta, mennyit késtek átlagosan a késve érkezett rendelések 2017 júliusától 2018 júniusáig! | 3 | hibás értelmezés: metrika: kesesi_arany (elvárt: atlagos_keses) |
| k046 | Hogyan változott a vállalt szállítási idő havonta az elmúlt egy évben? | 3 | hibás értelmezés: rendezes: ertek_csokkeno (elvárt: bontas) |
| k047 | Melyik kategóriában volt a legnagyobb a forgalom 2018-ban a déli régióban? | 3 | hibás értelmezés: bontás: [] (elvárt: ['kategoria']) |
| k048 | Rio Grande do Sulban melyik három kategóriában a legmagasabb a késési arány? | 3 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: ['kategoria']); szűrő: {} (elvárt: {'vevo_allam': ['RS']}) |
| k049 | A São Pauló-i eladóktól melyik vevői államba a leglassabb a szállítás? | 3 | hibás értelmezés: bontás: [] (elvárt: ['vevo_allam']); szűrő: {'vevo_allam': ['SP']} (elvárt: {'elado_allam': ['SP']}); rendezes: ertek_novekvo (elvárt: ertek_csokkeno) |
| k050 | Hétvégi rendeléseknél melyik régióban a legnagyobb az átlagos kosárérték? | 3 | hibás értelmezés: szűrő: {} (elvárt: {'het_napja': ['6', '7']}) |
| k051 | Mennyi volt a játékok forgalma havonta 2017-ben? | 3 | hibás értelmezés: bontás: [] (elvárt: ['honap']); szűrő: {} (elvárt: {'kategoria': ['toys']}); rendezes: ertek_csokkeno (elvárt: bontas) |
| k052 | A babatermékeknél hogyan oszlik meg a rendelések száma a régiók között? | 3 | hibás értelmezés: szűrő: {} (elvárt: {'kategoria': ['baby']}) |
| k054 | Mennyit csúsztak átlagosan a késett szállítások a közép-nyugati régióban tavaly? | 3 | téves elutasítás: tiltott_kombinacio: A késési arány a késésből számolódik, ezért nem szűrhető aszerint, hogy a rendelés késett-e (az eredmény definíció szerint 0 vagy 100% lenne). |
| k055 | Melyik eladói állam forgalma volt a legnagyobb 2018 márciusában? | 3 | hibás értelmezés: bontás: [] (elvárt: ['elado_allam']) |
| k056 | Hány késett rendelés volt a lakástextil kategóriában 2018 első negyedévében, államonként? | 3 | hibás értelmezés: szűrő: {} (elvárt: {'kategoria': ['bed_bath_table']}) |
| k057 | Átlagosan hány nap volt a vállalt határidő a Paranába menő rendeléseknél 2017-ben? | 3 | hibás értelmezés: szűrő: {'kategoria': ['industry_commerce_and_business']} (elvárt: {'vevo_allam': ['PR']}) |
| k058 | Az elmúlt négy hónapban a hét melyik napjain volt a legmagasabb a késési arány? | 3 | hibás értelmezés: bontás: [] (elvárt: ['het_napja']) |
| k059 | Hogyan alakult évente az átlagos szállítási díj az elektronikai termékeknél? | 3 | hibás értelmezés: szűrő: {} (elvárt: {'kategoria': ['electronics']}); rendezes: ertek_csokkeno (elvárt: bontas) |
| k060 | Mennyi volt a vállalt szállítási idő átlaga a hétvégén leadott rendeléseknél 2018-ban? | 3 | hibás értelmezés: szűrő: {} (elvárt: {'het_napja': ['6', '7']}) |
| k061 | kesesi arany regionkent 2018 | 3 | téves elutasítás: ertelmezhetetlen: A nyelvi modell válaszából nem lett érvényes kérdés-specifikáció, ezért nem mondok számot. Fogalmazd meg másképp, vagy állítsd össze a kérdést a kérdésépítővel. |
| k063 | mennyi pénz jött be a kerti eszközökből tavaly | 3 | téves elutasítás: nem_elerheto: Ezt nem tudom kiszámolni: az adathalmaz nem tartalmaz beszerzési árat, ezért haszon vagy árrés nem számolható. Ami közel áll hozzá: átlagos kosárérték és átlagos szállítási díj. |
| k064 | Szóval mennyi ideig tart nagyjából, amíg egy Pernambucóba küldött csomag megérkezik? | 3 | téves elutasítás: ertelmezhetetlen: A nyelvi modell válaszából nem lett érvényes kérdés-specifikáció, ezért nem mondok számot. Fogalmazd meg másképp, vagy állítsd össze a kérdést a kérdésépítővel. |
| k067 | Hány rendelést fizettek bankkártyával? | 3 | hiányzó elutasítás: elfogadva: {"bontas": [], "limit": 10, "metrika": "rendelesek_szama", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k077 | Mekkora az átlagos késés az időben kézbesített rendeléseknél? | 3 | más elutasítás: elvárt: tiltott_kombinacio, kapott: ertelmezhetetlen |
| k078 | Bontsd le a forgalmat egyszerre régiók és termékkategóriák szerint! | 3 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_regio"], "limit": 10, "metrika": "forgalom", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k081 | Hány rendelésünk volt összesen 2018 első félévében? | 3 | hibás értelmezés: ig: 2018-03-31 (elvárt: 2018-06-30) |
| k082 | átlagos kosárérték mennyi volt az elmult 3 honapban? | 3 | hibás értelmezés: tól: az adat eleje (elvárt: 2018-06-01) |
| k083 | Melyik 5 termékkategória pörgette a legnagyobb forgalmat? | 3 | téves elutasítás: ertelmezhetetlen: A nyelvi modell válaszából nem lett érvényes kérdés-specifikáció, ezért nem mondok számot. Fogalmazd meg másképp, vagy állítsd össze a kérdést a kérdésépítővel. |
| k085 | Melyik államban vannak a vevőink a legtöbben? | 3 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_allam"], "limit": 10, "metrika": "rendelesek_szama", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k087 | bútor kategóriában mennyi volt a szállítási díj átlagosan? | 3 | hibás értelmezés: szűrő: {} (elvárt: {'kategoria': ['furniture_decor']}) |
| k088 | Hétfői napokon több a rendelés mint pénteken? | 3 | hibás értelmezés: bontás: [] (elvárt: ['het_napja']); szűrő: {'het_napja': ['1', '5']} (elvárt: {}) |
| k089 | északkeleti régióba mennyi idő alatt érnek ki a csomagok átlagosan? | 3 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: []); szűrő: {} (elvárt: {'vevo_regio': ['NE']}) |
| k090 | tavaly negyedik negyedévben mennyi volt a bevétel? | 3 | hibás értelmezés: tól: 2017-01-01 (elvárt: 2017-10-01) |
| k092 | az elmúlt fél évben mennyi volt a medián szállítási idő? | 3 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: median_szallitasi_ido); tól: az adat eleje (elvárt: 2018-03-01) |
| k093 | Hogy alakult a rendelések száma havonta 2017-ben? | 3 | hibás értelmezés: rendezes: ertek_csokkeno (elvárt: bontas) |
| k094 | mutasd az átlagos kosárértéket éves bontásban | 3 | hibás értelmezés: bontás: [] (elvárt: ['ev']); rendezes: ertek_csokkeno (elvárt: bontas) |
| k095 | szállítási díjak alakulása havonta az idén? | 3 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „szallitasi_dij” nincs a metrikakatalógusban. Ami közel áll hozzá: átlagos szállítási díj, szállítási idő mediánja és átlagos szállítási idő. |
| k096 | Melyik az az 5 termékkategória, ahol a legmagasabb a késési arány Sao Paulo államba 2018-ban? | 3 | hibás értelmezés: bontás: ['vevo_allam'] (elvárt: ['kategoria']); szűrő: {'kategoria': ['industry_commerce_and_business']} (elvárt: {'vevo_allam': ['SP']}) |
| k097 | Átlagos eladó-vevő táv és szállítási díj az elmúlt 6 hónapban, régiós bontásban? | 3 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: atlagos_tavolsag vagy atlagos_szallitasi_dij) |
| k098 | mennyi a bevétel az elektronikai cuccokból hétvégente? | 3 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „bevétel” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k099 | tavalyi év Q3-ban melyik eladói állam küldte a legtöbb csomagot? | 3 | hibás értelmezés: tól: 2017-01-01 (elvárt: 2017-07-01); ig: 2017-12-31 (elvárt: 2017-09-30) |
| k100 | 2018-as évi forgalom havi bontásban, de csak a szépségápolás kategóriára | 3 | hibás értelmezés: szűrő: {} (elvárt: {'kategoria': ['health_beauty']}); rendezes: ertek_csokkeno (elvárt: bontas) |
| k101 | Átlagos késés napokban az idei első negyedévben Rio de Janeiro-ba? | 3 | hibás értelmezés: metrika: kesesi_arany (elvárt: atlagos_keses); szűrő: {} (elvárt: {'vevo_allam': ['RJ']}); ig: az adat vége (elvárt: 2018-03-31) |
| k102 | mennyi az átlag kosárérték keddenként az északi régióban? | 3 | téves elutasítás: nem_elerheto: Ezt nem tudom kiszámolni: a metrikakatalógus a múltról szól; egy rendelés késési kockázatát a „Rendelés kockázata” oldal becsli, havi előrejelzést a rendszer nem ad. Ami közel áll hozzá: késési arány. |
| k103 | 2017 második félév 10 legkisebb forgalmú állama | 3 | hibás értelmezés: bontás: [] (elvárt: ['vevo_allam']); tól: 2017-06-30 (elvárt: 2017-07-01); ig: 2017-09-30 (elvárt: 2017-12-31) |
| k104 | van olyan hónap 2018ban amikor több volt a késett rendelés mint 2017 azonos hónapjában? | 3 | hibás értelmezés: metrika: kesesi_arany (elvárt: kesett_rendelesek); rendezes: ertek_csokkeno (elvárt: bontas) |
| k106 | mennyi a vállalt szállítási idő átlaga ha a vevő és eladó is déli régiós? | 3 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: atlagos_vallalt_ido); bontás: ['vevo_regio'] (elvárt: []); szűrő: {} (elvárt: {'vevo_regio': ['S'], 'elado_allam': ['PR', 'RS', 'SC']}) |
| k107 | Melyik hónap hozta a legnagyobb forgalmat összesen eddig? | 3 | hibás értelmezés: bontás: [] (elvárt: ['honap']) |
| k108 | mutasd a 3 legrosszabb államot a késések száma alapján az elmult negyedévben | 3 | hibás értelmezés: metrika: kesesi_arany (elvárt: kesett_rendelesek); tól: az adat eleje (elvárt: 2018-04-01); ig: az adat vége (elvárt: 2018-06-30) |
| k109 | tavaly augusztusban mennyi volt az átl szállítási költség a sport termékeknél? | 3 | hibás értelmezés: szűrő: {'kategoria': ['fashion_sport']} (elvárt: {'kategoria': ['sports_leisure']}); tól: 2017-01-01 (elvárt: 2017-08-01); ig: 2017-12-31 (elvárt: 2017-08-31) |
| k110 | augusztusban mennyi volt a késési arány összesen? | 3 | hibás értelmezés: tól: 2018-08-29 (elvárt: 2018-08-01) |
| k111 | mennyi az átlagos távolság a vevő és eladó között a bútoroknál? | 3 | téves elutasítás: ertelmezhetetlen: A nyelvi modell válaszából nem lett érvényes kérdés-specifikáció, ezért nem mondok számot. Fogalmazd meg másképp, vagy állítsd össze a kérdést a kérdésépítővel. |
| k116 | Hány darab okostelefon van jelenleg raktáron a sao paulo-i központban? | 3 | más elutasítás: elvárt: nem_elerheto, kapott: ismeretlen_metrika |
| k118 | mutasd a 2015-ös és 2016-os év teljes forgalmát egymás mellett | 3 | hibás értelmezés: bontás: [] (elvárt: ['ev']) |
| k121 | menniy vót a redneles összesen rioban a tavaj? | 3 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: []); szűrő: {} (elvárt: {'vevo_allam': ['RJ']}); tól: 2017-09-01 (elvárt: 2017-01-01); ig: az adat vége (elvárt: 2017-12-31) |
| k122 | melyik volt a legjobb kategoria amibol a legtöbb pézt csináltuk mostanában? | 3 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „legjobb kategoria” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k123 | atlagosan meniy idö alat ér oda a cucc az északiknak? | 3 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: []); szűrő: {} (elvárt: {'vevo_regio': ['N']}) |
| k124 | mult évbe hányan késtek a kiszálitással a butoroknál? | 3 | téves elutasítás: ertelmezhetetlen: A nyelvi modell válaszából nem lett érvényes kérdés-specifikáció, ezért nem mondok számot. Fogalmazd meg másképp, vagy állítsd össze a kérdést a kérdésépítővel. |
| k126 | sp ba mibe kerult a fuvar atlagba 2018 elejen? | 3 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: atlagos_szallitasi_dij); bontás: ['vevo_allam'] (elvárt: []); szűrő: {} (elvárt: {'vevo_allam': ['SP']}); ig: az adat vége (elvárt: 2018-03-31) |
| k127 | mi a top 5 legroszabb dolog amiket a leglassabban visznek ki? | 3 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „top 5 legrosszabb dolog” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k128 | honnan jött a legtob vásárlo amikor a legnagyob volt a forgalom? | 3 | hiányzó elutasítás: elfogadva: {"bontas": [], "limit": 10, "metrika": "forgalom", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k130 | rio meg sp kozott mi volt a difi eladasban 17 nyaran? | 3 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „difi eladas” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
