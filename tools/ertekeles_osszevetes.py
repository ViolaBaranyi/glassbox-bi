"""
A késés és a vevői értékelés együttjárása (a gazdasági fejezet táblázata) — utólagos, leíró.

A tárház kézbesített rendeléseit (`fact_orders`, a `kesett` címkével) összeveti az Olist
értékelési fájljával (`olist_order_reviews_dataset.csv`). Egy rendeléshez több értékelés is
tartozhat (a valódi adatban néhány száz rendelésnél), ezért a fő szabály: rendelésenként az értékelések
átlaga; „alacsony” az 1–2 csillagos, vagyis ahol az átlag legfeljebb 2. Érzékenységként a
többi ésszerű szabály is (értékelésenként; a legelső, illetve a legutolsó értékelés; bármelyik
értékelés legfeljebb 2 csillagos). Az értékelés a késés után keletkezik: jellemzőként tiltott,
csak a gazdasági értelmezés adata. Együttjárás, nem ok.

    uv run python tools/ertekeles_osszevetes.py      # → docs/ertekeles_osszevetes.json és .md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.db import DB_PATH, connect, use_utf8_console  # noqa: E402

REVIEWS = ROOT / "data" / "raw" / "olist_order_reviews_dataset.csv"
OUT = ROOT / "docs" / "ertekeles_osszevetes.json"
LOW = 2  # „alacsony”: legfeljebb ennyi csillag
RULES = {
    "atlag": "rendelésenként az értékelések átlaga (fő szabály)",
    "ertekelesenkent": "értékelésenként, összevonás nélkül",
    "elso": "rendelésenként a legkorábban létrehozott értékelés",
    "utolso": "rendelésenként a legkésőbb létrehozott értékelés",
    "barmelyik": "rendelésenként az átlag; alacsony, ha bármelyik értékelés legfeljebb 2 csillagos",
}


def wilson(k: int, n: int, z: float = 1.959964) -> list[float]:
    if n == 0:
        return [float("nan"), float("nan")]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [c - h, c + h]


def _per_rule(m: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Rendelésenként (vagy értékelésenként) egy sor: kesett, pont, alacsony."""
    if rule == "ertekelesenkent":
        d = m[["kesett", "review_score"]].rename(columns={"review_score": "pont"})
        d["alacsony"] = d["pont"] <= LOW
        return d
    if rule in ("elso", "utolso"):
        s = m.sort_values(["review_creation_date", "review_id"], kind="mergesort")
        g = s.groupby("order_key", sort=False)
        d = (g.head(1) if rule == "elso" else g.tail(1))[["kesett", "review_score"]]
        d = d.rename(columns={"review_score": "pont"})
        d["alacsony"] = d["pont"] <= LOW
        return d
    g = m.groupby("order_key")
    d = pd.DataFrame({"kesett": g["kesett"].first(), "pont": g["review_score"].mean()})
    d["alacsony"] = g["review_score"].min() <= LOW if rule == "barmelyik" else d["pont"] <= LOW
    return d


def compare(orders: pd.DataFrame, reviews: pd.DataFrame) -> dict:
    """orders: order_key, kesett; reviews: review_id, order_id, review_score, review_creation_date."""
    m = reviews.merge(orders, left_on="order_id", right_on="order_key", how="inner")
    res = {
        "rendelesek_a_tarhazban": int(len(orders)),
        "ertekelesek_a_tarhaz_rendelesein": int(len(m)),
        "ertekelt_rendelesek": int(m["order_key"].nunique()),
        "tobb_ertekeles": int((m.groupby("order_key").size() > 1).sum()),
        "szabalyok": {},
    }
    for rule, desc in RULES.items():
        d = _per_rule(m, rule)
        out = {"leiras": desc}
        for key, flag in (("kesett", True), ("idoben", False)):
            x = d[d["kesett"] == flag]
            k, n = int(x["alacsony"].sum()), int(len(x))
            out[key] = {"n": n, "atlag": float(x["pont"].mean()), "alacsony_k": k,
                        "alacsony_arany": k / n if n else float("nan"), "ci95": wilson(k, n)}
        res["szabalyok"][rule] = out
    return res


def _pct(x: float) -> str:
    return f"{100 * x:.1f}".replace(".", ",") + "%"


def _num(x: float, d: int = 2) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def _int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def report(res: dict) -> str:
    f = res["szabalyok"]["atlag"]
    lines = [
        "# A késés és a vevői értékelés együttjárása",
        "",
        f"Készült: {res['keszult']} · forrás: `{res['forras']['ertekelesek']}` "
        f"(SHA-256 `{res['forras']['sha256'][:16]}…`), tárház `{res['forras']['tarhaz']}`.",
        "",
        "Utólagos, leíró összevetés (a gazdasági fejezet táblázata). Együttjárás, nem ok: az "
        "értékelést a termék, az ár és a vevő várakozása is befolyásolja.",
        "",
        f"A tárház {_int(res['rendelesek_a_tarhazban'])} kézbesített rendeléséből "
        f"{_int(res['ertekelt_rendelesek'])} rendelésnek van értékelése "
        f"({_int(res['ertekelesek_a_tarhaz_rendelesein'])} értékelés; {res['tobb_ertekeles']} rendelésnek több).",
        "",
        "## Fő szabály: rendelésenként az értékelések átlaga",
        "",
        "| Rendelés | Darab | Átlagos értékelés | 1–2 csillagos [95%] |",
        "|---|---:|---:|---|",
    ]
    for key, name in (("kesett", "Késett"), ("idoben", "Időben érkezett")):
        r = f[key]
        lines.append(f"| {name} | {_int(r['n'])} | {_num(r['atlag'])} | {_pct(r['alacsony_arany'])} "
                     f"[{_pct(r['ci95'][0])}; {_pct(r['ci95'][1])}] |")
    lines += ["", "## Érzékenység: más összevonási szabályok", "",
              "| Szabály | Késett: n; átlag; 1–2 csillagos | Időben: n; átlag; 1–2 csillagos |", "|---|---|---|"]
    for rule, r in res["szabalyok"].items():
        a, b = r["kesett"], r["idoben"]
        lines.append(f"| {r['leiras']} | {_int(a['n'])}; {_num(a['atlag'])}; {_pct(a['alacsony_arany'])} | "
                     f"{_int(b['n'])}; {_num(b['atlag'])}; {_pct(b['alacsony_arany'])} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="A késés és a vevői értékelés együttjárása (leíró).")
    ap.add_argument("--tarhaz", type=Path, default=DB_PATH)
    ap.add_argument("--ertekelesek", type=Path, default=REVIEWS)
    ap.add_argument("--kimenet", type=Path, default=OUT)
    a = ap.parse_args(argv)
    con = connect(a.tarhaz)
    try:
        orders = con.execute("SELECT order_key, kesett FROM fact_orders").df()
        built = con.execute("SELECT * FROM meta_build").df()
    finally:
        con.close()
    reviews = pd.read_csv(a.ertekelesek, usecols=["review_id", "order_id", "review_score", "review_creation_date"])
    res = compare(orders, reviews)
    res["keszult"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    res["forras"] = {
        "ertekelesek": a.ertekelesek.name,
        "sha256": hashlib.sha256(a.ertekelesek.read_bytes()).hexdigest(),
        "tarhaz": a.tarhaz.name,
        "adatforras": str(built["adatforras"].iloc[0]) if "adatforras" in built else None,
    }
    a.kimenet.parent.mkdir(parents=True, exist_ok=True)
    a.kimenet.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    a.kimenet.with_suffix(".md").write_text(report(res), encoding="utf-8")
    f = res["szabalyok"]["atlag"]
    print(f"késett: {f['kesett']['n']} rendelés, átlag {f['kesett']['atlag']:.2f}, 1–2 csillagos {_pct(f['kesett']['alacsony_arany'])}")
    print(f"időben: {f['idoben']['n']} rendelés, átlag {f['idoben']['atlag']:.2f}, 1–2 csillagos {_pct(f['idoben']['alacsony_arany'])}")
    print(f"→ {a.kimenet} és .md")


if __name__ == "__main__":
    main()
