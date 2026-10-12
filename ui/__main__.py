"""
python -m ui — elindítja a BI-felületet, és megnyitja a böngészőben.

A felület csak ezen a gépen érhető el (localhost:8501), használati statisztikát
nem küld. További Streamlit-kapcsolók továbbadhatók, pl.:
    python -m ui --server.port 8502
Leállítás: Ctrl+C a terminálban (vagy zárd be az ablakot).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    os.chdir(ROOT)                      # a relatív útvonalak (data/, docs/) innen értendők
    from streamlit.web import cli as stcli
    sys.argv = ["streamlit", "run", str(ROOT / "ui" / "app.py"),
                "--server.address=localhost",
                "--browser.gatherUsageStats=false",
                "--client.toolbarMode=minimal",
                *sys.argv[1:]]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
