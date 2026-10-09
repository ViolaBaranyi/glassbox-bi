# Referencia-modellek — lezárt összevetés

Protokoll: `docs/v3_referencia_protokoll.json`, SHA256 `6ea464ac7fd7c4cda825282c2cd324d132495dd306c5eec9a7fb8cf33fcce34f`
(alap: `docs/v3_protokoll.json`, `9407febe2a77b894…`).
Jóváhagyta: Baranyi Viola (2026-10-09).
Futás: 2026-10-09 11:24:42 UTC · git `76934b1` · Python 3.14.3.
Teszt: 0.0361 késési arány; tanító sorok (tisztítva): 50,623.

## Eredmény a teszten (95% CI, heti blokk-bootstrap)

| modell | beállítás (CV-n választva) | CV PR-AUC | teszt PR-AUC | teszt ROC-AUC | teszt Brier | ECE (tizedek) |
|---|---|---|---|---|---|---|
| LightGBM (lezárt) | 119 fa | 0.1258 | 0.0978 [0.0552; 0.1274] | 0.7640 [0.7229; 0.7877] | 0.0339 [0.0188; 0.0495] | 0.0099 |
| logisztikus regresszió | C = 0.1 | 0.1241 | 0.0836 [0.0603; 0.1030] | 0.7401 [0.6922; 0.7810] | 0.0341 [0.0182; 0.0503] | 0.0115 |
| döntési fa | max_depth = 10 | 0.0934 | 0.0609 [0.0374; 0.0837] | 0.5972 [0.5726; 0.6338] | 0.0363 [0.0205; 0.0527] | 0.0232 |
| random forest | min_samples_leaf = 10 | 0.1131 | 0.0880 [0.0504; 0.1182] | 0.7385 [0.6958; 0.7619] | 0.0342 [0.0193; 0.0495] | 0.0180 |

## Páros összevetés: LightGBM − referencia (ugyanazokon a húzott heteken)

Pozitív PR-AUC / ROC-AUC és negatív Brier-különbség = a LightGBM jobb. Ha az
intervallum a nullát is tartalmazza, a különbség ezen a teszten nem kimutatható.

| referencia | PR-AUC különbség | ROC-AUC különbség | Brier-különbség |
|---|---|---|---|
| logisztikus regresszió | +0.0142 [-0.0101; +0.0292] | +0.0239 [-0.0175; +0.0568] | -0.00024 [-0.00102; +0.00056] |
| döntési fa | +0.0369 [+0.0023; +0.0534] | +0.1668 [+0.1050; +0.2014] | -0.00242 [-0.00341; -0.00135] |
| random forest | +0.0099 [+0.0004; +0.0176] | +0.0255 [+0.0134; +0.0386] | -0.00031 [-0.00062; +0.00005] |

Random forest, 5 mag: PR-AUC 0.0926 ± 0.0041,
ROC-AUC 0.7433 ± 0.0038.
