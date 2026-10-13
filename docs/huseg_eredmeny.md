# A magyarázatok hűsége a modellhez — eredmény

Futás: 2026-10-13 10:32:15 UTC, Linux-6.18.44-fc-v114-x86_64-with-glibc2.39, Python 3.14.6, 1643 mp. A paraméterek a futás előtt rögzítve (döntési napló, 2026-10-13). A valódi teszt-címkéket egyik mérés sem használja.

## 1. Törlési és beszúrási görbe

200 teszt-rendelés (a KernelSHAP-kontrollkar részhalmaza, ujjlenyomat `bc675af716b0161e…`), 21 tényező, interventional maszkolás 100 rendelésnyi közös háttérrel, valószínűség-tér. Sorrend: a magyarázat szerint a legjobban növelő tényező előre. **AOPC** — a törlésnél a becslés esésének, a beszúrásnál az emelkedésének átlaga a 22 lépésen (százalékpont, a nagyobb a jobb); **top-3 esés** — az első 3 tényező kivétele után. Véletlen: 5 sorrend átlaga rendelésenként.

| modell | sorrend | törlés AOPC | beszúrás AOPC | top-3 esés |
|---|---|---|---|---|
| LightGBM | a felület magyarázata | 2,31 [1,74; 2,96] | 4,98 [4,38; 5,62] | 2,77 [2,17; 3,44] |
| LightGBM | KernelSHAP (felső viszonyítás) | 2,27 [1,71; 2,92] | 5,34 [4,71; 6,03] | 2,75 [2,16; 3,41] |
| LightGBM | véletlen (alsó viszonyítás) | −0,33 [−0,74; 0,14] | −0,50 [−0,78; −0,18] | −0,01 [−0,21; 0,20] |
| logisztikus regresszió | a felület magyarázata | 1,98 [1,59; 2,42] | 8,67 [7,86; 9,55] | 2,44 [2,05; 2,88] |
| logisztikus regresszió | KernelSHAP (felső viszonyítás) | 1,98 [1,60; 2,43] | 8,70 [7,89; 9,58] | 2,44 [2,06; 2,89] |
| logisztikus regresszió | véletlen (alsó viszonyítás) | −1,45 [−1,72; −1,14] | −0,71 [−1,03; −0,36] | −0,47 [−0,60; −0,35] |
| döntési fa | a felület magyarázata | 1,45 [0,78; 2,17] | 4,11 [3,46; 4,81] | 1,98 [1,26; 2,73] |
| döntési fa | KernelSHAP (felső viszonyítás) | 1,46 [0,78; 2,17] | 4,29 [3,64; 5,00] | 1,94 [1,23; 2,67] |
| döntési fa | véletlen (alsó viszonyítás) | −0,98 [−1,49; −0,47] | −1,02 [−1,32; −0,69] | −0,35 [−0,63; −0,07] |
| random forest | a felület magyarázata | 1,97 [1,63; 2,29] | 3,05 [2,76; 3,36] | 2,47 [2,14; 2,81] |
| random forest | KernelSHAP (felső viszonyítás) | 1,99 [1,65; 2,32] | 3,10 [2,81; 3,42] | 2,52 [2,19; 2,86] |
| random forest | véletlen (alsó viszonyítás) | −0,45 [−0,69; −0,21] | −0,08 [−0,27; 0,11] | −0,22 [−0,33; −0,10] |

**Páros különbség (a felület − véletlen, ill. − KernelSHAP), rendelésenként:**

| modell | törlés AOPC: − véletlen | − KernelSHAP | top-3 esés: − véletlen | a rendelések hány %-ában jobb a véletlennél |
|---|---|---|---|---|
| LightGBM | 2,64 [2,43; 2,86] | 0,03 [0,02; 0,05] | 2,78 [2,33; 3,30] | 100% |
| logisztikus regresszió | 3,42 [3,20; 3,65] | −0,01 [−0,01; −0,01] | 2,91 [2,56; 3,31] | 100% |
| döntési fa | 2,44 [2,19; 2,69] | −0,01 [−0,03; 0,01] | 2,33 [1,79; 2,89] | 100% |
| random forest | 2,42 [2,29; 2,54] | −0,03 [−0,03; −0,02] | 2,69 [2,43; 2,95] | 100% |

## 2. Beültetett jellemző

A „jel” a `kategoria_szam`, a „zaj” a `vevo_korabbi_rendelesek` helyén (a két leggyengébb valódi jellemző). Jel: P = 0,20; a jel = 1, időben érkezett rendelések 10%-a késettre vált a címkében → a tanító ablakban a késési arány jel = 1-nél 15,1%, jel = 0-nál 5,7% (eredetileg 5,6%). Zaj: egyenletes 0–9. Mag 20261013. A felület magyarázata 500 teszt-rendelésen. Küszöbök (előre rögzítve): jel a top-3-ban ≥ 90%, iránya ≥ 95%; zaj a top-3-ban ≤ 1%, átlagos |hatása| ≤ a jelé 5%-a.

| modell | jel a top-3-ban (jel = 1) | jel iránya helyes | jel helyezése | zaj a top-3-ban | zaj / jel átl. |hatás| | zaj helyezése | megfelelt? | teszt-AUC (félszint.) | a zaj valódi hatása a modellre* |
|---|---|---|---|---|---|---|---|---|---|
| LightGBM | 100,0% (igen) | 100,0% (igen) | 1. | 0,0% (igen) | 1,5% (igen) | 21. | igen | 0,763 | 0,124 pp (magyarázat: 0,039 pp) |
| logisztikus regresszió | 100,0% (igen) | 100,0% (igen) | 2. | 0,0% (igen) | 1,1% (igen) | 19. | igen | 0,730 | 0,025 pp (magyarázat: 0,024 pp) |
| döntési fa | 100,0% (igen) | 100,0% (igen) | 1. | 0,6% (igen) | 3,1% (igen) | 17. | igen | 0,724 | 0,133 pp (magyarázat: 0,093 pp) |
| random forest | 100,0% (igen) | 100,0% (igen) | 1. | 0,0% (igen) | 5,4% (**nem**) | 18. | **nem** | 0,750 | 0,189 pp (magyarázat: 0,116 pp) |

\* Feltáró, nem előre rögzített ellenőrzés: ha CSAK a zajt cseréljük a háttér 50 értékére, a modell becslése átlagosan ennyit mozdul (százalékpont) — vagyis mennyire használja maga a modell a zajt. Ha ez nagyobb, mint amit a magyarázat a zajnak tulajdonít, a magyarázat nem túlozza el a zaj szerepét: a modell épít rá.
