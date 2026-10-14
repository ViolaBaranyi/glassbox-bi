"""
Az Olist adathalmaz letöltése a data\\raw mappába.

    python -m data.fetch_olist            # letölti, ha még nincs valódi adat
    python -m data.fetch_olist --force    # akkor is újra letölti, ha már megvan

Forrás: Kaggle, olistbr/brazilian-ecommerce — „Brazilian E-Commerce Public
Dataset by Olist". Nyilvános adathalmaz, a letöltéshez nem kell Kaggle-fiók.
Licenc: CC BY-NC-SA 4.0 (nem kereskedelmi felhasználás, forrásmegjelöléssel).

A kagglehub a saját gyorsítótárába tölt (Windowson %USERPROFILE%\\.cache\\kagglehub),
onnan másoljuk át a 9 CSV-t. A valódi adat soha nem kerül a tárolóba (.gitignore).

A demo.py tiszta indításnál ezt hívja meg; a szintetikus adat csak a CI-é és a
teszteké (python demo.py --synthetic).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from data.build_warehouse import RAW, SOURCES, SYNTHETIC_MARKER, sha256
from data.db import use_utf8_console

DATASET = "olistbr/brazilian-ecommerce"
DATASET_URL = "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce"


class FetchError(RuntimeError):
    """A valódi adat nem tölthető le vagy hiányos."""


def data_state(raw_dir: Path = RAW) -> str:
    """'nincs' | 'szintetikus' | 'valós' — a build_warehouse logikájával."""
    raw_dir = Path(raw_dir)
    if not all((raw_dir / f).exists() for f in SOURCES.values()):
        return "nincs"
    marker = raw_dir / SYNTHETIC_MARKER
    if not marker.exists():
        return "valós"
    rec = json.loads(marker.read_text(encoding="utf-8")).get("files", {})
    same = all(rec.get(f) == sha256(raw_dir / f) for f in SOURCES.values())
    return "szintetikus" if same else "valós"


def _manual_help(reason: str, raw_dir: Path = RAW) -> str:
    return (
        f"Az Olist adathalmaz letöltése nem sikerült: {reason}\n\n"
        "Kézi letöltés:\n"
        f"  1. {DATASET_URL} -> Download (kb. 45 MB-os ZIP)\n"
        f"  2. A ZIP-ből mind a 9 CSV-t másold ide: {raw_dir}\n"
        "  3. Futtasd újra: uv run demo.py\n\n"
        "Ha csak a gépezetet akarod kipróbálni valódi adat nélkül:\n"
        "  uv run demo.py --synthetic"
    )


def _find(src: Path, name: str) -> Path | None:
    direct = src / name
    if direct.exists():
        return direct
    return next(iter(sorted(src.rglob(name))), None)


def fetch(raw_dir: Path = RAW, force: bool = False, verbose: bool = True) -> Path:
    """Letölti az Olist adathalmazt, és bemásolja a 9 CSV-t a raw_dir mappába."""
    raw_dir = Path(raw_dir)
    try:
        import kagglehub
    except ImportError as exc:
        raise FetchError(_manual_help(
            "a kagglehub csomag nincs telepítve — indítsd uv run-nal (pl. uv run demo.py), az előkészíti "
            "a rögzített környezetet",
            raw_dir)) from exc

    if verbose:
        print(f"   Letöltés a Kaggle-ről: {DATASET}")
    try:
        src = Path(kagglehub.dataset_download(DATASET, force_download=force))
    except Exception as exc:  # hálózat, Kaggle-hiba, jogosultság
        raise FetchError(_manual_help(f"{type(exc).__name__}: {exc}", raw_dir)) from exc

    found = {f: _find(src, f) for f in SOURCES.values()}
    missing = [f for f, p in found.items() if p is None]
    if missing:
        raise FetchError(_manual_help(
            f"a letöltött mappából hiányzik: {', '.join(missing)} ({src})", raw_dir))

    raw_dir.mkdir(parents=True, exist_ok=True)
    for name, path in found.items():
        shutil.copy2(path, raw_dir / name)

    # A szintetikus jelölőt csak a teljes másolás UTÁN töröljük: ha a másolás
    # félúton elakad, a jelölő megmarad, és a tárház „vegyes forrású adat"
    # hibával leáll — nem fut csendben félig szintetikus adaton.
    marker = raw_dir / SYNTHETIC_MARKER
    if marker.exists():
        marker.unlink()

    if verbose:
        mb = sum((raw_dir / f).stat().st_size for f in SOURCES.values()) / 1e6
        print(f"   {len(found)} CSV a(z) {raw_dir} mappában ({mb:.0f} MB)")
    return raw_dir


def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="Az Olist adathalmaz letöltése a data\\raw mappába")
    ap.add_argument("--raw", type=Path, default=RAW)
    ap.add_argument("--force", action="store_true",
                    help="akkor is újra letölti, ha a valódi adat már megvan")
    args = ap.parse_args()
    if data_state(args.raw) == "valós" and not args.force:
        print(f"A valódi Olist adat már megvan: {args.raw}  (újratöltés: --force)")
        return
    try:
        fetch(args.raw, force=args.force)
    except FetchError as exc:
        print(f"\nHIBA:\n{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
