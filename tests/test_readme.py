"""
A README parancsai Windows PowerShellben is bemásolhatók legyenek.

A PowerShellben a `<` foglalt operátor („The '<' operator is reserved for future use”),
a `>` pedig fájlba irányít — egy `<order_key>`-féle helyőrző ott hibát ad, vagy csendben
fájlt ír. A helyőrző ezért csupa nagybetűs szó (pl. RENDELES_KULCS).
"""

from __future__ import annotations

import re
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"


def command_lines(text: str):
    """A ```bash / ```powershell blokkok sorai, a megjegyzések (# …) nélkül."""
    lang = None
    for i, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^\s*```(\w*)", line)
        if m:
            lang = m.group(1) if lang is None else None
            continue
        if lang in ("bash", "powershell", "ps1"):
            cmd = re.sub(r"(^|\s)#.*$", "", line).strip()
            if cmd:
                yield i, cmd


def test_a_kereso_megtalalja_a_hibas_helyorzot():
    text = "```bash\npython -m x --a <kulcs>   # megjegyzés <ez nem számít>\n```\n```\n<szöveg>\n```\n"
    assert list(command_lines(text)) == [(2, "python -m x --a <kulcs>")]


def test_a_readme_parancsai_powershellben_is_futnak():
    lines = list(command_lines(README.read_text(encoding="utf-8")))
    assert any("python -m pytest" in cmd for _, cmd in lines)          # a blokkokat megtalálta
    bad = [(i, cmd) for i, cmd in lines if re.search(r"[<>]", cmd)]
    assert not bad, f"PowerShellben hibát adó helyőrző a README-ben (sor, parancs): {bad}"
