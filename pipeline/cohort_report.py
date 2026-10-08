"""
Érzékenységi jelentés: mennyire függ a késési arány attól, kiket hagyunk ki?

A fő elemzés (v2, a témavezetővel egyeztetve) CSAK a kézbesített rendelésekkel
számol: máshol nincs címke. A kizárt rendelések között viszont vannak olyanok,
amelyek a megfigyelési zárónapig nem érkeztek meg, pedig a vállalt határidejük
már lejárt (státusz: feladva, számlázva, feldolgozás alatt…). Két változat:

    A — fő elemzés:      csak a kézbesített rendelések
    B — érzékenységi:    A + a lejárt határidejű, még úton lévő rendelések
                         KÉSETTKÉNT (a lemondott / nem elérhető rendelés más
                         kimenet, egyik változat sem számolja)

A jelentés ablakonként (tanító / validációs / teszt) és havonta adja meg a
késési arányt mindkét változatra, 95%-os Wilson-intervallummal, valamint a
2018-as brazil kamionos-sztrájk körüli időszakot.

Futtatás:
    python -m pipeline.cohort_report
Kimenet: a képernyő + artifacts/kohorsz_erzekenyseg.json
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

from data.db import DB_PATH, WarehouseUnavailable, connect, use_utf8_console
from pipeline.split import temporal_split

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "artifacts" / "kohorsz_erzekenyseg.json"

# A 2018-as brazil kamionos-sztrájk 2018. május 21-én kezdődött és kb. június
# 1-ig tartott; a szállítások csak utána álltak helyre. Az érintett rendeléseket
# az ÍGÉRT kézbesítési nap alapján fogjuk meg (a sztrájk alatt kellett volna
# megérkezniük): május 21. – június 10.
SZTRAJK_IGERT = (pd.Timestamp("2018-05-21"), pd.Timestamp("2018-06-10"))


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """95%-os Wilson-intervallum egy arányra (kis mintán is jól viselkedik)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    lo = 0.0 if k == 0 else max(0.0, c - h)   # a határok pontosan 0 / 1, nem 1e-18
    hi = 1.0 if k == n else min(1.0, c + h)
    return (lo, hi)


def _rate(df: pd.DataFrame) -> dict:
    n, k = len(df), int(df["kesett"].sum())
    lo, hi = wilson(k, n)
    return {"n": n, "kesett": k, "arany": round(k / n, 4) if n else None,
            "ci95": [round(lo, 4), round(hi, 4)]}


def load(con) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    a = con.execute("""
        SELECT order_key, rendeles_idopont, vallalt_hatarido, kesett
        FROM fact_orders""").df()
    extra = con.execute("""
        SELECT order_key, rendeles_idopont, vallalt_hatarido, statusz
        FROM kizart_rendelesek
        WHERE kesett_erzekenysegi""").df()
    meta = con.execute("SELECT * FROM meta_build").df().iloc[0].to_dict()
    for d in (a, extra):
        d["rendeles_idopont"] = pd.to_datetime(d["rendeles_idopont"])
        d["vallalt_hatarido"] = pd.to_datetime(d["vallalt_hatarido"])
    a["kesett"] = a["kesett"].astype(bool)
    extra["kesett"] = True
    b = pd.concat([a, extra[a.columns]], ignore_index=True)
    return a, b, meta


def report(db_path: Path = DB_PATH, verbose: bool = True, write: bool = True) -> dict:
    con = connect(db_path, read_only=True)
    a, b, meta = load(con)
    con.close()

    sp = temporal_split(a["rendeles_idopont"])     # ugyanaz a vágás, mint a betanításnál

    def window(ts):
        return pd.Series(pd.NA, index=ts.index, dtype="object").mask(
            ts < sp.train_end, "tanito").mask(
            (ts >= sp.train_end) & (ts < sp.valid_end), "validacios").mask(
            ts >= sp.valid_end, "teszt")

    out = {
        "adatforras": str(meta["adatforras"]),
        "megfigyelesi_zarnap": str(meta.get("megfigyelesi_zarnap", "")),
        "szetvagas": {"tanito_vege": str(sp.train_end.date()),
                      "validacio_vege": str(sp.valid_end.date())},
        "hozzaadott_rendelesek_B": int(len(b) - len(a)),
        "ablakok": {},
        "havi": [],
        "sztrajk": {},
    }
    for name in ["tanito", "validacios", "teszt"]:
        ra = _rate(a[window(a["rendeles_idopont"]) == name])
        rb = _rate(b[window(b["rendeles_idopont"]) == name])
        out["ablakok"][name] = {"A": ra, "B": rb}

    for kohorsz, df in [("A", a), ("B", b)]:
        g = df.assign(honap=df["rendeles_idopont"].dt.to_period("M").astype(str))
        for honap, part in g.groupby("honap"):
            out["havi"].append({"kohorsz": kohorsz, "honap": honap, **_rate(part)})

    s0, s1 = SZTRAJK_IGERT
    for kohorsz, df in [("A", a), ("B", b)]:
        in_strike = df["vallalt_hatarido"].between(s0, s1)
        out["sztrajk"][kohorsz] = {
            "igert_ablak": [str(s0.date()), str(s1.date())],
            "ablakban": _rate(df[in_strike]),
        }

    if verbose:
        print(f"Adatforrás: {out['adatforras'].upper()} · megfigyelési zárónap: "
              f"{out['megfigyelesi_zarnap'][:16]}")
        print(f"B változat: +{out['hozzaadott_rendelesek_B']:,} lejárt határidejű, "
              "még úton lévő rendelés késettként\n")
        print(f"  {'ablak':<12}{'A: n':>9}{'A: arány':>10}{'95% CI':>17}"
              f"{'B: n':>9}{'B: arány':>10}{'95% CI':>17}")
        for name, r in out["ablakok"].items():
            ra, rb = r["A"], r["B"]
            print(f"  {name:<12}{ra['n']:>9,}{ra['arany']:>10.2%}"
                  f"{'[' + format(ra['ci95'][0], '.2%') + '; ' + format(ra['ci95'][1], '.2%') + ']':>17}"
                  f"{rb['n']:>9,}{rb['arany']:>10.2%}"
                  f"{'[' + format(rb['ci95'][0], '.2%') + '; ' + format(rb['ci95'][1], '.2%') + ']':>17}")
        print("\n  havi késési arány (rendelési dátum szerint), A / B:")
        hav = pd.DataFrame(out["havi"]).pivot(index="honap", columns="kohorsz", values="arany")
        nn = pd.DataFrame(out["havi"]).pivot(index="honap", columns="kohorsz", values="n")
        for honap in hav.index:
            if nn.loc[honap, "A"] >= 500:
                print(f"    {honap}   {hav.loc[honap, 'A']:>7.2%}   {hav.loc[honap, 'B']:>7.2%}"
                      f"   (n = {int(nn.loc[honap, 'A']):,})")
        sa, sb = out["sztrajk"]["A"]["ablakban"], out["sztrajk"]["B"]["ablakban"]
        print(f"\n  sztrájk-ablak (ígért nap {s0.date()} – {s1.date()}): "
              f"A {sa['arany']:.2%} (n = {sa['n']:,}) · B {sb['arany']:.2%} (n = {sb['n']:,})")

    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        if verbose:
            print(f"\nMentve: {OUT}")
    return out


def main() -> None:
    use_utf8_console()
    try:
        report()
    except WarehouseUnavailable as exc:
        print(f"\nHIBA:\n{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
