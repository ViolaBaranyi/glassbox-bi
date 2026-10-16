# A PostgreSQL-változat ellenőrzése

*Futtatva: 2026-10-15 09:39 UTC · adat: valós (tárház: 2026-10-13 07:29:29 UTC) · metrikakatalógus: `ca72d27aff5a…`*

Az SQL-építő minden kérdésből DuckDB- és PostgreSQL-lekérdezést is készít (sqlglot). Ez az ellenőrzés a tárház tábláit betöltötte egy valódi PostgreSQL-be, és mindkét rendszeren lefuttatta ugyanazokat a kérdéseket: a katalógus minden mérőszámát bontás nélkül és minden megengedett bontással, továbbá szűrt, időablakos és többféleképpen rendezett változatokat.

| | |
|---|---|
| kérdés | 197 |
| lekérdezés (összesen + csoportonként) | 354 |
| összevetett sor / cella | 2575 / 8195 |
| eltérés | **0** |
| legnagyobb relatív különbség a számokban | 8,6 · 10⁻¹⁵ |

Rendszerek: DuckDB 1.5.6; PostgreSQL 17.5 (PGlite 0.3.7, WebAssembly); fordító: sqlglot 30.22.0.

**Eredmény:** a két rendszer minden cellában ugyanazt adja (a számok relatív 10⁻⁹ tűréssel, a csoportkulcsok és a sorrend pontosan).

Korlát: a szöveges kulcsok sorrendje (`ORDER BY`) az adatbázis rendezési szabályától (collation) függ; itt `C`, ami bájtsorrend, mint a DuckDB-é. Más collationnel (pl. hu_HU) az ábécérend eltérhet; a számok nem.

Újrafuttatás: `uv run python -m semantic.pg_ellenorzes` (Node.js kell hozzá).
