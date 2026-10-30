"""
A bemutató mód adatai: egy lezárt K1-futás rögzített modellválaszai → docs/bemutato_valaszok.json.

    uv run python tools/bemutato_export.py logs\\meres\\20261022_1902_qwen3.5-4b

A felület Kérdezz oldala ezekből Ollama nélkül, azonnal válaszol (ui/bemutato.py): a nyelvi modell
két hívása helyett a rögzített kimenetet kapja (az ① űrlapot és a fő ág ② szövegét), minden más
— értékfeloldás, kódbeli javítások, 1. kapu, lekérdezés, behelyettesítés, 2. kapu — élőben fut.
A fájlba a futás azonosítói és a rögzített ítéletek is bekerülnek, hogy a visszajátszás
egyezése ellenőrizhető legyen. A teljes mérési napló a logs/meres/ mappában van; a felület ezt a
kivonatot olvassa.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "bemutato_valaszok.json"


def export(run: Path) -> dict:
    head = json.loads((run / "fej.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (run / "sorok.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    latest: dict = {}
    for r in rows:                                   # ismétlésnél a legutolsó
        if not r.get("hiba"):
            latest[r["id"]] = r
    records = []
    for qid in sorted(latest):
        r = latest[qid]
        main = (r.get("agak") or {}).get("jelolo") or {}
        records.append({
            "id": qid, "kerdes": r["kerdes"], "tipus": r.get("tipus"), "csapda": r.get("csapda"),
            "urlap": r.get("urlap"), "modell_szoveg": main.get("modell_szoveg"),
            "rogzitett": {"kapu1": r.get("kapu1"), "spec": r.get("spec"), "itelet": r.get("itelet"),
                          "sablon": main.get("sablon"), "mag": main.get("mag"),
                          "problemak": main.get("problemak") or []},
        })
    return {
        "leiras": "A Kérdezz oldal bemutató módja: egy lezárt K1-futás rögzített modellválaszai "
                  "(tools/bemutato_export.py).",
        "futas": run.name, "modell": head["modell"], "digest": head.get("digest"),
        "kezdes": head.get("kezdes"), "kod": head.get("kod"), "kerdessor": head.get("kerdessor"),
        "valaszok": records,
    }


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        raise SystemExit(__doc__)
    run = Path(args[0])
    if not (run / "sorok.jsonl").exists():
        raise SystemExit(f"Nincs ilyen mérés ezen a gépen: {run}")
    res = export(run)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(res['valaszok'])} kérdés → {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
