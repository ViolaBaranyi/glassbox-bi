"""
A futtatókörnyezet leírása: egy forrásból, gépfüggő útvonal nélkül.

A környezetet a uv építi a uv.lock-ból (pip-nek ugyanez a requirements.lock). A
virtuális környezet (.venv) gépenként készül, és — mint minden Python-környezet — az
adott gép abszolút útvonalaira mutat; ezért nem része a tárolónak. A tároló saját
fájljaiban viszont nem lehet ilyen útvonal, és virtuális környezetre sem hivatkozhatnak:
a parancsok `uv run`-nal indulnak.

  * a pyproject.toml függőségei = a requirements.txt (pip-nek ugyanaz a lista);
  * a uv.lock és a requirements.lock ugyanazokat a pontos változatokat rögzíti
    (a uv és a pip ugyanazt telepíti → bitre azonos számok), és minden közvetlen
    függőség benne van;
  * a Python-verzió mindenhol 3.14;
  * a tároló szöveges fájljaiban nincs gépfüggő abszolút útvonal, és az indítófájl
    nem hivatkozik virtuális környezetre.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirements(text: str) -> dict[str, str]:
    """név → változat-feltétel (szóközök nélkül), a megjegyzések és a platformjelölők nélkül."""
    out = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.fullmatch(r"([A-Za-z0-9_.\-]+)\s*([^;]*?)\s*(;.*)?", line)
        out[_norm(m.group(1))] = m.group(2).replace(" ", "")
    return out


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _uv_lock() -> dict:
    return tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))


def test_a_fuggosegek_egy_forrasbol():
    deps = _requirements("\n".join(_pyproject()["project"]["dependencies"]))
    assert "numpy" in deps and "streamlit" in deps
    assert deps == _requirements((ROOT / "requirements.txt").read_text(encoding="utf-8"))


def test_a_uv_es_a_pip_ugyanazt_telepiti():
    lock = _uv_lock()
    uv = {_norm(p["name"]): p["version"] for p in lock["package"]
          if "virtual" not in p.get("source", {})}                   # maga a projekt nem csomag
    pip = {name: spec.removeprefix("==")
           for name, spec in _requirements((ROOT / "requirements.lock").read_text(encoding="utf-8")).items()}
    assert uv == pip
    assert set(_requirements("\n".join(_pyproject()["project"]["dependencies"]))) <= set(uv)


def test_python_314_mindenhol():
    assert _pyproject()["project"]["requires-python"] == ">=3.14,<3.15"
    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.14"
    assert _uv_lock()["requires-python"] == "==3.14.*"


SKIP_DIRS = {".git", "artifacts", "logs", "__pycache__", ".pytest_cache", ".ipynb_checkpoints",
             ".idea", ".vscode"}
TEXT_SUFFIXES = {".py", ".md", ".toml", ".txt", ".bat", ".yml", ".yaml", ".cff", ".json", ".lock",
                 ".cfg", ".ini", ".gitignore", ".gitattributes", ".example"}
# gépfüggő abszolút útvonal: bármely Windows-meghajtó (C:\…, E:/…) vagy Linux/macOS
# felhasználói, rendszergazdai, ideiglenes mappa (az URL-ek „https://” része nem számít)
MACHINE_PATH = re.compile(r"(?<![\w/])[A-Za-z]:[\\/]+(?=[\w.%$-])|/(?:home|Users|root|tmp)/\w")


def _tracked_text_files():
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        top = rel.parts[0]
        if (any(part in SKIP_DIRS for part in rel.parts) or top.startswith((".venv", "venv"))
                or rel.parts[:2] == ("data", "raw") or not path.is_file()):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in TEXT_SUFFIXES:
            yield rel, path


def test_nincs_gepfuggo_utvonal_a_taroloban():
    me = Path(__file__).resolve()
    found = []
    for rel, path in _tracked_text_files():
        if path.resolve() == me:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if MACHINE_PATH.search(line):
                found.append(f"{rel}:{i}: {line.strip()[:120]}")
    assert not found, "gépfüggő útvonal a tárolóban:\n" + "\n".join(found)


def test_az_indito_nem_hivatkozik_virtualis_kornyezetre():
    bat = (ROOT / "indit_felulet.bat").read_bytes()
    assert b"\r\n" in bat and b"\n" not in bat.replace(b"\r\n", b"")   # cmd-nek CRLF kell
    text = bat.decode("ascii")
    assert "uv run python -m ui" in text
    assert ".venv" not in text and "Scripts\\python" not in text


def test_a_kereso_eszreveszi_a_gepfuggo_utvonalat():
    for bad in (r"home = C:\Users\viola\AppData\Local\Python", "E:\\EKKE\\EKOP\\glassbox-bi",
                "/home/claude/repo", "c:/Users/E1476338/PycharmProjects"):
        assert MACHINE_PATH.search(bad), bad
    for ok in ("%USERPROFILE%\\.local\\bin", "data\\raw\\", "https://github.com/ViolaBaranyi/glassbox-bi.git",
               "http://localhost:8501", ".venv\\Scripts\\Activate.ps1", "docs/huseg_eredmeny.md",
               "a hónap: 1–12"):
        assert not MACHINE_PATH.search(ok), ok
