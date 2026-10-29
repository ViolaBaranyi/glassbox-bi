"""
Üvegdoboz BI — futtatás bármely gépen (Windows, macOS, Linux), egyetlen paranccsal.

A legegyszerűbb a parancsfájl, mert az a uv-t is telepíti, ha még nincs:

    Windows:        indit_felulet.bat          (dupla kattintás is jó)
    macOS, Linux:   sh indit_felulet.sh

Ha a uv már megvan, bármelyik rendszeren:

    uv run python inditas.py                 # előkészít, ami hiányzik, és megnyitja a felületet
    uv run python inditas.py --ellenorzes    # csak megnézi, mi van meg (adatot nem tölt le)
    uv run python inditas.py --help          # a többi kapcsoló

Sima `python inditas.py` is működik: ha van uv a gépen, átadja neki a futtatást.

Lépések:
  1. Gép és környezet: Python 3.14 és a rögzített csomagok (uv.lock). macOS-en a LightGBM-hez
     a libomp, Linuxon a libgomp kell.
  2. Adat: a valódi Olist-adat a Kaggle-ről (kb. 45 MB, fiók nem kell). Internet nélkül:
     --szintetikus.
  3. Tárház: DuckDB. Csak akkor épül újra, ha hiányzik, vagy az adat újabb nála.
  4. Modellek: a négy modell egyszeri betanítása (kb. fél perc), utána gyorsítótárból.
  5. Nyelvi modell (nem kötelező): Ollama és a qwen3.5:4b. Nélküle a szabad szöveges fülön a
     bemutató mód a mérés rögzített válaszait mutatja; minden más oldal működik.
  6. Felület: szabad portot keres (8501-től), és megnyitja a böngészőben.

A fájl eleje szándékosan csak a Python saját könyvtárát használja, hogy régebbi Pythonnal is
el tudja mondani, mi hiányzik.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGET_PYTHON = (3, 14)
REEXEC_FLAG = "UVEGDOBOZ_INDITAS_UV"        # végtelen ciklus ellen: egyszer adjuk át a uv-nek
PACKAGES = ("duckdb", "lightgbm", "sklearn", "pandas", "pyarrow", "shap", "streamlit", "sqlglot",
            "kagglehub")
OLLAMA_DOWNLOAD = "https://ollama.com/download"
UV_INSTALL = {
    "Windows": 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"',
    "other": "curl -LsSf https://astral.sh/uv/install.sh | sh",
}


# ------------------------------------------------------------------ kiírás
def say(msg: str = "") -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:                      # régi Windows-konzol, nem UTF-8-as kimenet
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def step(i: int, n: int, title: str) -> None:
    say(f"\n[{i}/{n}] {title}")


def stop(msg: str) -> int:
    say("\n" + msg)
    return 1


# ------------------------------------------------------------- környezet
def in_project_env(prefix: str | None = None, root: Path = ROOT) -> bool:
    """A projekt saját környezetében (.venv) fut-e ez a Python?"""
    venv = root / ".venv"
    try:
        return Path(prefix or sys.prefix).resolve() == venv.resolve()
    except OSError:
        return False


def find_uv() -> str | None:
    found = shutil.which("uv")
    if found:
        return found
    for cand in (Path.home() / ".local" / "bin" / "uv", Path.home() / ".local" / "bin" / "uv.exe",
                 Path.home() / ".cargo" / "bin" / "uv", Path.home() / ".cargo" / "bin" / "uv.exe"):
        if cand.exists():
            return str(cand)
    return None


def hand_over_to_uv(argv: list[str]) -> int | None:
    """Ha nem a projekt környezetében futunk, és van uv, a uv futtassa (az előkészíti a
    környezetet a rögzített csomagokkal). None: maradunk ebben a Pythonban."""
    if in_project_env() or os.environ.get(REEXEC_FLAG):
        return None
    uv = find_uv()
    if not uv:
        return None
    env = dict(os.environ, **{REEXEC_FLAG: "1"})
    env.pop("VIRTUAL_ENV", None)                   # egy bekapcsolt régi környezet ne zavarjon
    say("A futtatást a uv-nek adom át (a rögzített környezetben fut)…")
    try:
        return subprocess.call([uv, "run", "python", str(ROOT / "inditas.py"), *argv], cwd=ROOT, env=env)
    except KeyboardInterrupt:
        return 0


def openmp_hint(system: str) -> str:
    if system == "Darwin":
        return ("A LightGBM-hez macOS-en a libomp kell: brew install libomp\n"
                "(Homebrew nélkül előbb: https://brew.sh)")
    if system == "Linux":
        return ("A LightGBM-hez Linuxon a libgomp kell: sudo apt install libgomp1 "
                "(Fedora: sudo dnf install libgomp)")
    return ""


def check_platform() -> tuple[bool | None, str]:
    system, machine = platform.system(), platform.machine().lower()
    name = {"Darwin": "macOS", "Windows": "Windows", "Linux": "Linux"}.get(system, system)
    if (system, machine) in {("Windows", "amd64"), ("Windows", "x86_64"), ("Linux", "x86_64"),
                             ("Linux", "amd64"), ("Darwin", "arm64"), ("Darwin", "x86_64")}:
        return True, f"{name} {machine}"
    if (system, machine) in {("Linux", "aarch64"), ("Linux", "arm64")}:
        return None, f"{name} {machine}: a csomagok elérhetők, de ezen a gépfajtán nem próbáltuk"
    return False, (f"{name} {machine}: nem támogatott (Windows ARM-on egyes csomagokhoz nincs kész "
                   "telepítőcsomag). Támogatott: Windows x64, macOS (Apple Silicon és Intel), Linux x64.")


def check_python() -> tuple[bool | None, str]:
    v = sys.version_info
    text = f"Python {v[0]}.{v[1]}.{v[2]}"
    if v[:2] == TARGET_PYTHON:
        return True, text
    return None, (f"{text} — a projekt a {TARGET_PYTHON[0]}.{TARGET_PYTHON[1]}-re van rögzítve; más "
                  "verzióval futhat, de a számok bitre azonossága csak a rögzített környezetben "
                  "garantált (uv run python inditas.py)")


def check_packages() -> tuple[bool, str]:
    missing, broken = [], []
    for name in PACKAGES:
        try:
            __import__(name)
        except ImportError as exc:
            (broken if "libomp" in str(exc) or "libgomp" in str(exc) else missing).append(name)
        except OSError:                             # pl. a LightGBM nem találja az OpenMP-t
            broken.append(name)
    if broken:
        return False, f"nem tölthető be: {', '.join(broken)}. {openmp_hint(platform.system())}".strip()
    if missing:
        how = ("uv run python inditas.py" if find_uv() else
               f"telepítsd a uv-t ({UV_INSTALL['Windows' if os.name == 'nt' else 'other']}), "
               "utána: uv run python inditas.py")
        return False, f"hiányzó csomagok: {', '.join(missing)}. Indítsd így: {how}"
    import streamlit
    import lightgbm
    import duckdb
    return True, f"streamlit {streamlit.__version__}, lightgbm {lightgbm.__version__}, duckdb {duckdb.__version__}"


# -------------------------------------------------------------- adat, tárház
def raw_newest(raw_dir: Path) -> float:
    files = list(raw_dir.glob("*.csv"))
    return max((f.stat().st_mtime for f in files), default=0.0)


def warehouse_state(db_path: Path, raw_dir: Path) -> tuple[str, str]:
    """('nincs' | 'elavult' | 'zarolt' | 'rendben', magyarázat)."""
    if not db_path.exists():
        return "nincs", "még nincs felépítve"
    if raw_newest(raw_dir) > db_path.stat().st_mtime:
        return "elavult", "az adat újabb, mint a tárház — újraépül"
    try:
        from data.db import WarehouseUnavailable, connect
        con = connect(db_path, read_only=True)
    except WarehouseUnavailable as exc:
        return "zarolt", str(exc).splitlines()[0]
    try:
        row = con.execute("SELECT adatforras, epitve FROM meta_build").fetchone()
        n = con.execute("SELECT count(*) FROM fact_orders").fetchone()[0]
    except Exception:                               # régebbi szerkezetű tárház
        return "elavult", "régebbi szerkezetű tárház — újraépül"
    finally:
        con.close()
    return "rendben", f"{n:,} rendelés, adatforrás: {row[0]}".replace(",", " ", 1)


def prepare_data(synthetic: bool, raw_dir: Path) -> tuple[bool, str]:
    from data.fetch_olist import FetchError, data_state, fetch
    state = data_state(raw_dir)
    if state == "valós":
        if synthetic:
            return True, "valódi Olist-adat van a data/raw mappában — azt használjuk (a --szintetikus itt nem kell)"
        return True, "valódi Olist-adat (data/raw)"
    if synthetic:
        if state == "szintetikus":
            return True, "szintetikus adat (nem a valóság: csak a gépezet kipróbálására)"
        from data.make_synthetic import generate
        say("   Szintetikus, Olist-alakú adat generálása…")
        generate(out_dir=raw_dir)
        return True, "szintetikus adat (nem a valóság: csak a gépezet kipróbálására)"
    say("   A valódi Olist-adat letöltése a Kaggle-ről (kb. 45 MB, Kaggle-fiók nem kell)…")
    try:
        fetch(raw_dir)
    except FetchError as exc:
        if state == "szintetikus":
            say(f"   ! A letöltés nem sikerült, a meglévő szintetikus adattal megyünk tovább.\n   {exc}")
            return True, "szintetikus adat (a valódi letöltése nem sikerült)"
        return False, (f"{exc}\n\nA felület internet nélkül, generált adattal is kipróbálható: "
                       "uv run python inditas.py --szintetikus")
    return True, "valódi Olist-adat (most letöltve)"


# --------------------------------------------------------------- nyelvi modell
def llm_status() -> tuple[bool, str, str]:
    """(elérhető-e, magyarázat, modellnév). A naplóba nem ír."""
    from narrative.client import LlmClient, load_config
    cfg = load_config()
    ok, msg = LlmClient(cfg, log_path=None).status()
    return ok, msg, cfg.modell


def ollama_hint() -> str:
    if platform.system() == "Linux":
        return "Linuxon egy paranccsal: curl -fsSL https://ollama.com/install.sh | sh"
    return f"Telepítő: {OLLAMA_DOWNLOAD} (utána a háttérben fut)"


def ask_yes(question: str) -> bool:
    if not sys.stdin or not sys.stdin.isatty():
        return False
    try:
        return input(f"   {question} [i/N] ").strip().lower() in ("i", "igen", "y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


# ------------------------------------------------------------------- port
def port_free(port: int, host: str = "localhost") -> bool:
    """Szabad-e a port? Két próba kell: ha valaki figyel rajta, a kapcsolódás sikerül; de egy
    olyan program, amely figyel, de nem fogad (vagy betelt a várakozási sora), Windowson
    visszautasítja a kapcsolódást — ezért a lefoglalást is megpróbáljuk."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        if s.connect_ex((host, port)) == 0:
            return False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
    except OSError:
        return False
    return True


def find_free_port(start: int = 8501, tries: int = 20) -> int | None:
    for port in range(start, start + tries):
        if port_free(port):
            return port
    return None


# ------------------------------------------------------------------- fő
def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="inditas.py",
        description="Üvegdoboz BI: előkészíti, ami hiányzik, és elindítja a felületet "
                    "(Windows, macOS, Linux).")
    ap.add_argument("--ellenorzes", action="store_true",
                    help="csak megnézi, mi van meg és mi hiányzik; adatot nem tölt le, "
                         "a tárházhoz és a modellekhez nem nyúl")
    ap.add_argument("--szintetikus", action="store_true",
                    help="internet nélkül: generált, Olist-alakú adattal (nem a valóság)")
    ap.add_argument("--modell", action="store_true",
                    help="ha fut az Ollama, de a nyelvi modell nincs letöltve, kérdés nélkül letölti (kb. 3,4 GB)")
    ap.add_argument("--tesztek", action="store_true",
                    help="indítás előtt lefuttatja a teljes tesztsort is (néhány perc)")
    ap.add_argument("--ujraepites", action="store_true", help="a tárházat akkor is újraépíti, ha rendben van")
    ap.add_argument("--port", type=int, default=8501, help="a felület portja (ha foglalt, a következő szabadot keresi)")
    ap.add_argument("--nincs-bongeszo", action="store_true", help="nem nyitja meg a böngészőt (pl. távoli gépen)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parse_args(argv)
    os.chdir(ROOT)
    handed = hand_over_to_uv(argv)
    if handed is not None:
        return handed
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    check = args.ellenorzes
    n = 6
    say("Üvegdoboz BI — " + ("ellenőrzés (adatot nem tölt le, a tárházhoz és a modellekhez nem nyúl)"
                             if check else "indítás"))
    problems = 0

    # 1. gép és környezet
    step(1, n, "Gép és környezet")
    ok, msg = check_platform()
    say(f"   {'rendben' if ok else ('figyelem' if ok is None else 'HIBA')}: {msg}")
    if ok is False:
        return stop("Ezen a gépen a program nem futtatható.")
    ok, msg = check_python()
    say(f"   {'rendben' if ok else 'figyelem'}: {msg}")
    ok, msg = check_packages()
    say(f"   {'rendben' if ok else 'HIBA'}: {msg}")
    if not ok:
        return stop("Előbb a csomagokat kell rendbe tenni (lásd fent).")
    free_gb = shutil.disk_usage(ROOT).free / 1e9
    say(f"   {'rendben' if free_gb >= 1 else 'figyelem'}: szabad hely {free_gb:.1f} GB"
        + ("" if free_gb >= 1 else " (az adathoz és a modellekhez kb. 0,5 GB kell)"))

    from data.build_warehouse import DB_PATH, RAW

    # 2. adat
    step(2, n, "Adat")
    if check:
        from data.fetch_olist import data_state
        state = data_state(RAW)
        say({"valós": "   rendben: valódi Olist-adat (data/raw)",
             "szintetikus": "   figyelem: szintetikus adat (a valódihoz: uv run python inditas.py)",
             "nincs": "   hiányzik: első indításkor letöltjük (kb. 45 MB, internet kell)"}[state])
        problems += state == "nincs"
    else:
        ok, msg = prepare_data(args.szintetikus, RAW)
        if not ok:
            return stop(msg)
        say(f"   rendben: {msg}")

    # 3. tárház
    step(3, n, "Tárház (DuckDB)")
    wstate, wmsg = warehouse_state(DB_PATH, RAW) if RAW.exists() else ("nincs", "még nincs adat")
    if wstate == "zarolt":
        say(f"   HIBA: {wmsg}")
        return stop("Zárd be a programot, amely a tárházat nyitva tartja (pl. DBeaver), és indítsd újra.")
    if check:
        say(f"   {'rendben' if wstate == 'rendben' else 'hiányzik'}: {wmsg}")
        problems += wstate != "rendben"
    elif wstate != "rendben" or args.ujraepites:
        say(f"   {wmsg if wstate != 'rendben' else 'újraépítés (--ujraepites)'}…")
        from data.build_warehouse import ValidationError, build
        from data.db import WarehouseUnavailable
        try:
            build(RAW, DB_PATH, verbose=False)
        except (ValidationError, WarehouseUnavailable) as exc:
            return stop(f"A tárház nem épült fel:\n{exc}")
        say(f"   rendben: {warehouse_state(DB_PATH, RAW)[1]}")
    else:
        say(f"   rendben: {wmsg}")

    # 4. modellek
    step(4, n, "Modellek (LightGBM, logisztikus regresszió, döntési fa, véletlen erdő)")
    from xai.models import CACHE
    if check:
        say("   rendben: van gyorsítótár" if CACHE.exists() else
            "   hiányzik: első indításkor betanítjuk (kb. fél perc)")
        problems += not CACHE.exists()
    else:
        from xai.models import load_bundle
        t = time.time()
        say("   A modellek betöltése (első alkalommal betanítás, kb. fél perc)…")
        bundle = load_bundle(verbose=False)
        say(f"   rendben: {bundle.info['lightgbm_fak']} fás LightGBM és a három referencia-modell "
            f"({time.time() - t:.0f} mp)")

    # 5. nyelvi modell
    step(5, n, "Nyelvi modell (nem kötelező; a szabad szöveges kérdéshez)")
    ok, msg, model = llm_status()
    if ok:
        say(f"   rendben: {msg}")
    else:
        say(f"   nincs: {msg}")
        has_cli = shutil.which("ollama") is not None
        if not has_cli:
            say(f"   {ollama_hint()}")
        elif "nincs letöltve" in msg and not check:
            if args.modell or ask_yes(f"Letöltsem most a {model} modellt (kb. 3,4 GB)?"):
                subprocess.call(["ollama", "pull", model])
                ok, msg, _ = llm_status()
                say(f"   {'rendben' if ok else 'nincs'}: {msg}")
        if not ok:
            say("   Nélküle is működik minden oldal; a szabad szöveges fülön a bemutató mód a mérés "
                "rögzített válaszait mutatja.")

    # tesztek (kérésre)
    if args.tesztek and not check:
        say("\nTesztek (néhány perc)…")
        code = subprocess.call([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=ROOT)
        if code != 0:
            return stop("Legalább egy teszt elbukott — a kimenet fent látható.")

    # 6. felület
    step(6, n, "Felület")
    port = find_free_port(args.port)
    if port is None:
        return stop(f"Nincs szabad port {args.port} és {args.port + 19} között; adj meg mást: --port 9000")
    if check:
        say(f"   rendben: a felület a http://localhost:{port} címen indulna")
        say("\nÖsszegzés: " + ("minden megvan." if not problems else
                               f"{problems} dolog hiányzik — a sima indítás (kapcsoló nélkül) előkészíti."))
        return 0
    if port != args.port:
        say(f"   A {args.port}-es port foglalt (talán már fut egy felület) — a {port}-est használjuk.")
    say(f"   A felület: http://localhost:{port}   Leállítás: Ctrl+C (vagy zárd be az ablakot).")
    cmd = [sys.executable, "-m", "ui", f"--server.port={port}"]
    if args.nincs_bongeszo:
        cmd.append("--server.headless=true")
    try:
        return subprocess.call(cmd, cwd=ROOT)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
