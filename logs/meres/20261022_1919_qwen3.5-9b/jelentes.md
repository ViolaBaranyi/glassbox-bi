# K1 mérés — qwen3.5:9b

Kezdés: 2026-10-22T19:19:45 · ismétlés: 1 · értelmezés és mindkét ág

- modell: `qwen3.5:9b` (`56671c2ab9385f9c`)
- protokoll: `docs/k1_protokoll_v3.json` · SHA256 `c704d15f619c565904bb9fa1cbb254c10da36c1e18ef0cbeed3466af99782d62`
- kérdéssor: `eval/meresi_kerdessor_v3.toml` · SHA256 `4ceea2657461afdb9419f317807947fe5ccc7018d03120bd671716a5f0a8a9aa` · 50 kérdés
- promptok: to_spec = `prompts/to_spec.v3.md` (`9266f3285311`), to_text = `prompts/to_text.v3.md` (`401ad3d593d2`), to_text_szabad = `prompts/to_text_szabad.v3.md` (`4070fbfeeb31`)
- kód: commit `98a4bc5ccd2825bd29b5f2c91279e5dcae62bc17` · ujjlenyomat `9295c1cdc88d360b`
- mért egységek (kérdés × ismétlés): 50

## Értelmezés (F-1) és elutasítás (F-2)

| mutató | eredmény | ismétlésenként | cél |
|---|---|---|---|
| F-1 — helyes mérőszám és bontás | 28/39 = **71,8%** (95%: 56,2% – 83,5%) | 71,8% (ismétlésenként: 71,8%) | ≥ 85% |
| teljes egyezés (szűrő, időablak, rendezés is) | 25/39 = **64,1%** (95%: 48,4% – 77,3%) | | |
| F-2 — a csapdát elutasítja | 7/11 = **63,6%** (95%: 35,4% – 84,8%) | 63,6% (ismétlésenként: 63,6%) | ≥ 90% |
| … az elvárt indokkal | 7/11 = **63,6%** (95%: 35,4% – 84,8%) | | |
| ugyanaz a gépi alak minden ismétlésben | 50/50 kérdés | | |

| kérdéstípus | egység | F-1 | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| csapda | 11 | — | 7 |
| idosor | 5 | 4 | 4 |
| idoszak | 2 | 1 | 1 |
| kombinalt | 17 | 11 | 8 |
| osszesito | 6 | 4 | 4 |
| rangsor | 7 | 6 | 6 |
| szures | 2 | 2 | 2 |

| szerző | egység | F-1 (megválaszolandó) | teljes egyezés / helyes elutasítás |
|---|---|---|---|
| viola | 50 | 28 | 32 |

| csapda-fajta | egység | elutasítva | az elvárt indokkal |
|---|---|---|---|
| adaton_kivul | 1 | 1 | 1 |
| jovo | 1 | 1 | 1 |
| katalogus_kivul | 1 | 1 | 1 |
| korlat | 3 | 0 | 0 |
| nincs_adat | 5 | 4 | 4 |

## K1 — alá nem támasztott állítás a modell szövegében

A 2. kapu által talált állítások: ez **alsó becslés** (amit a kapu nem lát, azt a kézi ellenőrzés becsli — `kezi_ellenorzes.csv`).

| | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| modellszöveg | 34 | 34 |
| **van benne alá nem támasztott állítás** | 5/34 = **14,7%** (95%: 6,4% – 30,1%) | 7/34 = **20,6%** (95%: 10,3% – 36,8%) |
| … ismétlésenként | 14,7% (ismétlésenként: 14,7%) | 20,6% (ismétlésenként: 20,6%) |
| … és el is jut a felhasználóhoz | 0/34 = **0,0%** (95%: 0,0% – 10,2%) | 7/34 = **20,6%** (95%: 10,3% – 36,8%) |
| a sablonos válasz látszik helyette | 5/34 = **14,7%** (95%: 6,4% – 30,1%) | — (a kontrollág nem vált) |
| leírt számok közül vissza nem vezethető | 3/7 | 4/123 |
| üres / értelmezhetetlen válasz | 0 | 0 |

Páros összevetés (34 kérdés, kérdésenként az ismétlések átlaga): a kontrollág és a fő ág különbsége **5,9 százalékpont** (95%-os bootstrap-intervallum: −8,8 – 23,5).

| állítás fajtája | fő ág (jelölők) | kontrollág (szabad) |
|---|---|---|
| vissza nem vezethető szám | 3 | 4 |
| rossz csoporthoz kötött érték | 1 | 1 |
| hamis felsőfok | 2 | 3 |

## Idő

| | medián |
|---|---|
| ① kérdés → gépi alak | 4,8 mp |
| … ebből betöltés | 0,0 mp |
| … ebből a prompt beolvasása | 0,4 mp |
| … ebből generálás | 2,2 mp |
| ② fő ág (jelölők) | 5,0 mp |
| ② kontrollág (szabad) | 5,5 mp |
| a mérés összesen | 0,2 óra |

## Ahol az értelmezés nem az elvárt

| # | kérdés | hányszor | ítélet és eltérés (első eset) |
|---|---|---|---|
| k301 | mennyi most az atlagos kiszallitasi ido osszessegeben? | 1 | téves elutasítás: nem_elerheto: Ezt nem tudom kiszámolni: a metrikakatalógus a múltról szól; egy rendelés késési kockázatát a „Rendelés kockázata” oldal becsli, havi előrejelzést a rendszer nem ad. Ami közel áll hozzá: késési arány. |
| k308 | SP-i eladoknal mennyi az atlagos szallitasi ido a vevo allama szerint, csak ott ahol kesett a csomag | 1 | hibás értelmezés: bontás: [] (elvárt: ['vevo_allam']); szűrő: {'elado_allam': ['SP']} (elvárt: {'elado_allam': ['SP'], 'kesett': ['kesett']}) |
| k321 | mennyi volt a teljes forgalom 2017-ben es 2018-ban? egymas mellett kernem | 1 | hibás értelmezés: bontás: ['honap'] (elvárt: ['ev']) |
| k322 | negyedeves bontasban kerem a forgalmat 2017 elejetol | 1 | hibás értelmezés: bontás: ['ev'] (elvárt: ['honap']) |
| k329 | a szallitasi dij atlaga a kosarertek mekkora reszet teszi ki? | 1 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „kosarertek aranya a szallitasi dijhoz” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k331 | hogy all a delkelet forgalomban az osszeshez kepest? | 1 | hibás értelmezés: bontás: [] (elvárt: ['vevo_regio']); szűrő: {'vevo_regio': ['SE']} (elvárt: {}) |
| k336 | RJ vs MG, melyik hoz tobb bevetelt, es melyikben nagyobb az atlagos kosarertek? | 1 | hibás értelmezés: metrika: rendelesek_szama (elvárt: forgalom vagy atlagos_kosarertek) |
| k337 | mennyi rendeles jott be Bahiabol tavaly | 1 | hibás értelmezés: szűrő: {'elado_allam': ['BA']} (elvárt: {'vevo_allam': ['BA']}) |
| k340 | a het melyik napjan rendelnek a legtobbet a deli regioban? oda idoznenk a kampanyt | 1 | hibás értelmezés: bontás: ['vevo_regio'] (elvárt: ['het_napja']); szűrő: {} (elvárt: {'vevo_regio': ['S']}) |
| k347 | hany rendelest mondtak le vagy kuldtek vissza tavaly? | 1 | hiányzó elutasítás: elfogadva: {"bontas": [], "idoablak": {"ig": "2017-12-31", "tol": "2017-01-01"}, "limit": 10, "metrika": "rendelesek_szama", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k348 | hol nagyobb a keses, ha a vevo es az elado ugyanabban az allamban van vagy ha nem? | 1 | hiányzó elutasítás: elfogadva: {"bontas": [], "limit": 10, "metrika": "atlagos_keses", "rendezes": "ertek_csokkeno", "szuro": {}} |
| k349 | 2017 novemberben allamonkent hany csomag kesett? black friday utan allt meg a telefon | 1 | hibás értelmezés: szűrő: {'kategoria': ['telephony']} (elvárt: {}) |
| k350 | a hetvegen leadott rendelesek jobban kesnek mint a hetkozbeniek? | 1 | hibás értelmezés: szűrő: {'het_napja': ['6', '7']} (elvárt: {}) |
| k353 | mi az 5 legnagyobb kategoria es az 5 legnagyobb allam bevetel szerint? | 1 | téves elutasítás: tul_sok_bontas: Egyszerre legfeljebb 1 bontás lehet (a kérdésben 2 van). |
| k356 | regios bontasban a forgalom es a rendelesszam, szazalekokkal. ezt vinnem a boardnak | 1 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „szazalekokkal” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k357 | atlagos szallitasi ido es kesesi arany osszessegeben, ezt a kettot kerem | 1 | téves elutasítás: ismeretlen_metrika: Ezt nem tudom kiszámolni: „atlagos szallitasi ido es kesesi arany osszessegeben” nincs a metrikakatalógusban. A katalógusban szereplő mérőszámok: rendelések száma, késett rendelések száma, késési arány, átlagos szállítási idő, szállítási idő mediánja, átlagos vállalt szállítási idő, átlagos késés, átlagos kosárérték, forgalom, átlagos szállítási díj és átlagos eladó–vevő távolság. |
| k359 | a 3 legnagyobb regioban hogy alakult a kesesi arany az elmult evben? ha romlik az baj | 1 | hiányzó elutasítás: elfogadva: {"bontas": ["vevo_regio"], "idoablak": {"tol": "2017-10-01"}, "limit": 3, "metrika": "kesesi_arany", "rendezes": "ertek_csokkeno", "szuro": {"vevo_regio": ["NE", "SE", "S"]}} |
| k360 | a delkelet reszaranya a bevetelbol novekszik vagy csokken eves szinten? | 1 | hiányzó elutasítás: elfogadva: {"bontas": ["ev"], "limit": 100, "metrika": "forgalom", "rendezes": "bontas", "szuro": {"vevo_regio": ["SE"]}} |
