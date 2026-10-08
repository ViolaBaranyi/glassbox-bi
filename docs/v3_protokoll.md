# Lezárt v3 alapfutás — protokoll

**Állapot: TERVEZET** — két döntés hiányzik (lent). Amíg a `docs/v3_protokoll.json`
nincs jóváhagyva, a `python -m pipeline.v3_baseline` nem indul el.

## Miért kell lezárt futás?

A teszthalmazt (2018. június–augusztus) eddig sokszor láttuk; a döntési napló
minden alkalmat rögzít. Ha a következő döntéseket is a teszt eredménye után
hoznánk, a végső szám a „választások kertjében" (forking paths) születne: nem
lehetne tudni, mennyi benne a valódi teljesítmény, és mennyi a teszthez igazítás.

Ezért a végleges mérés előtt **minden döntés írásban rögzül**, és a futás után nem
változik. A futás a protokollfájl ujjlenyomatát (SHA256) is elmenti, és a commit
időbélyegzi — utólag ellenőrizhető, melyik protokoll szerint mért. A teszthez a
futás egyszer nyúl; ismételt futás csak `--ismetles` kapcsolóval megy, és az
eredményben látszik.

## Mi van rögzítve

| | |
|---|---|
| Adat | valódi Olist-adat, A kohorsz: csak a kézbesített rendelések (v2) |
| Ablakok | tanító: 2018. márc. 1. előtt · validáció: márc.–máj. · teszt: jún.–aug. (v2, a rendelés időpontja szerint) |
| Jellemzők | 22 (`features.FEATURES`) |
| Fa-szám | bővülő ablakos CV a tanító időszakon: 4 hajtás × 3 mag (1, 2, 3), korai leállítás PR-AUC-ra (150 kör) → `N_fix = max(50, medián)` |
| Végső modell | a tanító ablakon, pontosan N_fix fával, mag 42; súlyozás nincs, utólagos kalibrátor nincs, learning_rate 0,05 |
| Validáció | időn kívüli ellenőrzés — semmit nem befolyásol |
| Fő mutató | PR-AUC; mellette ROC-AUC, Brier, ECE (két sávolással) |
| Bizonytalanság | heti blokk-bootstrap (ISO-hét), B = 2000, mag 20261008, percentilis 95% |
| Páros összevetés | a modell és a tanító időszak arányát mondó konstans előrejelzés (PR-AUC, Brier) |
| Tanítási véletlen | ugyanez öt maggal (1–5), átlag ± szórás, a bootstrap-intervallumtól külön |

A futás ellenőrzi, hogy a protokoll pontosan azt írja-e le, amit a kód csinál (hajtások,
magok, alsó korlát, korai leállítás, ablakok, adatforrás). Ha bármi eltér, a modellhez
sem nyúl.

## Nyitott döntések

### 1. Címke-tisztítás — javaslat: IGEN

**A probléma (okt. 8-án találtuk, a teszt nélkül).** A jellemzőkre már érvényes a
point-in-time szabály: csak a leadáskor ismert információ. A tanító *címkékre* ez
eddig nem volt kimondva. A 2018. március 1-jei vágásnál:

* 6 694 tanító rendelés (11,7%) vállalt határideje március 1. vagy később volt;
* ebből 3 539 (a tanító sorok 6,2%-a) március 1-jéig meg sem érkezett — a kimenetük
  akkor még ismeretlen volt, és **26,6%-uk késett** (a márciusi válság).

Egy március 1-jén betanított modell ezt nem tudhatta volna. Ha mégis tanítunk rajta,
a modell a vágás utáni szállítási viszonyokból is tanul.

**A bizonyíték (csak a tanító időszakon, bővülő ablakos CV, 3 mag átlaga, azonos fa-számmal):**

| hajtás (értékelő szakasz) | késés | PR-AUC tisztítás nélkül | PR-AUC tisztítással | ROC-AUC nélküle | ROC-AUC vele |
|---|---|---|---|---|---|
| 1. 2017. jún. 4. – szept. 4. | 2,9% | 0,039–0,040 | 0,042–0,044 | 0,596 | 0,606–0,616 |
| 2. 2017. szept. 5. – nov. 21. | 5,2% | 0,099 | 0,102 | 0,650–0,653 | 0,649–0,652 |
| 3. 2017. nov. 22. – 2018. jan. 10. | 10,0% | **0,244–0,246** | **0,167–0,171** | **0,731–0,732** | **0,653–0,656** |
| 4. 2018. jan. 11. – febr. 28. | 10,9% | 0,214–0,215 | 0,194–0,198 | 0,685 | 0,662–0,668 |

(a sávok: 67 és 119 fával mérve.) A nyugodt hajtásokban (1–2) nincs különbség. A
zavarokkal kezdődő hajtásokban (3: Black Friday és a karácsonyi csúcs; 4: a 2018 eleji
torlódás) a tisztítás nélküli becslés optimista: a még ismeretlen címkék épp a zavar
kezdetét árulták el. Ez a különbség élesben nem állna rendelkezésre.

**A szabály:** minden vágásnál csak azok a tanító sorok maradnak, amelyeknek a vállalt
határideje a vágás előtt lejárt (`split.settled_before`). Ezeknek a sorsa biztosan eldőlt:
vagy megjöttek időben, vagy késtek. A határidő a leadáskor ismert, ezért a szűrés **a
kimenettől független** — nem torzít. (A „már kézbesítettek maradnak" szabály torzítana:
a vágás közelében csak a gyorsan, tehát időben megérkezettek maradnának bent.)

**Ára:** a tanító ablakból 6 694 sor (11,7%) kimarad — a legfrissebb hetek. A fa-szám
a tisztítással 119 (medián 118,5), nélküle 67 (medián 66,5).

**Eltérés a v2-től:** a v2 a vágást csak a rendelés időpontjával definiálta. A tisztítás
ugyanannak a point-in-time elvnek a következetes alkalmazása, amit a jellemzőknél a
témavezetővel már egyeztettünk — de mivel a tanító halmazt érinti, **témavezetői
jóváhagyás javasolt**.

### 2. A fa-szám alsó korlátja: 50 — megerősítendő

A korlát az összeomló korai leállítás ellen véd (egy ablációs futásban egyszer 2 fánál
állt meg; a tisztított CV 1. hajtásában 3–6 fánál). A valódi adaton egyik változatban
sem ez dönt (medián 66,5, ill. 118,5). Ha a témavezető mást javasol, **a futás előtt**
kell átírni: a futás utáni módosítás új „elágazás" lenne.

## Jóváhagyás és futtatás

1. A `docs/v3_protokoll.json`-ban:
   * `"allapot": "jovahagyva"`,
   * `"jovahagyas": {"ki": "…", "mikor": "2026-…", "megjegyzes": "…"}`,
   * `"cimke_tisztitas": true` (vagy `false`),
   * ha kell, `"modellvalasztas"` → `"n_min"` — és a kódban az `N_MIN` is (a futás
     ellenőrzi, hogy egyeznek).
2. Commit („v3 protokoll jóváhagyva") — ez a futás ELŐTTI időbélyeg.
3. `python -m pipeline.v3_baseline` (néhány perc; a bootstrap a leghosszabb).
4. Commit: `docs/v3_lezart_eredmeny.json` és `docs/v3_lezart_eredmeny.md`.
5. Utána a demó alapbeállítása a protokollra vált (`--trees cv`, és a döntés szerinti
   címke-tisztítás), és erre a modellre épül a SHAP-réteg (M3).

## Mi NEM része a lezárt futásnak

* a B kohorsz (érzékenységi jelentés: `python -m pipeline.cohort_report`);
* a hiperparaméter-hangolás és a referencia-modellek (logisztikus regresszió, döntési
  fa, random forest) — ezek külön, saját protokollal jönnek, a keresztvalidáción
  választva, nem a teszten;
* újratanítás a tanító + validációs ablakon — elvetve: a v2 ablakai változatlanok
  maradnak, és a validáció így tiszta, időn kívüli ellenőrzés.
