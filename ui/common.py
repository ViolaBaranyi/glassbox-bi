"""
A felület közös Streamlit-elemei: gyorsítótárazott betöltők, oldalsáv, fejléc.

A gyorsítótárak kulcsa a tárházfájl útvonala + módosítási ideje (ui.data.stamp):
ha a tárházat újraépíted (python demo.py), a felület magától frissül, nem kell
újraindítani.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from data.db import WarehouseUnavailable
from ui import backend as d
from xai import narrative as nv
from xai.models import KINDS

SHOW_OUTCOME = "mutasd_kimenet"     # az oldalsáv kapcsolója (a valós kimenet mutatása)


def _key() -> tuple[str, str, str]:
    p = d.db_path()
    return str(p), d.stamp(p), str(d.cache_path())


# ------------------------------------------------------------ betöltők
@st.cache_data(show_spinner=False, max_entries=4)
def _overview(path: str, stamp: str) -> dict:
    return d.overview(Path(path))


@st.cache_data(show_spinner=False, max_entries=4)
def _monthly(path: str, stamp: str):
    return d.monthly(Path(path))


@st.cache_data(show_spinner=False, max_entries=4)
def _windows(path: str, stamp: str):
    return d.windows(Path(path))


@st.cache_data(show_spinner=False, max_entries=32)
def _by_dimension(path: str, stamp: str, dim: str, min_n: int):
    return d.by_dimension(dim, min_n, Path(path))


@st.cache_resource(show_spinner=False, max_entries=2)
def _bundle(path: str, stamp: str, cache: str):
    from xai.models import load_bundle
    return load_bundle(Path(path), cache_path=Path(cache))


@st.cache_data(show_spinner=False, max_entries=2)
def _risk(path: str, stamp: str, cache: str):
    return d.risk_table(_bundle(path, stamp, cache))


@st.cache_data(show_spinner=False, max_entries=64)
def _order(path: str, stamp: str, cache: str, order_key: str, period_avg: float, window: str):
    return d.order_detail(_bundle(path, stamp, cache), order_key, k=12, period_avg=period_avg,
                          record_window=window)


@st.cache_data(show_spinner=False, max_entries=8)
def _calibration(path: str, stamp: str, cache: str, kind: str):
    return d.calibration(_bundle(path, stamp, cache), kind)


@st.cache_data(show_spinner=False, max_entries=16)
def _bands(path: str, stamp: str, cache: str, kind: str, window: str):
    return d.band_table(_bundle(path, stamp, cache), kind, window)


@st.cache_data(show_spinner=False, max_entries=4)
def _capture(path: str, stamp: str, cache: str, share: float):
    return d.capture(_bundle(path, stamp, cache), share)


@st.cache_data(show_spinner=False, max_entries=4)
def _sample(path: str, stamp: str, cache: str, kinds: tuple):
    return d.sample_explanations(_bundle(path, stamp, cache), kinds)


@st.cache_data(show_spinner=False, max_entries=2)
def _integrity(path: str, stamp: str, cache: str):
    return d.integrity(_bundle(path, stamp, cache), d.locked_results(), Path(path))


@st.cache_resource(show_spinner=False, max_entries=2)
def _semantic_catalog(version: int):
    return d.semantic_catalog()


def _catalog_version() -> int:
    """A katalógusfájl módosítási ideje: ha átírják, a felület újratölti (újraindítás nélkül)."""
    from semantic.catalog import KATALOGUS
    return KATALOGUS.stat().st_mtime_ns


@st.cache_data(show_spinner=False, max_entries=4)
def _semantic_whitelist(path: str, stamp: str, version: int):
    return d.semantic_whitelist(Path(path))


@st.cache_data(show_spinner=False, max_entries=128)
def _ask(path: str, stamp: str, version: int, spec_json: str):
    import json
    return d.ask(json.loads(spec_json), Path(path), _semantic_catalog(version),
                 _semantic_whitelist(path, stamp, version))


@st.cache_data(show_spinner=False, ttl=20)
def llm_status() -> tuple[bool, str]:
    """Elérhető-e a nyelvi modell — 20 másodpercig gyorsítótárazva (ne kérdezze minden kattintásnál)."""
    return d.llm_status()


@st.cache_data(show_spinner=False, max_entries=64)
def _ask_free(path: str, stamp: str, version: int, llm: str, question: str):
    return d.ask_free(question, Path(path), _semantic_catalog(version), _semantic_whitelist(path, stamp, version))


@st.cache_data(show_spinner=False, max_entries=64)
def _ask_recorded(path: str, stamp: str, version: int, rec_id: str):
    return d.ask_recorded(rec_id, Path(path), _semantic_catalog(version),
                          _semantic_whitelist(path, stamp, version))


@st.cache_data(show_spinner=False)
def recorded() -> dict:
    """A bemutató mód rögzített modellválaszai (docs/bemutato_valaszok.json)."""
    from ui import bemutato
    return bemutato.load()


def ask_recorded(rec_id: str):
    """Bemutató mód: a rögzített kérdés végig a szabad szöveges úton (gyorsítótárazva)."""
    return _ask_recorded(*_key()[:2], _catalog_version(), rec_id)


def _llm_key() -> str:
    """A nyelvi beállítás ujjlenyomata a gyorsítótárhoz: modell + a promptok változata és ideje
    (ha a prompt változik, a régi válasz ne jöjjön vissza a gyorsítótárból)."""
    from narrative.client import ROOT, load_config
    cfg = load_config()
    parts = [cfg.szolgaltato, cfg.modell]
    for call in sorted(cfg.hivasok.values(), key=lambda c: c.prompt):
        f = ROOT / call.prompt
        parts.append(f"{call.version}@{f.stat().st_mtime_ns if f.exists() else 0}")
    return "|".join(parts)


def ask_free(question: str):
    """Szabad szöveges kérdés (nyelvi modell + két kapu); ugyanarra a kérdésre ugyanaz a válasz,
    amíg az adat, a katalógus, a modell és a promptok nem változnak."""
    answer = _ask_free(*_key()[:2], _catalog_version(), _llm_key(), question.strip())
    if answer.modell_hiba:          # a modell nem volt elérhető: ezt ne jegyezze meg
        _ask_free.clear()
    return answer


_WARMED: dict[str, float] = {}


def warm_llm(every_s: float = 600.0) -> bool:
    """A helyi modell betöltése a háttérben (legfeljebb tízpercenként), amíg a felhasználó a
    kérdést gépeli — így az első kérdésnek nem kell a betöltésre várnia. Vissza: indult-e."""
    import threading
    import time
    client = d.llm_client()
    if client.cfg.szolgaltato != "ollama":
        return False
    key = f"{client.cfg.url}|{client.cfg.modell}"
    now = time.monotonic()
    if now - _WARMED.get(key, -1e12) < every_s:
        return False
    _WARMED[key] = now
    threading.Thread(target=client.preload, name="nyelvi-modell-betoltes", daemon=True).start()
    return True


def overview() -> dict:
    return _overview(*_key()[:2])


def semantic_catalog():
    return _semantic_catalog(_catalog_version())


def semantic_whitelist():
    return _semantic_whitelist(*_key()[:2], _catalog_version())


def ask_gate(text: str):
    """Csak a KAPU ① (a „Próbáld ki az 1. kaput” doboznak): nem fut le semmi az adatbázison."""
    from semantic import spec as sp
    return sp.check(text, semantic_catalog(), semantic_whitelist())


def ask(raw: dict):
    """KAPU ① → SQL → eredmény → sablonos válasz (gyorsítótárazva a kérdés szövegére)."""
    import json
    return _ask(*_key()[:2], _catalog_version(),
                json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str))


def monthly():
    return _monthly(*_key()[:2])


def windows():
    return _windows(*_key()[:2])


def by_dimension(dim: str, min_n: int):
    return _by_dimension(*_key()[:2], dim, int(min_n))


def window_period(name: str) -> str:
    """Egy időszak hónapokban, közérthetően: „2018. június–augusztus"."""
    import pandas as pd
    w = windows().set_index("ablak")
    if name not in w.index:
        return ""
    start = pd.Timestamp(w.loc[name, "kezdet"])
    end = pd.Timestamp(w.loc[name, "veg"]) - pd.Timedelta(seconds=1)   # a vég kizáró határ
    if start.year == end.year:
        if start.month == end.month:
            return f"{start.year}. {nv.MONTHS[start.month - 1]}"
        return f"{start.year}. {nv.MONTHS[start.month - 1]}–{nv.MONTHS[end.month - 1]}"
    return f"{start.year}. {nv.MONTHS[start.month - 1]} – {end.year}. {nv.MONTHS[end.month - 1]}"


def bundle():
    with st.spinner("A négy modell betöltése… (az első indításkor betanítja őket: kb. egy perc)"):
        return _bundle(*_key())


def risk_table():
    bundle()
    return _risk(*_key())


def record_window() -> str:
    """Melyik időszak kimenetei mutatják a becslések múltbeli pontosságát?
    Valós kimenettel a teszt-időszaké (utólag); nélküle a validációs időszaké — azt egy
    éles bevezetéskor, a teszt-időszak elején már ismerni lehetett volna."""
    return "test" if show_outcome() else "valid"


def order_detail(order_key: str, period_avg: float) -> dict:
    with st.spinner("A rendelés magyarázata négy modellel…"):
        return _order(*_key(), str(order_key), float(period_avg), record_window())


def calibration(kind: str):
    bundle()
    return _calibration(*_key(), kind)


def bands(kind: str, window: str):
    bundle()
    return _bands(*_key(), kind, window)


def capture(share: float = 0.10) -> dict:
    bundle()
    return _capture(*_key(), float(share))


def sample_explanations(kinds) -> tuple:
    bundle()
    slow = "random_forest" in kinds
    msg = ("Magyarázatok a mintán… (a random forest lassú: kb. fél perc)" if slow
           else "Magyarázatok a mintán…")
    with st.spinner(msg):
        return _sample(*_key(), tuple(kinds))


def integrity() -> dict:
    bundle()
    return _integrity(*_key())


def locked() -> dict:
    return d.locked_results()


# --------------------------------------------------------------- elemek
def require_warehouse() -> dict:
    """Az áttekintő adatok — ha nincs tárház, érthető hibaüzenettel megáll."""
    try:
        return overview()
    except WarehouseUnavailable as exc:
        st.error("**Az adatbázis (tárház) még nincs felépítve, ezért nincs mit megmutatni.**\n\n"
                 + str(exc).split("\n")[0])
        st.markdown("Futtasd le egyszer a teljes demót (letölti az adatot és felépíti az "
                    "adatbázist), majd frissítsd ezt az oldalt:")
        st.code("uv run demo.py\n# vagy lépésenként:\nuv run python -m data.fetch_olist\nuv run python -m data.build_warehouse",
                language="bash")
        st.stop()


def page_header(title: str, subtitle: str) -> None:
    st.title(title)
    st.caption(subtitle)


def intro(text: str, expanded_help: str | None = None) -> None:
    """Az oldal tetején: mit látsz itt, hétköznapi nyelven (+ opcionális részletes súgó)."""
    st.info(text, icon=":material/lightbulb:")
    if expanded_help:
        with st.expander("Részletesebben: hogyan olvasd ezt az oldalt?"):
            st.markdown(expanded_help)


def details(label: str = "Szakmai részletek"):
    """Lenyitható rész a szakembereknek (a dolgozathoz), alapból csukva."""
    return st.expander(f":material/science: {label}")


def show_outcome() -> bool:
    return bool(st.session_state.get(SHOW_OUTCOME, True))


def ink():
    """A grafikonok felirat- és vonalszínei az aktuális témához (világos / sötét)."""
    from ui import charts
    try:
        theme = st.context.theme.type
    except AttributeError:          # tesztkörnyezetben nincs böngésző-téma
        theme = None
    return charts.ink_for(theme)


def sidebar() -> None:
    with st.sidebar:
        st.markdown("**Üvegdoboz BI**")
        st.caption("Késések előrejelzése, érthető magyarázattal · EKÖP-26-I-1")
        try:
            ov = overview()
        except WarehouseUnavailable:
            st.warning("Még nincs adatbázis — lásd a főoldalt.")
            return
        source = ("valódi rendelések egy brazil webáruház-platformról (Olist)"
                  if ov["adatforras"] == "valós" else "szintetikus (kitalált) próbaadat")
        st.markdown(f"**Adat:** {source}  \n"
                    f"{nv.fmt_num(ov['rendelesek'], 0)} kézbesített rendelés  \n"
                    f"{nv.fmt_date(ov['elso'])} – {nv.fmt_date(ov['utolso'])}")
        st.caption(f"adatbázis frissítve: {ov['epitve'][:16]} (UTC)")
        base = (locked().get("alapfutas") or {})
        n_trees = (base.get("vegso_modell") or {}).get("fak_szama")
        if ov["adatforras"] == "valós" and n_trees:
            st.markdown(f"**Modell:** LightGBM ({n_trees} döntési fából álló modell), pontosan az, "
                        "amelyet a lezárt mérésben kiértékeltünk")
        else:
            st.markdown("**Modell:** LightGBM (a próbaadaton betanítva)")
        st.toggle("Mutassa, mi történt valójában", value=True, key=SHOW_OUTCOME,
                  help="Bekapcsolva a felület azt is megmutatja, hogy egy rendelés ténylegesen "
                       "késett-e — ezt ma már tudjuk. Kikapcsolva úgy működik, mintha a csomag még "
                       "úton lenne, ahogy egy valódi döntési helyzetben.")
        st.divider()
        st.page_link("oldalak/sugo.py", label="Súgó: fogalmak, rövidítések", icon=":material/help:")
        st.caption("Minden szám közvetlenül az adatokból vagy a modellből jön; a felület semmit nem "
                   "„saccol”. Csak ezen a gépen fut (localhost), az adat nem megy ki az internetre.")


MODEL_ORDER = list(KINDS)
