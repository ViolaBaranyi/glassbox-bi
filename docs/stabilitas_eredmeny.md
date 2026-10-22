# A magyarázatok stabilitása (K3)

Géppel készült (`python -m xai.stability`), 2026-10-22T18:47:09+00:00. 20 bootstrap-újratanítás (mag 20261023 + i) és 5 kontroll-mag; 200 teszt-rendelés (a kontrollkaré, ujjlenyomat `bc675af716b0161e…`), 500 soros háttér, 50623 tisztított tanító sor. A valódi teszt-címkét a mérés nem használja. Idő: 61 perc.

## 1. A tanítóadat újramintázása

Rendelésenként a lezárt modell magyarázatához mérve, a minták átlaga, majd a rendelések átlaga (95%-os bootstrap-intervallum a rendelések felett). Kontroll: ugyanaz az adat, más tanítási mag — a tanítás saját zaja.

| modell | RBO | súlyozott tau | top-3 | top-3 iránya | CIES-súlyozott | RBO, kontroll-mag | becslés változása (pp): bootstrap / kontroll |
|---|---|---|---|---|---|---|---|
| LightGBM | 0,83 [0,83; 0,84] | 0,79 [0,78; 0,79] | 0,77 [0,75; 0,78] | 0,99 [0,99; 0,99] | 0,69 [0,68; 0,70] | 0,89 [0,89; 0,90] | 1,47 / 0,82 |
| logisztikus regresszió | 0,93 [0,93; 0,93] | 0,91 [0,90; 0,91] | 0,91 [0,90; 0,92] | 1,00 [1,00; 1,00] | 0,88 [0,88; 0,89] | 1,00 [1,00; 1,00] | 0,48 / 0,00 |
| döntési fa | 0,75 [0,74; 0,75] | 0,71 [0,70; 0,72] | 0,62 [0,61; 0,64] | 0,92 [0,90; 0,93] | 0,43 [0,40; 0,45] | 0,97 [0,97; 0,98] | 4,07 / 0,06 |
| random forest | 0,86 [0,86; 0,87] | 0,84 [0,83; 0,84] | 0,82 [0,81; 0,84] | 1,00 [1,00; 1,00] | 0,79 [0,78; 0,80] | 0,91 [0,91; 0,92] | 0,97 / 0,52 |

### A globális rangsor (a 200 rendelés átlagos |hatása|)

| modell | a lezárt modell top-5-je | RBO a lezárthoz (átlag [CI]; legkisebb) | azonos top-3 | azonos első |
|---|---|---|---|---|
| LightGBM | vállalt szállítási idő, vevő állama, eladó átlagos feladási ideje, rendelés hónapja, termékkategória | 0,95 [0,94; 0,96]; 0,86 | 70% | 95% |
| logisztikus regresszió | vállalt szállítási idő, rendelés hónapja, vevő állama, távolság, azonos állam | 0,93 [0,91; 0,94]; 0,86 | 40% | 100% |
| döntési fa | vállalt szállítási idő, ünnep közeli időszak, távolság, eladó átlagos feladási ideje, vevő állama | 0,86 [0,82; 0,89]; 0,70 | 45% | 70% |
| random forest | vállalt szállítási idő, vevő állama, rendelés hónapja, ünnep közeli időszak, eladó átlagos feladási ideje | 0,95 [0,94; 0,96]; 0,88 | 50% | 95% |

### A modellek páronként (K4): rendelésenkénti RBO-különbség

Előre rögzített sejtés: a logisztikus regresszió a legstabilabb, a döntési fa a legkevésbé; a LightGBM és a random forest a kettő között (egymáshoz képest nincs előzetes állítás).

Olvasat: a sejtés teljesült, ha a különbség 95%-os intervalluma 0 fölött van; fordított, ha 0 alatt; ha a 0-t tartalmazza, nem dönthető el.

| pár (A − B) | különbség [95%] | sejtés: A stabilabb? | olvasat |
|---|---|---|---|
| logisztikus regresszió − LightGBM | 0,095 [0,090; 0,100] | igen | teljesült |
| logisztikus regresszió − random forest | 0,067 [0,061; 0,072] | igen | teljesült |
| LightGBM − döntési fa | 0,087 [0,079; 0,095] | igen | teljesült |
| random forest − döntési fa | 0,115 [0,108; 0,122] | igen | teljesült |
| logisztikus regresszió − döntési fa | 0,182 [0,175; 0,189] | igen | teljesült |
| LightGBM − random forest | −0,028 [−0,035; −0,022] | nincs sejtés | B stabilabb |

## 2. A CIES eredeti meghatározása (bemeneti zaj)

A lezárt modellek; minden rendeléshez M zajos szomszéd (a számszerű jellemzők relatív α zajjal, a kategóriák és a logikai jellemzők változatlanok); CIES = max(0, 1 − átlagos súlyozott távolság / súlyozott nagyság). 1 = tökéletesen stabil.

| modell | α = 0,03 (M = 10) | α = 0,01 (M = 5) | α = 0,05 (M = 5) |
|---|---|---|---|
| LightGBM | 0,87 [0,86; 0,89] (szórás 0,13) | 0,90 [0,88; 0,92] (szórás 0,15) | 0,85 [0,83; 0,87] (szórás 0,14) |
| logisztikus regresszió | 0,95 [0,95; 0,96] (szórás 0,02) | 0,98 [0,98; 0,99] (szórás 0,01) | 0,93 [0,92; 0,93] (szórás 0,03) |
| döntési fa | 0,94 [0,93; 0,96] (szórás 0,09) | 0,98 [0,97; 0,99] (szórás 0,07) | 0,91 [0,89; 0,93] (szórás 0,12) |
| random forest | 0,96 [0,95; 0,96] (szórás 0,02) | 0,98 [0,98; 0,98] (szórás 0,01) | 0,93 [0,93; 0,94] (szórás 0,04) |

## 3. Utólagos, feltáró ellenőrzés: mitől kisebb a LightGBM CIES-e?

Nem előre rögzített; az eredmény ismeretében, a LightGBM alacsonyabb értéke miatt. Mindkét változat ugyanazokat a zajos szomszédokat használja, mint a 2. rész α = 0,03-as oszlopa (ugyanaz a mag, ugyanazok a húzások), így párosítva összevethető vele.

(a) **Kerekítve:** az egész értékű jellemzők (tételek száma, eladók száma, kategóriák száma, súly, térfogat, vállalt szállítási idő, hét napja, eladó korábbi rendelései, vevő korábbi rendelései) a zaj után egészre kerekítve — nincs például „0,03 korábbi rendelés”. Sejtés volt, hogy a LightGBM 0-hoz tapadó vágásai miatt a nullából lett kis pozitív szám másik ágra visz.

(b) **Kerekítve, a hónap zaja nélkül:** ugyanez, de a hónap körkódolása (szinusz, koszinusz) nem kap zajt. A hónap a valóságban nem „zajos” érték, és a kódolása lebegőpontosan sem egyértelmű: április és augusztus koszinusza egyaránt −0,5, de gépi ábrázolásban −0,4999999999999998, illetve −0,5000000000000004, és a LightGBM ezen a 6·10⁻¹⁶-os különbségen vág (küszöb −0,5). Az augusztusi rendelések így pontosan a vágáson ülnek, és a legkisebb zaj is áttolja őket.

| modell | 2. rész (α = 0,03, M = 10) | (a) kerekítve | (b) kerekítve, hónap zaja nélkül |
|---|---|---|---|
| LightGBM | 0,87 [0,86; 0,89] (szórás 0,13) | 0,87 [0,86; 0,89] (szórás 0,13) | 0,95 [0,94; 0,95] (szórás 0,04) |
| logisztikus regresszió | 0,95 [0,95; 0,96] (szórás 0,02) | 0,96 [0,96; 0,97] (szórás 0,02) | 0,97 [0,96; 0,97] (szórás 0,02) |
| döntési fa | 0,94 [0,93; 0,96] (szórás 0,09) | 0,94 [0,93; 0,96] (szórás 0,09) | 0,94 [0,93; 0,96] (szórás 0,09) |
| random forest | 0,96 [0,95; 0,96] (szórás 0,02) | 0,96 [0,96; 0,96] (szórás 0,02) | 0,96 [0,96; 0,96] (szórás 0,02) |

Ellenőrzés: a kerekítetlen szomszédokon a LightGBM CIES-e újraszámolva 0,8740, a 2. részben 0,8740 (ugyanazok a húzások).
