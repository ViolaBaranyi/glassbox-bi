"""
Bemutató mód a Kérdezz oldalon: a szabad szöveges út Ollama nélkül, egy lezárt K1-futás rögzített
modellválaszaival (docs/bemutato_valaszok.json, tools/bemutato_export.py).

Csak a nyelvi modell két hívása cserélődik a rögzített kimenetre (az ① űrlap és a fő ág ② szövege);
minden más — az értékek feloldása, a kódbeli javítások, az 1. kapu, a lekérdezés, a behelyettesítés
és a 2. kapu — most fut le, a mostani kóddal és adattal. Így a felület azt mutatja, amit a
felhasználó a mérés idején látott volna, és a bemutató nem a gép sebességén múlik.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from narrative.client import LlmClient, Reply

ROOT = Path(__file__).resolve().parent.parent
RECORDS = ROOT / "docs" / "bemutato_valaszok.json"


def load(path: Path = RECORDS) -> dict:
    """A rögzített válaszok (ha a fájl nincs meg, üres lista)."""
    if not path.exists():
        return {"valaszok": []}
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class ReplayClient(LlmClient):
    """Az LlmClient helyett: a hívásra a rögzített kimenetet adja vissza, hálózat nélkül."""
    rekord: dict = field(default_factory=dict)
    modell: str = ""
    lenyomat: str | None = None
    log_path: Path | None = None

    def status(self, timeout: float = 2.0) -> tuple[bool, str]:
        return True, f"{self.modell}, rögzített válasz"

    def preload(self, timeout: float = 120.0) -> bool:
        return False

    def chat(self, call_name: str, messages: list[dict], schema: dict, name: str) -> Reply:
        if call_name == "to_spec":
            out = self.rekord.get("urlap") or {}
        else:
            out = {"szoveg": self.rekord.get("modell_szoveg") or ""}
        return Reply(text=json.dumps(out, ensure_ascii=False), model=f"{self.modell}, rögzített válasz",
                     digest=self.lenyomat)


def client_for(rec: dict, meta: dict) -> ReplayClient:
    return ReplayClient(rekord=rec, modell=meta.get("modell", ""), lenyomat=meta.get("digest"))


def ask(rec: dict, meta: dict, cat, wl, con):
    """Egy rögzített kérdés végig a szabad szöveges úton (narrative.pipeline), a fő ágon."""
    from narrative.pipeline import ask as ask_llm
    return ask_llm(rec["kerdes"], cat, wl, con, client_for(rec, meta), mod="jelolo")


def label(rec: dict) -> str:
    """A választóban: a kérdés úgy, ahogy a szerző beírta (ékezet nélkül is)."""
    return rec["kerdes"].strip().rstrip("?") + "?"


def source_line(meta: dict) -> str:
    kod = meta.get("kod") or {}
    when = (meta.get("kezdes") or "")[:10].replace("-", ". ") + "."
    return (f"{meta.get('modell', '')}, a nyelvi réteg {kod.get('verzio', '')} változata, "
            f"a {meta.get('futas', '')} futás ({when})")
