"""
Gazdasági forgatókönyvek: mit ér a modell egy kapacitáskorlátos beavatkozásban, ha a költségeket
nem ismerjük, csak az arányukat feltételezzük?

Az Olist-adat költséget nem tartalmaz. A döntés értékét ezért egy elkerült késés értékének (B)
egységében adjuk meg, forgatókönyvekre:
  * c = C / B: egy beavatkozás ára az elkerült késés értékéhez képest (0,01; 0,02; 0,05; 0,10);
  * e: a beavatkozás hatékonysága, vagyis annak valószínűsége, hogy egy egyébként késő rendelés
    késését elkerüli (0,3 és 0,6).
Egy beavatkozási szabály nettó értéke B-egységben: e · L − c · N, ahol N a megjelölt rendelések,
L közülük a ténylegesen késettek száma (a teszt-időszak valódi kimenetéből; leíró, semmit nem
választunk vele). A nullszint: senkit nem jelölünk meg (0). Megtérülési küszöb: L / N > c / e.

Szabályok:
  1. Kapacitás: a legkockázatosabb q hányad (1, 2, 5, 10, 20%) megjelölése — LightGBM, logisztikus
     regresszió és véletlen kiválasztás (várható érték: q · az összes késés).
  2. Küszöb a becsült valószínűségen: megjelölünk minden rendelést, ahol a becslés > c / e — a
     „tankönyvi” szabály. Mellé: a döntéshozó által a becslésből várt nettó érték, Σ (e · p − c),
     és a ténylegesen elért — a kalibráció gazdasági tétje.
Bizonytalanság: heti blokk-bootstrap a teszt heteken (B = 2000), a véletlenhez mért különbség
párosítva; a tanítóadat véletlene: a K3 20 bootstrap-modellje (LightGBM, ugyanazok a minták).
A beállítások a futás előtt a döntési naplóban.

    uv run python tools/gazdasagi_forgatokonyv.py         # → docs/gazdasagi_forgatokonyv.json és .md
    uv run python tools/gazdasagi_forgatokonyv.py --bootstrap 2 --b-huzas 50 --kimenet artifacts/gazd_proba.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.db import DB_PATH, use_utf8_console  # noqa: E402
from pipeline.bootstrap import resample_indices, week_blocks  # noqa: E402
from xai import stability as st  # noqa: E402
from xai.models import Bundle, load_bundle  # noqa: E402

SHARES = (0.01, 0.02, 0.05, 0.10, 0.20)
COSTS = (0.01, 0.02, 0.05, 0.10)
EFFECTS = (0.3, 0.6)
B_DRAWS = 2000
CI_SEED = 20261104
N_BOOT = st.N_BOOT
MODELS = ("lightgbm", "logreg")
MODEL_NAMES = {"lightgbm": "LightGBM", "logreg": "logisztikus regresszió", "veletlen": "véletlen kiválasztás"}
# Előre rögzített várakozások (döntési napló, a futás előtt) — leíró, küszöb nélkül:
#  V1: a LightGBM szerinti kiválasztás minden q-nál több késést fog, mint a véletlen;
#  V2: a küszöbszabálynál a becslésből várt nettó érték meghaladja a ténylegesen elértet, ha a
#      küszöb (c / e) legalább 0,1 — a felső sávban a modell túlbecsül;
#  V3: a LightGBM és a logisztikus regresszió nettó értéke között a 10%-os kapacitásnál nincs előzetes irány.


def top_mask(p: np.ndarray, share: float) -> np.ndarray:
    n_top = max(1, int(round(share * len(p))))
    m = np.zeros(len(p), dtype=bool)
    m[np.argsort(-p, kind="stable")[:n_top]] = True
    return m


def net(late: int, flagged: int, c: float, e: float) -> float:
    """Nettó érték B-egységben: e · L − c · N."""
    return e * late - c * flagged


def capacity_rows(y: np.ndarray, p: np.ndarray, shares=SHARES) -> list[dict]:
    rows = []
    for q in shares:
        m = top_mask(p, q)
        rows.append({"q": q, "N": int(m.sum()), "L": int(y[m].sum()),
                     "pontossag": float(y[m].mean()), "fogas": float(y[m].sum() / y.sum())})
    return rows


def random_rows(y: np.ndarray, shares=SHARES) -> list[dict]:
    """A véletlen kiválasztás várható értéke (q · N, a késések aránya)."""
    n, late = len(y), float(y.sum())
    return [{"q": q, "N": int(max(1, round(q * n))), "L": max(1, round(q * n)) * late / n,
             "pontossag": late / n, "fogas": max(1, round(q * n)) / n} for q in shares]


def threshold_rows(y: np.ndarray, p: np.ndarray, costs=COSTS, effects=EFFECTS) -> list[dict]:
    rows = []
    for e in effects:
        for c in costs:
            t = c / e
            m = p > t
            n, late = int(m.sum()), int(y[m].sum())
            expected = float(np.sum(e * p[m] - c))
            rows.append({"e": e, "c": c, "kuszob": t, "N": n, "L": late,
                         "pontossag": float(y[m].mean()) if n else float("nan"),
                         "becsles_atlag": float(p[m].mean()) if n else float("nan"),
                         "vart_netto": expected, "elert_netto": net(late, n, c, e)})
    return rows


def _ci(vals) -> dict:
    a = np.asarray(vals, dtype=float)
    return {"ci95": [float(np.quantile(a, 0.025)), float(np.quantile(a, 0.975))]}


def bootstrap_net(y, p_models: dict, blocks, shares=SHARES, costs=COSTS, effects=EFFECTS,
                  B: int = B_DRAWS, seed: int = CI_SEED) -> dict:
    """Heti blokk-bootstrap: a nettó érték 1000 rendelésre, modellenként és a véletlenhez mért különbsége."""
    keys = [(k, q, c, e) for k in p_models for q in shares for c in costs for e in effects]
    draws = {key: [] for key in keys}
    diff_rand = {key: [] for key in keys}
    diff_lr = {(q, c, e): [] for q in shares for c in costs for e in effects}
    for idx in resample_indices(blocks, B, seed):
        yy = y[idx]
        n, late_all = len(yy), yy.sum()
        cache = {}
        for k, p in p_models.items():
            pp = p[idx]
            for q in shares:
                m = top_mask(pp, q)
                cache[(k, q)] = (int(m.sum()), int(yy[m].sum()))
        for (k, q, c, e) in keys:
            N, L = cache[(k, q)]
            v = net(L, N, c, e) * 1000 / n
            r = net(N * late_all / n, N, c, e) * 1000 / n
            draws[(k, q, c, e)].append(v)
            diff_rand[(k, q, c, e)].append(v - r)
        if "lightgbm" in p_models and "logreg" in p_models:
            for (q, c, e) in diff_lr:
                a = net(cache[("lightgbm", q)][1], cache[("lightgbm", q)][0], c, e)
                b = net(cache[("logreg", q)][1], cache[("logreg", q)][0], c, e)
                diff_lr[(q, c, e)].append((a - b) * 1000 / n)
    fmt = lambda t: "|".join(str(x) for x in t)  # noqa: E731
    return {"netto": {fmt(k): _ci(v) for k, v in draws.items()},
            "netto_minusz_veletlen": {fmt(k): _ci(v) for k, v in diff_rand.items()},
            "lightgbm_minusz_logreg": {fmt(k): _ci(v) for k, v in diff_lr.items()}}


def run(b: Bundle, n_boot: int = N_BOOT, B: int = B_DRAWS, verbose: bool = True) -> dict:
    t0 = time.time()
    te = b.split.test.sort_values()
    X, y = b.X.loc[te], b.y.loc[te].to_numpy(dtype=int)
    p = {k: b.models[k].predict_proba(X)[:, 1] for k in MODELS}
    n = len(y)
    per1000 = 1000 / n
    cap = {k: capacity_rows(y, p[k]) for k in MODELS}
    cap["veletlen"] = random_rows(y)
    scen = []
    for e in EFFECTS:
        for c in COSTS:
            row = {"e": e, "c": c, "kuszob": c / e}
            for k in (*MODELS, "veletlen"):
                vals = [net(r["L"], r["N"], c, e) * per1000 for r in cap[k]]
                row[k] = vals
                row[f"{k}_legjobb_q"] = SHARES[int(np.argmax(vals))] if max(vals) > 0 else None
            scen.append(row)
    thr = threshold_rows(y, p["lightgbm"])
    if verbose:
        print(f"[{time.time() - t0:5.0f} mp] pontbecslések kész; blokk-bootstrap (B = {B})…", flush=True)
    blocks = week_blocks(b.meta.loc[te, "rendeles_idopont"])
    boot = bootstrap_net(y, p, blocks, B=B)
    # a tanítóadat véletlene: a K3 bootstrap-modelljei (csak a LightGBM)
    boot_models = []
    seed = int(b.info.get("mag", 42))
    for i in range(n_boot):
        m = st.fit_models(b, st.bootstrap_index(b, i), seed, ("lightgbm",))["lightgbm"]
        pi = m.predict_proba(X)[:, 1]
        boot_models.append(capacity_rows(y, pi))
        if verbose:
            print(f"[{time.time() - t0:5.0f} mp] bootstrap-modell {i + 1}/{n_boot}", flush=True)
    rash = {}
    for qi, q in enumerate(SHARES):
        Ls = [r[qi]["L"] for r in boot_models]
        rash[str(q)] = {"L_min": int(min(Ls)) if Ls else None, "L_max": int(max(Ls)) if Ls else None,
                        "L_atlag": float(np.mean(Ls)) if Ls else None}
    return {
        "letrehozva": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kod_ujjlenyomat": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "beallitas": {"hanyadok": list(SHARES), "c": list(COSTS), "e": list(EFFECTS), "B": B, "ci_mag": CI_SEED,
                      "bootstrap_modellek": n_boot, "bootstrap_mag": st.BOOT_SEED, "teszt_rendelesek": int(n),
                      "teszt_kesesek": int(y.sum()), "egyseg": "B (egy elkerült késés értéke) 1000 rendelésre"},
        "adat": {k: v for k, v in b.info.items() if k in ("adatforras", "tarhaz_epitve", "lightgbm_fak")},
        "kapacitas": cap,
        "forgatokonyvek": scen,
        "kuszob_szabaly": thr,
        "bizonytalansag": boot,
        "tanitoadat_veletlene": rash,
        "ido_mp": round(time.time() - t0, 1),
    }


# ------------------------------------------------------------------ jelentés
def _n(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def _pct(x: float, d: int = 1) -> str:
    return _n(100 * x, d) + "%"


def report(res: dict) -> str:
    s = res["beallitas"]
    cap, boot = res["kapacitas"], res["bizonytalansag"]
    L = ["# Gazdasági forgatókönyvek — mit ér a modell egy kapacitáskorlátos beavatkozásban?", "",
         f"Készült: {res['letrehozva']} · kód-ujjlenyomat `{res['kod_ujjlenyomat'][:16]}…` · {res['ido_mp']:.0f} mp. "
         "Az előre rögzített beállítások: döntési napló.", "",
         f"A teszt-időszak {s['teszt_rendelesek']} rendelése, ebből {s['teszt_kesesek']} késett. Az érték egysége: "
         "egy elkerült késés értéke (B), 1000 rendelésre vetítve. c = a beavatkozás ára B-hez képest, e = a "
         "beavatkozás hatékonysága. Nettó érték = e · (megjelölt és ténylegesen késett) − c · (megjelölt). "
         "A költségek feltevések, nem mért adatok.", "",
         "## 1. Kapacitás: a legkockázatosabb q hányad megjelölése", "",
         "| q | megjelölt | késett közülük: LightGBM | LR | véletlen (várható) | pontosság: LightGBM | LR | véletlen |",
         "|---|---|---|---|---|---|---|---|"]
    for i, q in enumerate(s["hanyadok"]):
        g, lr, r = cap["lightgbm"][i], cap["logreg"][i], cap["veletlen"][i]
        L.append(f"| {_pct(q, 0)} | {g['N']} | {g['L']} | {lr['L']} | {_n(r['L'])} | {_pct(g['pontossag'])} | "
                 f"{_pct(lr['pontossag'])} | {_pct(r['pontossag'])} |")
    L += ["", "## 2. Nettó érték forgatókönyvenként (B-egység / 1000 rendelés; zárójelben 95% heti blokk-bootstrap)", "",
          "| e | c | megtérülési küszöb (c/e) | " + " | ".join(f"q = {_pct(q, 0)}" for q in s["hanyadok"]) + " | legjobb q |",
          "|---|---|---|" + "---|" * len(s["hanyadok"]) + "---|"]
    for sc in res["forgatokonyvek"]:
        cells = []
        for i, q in enumerate(s["hanyadok"]):
            key = f"lightgbm|{q}|{sc['c']}|{sc['e']}"
            ci = boot["netto"][key]["ci95"]
            cells.append(f"{_n(sc['lightgbm'][i])} [{_n(ci[0])}; {_n(ci[1])}]")
        best = sc["lightgbm_legjobb_q"]
        L.append(f"| {_n(sc['e'], 1)} | {_n(sc['c'], 2)} | {_pct(sc['kuszob'])} | " + " | ".join(cells)
                 + f" | {_pct(best, 0) if best else 'senki'} |")
    L += ["", "A véletlen kiválasztás nettó értéke ugyanezekben a forgatókönyvekben (pontbecslés):", "",
          "| e | c | " + " | ".join(f"q = {_pct(q, 0)}" for q in s["hanyadok"]) + " |",
          "|---|---|" + "---|" * len(s["hanyadok"])]
    for sc in res["forgatokonyvek"]:
        L.append(f"| {_n(sc['e'], 1)} | {_n(sc['c'], 2)} | " + " | ".join(_n(v) for v in sc["veletlen"]) + " |")
    L += ["", "## 3. LightGBM − logisztikus regresszió a 10%-os kapacitásnál (B / 1000 rendelés, 95% CI)", "",
          "| e | c | különbség |", "|---|---|---|"]
    for sc in res["forgatokonyvek"]:
        i = s["hanyadok"].index(0.10)
        d = sc["lightgbm"][i] - sc["logreg"][i]
        ci = boot["lightgbm_minusz_logreg"][f"0.1|{sc['c']}|{sc['e']}"]["ci95"]
        L.append(f"| {_n(sc['e'], 1)} | {_n(sc['c'], 2)} | {_n(d)} [{_n(ci[0])}; {_n(ci[1])}] |")
    L += ["", "## 4. Küszöb a becsült valószínűségen (LightGBM): várt és elért nettó érték", "",
          "| e | c | küszöb | megjelölt | átlagos becslés | tényleges arány | várt nettó (B) | elért nettó (B) |",
          "|---|---|---|---|---|---|---|---|"]
    for t in res["kuszob_szabaly"]:
        L.append(f"| {_n(t['e'], 1)} | {_n(t['c'], 2)} | {_pct(t['kuszob'])} | {t['N']} | "
                 f"{_pct(t['becsles_atlag']) if t['N'] else '—'} | {_pct(t['pontossag']) if t['N'] else '—'} | "
                 f"{_n(t['vart_netto'])} | {_n(t['elert_netto'])} |")
    L += ["", f"## 5. A tanítóadat véletlene ({s['bootstrap_modellek']} bootstrap-modell, LightGBM)", "",
          "| q | késett a megjelöltek közül: lezárt | bootstrap-modellek: átlag (legkisebb – legnagyobb) |", "|---|---|---|"]
    for i, q in enumerate(s["hanyadok"]):
        r = res["tanitoadat_veletlene"][str(q)]
        L.append(f"| {_pct(q, 0)} | {cap['lightgbm'][i]['L']} | {_n(r['L_atlag'])} ({r['L_min']} – {r['L_max']}) |")
    L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="Gazdasági forgatókönyvek a lezárt modellekkel (leíró).")
    ap.add_argument("--bootstrap", type=int, default=N_BOOT, help="bootstrap-modellek száma")
    ap.add_argument("--b-huzas", type=int, default=B_DRAWS, help="heti blokk-bootstrap húzásai")
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--kimenet", type=Path, default=ROOT / "docs" / "gazdasagi_forgatokonyv.json")
    ap.add_argument("--jelentes", type=Path, default=None, help="csak a .md újraírása egy meglévő JSON-ból")
    a = ap.parse_args(argv)
    if a.jelentes:
        res = json.loads(a.jelentes.read_text(encoding="utf-8"))
        a.jelentes.with_suffix(".md").write_text(report(res), encoding="utf-8")
        return
    full = a.bootstrap == N_BOOT and a.b_huzas == B_DRAWS
    if not full and a.kimenet.resolve().parent == (ROOT / "docs").resolve():
        sys.exit("Próbafutás (nem az előre rögzített beállítás) nem írhat a docs/ mappába — adj meg --kimenet-et.")
    b = load_bundle(a.db, verbose=True)
    res = run(b, n_boot=a.bootstrap, B=a.b_huzas)
    a.kimenet.parent.mkdir(parents=True, exist_ok=True)
    a.kimenet.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    a.kimenet.with_suffix(".md").write_text(report(res), encoding="utf-8")
    print(f"Eredmény: {a.kimenet} (és {a.kimenet.with_suffix('.md').name}); {res['ido_mp']} mp")


if __name__ == "__main__":
    main()
