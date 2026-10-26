# ROAR — a fontosnak mutatott tényezők kivétele és újratanítás

Készült: 2026-10-25T21:12:42+00:00 · kód-ujjlenyomat `6624522822431758…` · 747 mp. Az előre rögzített beállítások: döntési napló.

A rangsor a felület magyarázata a kontrollkar 200 teszt-rendelésén; a kivett tényező minden rendelésnél a tisztított tanító ablak mediánját / leggyakoribb értékét kapja, a tanításban és a tesztben is; a modell a lezárt beállításokkal újratanul (50623 sor), mérés az időbeli teszten (18603 rendelés). Véletlen készletek: 10 darab k-nként (mag 20261103), mind a négy modellnél ugyanazok. **Esés** = a lezárt modell értéke − az újratanítotté (pozitív: romlott).

Sejtések: R1 (a legfontosabbak kivétele > a véletlenek mediánja, ROC-AUC) 16/16; R2 (k ≤ 3: legalább 9 véletlen készletnél jobban ront) 10/12; R3 (a legkevésbé fontosak kivétele kevésbé ront) 16/16.

## LightGBM

Alap (lezárt): PR-AUC 0,098, ROC-AUC 0,764; az újratanítás kivétel nélkül a lezártat adja: igen. A rangsor eleje: vállalt szállítási idő, vevő állama, eladó átlagos feladási ideje, rendelés hónapja, termékkategória.

| k | kivett (legfontosabbak) | ROC-AUC esés | véletlen: medián (legkisebb – legnagyobb) | hány véletlennél ront jobban | a legkevésbé fontosak kivétele | PR-AUC esés | véletlen PR-AUC medián |
|---|---|---|---|---|---|---|---|
| 1 | vállalt szállítási idő | +0,163 | −0,002 (−0,006 – +0,005) | 10/10 | −0,001 | +0,050 | −0,002 |
| 2 | vállalt szállítási idő, vevő állama | +0,211 | −0,001 (−0,006 – +0,174) | 10/10 | −0,005 | +0,054 | −0,003 |
| 3 | vállalt szállítási idő, vevő állama, eladó átlagos feladási ideje | +0,183 | +0,003 (−0,006 – +0,210) | 9/10 | −0,009 | +0,051 | −0,002 |
| 5 | vállalt szállítási idő, vevő állama, eladó átlagos feladási ideje, rendelés hónapja, termékkategória | +0,243 | +0,018 (−0,007 – +0,246) | 9/10 | −0,003 | +0,057 | −0,005 |

## logisztikus regresszió

Alap (lezárt): PR-AUC 0,084, ROC-AUC 0,740; az újratanítás kivétel nélkül a lezártat adja: igen. A rangsor eleje: vállalt szállítási idő, rendelés hónapja, vevő állama, távolság, azonos állam.

| k | kivett (legfontosabbak) | ROC-AUC esés | véletlen: medián (legkisebb – legnagyobb) | hány véletlennél ront jobban | a legkevésbé fontosak kivétele | PR-AUC esés | véletlen PR-AUC medián |
|---|---|---|---|---|---|---|---|
| 1 | vállalt szállítási idő | +0,180 | +0,003 (−0,002 – +0,031) | 10/10 | +0,001 | +0,042 | +0,002 |
| 2 | vállalt szállítási idő, rendelés hónapja | +0,211 | +0,000 (−0,003 – +0,184) | 10/10 | +0,003 | +0,044 | +0,001 |
| 3 | vállalt szállítási idő, rendelés hónapja, vevő állama | +0,278 | +0,011 (−0,002 – +0,219) | 10/10 | +0,002 | +0,049 | +0,005 |
| 5 | vállalt szállítási idő, rendelés hónapja, vevő állama, távolság, azonos állam | +0,227 | +0,048 (+0,004 – +0,229) | 9/10 | +0,002 | +0,045 | +0,016 |

## döntési fa

Alap (lezárt): PR-AUC 0,061, ROC-AUC 0,597; az újratanítás kivétel nélkül a lezártat adja: igen. A rangsor eleje: vállalt szállítási idő, ünnep közeli időszak, távolság, eladó átlagos feladási ideje, vevő állama.

| k | kivett (legfontosabbak) | ROC-AUC esés | véletlen: medián (legkisebb – legnagyobb) | hány véletlennél ront jobban | a legkevésbé fontosak kivétele | PR-AUC esés | véletlen PR-AUC medián |
|---|---|---|---|---|---|---|---|
| 1 | vállalt szállítási idő | +0,077 | −0,016 (−0,058 – +0,031) | 10/10 | −0,001 | +0,022 | −0,002 |
| 2 | vállalt szállítási idő, ünnep közeli időszak | +0,025 | −0,002 (−0,084 – +0,077) | 7/10 | −0,001 | +0,016 | −0,001 |
| 3 | vállalt szállítási idő, ünnep közeli időszak, távolság | +0,069 | −0,035 (−0,084 – +0,081) | 8/10 | −0,001 | +0,020 | −0,005 |
| 5 | vállalt szállítási idő, ünnep közeli időszak, távolság, eladó átlagos feladási ideje, vevő állama | +0,031 | −0,021 (−0,112 – +0,111) | 7/10 | +0,000 | +0,014 | +0,002 |

## random forest

Alap (lezárt): PR-AUC 0,088, ROC-AUC 0,738; az újratanítás kivétel nélkül a lezártat adja: igen. A rangsor eleje: vállalt szállítási idő, vevő állama, rendelés hónapja, ünnep közeli időszak, eladó átlagos feladási ideje.

| k | kivett (legfontosabbak) | ROC-AUC esés | véletlen: medián (legkisebb – legnagyobb) | hány véletlennél ront jobban | a legkevésbé fontosak kivétele | PR-AUC esés | véletlen PR-AUC medián |
|---|---|---|---|---|---|---|---|
| 1 | vállalt szállítási idő | +0,201 | +0,001 (−0,020 – +0,018) | 10/10 | −0,001 | +0,045 | −0,002 |
| 2 | vállalt szállítási idő, vevő állama | +0,214 | +0,001 (−0,019 – +0,207) | 10/10 | −0,004 | +0,049 | +0,001 |
| 3 | vállalt szállítási idő, vevő állama, rendelés hónapja | +0,246 | +0,001 (−0,010 – +0,223) | 10/10 | +0,009 | +0,050 | −0,000 |
| 5 | vállalt szállítási idő, vevő állama, rendelés hónapja, ünnep közeli időszak, eladó átlagos feladási ideje | +0,276 | +0,021 (−0,033 – +0,248) | 10/10 | +0,004 | +0,053 | +0,001 |

## Olvasat

Ha a magyarázat szerinti kivétel alig ront, annak két oka lehet: a magyarázat túlbecsüli a tényezőt, vagy a tényező információja más tényezőkben is megvan, és az újratanított modell onnan pótolja (Hooker és mtsai is ezt a korlátot írják). A ROAR ezért a K2 törlési görbéjét és beültetett jelét kiegészíti, nem helyettesíti.
