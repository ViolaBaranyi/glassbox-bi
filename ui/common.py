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
def _sample(path: str, stamp: str, cache: str, kinds: tuple):
    return d.sample_explanations(_bundle(path, stamp, cache), kinds)


@st.cache_data(show_spinner=False, max_entries=2)
def _integrity(path: str, stamp: str, cache: str):
    return d.integrity(_bundle(path, stamp, cache), d.locked_results(), Path(path))


def overview() -> dict:
    return _overview(*_key()[:2])


def monthly():
    return _monthly(*_key()[:2])


def windows():
    return _windows(*_key()[:2])


def by_dimension(dim: str, min_n: int):
    return _by_dimension(*_key()[:2], dim, int(min_n))


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
        st.error("**A tárház nem érhető el.**\n\n" + str(exc).split("\n")[0])
        st.markdown("Építsd fel (vagy futtasd a teljes demót), majd frissítsd ezt az oldalt:")
        st.code("python demo.py\n# vagy lépésenként:\npython -m data.fetch_olist\npython -m data.build_warehouse",
                language="bash")
        st.stop()


def page_header(title: str, subtitle: str) -> None:
    st.title(title)
    st.caption(subtitle)


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
        st.caption("Magyarázható késés-előrejelzés egy self-service BI-felületen · EKÖP-26-I-1")
        try:
            ov = overview()
        except WarehouseUnavailable:
            st.warning("Nincs tárház — lásd a főoldalt.")
            return
        st.markdown(f"**Adat:** {ov['adatforras']} Olist-rendelések  \n"
                    f"{nv.fmt_num(ov['rendelesek'], 0)} kézbesített rendelés  \n"
                    f"{ov['elso'][:7]} – {ov['utolso'][:7]}")
        st.caption(f"tárház építve: {ov['epitve']}")
        base = (locked().get("alapfutas") or {})
        n_trees = (base.get("vegso_modell") or {}).get("fak_szama")
        if ov["adatforras"] == "valós" and n_trees:
            st.markdown(f"**Modell:** LightGBM, {n_trees} fa — a lezárt v3 protokoll szerint")
        else:
            st.markdown("**Modell:** LightGBM — a fák számát a keresztvalidáció adja")
        st.toggle("Valós kimenet mutatása", value=True, key=SHOW_OUTCOME,
                  help="Történeti adat: utólag tudjuk, késett-e a rendelés. Döntési helyzetben ez "
                       "még nem ismert — kikapcsolva a felület úgy viselkedik, mint élesben.")
        st.divider()
        st.caption("Minden szám a tárházból (SQL) vagy a lezárt modellekből jön; a felület "
                   "nem számol fejben. Csak ezen a gépen fut (localhost).")


MODEL_ORDER = list(KINDS)
