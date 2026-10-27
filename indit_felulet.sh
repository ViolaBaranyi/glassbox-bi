#!/bin/sh
# Üvegdoboz BI — indítás macOS-en és Linuxon:   sh indit_felulet.sh
# (A Windowsos párja: indit_felulet.bat.) Kapcsolók: sh indit_felulet.sh --help
#
# 1. ha nincs uv, telepíti (egyszer, néhány másodperc; a saját mappájába, rendszergazda nélkül);
# 2. a uv a rögzített változatokkal (uv.lock) előállítja a Python 3.14-et és a csomagokat;
# 3. az inditas.py előkészíti, ami hiányzik (adat, tárház, modellek), és megnyitja a felületet.
set -e
cd "$(dirname "$0")"
PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
export PATH

if ! command -v uv >/dev/null 2>&1; then
    echo "A uv nincs telepítve — telepítés (egyszer, néhány másodperc)…"
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        echo "Sem curl, sem wget nincs ezen a gépen. Telepítsd a uv-t kézzel:"
        echo "  https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
    if ! command -v uv >/dev/null 2>&1; then
        echo "A uv telepítése nem sikerült. Részletek fent; kézi telepítés:"
        echo "  https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
fi

unset VIRTUAL_ENV            # egy bekapcsolt régi környezet ne zavarjon (a uv a .venv-et használja)
exec uv run python inditas.py "$@"
