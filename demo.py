"""
Üvegdoboz BI — a teljes pipeline egyetlen paranccsal, bemutatáshoz.

    python demo.py              # a valódi Olist-adaton fut; ha még nincs meg, letölti
    python demo.py --synthetic  # szintetikus adaton (CI, gépezet-próba valódi adat nélkül)

Lépések:
  1. környezet ellenőrzése
  2. adat — a valódi Olist-adat; első indításkor letöltés a Kaggle-ről
  3. tárház felépítése — V-1 validáció
  4. tesztek — szivárgás és V-1; ha bármelyik elbukik, a demó leáll
  5. betanítás — a lezárt v3 protokoll szerint: LightGBM súlyozás nélkül, a fák
     száma bővülő ablakos CV-vel a tanító időszakon, címke-tisztítással; érintetlen
     teszthalmazon mérve; a kalibráció csak diagnosztika (nincs utólagos kalibrátor)
  6. összegzés

PyCharmban a zöld Run gombbal is indítható.
"""

from __future__ import annotations

import argparse
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.db import use_utf8_console  # noqa: E402

LINE = "=" * 72
TARGET_PYTHON = (3, 14)   # a rögzített környezet (pyproject.toml, requirements.lock)


def header(n: int, title: str) -> float:
    print(f"\n{LINE}\n {n}. {title}\n{LINE}")
    return time.perf_counter()


def done(t0: float) -> None:
    print(f"   ({time.perf_counter() - t0:.1f} mp)")


def fail(msg: str) -> None:
    print(f"\n{LINE}\n A DEMÓ LEÁLLT\n{LINE}\n{msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="Üvegdoboz BI — teljes pipeline")
    ap.add_argument("--synthetic", action="store_true",
                    help="szintetikus adaton fut (CI, gépezet-próba); "
                         "valódi adatot nem ír felül")
    ap.add_argument("--balance", choices=["none", "balanced"], default="none",
                    help="none (alapértelmezett) vagy balanced (csak összevetéshez)")
    args = ap.parse_args()

    started = time.perf_counter()
    print(LINE)
    print(" ÜVEGDOBOZ BI — kutatási prototípus (EKÖP-26-I-1)")
    print(" XAI és LLM integrálása self-service BI rendszerbe")
    print(LINE)

    # ------------------------------------------------------------ 1. környezet
    t = header(1, "Környezet")
    import duckdb
    import lightgbm
    import pandas
    import sklearn
    print(f"   Python {platform.python_version()} · {platform.system()} {platform.release()}")
    print(f"   duckdb {duckdb.__version__} · lightgbm {lightgbm.__version__} · "
          f"scikit-learn {sklearn.__version__} · pandas {pandas.__version__}")
    if sys.version_info[:2] != TARGET_PYTHON:
        print(f"   ! A projekt a Python {TARGET_PYTHON[0]}.{TARGET_PYTHON[1]}-re van rögzítve "
              "(README, requirements.lock). Más verzióval futhat,")
        print("     de a számok bitre azonossága csak a rögzített környezetben garantált.")
    done(t)

    # ------------------------------------------------------------------ 2. adat
    t = header(2, "Adat")
    from data.fetch_olist import FetchError, data_state, fetch
    from data.make_synthetic import RAW, generate
    state = data_state(RAW)
    if args.synthetic:
        if state == "valós":
            fail("A data\\raw mappában valódi Olist-adat van, a --synthetic felülírná.\n"
                 "Szintetikus futáshoz használj egy friss klónt, vagy nevezd át a\n"
                 "data\\raw mappát (a valódi adat bármikor újra letölthető).")
        if state == "szintetikus":
            print("   A korábban generált szintetikus adatot használjuk (--synthetic).")
        else:
            print("   Szintetikus, Olist-alakú adat generálása (--synthetic)...")
            generate(out_dir=RAW)
    elif state == "valós":
        print("   A valódi Olist-adatot használjuk (data\\raw).")
    else:
        if state == "szintetikus":
            print("   A data\\raw mappában szintetikus adat van — lecseréljük a valódira.")
        else:
            print("   Még nincs adat a data\\raw mappában — első indítás.")
        try:
            fetch(RAW)
        except FetchError as exc:
            fail(str(exc))
    done(t)

    # ---------------------------------------------------------------- 3. tárház
    t = header(3, "Tárház — csillagséma DuckDB-ben, V-1 validációval")
    from data.build_warehouse import ValidationError, build
    from data.db import WarehouseUnavailable
    try:
        wh = build()
    except (ValidationError, WarehouseUnavailable) as exc:
        fail(str(exc))
    done(t)

    # --------------------------------------------------------------- 4. tesztek
    t = header(4, "Tesztek — szivárgásvédelem, V-1 validáció, magyarázatok, felület")
    import pytest
    code = pytest.main(["-q", "--no-header", "-p", "no:cacheprovider",
                        str(ROOT / "tests")])
    if code != 0:
        fail("Legalább egy teszt elbukott. Amíg ez így van, a betanítás eredménye\n"
             "nem hiteles — a demó ezért itt megáll.")
    done(t)

    # ------------------------------------------------------------ 5. betanítás
    t = header(5, "Betanítás — LightGBM, érintetlen teszthalmaz")
    from pipeline.features import LeakageError
    from pipeline.train import run
    try:
        res = run(balance=args.balance)
    except (LeakageError, WarehouseUnavailable) as exc:
        fail(str(exc))
    done(t)

    # ------------------------------------------------------------- 6. összegzés
    m = res["teszt"]
    diag = res["teszt_diagnosztika"]
    print(f"\n{LINE}\n ÖSSZEGZÉS\n{LINE}")
    if res["adatforras"] == "szintetikus":
        print("   ! SZINTETIKUS ADAT — a számok a gépezet működését mutatják,")
        print("     a valóságról semmit nem mondanak.\n")
    print(f"   Tárház         {wh['fact_sorok']:,} rendelés, "
          f"{wh['idoszak'][0]} .. {wh['idoszak'][1]}")
    kar = ", ".join(f"{ok}: {n:,}" for ok, n in wh["karanten"]) or "üres"
    print(f"   V-1 validáció  rendben, karantén: {kar}")
    print(f"   Kizárva        {wh['kizart']:,} nem kézbesített rendelés "
          f"(zárónap {wh['zarnap'][:10]}; érzékenység: python -m pipeline.cohort_report)")
    print("   Tesztek        mind átment")
    print(f"   Modell         LightGBM, {res['jellemzok']} jellemző, {res['fak_szama']} fa "
          f"(bővülő ablakos CV{', címke-tisztítással' if res['cimke_tisztitas']['be'] else ''}), "
          f"súlyozás: {res['kiegyensulyozas']}")
    print(f"   Rangsorolás    PR-AUC {m['pr_auc']:.3f}  "
          f"(bázisráta {res['bazisrata']:.3f}, {m['pr_auc'] / res['bazisrata']:.1f}x)  "
          f"ROC-AUC {m['roc_auc']:.3f}")
    print(f"   Kalibráció     ECE {m['ece']:.3f} (egyenlő elemszámú sávokkal "
          f"{m['ece_egyenlo_elemszam']:.3f})   Brier {m['brier']:.4f}, "
          f"készség {diag['brier_keszseg']['tanito_bazisratahoz']:.1%}")
    print(f"   Artefaktumok   {Path(res['artifacts']).relative_to(ROOT)}")
    print("   Felület        python -m ui   (megnyílik a böngészőben: http://localhost:8501)")
    print(f"\n   Teljes futásidő: {time.perf_counter() - started:.0f} mp")
    print(LINE)


if __name__ == "__main__":
    main()
