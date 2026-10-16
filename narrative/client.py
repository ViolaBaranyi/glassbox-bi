"""
Vékony LLM-kliens (rendszerterv 14.): a két hívás ugyanazon a felületen megy, a szolgáltató
a beállításból cserélhető.

  * ``ollama`` — helyi modell az Ollama natív felületén (``/api/chat``): offline is működik,
    és semmi nem hagyja el a gépet (NF-4);
  * ``api`` — OpenAI-kompatibilis chat-completions végpont (``/chat/completions``).

Mindkettő JSON-sémához kötött kimenetet kér (M-1, M-5): az Ollama a ``format`` mezőben, az
API a ``response_format`` mezőben kapja a sémát. Hálózati hiba vagy időtúllépés után
exponenciálisan növekvő várakozással újrapróbál, utána ``LLMUnavailable`` — a felület ilyenkor
nyelvi modell nélkül működik tovább.

Minden hívás egy sor a ``logs/llm_calls.jsonl``-ban (NF-8): időpont, hívás, prompt-változat,
modell és ujjlenyomata (M-2), késleltetés, tokenek, újrapróbálások — ebből lesz a mérőpad
nyersanyaga. Az Ollama a késleltetést részekre is bontja (a modell betöltése, a prompt
beolvasása, a válasz generálása), ez is a naplóba kerül: ebből látszik, mire megy el az idő.
A kérdés és a válasz szövege is bekerül (a mérés megismételhetőségéhez); a naplómappa nem
része a tárolónak.

Helyi modellnél két beállítás számít a sebességben (configs/llm.toml):

  * ``tartas`` (az Ollama ``keep_alive``-ja): ennyi ideig marad a modell a memóriában az
    utolsó hívás után — különben öt perc tétlenség után újra be kell tölteni;
  * ``kontextus`` (``num_ctx``): a prompt és a válasz együtt ennyi tokenbe férjen. Rögzítve,
    hogy a mérés ismételhető legyen, és hogy egy túl hosszú prompt eleje ne vesszen el
    csendben (ha a hívás a határ közelébe ér, a napló jelzi).
"""

from __future__ import annotations

import json
import os
import time
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "configs" / "llm.toml"
LOG = ROOT / "logs" / "llm_calls.jsonl"
ENV_FILE = ROOT / ".env"
PROVIDERS = ("ollama", "api")


class LLMUnavailable(RuntimeError):
    """A nyelvi modell nem érhető el (nem fut, nincs letöltve, hálózati hiba)."""


@dataclass(frozen=True)
class CallConfig:
    prompt: str               # a prompt fájlja (verziózva: prompts/to_spec.v1.md)
    temperature: float
    max_tokens: int

    @property
    def version(self) -> str:
        return Path(self.prompt).name.removesuffix(".md")


@dataclass(frozen=True)
class LlmConfig:
    szolgaltato: str
    url: str
    modell: str
    timeout_s: float
    max_retries: int
    seed: int
    gondolkodas: bool
    api_kulcs: str | None
    hivasok: dict
    tartas: str | None = None         # Ollama keep_alive (pl. "30m")
    kontextus: int | None = None      # Ollama num_ctx

    @property
    def leiras(self) -> str:
        return f"{self.modell} ({'helyi, Ollama' if self.szolgaltato == 'ollama' else 'API'})"


def read_env_file(path: Path = ENV_FILE) -> dict:
    """A .env egyszerű KULCS=érték sorai (python-dotenv nélkül)."""
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def load_config(path: Path = CONFIG, env: dict | None = None) -> LlmConfig:
    """A beállítás a configs/llm.toml-ból; a környezeti változók (és a .env) felülírják."""
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    env = {**read_env_file(), **os.environ} if env is None else env
    provider = (env.get("LLM_PROVIDER") or raw.get("szolgaltato", "ollama")).strip().lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Ismeretlen nyelvimodell-szolgáltató: {provider!r} (lehet: {', '.join(PROVIDERS)})")
    section = raw.get(provider, {})
    calls = {name: CallConfig(prompt=c["prompt"], temperature=float(c["temperature"]),
                              max_tokens=int(c["max_tokens"]))
             for name, c in raw.get("hivas", {}).items()}
    return LlmConfig(
        szolgaltato=provider,
        url=(env.get("LLM_BASE_URL") or section.get("url", "")).rstrip("/"),
        modell=env.get("LLM_MODEL") or section.get("modell", ""),
        timeout_s=float(raw.get("timeout_s", 120)),
        max_retries=int(raw.get("max_retries", 2)),
        seed=int(raw.get("seed", 0)),
        gondolkodas=bool(section.get("gondolkodas", False)),
        api_kulcs=env.get("LLM_API_KEY") or None,
        hivasok=calls,
        tartas=str(section["tartas"]) if section.get("tartas") else None,
        kontextus=int(section["kontextus"]) if section.get("kontextus") else None,
    )


@dataclass
class Reply:
    text: str                     # a modell válasza (JSON-szöveg)
    model: str
    digest: str | None = None     # a modell ujjlenyomata (Ollama), ha ismert
    latency_ms: float = 0.0
    tokens_in: int | None = None
    tokens_out: int | None = None
    retries: int = 0
    idok: dict = field(default_factory=dict)   # Ollama: betoltes_ms, prompt_ms, generalas_ms
    kontextus_tele: bool = False  # a prompt és a válasz a kontextus határáig ért (csonkolás gyanúja)

    def log_fields(self) -> dict:
        """A naplósor közös mezői (a hívó adja hozzá a saját ítéletét)."""
        out = {"modell": self.model, "digest": self.digest, "latency_ms": round(self.latency_ms),
               "tokens_in": self.tokens_in, "tokens_out": self.tokens_out, "retry": self.retries, **self.idok}
        if self.kontextus_tele:
            out["kontextus_tele"] = True
        return out


_NS = {"load_duration": "betoltes_ms", "prompt_eval_duration": "prompt_ms", "eval_duration": "generalas_ms"}


def _http_json(url: str, payload: dict | None, timeout: float, headers: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="GET" if payload is None else "POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_error_text(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", "replace")
        return json.loads(body).get("error", body) if body.startswith("{") else body
    except Exception:  # noqa: BLE001 — csak az üzenethez
        return str(exc)


@dataclass
class LlmClient:
    cfg: LlmConfig = field(default_factory=load_config)
    http: object = _http_json          # (url, payload|None, timeout, headers) → dict; tesztben cserélhető
    log_path: Path | None = LOG
    sleep: object = time.sleep
    _digest: str | None = None

    # ------------------------------------------------------------------ állapot
    def status(self, timeout: float = 2.0) -> tuple[bool, str]:
        """Elérhető-e a modell? (igen/nem, magyar magyarázat) — gyors, hívás nélkül."""
        c = self.cfg
        if c.szolgaltato == "api":
            if not (c.url and c.modell and c.api_kulcs):
                return False, ("Az API-hoz a .env-ben meg kell adni: LLM_BASE_URL, LLM_MODEL és "
                               "LLM_API_KEY.")
            return True, f"{c.modell} (API)"
        try:
            tags = self.http(f"{c.url}/api/tags", None, timeout, None)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return False, (f"Az Ollama nem fut ezen a gépen (nem érhető el: {c.url}). Telepítés: "
                           "https://ollama.com — utána indítsd el.")
        names = {m.get("name"): m.get("digest") for m in tags.get("models", [])}
        wanted = c.modell if ":" in c.modell else f"{c.modell}:latest"
        if wanted not in names:
            return False, (f"Az Ollama fut, de a „{c.modell}” modell nincs letöltve. Töltsd le: "
                           f"ollama pull {c.modell}")
        self._digest = names[wanted]
        return True, f"{c.modell} (helyi, Ollama)"

    # ------------------------------------------------------------------ hívás
    def _request(self, call: CallConfig, messages: list[dict], schema: dict, name: str) -> tuple[str, dict]:
        c = self.cfg
        if c.szolgaltato == "ollama":
            payload = {"model": c.modell, "messages": messages, "stream": False, "format": schema,
                       "options": {"temperature": call.temperature, "seed": c.seed,
                                   "num_predict": call.max_tokens}}
            if c.kontextus:
                payload["options"]["num_ctx"] = c.kontextus
            if c.tartas:
                payload["keep_alive"] = c.tartas
            if not c.gondolkodas:
                payload["think"] = False
            return f"{c.url}/api/chat", payload
        payload = {"model": c.modell, "messages": messages, "temperature": call.temperature,
                   "max_tokens": call.max_tokens, "seed": c.seed,
                   "response_format": {"type": "json_schema",
                                       "json_schema": {"name": name, "strict": True, "schema": schema}}}
        return f"{c.url}/chat/completions", payload

    def _parse(self, resp: dict) -> Reply:
        if self.cfg.szolgaltato == "ollama":
            reply = Reply(text=resp.get("message", {}).get("content", ""), model=resp.get("model", self.cfg.modell),
                          digest=self._digest, tokens_in=resp.get("prompt_eval_count"),
                          tokens_out=resp.get("eval_count"),
                          idok={name: round(resp[key] / 1e6) for key, name in _NS.items()
                                if isinstance(resp.get(key), (int, float))})
            if self.cfg.kontextus and reply.tokens_in is not None:
                reply.kontextus_tele = reply.tokens_in + (reply.tokens_out or 0) >= self.cfg.kontextus - 8
            return reply
        usage = resp.get("usage") or {}
        return Reply(text=resp["choices"][0]["message"].get("content") or "",
                     model=resp.get("model", self.cfg.modell), tokens_in=usage.get("prompt_tokens"),
                     tokens_out=usage.get("completion_tokens"))

    def chat(self, call_name: str, messages: list[dict], schema: dict, name: str) -> Reply:
        """Egy hívás JSON-sémához kötött kimenettel. Hibánál újrapróbál, végül LLMUnavailable."""
        call = self.cfg.hivasok[call_name]
        url, payload = self._request(call, messages, schema, name)
        headers = {"Authorization": f"Bearer {self.cfg.api_kulcs}"} if self.cfg.szolgaltato == "api" else None
        last = ""
        t0 = time.perf_counter()
        for attempt in range(self.cfg.max_retries + 1):
            try:
                resp = self.http(url, payload, self.cfg.timeout_s, headers)
                reply = self._parse(resp)
                reply.latency_ms = (time.perf_counter() - t0) * 1000.0
                reply.retries = attempt
                return reply
            except urllib.error.HTTPError as exc:
                last = _http_error_text(exc)
                if "think" in last.lower() and "think" in payload:     # nem gondolkodó modell
                    payload = {k: v for k, v in payload.items() if k != "think"}
                    continue
                if exc.code < 500:
                    raise LLMUnavailable(f"A nyelvi modell hibát adott ({exc.code}): {last}") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = str(getattr(exc, "reason", exc))
            if attempt < self.cfg.max_retries:
                self.sleep(0.5 * 2 ** attempt)
        raise LLMUnavailable(f"A nyelvi modell nem válaszolt ({last}).")

    def preload(self, timeout: float = 120.0) -> bool:
        """Betölti a modellt a memóriába (Ollama: üres üzenetlistás hívás), hogy az első kérdésnek
        ne kelljen erre várnia. Ugyanazzal a kontextusmérettel, mint a hívások — különben a
        modell az első kérdésnél újratöltődne. Hiba esetén csak hamisat ad."""
        c = self.cfg
        if c.szolgaltato != "ollama":
            return False
        payload: dict = {"model": c.modell, "messages": []}
        if c.kontextus:
            payload["options"] = {"num_ctx": c.kontextus}
        if c.tartas:
            payload["keep_alive"] = c.tartas
        try:
            self.http(f"{c.url}/api/chat", payload, timeout, None)
            return True
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return False

    # ------------------------------------------------------------------ napló
    def log(self, **event) -> None:
        """Egy sor a logs/llm_calls.jsonl-ba (a hívó adja hozzá az érvényességet)."""
        if self.log_path is None:
            return
        row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "szolgaltato": self.cfg.szolgaltato, **event}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
