# A döntés stabilitása — mennyire marad ugyanaz a legkockázatosabb 10%?

Készült: 2026-10-25T20:57:51+00:00 · kód-ujjlenyomat `af790b3b7b79e4e0…` · 386 mp. Az előre rögzített beállítások: döntési napló.

Az időbeli teszt 18603 rendelése (késési arány 3,6%); a felső 10% = 1860 rendelés. 20 bootstrap-újratanítás (mag 20261023 + i) és 5 kontroll-mag — ugyanazok a modellek, mint a K3-ban. Szögletes zárójelben 95%-os intervallum a minták felett.

## Új tanítóadaton (bootstrap)

| modell | a felső 10% átfedése | legkisebb | stabil mag | többértelműség | legnagyobb eltérés | a 200-as lista átfedése | Spearman |
|---|---|---|---|---|---|---|---|
| LightGBM | 60,9% [58,4%; 63,0%] | 48,5% | 5,3% | 30,9% | 10,3% | 44,2% [41,7%; 46,6%] | 0,860 |
| logisztikus regresszió | 87,4% [86,9%; 87,9%] | 85,2% | 49,9% | 12,1% | 3,0% | 80,4% [79,4%; 81,5%] | 0,980 |
| döntési fa | 31,1% [25,6%; 36,8%] | 14,3% | 0,0% | 54,1% | 17,1% | 21,1% [15,3%; 27,2%] | 0,296 |
| random forest | 65,8% [62,9%; 68,5%] | 50,9% | 7,2% | 26,2% | 9,8% | 46,9% [43,7%; 49,9%] | 0,924 |

*Stabil mag:* a lezárt felső 10% mekkora része van minden újratanított modellnél is a felső 10%-ban. *Többértelműség:* a teszt-rendelések mekkora részének a besorolása (felső 10% vagy sem) tér el legalább egy modellnél. *Legnagyobb eltérés:* egyetlen modellnél a legtöbb átsorolás.

## Viszonyítás: ugyanaz az adat, más tanítási mag

| modell | a felső 10% átfedése | stabil mag | többértelműség | a 200-as lista átfedése |
|---|---|---|---|---|
| LightGBM | 78,2% [76,9%; 79,4%] | 53,4% | 10,4% | 66,6% [65,8%; 67,4%] |
| logisztikus regresszió | 100,0% [100,0%; 100,0%] | 100,0% | 0,0% | 100,0% [100,0%; 100,0%] |
| döntési fa | 94,6% [83,9%; 100,0%] | 73,1% | 5,4% | 100,0% [100,0%; 100,0%] |
| random forest | 83,0% [82,4%; 83,6%] | 62,8% | 8,1% | 72,4% [71,2%; 73,6%] |

## A modellek teljesítménye ugyanezeken az újratanításokon (leíró)

| modell | PR-AUC (lezárt) | PR-AUC (újratanítva; legkisebb – legnagyobb) | felső 10% fogása (lezárt) | felső 10% fogása (újratanítva; legkisebb – legnagyobb) |
|---|---|---|---|---|
| LightGBM | 0,098 | 0,093 (0,076 – 0,116) | 32,0% | 30,2% (24,4% – 36,6%) |
| logisztikus regresszió | 0,084 | 0,082 (0,076 – 0,091) | 22,8% | 22,9% (20,1% – 26,6%) |
| döntési fa | 0,061 | 0,067 (0,043 – 0,100) | 22,3% | 24,8% (10,6% – 42,6%) |
| random forest | 0,088 | 0,083 (0,060 – 0,109) | 31,2% | 27,6% (19,3% – 38,5%) |

## Páros összevetés: a felső 10% átfedése (A − B, mintánként párosítva)

| pár | különbség | előzetes sejtés | olvasat |
|---|---|---|---|
| logisztikus regresszió − LightGBM | 26,5 pp [24,4; 28,9] | A stabilabb | teljesült |
| logisztikus regresszió − random forest | 21,7 pp [18,9; 24,5] | A stabilabb | teljesült |
| LightGBM − döntési fa | 29,7 pp [23,8; 35,7] | A stabilabb | teljesült |
| random forest − döntési fa | 34,6 pp [28,3; 40,8] | A stabilabb | teljesült |
| logisztikus regresszió − döntési fa | 56,3 pp [50,6; 61,8] | A stabilabb | teljesült |
| LightGBM − random forest | −4,9 pp [−6,9; −2,9] | nincs | B stabilabb |

## Mellette: a magyarázat stabilitása (K3, ugyanezeken a modelleken)

| modell | a felső 10% átfedése | a magyarázat RBO-ja (K3) |
|---|---|---|
| LightGBM | 60,9% | 0,83 |
| logisztikus regresszió | 87,4% | 0,93 |
| döntési fa | 31,1% | 0,75 |
| random forest | 65,8% | 0,86 |
