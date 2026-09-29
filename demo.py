"""
Üvegdoboz BI — a teljes pipeline egyetlen paranccsal, bemutatáshoz.

    python demo.py            # meglévő adatot használ; ha nincs, szintetikusat generál
    python demo.py --fresh    # a szintetikus adatot újragenerálja (valódi adatot soha nem ír felül)

Lépések:
  1. környezet ellenőrzése
  2. adat (szintetikus, ha nincs valódi)
  3. tárház felépítése — V-1 validáció
  4. tesztek — szivárgás és V-1; ha bármelyik elbukik, a demó leáll
  5. betanítás — LightGBM + kalibráció, érintetlen teszthalmazon mérve
  6. összegzés

PyCharmban a zöld Run gombbal is indítható.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.db import use_utf8_console  # noqa: E402

LINE = "=" * 72


def header(n: int, title: str) -> float:
    print(f"\n{LINE}\n {n}. {title}\n{LINE}")
    return time.perf_counter()


def done(t0: float) -> None:
    print(f"   ({time.perf_counter() - t0:.1f} mp)")


def fail(msg: str) -> None:
    print(f"\n{LINE}\n A DEMÓ LEÁLLT\n{LINE}\n{msg}", file=sys.stderr)
    sys.exit(1)


def raw_state(raw_dir: Path) -> str:
    """'nincs' | 'szintetikus' | 'valós' — a build_warehouse logikájával."""
    from data.build_warehouse import SOURCES, SYNTHETIC_MARKER, sha256
    if not all((raw_dir / f).exists() for f in SOURCES.values()):
        return "nincs"
    marker = raw_dir / SYNTHETIC_MARKER
    if not marker.exists():
        return "valós"
    rec = json.loads(marker.read_text(encoding="utf-8")).get("files", {})
    same = all(rec.get(f) == sha256(raw_dir / f) for f in SOURCES.values())
    return "szintetikus" if same else "valós"


def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="Üvegdoboz BI — teljes pipeline")
    ap.add_argument("--fresh", action="store_true",
                    help="szintetikus adat újragenerálása (valódit nem ír felül)")
    ap.add_argument("--balance", choices=["balanced", "none"], default="balanced")
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
    done(t)

    # ------------------------------------------------------------------ 2. adat
    t = header(2, "Adat")
    from data.make_synthetic import RAW, generate
    state = raw_state(RAW)
    if state == "valós":
        print("   Valódi (nem generált) forrásfájlok vannak a data\\raw mappában —")
        print("   ezeket használjuk." + ("  A --fresh ezeket NEM írja felül." if args.fresh else ""))
    elif state == "nincs" or args.fresh:
        print("   Szintetikus, Olist-alakú adat generálása...")
        generate(out_dir=RAW)
    else:
        print("   A korábban generált szintetikus adatot használjuk.")
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
    t = header(4, "Tesztek — szivárgásvédelem és V-1 validáció")
    import pytest
    code = pytest.main(["-q", "--no-header", "-p", "no:cacheprovider",
                        str(ROOT / "tests")])
    if code != 0:
        fail("Legalább egy teszt elbukott. Amíg ez így van, a betanítás eredménye\n"
             "nem hiteles — a demó ezért itt megáll.")
    done(t)

    # ------------------------------------------------------------ 5. betanítás
    t = header(5, "Betanítás — LightGBM, kalibráció, érintetlen teszthalmaz")
    from pipeline.features import LeakageError
    from pipeline.train import run
    try:
        res = run(balance=args.balance)
    except (LeakageError, WarehouseUnavailable) as exc:
        fail(str(exc))
    done(t)

    # ------------------------------------------------------------- 6. összegzés
    raw_m, cal_m = res["teszt_kalibralatlan"], res["teszt_kalibralt"]
    print(f"\n{LINE}\n ÖSSZEGZÉS\n{LINE}")
    if res["adatforras"] == "szintetikus":
        print("   ! SZINTETIKUS ADAT — a számok a gépezet működését mutatják,")
        print("     a valóságról semmit nem mondanak.\n")
    print(f"   Tárház         {wh['fact_sorok']:,} rendelés, "
          f"{wh['idoszak'][0]} .. {wh['idoszak'][1]}")
    kar = sum(n for _, n in wh["karanten"])
    print(f"   V-1 validáció  rendben, karanténban {kar:,} sor")
    print("   Tesztek        mind átment")
    print(f"   Modell         LightGBM, {res['jellemzok']} jellemző, {res['fak_szama']} fa, "
          f"súlyozás: {res['kiegyensulyozas']}")
    print(f"   Rangsorolás    PR-AUC {raw_m['pr_auc']:.3f}  "
          f"(bázisráta {res['bazisrata']:.3f}, {raw_m['pr_auc'] / res['bazisrata']:.1f}x)  "
          f"ROC-AUC {raw_m['roc_auc']:.3f}")
    print(f"   Kalibráció     ECE {raw_m['ece']:.3f} -> {cal_m['ece']:.3f}   "
          f"Brier {raw_m['brier']:.3f} -> {cal_m['brier']:.3f}")
    print(f"   Artefaktumok   {Path(res['artifacts']).relative_to(ROOT)}")
    print(f"\n   Teljes futásidő: {time.perf_counter() - started:.0f} mp")
    print(LINE)


if __name__ == "__main__":
    main()
