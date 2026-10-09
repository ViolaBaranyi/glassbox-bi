# Lezárt v3 alapfutás — eredmény

Protokoll: `docs/v3_protokoll.json`, SHA256 `9407febe2a77b8945baa8500dc8f66831c615325b9bbe9ef4d326d743b7da134`
Jóváhagyta: Baranyi Viola (2026-10-09).
Futás: 2026-10-09 10:29:24 UTC · git `6f1b792` (tiszta munkapéldány, commitolt protokoll) · Python 3.14.3.
Adat: valós, 96,470 rendelés.

## Modellválasztás (csak a tanító időszak)
Bővülő ablakos CV, 4 hajtás × 3 mag, korai leállítás PR-AUC-ra.
Legjobb iterációk mediánja 118.5 → **N_fix = 119 fa**
(alsó korlát 50).
Címke-tisztítás: be
(50,623 tanító sor; 6,694 kimaradt).

## Eredmény
Végső modell: mag 42, 119 fa, 22 jellemző.
Bázisráta (késési arány): teszt 0.0361, validáció 0.1011,
tanító 0.0562.

| mérőszám | teszt [95% CI, heti blokk-bootstrap] | validáció [95% CI] | teszt, 5 mag (átlag ± szórás) |
|---|---|---|---|
| PR-AUC | 0.0978 [0.0552; 0.1274] | 0.1791 [0.1288; 0.2423] | 0.1010 ± 0.0027 |
| ROC-AUC | 0.7640 [0.7229; 0.7877] | 0.6497 [0.6139; 0.6908] | 0.7673 ± 0.0041 |
| Brier | 0.0339 [0.0188; 0.0495] | 0.0906 [0.0592; 0.1269] | 0.0337 ± 0.0001 |
| ECE (egyenlő szélességű sávok) | 0.0078 [0.0026; 0.0196] | 0.0490 [0.0163; 0.0912] | 0.0076 ± 0.0015 |
| ECE (tizedek) | 0.0099 [0.0080; 0.0195] | 0.0482 [0.0159; 0.0912] | 0.0091 ± 0.0007 |

Páros összevetés a teszten — a modell és a tanító időszak arányát mondó konstans előrejelzés:
PR-AUC különbség +0.0617 [+0.0349; +0.0782],
Brier-különbség -0.00134 [-0.00186; -0.00072]
(negatív = a modell jobb).

Az intervallumok a teszt heteinek véletlenségét mérik (14 hét,
B = 2000); a magok szórása a tanítási véletlent — a kettő külön forrás.
Az ECE torzított mutató: a bootstrap-intervalluma felfelé tolódik, a pontbecslés a széle közelébe eshet.
