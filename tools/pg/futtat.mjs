// A PostgreSQL-ellenőrzés futtatója (a semantic/pg_ellenorzes.py hívja, nem kézzel).
//
//   node futtat.mjs <munkamappa>
//
// A munkamappában: ddl.json (CREATE TABLE-ök), <tábla>.csv, esetek.json (a PostgreSQL-SQL-ek).
// Ide írja: pg_eredmeny.json (a lekérdezések eredménye) és pg_info.json (verzió, collation).
// A PGlite a PostgreSQL WebAssemblyre fordítva: szerver és telepítés nélkül, memóriában fut.
import { PGlite } from "@electric-sql/pglite";
import fs from "node:fs";
import path from "node:path";

const dir = process.argv[2];
const read = (name) => JSON.parse(fs.readFileSync(path.join(dir, name), "utf8"));
const pkg = JSON.parse(fs.readFileSync(new URL("./node_modules/@electric-sql/pglite/package.json", import.meta.url), "utf8"));

const db = new PGlite();
const info = (await db.query(
  "SELECT version() AS v, datcollate AS c FROM pg_database WHERE datname = current_database()")).rows[0];
fs.writeFileSync(path.join(dir, "pg_info.json"), JSON.stringify({
  postgresql: `${info.v.split(" on ")[0]} (PGlite ${pkg.version}, WebAssembly)`,
  collation: info.c,
}));

for (const stmt of read("ddl.json")) await db.exec(stmt);
for (const table of ["fact_orders", "dim_customer", "dim_seller", "dim_product"]) {
  const blob = new Blob([fs.readFileSync(path.join(dir, `${table}.csv`))]);
  await db.query(`COPY ${table} FROM '/dev/blob' WITH (FORMAT csv, HEADER true)`, [], { blob });
}

const plain = (v) => (v instanceof Date ? v.toISOString().slice(0, 10) : typeof v === "bigint" ? Number(v) : v);
const out = [];
for (const c of read("esetek.json")) {
  const res = {};
  for (const [part, sql] of Object.entries(c.pg)) {
    try {
      const r = await db.query(sql, [], { rowMode: "array" });
      res[part] = { oszlopok: r.fields.map((f) => f.name), sorok: r.rows.map((row) => row.map(plain)) };
    } catch (e) {
      res[part] = { hiba: String(e.message || e) };
    }
  }
  out.push(res);
  if (out.length % 50 === 0) process.stdout.write(`    ${out.length} kérdés kész\n`);
}
fs.writeFileSync(path.join(dir, "pg_eredmeny.json"), JSON.stringify(out));
await db.close();
