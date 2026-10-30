"""
A K1 mérések nyers naplói a tároló részei (logs/meres/, leírás: logs/meres/README.md).

Minden futás, amelyre a docs/ eredményfájljai hivatkoznak, megvan a fejlécével és a soraival; a
kézi ellenőrzés összesítése a naplókból újraszámolva pontosan a közölt (docs/k1_kezi_ellenorzes.json);
és az első mérés jelentései a futások saját jelentései. Modell és tárház nem kell hozzá.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MERES = ROOT / "logs" / "meres"
RUN = re.compile(r"20261\d{3}_\d{4}_qwen3\.5-\d+b")


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n")


def test_minden_hivatkozott_futas_naploja_megvan():
    refs = set()
    for p in (ROOT / "docs").glob("k1_*.md"):
        refs |= set(RUN.findall(p.read_text(encoding="utf-8")))
    assert len(refs) == 10
    for name in sorted(refs):
        run = MERES / name
        assert (run / "fej.json").is_file() and (run / "sorok.jsonl").is_file(), name
        head = json.loads((run / "fej.json").read_text(encoding="utf-8"))
        assert name.endswith(head["modell"].replace(":", "-")), name
        assert name.startswith(head["kezdes"][:10].replace("-", "") + "_" + head["kezdes"][11:16].replace(":", ""))


def test_a_kezi_ellenorzes_osszesitese_a_naplokbol_ujraszamolhato():
    spec = importlib.util.spec_from_file_location("kezi_minta", ROOT / "tools" / "kezi_minta.py")
    km = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(km)
    published = json.loads((ROOT / "docs" / "k1_kezi_ellenorzes.json").read_text(encoding="utf-8"))
    assert km.summarize(MERES) == published
    assert len(published["futasok"]) == 5


def test_az_elso_meres_jelentesei_a_futasok_sajat_jelentesei():
    for model, run in (("4b", "20261016_1426_qwen3.5-4b"), ("2b", "20261019_0910_qwen3.5-2b")):
        doc = (ROOT / "docs" / f"k1_eredmeny_qwen3.5-{model}.md").read_text(encoding="utf-8")
        assert _norm(doc) == _norm((MERES / run / "jelentes.md").read_text(encoding="utf-8"))
