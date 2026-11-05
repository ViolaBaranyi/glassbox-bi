# A késés és a vevői értékelés együttjárása

Készült: 2026-11-04 17:21 UTC · forrás: `olist_order_reviews_dataset.csv` (SHA-256 `012b61c7593e34f5…`), tárház `warehouse.duckdb`.

Utólagos, leíró összevetés (a gazdasági fejezet táblázata). Együttjárás, nem ok: az értékelést a termék, az ár és a vevő várakozása is befolyásolja.

A tárház 96 470 kézbesített rendeléséből 95 824 rendelésnek van értékelése (96 353 értékelés; 525 rendelésnek több).

## Fő szabály: rendelésenként az értékelések átlaga

| Rendelés | Darab | Átlagos értékelés | 1–2 csillagos [95%] |
|---|---:|---:|---|
| Késett | 6 381 | 2,27 | 62,4% [61,2%; 63,5%] |
| Időben érkezett | 89 443 | 4,29 | 9,2% [9,0%; 9,4%] |

## Érzékenység: más összevonási szabályok

| Szabály | Késett: n; átlag; 1–2 csillagos | Időben: n; átlag; 1–2 csillagos |
|---|---|---|
| rendelésenként az értékelések átlaga (fő szabály) | 6 381; 2,27; 62,4% | 89 443; 4,29; 9,2% |
| értékelésenként, összevonás nélkül | 6 409; 2,27; 62,4% | 89 944; 4,29; 9,3% |
| rendelésenként a legkorábban létrehozott értékelés | 6 381; 2,27; 62,4% | 89 443; 4,29; 9,3% |
| rendelésenként a legkésőbb létrehozott értékelés | 6 381; 2,27; 62,4% | 89 443; 4,29; 9,3% |
| rendelésenként az átlag; alacsony, ha bármelyik értékelés legfeljebb 2 csillagos | 6 381; 2,27; 62,5% | 89 443; 4,29; 9,3% |
