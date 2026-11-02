# K1 mérés — qwen3.5:4b

Kezdés: 2026-11-01T19:37:04 · ismétlés: 3 · értelmezés és mindkét ág

- modell: `qwen3.5:4b` (`d8b0f5e9760cd168`)
- protokoll: `docs/k1_protokoll.json` · SHA256 `7663856c9d3fdf65755d58a8718964f5aee7ac24ad6d57193cd67159e9cd79a6`
- kérdéssor: `eval/meresi_kerdessor.toml` · SHA256 `ce87d85fd44038c96f107f6474b4c6cdf1a5978afb88b3bfa6629784a69bc01f` · 130 kérdés
- promptok: to_spec = `prompts/to_spec.v3.md` (`9266f3285311`), to_text = `prompts/to_text.v3.md` (`401ad3d593d2`), to_text_szabad = `prompts/to_text_szabad.v3.md` (`4070fbfeeb31`)
- kód: commit `f5db16915e45a111ac7b1c4adb6665c505b8352d` · ujjlenyomat `db97e252c9902346`
- mért egységek (kérdés × ismétlés): 390

## Értelmezés (F-1) és elutasítás (F-2)

| mutató | eredmény | ismétlésenként | cél |
|---|---|---|---|
| F-1 — helyes mérőszám és bontás | 253/306 = **82,7%** (95%: 78,0% – 86,5%) | 82,7% ± 0,6% (ismétlésenként: 83,3%, 82,4%, 82,4%) | ≥ 85% |
| teljes egyezés (szűrő, időablak, rendezés is) | 186/306 = **60,8%** (95%: 55,2% – 66,1%) | | |
| F-2 — a csapdát elutasítja | 75/84 = **89,3%** (95%: 80,9% – 94,3%) | 89,3% ± 0,0% (ismétlésenként: 89,3%, 89,3%, 89,3%) | ≥ 90% |
| … az elvárt indokkal | 75/84 = **89,3%** (95%: 80,9% – 94,3%) | | |
| ugyanaz a gépi alak minden ismétlésben | 126/130 kérdés | | |

| kérdéstípus | egység | F-1 | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| csapda | 84 | — | 75 |
| idosor | 39 | 33 | 12 |
| idoszak | 48 | 42 | 30 |
| kombinalt | 75 | 60 | 42 |
| nyelvi | 33 | 24 | 12 |
| osszesito | 18 | 18 | 18 |
| rangsor | 51 | 39 | 39 |
| szures | 42 | 37 | 33 |

| szerző | egység | F-1 (megválaszolandó) | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| claude | 240 | 166 | 186 |
| viola | 150 | 87 | 75 |

| csapda-fajta | egység | elutasítva | az elvárt indokkal |
|---|---|---|---|
| adaton_kivul | 6 | 6 | 6 |
| atveres | 6 | 6 | 6 |
| jovo | 9 | 9 | 9 |
| katalogus_kivul | 15 | 12 | 12 |
| ketertelmu | 3 | 3 | 3 |
| korlat | 3 | 0 | 0 |
| nem_adat | 3 | 3 | 3 |
| nincs_adat | 33 | 33 | 33 |
| tiltott | 3 | 3 | 3 |
| tobblepeses | 3 | 0 | 0 |

## K1 — alá nem támasztott állítás a modell szövegében

A 2. kapu által talált állítások: ez **alsó becslés** (amit a kapu nem lát, azt a kézi ellenőrzés becsli — `kezi_ellenorzes.csv`).

| | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| modellszöveg | 285 | 285 |
| **van benne alá nem támasztott állítás** | 83/285 = **29,1%** (95%: 24,2% – 34,6%) | 100/285 = **35,1%** (95%: 29,8% – 40,8%) |
| … ismétlésenként | 29,1% ± 1,2% (ismétlésenként: 30,5%, 28,4%, 28,4%) | 35,1% ± 0,6% (ismétlésenként: 35,8%, 34,7%, 34,7%) |
| … és el is jut a felhasználóhoz | 0/285 = **0,0%** (95%: 0,0% – 1,3%) | 100/285 = **35,1%** (95%: 29,8% – 40,8%) |
| a sablonos válasz látszik helyette | 83/285 = **29,1%** (95%: 24,2% – 34,6%) | — (a kontrollág nem vált) |
| leírt számok közül vissza nem vezethető | 12/158 | 36/795 |
| üres / értelmezhetetlen válasz | 0 | 0 |

Páros összevetés (95 kérdés, kérdésenként az ismétlések átlaga): a kontrollág és a fő ág különbsége **6,0 százalékpont** (95%-os bootstrap-intervallum: −5,3 – 17,9).

| állítás fajtája | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| kitalált jelölő | 30 | 0 |
| vissza nem vezethető szám | 12 | 36 |
| rossz csoporthoz kötött érték | 48 | 43 |
| hamis felsőfok | 20 | 17 |
| a szűrés tagadása | 19 | 28 |
| oksági állítás | 3 | 0 |

## Idő

| | medián |
|---|---|
| ① kérdés → gépi alak | 3,6 mp |
| … ebből betöltés | 0,0 mp |
| … ebből a prompt beolvasása | 0,4 mp |
| … ebből generálás | 1,1 mp |
| ② fő ág (jelölők) | 3,4 mp |
| ② kontrollág (szabad) | 3,5 mp |
| a mérés összesen | 1,0 óra |

## Ahol az értelmezés nem az elvárt

| # | kérdés | hányszor | ítélet és eltérés (első eset) |
|---|---|---|---|
| k007 | Melyik termékkategóriából rendelnek a legtöbbet? | 3 | hibás értelmezés: metrika: forgalom (elvárt: rendelesek_szama) |
| k011 | Mely termékkategóriák csomagjai utaznak a legtovább? | 3 | hibás értelmezés: metrika: atlagos_tavolsag (elvárt: atlagos_szallitasi_ido vagy median_szallitasi_ido) |
| k012 | Melyik eladói államban késik a legtöbb rendelés darabszámra? | 3 | hibás értelmezés: metrika: rendelesek_szama (elvárt: kesett_rendelesek) |
| k020 | Melyik vevői régióba a legrövidebb az átlagos szállítási távolság? | 3 | hibás értelmezés: metrika: atlagos_szallitasi_ido (elvárt: atlagos_tavolsag) |
| k023 | Átlagosan mennyibe kerül a szállítás a déli régióban? | 2 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: []); szűrő: {} (elvárt: {'vevo_regio': ['S']}) |
| k024 | Hány rendelést adtak le hétvégén? | 1 | hibás értelmezés: szűrő: {'het_napja': ['6', '7'], 'kesett': ['kesett']} (elvárt: {'het_napja': ['6', '7']}) |
| k038 | Hány rendelés késett 2017 októbere és 2018 márciusa között? | 3 | téves elutasítás: tiltott_kombinacio: A késett rendelések száma a késésből számolódik, ezért nem szűrhető aszerint, hogy a rendelés késett-e (az eredmény definíció szerint 0 vagy 100% lenne). |
| k039 | Hónapról hónapra hogyan változott az átlagos szállítási díj? | 3 | hibás értelmezés: tól: 2017-09-01 (elvárt: az adat eleje) |
| k040 | Mutasd évenkénti bontásban, hány rendelés érkezett! | 3 | hibás értelmezés: rendezes: ertek_csokkeno (elvárt: bontas) |
| k042 | Évről évre nőtt vagy csökkent az átlagos kosárérték? | 3 | hibás értelmezés: rendezes: ertek_novekvo (elvárt: bontas) |
| k043 | Hogyan alakult havonta a késett rendelések száma a délkeleti régióban? | 3 | hibás értelmezés: bontás: [] (elvárt: ['honap']) |
| k044 | Mutasd havonta, mennyit késtek átlagosan a késve érkezett rendelések 2017 júliusától 2018 júniusáig! | 3 | téves elutasítás: tiltott_kombinacio: Az átlagos késés a késésből számolódik, ezért nem szűrhető aszerint, hogy a rendelés késett-e (az eredmény definíció szerint 0 vagy 100% lenne). |
| k045 | Melyik hónapban volt a legtöbb rendelés? | 3 | hibás értelmezés: tól: 2017-09-01 (elvárt: az adat eleje) |
| k048 | Rio Grande do Sulban melyik három kategóriában a legmagasabb a késési arány? | 3 | téves elutasítás: tiltott_kombinacio: A késési arány a késésből számolódik, ezért nem szűrhető aszerint, hogy a rendelés késett-e (az eredmény definíció szerint 0 vagy 100% lenne). |
| k049 | A São Pauló-i eladóktól melyik vevői államba a leglassabb a szállítás? | 3 | hibás értelmezés: szűrő: {'elado_allam': ['SP'], 'kesett': ['idoben']} (elvárt: {'elado_allam': ['SP']}) |
| k050 | Hétvégi rendeléseknél melyik régióban a legnagyobb az átlagos kosárérték? | 3 | hibás értelmezés: szűrő: {'kesett': ['idoben']} (elvárt: {'het_napja': ['6', '7']}) |
| k059 | Hogyan alakult évente az átlagos szállítási díj az elektronikai termékeknél? | 3 | hibás értelmezés: rendezes: ertek_csokkeno (elvárt: bontas) |
| k064 | Szóval mennyi ideig tart nagyjából, amíg egy Pernambucóba küldött csomag megérkezik? | 3 | hibás értelmezés: tól: 2018-01-01 (elvárt: az adat eleje) |
| k078 | Bontsd le a forgalmat egyszerre régiók és termékkategóriák szerint! | 3 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_regio"], "limit": 10, "metrika": "forgalom", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k082 | átlagos kosárérték mennyi volt az elmult 3 honapban? | 3 | hibás értelmezés: tól: 2018-06-03 (elvárt: 2018-06-01) |
| k085 | Melyik államban vannak a vevőink a legtöbben? | 3 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_allam"], "limit": 10, "metrika": "rendelesek_szama", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k087 | bútor kategóriában mennyi volt a szállítási díj átlagosan? | 3 | téves elutasítás: ismeretlen_ertek: „konyhai, etkezohez, mosokonyhaba es kertbe valo butorok” nem szerepel az adatban (a fő termék kategóriája). Talán: konyhai, étkezőhöz, mosókonyhába és kertbe való bútorok. |
| k090 | tavaly negyedik negyedévben mennyi volt a bevétel? | 3 | hibás értelmezés: tól: 2017-01-01 (elvárt: 2017-10-01) |
| k091 | 2017 márciusában hány csomag késett? | 3 | hibás értelmezés: szűrő: {'kategoria': ['toys']} (elvárt: {}) |
| k094 | mutasd az átlagos kosárértéket éves bontásban | 3 | hibás értelmezés: rendezes: ertek_csokkeno (elvárt: bontas) |
| k095 | szállítási díjak alakulása havonta az idén? | 3 | hibás értelmezés: rendezes: ertek_csokkeno (elvárt: bontas) |
| k096 | Melyik az az 5 termékkategória, ahol a legmagasabb a késési arány Sao Paulo államba 2018-ban? | 3 | téves elutasítás: tiltott_kombinacio: A késési arány a késésből számolódik, ezért nem szűrhető aszerint, hogy a rendelés késett-e (az eredmény definíció szerint 0 vagy 100% lenne). |
| k099 | tavalyi év Q3-ban melyik eladói állam küldte a legtöbb csomagot? | 3 | hibás értelmezés: tól: 2017-01-01 (elvárt: 2017-07-01); ig: 2017-12-31 (elvárt: 2017-09-30) |
| k101 | Átlagos késés napokban az idei első negyedévben Rio de Janeiro-ba? | 3 | téves elutasítás: tiltott_kombinacio: Az átlagos késés a késésből számolódik, ezért nem szűrhető aszerint, hogy a rendelés késett-e (az eredmény definíció szerint 0 vagy 100% lenne). |
| k102 | mennyi az átlag kosárérték keddenként az északi régióban? | 3 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: []); szűrő: {'het_napja': ['2']} (elvárt: {'het_napja': ['2'], 'vevo_regio': ['N']}) |
| k104 | van olyan hónap 2018ban amikor több volt a késett rendelés mint 2017 azonos hónapjában? | 3 | hibás értelmezés: rendezes: ertek_csokkeno (elvárt: bontas) |
| k106 | mennyi a vállalt szállítási idő átlaga ha a vevő és eladó is déli régiós? | 3 | hibás értelmezés: szűrő: {'vevo_regio': ['S']} (elvárt: {'vevo_regio': ['S'], 'elado_allam': ['PR', 'RS', 'SC']}) |
| k108 | mutasd a 3 legrosszabb államot a késések száma alapján az elmult negyedévben | 3 | hibás értelmezés: tól: 2018-07-01 (elvárt: 2018-04-01); ig: 2018-07-31 (elvárt: 2018-06-30) |
| k109 | tavaly augusztusban mennyi volt az átl szállítási költség a sport termékeknél? | 3 | téves elutasítás: ismeretlen_ertek: „sport” nem szerepel az adatban (a fő termék kategóriája). |
| k110 | augusztusban mennyi volt a késési arány összesen? | 3 | hibás értelmezés: tól: 2018-07-01 (elvárt: 2018-08-01) |
| k111 | mennyi az átlagos távolság a vevő és eladó között a bútoroknál? | 3 | hibás értelmezés: szűrő: {'kategoria': ['kitchen_dining_laundry_garden_furniture']} (elvárt: {'kategoria': ['furniture_decor']}) |
| k118 | mutasd a 2015-ös és 2016-os év teljes forgalmát egymás mellett | 3 | hibás értelmezés: bontás: [] (elvárt: ['ev']) |
| k121 | menniy vót a redneles összesen rioban a tavaj? | 3 | hibás értelmezés: szűrő: {'kategoria': ['toys'], 'vevo_allam': ['RJ']} (elvárt: {'vevo_allam': ['RJ']}); tól: 2017-09-01 (elvárt: 2017-01-01); ig: az adat vége (elvárt: 2017-12-31) |
| k123 | atlagosan meniy idö alat ér oda a cucc az északiknak? | 3 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: []); szűrő: {} (elvárt: {'vevo_regio': ['N']}) |
| k124 | mult évbe hányan késtek a kiszálitással a butoroknál? | 3 | hibás értelmezés: szűrő: {'kategoria': ['kitchen_dining_laundry_garden_furniture']} (elvárt: {'kategoria': ['furniture_decor']}); tól: az adat eleje (elvárt: 2017-01-01); ig: az adat vége (elvárt: 2017-12-31) |
| k126 | sp ba mibe kerult a fuvar atlagba 2018 elejen? | 3 | hibás értelmezés: szűrő: {} (elvárt: {'vevo_allam': ['SP']}) |
| k127 | mi a top 5 legroszabb dolog amiket a leglassabban visznek ki? | 3 | hibás értelmezés: bontás: ['vevo_allam'] (elvárt: ['kategoria']) |
| k128 | honnan jött a legtob vásárlo amikor a legnagyob volt a forgalom? | 3 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_allam"], "limit": 10, "metrika": "forgalom", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k130 | rio meg sp kozott mi volt a difi eladasban 17 nyaran? | 3 | hibás értelmezés: bontás: [] (elvárt: ['vevo_allam']); szűrő: {'vevo_allam': ['RJ']} (elvárt: {'vevo_allam': ['RJ', 'SP']}); tól: 2017-08-01 (elvárt: 2017-06-01); ig: 2017-12-31 (elvárt: 2017-08-31) |
