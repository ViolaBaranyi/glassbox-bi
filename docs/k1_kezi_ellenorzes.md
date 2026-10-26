# A K1 kézi ellenőrzése — összesítés

A vak kézi minták kiértékelése (`tools/kezi_minta.py osszesit`). A minta rétegzett: ágonként (legfeljebb) 20 olyan szöveg, amelyet a 2. kapu nem jelölt meg, és 10, amelyet megjelölt. **Pontosság**: a megjelöltekből mennyi valóban hibás; **kihagyás**: a meg nem jelöltekből mennyi mégis az (95%-os Wilson-intervallum). **K1 korrigálva** = megjelölt arány × pontosság + (1 − megjelölt arány) × kihagyás. A fő ágon a megjelölt szöveg helyett a sablon jut el a felhasználóhoz, ezért ott a **felhasználóhoz eljutó, a kapu által nem látott hiba** becslése (1 − megjelölt arány) × kihagyás; ez utólag (a minták egy részének kiértékelése után) meghatározott, származtatott mennyiség, nem a protokoll fő mutatója.

## 20261016_1426_qwen3.5-4b — qwen3.5:4b, v3, eval/meresi_kerdessor.toml (130 kérdés)

| ág | megjelölt arány | pontosság | kihagyás | K1 korrigálva | eljut, nem látott |
|---|---|---|---|---|---|
| fő ág (jelölők) | 29,0% | 9/10 [59,6%; 98,2%] | 4/20 [8,1%; 41,6%] | 40,3% | 14,2% [5,7%; 29,6%] |
| kontrollág (szabad) | 29,7% | 6/10 [31,3%; 83,2%] | 6/20 [14,5%; 51,9%] | 38,9% | — (nincs kapu) |

## 20261019_0910_qwen3.5-2b — qwen3.5:2b, v3, eval/meresi_kerdessor.toml (130 kérdés)

| ág | megjelölt arány | pontosság | kihagyás | K1 korrigálva | eljut, nem látott |
|---|---|---|---|---|---|
| fő ág (jelölők) | 39,7% | 6/10 [31,3%; 83,2%] | 6/20 [14,5%; 51,9%] | 41,9% | 18,1% [8,8%; 31,3%] |
| kontrollág (szabad) | 45,6% | 3/10 [10,8%; 60,3%] | 12/20 [38,7%; 78,1%] | 46,3% | — (nincs kapu) |

## 20261020_1300_qwen3.5-4b — qwen3.5:4b, v4, eval/meresi_kerdessor_v2.toml (56 kérdés)

| ág | megjelölt arány | pontosság | kihagyás | K1 korrigálva | eljut, nem látott |
|---|---|---|---|---|---|
| fő ág (jelölők) | 36,4% | 8/10 [49,0%; 94,3%] | 3/20 [5,2%; 36,0%] | 38,6% | 9,5% [3,3%; 22,9%] |
| kontrollág (szabad) | 36,4% | 5/10 [23,7%; 76,3%] | 4/20 [8,1%; 41,6%] | 30,9% | — (nincs kapu) |

## 20261020_1404_qwen3.5-2b — qwen3.5:2b, v4, eval/meresi_kerdessor_v2.toml (56 kérdés)

| ág | megjelölt arány | pontosság | kihagyás | K1 korrigálva | eljut, nem látott |
|---|---|---|---|---|---|
| fő ág (jelölők) | 60,0% | 9/10 [59,6%; 98,2%] | 3/12 [8,9%; 53,2%] | 64,0% | 10,0% [3,6%; 21,3%] |
| kontrollág (szabad) | 53,3% | 8/10 [49,0%; 94,3%] | 6/14 [21,4%; 67,4%] | 62,7% | — (nincs kapu) |

## 20261022_1902_qwen3.5-4b — qwen3.5:4b, v5, eval/meresi_kerdessor_v3.toml (50 kérdés)

**Kitöltetlen sor: 59** — a becslés még nem végleges.

| ág | megjelölt arány | pontosság | kihagyás | K1 korrigálva | eljut, nem látott |
|---|---|---|---|---|---|
| fő ág (jelölők) | 37,8% | 0/0 — | 0/0 — | — | — (nincs kapu) |
| kontrollág (szabad) | 24,3% | 0/0 — | 0/0 — | — | — (nincs kapu) |
