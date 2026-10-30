# K1 mérés — qwen3.5:4b

Kezdés: 2026-10-22T19:11:08 · ismétlés: 1 · értelmezés és mindkét ág

- modell: `qwen3.5:4b` (`d8b0f5e9760cd168`)
- protokoll: `docs/k1_protokoll_v3.json` · SHA256 `6e2ecd029ca708f93041dd147d9ce059dc27d7fa941714f8615c9f7a75ab9c7a`
- kérdéssor: `eval/meresi_kerdessor_v3.toml` · SHA256 `4ceea2657461afdb9419f317807947fe5ccc7018d03120bd671716a5f0a8a9aa` · 50 kérdés
- promptok: to_spec = `prompts/to_spec.v3.md` (`9266f3285311`), to_text = `prompts/to_text.v3.md` (`401ad3d593d2`), to_text_szabad = `prompts/to_text_szabad.v3.md` (`4070fbfeeb31`)
- kód: commit `e8c8bdda8f6ee6b193dd1154512fb63fbd2c50da` · ujjlenyomat `7a3a5e94fe9efe50`
- mért egységek (kérdés × ismétlés): 50

## Értelmezés (F-1) és elutasítás (F-2)

| mutató | eredmény | ismétlésenként | cél |
|---|---|---|---|
| F-1 — helyes mérőszám és bontás | 28/39 = **71,8%** (95%: 56,2% – 83,5%) | 71,8% (ismétlésenként: 71,8%) | ≥ 85% |
| teljes egyezés (szűrő, időablak, rendezés is) | 23/39 = **59,0%** (95%: 43,4% – 72,9%) | | |
| F-2 — a csapdát elutasítja | 7/11 = **63,6%** (95%: 35,4% – 84,8%) | 63,6% (ismétlésenként: 63,6%) | ≥ 90% |
| … az elvárt indokkal | 7/11 = **63,6%** (95%: 35,4% – 84,8%) | | |
| ugyanaz a gépi alak minden ismétlésben | 50/50 kérdés | | |

| kérdéstípus | egység | F-1 | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| csapda | 11 | — | 7 |
| idosor | 5 | 4 | 4 |
| idoszak | 2 | 0 | 0 |
| kombinalt | 17 | 11 | 8 |
| osszesito | 6 | 5 | 5 |
| rangsor | 7 | 6 | 4 |
| szures | 2 | 2 | 2 |

| szerző | egység | F-1 (megválaszolandó) | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| viola | 50 | 28 | 30 |

| csapda-fajta | egység | elutasítva | az elvárt indokkal |
|---|---|---|---|
| adaton_kivul | 1 | 0 | 0 |
| jovo | 1 | 0 | 0 |
| katalogus_kivul | 1 | 1 | 1 |
| korlat | 3 | 1 | 1 |
| nincs_adat | 5 | 5 | 5 |

## K1 — alá nem támasztott állítás a modell szövegében

A 2. kapu által talált állítások: ez **alsó becslés** (amit a kapu nem lát, azt a kézi ellenőrzés becsli — `kezi_ellenorzes.csv`).

| | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| modellszöveg | 38 | 38 |
| **van benne alá nem támasztott állítás** | 15/38 = **39,5%** (95%: 25,6% – 55,3%) | 7/38 = **18,4%** (95%: 9,2% – 33,4%) |
| … ismétlésenként | 39,5% (ismétlésenként: 39,5%) | 18,4% (ismétlésenként: 18,4%) |
| … és el is jut a felhasználóhoz | 0/38 = **0,0%** (95%: 0,0% – 9,2%) | 7/38 = **18,4%** (95%: 9,2% – 33,4%) |
| a sablonos válasz látszik helyette | 15/38 = **39,5%** (95%: 25,6% – 55,3%) | — (a kontrollág nem vált) |
| leírt számok közül vissza nem vezethető | 9/22 | 5/106 |
| üres / értelmezhetetlen válasz | 0 | 0 |

Páros összevetés (38 kérdés, kérdésenként az ismétlések átlaga): a kontrollág és a fő ág különbsége **−21,1 százalékpont** (95%-os bootstrap-intervallum: −39,5 – −2,6).

| állítás fajtája | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| kitalált jelölő | 10 | 0 |
| vissza nem vezethető szám | 9 | 5 |
| rossz csoporthoz kötött érték | 8 | 3 |
| hamis felsőfok | 1 | 1 |

## Idő

| | medián |
|---|---|
| ① kérdés → gépi alak | 3,6 mp |
| … ebből betöltés | 0,0 mp |
| … ebből a prompt beolvasása | 0,3 mp |
| … ebből generálás | 1,1 mp |
| ② fő ág (jelölők) | 3,8 mp |
| ② kontrollág (szabad) | 3,8 mp |
| a mérés összesen | 0,1 óra |

## Ahol az értelmezés nem az elvárt

| # | kérdés | hányszor | ítélet és eltérés (első eset) |
|---|---|---|---|
| k308 | SP-i eladoknal mennyi az atlagos szallitasi ido a vevo allama szerint, csak ott ahol kesett a csomag | 1 | hibás értelmezés: bontás: [] (elvárt: ['vevo_allam']); szűrő: {'elado_allam': ['SP']} (elvárt: {'elado_allam': ['SP'], 'kesett': ['kesett']}) |
| k314 | mennyi az atlagos kosarertek osszessegeben, kene egy referencia amihez tudom meri a sajatjaimat | 1 | hibás értelmezés: metrika: forgalom (elvárt: atlagos_kosarertek) |
| k315 | butor vs lakastextil: melyikbol megy tobb rendeles, es forgalomban melyik a nagyobb? | 1 | hibás értelmezés: szűrő: {} (elvárt: {'kategoria': ['bed_bath_table', 'furniture_decor']}) |
| k319 | mi az a 10 kategoria amibol szinte semmi nem megy? kivezetnem oket | 1 | hibás értelmezés: rendezes: ertek_csokkeno (elvárt: ertek_novekvo) |
| k321 | mennyi volt a teljes forgalom 2017-ben es 2018-ban? egymas mellett kernem | 1 | hibás értelmezés: bontás: [] (elvárt: ['ev']); rendezes: ertek_csokkeno (elvárt: bontas) |
| k325 | melyik 5 allam adja a forgalom legnagyobb reszet? szazalekosan is kernem | 1 | hibás értelmezés: bontás: [] (elvárt: ['vevo_allam']) |
| k329 | a szallitasi dij atlaga a kosarertek mekkora reszet teszi ki? | 1 | téves elutasítás: nem_elerheto: Ezt nem tudom kiszámolni: az adathalmaz nem tartalmaz beszerzési árat, ezért haszon vagy árrés nem számolható. Ami közel áll hozzá: átlagos kosárérték és átlagos szállítási díj. |
| k330 | allamonkent az atlagos kosarertek 2018-ban, es hogy viszonyul ez az orszagos atlaghoz | 1 | hibás értelmezés: bontás: ['elado_allam'] (elvárt: ['vevo_allam']) |
| k331 | hogy all a delkelet forgalomban az osszeshez kepest? | 1 | hibás értelmezés: bontás: [] (elvárt: ['vevo_regio']) |
| k335 | hogy alakult az eszakkeleti regio forgalma negyedevente? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); tól: 2018-04-01 (elvárt: az adat eleje); ig: 2018-06-30 (elvárt: az adat vége); rendezes: ertek_csokkeno (elvárt: bontas) |
| k336 | RJ vs MG, melyik hoz tobb bevetelt, es melyikben nagyobb az atlagos kosarertek? | 1 | hibás értelmezés: szűrő: {} (elvárt: {'vevo_allam': ['MG', 'RJ']}) |
| k339 | mennyi forgalomra szamithatok a kovetkezo negyedevben a regiomban? tervet kell irnom a heten | 1 | hiányzó elutasítás: elfogadva: {"bontas": [], "limit": 10, "metrika": "forgalom", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k340 | a het melyik napjan rendelnek a legtobbet a deli regioban? oda idoznenk a kampanyt | 1 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: ['het_napja']); szűrő: {} (elvárt: {'vevo_regio': ['S']}) |
| k348 | hol nagyobb a keses, ha a vevo es az elado ugyanabban az allamban van vagy ha nem? | 1 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_allam"], "limit": 10, "metrika": "kesesi_arany", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k349 | 2017 novemberben allamonkent hany csomag kesett? black friday utan allt meg a telefon | 1 | hibás értelmezés: szűrő: {'kategoria': ['telephony']} (elvárt: {}) |
| k350 | a hetvegen leadott rendelesek jobban kesnek mint a hetkozbeniek? | 1 | hibás értelmezés: bontás: [] (elvárt: ['het_napja']); szűrő: {'het_napja': ['7']} (elvárt: {}) |
| k353 | mi az 5 legnagyobb kategoria es az 5 legnagyobb allam bevetel szerint? | 1 | hibás értelmezés: limit: 10 (elvárt: 5) |
| k354 | a 2015-es evhez kepest hogy allunk? kerek egy osszehasonlitast 2015 es 2017 kozott | 1 | hiányzó elutasítás: elfogadva: {"bontas": [], "idoablak": {"ig": "2017-12-31"}, "limit": 10, "metrika": "forgalom", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k355 | 2017 es 2018 elso 8 honapja hogy all egymashoz forgalomban? | 1 | hibás értelmezés: bontás: [] (elvárt: ['honap']); ig: 2018-06-30 (elvárt: az adat vége); rendezes: ertek_csokkeno (elvárt: bontas) |
| k359 | a 3 legnagyobb regioban hogy alakult a kesesi arany az elmult evben? ha romlik az baj | 1 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_regio"], "idoablak": {"tol": "2017-09-01"}, "limit": 3, "metrika": "kesesi_arany", "rendezes": "ertek_csokkeno", "szuro": {}} |
