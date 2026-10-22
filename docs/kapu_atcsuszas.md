# A második kapu véletlen átcsúszása

Géppel készült (`tools/kapu_atcsuszas.py`), 2026-10-22T20:44:00+00:00; modell nélkül, a valódi tárházon, a lezárt kapuval (kód-ujjlenyomat `9295c1cdc88d360b…`). 186 eredmény a három lezárt kérdéssor megválaszolandó kérdéseiből; kérdésenként, áganként és alakonként 200 kitalált szám (mag 20261026), a [0.5; 1.5] · (legkisebb; legnagyobb) tartományból, az összesített érték alakja nélkül. Átcsúszás: a kapu átengedi az „Az érték X.” mondatot. Az arány kérdésenként, majd a kérdések átlaga, 95%-os bootstrap-intervallummal (a kérdések felett, mag 20261027).

Alakok: (a) a megjelenítés pontosságával; (b) eggyel kevesebb tizedessel; (c) eggyel kevesebb tizedessel, „kb.” előtaggal. A (b) és a (c) csak tizedes megjelenítésű mérőszámnál értelmezett.

## Összesen

| | fő ág (jelölők), (a) | fő ág (jelölők), (b) | fő ág (jelölők), (c) | kontrollág (szabad), (a) | kontrollág (szabad), (b) | kontrollág (szabad), (c) |
|---|---|---|---|---|---|---|
| átcsúszik | 0,8% [0,5; 1,1] (n = 186) | 0,0% [0,0; 0,0] (n = 98) | 5,3% [3,8; 6,9] (n = 98) | 1,2% [0,7; 1,9] (n = 186) | 0,6% [0,2; 1,0] (n = 98) | 5,2% [3,7; 6,8] (n = 98) |

## Mértékegység szerint

| | fő ág (jelölők), (a) | fő ág (jelölők), (b) | fő ág (jelölők), (c) | kontrollág (szabad), (a) | kontrollág (szabad), (b) | kontrollág (szabad), (c) |
|---|---|---|---|---|---|---|
| arány (%) | 3,6% [2,1; 5,2] (n = 19) | 0,0% [0,0; 0,0] (n = 19) | 5,6% [3,2; 8,3] (n = 19) | 3,9% [2,4; 5,6] (n = 19) | 1,1% [0,0; 2,6] (n = 19) | 6,0% [3,6; 8,7] (n = 19) |
| BRL | 0,1% [0,0; 0,1] (n = 72) | 0,0% [0,0; 0,0] (n = 31) | 0,8% [0,3; 1,4] (n = 31) | 0,0% [0,0; 0,1] (n = 72) | 0,0% [0,0; 0,0] (n = 31) | 0,7% [0,4; 1,2] (n = 31) |
| darab | 0,0% [0,0; 0,0] (n = 38) | — | — | 2,0% [0,1; 5,1] (n = 38) | — | — |
| km | 0,2% [0,0; 0,4] (n = 9) | — | — | 0,4% [0,0; 1,1] (n = 9) | — | — |
| nap | 1,5% [0,9; 2,3] (n = 48) | 0,0% [0,0; 0,0] (n = 48) | 8,0% [5,5; 10,9] (n = 48) | 1,3% [0,8; 1,9] (n = 48) | 0,7% [0,2; 1,2] (n = 48) | 7,8% [5,3; 10,7] (n = 48) |

## A nézet értékeinek száma szerint

| | fő ág (jelölők), (a) | fő ág (jelölők), (b) | fő ág (jelölők), (c) | kontrollág (szabad), (a) | kontrollág (szabad), (b) | kontrollág (szabad), (c) |
|---|---|---|---|---|---|---|
| 1 érték | 0,0% [0,0; 0,0] (n = 77) | 0,0% [0,0; 0,0] (n = 51) | 1,0% [0,1; 2,1] (n = 51) | 0,0% [0,0; 0,0] (n = 77) | 0,0% [0,0; 0,0] (n = 51) | 0,8% [0,1; 1,8] (n = 51) |
| 2–5 érték | 0,9% [0,2; 2,0] (n = 20) | 0,0% [0,0; 0,0] (n = 8) | 2,9% [0,3; 6,7] (n = 8) | 1,1% [0,2; 2,3] (n = 20) | 2,1% [0,0; 5,0] (n = 8) | 4,8% [0,9; 9,9] (n = 8) |
| 6 vagy több érték | 1,4% [0,9; 2,0] (n = 89) | 0,0% [0,0; 0,0] (n = 39) | 11,4% [8,6; 14,3] (n = 39) | 2,2% [1,2; 3,6] (n = 89) | 1,0% [0,4; 1,6] (n = 39) | 11,1% [8,3; 13,9] (n = 39) |

## Kérdéssor szerint

| | fő ág (jelölők), (a) | fő ág (jelölők), (b) | fő ág (jelölők), (c) | kontrollág (szabad), (a) | kontrollág (szabad), (b) | kontrollág (szabad), (c) |
|---|---|---|---|---|---|---|
| meresi_kerdessor | 0,7% [0,4; 1,1] (n = 102) | 0,0% [0,0; 0,0] (n = 58) | 4,6% [2,7; 6,8] (n = 58) | 0,7% [0,4; 1,1] (n = 102) | 0,6% [0,1; 1,1] (n = 58) | 4,5% [2,7; 6,5] (n = 58) |
| meresi_kerdessor_v2 | 1,0% [0,5; 1,7] (n = 45) | 0,0% [0,0; 0,0] (n = 24) | 6,4% [3,5; 9,4] (n = 24) | 2,6% [0,9; 5,3] (n = 45) | 0,2% [0,0; 0,8] (n = 24) | 6,1% [3,1; 9,6] (n = 24) |
| meresi_kerdessor_v3 | 0,8% [0,1; 1,7] (n = 39) | 0,0% [0,0; 0,0] (n = 16) | 5,9% [2,4; 10,2] (n = 16) | 0,6% [0,2; 1,2] (n = 39) | 0,9% [0,0; 2,0] (n = 16) | 6,4% [2,5; 10,9] (n = 16) |
