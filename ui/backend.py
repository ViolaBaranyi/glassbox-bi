"""
A BI-felület adatrétege — Streamlit nélkül is futtatható és tesztelhető.

Minden szám vagy determinisztikus SQL-lekérdezésből jön a tárházból (DuckDB),
vagy a lezárt modellekből és a mentett eredményfájlokból (docs/). A felület
maga semmit nem számol „fejben", és a lekérdezések szövegét is megmutatja.

Környezeti változók (a tesztekhez):
    GLASSBOX_DB     másik tárházfájl (alapból data/warehouse.duckdb)
    GLASSBOX_CACHE  másik modell-gyorsítótár (alapból artifacts/v3_modellek.joblib)

(A modul neve szándékosan nem data.py: a Streamlit a felület mappáját a keresési
út elejére teszi, és egy ui/data.py elfedné a projekt `data` csomagját.)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from data.db import DB_PATH, connect
from pipeline.cohort_report import wilson
from pipeline.split import temporal_split
from pipeline.train import _bins  # ugyanaz a sávolás, mint a lezárt megbízhatósági táblában
from xai import labels
from xai import narrative as nv
from xai.explain import explain, percentage_points
from xai.models import CACHE, KINDS, NAMES, Bundle, load_bundle

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

MIN_MONTH_ORDERS = 100     # ennél kevesebb rendeléses hónap aránya csak zaj (2016. szept., dec.)
SAMPLE_N = 2000            # a globális összegzések mintája a teszt-időszakból
SLOW_N = 100               # a random forest TreeSHAP-ja lassú (~0,3 mp/rendelés)
SAMPLE_SEED = 0

DIMENSIONS = {
    "vevo_allam": ("a vevő állama", "c.allam",
                   "LEFT JOIN dim_customer c ON f.customer_key = c.customer_key"),
    "elado_allam": ("az eladó állama", "s.allam",
                    "LEFT JOIN dim_seller s ON f.seller_key = s.seller_key"),
    "kategoria": ("a fő termék kategóriája", "p.kategoria",
                  "LEFT JOIN dim_product p ON f.product_key = p.product_key"),
}
WINDOW_NAMES = {"train": "tanító", "valid": "validációs", "test": "teszt"}


def db_path() -> Path:
    return Path(os.environ.get("GLASSBOX_DB", DB_PATH))


def cache_path() -> Path:
    return Path(os.environ.get("GLASSBOX_CACHE", CACHE))


def stamp(path: Path | None = None) -> str:
    """A tárházfájl azonosítója a gyorsítótárakhoz: újraépítéskor megváltozik."""
    p = Path(path or db_path())
    return f"{p}|{p.stat().st_mtime_ns}" if p.exists() else f"{p}|hiányzik"


# ------------------------------------------------------- SQL (a felület mutatja)
SQL_OVERVIEW = """\
SELECT count(*)                       AS rendelesek,
       avg(CAST(kesett AS DOUBLE))    AS kesesi_arany,
       min(rendeles_idopont)          AS elso,
       max(rendeles_idopont)          AS utolso
FROM fact_orders"""

SQL_MONTHLY = """\
SELECT date_trunc('month', rendeles_idopont) AS honap,
       count(*)                              AS rendelesek,
       sum(CAST(kesett AS INTEGER))          AS kesett
FROM fact_orders
GROUP BY 1
ORDER BY 1"""


def sql_by_dimension(dim: str) -> str:
    if dim not in DIMENSIONS:
        raise ValueError(f"Ismeretlen dimenzió: {dim!r}")
    _, col, join = DIMENSIONS[dim]
    return f"""\
SELECT coalesce({col}, '(ismeretlen)')  AS ertek,
       count(*)                         AS rendelesek,
       sum(CAST(f.kesett AS INTEGER))   AS kesett,
       avg(CAST(f.kesett AS DOUBLE))    AS kesesi_arany
FROM fact_orders f
{join}
GROUP BY 1
HAVING count(*) >= ?
ORDER BY kesesi_arany DESC, ertek"""


def _with_ci(df: pd.DataFrame, k: str = "kesett", n: str = "rendelesek") -> pd.DataFrame:
    ci = [wilson(int(a), int(b)) for a, b in zip(df[k], df[n])]
    df["ci_also"] = [c[0] for c in ci]
    df["ci_felso"] = [c[1] for c in ci]
    return df


# ------------------------------------------------------------- áttekintés
def overview(path: Path | None = None) -> dict:
    con = connect(path or db_path(), read_only=True)
    n, late, first, last = con.execute(SQL_OVERVIEW).fetchone()
    mb = con.execute("SELECT adatforras, epitve, kizart_rendelesek, megfigyelesi_zarnap "
                     "FROM meta_build").fetchone()
    con.close()
    return {"rendelesek": int(n), "kesesi_arany": float(late), "elso": str(first)[:10],
            "utolso": str(last)[:10], "adatforras": str(mb[0]), "epitve": str(mb[1]),
            "kizart": int(mb[2] or 0), "zarnap": str(mb[3])[:10]}


def monthly(path: Path | None = None) -> pd.DataFrame:
    con = connect(path or db_path(), read_only=True)
    df = con.execute(SQL_MONTHLY).df()
    con.close()
    df["honap"] = pd.to_datetime(df["honap"])
    df["kesett"] = df["kesett"].astype(int)
    df["kesesi_arany"] = df["kesett"] / df["rendelesek"]
    df["megbizhato"] = df["rendelesek"] >= MIN_MONTH_ORDERS
    return _with_ci(df)


def windows(path: Path | None = None) -> pd.DataFrame:
    """A tanító / validációs / teszt ablak határai (ugyanaz a vágás, mint a modelleknél)."""
    con = connect(path or db_path(), read_only=True)
    ts = con.execute("SELECT rendeles_idopont FROM fact_orders").df()["rendeles_idopont"]
    con.close()
    ts = pd.to_datetime(ts)
    sp = temporal_split(ts)
    rows = []
    for key, idx, start, end in [("train", sp.train, ts.min(), sp.train_end),
                                 ("valid", sp.valid, sp.train_end, sp.valid_end),
                                 ("test", sp.test, sp.valid_end, ts.max())]:
        rows.append({"ablak": WINDOW_NAMES[key], "kezdet": pd.Timestamp(start).normalize(),
                     "veg": pd.Timestamp(end), "rendelesek": int(len(idx))})
    return pd.DataFrame(rows)


def value_label(dim: str, value) -> str:
    """Egy dimenzióérték emberi neve: „Alagoas (AL)", „egészség és szépségápolás"."""
    if dim in ("vevo_allam", "elado_allam"):
        return labels.state_label(None if value == "(ismeretlen)" else value)
    if dim == "kategoria":
        return labels.category_name(value)
    return str(value)


def by_dimension(dim: str, min_n: int = 300, path: Path | None = None) -> pd.DataFrame:
    """Késési arány egy dimenzió szerint, 95%-os Wilson-intervallummal (legalább min_n rendelés).
    A `megnevezes` oszlop az érték emberi neve (állam teljes neve, magyar kategória)."""
    sql = sql_by_dimension(dim)
    con = connect(path or db_path(), read_only=True)
    df = con.execute(sql, [int(min_n)]).df()
    con.close()
    df["kesett"] = df["kesett"].astype(int)
    df.insert(1, "megnevezes", [value_label(dim, v) for v in df["ertek"]])
    if dim in ("vevo_allam", "elado_allam"):
        df.insert(2, "regio", [labels.state_region(v) for v in df["ertek"]])
    return _with_ci(df).reset_index(drop=True)


# ------------------------------------------------------------ modellek
def bundle(path: Path | None = None) -> Bundle:
    return load_bundle(path or db_path(), cache_path=cache_path())


def _proba(b: Bundle, kind: str, idx) -> np.ndarray:
    return b.models[kind].predict_proba(b.X.loc[idx])[:, 1]


def risk_table(b: Bundle) -> pd.DataFrame:
    """A teszt-időszak rendelései a LightGBM becslésével, kockázat szerint csökkenő sorrendben."""
    idx = b.split.test
    p = _proba(b, "lightgbm", idx)
    df = pd.DataFrame({
        "order_key": b.meta.loc[idx, "order_key"].astype(str).to_numpy(),
        "leadva": pd.to_datetime(b.meta.loc[idx, "rendeles_idopont"]).to_numpy(),
        "valoszinuseg": p,
        "kategoria": b.X.loc[idx, "kategoria"].astype(str).to_numpy(),
        "vevo_allam": b.X.loc[idx, "vevo_allam"].astype(str).to_numpy(),
        "elado_allam": b.X.loc[idx, "elado_allam"].astype(str).to_numpy(),
        "vallalt_ido_nap": b.X.loc[idx, "vallalt_ido_nap"].to_numpy(),
        "kesett": b.y.loc[idx].astype(bool).to_numpy(),
    })
    df["relativ"] = df["valoszinuseg"] / float(np.mean(p))
    df["relativ_szoveg"] = [f"{nv.fmt_num(v, 1)}×" for v in df["relativ"]]   # „13,1×" (nem „13.1×")
    # emberi nevek a felülethez (a kódok maradnak a szűréshez és a tesztekhez)
    df["kategoria_nev"] = [labels.category_name(v) for v in df["kategoria"]]
    df["vevo_nev"] = [labels.state_label(v) for v in df["vevo_allam"]]
    df["elado_nev"] = [labels.state_label(v) for v in df["elado_allam"]]
    df = df.sort_values(["valoszinuseg", "order_key"], ascending=[False, True])
    df.insert(0, "rang", np.arange(1, len(df) + 1))
    return df.reset_index(drop=True)


def capture(b: Bundle, share: float = 0.10, kind: str = "lightgbm") -> dict:
    """
    Közérthető mérőszám a teszt-időszakon: a modell szerint legkockázatosabb `share`
    hányadban (pl. 10%) a késések hány százaléka van. Véletlen kiválasztásnál ez épp
    `share` lenne. (A lezárt kiértékelés modelljein, diagnosztika.)
    """
    if kind != "lightgbm":
        raise ValueError("A közérthető összefoglaló a fő modellre (LightGBM) szól.")
    rt = risk_table(b)                         # ugyanaz a sorrend, mint a kockázati listán
    n = len(rt)
    n_top = max(1, int(round(share * n)))
    late_all, late_top = int(rt["kesett"].sum()), int(rt["kesett"].head(n_top).sum())
    return {"hanyad": share, "rendelesek": int(n), "felso_rendelesek": n_top,
            "kesett_osszes": late_all, "kesett_felso": late_top,
            "kesesek_aranya_a_felsoben": late_top / late_all if late_all else float("nan"),
            "kesesi_arany_felso": late_top / n_top, "kesesi_arany": late_all / n}


def period_average(b: Bundle) -> float:
    """A teszt-időszak átlagos becsült kockázata (LightGBM) — a relatív kockázat alapja."""
    return float(np.mean(_proba(b, "lightgbm", b.split.test)))


def find_order(b: Bundle, order_key) -> int | None:
    hit = b.meta.index[b.meta["order_key"].astype(str) == str(order_key).strip()]
    return int(hit[0]) if len(hit) else None


def _window(b: Bundle, i) -> str:
    if i in b.split.train:
        return WINDOW_NAMES["train"]
    return WINDOW_NAMES["valid"] if i in b.split.valid else WINDOW_NAMES["test"]


def order_detail(b: Bundle, order_key, k: int = 6, period_avg: float | None = None,
                 record_window: str | None = "test") -> dict:
    """
    Egy rendelés teljes magyarázata mind a négy modellel (megjelenítési tényezőkben),
    és a LightGBM-becslés múltbeli pontossága a `record_window` ablakban
    (test: utólag, valid: a teszt előtt is ismert; None: nincs).
    """
    i = find_order(b, order_key)
    if i is None:
        raise ValueError(f"Nincs ilyen rendelés: {order_key}")
    row = b.X.loc[[i]]
    x = row.iloc[0]
    avg = period_average(b) if period_avg is None else float(period_avg)
    bg = b.background()
    models = {}
    for kind in KINDS:
        e = explain(kind, b.models[kind], row, bg)
        frame = nv.display_frame(percentage_points(e).iloc[0], x)
        models[kind] = {"nev": NAMES[kind], "ter": e.space,
                        "valoszinuseg": float(e.proba[0]), "alap": float(e.p0[0]),
                        "tenyezok": frame}
    lg = models["lightgbm"]
    p, p0, frame = lg["valoszinuseg"], lg["alap"], lg["tenyezok"]
    full = frame.assign(leiras=[nv.display_info(t) for t in frame["tenyezo"]])
    key = str(b.meta.loc[i, "order_key"])
    record = similar_orders(b, p, key, window=record_window) if record_window else None
    return {
        "order_key": key,
        "leadva": str(b.meta.loc[i, "rendeles_idopont"])[:16],
        "vallalt_hatarido": str(b.meta.loc[i, "vallalt_hatarido"])[:10],
        "ablak": _window(b, i),
        "kesett": bool(b.y.loc[i]),
        "valoszinuseg": p,
        "alap": p0,
        "idoszak_atlag": avg,
        "relativ_kockazat": p / avg if avg > 0 else float("nan"),
        "szazbol": int(round(p * 100)),
        "hasonlok": record,
        "okok": frame.head(k).reset_index(drop=True),
        "tenyezok": full,
        "narrativa": nv.narrative(p, p0, avg, frame, record=record),
        # alapérték + Σ hatás = becslés — százalékpontban ellenőrizve
        "additivitasi_elteres_pp": abs(100 * p0 + frame["hatas_pp"].sum() - 100 * p),
        "modellek": models,
    }


def model_comparison(detail: dict, top: int = 8) -> pd.DataFrame:
    """Hosszú tábla a hőtérképhez: a legerősebb tényezők hatása mind a négy modellben."""
    mats = {kind: m["tenyezok"].set_index("tenyezo")["hatas_pp"]
            for kind, m in detail["modellek"].items()}
    wide = pd.DataFrame(mats)
    order = wide.abs().max(axis=1).sort_values(ascending=False, kind="stable").index[:top]
    rows = []
    for t in order:
        for kind in KINDS:
            rows.append({"tenyezo": t, "nev": nv.display_name(t), "modell": NAMES[kind],
                         "hatas_pp": float(wide.loc[t, kind])})
    return pd.DataFrame(rows)


def agreement(detail: dict, k: int = 3) -> pd.DataFrame:
    """Modellenként a becslés és a top-k tényező; hány egyezik a LightGBM top-k-jával."""
    ref = set(detail["modellek"]["lightgbm"]["tenyezok"]["tenyezo"].head(k))
    rows = []
    for kind in KINDS:
        m = detail["modellek"][kind]
        top = m["tenyezok"].head(k)
        rows.append({
            "modell": m["nev"],
            "becsles": m["valoszinuseg"],
            "kiindulopont": m["alap"],
            "legerosebb_tenyezok": " · ".join(
                f"{r.nev} {'▲' if r.hatas_pp >= 0 else '▼'}" for r in top.itertuples()),
            "kozos_a_lightgbm_mel": f"{len(ref & set(top['tenyezo']))}/{k}",
            "magyarazo_ter": m["ter"],
        })
    return pd.DataFrame(rows)


def calibration(b: Bundle, kind: str = "lightgbm", n_bins: int = 10) -> pd.DataFrame:
    """Megbízhatósági tizedek a teszt-időszakon (egyenlő elemszámú sávok), Wilson-intervallummal."""
    idx = b.split.test
    p = _proba(b, kind, idx)
    y = b.y.loc[idx].to_numpy().astype(int)
    edges, bins = _bins(p, n_bins, "quantile")
    rows = []
    for j in range(len(edges) - 1):
        m = bins == j
        if m.any():
            rows.append({"sav": f"{nv.fmt_pct(edges[j])} – {nv.fmt_pct(edges[j + 1])}",
                         "also": float(edges[j]), "felso": float(edges[j + 1]),
                         "rendelesek": int(m.sum()),
                         "kesett": int(y[m].sum()), "atlag_becsles": float(p[m].mean()),
                         "tenyleges_arany": float(y[m].mean())})
    return _with_ci(pd.DataFrame(rows))


# ------------------------------------------------ becslési sávok és múltbeli pontosság
# Rögzített valószínűség-sávok: egy becslés „hitelessége" az, hogy a hasonló becslésű
# rendelések közül ténylegesen hány késett. A tizedekkel szemben ezek a sávok minden
# időszakban ugyanazok, és a ritka, magas becsléseket is külön mutatják (a legfelső
# tized a teszt-időszakban 9%-tól 58%-ig tart — átlaga elfedi a farok túlbecslését).
BANDS = (0.0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 1.0)
MIN_BAND_N = 20            # ennél kevesebb rendelésből nem ítélünk a sávról
RECORD_WINDOWS = ("test", "valid")


def _window_index(b: Bundle, window: str):
    if window == "test":
        return b.split.test
    if window == "valid":
        return b.split.valid
    raise ValueError(f"Ismeretlen ablak: {window!r} (test | valid)")


def band_index(p) -> np.ndarray:
    """A becslés sávjának sorszáma (0 … len(BANDS) − 2); a határ a felső sávba esik."""
    return np.searchsorted(np.asarray(BANDS[1:-1]), np.asarray(p, dtype=float), side="right")


def _pct_edge(x: float) -> str:
    return nv.fmt_num(100 * x, 0) + "%"


def band_name(j: int) -> str:
    """Rövid sávnév táblázatba: „2% alatt", „5–10%", „30% fölött"."""
    if j == 0:
        return f"{_pct_edge(BANDS[1])} alatt"
    if j == len(BANDS) - 2:
        return f"{_pct_edge(BANDS[-2])} fölött"
    return f"{nv.fmt_num(100 * BANDS[j], 0)}–{_pct_edge(BANDS[j + 1])}"


def band_phrase(j: int) -> str:
    """Melléknévi alak mondatba: „2% alatti", „5–10%-os", „30% feletti"."""
    if j == 0:
        return f"{_pct_edge(BANDS[1])} alatti"
    if j == len(BANDS) - 2:
        return f"{_pct_edge(BANDS[-2])} feletti"
    return f"{nv.fmt_num(100 * BANDS[j], 0)}–{_pct_edge(BANDS[j + 1])}-os"


def verdict(mean_p: float, ci: tuple[float, float], n: int) -> str:
    """A sáv átlagos becslése és a tényleges arány 95%-os intervalluma alapján."""
    if n < MIN_BAND_N:
        return "kevés adat"
    if mean_p > ci[1]:
        return "túlbecsült"
    if mean_p < ci[0]:
        return "alábecsült"
    return "összhangban"


def band_table(b: Bundle, kind: str = "lightgbm", window: str = "test") -> pd.DataFrame:
    """Becslési sávonként: rendelések, átlagos becslés, tényleges arány (Wilson), ítélet."""
    idx = _window_index(b, window)
    p = _proba(b, kind, idx)
    y = b.y.loc[idx].to_numpy().astype(int)
    j = band_index(p)
    rows = []
    for k in range(len(BANDS) - 1):
        m = j == k
        n, late = int(m.sum()), int(y[m].sum())
        ci = wilson(late, n)
        mean_p = float(p[m].mean()) if n else float("nan")
        rows.append({"sav": band_name(k), "also": BANDS[k], "felso": BANDS[k + 1],
                     "rendelesek": n, "kesett": late, "atlag_becsles": mean_p,
                     "tenyleges_arany": late / n if n else float("nan"),
                     "ci_also": ci[0], "ci_felso": ci[1], "itelet": verdict(mean_p, ci, n)})
    return pd.DataFrame(rows)


# A közérthető összefoglalóhoz a sávok három csoportban: alacsony · közepes · magas becslés.
BAND_GROUPS = (("alacsony", 0.0, 0.05), ("közepes", 0.05, 0.20), ("magas", 0.20, 1.0))


def band_groups(bt: pd.DataFrame) -> pd.DataFrame:
    """A band_table sávjai három csoportba összevonva (5% alatt · 5–20% · 20% fölött):
    rendelések, átlagos becslés, tényleges arány (Wilson-intervallum), ítélet."""
    rows = []
    for name, lo, hi in BAND_GROUPS:
        g = bt[(bt["also"] >= lo - 1e-12) & (bt["felso"] <= hi + 1e-12) & (bt["rendelesek"] > 0)]
        n, late = int(g["rendelesek"].sum()), int(g["kesett"].sum())
        mean_p = float((g["atlag_becsles"] * g["rendelesek"]).sum() / n) if n else float("nan")
        ci = wilson(late, n)
        rows.append({"csoport": name, "also": lo, "felso": hi, "rendelesek": n, "kesett": late,
                     "atlag_becsles": mean_p, "tenyleges_arany": late / n if n else float("nan"),
                     "ci_also": ci[0], "ci_felso": ci[1], "itelet": verdict(mean_p, ci, n)})
    return pd.DataFrame(rows)


def similar_orders(b: Bundle, p: float, order_key=None, window: str = "test",
                   kind: str = "lightgbm") -> dict:
    """
    A becslés múltbeli pontossága: az ablak azon rendelései, amelyek a modelltől
    ugyanabba a sávba eső becslést kaptak — és közülük ténylegesen hány késett.
    Ha maga a rendelés is az ablakban van, kimarad (a saját kimenete nem számít bele).
    """
    idx = _window_index(b, window)
    keys = b.meta.loc[idx, "order_key"].astype(str).to_numpy()
    pw = _proba(b, kind, idx)
    y = b.y.loc[idx].to_numpy().astype(int)
    k = int(band_index([p])[0])
    m = band_index(pw) == k
    self_in = order_key is not None and bool((keys == str(order_key)).any())
    if self_in:
        m &= keys != str(order_key)
    n, late = int(m.sum()), int(y[m].sum())
    ci = wilson(late, n)
    mean_p = float(pw[m].mean()) if n else float("nan")
    rate = late / n if n else float("nan")
    base = float(y.mean()) if len(y) else float("nan")
    return {"ablak": window, "sav": k, "sav_nev": band_name(k), "sav_szoveg": band_phrase(k),
            "rendelesek": n, "kesett": late, "tenyleges_arany": rate,
            "ci_also": ci[0], "ci_felso": ci[1], "atlag_becsles": mean_p,
            "idoszak_arany": base,
            "relativ_tenyleges": rate / base if base > 0 and n else float("nan"),
            "itelet": verdict(mean_p, ci, n), "onmaga_kihagyva": self_in}


# ---------------------------------------------- globális összegzések (minta)
def sample_explanations(b: Bundle, kinds=KINDS, n: int = SAMPLE_N, n_slow: int = SLOW_N,
                        seed: int = SAMPLE_SEED) -> tuple[pd.DataFrame, dict]:
    """
    Rögzített véletlen minta a teszt-időszakból; modellenként a megjelenítési
    tényezők hatása százalékpontban (sor = rendelés). A random forest a minta
    első `n_slow` sorát kapja (lassú).
    """
    test = b.X.loc[b.split.test]
    sample = test.sample(min(n, len(test)), random_state=seed)
    bg = b.background()
    out = {}
    for kind in kinds:
        rows = sample.head(n_slow) if kind == "random_forest" else sample
        out[kind] = nv.merge_display(percentage_points(explain(kind, b.models[kind], rows, bg)))
    return sample, out


def global_importance_table(expl: dict) -> pd.DataFrame:
    """Átlagos abszolút hatás (százalékpont) modellenként és tényezőnként, rangsorral."""
    rows = []
    for kind, pp in expl.items():
        imp = pp.abs().mean().sort_values(ascending=False, kind="stable")
        for rank, (t, v) in enumerate(imp.items(), start=1):
            rows.append({"modell": NAMES[kind], "tenyezo": t, "nev": nv.display_name(t),
                         "atlag_abs_pp": float(v), "rang": rank, "minta": len(pp)})
    return pd.DataFrame(rows)


def dependence(sample: pd.DataFrame, pp: pd.DataFrame, key: str) -> pd.DataFrame:
    """Egy tényező értéke és hatása a mintán (függőségi ábra)."""
    if key == nv.MONTH:
        vals = [nv.month_number(s, c) for s, c in zip(sample["honap_sin"], sample["honap_cos"])]
        x = pd.Series(vals, index=sample.index)
    else:
        x = sample[key]
    rows = sample.index.intersection(pp.index)
    return pd.DataFrame({"ertek": x.loc[rows].to_numpy(),
                         "hatas_pp": pp.loc[rows, key].to_numpy()}, index=rows)


# ------------------------------------------------------- lezárt eredmények
def locked_results() -> dict:
    def read(name):
        p = DOCS / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    return {"alapfutas": read("v3_lezart_eredmeny.json"),
            "referencia": read("v3_referencia_eredmeny.json")}


def results_table(res: dict) -> pd.DataFrame | None:
    """A négy modell teszt-eredménye a lezárt összevetésből (pont + 95% CI)."""
    ref = res.get("referencia")
    if not ref:
        return None
    rows = []
    for kind, m in ref["modellek"].items():
        t = m["teszt"]
        row = {"kulcs": kind, "modell": m["nev"], "beallitas": m["beallitas"]}
        for metric in ("pr_auc", "roc_auc", "brier", "ece"):
            row[metric] = t[metric]["ertek"]
            row[f"{metric}_also"], row[f"{metric}_felso"] = t[metric]["ci95"]
        rows.append(row)
    return pd.DataFrame(rows)


def paired_table(res: dict) -> pd.DataFrame | None:
    """LightGBM − referencia, páros heti blokk-bootstrap (a lezárt összevetésből)."""
    ref = res.get("referencia")
    if not ref:
        return None
    better = {"pr_auc": 1, "roc_auc": 1, "brier": -1}   # +1: a nagyobb a jobb
    rows = []
    for kind, m in ref["modellek"].items():
        d = m.get("paros_lightgbm_minusz_referencia")
        if not d:
            continue
        for metric, sign in better.items():
            lo, hi = d[metric]["ci95"]
            if lo > 0 or hi < 0:
                good = (lo > 0) == (sign > 0)
                verdict = "a LightGBM jobb" if good else "a referencia jobb"
            else:
                verdict = "nem kimutatható"
            rows.append({"referencia": m["nev"], "mutato": metric,
                         "kulonbseg": d[metric]["kulonbseg"], "also": lo, "felso": hi,
                         "itelet": verdict})
    return pd.DataFrame(rows)


def integrity(b: Bundle, res: dict, path: Path | None = None) -> dict:
    """
    Ugyanazok-e a felület modelljei, mint a lezárt futásokéi?
      1. a tárház forrásfájljainak ujjlenyomata = a lezárt futásé;
      2. mind a négy modell teszt PR-AUC-je = a lezárt érték (5 tizedesjegyig).
    Szintetikus adaton nincs mivel összevetni.
    """
    if b.info.get("adatforras") != "valós":
        return {"statusz": "szintetikus", "forrasok_egyeznek": None, "modellek": None}
    base, ref = res.get("alapfutas"), res.get("referencia")
    if not base:
        return {"statusz": "nincs_eredmeny", "forrasok_egyeznek": None, "modellek": None}
    con = connect(path or db_path(), read_only=True)
    live = dict(con.execute("SELECT fajl, sha256 FROM meta_sources").fetchall())
    con.close()
    locked_src = {f: v["sha256"] for f, v in base["adat"]["forrasfajlok"].items()}
    same_sources = live == locked_src

    idx = b.split.test
    y = b.y.loc[idx].to_numpy()
    rows = []
    for kind in KINDS:
        if ref and kind in ref["modellek"]:
            locked = ref["modellek"][kind]["teszt"]["pr_auc"]["ertek"]
        elif kind == "lightgbm":
            locked = base["teszt"]["bootstrap"]["pr_auc"]["ertek"]
        else:
            continue
        now = float(average_precision_score(y, _proba(b, kind, idx)))
        rows.append({"modell": NAMES[kind], "most": now, "lezart": float(locked),
                     "egyezik": abs(now - float(locked)) < 1e-5})
    tab = pd.DataFrame(rows)
    ok = same_sources and bool(tab["egyezik"].all())
    return {"statusz": "egyezik" if ok else "elter", "forrasok_egyeznek": same_sources,
            "modellek": tab}


def kernel_arm_results(path: Path | None = None) -> dict | None:
    """A KernelSHAP-kontrollkar mentett eredménye (python -m xai.kernel_arm), ha van."""
    p = Path(path or DOCS / "kernel_kar_eredmeny.json")
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _ci_text(m: dict, digits: int = 2) -> str:
    lo, hi = m["ci95"]
    return f"{nv.fmt_num(m['atlag'], digits)} [{nv.fmt_num(lo, digits)}; {nv.fmt_num(hi, digits)}]"


def kernel_pairs_table(res: dict) -> pd.DataFrame:
    """Modellpáronként a magyarázatok egyezése: a karon (ugyanaz a magyarázó) és a saját magyarázókkal."""
    names = {k: m["nev"] for k, m in res["modellek"].items()}
    rows = []
    for key, d in res["modellparok"].items():
        a, c = key.split("|")
        rows.append({"modellpar": f"{names[a]} – {names[c]}",
                     "rbo_kar": _ci_text(d["kontrollkar"]["rbo"]),
                     "rbo_sajat": _ci_text(d["sajat_magyarazok"]["rbo"]),
                     "top3_kar": nv.fmt_num(d["kontrollkar"]["top3"]["atlag"], 2),
                     "top3_sajat": nv.fmt_num(d["sajat_magyarazok"]["top3"]["atlag"], 2)})
    return pd.DataFrame(rows)


def kernel_checks_table(res: dict) -> pd.DataFrame:
    """Modellenként: a kar zaja (más mag, más háttér) és a felület magyarázatának egyezése a karral."""
    rows = []
    for kind, m in res["modellek"].items():
        z, conv = res["zaj"][kind], res["atvaltas"][kind]["felulet"]
        rows.append({"modell": m["nev"],
                     "zaj_mag_rbo": _ci_text(z["mintavetel"]["rbo"]),
                     "zaj_hatter_rbo": _ci_text(z["hatter"]["rbo"]),
                     "felulet_rbo": _ci_text(conv["rbo"]),
                     "felulet_top3": nv.fmt_num(conv["top3"]["atlag"], 2),
                     "felulet_elojel3": nv.fmt_pct(conv["elojel3"]["atlag"], 0)})
    return pd.DataFrame(rows)


def provenance(res: dict) -> list[dict]:
    """A lezárt futások eredete (protokoll-ujjlenyomat, commit, idő, gép)."""
    out = []
    for name, key in [("v3 alapfutás (LightGBM)", "alapfutas"),
                      ("referencia-összevetés", "referencia")]:
        r = res.get(key)
        if not r:
            continue
        f = r["futas"]
        out.append({"futas": name, "protokoll_sha256": r["protokoll_sha256"][:12] + "…",
                    "jovahagyta": r["protokoll"]["jovahagyas"]["ki"],
                    "git": f["git"], "idopont_utc": f["idopont_utc"],
                    "gep": f"{f['os']} · Python {f['python']}",
                    "tiszta_munkapeldany": bool(f["git_allapot"]["munkapeldany_tiszta"])})
    return out
