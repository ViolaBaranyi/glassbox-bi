# Referencia-modellek — a lezárt összevetés protokollja

**Állapot: TERVEZET** — jóváhagyásra vár. Amíg a `docs/v3_referencia_protokoll.json`
nincs jóváhagyva és commitolva, a `python -m pipeline.v3_reference` nem indul el.

## Miért kellenek referencia-modellek?

1. **Megéri-e a LightGBM bonyolultsága?** Ha egy egyszerűbb modell ugyanannyit tud,
   az átláthatóbbat kell választani — egy XAI-dolgozatban ez különösen fontos.
2. **A K4 kutatási kérdés** (bonyolultság ↔ magyarázat) több bonyolultsági szintet kíván:
   lineáris → egyetlen fa → erdő → gradiens-boosting.
3. **A SHAP-réteg** mind a négy modellre elkészül (lineáris magyarázó, illetve TreeSHAP).

## Tisztességes összevetés

* **Ugyanaz az adat-protokoll**, mint a lezárt LightGBM-nél (`docs/v3_protokoll.json`):
  22 jellemző, időbeli vágás, címke-tisztítás, súlyozás és utólagos kalibrátor nélkül.
  A LightGBM a lezárt modell — nem tanul újra mást.
* **Közös előfeldolgozás:** hiányzó számérték → medián + hiány-jelző oszlop; kategória →
  one-hot (a 20-nál ritkább kategóriák összevonva); a logisztikus regressziónál
  standardizálás is.
* **Mindegyik modell egy, a bonyolultságát szabályozó hiperparamétert kap**, és ugyanaz
  a bővülő ablakos keresztvalidáció választja (4 tisztított hajtás a tanító időszakon,
  a legnagyobb átlagos PR-AUC nyer, egyezésnél az egyszerűbb):

| modell | hiperparaméter | rács (egyszerűtől a bonyolultig) | rögzített |
|---|---|---|---|
| LightGBM | a fák száma | korai leállítás → medián (lezárt: 119) | minden más a v3 szerint |
| logisztikus regresszió | C (a regularizáció; kisebb = erősebb) | 0,001 · 0,01 · 0,1 · 1 | L2, max. 5000 iteráció |
| döntési fa | max_depth (mélység) | 3 · 4 · 5 · 6 · 8 · 10 · 12 · 15 · 20 | levél legalább 50 rendelés |
| random forest | min_samples_leaf (levélméret) | 100 · 30 · 10 · 5 · 2 | 300 fa, √jellemző/vágás |

## A keresztvalidáció eredménye (2026. okt. 9., CSAK a tanító időszak — a tesztet nem láttuk)

`python -m pipeline.reference_models`, mag 42, a hajtások átlaga:

| modell | választott beállítás | PR-AUC | ROC-AUC | Brier | ECE |
|---|---|---|---|---|---|
| LightGBM | 119 fa | 0,1258 | 0,6391 | 0,0672 | 0,0398 |
| logisztikus regresszió | C = 0,1 | 0,1241 | 0,6338 | 0,0680 | 0,0480 |
| random forest | min_samples_leaf = 10 | 0,1131 | 0,6240 | 0,0670 | 0,0376 |
| döntési fa | max_depth = 10 | 0,0934 | 0,5713 | 0,0692 | 0,0474 |

* **A logisztikus regresszió szinte eléri a LightGBM-et** (PR-AUC 0,124 vs 0,126). Hogy a
  különbség a teszten kimutatható-e, azt a páros összevetés dönti el.
* **A döntési fa a leggyengébb** — egyetlen fa ezen a zajos, ritka eseményen keveset fog meg.
* **A rácsot kibővítettük:** az első futásban a döntési fánál (10) és a random forestnél (10)
  a rács szélén volt a legjobb érték. A kibővített rácsban (fa: 12–20, erdő: 5, 2) mindkettő
  belül van, a választás nem változott. Ez a tanító időszakon történt, a teszt nélkül.
* Az ECE itt mind a négynél 0,04–0,05: a hajtások késési aránya erősen eltér (2,9% … 10,9%),
  ezt egyik modell sem tudhatja előre.

## Mi kerül a tesztre

* mind a négy modell: PR-AUC, ROC-AUC, Brier, ECE a teszten, 95%-os intervallummal (heti
  blokk-bootstrap, B = 2000, mag 20261008) — a LightGBM számai a lezárt futáséval egyeznek;
* **páros összevetés: LightGBM − referencia** ugyanazokon a húzott heteken (PR-AUC, ROC-AUC,
  Brier). Ha az intervallum a nullát is tartalmazza, a különbség ezen a teszten nem
  kimutatható — ezt is így közöljük;
* a random forest tanítási véletlene 5 maggal (a logisztikus regresszió determinisztikus);
* a validációs ablak pontbecslései (időn kívüli ellenőrzés).

A futás a teszt előtt megáll, ha a keresztvalidáció más beállítást választana, mint ami a
protokollban áll (`cv_valasztas_elvart`: C = 0,1 · mélység 10 · levélméret 10).

## Jóváhagyás és futtatás

1. A `docs/v3_referencia_protokoll.json`-ban: `"allapot": "jovahagyva"`, és a
   `"jovahagyas"` mezőben ki és mikor.
2. Commit + push — ez a futás előtti időbélyeg (a futás ellenőrzi).
3. `.\.venv-1\Scripts\python.exe -m pipeline.v3_reference` (kb. 5–10 perc).
4. Commit + push: `docs/v3_referencia_eredmeny.json` és `.md`.
