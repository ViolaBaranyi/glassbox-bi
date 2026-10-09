"""
A referencia-modellek LEZÁRT összevetése a teszten — ugyanazzal a fegyelemmel,
mint a v3 alapfutás: a protokoll (docs/v3_referencia_protokoll.json) a futás
ELŐTT rögzül, jóvá van hagyva és commitolva, és a futás egyszer nyúl a teszthez.

A LightGBM eredménye itt nem változik — az a lezárt v3 alapfutás. A kérdés az,
hogyan teljesítenek mellette az egyszerűbb modellek UGYANAZON a teszten.

  1. protokoll-ellenőrzés: jóváhagyva, commitolva, a rácsok és a mag egyeznek
     a kóddal, az alap-protokoll ujjlenyomata egyezik a lezárt v3 futáséval, és
     a lezárt eredmény megvan;
  2. hiperparaméter-választás a tanító ablakon (bővülő ablakos CV, ugyanaz,
     mint a `python -m pipeline.reference_models`) — ha más jönne ki, mint ami
     a protokollban áll, a futás a teszt előtt megáll;
  3. végső illesztés a tisztított tanító ablakon, mag 42;
  4. a teszten: mérőszámok heti blokk-bootstrap intervallummal, és PÁROS
     összevetés a lezárt LightGBM-mel (ugyanazokon a húzott heteken);
  5. a random forest tanítási véletlene 5 maggal;
  6. eredmény: docs/v3_referencia_eredmeny.json + .md — egyszer.

Futtatás (csak jóváhagyott és commitolt protokollal):
    python -m pipeline.v3_reference
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from data.db import DB_PATH, WarehouseUnavailable, connect, use_utf8_console
from pipeline import reference_models as rm
from pipeline import train
from pipeline import v3_baseline as vb
from pipeline.bootstrap import METRICS, block_bootstrap, paired_block_bootstrap, week_blocks
from pipeline.features import LeakageError, build_features
from pipeline.split import settled_before, temporal_split

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL = ROOT / "docs" / "v3_referencia_protokoll.json"
RESULT_JSON = ROOT / "docs" / "v3_referencia_eredmeny.json"
RESULT_MD = ROOT / "docs" / "v3_referencia_eredmeny.md"
PAIRED = ("pr_auc", "roc_auc", "brier")


def check_reference_protocol(p: dict, base_sha: str, locked: dict | None) -> None:
    hibak = []
    if p.get("allapot") != "jovahagyva":
        hibak.append(f"a protokoll állapota „{p.get('allapot')}\", nem „jovahagyva\"")
    jov = p.get("jovahagyas") or {}
    if not jov.get("ki") or not jov.get("mikor"):
        hibak.append("hiányzik, ki és mikor hagyta jóvá (jovahagyas.ki, jovahagyas.mikor)")
    alap = p.get("alap_protokoll") or {}
    if alap.get("sha256") != base_sha:
        hibak.append("az alap-protokoll (docs/v3_protokoll.json) ujjlenyomata eltér a "
                     "referencia-protokollban rögzítettől")
    if locked is None:
        hibak.append("nincs lezárt v3 eredmény (docs/v3_lezart_eredmeny.json) — az összevetés "
                     "a lezárt LightGBM-hez képest készül")
    elif locked.get("protokoll_sha256") != base_sha:
        hibak.append("a lezárt v3 eredmény más protokollal készült, mint a mostani alap-protokoll")
    mods = p.get("modellek") or {}
    for kind, spec in rm.MODELS.items():
        if (mods.get(kind) or {}).get("racs") != spec["racs"]:
            hibak.append(f"modellek.{kind}.racs = {(mods.get(kind) or {}).get('racs')!r}, "
                         f"a kódban {spec['racs']!r}")
    if (mods.get("dontesi_fa") or {}).get("min_samples_leaf") != rm.DT_MIN_LEAF:
        hibak.append(f"modellek.dontesi_fa.min_samples_leaf: a kódban {rm.DT_MIN_LEAF}")
    if (mods.get("random_forest") or {}).get("n_estimators") != rm.RF_TREES:
        hibak.append(f"modellek.random_forest.n_estimators: a kódban {rm.RF_TREES}")
    if p.get("mag") != rm.SEED:
        hibak.append(f"mag = {p.get('mag')!r}, a kódban {rm.SEED}")
    tv = p.get("tanitasi_veletlen") or {}
    if not isinstance(tv.get("magok"), list) or len(tv["magok"]) < 2:
        hibak.append("tanitasi_veletlen.magok: legalább két mag kell")
    bs = p.get("bizonytalansag") or {}
    if not isinstance(bs.get("B"), int) or bs["B"] < 100 or not isinstance(bs.get("mag"), int):
        hibak.append("bizonytalansag.B (legalább 100) és bizonytalansag.mag kell")
    if hibak:
        raise vb.ProtocolError("A lezárt összevetés nem indul — a protokoll:\n  - "
                               + "\n  - ".join(hibak))


def run_reference(db_path: Path = DB_PATH, protocol_path: Path = PROTOCOL,
                  base_protocol_path: Path = vb.PROTOCOL, locked_path: Path = vb.RESULT_JSON,
                  out_json: Path = RESULT_JSON, out_md: Path = RESULT_MD,
                  ismetles: bool = False, require_committed: bool = True) -> dict:
    prot, sha = vb.load_protocol(protocol_path)
    base, base_sha = vb.load_protocol(base_protocol_path)
    locked = (json.loads(Path(locked_path).read_text(encoding="utf-8"))
              if Path(locked_path).exists() else None)
    check_reference_protocol(prot, base_sha, locked)
    prov = vb._provenance(db_path)
    if (base.get("adat") or {}).get("forras") != prov["adatforras"]:
        raise vb.ProtocolError(f"Az alap-protokoll adatforrása {base['adat']['forras']!r}, "
                               f"a tárházé {prov['adatforras']!r}.")
    gs = vb.git_state(protocol_path)
    if require_committed and not (gs["protokoll_commitolva"] and gs["munkapeldany_tiszta"]):
        raise vb.ProtocolError(
            "A lezárt összevetés előtt a jóváhagyott protokollt és a kódot commitolni kell.\n"
            "Teendő:\n  git add -A\n  git commit -m \"referencia-protokoll jóváhagyva\"\n"
            "  git push\nmajd újra: python -m pipeline.v3_reference")
    if Path(out_json).exists() and not ismetles:
        raise vb.LockedRunExists(f"Már van lezárt összevetés: {out_json} "
                                 "(ismételt futás: --ismetles)")

    purge = bool(base["cimke_tisztitas"])
    seed = int(prot["mag"])
    bs = prot["bizonytalansag"]
    print(f"Protokoll: {Path(protocol_path).name} · SHA256 {sha[:16]}… · jóváhagyta: "
          f"{prot['jovahagyas']['ki']} ({prot['jovahagyas']['mikor']})")

    con = connect(db_path, read_only=True)
    X, y, meta = build_features(con)
    con.close()
    sp = temporal_split(meta["rendeles_idopont"])
    tr = settled_before(sp.train, meta["vallalt_hatarido"], sp.train_end) if purge else sp.train

    # 2. választás a tanító ablakon
    print("\nHiperparaméter-választás a tanító ablakon (bővülő ablakos CV)…")
    with contextlib.redirect_stdout(io.StringIO()):
        cv = rm.compare(X, y, meta, sp.train, purge=purge, seed=seed, verbose=False)
    elvart = prot.get("cv_valasztas_elvart") or {}
    for kind in rm.MODELS:
        if kind in elvart and elvart[kind] != cv["modellek"][kind]["valasztott"]:
            raise vb.ProtocolError(
                f"A {kind} választása a CV-n {cv['modellek'][kind]['valasztott']!r}, a "
                f"protokollban {elvart[kind]!r} — a futás a teszt előtt megáll.")

    # 3–4. a lezárt LightGBM és a referenciák a teszten
    print("A lezárt LightGBM előrejelzései (a v3 protokoll szerint)…")
    with contextlib.redirect_stdout(io.StringIO()):
        lg = train.run(db_path, seed=int(base["vegso_modell"]["mag"]), tag="v3_referencia",
                       balance="none", write_artifacts=False, trees="cv", purge=purge,
                       return_predictions=True)
    te = lg["elorejelzesek"]["teszt"]
    if locked is not None and round(lg["teszt"]["pr_auc"], 4) != round(
            locked["teszt"]["bootstrap"]["pr_auc"]["ertek"], 4):
        raise RuntimeError("A LightGBM nem a lezárt eredményt adja — a környezet eltér.")
    blocks = week_blocks(te["ido"])
    yte, yva = te["y"], lg["elorejelzesek"]["valid"]["y"]

    eredm = {"lightgbm": {"nev": "LightGBM (lezárt)", "beallitas": f"{lg['fak_szama']} fa",
                          "teszt": block_bootstrap(yte, te["p"], blocks, B=bs["B"], seed=bs["mag"]),
                          "validacio": lg["validacio"]}}
    for kind, spec in rm.MODELS.items():
        val = cv["modellek"][kind]["valasztott"]
        print(f"{spec['nev']} ({spec['param']} = {val}): illesztés és bootstrap…")
        m = rm.make_model(kind, val, seed).fit(X.loc[tr], y.loc[tr])
        p_te = m.predict_proba(X.loc[sp.test])[:, 1]
        p_va = m.predict_proba(X.loc[sp.valid])[:, 1]
        eredm[kind] = {
            "nev": spec["nev"], "beallitas": f"{spec['param']} = {val}",
            "teszt": block_bootstrap(yte, p_te, blocks, B=bs["B"], seed=bs["mag"]),
            "validacio": train.evaluate(yva, p_va),
            "paros_lightgbm_minusz_referencia": paired_block_bootstrap(
                yte, te["p"], p_te, blocks, metrics={k: METRICS[k] for k in PAIRED},
                B=bs["B"], seed=bs["mag"]),
        }

    # 5. a random forest tanítási véletlene
    rf_val = cv["modellek"]["random_forest"]["valasztott"]
    print("Random forest — tanítási véletlen több maggal…")
    rf_runs = []
    for s in prot["tanitasi_veletlen"]["magok"]:
        m = rm.make_model("random_forest", rf_val, int(s)).fit(X.loc[tr], y.loc[tr])
        rf_runs.append({"mag": int(s), **train.evaluate(yte, m.predict_proba(X.loc[sp.test])[:, 1])})
    rf_sweep = {k: {"atlag": round(float(np.mean([r[k] for r in rf_runs])), 5),
                    "szoras": round(float(np.std([r[k] for r in rf_runs], ddof=1)), 5)}
                for k in METRICS}

    result = {
        "nev": prot.get("nev"),
        "protokoll_sha256": sha,
        "alap_protokoll_sha256": base_sha,
        "protokoll": prot,
        "futas": {"idopont_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                  "ismetles": bool(ismetles), "git": gs["commit"] or train.git_hash(),
                  "git_allapot": gs, "commit_nelkul_engedve": not require_committed,
                  "python": platform.python_version(), "os": platform.platform()},
        "adat": prov,
        "cimke_tisztitas": bool(purge),
        "tanito_sorok": int(len(tr)),
        "teszt_bazisrata": round(float(np.mean(yte)), 4),
        "cv": cv,
        "modellek": eredm,
        "random_forest_magok": {"futasok": rf_runs, "osszegzes": rf_sweep},
    }
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(out_json).write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str),
                              encoding="utf-8")
    Path(out_md).write_text(summary_markdown(result), encoding="utf-8")
    print("\n" + summary_markdown(result))
    print(f"Mentve: {out_json}\n        {out_md}\nEzeket a fájlokat commitold.")
    return result


def _ci(d: dict, nd: int = 4) -> str:
    return f"{d['ertek']:.{nd}f} [{d['ci95'][0]:.{nd}f}; {d['ci95'][1]:.{nd}f}]"


def summary_markdown(r: dict) -> str:
    rows = []
    for kind, m in r["modellek"].items():
        t = m["teszt"]
        cvr = r["cv"]["modellek"][kind]["cv"]
        rows.append(f"| {m['nev']} | {m['beallitas']} | {cvr['pr_auc']:.4f} | {_ci(t['pr_auc'])} | "
                    f"{_ci(t['roc_auc'])} | {_ci(t['brier'])} | {t['ece_egyenlo_elemszam']['ertek']:.4f} |")
    paros = []
    for kind in rm.MODELS:
        d = r["modellek"][kind]["paros_lightgbm_minusz_referencia"]
        paros.append(
            f"| {r['modellek'][kind]['nev']} | {d['pr_auc']['kulonbseg']:+.4f} "
            f"[{d['pr_auc']['ci95'][0]:+.4f}; {d['pr_auc']['ci95'][1]:+.4f}] | "
            f"{d['roc_auc']['kulonbseg']:+.4f} [{d['roc_auc']['ci95'][0]:+.4f}; {d['roc_auc']['ci95'][1]:+.4f}] | "
            f"{d['brier']['kulonbseg']:+.5f} [{d['brier']['ci95'][0]:+.5f}; {d['brier']['ci95'][1]:+.5f}] |")
    sw = r["random_forest_magok"]["osszegzes"]
    ism = " — **ISMÉTELT FUTÁS**" if r["futas"]["ismetles"] else ""
    return f"""# Referencia-modellek — lezárt összevetés{ism}

Protokoll: `docs/v3_referencia_protokoll.json`, SHA256 `{r['protokoll_sha256']}`
(alap: `docs/v3_protokoll.json`, `{r['alap_protokoll_sha256'][:16]}…`).
Jóváhagyta: {r['protokoll']['jovahagyas']['ki']} ({r['protokoll']['jovahagyas']['mikor']}).
Futás: {r['futas']['idopont_utc']} UTC · git `{r['futas']['git']}` · Python {r['futas']['python']}.
Teszt: {r['teszt_bazisrata']:.4f} késési arány; tanító sorok (tisztítva): {r['tanito_sorok']:,}.

## Eredmény a teszten (95% CI, heti blokk-bootstrap)

| modell | beállítás (CV-n választva) | CV PR-AUC | teszt PR-AUC | teszt ROC-AUC | teszt Brier | ECE (tizedek) |
|---|---|---|---|---|---|---|
{chr(10).join(rows)}

## Páros összevetés: LightGBM − referencia (ugyanazokon a húzott heteken)

Pozitív PR-AUC / ROC-AUC és negatív Brier-különbség = a LightGBM jobb. Ha az
intervallum a nullát is tartalmazza, a különbség ezen a teszten nem kimutatható.

| referencia | PR-AUC különbség | ROC-AUC különbség | Brier-különbség |
|---|---|---|---|
{chr(10).join(paros)}

Random forest, 5 mag: PR-AUC {sw['pr_auc']['atlag']:.4f} ± {sw['pr_auc']['szoras']:.4f},
ROC-AUC {sw['roc_auc']['atlag']:.4f} ± {sw['roc_auc']['szoras']:.4f}.
"""


def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="Referencia-modellek lezárt összevetése a teszten")
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--ismetles", action="store_true")
    ap.add_argument("--commit-nelkul", action="store_true")
    a = ap.parse_args()
    try:
        run_reference(a.db, ismetles=a.ismetles, require_committed=not a.commit_nelkul)
    except (vb.ProtocolError, vb.LockedRunExists, WarehouseUnavailable, LeakageError,
            ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"\nA LEZÁRT ÖSSZEVETÉS NEM INDULT:\n{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
