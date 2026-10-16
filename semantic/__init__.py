"""
Szemantikus réteg (M1): a metrikakatalógus, a kérdés-specifikáció (QuerySpec), a
KAPU ① és a determinisztikus SQL-építő.

A természetes nyelvű kérdésből (később a nyelvi modell, most a felület kérdésépítője)
egy QuerySpec lesz; a KAPU ① a katalógushoz és az adatból generált fehérlistához méri;
csak elfogadott specifikációból épül SQL, és csak ellenőrzött SQL fut le a tárházon.
Ami nincs a katalógusban, arra indokolt elutasítás jön — szám nélkül.
"""
