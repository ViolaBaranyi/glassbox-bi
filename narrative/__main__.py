"""
Szabad szöveges kérdés parancssorból — ugyanaz az út, mint a Kérdezz oldalon.

    uv run python -m narrative --allapot
    uv run python -m narrative "Melyik államban késnek a legtöbbet?"
    uv run python -m narrative "Mekkora volt a forgalom tavaly?" --reszletek
    uv run python -m narrative "Melyik régióban a leglassabb a szállítás?" --szabad   # kontrollág
    uv run python -m narrative "Mennyi a forgalom?" --modell gemma3:4b                # másik modell

Helyi modellhez az Ollama kell (https://ollama.com) és a beállított modell
(configs/llm.toml), pl. ``ollama pull qwen3.5:4b``. Több kérdés egyben, ítélettel és
időkkel: ``python -m narrative.proba`` (fejlesztői próbasor).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from data.db import DB_PATH, WarehouseUnavailable, connect, use_utf8_console
from narrative.client import LlmClient, load_config
from narrative.pipeline import ask
from semantic import catalog
from xai import narrative as nv


def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="Szabad szöveges kérdés: nyelvi modell + két kapu")
    ap.add_argument("kerdes", nargs="?", help="a kérdés magyarul (idézőjelek között)")
    ap.add_argument("--allapot", action="store_true", help="csak azt nézi meg, elérhető-e a modell")
    ap.add_argument("--szabad", action="store_true", help="kontrollág: a modell maga írja a számokat")
    ap.add_argument("--reszletek", action="store_true", help="a modell nyers válaszai és a nézet is")
    ap.add_argument("--modell", help="másik modell (felülírja a configs/llm.toml-t)")
    a = ap.parse_args()

    cfg = load_config()
    client = LlmClient(dataclasses.replace(cfg, modell=a.modell) if a.modell else cfg)
    ok, msg = client.status()
    print(f"Nyelvi modell: {'elérhető' if ok else 'NEM érhető el'} — {msg}")
    if a.allapot or not a.kerdes:
        sys.exit(0 if ok else 1)
    if not ok:
        sys.exit(1)
    try:
        con = connect(DB_PATH, read_only=True)
    except WarehouseUnavailable as exc:
        print(f"\nHIBA:\n{exc}", file=sys.stderr)
        sys.exit(1)
    cat = catalog.load()
    wl = catalog.whitelist(cat, con)
    fa = ask(a.kerdes, cat, wl, con, client, mod="szabad" if a.szabad else "jelolo")
    con.close()

    s = fa.spec
    print(f"\n① A modell értelmezése ({nv.fmt_num(s.ido_ms / 1000, 1)} mp{', javító körrel' if s.javito_kor else ''}"
          f"{_parts(s.idok)}; prompt: {s.prompt}):")
    print("  " + json.dumps(s.urlap, ensure_ascii=False) if s.urlap else "  (nincs érvényes űrlap)")
    for n in s.feloldasok:
        print(f"  feloldva: „{n.beirt}” → " + (n.kulcs or "nem egyértelmű (" + ", ".join(n.jeloltek) + ")"))
    print(f"KAPU ①: {s.gate.status}")
    if not s.gate.ok:
        print(s.gate.elutasitas.uzenet)
        sys.exit(2)
    print("  " + json.dumps(s.gate.spec.to_dict(), ensure_ascii=False))
    t = fa.szoveg
    print(f"\n② Válasz ({nv.fmt_num(t.ido_ms / 1000, 1)} mp{_parts([t.idok])}; prompt: {t.prompt}"
          f"{'; a hatókört és a korlátot a kód írta' if t.keret else ''}):")
    print(t.szoveg)
    if t.verdict:
        print(f"\nKAPU ②: {'átment' if t.verdict.ok else 'NEM ment át'} — {t.verdict.fedett}/{t.verdict.szamok} "
              "szám visszavezethető" + (f"; {'; '.join(t.verdict.problemak)}" if t.verdict.problemak else "")
              + (f" (ismételt jelölő: {', '.join(t.verdict.ismetelt_jelolok)})" if t.verdict.ismetelt_jelolok else ""))
    if t.sablon:
        print(f"(A sablonos válasz látszik: {t.ok_sablon})")
    if a.reszletek:
        print("\n--- a modell szövege jelölőkkel ---\n" + (t.modell_szoveg or ""))
        print("\n--- amit a modell az eredményből látott ---\n" + t.nezet)
        print("\n--- a modell nyers válaszai (①) ---")
        for raw in s.valaszok:
            print(raw)
    print(f"\n(összesen {nv.fmt_num(fa.ido_ms / 1000, 1)} mp; modell: {s.modell}{' · ' + s.digest[:12] if s.digest else ''})")


def _parts(times: list[dict]) -> str:
    """„; betöltés 0,1 + prompt 18,2 + generálás 5,0 mp” — ha a szolgáltató megadja."""
    total: dict[str, int] = {}
    for t in times:
        for k, v in (t or {}).items():
            total[k] = total.get(k, 0) + v
    names = (("betoltes_ms", "betöltés"), ("prompt_ms", "prompt"), ("generalas_ms", "generálás"))
    parts = [f"{name} {nv.fmt_num(total[k] / 1000, 1)}" for k, name in names if k in total]
    return f"; ebből {' + '.join(parts)} mp" if parts else ""


if __name__ == "__main__":
    main()
