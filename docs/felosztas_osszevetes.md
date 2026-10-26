# Időbeli vagy véletlen felosztás — ugyanaz az adat, ugyanazok a beállítások

Készült: 2026-10-25T20:50:09+00:00 · kód-ujjlenyomat `eef140f2e0d4f3c8…` · 430 mp. Az előre rögzített beállítások: döntési napló.

Címkézett rendelés: 96470; a tisztított tanító ablak 50623 sor, az időbeli teszt 18603 sor. Véletlen felosztás: 10 ismétlés (mag 20261101 + r); zárójelben a legkisebb és a legnagyobb érték. Az időrendi belső ellenőrzés vágása 2017-12-10 (33654 tanító, 10291 értékelő sor).

## LightGBM

| mérőszám | időbeli teszt (2018. jún.–aug.) | véletlen felosztás a teljes időszakon | időn belül: véletlen 20% a tanító ablakból | ugyanazok a modellek az időbeli teszten | időrendi ellenőrzés a tanító ablak utolsó 20%-án |
|---|---|---|---|---|---|
| PR-AUC | 0,098 | 0,279 (0,262 – 0,303) | 0,240 (0,217 – 0,260) | 0,101 (0,095 – 0,110) | 0,079 |
| ROC-AUC | 0,764 | 0,796 (0,784 – 0,804) | 0,769 (0,758 – 0,781) | 0,764 (0,758 – 0,770) | 0,600 |
| késési arány | 3,6% | 6,8% (6,6% – 7,0%) | 5,6% (5,3% – 5,7%) | 3,6% (3,6% – 3,6%) | 5,5% |
| PR-AUC / késési arány | 2,71× | 4,13× (3,89× – 4,47×) | 4,32× (4,09× – 4,56×) | 2,80× (2,62× – 3,05×) | 1,44× |
| a felső 10% a késések ennyiedét fogja | 32,0% | 41,4% (40,3% – 42,7%) | 40,5% (39,3% – 42,7%) | 32,6% (30,1% – 34,4%) | 15,6% |
| átlagos becslés − tényleges arány (pp) | +0,78 | −0,06 (−0,33 – +0,25) | −0,03 (−0,31 – +0,28) | +0,67 (+0,45 – +0,90) | −1,56 |

## logisztikus regresszió

| mérőszám | időbeli teszt (2018. jún.–aug.) | véletlen felosztás a teljes időszakon | időn belül: véletlen 20% a tanító ablakból | ugyanazok a modellek az időbeli teszten | időrendi ellenőrzés a tanító ablak utolsó 20%-án |
|---|---|---|---|---|---|
| PR-AUC | 0,084 | 0,220 (0,204 – 0,236) | 0,189 (0,165 – 0,202) | 0,082 (0,079 – 0,083) | 0,087 |
| ROC-AUC | 0,740 | 0,763 (0,744 – 0,777) | 0,740 (0,729 – 0,752) | 0,736 (0,730 – 0,739) | 0,609 |
| késési arány | 3,6% | 6,8% (6,6% – 7,0%) | 5,6% (5,3% – 5,7%) | 3,6% (3,6% – 3,6%) | 5,5% |
| PR-AUC / késési arány | 2,32× | 3,26× (3,03× – 3,48×) | 3,40× (3,11× – 3,63×) | 2,26× (2,20× – 2,30×) | 1,59× |
| a felső 10% a késések ennyiedét fogja | 22,8% | 36,6% (34,7% – 38,5%) | 37,3% (35,8% – 38,2%) | 22,3% (21,1% – 23,1%) | 18,2% |
| átlagos becslés − tényleges arány (pp) | +0,17 | +0,03 (−0,25 – +0,28) | +0,08 (−0,20 – +0,34) | +0,23 (+0,10 – +0,34) | −0,17 |

## döntési fa

| mérőszám | időbeli teszt (2018. jún.–aug.) | véletlen felosztás a teljes időszakon | időn belül: véletlen 20% a tanító ablakból | ugyanazok a modellek az időbeli teszten | időrendi ellenőrzés a tanító ablak utolsó 20%-án |
|---|---|---|---|---|---|
| PR-AUC | 0,061 | 0,207 (0,194 – 0,224) | 0,186 (0,160 – 0,210) | 0,071 (0,058 – 0,095) | 0,066 |
| ROC-AUC | 0,597 | 0,732 (0,722 – 0,741) | 0,704 (0,681 – 0,717) | 0,648 (0,593 – 0,739) | 0,531 |
| késési arány | 3,6% | 6,8% (6,6% – 7,0%) | 5,6% (5,3% – 5,7%) | 3,6% (3,6% – 3,6%) | 5,5% |
| PR-AUC / késési arány | 1,69× | 3,07× (2,90× – 3,21×) | 3,36× (3,02× – 3,76×) | 1,96× (1,60× – 2,64×) | 1,19× |
| a felső 10% a késések ennyiedét fogja | 22,3% | 34,5% (32,8% – 36,6%) | 35,0% (31,8% – 37,1%) | 27,8% (19,6% – 40,8%) | 14,0% |
| átlagos becslés − tényleges arány (pp) | +1,22 | +0,01 (−0,35 – +0,39) | +0,06 (−0,18 – +0,32) | +1,21 (+0,58 – +1,79) | −1,45 |

## random forest

| mérőszám | időbeli teszt (2018. jún.–aug.) | véletlen felosztás a teljes időszakon | időn belül: véletlen 20% a tanító ablakból | ugyanazok a modellek az időbeli teszten | időrendi ellenőrzés a tanító ablak utolsó 20%-án |
|---|---|---|---|---|---|
| PR-AUC | 0,088 | 0,272 (0,245 – 0,291) | 0,233 (0,216 – 0,254) | 0,093 (0,085 – 0,107) | 0,076 |
| ROC-AUC | 0,738 | 0,786 (0,775 – 0,797) | 0,759 (0,750 – 0,769) | 0,743 (0,737 – 0,755) | 0,577 |
| késési arány | 3,6% | 6,8% (6,6% – 7,0%) | 5,6% (5,3% – 5,7%) | 3,6% (3,6% – 3,6%) | 5,5% |
| PR-AUC / késési arány | 2,43× | 4,03× (3,65× – 4,29×) | 4,19× (3,97× – 4,57×) | 2,56× (2,36× – 2,97×) | 1,39× |
| a felső 10% a késések ennyiedét fogja | 31,2% | 41,5% (39,5% – 43,2%) | 39,9% (38,4% – 41,1%) | 31,3% (28,7% – 37,8%) | 13,6% |
| átlagos becslés − tényleges arány (pp) | +1,80 | +0,06 (−0,23 – +0,29) | +0,11 (−0,12 – +0,39) | +1,87 (+1,73 – +2,03) | −0,00 |

## Az előre rögzített sejtések

E1 (LightGBM) — hány ismétlésben nagyobb a mérőszám:

| mérőszám | véletlen felosztás > időbeli teszt | időn belül > időn kívül (ugyanaz a modell) |
|---|---|---|
| ROC-AUC | 10/10 | 7/10 |
| PR-AUC / késési arány | 10/10 | 10/10 |
| a felső 10% a késések ennyiedét fogja | 10/10 | 10/10 |

E2 — a LightGBM ROC-AUC-előnye a logisztikus regresszióval szemben: az időbeli teszten 0,024, véletlen felosztásnál átlagosan 0,034 (0,022 – 0,039); nagyobb 9/10 ismétlésben.

E3 — kalibráció egészében: véletlen felosztásnál a legnagyobb eltérés 0,33 pp, az időbeli teszten +0,78 pp.

## Olvasat

A „véletlen felosztás” és az „időn belül” oszlop azt mutatja, amit egy időrendet figyelmen kívül hagyó értékelés jelentene; az „időbeli teszt” azt, amit a modell élesben, a jövőre nézve tud. A PR-AUC a késési aránytól függ (az időbeli teszten kisebb a késés), ezért mellette az emelés és a felső 10% is szerepel. A tanítóadat mindhárom esetben ugyanakkora vagy kisebb, mint a lezárt modelleké, a beállítások azonosak — a különbség a felosztásé.
