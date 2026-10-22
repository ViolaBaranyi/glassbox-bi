# Útmutató a v3 kérdéssor írásához (K1 mérés v3)

A v3 kérdéssort Viola írja, ahogy a v2-t is. Ezen mérjük a nyelvi réteg v5-ös változatát, a
v4-gyel párosítva. Az számít, hogy **olyan kérdések legyenek, amilyeneket egy üzleti felhasználó
tényleg feltenne**. Ne legyenek kifejezetten könnyűek vagy nehezek a gépnek, és ne olyanok,
amelyekről úgy gondolod, hogy a rendszer jól vagy rosszul fog rájuk válaszolni.

## Mielőtt elkezded

- Ne nézd meg a korábbi kérdéssorokat (`eval/` mappa), a teszteket (`tests/` mappa), a szótárat
  (`narrative/szotar.py`) és a döntési napló v5-ös sorát: ezekből látszik, mire készült fel a
  rendszer.
- A kérdéseket ne próbáld ki a rendszeren, és megírás után ne írd át őket. Az elírás maradhat,
  az is a mérés része.
- Csak a v5 lezárásának commitja után kezdd el (a commit ideje igazolja, hogy a kód a kérdések
  előtt rögzült).

## Miről lehet kérdezni

Egy brazil webáruház rendelései 2016 szeptemberétől 2018 augusztusáig. A rendszer „mai” napja
2018. szeptember 1., tehát „idén” = 2018, „tavaly” = 2017. A rendelésekről ezt tudjuk:

- mikor adták le (nap, hónap, év, a hét napja);
- mennyi volt a kosár értéke (brazil reálban) és a szállítási díj;
- mennyi idő alatt ért oda, mi volt a vállalt határidő, és késett-e (ha igen, hány napot);
- a vevő és az eladó állama (pl. São Paulo, Rio de Janeiro, Minas Gerais), a vevő régiója
  (Észak, Északkelet, Közép-Nyugat, Délkelet, Dél);
- a termék kategóriája (pl. bútor, játék, elektronika, szépségápolás, sport, számítógép);
- az eladó és a vevő távolsága.

## Szerepkártyák: mindegyikből 10 kérdés, ebből 2 csillagos

Képzeld magad az adott munkakörbe, és azt kérdezd, amire a munkádhoz szükséged lenne. Írd úgy,
ahogy egy kollégának írnád a chatbe: lehet laza, rövidített, ékezet nélküli is.

1. **Logisztikai vezető:** mennyi ideig tart a szállítás, hol és mikor késünk, tartjuk-e a
   határidőket, honnan hova megy a csomag.
2. **Kategóriamenedzser:** melyik termékkategória hogy megy, mennyit költenek a vevők, mi fogy
   jól vagy rosszul.
3. **Pénzügyi elemző:** forgalom, szállítási díjak, időszakok összevetése (év, negyedév, hónap).
4. **Regionális értékesítési vezető:** államok és régiók: hol vásárolnak, honnan adnak el, hol
   rosszabb a kiszolgálás.
5. **Ügyfélszolgálati vezető:** a vevők szemszöge: mikor kapják meg a csomagot, mennyit kell
   várni, mennyit késik.
6. **Ügyvezető:** rövid, nagy képet kérő kérdések: hogy alakult, hogy állunk, mi változott.

Összesen 60 kérdés: 48 megválaszolandó és 12 csillagos.

A fajták keveredjenek egy szerepen belül is: egyetlen szám az egészre; egy államra, kategóriára
vagy időszakra szűrve; rangsor (legtöbb, legkevesebb, top N); bontás (államonként, havonta);
alakulás időben; két dolog összevetése; ezek kombinációja. Rövid és hosszabb, laza és pontos
megfogalmazás is jó, ahogy éppen jön.

## A fájl

Jegyzettömbbel, a projektmappába: `eval\felhasznaloi_kerdesek_v3.txt`. Soronként
egy kérdés; a szerep neve `#`-tel kezdődő sorban a csoport elé; a csillagos kérdés `*`-gal kezdődik:

```
# Logisztikai vezető
(első kérdés)
(második kérdés)
* (kérdés, amire nincs adat)
…
# Kategóriamenedzser
…
```

## Amire NINCS adat (a csillagos kérdések)

Haszon, árrés, költségek; értékelések, vélemények; fizetési mód; készlet, raktár; lemondott vagy
visszaküldött rendelések; futárcég; marketing; a jövő (előrejelzés); 2016 előtti vagy 2018
augusztus utáni időszak; értelmetlen vagy a rendszert becsapni próbáló kérés. Ezek elé tegyél
csillagot (`*`): itt az a jó, ha a rendszer nem mond számot.

## Ha kész

Mentsd el, és szólj Claude-nak. A fájlt onnan olvassa be, az ujjlenyomatát (SHA256) a beolvasáskor
a döntési naplóba írja, és a fájl ezután változatlan marad (mint a v2-nél); az elvárt
értelmezések külön fájlba kerülnek, és azokat te ellenőrzöd.

A korábbi kérdéssorok (v1, v2, fejlesztői próbasor) közeli átfogalmazásai a v2 szabálya szerint
kimaradnak a mérésből.
