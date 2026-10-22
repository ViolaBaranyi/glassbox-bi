"""
Egy szabad szöveges kérdés végig: ① kérdés → QuerySpec (nyelvi modell) → KAPU ① → SQL és
eredmény (determinisztikus réteg) → ② eredmény → mondat (nyelvi modell, hely-kitöltés) →
KAPU ②. A nyelvi modell sehol máshol nem fér hozzá az adathoz (rendszerterv 14.).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from narrative.client import LlmClient
from narrative.to_spec import SpecAttempt, to_spec
from narrative.to_text import TextAttempt, to_text
from semantic import engine
from semantic.catalog import Catalog, Whitelist
from semantic.engine import MetricResult


@dataclass
class FreeAnswer:
    kerdes: str
    spec: SpecAttempt                  # ① és a KAPU ①
    eredmeny: MetricResult | None      # csak elfogadott kérdésnél
    szoveg: TextAttempt | None         # ② és a KAPU ② (vagy a sablon)
    ido_ms: float = 0.0

    @property
    def ok(self) -> bool:
        return self.eredmeny is not None

    @property
    def modell_hiba(self) -> bool:
        """A nyelvi modell nem volt elérhető (ilyenkor a választ nem érdemes megjegyezni)."""
        return self.spec.hiba is not None or bool(self.szoveg and self.szoveg.modell_hiba)


def ask(question: str, cat: Catalog, wl: Whitelist, con, client: LlmClient, mod: str = "jelolo",
        question_id: str | None = None) -> FreeAnswer:
    t0 = time.perf_counter()
    att = to_spec(question, cat, wl, client, question_id=question_id, con=con)
    if not att.gate.ok:
        return FreeAnswer(question, att, None, None, (time.perf_counter() - t0) * 1000.0)
    result = engine.run(att.gate.spec, cat, wl, con, att.gate.megjegyzesek)
    text = to_text(question, result, client, mod=mod, question_id=question_id)
    return FreeAnswer(question, att, result, text, (time.perf_counter() - t0) * 1000.0)
