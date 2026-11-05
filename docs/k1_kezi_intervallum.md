# A K1 kézi ellenőrzésének bizonytalansága (utólagos)

Forrás: `docs/k1_kezi_ellenorzes.json`. Jeffreys-féle béta-eloszlás rétegenként, 40000 húzás, mag 20261104; a megjelölt arány rögzített. Eljut: a fő ágon a kapu által nem látott, a kontrollágon minden alátámasztatlan szöveg (a modell szövege jut el). Különbség: kontrollág − fő ág; hányados: fő ág / kontrollág.

| Futás | Modell | fő ág K1 korr. | fő ág: eljut | kontrollág: eljut | különbség (pp) | hányados |
|---|---|---|---|---|---|---|
| 1. mérés (v3) | qwen3.5:4b | 40,3 [28,0; 54,8] | 14,2 [5,1; 29,1] | 47,8 [33,5; 62,8] | 33,6 [12,8; 51,1] | 0,30 [0,10; 0,67] |
| 1. mérés (v3) | qwen3.5:2b | 74,0 [56,2; 85,9] | 42,2 [29,1; 52,0] | 62,8 [46,6; 74,9] | 20,6 [1,5; 38,0] | 0,67 [0,45; 0,97] |
| 2. mérés (v4) | qwen3.5:4b | 38,6 [25,7; 52,2] | 9,5 [2,8; 21,9] | 30,9 [17,8; 47,7] | 21,4 [3,3; 39,4] | 0,31 [0,08; 0,84] |
| 2. mérés (v4) | qwen3.5:2b | 64,0 [46,1; 76,3] | 10,0 [3,0; 21,2] | 62,7 [43,3; 77,4] | 52,7 [30,3; 69,0] | 0,16 [0,05; 0,38] |
| 3. mérés (v5) | qwen3.5:4b | 43,4 [30,9; 55,9] | 9,3 [2,8; 21,7] | 33,0 [22,1; 47,9] | 23,6 [7,0; 39,7] | 0,28 [0,08; 0,73] |
| összevont (súlyozatlan) | | 52,1 [45,1; 57,5] | 17,1 [13,2; 22,7] | 47,4 [40,4; 53,7] | 30,4 [21,2; 37,4] | 0,36 [0,27; 0,50] |
