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


def test_a_9b_kiegeszites_az_elso_meres_feltetelein_fut():
    """docs/k1_protokoll_v1_9b.json: csak a modell más, minden más az első mérésé (kérdéssor, beállítások,
    ágak, statisztika, kézi minta magja, és a kód — a 4B-futás fejléce szerint); az összevető eszköz rögzítve."""
    import sys
    sys.path.insert(0, str(ROOT))
    from narrative import meres

    v1 = json.loads((ROOT / "docs" / "k1_protokoll.json").read_text(encoding="utf-8"))
    p9 = json.loads((ROOT / "docs" / "k1_protokoll_v1_9b.json").read_text(encoding="utf-8"))
    assert p9["allapot"] == "jovahagyva" and [m["nev"] for m in p9["modellek"]] == ["qwen3.5:9b"]
    for key in ("fajl", "sha256", "kerdesek", "megvalaszolando", "csapda", "szerzok"):
        assert p9["kerdessor"][key] == v1["kerdessor"][key], key
    assert {k: v for k, v in p9["beallitasok"].items() if k != "kod"} == \
           {k: v for k, v in v1["beallitasok"].items() if k != "kod"}
    assert p9["agak"] == v1["agak"] and p9["statisztika"] == v1["statisztika"]
    assert p9["kezi_ellenorzes"]["mag"] == v1["kezi_ellenorzes"]["mag"]
    head4b = json.loads((MERES / "20261016_1426_qwen3.5-4b" / "fej.json").read_text(encoding="utf-8"))
    assert p9["kod"]["ujjlenyomat"] == head4b["kod"]["ujjlenyomat"] and p9["kod"]["commit"] == head4b["kod"]["commit"]
    assert p9["elemzes"]["sha256"] == meres.sha256_text(ROOT / p9["elemzes"]["eszkoz"])
    bat = (ROOT / "tools" / "v1_9b_futtatas.bat").read_bytes().replace(b"\r\n", b"\n").decode("ascii")
    assert head4b["kod"]["commit"] in bat and "docs\\k1_protokoll_v1_9b.json" in bat and "--modell qwen3.5:9b" in bat
