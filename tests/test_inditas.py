"""
inditas.py — a platformfüggetlen indító (Windows: indit_felulet.bat, macOS/Linux: indit_felulet.sh).

Az ellenőrző mód nem ír és nem tölt le; a tárház csak hiányzó vagy elavult állapotban épül újra
(különben a modell-gyorsítótár kulcsa is változna); foglalt portnál a következő szabadot választja;
a uv-nek legfeljebb egyszer adja át a futtatást. A parancsfájlok sorvégei és a felület első
indítása (ne kérjen e-mail-címet) is itt van őrizve.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

import inditas

ROOT = Path(__file__).resolve().parent.parent


def test_a_foglalt_portot_atugorja():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        s.listen(1)
        busy = s.getsockname()[1]
        assert not inditas.port_free(busy)
        free = inditas.find_free_port(busy, tries=5)
        assert free is not None and free != busy


def test_a_projekt_kornyezetet_felismeri(tmp_path):
    (tmp_path / ".venv").mkdir()
    assert inditas.in_project_env(str(tmp_path / ".venv"), tmp_path)
    assert not inditas.in_project_env(str(tmp_path), tmp_path)


def test_a_uv_nek_legfeljebb_egyszer_adja_at(monkeypatch):
    monkeypatch.setattr(inditas, "in_project_env", lambda *a, **k: False)
    monkeypatch.setenv(inditas.REEXEC_FLAG, "1")                 # már a uv indította: nincs ciklus
    assert inditas.hand_over_to_uv([]) is None
    monkeypatch.delenv(inditas.REEXEC_FLAG)
    monkeypatch.setattr(inditas, "find_uv", lambda: None)        # nincs uv: marad ebben a Pythonban
    assert inditas.hand_over_to_uv([]) is None


def test_a_tarhaz_csak_hianyzo_vagy_elavult_allapotban_epul_ujra(tmp_path, synth_db):
    raw = tmp_path / "raw"
    raw.mkdir()
    assert inditas.warehouse_state(tmp_path / "nincs.duckdb", raw)[0] == "nincs"
    state, msg = inditas.warehouse_state(synth_db, raw)
    assert state == "rendben" and "szintetikus" in msg
    newer = raw / "olist_orders_dataset.csv"
    newer.write_text("x", encoding="utf-8")
    t = synth_db.stat().st_mtime + 60
    os.utime(newer, (t, t))
    assert inditas.warehouse_state(synth_db, raw)[0] == "elavult"


def test_az_ellenorzo_mod_nem_ir_es_nem_tolt_le(tmp_path, monkeypatch, capsys):
    import data.build_warehouse as bw
    import xai.models as xm
    raw, db, cache = tmp_path / "raw", tmp_path / "w.duckdb", tmp_path / "m.joblib"
    monkeypatch.setattr(bw, "RAW", raw)
    monkeypatch.setattr(bw, "DB_PATH", db)
    monkeypatch.setattr(xm, "CACHE", cache)
    monkeypatch.setattr(inditas, "hand_over_to_uv", lambda argv: None)
    monkeypatch.setattr(inditas, "llm_status", lambda: (False, "nem fut", "qwen3.5:4b"))
    monkeypatch.chdir(ROOT)
    assert inditas.main(["--ellenorzes", "--port", "8590"]) == 0
    out = capsys.readouterr().out
    assert "3 dolog hiányzik" in out and "hiányzik: első indításkor letöltjük" in out
    assert list(tmp_path.iterdir()) == []                        # semmi nem jött létre


def test_a_macos_linux_parancsfajl_az_inditot_hivja_lf_sorvegekkel():
    sh = (ROOT / "indit_felulet.sh").read_bytes()          # a Windowsos párját a test_kornyezet őrzi
    assert sh.startswith(b"#!/bin/sh") and b"\r" not in sh       # CRLF-fel a sh nem futna
    assert b'exec uv run python inditas.py "$@"' in sh


def test_a_felulet_elso_inditasa_nem_ker_emailt(monkeypatch):
    from streamlit.web import cli as stcli
    import ui.__main__ as ui_main
    seen = {}
    monkeypatch.setattr(stcli, "main", lambda: seen.setdefault("argv", list(sys.argv)) and 0)
    monkeypatch.setattr(sys, "argv", ["ui", "--server.port=8590"])
    monkeypatch.chdir(ROOT)
    with pytest.raises(SystemExit):
        ui_main.main()
    assert "--server.showEmailPrompt=false" in seen["argv"]
    assert seen["argv"][-1] == "--server.port=8590"
