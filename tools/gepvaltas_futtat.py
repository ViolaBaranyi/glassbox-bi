"""
A K1 géphatás futtatója (docs/k1_protokoll_gepvaltas.json) — minden gépen ugyanaz a parancs.

    tools\\gepvaltas.bat felvesz GÉP          # a gép felvétele: docs/gepvaltas_gepek/GÉP.json (utána commit + push)
    tools\\gepvaltas.bat GÉP                  # a gépen még hiányzó futások, körökben (minden konfiguráció 3×)
    tools\\gepvaltas.bat GÉP --allapot        # mi van meg, mi hiányzik, mi félbehagyott (modell nélkül)
    tools\\gepvaltas.bat GÉP --csak m1-4b     # csak a megadott pár(ok)

Indulás előtt mindent ellenőriz, hogy egy éjszakai sor ne órák múlva akadjon el: a protokoll és a gép
fájlja commitolva és változatlan; ez tényleg az a gép (a gépnév egyezik); a tárház tartalma a
protokollé; minden kellő modellfájl a protokoll szerinti; és nem fut épp másik mérés ezen a gépen.

Egy futás: a saját kódjával (v3, v4: külön munkamappa, git worktree, változatlanul; v5: ez a mappa), a
saját protokolljával és kérdéssorával. Ha félbeszakad (áramszünet, bezárt ablak), a következő indításkor
magától folytatja (--folytat), nem kezd újat; a modellhibás sorokat a mérőprogram folytatáskor újra
futtatja. A kész futás a logs/meres/<GÉP>/ mappába kerül, mellé a gep.json: a gép adatai, az ollama
változata, a modell a futás után a videókártyán vagy a processzoron volt-e (`ollama ps`), és minden
indítás ideje. Futás közben a gép nem alszik el (Windows), de a fedél lecsukása ettől még altathat.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from narrative import meres  # noqa: E402

_spec = importlib.util.spec_from_file_location("k1_gepvaltas", ROOT / "tools" / "k1_gepvaltas.py")
gv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gv)

PROTOKOLL = ROOT / "docs" / "k1_protokoll_gepvaltas.json"
NEV = re.compile(r"^[a-z0-9][a-z0-9_-]{1,30}$")
FELBEHAGYOTT_PERC = 15

# Mi kerül a futás kódja mellé, és hogyan indul. A protokollt és a kérdéssort ebből a mappából másolja
# (a v3 és a v4 kódhoz); a futás előtt ellenőrzi, hogy a kód mappájában a pár szerinti ujjlenyomatuk van.
RECEPTEK: dict[str, dict] = {
    "m1-4b": {"kod": "v3", "masol": {"docs/k1_protokoll.json": "docs/k1_protokoll.json"}, "protokoll": "docs/k1_protokoll.json"},
    "m1-2b": {"kod": "v3", "masol": {"docs/k1_protokoll.json": "docs/k1_protokoll.json"}, "protokoll": "docs/k1_protokoll.json"},
    "m1-9b": {"kod": "v3", "masol": {"docs/k1_protokoll_v1_9b.json": "docs/k1_protokoll.json"}, "protokoll": "docs/k1_protokoll.json"},
    "m2-v3-4b": {"kod": "v3", "masol": {"docs/k1_protokoll_v2.json": "docs/k1_protokoll.json"}, "protokoll": "docs/k1_protokoll.json"},
    "m2-v4-4b": {"kod": "v4", "masol": {"docs/k1_protokoll_v2.json": "docs/k1_protokoll_v2.json"},
                 "protokoll": "docs/k1_protokoll_v2.json", "kapcsolo": True},
    "m2-v4-2b": {"kod": "v4", "masol": {"docs/k1_protokoll_v2.json": "docs/k1_protokoll_v2.json"},
                 "protokoll": "docs/k1_protokoll_v2.json", "kapcsolo": True},
    "m2-v4-9b": {"kod": "v4", "masol": {"docs/k1_protokoll_v2_9b.json": "docs/k1_protokoll_v2_9b.json"},
                 "protokoll": "docs/k1_protokoll_v2_9b.json", "kapcsolo": True},
    "m3-v5-4b": {"kod": "v5", "masol": {}, "protokoll": "docs/k1_protokoll_v3.json", "kapcsolo": True},
    "m3-v4-4b": {"kod": "v4", "masol": {}, "szarmaztat": "docs/k1_protokoll_v3.json",
                 "protokoll": "docs/k1_protokoll_v3.json", "kapcsolo": True},
    "m3-v5-9b": {"kod": "v5", "masol": {}, "protokoll": "docs/k1_protokoll_v3.json", "kapcsolo": True},
}


class Megall(Exception):
    """A futtató megáll; az üzenet megmondja, mit kell tenni."""


# ------------------------------------------------------------------ a gép adatai
def _env() -> dict:
    env = dict(os.environ)
    env.pop("VIRTUAL_ENV", None)      # a belső `uv run` a kód saját környezetét használja
    return env


def _ki(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> str | None:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, env=_env())
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout.strip() if p.returncode == 0 else None


def gepnev() -> str:
    return os.environ.get("COMPUTERNAME") or platform.node()


def ollama_list(text: str | None) -> dict[str, str]:
    """Az `ollama list` kimenetéből: {modell: a modellfájl azonosítója (12 hexa)}."""
    out = {}
    for line in (text or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and re.fullmatch(r"[0-9a-f]{12}", parts[1]):
            out[parts[0]] = parts[1]
    return out


def gep_adatok() -> dict:
    """A gép leírása a nyilvántartáshoz és a gep.json-hoz (ami nem olvasható ki, az üres marad)."""
    d: dict = {"gepnev": gepnev(), "rendszer": platform.platform(), "processzor": None, "memoria_gb": None,
               "videokartyak": [], "egyeb_kijelzo": None}
    if os.name == "nt":
        ps = ("$p=(Get-CimInstance Win32_Processor | Select-Object -First 1).Name;"
              "$m=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory;"
              "$v=(Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }) -join '; ';"
              "ConvertTo-Json @{p=$p;m=$m;v=$v}")
        raw = _ki(["powershell", "-NoProfile", "-Command", ps])
        try:
            j = json.loads(raw or "")
            d["processzor"], d["egyeb_kijelzo"] = (j.get("p") or "").strip() or None, j.get("v") or None
            d["memoria_gb"] = round(int(j["m"]) / 2**30, 1) if j.get("m") else None
        except (ValueError, TypeError):
            pass
    else:
        try:
            cpu = Path("/proc/cpuinfo").read_text()
            d["processzor"] = next((ln.split(":", 1)[1].strip() for ln in cpu.splitlines() if ln.startswith("model name")), None)
            d["memoria_gb"] = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
        except (OSError, ValueError, AttributeError):
            pass
    smi = _ki(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"])
    d["videokartyak"] = [ln.strip() for ln in (smi or "").splitlines() if ln.strip()]
    d["osztaly"] = "videokartya" if d["videokartyak"] else "processzor"
    ver = (_ki(["ollama", "--version"]) or "").splitlines()
    d["ollama"] = ver[-1].strip() if ver else None
    d["modellek"] = ollama_list(_ki(["ollama", "list"]))
    return d


def tarhaz_ujjlenyomat(db: Path) -> str:
    """A tárház tartalmának ujjlenyomata: minden tábla oszlopai és sorai, rendezve — az építés ideje
    (meta_build.epitve) nélkül, mert csak az más két azonos építésben."""
    import duckdb

    h = hashlib.sha256()
    con = duckdb.connect(str(db), read_only=True)
    try:
        tables = [t for (t,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main' "
                                            "AND table_type='BASE TABLE' ORDER BY 1").fetchall()]
        for t in tables:
            cols = con.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='main' "
                               "AND table_name=? ORDER BY ordinal_position", [t]).fetchall()
            keep = [c for c, _ in cols if not (t == "meta_build" and c == "epitve")]
            h.update(repr((t, [c for c in cols if c[0] in keep])).encode())
            cur = con.execute(f'SELECT {", ".join(chr(34) + c + chr(34) for c in keep)} FROM "{t}" ORDER BY ALL')
            while batch := cur.fetchmany(20000):
                for row in batch:
                    h.update(repr(row).encode())
                    h.update(b"\n")
    finally:
        con.close()
    return h.hexdigest()


def futo_meresek() -> list[str]:
    """Fut-e most mérés ezen a gépen (bármelyik munkamappából): a narrative.meres folyamatai."""
    me = os.getpid()
    if os.name == "nt":
        ps = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*narrative.meres*' -and "
              "$_.CommandLine -notlike '*Get-CimInstance*' } | ForEach-Object { \"$($_.ProcessId) $($_.CommandLine)\" }")
        lines = (_ki(["powershell", "-NoProfile", "-Command", ps]) or "").splitlines()
    else:
        lines = []
        for p in Path("/proc").glob("[0-9]*/cmdline"):
            try:
                cmd = p.read_bytes().replace(b"\0", b" ").decode(errors="replace")
            except OSError:
                continue
            if "narrative.meres" in cmd:
                lines.append(f"{p.parent.name} {cmd}")
    return [ln for ln in lines if ln.strip() and ln.split()[0] != str(me)]


def ebren_tart(be: bool) -> None:
    """Windowson a gép nem alszik el, amíg a futtató dolgozik (a képernyő kikapcsolhat)."""
    if os.name != "nt":
        return
    import ctypes
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if be else 0))


# ------------------------------------------------------------------ a futtató
class Futtato:
    def __init__(self, gep: str, root: Path = ROOT, protocol_path: Path | None = None, gepadatok=gep_adatok,
                 futo=futo_meresek, kimenet=_ki, parancs=None):
        self.gep, self.root = gep, root
        self.protocol_path = protocol_path or root / "docs" / "k1_protokoll_gepvaltas.json"
        self.protocol = json.loads(self.protocol_path.read_text(encoding="utf-8"))
        self.pairs = {p["id"]: p for p in self.protocol["parok"]}
        if gep in (self.protocol.get("kimarad") or {}):
            raise Megall(f"a protokoll szerint a(z) {gep} gép kimarad a géphatás-összevetésből: ezen nem futtatunk")
        self.meres_dir = root / "logs" / "meres"
        self.gepek_dir = root / "docs" / "gepvaltas_gepek"
        self.gepadatok, self.futo, self.kimenet = gepadatok, futo, kimenet
        self.parancs = parancs or self._popen
        self._kesz_kod: set[str] = set()
        self._adat: dict | None = None
        self._tarhaz: dict[str, str] = {}

    # ---------------------------------------------------------- segédek
    def adat(self) -> dict:
        if self._adat is None:
            self._adat = self.gepadatok()
        return self._adat

    def git(self, *args: str, cwd: Path | None = None) -> str | None:
        return self.kimenet(["git", *args], cwd or self.root)

    def committed(self, path: Path) -> bool:
        rel = path.relative_to(self.root).as_posix()
        return (self.git("ls-files", "--error-unmatch", rel) is not None
                and self.git("diff", "--quiet", "HEAD", "--", rel) is not None)

    def registry(self) -> Path:
        return self.gepek_dir / f"{self.gep}.json"

    def tarhaz(self, db: Path) -> str:
        key = str(db.resolve())
        if key not in self._tarhaz:
            self._tarhaz[key] = tarhaz_ujjlenyomat(db)
        return self._tarhaz[key]

    def kod_mappa(self, kod: str) -> Path:
        k = self.protocol["kodok"][kod]
        return self.root if k["mappa"] == "." else self.root / k["mappa"]

    # ---------------------------------------------------------- állapot
    def helyek(self) -> dict:
        _, hely, _ = gv.slots(self.protocol, self.meres_dir, self.gepek_dir, (self.gep,))
        return {pid: v[self.gep] for pid, v in hely.items()}

    def terv(self, csak: list[str] | None = None) -> list[str]:
        """A gépen még hátralévő futások, körökben: előbb minden pár az első futásáig, aztán a másodikig, a
        harmadikig (a protokoll sorrendjében). Egy pár annyiszor szerepel, ahány teljes futása hiányzik."""
        n = int(self.protocol["ismetles_futas"]["szam"])
        h = self.helyek()
        have = {}
        for pid in self.pairs:
            u = h[pid]["uj"]
            if u["allapot"] == "hiba":
                raise Megall(f"{pid}: {u['megjegyzes']}")
            have[pid] = len(u["futasok"])
        return [pid for kor in range(1, n + 1) for pid in self.pairs
                if (not csak or pid in csak) and have[pid] < kor]

    def felbehagyott(self, pid: str, code: Path) -> Path | None:
        """A pár félbehagyott futása a kód mappájában (logs/meres), ha van — ezt kell folytatni."""
        par = self.pairs[pid]
        kuszob = int(self.protocol["gep_azonositas"]["kuszob_ms"])
        named = {n for p in self.pairs.values() for n in (p.get("korabbi") or {}).values() if n}
        cands = [r for r in gv.scan(code / "logs" / "meres", kuszob)
                 if gv.fits(r, par) and not r["teljes"] and r["path"].name not in named]
        if not cands:
            return None
        if len(cands) > 1:
            raise Megall(f"{pid}: több félbehagyott futás is van ({', '.join(r['path'].name for r in cands)}) — "
                         "szólj, ne indíts újat.")
        run = cands[0]["path"]
        gj = run / "gep.json"
        if not gj.exists():
            raise Megall(f"{pid}: a {run} félbehagyott futás mellett nincs gep.json, így nem tudni, melyik gépen "
                         "indult — szólj, ne indíts újat.")
        g = json.loads(gj.read_text(encoding="utf-8"))
        if g.get("gep") != self.gep or any(i.get("gepnev") != self.adat()["gepnev"] for i in g.get("inditasok", [])):
            raise Megall(f"{pid}: a {run} félbehagyott futást másik gép kezdte ({g.get('gep')}) — szólj.")
        return run

    # ---------------------------------------------------------- ellenőrzések
    def elofeltetelek(self, pids: list[str]) -> list[str]:
        out = []
        if not self.committed(self.protocol_path):
            out.append("a protokoll (docs/k1_protokoll_gepvaltas.json) nincs commitolva, vagy azóta változott")
        reg = self.registry()
        if not reg.exists():
            out.append(f"a gép még nincs felvéve: tools\\gepvaltas.bat felvesz {self.gep}, utána commit + push")
            return out
        if not self.committed(reg):
            out.append(f"a gép fájlja ({reg.relative_to(self.root).as_posix()}) nincs commitolva, vagy azóta változott")
        r = json.loads(reg.read_text(encoding="utf-8"))
        if r.get("gepnev") != self.adat()["gepnev"]:
            out.append(f"ez nem a(z) {self.gep} gép: a gépnév {self.adat()['gepnev']}, a felvételkor {r.get('gepnev')} volt")
        db = self.root / "data" / "warehouse.duckdb"
        want = self.protocol["tarhaz"]["ujjlenyomat"]
        if not db.exists():
            out.append("nincs tárház (data/warehouse.duckdb): uv run python inditas.py")
        elif self.tarhaz(db) != want:
            out.append("a tárház tartalma nem a protokoll szerinti (data/warehouse.duckdb) — szólj")
        for kod in sorted({RECEPTEK[p]["kod"] for p in pids} - {"v5"}):
            wdb = self.kod_mappa(kod) / "data" / "warehouse.duckdb"
            if wdb.exists() and self.tarhaz(wdb) != want:
                out.append(f"a {self.kod_mappa(kod).name} munkamappa tárháza nem a protokoll szerinti — töröld a "
                           f"{wdb.relative_to(self.root)} fájlt, a futtató újra bemásolja")
        have = self.adat()["modellek"]
        for m in sorted({self.pairs[p]["modell"] for p in pids}):
            want_id = self.protocol["modellfajlok"][m]
            if m not in have:
                out.append(f"hiányzik a modell: ollama pull {m} (a protokoll szerinti fájl: {want_id})")
            elif have[m] != want_id:
                out.append(f"a {m} modellfájl más ({have[m]}), mint a protokollé ({want_id}) — szólj")
        others = self.futo()
        if others:
            out.append("most is fut mérés ezen a gépen — várd meg, hogy véget érjen:\n      " + "\n      ".join(others))
        return out

    # ---------------------------------------------------------- futás
    def elokeszit(self, pid: str) -> tuple[Path, list[str]]:
        par, rec = self.pairs[pid], RECEPTEK[pid]
        kod = rec["kod"]
        code = self.kod_mappa(kod)
        if kod != "v5" and kod not in self._kesz_kod:
            k = self.protocol["kodok"][kod]
            if not code.exists():
                self.git("worktree", "prune")
                if self.git("worktree", "add", k["mappa"], k["commit"]) is None:
                    raise Megall(f"a {k['mappa']} munkamappa nem jött létre (git worktree add {k['mappa']} {k['commit']})")
            if self.git("rev-parse", "HEAD", cwd=code) != k["commit"]:
                raise Megall(f"a {k['mappa']} munkamappa nem a {kod} kód commitján áll ({k['commit'][:12]})")
            wdb = code / "data" / "warehouse.duckdb"
            if not wdb.exists():
                shutil.copy2(self.root / "data" / "warehouse.duckdb", wdb)
            if self.parancs(["uv", "sync"], code) != 0:
                raise Megall(f"uv sync nem sikerült a {k['mappa']} mappában")
            self._kesz_kod.add(kod)
        if kod != "v5":
            for src, dst in {**rec["masol"], par["kerdessor"]["fajl"]: par["kerdessor"]["fajl"]}.items():
                (code / dst).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.root / src, code / dst)
            if rec.get("szarmaztat"):
                if self.parancs(["uv", "run", "python", "tools/v4_protokoll.py", str(code / rec["szarmaztat"])],
                                self.root) != 0:
                    raise Megall("a v4 protokoll származtatása nem sikerült (tools/v4_protokoll.py)")
        for rel, want, what in ((rec["protokoll"], par["futas_protokoll"]["sha256"], "protokoll"),
                                (par["kerdessor"]["fajl"], par["kerdessor"]["sha256"], "kérdéssor")):
            if meres.sha256_text(code / rel) != want:
                raise Megall(f"{pid}: a {what} ({rel}) a kód mappájában nem a pár szerinti")
        cmd = ["uv", "run", "python", "-m", "narrative.meres"]
        if rec.get("kapcsolo"):
            cmd += ["--protokoll", rec["protokoll"]]
        return code, cmd + ["--modell", par["modell"]]

    def _popen(self, cmd: list[str], cwd: Path, figyel=None) -> int:
        """Egy parancs a konzolra írva; ha `figyel` adott, futás közben kétmásodpercenként meghívja."""
        p = subprocess.Popen(cmd, cwd=cwd, env=_env())
        try:
            while p.poll() is None:
                if figyel:
                    figyel()
                time.sleep(2)
        except KeyboardInterrupt:
            p.wait()
            raise
        if figyel:
            figyel()
        return p.returncode

    def _gep_json(self, run: Path, pid: str, code: Path, cmd: list[str], start: dict) -> None:
        gj = run / "gep.json"
        d = json.loads(gj.read_text(encoding="utf-8")) if gj.exists() else {
            "gep": self.gep, "par": pid, **{k: v for k, v in self.adat().items() if k != "modellek"},
            "modellfajl": self.adat()["modellek"].get(self.pairs[pid]["modell"]),
            "tarhaz": self.protocol["tarhaz"]["ujjlenyomat"], "kod_mappa": code.relative_to(self.root).as_posix() or ".",
            "parancs": cmd, "futtato": meres.sha256_text(Path(__file__)), "inditasok": []}
        ind = d["inditasok"]
        if not ind or ind[-1].get("azon") != start["azon"]:
            ind.append(dict(start))
        else:
            ind[-1].update(start)
        gj.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    def futtat_par(self, pid: str) -> Path:
        code, cmd = self.elokeszit(pid)
        logs = code / "logs" / "meres"
        for probalkozas in range(1, 4):
            run = self.felbehagyott(pid, code)
            before = {d.name for d in logs.iterdir()} if logs.is_dir() else set()
            full = cmd + (["--folytat", str(run)] if run else [])
            start = {"azon": f"{time.time_ns():x}", "kezdes": datetime.now().isoformat(timespec="seconds"),
                     "gepnev": self.adat()["gepnev"], "folytatas": bool(run)}
            found: dict = {"run": run}

            def figyel():
                if found["run"] is None and logs.is_dir():
                    new = [logs / n for n in {d.name for d in logs.iterdir()} - before if (logs / n / "fej.json").exists()]
                    if len(new) == 1:
                        found["run"] = new[0]
                if found["run"] is not None and not start.get("_irva"):
                    self._gep_json(found["run"], pid, code, full, {k: v for k, v in start.items() if k != "_irva"})
                    start["_irva"] = True

            print(f"\n=== {self.gep} · {pid} ({self.pairs[pid]['modell']}, {RECEPTEK[pid]['kod']} kód)"
                  + (f" · folytatás: {run.name}" if run else "") + " ===", flush=True)
            rc = self.parancs(full, code, figyel)
            run = found["run"]
            if run is None:
                raise Megall(f"{pid}: a mérés nem indult el (kilépési kód {rc}) — lásd fent")
            start.pop("_irva", None)
            self._gep_json(run, pid, code, full, {**start, "vege": datetime.now().isoformat(timespec="seconds"),
                                                   "kilepes": rc})
            kuszob = int(self.protocol["gep_azonositas"]["kuszob_ms"])
            c = next(r for r in gv.scan(logs, kuszob) if r["path"] == run)
            if c["teljes"]:
                return self.lezar(pid, run)
            if rc != 0:
                raise Megall(f"{pid}: a mérés megszakadt ({c['kesz']}/{c['kell']}). Indítsd újra ugyanígy: "
                             f"tools\\gepvaltas.bat {self.gep} — onnan folytatja.")
            print(f"{pid}: {c['kesz']}/{c['kell']} kész (modellhibás sorok) — folytatás, {probalkozas + 1}. indítás", flush=True)
        raise Megall(f"{pid}: három indítás után sem teljes — szólj")

    def lezar(self, pid: str, run: Path) -> Path:
        gj = run / "gep.json"
        d = json.loads(gj.read_text(encoding="utf-8"))
        d["ollama_ps_utana"] = self.kimenet(["ollama", "ps"], self.root)
        gj.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        dest = self.meres_dir / self.gep / run.name
        if dest.exists():
            raise Megall(f"{pid}: a {dest} már létezik — szólj")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if run.resolve() != dest.resolve():
            try:
                shutil.move(str(run), str(dest))
            except OSError as exc:
                raise Megall(f"{pid}: a kész futás ({run}) nem került át a {dest} helyre ({exc}). Zárd be, ami "
                             f"nyitva van belőle, és indítsd újra ugyanígy — a kész futást nem futtatja újra.") from exc
        print(f"{pid}: kész → {dest.relative_to(self.root).as_posix()}", flush=True)
        return dest


# ------------------------------------------------------------------ parancsok
def felvesz(gep: str, root: Path = ROOT, gepadatok=gep_adatok) -> Path:
    if not NEV.match(gep):
        raise Megall("a gép neve kisbetű, szám, kötőjel vagy aláhúzás legyen (2–31 karakter), pl. violapc")
    protocol = json.loads((root / "docs" / "k1_protokoll_gepvaltas.json").read_text(encoding="utf-8"))
    if gep in (protocol.get("kimarad") or {}):
        raise Megall(f"a protokoll szerint a(z) {gep} gép kimarad a géphatás-összevetésből, így felvenni sem kell")
    path = root / "docs" / "gepvaltas_gepek" / f"{gep}.json"
    if path.exists():
        raise Megall(f"a(z) {gep} gép már fel van véve ({path.relative_to(root).as_posix()})")
    d = gepadatok()
    want = protocol["gepek"].get(gep, {}).get("osztaly")
    if want and d["osztaly"] != want:
        raise Megall(f"a protokoll szerint a(z) {gep} {gv.OSZTALY[want]}-gép, de ezen a gépen "
                     f"{'van' if d['osztaly'] == 'videokartya' else 'nincs'} NVIDIA-kártya — biztos ez a gép?")
    db = root / "data" / "warehouse.duckdb"
    rec = {"gep": gep, "felveve": datetime.now().isoformat(timespec="seconds"), **d,
           "tarhaz": tarhaz_ujjlenyomat(db) if db.exists() else None}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def _allapot(f: Futtato) -> None:
    n = f.protocol["ismetles_futas"]["szam"]
    print(f"  (új futás: konfigurációnként {n}, körökben; a korábbi, közölt futás külön)")
    for pid, s in f.helyek().items():
        k = s["korabbi"]
        extra = f"   korábbi: {k['futas']['path'].name if k['futas'] else k['megjegyzes']}" if k else ""
        print(f"  {pid:<9} új: {s['uj']['megjegyzes'] or s['uj']['allapot']:<12}{extra}")


def main(argv: list[str] | None = None) -> int:
    from data.db import use_utf8_console
    use_utf8_console()
    ap = argparse.ArgumentParser(description="A K1 géphatás futtatója (docs/k1_protokoll_gepvaltas.json).")
    ap.add_argument("gep", nargs="+", help="a gép neve, vagy: felvesz GÉP")
    ap.add_argument("--allapot", action="store_true", help="csak az állapot, futtatás nélkül")
    ap.add_argument("--csak", nargs="+", metavar="PÁR", help="csak ezek a párok")
    a = ap.parse_args(argv)
    try:
        if a.gep[0] == "felvesz":
            if len(a.gep) != 2:
                raise Megall("használat: tools\\gepvaltas.bat felvesz GÉP")
            p = felvesz(a.gep[1])
            d = json.loads(p.read_text(encoding="utf-8"))
            protocol = json.loads(PROTOKOLL.read_text(encoding="utf-8"))
            warn = []
            if d["tarhaz"] != protocol["tarhaz"]["ujjlenyomat"]:
                warn.append("a tárház (data/warehouse.duckdb) " + ("hiányzik: uv run python inditas.py" if d["tarhaz"] is None
                            else "tartalma nem a protokoll szerinti — szólj, mielőtt futtatsz"))
            for m, want in protocol["modellfajlok"].items():
                if m == "szabaly":
                    continue
                if m not in d["modellek"]:
                    warn.append(f"hiányzik a modell: ollama pull {m}")
                elif d["modellek"][m] != want:
                    warn.append(f"a {m} modellfájl más ({d['modellek'][m]}), mint a protokollé ({want}) — szólj")
            print(f"Felvéve: {p.relative_to(ROOT).as_posix()}\n  gépnév: {d['gepnev']}\n  processzor: {d['processzor']}\n"
                  f"  videókártya: {'; '.join(d['videokartyak']) or 'nincs NVIDIA-kártya'}\n  ollama: {d['ollama']}\n"
                  f"  modellek: {d['modellek']}\n\nMost commitold és pushold:\n"
                  f"  git add {p.relative_to(ROOT).as_posix()}\n  git commit -m \"Géphatás: a(z) {a.gep[1]} gép felvéve\"\n"
                  f"  git push\nutána: tools\\gepvaltas.bat {a.gep[1]}")
            if warn:
                print("\nFutás előtt még:\n  - " + "\n  - ".join(warn))
            return 0
        if len(a.gep) != 1:
            raise Megall("használat: tools\\gepvaltas.bat GÉP [--allapot] [--csak PÁR ...]")
        f = Futtato(a.gep[0])
        if a.csak and (bad := [p for p in a.csak if p not in f.pairs]):
            raise Megall(f"ismeretlen pár: {', '.join(bad)} (a párok: {', '.join(f.pairs)})")
        print(f"K1 géphatás · gép: {f.gep}")
        _allapot(f)
        if a.allapot:
            return 0
        todo = f.terv(a.csak)
        if not todo:
            print("\nEzen a gépen nincs több futtatnivaló.")
            return 0
        problems = f.elofeltetelek(todo)
        if problems:
            raise Megall("nem indul, mert:\n  - " + "\n  - ".join(problems))
        print(f"\nHátra: {len(todo)} futás, körökben (az első: {todo[0]}).")
        ebren_tart(True)
        try:
            for pid in todo:
                f.futtat_par(pid)
        finally:
            ebren_tart(False)
        print(f"\nKész: a(z) {f.gep} gép minden futása megvan (konfigurációnként {f.protocol['ismetles_futas']['szam']}). Másold fel (git add logs/meres/{f.gep} → commit → push), és szólj.")
        return 0
    except Megall as exc:
        print(f"\nMEGÁLLT: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nMegszakítva. Ugyanezzel a paranccsal folytatható.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
