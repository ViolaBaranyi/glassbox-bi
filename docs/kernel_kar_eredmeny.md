# KernelSHAP-kontrollkar — eredmény

200 teszt-rendelés (mag 20261012), közös háttér: 100 rendelés a tisztított tanító ablakból, 2090 koalíció rendelésenként, `l1_reg=False`, 21 játékos (a hónap egyben), valószínűség-tér, interventional. Futás: 2026-10-12 12:12:23 UTC, Linux-6.18.44-fc-v114-x86_64-with-glibc2.39, Python 3.14.8, 1862 mp. A rendelés-részhalmaz ujjlenyomata (SHA256): `bc675af716b0161e…`

Mértékek (rendelésenként, átlag [95% bootstrap-CI]): **top3** — a 3 legfontosabb tényező közös része; **RBO** (p = 0,9) — rangsor-egyezés, a rangsor elejét súlyozza; **wtau** — súlyozott Kendall-tau; **előjel3** — a viszonyítás top-3 tényezőjének iránya egyezik-e; **rel_L1** — Σ|eltérés| / Σ|viszonyítás|.

## 1. A felület arányos átváltása vs a valószínűség-tér Shapley-értékei

| modell | összevetés | top3 | RBO | wtau | előjel3 | rel_L1 |
|---|---|---|---|---|---|---|
| LightGBM | a felület magyarázata | 0,82 [0,80; 0,85] | 0,88 [0,88; 0,89] | 0,86 [0,85; 0,87] | 1,00 [1,00; 1,00] | 0,35 [0,33; 0,36] |
| logisztikus regresszió | a felület magyarázata | 0,91 [0,89; 0,93] | 0,93 [0,93; 0,94] | 0,92 [0,91; 0,92] | 1,00 [1,00; 1,00] | 0,34 [0,33; 0,35] |
| logisztikus regresszió | ugyanazzal a háttérrel | 0,89 [0,87; 0,91] | 0,94 [0,94; 0,95] | 0,94 [0,94; 0,94] | 1,00 [1,00; 1,00] | 0,30 [0,29; 0,31] |
| döntési fa | a felület magyarázata | 0,91 [0,88; 0,93] | 0,89 [0,88; 0,90] | 0,85 [0,85; 0,86] | 1,00 [1,00; 1,00] | 0,25 [0,24; 0,26] |
| random forest | a felület magyarázata | 0,88 [0,85; 0,90] | 0,90 [0,89; 0,90] | 0,88 [0,88; 0,89] | 1,00 [1,00; 1,00] | 0,19 [0,18; 0,20] |

## 2. A modellek egyezése (RBO, p = 0,9)

| modellpár | kontrollkar (ugyanaz a magyarázó) | saját magyarázók (a felületé) | top3: kar / saját |
|---|---|---|---|
| LightGBM – logisztikus regresszió | 0,74 [0,73; 0,75] | 0,72 [0,71; 0,73] | 0,61 / 0,61 |
| LightGBM – döntési fa | 0,65 [0,64; 0,66] | 0,66 [0,65; 0,67] | 0,47 / 0,43 |
| LightGBM – random forest | 0,77 [0,76; 0,78] | 0,74 [0,73; 0,75] | 0,69 / 0,63 |
| logisztikus regresszió – döntési fa | 0,62 [0,60; 0,63] | 0,61 [0,60; 0,62] | 0,37 / 0,33 |
| logisztikus regresszió – random forest | 0,71 [0,70; 0,73] | 0,67 [0,66; 0,68] | 0,57 / 0,48 |
| döntési fa – random forest | 0,65 [0,64; 0,66] | 0,67 [0,66; 0,68] | 0,45 / 0,47 |

## 3. A kar saját zaja

| modell | mintavételi mag: RBO | top3 | rel_L1 | más háttér: RBO | top3 | rel_L1 | alapérték-eltérés (pp) |
|---|---|---|---|---|---|---|---|
| LightGBM | 0,98 [0,97; 0,98] | 0,99 [0,97; 1,00] | 0,04 [0,04; 0,04] | 0,91 [0,90; 0,92] | 0,87 [0,83; 0,91] | 0,19 [0,18; 0,21] | 0,74 |
| logisztikus regresszió | 0,99 [0,98; 0,99] | 1,00 [1,00; 1,00] | 0,02 [0,02; 0,03] | 0,94 [0,93; 0,94] | 0,92 [0,88; 0,96] | 0,17 [0,16; 0,18] | 0,25 |
| döntési fa | 0,96 [0,96; 0,97] | 0,99 [0,97; 1,00] | 0,07 [0,07; 0,08] | 0,87 [0,86; 0,89] | 0,89 [0,85; 0,93] | 0,25 [0,22; 0,27] | 0,92 |
| random forest | 0,99 [0,98; 0,99] | 0,97 [0,95; 0,99] | 0,02 [0,02; 0,03] | 0,92 [0,91; 0,93] | 0,84 [0,79; 0,89] | 0,18 [0,16; 0,19] | 0,37 |

## 4. Modellenként

| modell | alapérték (E[f]) | additivitási hiba | idő (mp) | a 3 legfontosabb tényező a karon (átl. |pp|) |
|---|---|---|---|---|
| LightGBM | 5,22% | 3.5e-18 | 259 | vállalt szállítási idő 2,18 · vevő állama 1,46 · rendelés hónapja 1,19 |
| logisztikus regresszió | 5,73% | 8.3e-17 | 116 | vállalt szállítási idő 3,76 · rendelés hónapja 1,94 · vevő állama 1,65 |
| döntési fa | 6,44% | 2.8e-17 | 105 | vállalt szállítási idő 1,79 · ünnep közeli időszak 1,66 · távolság 1,45 |
| random forest | 5,72% | 2.8e-17 | 744 | vállalt szállítási idő 1,22 · rendelés hónapja 0,91 · vevő állama 0,90 |
