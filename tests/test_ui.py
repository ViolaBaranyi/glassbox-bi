"""
A BI-felület tesztjei — szintetikus tárházon.

  * az adatréteg (ui.backend) számai egymással és az SQL-lel összhangban vannak
    (havi összeg = összes rendelés, Wilson-intervallum tartalmazza az arányt, …);
  * egy rendelés magyarázata: a négy modell, additív tényezők, a LightGBM
    becslése = a kockázati lista értéke;
  * a lezárt eredmények táblái és a páros ítélet a docs/ fájlokból;
  * a grafikonok érvényes Vega-Lite-specifikációt adnak;
  * a felület minden oldala hiba nélkül lefut (Streamlit AppTest), és tárház
    nélkül érthető hibaüzenetet ad.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ui import backend as be
from ui import charts
from xai import narrative as nv
from xai.models import KINDS, NAMES

APP = Path(__file__).resolve().parent.parent / "ui" / "app.py"


# --------------------------------------------------------------- áttekintés
def test_attekintes_szamai_egybevagnak(synth_db):
    ov = be.overview(synth_db)
    m = be.monthly(synth_db)
    assert m["rendelesek"].sum() == ov["rendelesek"]
    assert m["kesett"].sum() / m["rendelesek"].sum() == pytest.approx(ov["kesesi_arany"])
    assert ((m["ci_also"] <= m["kesesi_arany"]) & (m["kesesi_arany"] <= m["ci_felso"])).all()
    assert (m["megbizhato"] == (m["rendelesek"] >= be.MIN_MONTH_ORDERS)).all()
    assert ov["adatforras"] == "szintetikus"

    w = be.windows(synth_db)
    assert list(w["ablak"]) == ["tanító", "validációs", "teszt"]
    assert w["rendelesek"].sum() == ov["rendelesek"]
    assert (w["kezdet"] < w["veg"]).all()


def test_bontas_dimenzio_szerint(synth_db):
    ov = be.overview(synth_db)
    for dim in be.DIMENSIONS:
        df = be.by_dimension(dim, 50, synth_db)
        assert len(df) > 0, dim
        assert (df["rendelesek"] >= 50).all()
        assert df["kesesi_arany"].is_monotonic_decreasing
        assert ((df["ci_also"] <= df["kesesi_arany"]) & (df["kesesi_arany"] <= df["ci_felso"])).all()
        assert np.allclose(df["kesett"] / df["rendelesek"], df["kesesi_arany"])
        assert (df["megnevezes"] == [be.value_label(dim, v) for v in df["ertek"]]).all()
        if dim != "kategoria":
            assert "regio" in df and df["megnevezes"].str.endswith(")").all()  # „São Paulo (SP)"
        full = be.by_dimension(dim, 1, synth_db)                      # küszöb nélkül mind
        assert full["rendelesek"].sum() == ov["rendelesek"], dim
    with pytest.raises(ValueError):
        be.by_dimension("nincs_ilyen", 10, synth_db)


# ------------------------------------------------------------------ rendelés
def test_kockazati_lista(synth_bundle):
    rt = be.risk_table(synth_bundle)
    assert len(rt) == len(synth_bundle.split.test)
    assert rt["valoszinuseg"].is_monotonic_decreasing
    assert list(rt["rang"]) == list(range(1, len(rt) + 1))
    assert rt["relativ"].mean() == pytest.approx(1.0)
    assert (rt["relativ_szoveg"] == [f"{nv.fmt_num(v, 1)}×" for v in rt["relativ"]]).all()
    assert not rt["relativ_szoveg"].str.contains(r"\.").any()          # „13,1×", nem „13.1×"
    assert be.period_average(synth_bundle) == pytest.approx(rt["valoszinuseg"].mean())
    assert not rt["kategoria_nev"].str.contains("_").any()          # magyar kategórianév
    assert rt["vevo_nev"].str.endswith(")").all()
    cap = be.capture(synth_bundle, 0.10)
    assert cap["felso_rendelesek"] == round(0.10 * len(rt))
    top = rt.head(cap["felso_rendelesek"])
    assert cap["kesett_felso"] == int(top["kesett"].sum())             # ugyanaz a sorrend
    assert cap["kesett_osszes"] == int(rt["kesett"].sum())
    assert 0 <= cap["kesesek_aranya_a_felsoben"] <= 1


def test_rendeles_magyarazata_negy_modellel(synth_bundle):
    rt = be.risk_table(synth_bundle)
    key = rt["order_key"].iloc[0]
    det = be.order_detail(synth_bundle, key, k=5)
    assert det["order_key"] == key and det["ablak"] == "teszt"
    assert det["valoszinuseg"] == pytest.approx(rt["valoszinuseg"].iloc[0], abs=1e-12)
    assert det["additivitasi_elteres_pp"] < 1e-9
    assert len(det["okok"]) == 5 and len(det["tenyezok"]) == 21
    assert det["relativ_kockazat"] == pytest.approx(det["valoszinuseg"] / det["idoszak_atlag"])
    assert nv.fmt_pct(det["valoszinuseg"]) in det["narrativa"]
    assert set(det["modellek"]) == set(KINDS)
    for kind, m in det["modellek"].items():
        fr = m["tenyezok"]
        assert len(fr) == 21, kind
        assert fr["hatas_pp"].sum() == pytest.approx(100 * (m["valoszinuseg"] - m["alap"]), abs=1e-7), kind
        assert m["ter"] == ("log-odds" if kind in ("lightgbm", "logreg") else "valószínűség")

    ag = be.agreement(det)
    assert list(ag["modell"]) == [NAMES[k] for k in KINDS]
    assert ag["kozos_a_lightgbm_mel"].iloc[0] == "3/3"
    comp = be.model_comparison(det, top=6)
    assert len(comp) == 6 * 4 and set(comp["modell"]) == set(NAMES.values())

    with pytest.raises(ValueError, match="Nincs ilyen"):
        be.order_detail(synth_bundle, "nincs-ilyen-rendeles")
    train_key = synth_bundle.meta.loc[synth_bundle.split.train[0], "order_key"]
    assert be.order_detail(synth_bundle, train_key)["ablak"] == "tanító"


def test_kalibracio_es_mintabeli_osszegzes(synth_bundle):
    n_test = len(synth_bundle.split.test)
    for kind in KINDS:
        cal = be.calibration(synth_bundle, kind)
        assert cal["rendelesek"].sum() == n_test
        assert ((cal["ci_also"] <= cal["tenyleges_arany"]) & (cal["tenyleges_arany"] <= cal["ci_felso"])).all()

    sample, expl = be.sample_explanations(synth_bundle, n=150, n_slow=20)
    assert len(sample) == 150 and len(expl["random_forest"]) == 20
    for kind, pp in expl.items():
        assert list(pp.columns) == nv.DISPLAY_FEATURES, kind
    gi = be.global_importance_table(expl)
    assert set(gi["modell"]) == set(NAMES.values())
    assert (gi.groupby("modell")["rang"].max() == 21).all()
    dep = be.dependence(sample, expl["lightgbm"], nv.MONTH)
    assert dep["ertek"].between(1, 12).all() and len(dep) == 150
    dep2 = be.dependence(sample, expl["random_forest"], "vallalt_ido_nap")
    assert len(dep2) == 20


def test_becslesi_savok_es_multbeli_pontossag(synth_bundle):
    b = synth_bundle
    assert list(be.band_index([0.0, 0.0199, 0.02, 0.05, 0.2999, 0.3, 0.99])) == [0, 0, 1, 2, 5, 6, 6]
    assert [be.band_name(j) for j in (0, 2, 6)] == ["2% alatt", "5–10%", "30% fölött"]
    assert [be.band_phrase(j) for j in (0, 2, 6)] == ["2% alatti", "5–10%-os", "30% feletti"]
    assert be.verdict(0.30, (0.04, 0.24), 39) == "túlbecsült"
    assert be.verdict(0.03, (0.04, 0.24), 39) == "alábecsült"
    assert be.verdict(0.10, (0.04, 0.24), 39) == "összhangban"
    assert be.verdict(0.30, (0.04, 0.24), be.MIN_BAND_N - 1) == "kevés adat"

    for window, idx in (("test", b.split.test), ("valid", b.split.valid)):
        bt = be.band_table(b, "lightgbm", window)
        assert len(bt) == len(be.BANDS) - 1
        assert bt["rendelesek"].sum() == len(idx) and bt["kesett"].sum() == int(b.y.loc[idx].sum())
        has = bt["rendelesek"] > 0
        assert ((bt.loc[has, "ci_also"] <= bt.loc[has, "tenyleges_arany"])
                & (bt.loc[has, "tenyleges_arany"] <= bt.loc[has, "ci_felso"])).all()
        assert (bt.loc[has, "atlag_becsles"] >= bt.loc[has, "also"]).all()
        assert (bt.loc[has, "atlag_becsles"] < bt.loc[has, "felso"]).all()
    with pytest.raises(ValueError, match="Ismeretlen ablak"):
        be.band_table(b, "lightgbm", "train")

    # a teszt-ablak egy rendelése: a saját kimenete kimarad a hasonlók közül
    rt = be.risk_table(b)
    key, p = rt["order_key"].iloc[0], float(rt["valoszinuseg"].iloc[0])
    bt = be.band_table(b, "lightgbm", "test")
    row = bt.iloc[int(be.band_index([p])[0])]
    rec = be.similar_orders(b, p, key, window="test")
    assert rec["onmaga_kihagyva"] and rec["rendelesek"] == row["rendelesek"] - 1
    assert rec["kesett"] == row["kesett"] - int(rt["kesett"].iloc[0])
    assert rec["idoszak_arany"] == pytest.approx(rt["kesett"].mean())
    # tanító ablakbeli rendelésnél nincs mit kihagyni
    tkey = str(b.meta.loc[b.split.train[0], "order_key"])
    rec2 = be.similar_orders(b, p, tkey, window="test")
    assert not rec2["onmaga_kihagyva"] and rec2["rendelesek"] == row["rendelesek"]

    det = be.order_detail(b, key)
    assert det["hasonlok"]["ablak"] == "test" and det["hasonlok"]["onmaga_kihagyva"]
    assert det["narrativa"].endswith(nv.record_phrase(det["hasonlok"]))
    det_v = be.order_detail(b, key, record_window="valid")
    assert det_v["hasonlok"]["ablak"] == "valid" and not det_v["hasonlok"]["onmaga_kihagyva"]
    det_none = be.order_detail(b, key, record_window=None)
    assert det_none["hasonlok"] is None and "Ha a modell ebben a tartományban" in det_none["narrativa"]


def test_becslesi_savcsoportok(synth_bundle):
    bt = be.band_table(synth_bundle, "lightgbm", "test")
    g = be.band_groups(bt).set_index("csoport")
    assert list(g.index) == ["alacsony", "közepes", "magas"]
    assert g["rendelesek"].sum() == bt["rendelesek"].sum() and g["kesett"].sum() == bt["kesett"].sum()
    for name, lo, hi in be.BAND_GROUPS:
        part = bt[(bt["also"] >= lo) & (bt["felso"] <= hi)]
        assert g.loc[name, "rendelesek"] == part["rendelesek"].sum(), name
        if g.loc[name, "rendelesek"]:
            w = (part["atlag_becsles"].fillna(0) * part["rendelesek"]).sum() / part["rendelesek"].sum()
            assert g.loc[name, "atlag_becsles"] == pytest.approx(w)
            assert g.loc[name, "itelet"] == be.verdict(g.loc[name, "atlag_becsles"],
                                                       (g.loc[name, "ci_also"], g.loc[name, "ci_felso"]),
                                                       int(g.loc[name, "rendelesek"]))
    # kézzel összerakott sávtábla: a csoport ítélete a súlyozott átlagból és a Wilson-sávból jön
    toy = pd.DataFrame({"also": [0.0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30],
                        "felso": [0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 1.0],
                        "rendelesek": [100, 100, 100, 0, 0, 30, 10], "kesett": [1, 3, 7, 0, 0, 3, 1],
                        "atlag_becsles": [0.01, 0.03, 0.07, np.nan, np.nan, 0.25, 0.40]})
    tg = be.band_groups(toy).set_index("csoport")
    assert tg.loc["magas", "rendelesek"] == 40 and tg.loc["magas", "kesett"] == 4
    assert tg.loc["magas", "atlag_becsles"] == pytest.approx((30 * 0.25 + 10 * 0.40) / 40)
    assert tg.loc["magas", "itelet"] == "túlbecsült"                  # 28,75% vs 10% [4,0; 23,1]
    assert tg.loc["közepes", "rendelesek"] == 100 and tg.loc["közepes", "itelet"] == "összhangban"


def test_ellenorzes_szintetikus_adaton(synth_bundle, synth_db):
    chk = be.integrity(synth_bundle, be.locked_results(), synth_db)
    assert chk["statusz"] == "szintetikus" and chk["modellek"] is None


# ------------------------------------------------------- lezárt eredmények
def test_lezart_eredmenyek_tablai():
    res = be.locked_results()
    tab = be.results_table(res)
    assert list(tab["kulcs"]) == list(KINDS)
    assert ((tab["pr_auc_also"] <= tab["pr_auc"]) & (tab["pr_auc"] <= tab["pr_auc_felso"])).all()
    pair = be.paired_table(res)
    verdict = pair.set_index(["referencia", "mutato"])["itelet"]
    assert verdict[("logisztikus regresszió", "pr_auc")] == "nem kimutatható"
    assert verdict[("döntési fa", "roc_auc")] == "a LightGBM jobb"
    assert verdict[("döntési fa", "brier")] == "a LightGBM jobb"       # kisebb Brier = jobb
    prov = be.provenance(res)
    assert [p["git"] for p in prov] == ["6f1b792", "76934b1"]
    assert be.results_table({"referencia": None}) is None


def test_paros_itelet_iranya():
    fake = {"referencia": {"modellek": {"x": {"nev": "X", "paros_lightgbm_minusz_referencia": {
        "pr_auc": {"kulonbseg": -0.02, "ci95": [-0.03, -0.01]},
        "roc_auc": {"kulonbseg": 0.01, "ci95": [-0.01, 0.02]},
        "brier": {"kulonbseg": 0.002, "ci95": [0.001, 0.003]}}}}}}
    v = be.paired_table(fake).set_index("mutato")["itelet"]
    assert v["pr_auc"] == "a referencia jobb"
    assert v["roc_auc"] == "nem kimutatható"
    assert v["brier"] == "a referencia jobb"                           # nagyobb Brier = rosszabb


# ----------------------------------------------------------------- grafikonok
def test_grafikonok_ervenyes_specifikaciot_adnak(synth_db, synth_bundle):
    ov = be.overview(synth_db)
    top, vol = charts.monthly_chart(be.monthly(synth_db), be.windows(synth_db))
    det = be.order_detail(synth_bundle, be.risk_table(synth_bundle)["order_key"].iloc[0])
    sample, expl = be.sample_explanations(synth_bundle, kinds=("lightgbm", "logreg"), n=80)
    gi = be.global_importance_table(expl)
    res = be.locked_results()
    specs = [
        top, vol,
        charts.dimension_chart(be.by_dimension("vevo_allam", 50, synth_db), ov["kesesi_arany"], "állam"),
        charts.reasons_chart(det["tenyezok"].head(8)),
        charts.comparison_heatmap(be.model_comparison(det), [NAMES[k] for k in KINDS]),
        charts.pr_auc_forest(be.results_table(res), 0.0361),
        charts.reliability_chart(be.calibration(synth_bundle)),
        charts.importance_heatmap(gi, [NAMES["lightgbm"], NAMES["logreg"]]),
        charts.dependence_chart(be.dependence(sample, expl["lightgbm"], "vallalt_ido_nap"), "idő", False),
        charts.dependence_chart(be.dependence(sample, expl["lightgbm"], "kategoria"), "kategória", True),
        charts.dependence_chart(be.dependence(sample, expl["lightgbm"], nv.MONTH).assign(
            ertek=lambda d: [nv.MONTHS[int(v) - 1] for v in d["ertek"]]), "hónap", True, order=nv.MONTHS),
        charts.dependence_chart(be.dependence(sample, expl["lightgbm"], "dij_arany"),
                                nv.axis_title("dij_arany"), False, percent=True),
        charts.state_tile_map(be.by_dimension("vevo_allam", 50, synth_db), ov["kesesi_arany"]),
        charts.state_tile_map(),
    ]
    for ch in specs:
        spec = ch.to_dict()           # az Altair itt validál a Vega-Lite sémával szemben
        assert "$schema" in spec
    # sötét témával is érvényes, és a feliratok a sötét téma színeit kapják
    dark = charts.reasons_chart(det["tenyezok"].head(8), ink=charts.DARK).to_dict()
    assert charts.DARK.text in str(dark) and charts.LIGHT.text not in str(dark)
    for ch in (charts.dimension_chart(be.by_dimension("vevo_allam", 50, synth_db), ov["kesesi_arany"],
                                      "állam", ink=charts.DARK),
               charts.pr_auc_forest(be.results_table(res), 0.0361, ink=charts.DARK),
               charts.reliability_chart(be.calibration(synth_bundle), ink=charts.DARK)):
        assert "$schema" in ch.to_dict()


def test_negyzetracsos_terkep(synth_db):
    from xai import labels
    ov = be.overview(synth_db)
    df = be.by_dimension("vevo_allam", 50, synth_db)
    spec = charts.state_tile_map(df, ov["kesesi_arany"], count_title="ide ment").to_dict()
    rows = next(r for r in spec["datasets"].values() if r and "kod" in r[0])
    assert sorted(r["kod"] for r in rows) == sorted(labels.STATES)             # mind a 27, egyszer
    shown = {r["kod"] for r in rows if r["kesesi_arany"] is not None}
    assert shown == set(df["ertek"]) & set(labels.STATES)                     # a küszöb alattiak szürkék
    by_code = {r["kod"]: r for r in rows}
    for _, r in df.iterrows():
        if r["ertek"] in by_code:
            assert by_code[r["ertek"]]["arany_szoveg"] == nv.fmt_pct(r["kesesi_arany"])
    # a szürke alapréteg minden államot mutat, a színezett csak az adattal rendelkezőket
    assert spec["layer"][0]["mark"]["color"] == charts.NO_DATA
    assert spec["layer"][1]["transform"][0]["filter"] == "isValid(datum.kesesi_arany)"
    assert spec["layer"][1]["encoding"]["color"]["scale"]["domainMid"] == pytest.approx(ov["kesesi_arany"])
    assert "ide ment" in str(spec["layer"][0]["encoding"]["tooltip"])
    # régió-mód (Súgó): öt régió a jelmagyarázatban
    reg = charts.state_tile_map().to_dict()
    assert reg["layer"][0]["encoding"]["color"]["scale"]["domain"] == list(charts.REGION_COLORS)
    assert set(charts.REGION_COLORS) == set(labels.REGIONS.values())


def test_tengelyek_magyar_szamalakkal(synth_db):
    _, vol = charts.monthly_chart(be.monthly(synth_db), be.windows(synth_db))
    axis = vol.to_dict()["encoding"]["y"]["axis"]
    assert axis["format"] == ",d" and axis["labelExpr"] == charts._THOUSANDS     # „8 000", nem „8k"
    gi = pd.DataFrame({"modell": ["M"] * 2, "tenyezo": ["a", "b"], "nev": ["A", "B"],
                       "atlag_abs_pp": [2.5, 0.5], "rang": [1, 2], "minta": [10, 10]})
    legend = charts.importance_heatmap(gi, ["M"]).to_dict()["layer"][0]["encoding"]["color"]["legend"]
    assert legend["labelExpr"] == charts._COMMA


def test_tema_es_hoterkep_feliratszine():
    assert charts.ink_for("dark") is charts.DARK
    assert charts.ink_for("light") is charts.LIGHT and charts.ink_for(None) is charts.LIGHT
    long = pd.DataFrame({"tenyezo": ["a", "a", "b", "b"], "nev": ["A", "A", "B", "B"],
                         "modell": ["M1", "M2", "M1", "M2"], "hatas_pp": [30.0, -5.0, 1.0, -28.0]})
    spec = charts.comparison_heatmap(long, ["M1", "M2"]).to_dict()
    text_color = spec["layer"][1]["encoding"]["color"]
    assert text_color["condition"]["test"] == "abs(datum['hatas_pp']) > 18"     # 0,6 × 30
    assert text_color["condition"]["value"] == "#ffffff" and text_color["value"] == "#1a1a1a"


def test_havi_vonal_megszakad_a_hianyzo_honapnal():
    m = pd.DataFrame({"honap": pd.to_datetime(["2016-10-01", "2017-01-01", "2017-02-01", "2017-03-01"]),
                      "rendelesek": [300, 800, 900, 1000], "kesett": [3, 20, 30, 40]})
    m["kesesi_arany"] = m["kesett"] / m["rendelesek"]
    m["megbizhato"] = True
    m["ci_also"], m["ci_felso"] = m["kesesi_arany"] * 0.8, m["kesesi_arany"] * 1.2
    win = pd.DataFrame({"ablak": ["tanító"], "kezdet": [pd.Timestamp("2016-10-01")],
                        "veg": [pd.Timestamp("2017-03-31")], "rendelesek": [3000]})
    top, _ = charts.monthly_chart(m, win)
    spec = top.to_dict()
    line = next(l for l in spec["layer"] if (l.get("mark") or {}).get("type") == "line"
                and "detail" in l.get("encoding", {}))
    assert line["encoding"]["detail"]["field"] == "szakasz"
    data = next(rows for rows in spec["datasets"].values() if rows and "szakasz" in rows[0])
    assert [r["szakasz"] for r in data] == [0, 1, 1, 1]     # 2016-10 külön: nov.–dec. hiányzik


def test_keves_adat_sav_a_havi_grafikonon():
    m = pd.DataFrame({"honap": pd.to_datetime(["2016-09-01", "2016-10-01", "2016-12-01", "2017-01-01",
                                               "2017-02-01"]),
                      "rendelesek": [1, 265, 1, 750, 1700], "kesett": [1, 2, 0, 22, 40]})
    m["megbizhato"] = m["rendelesek"] >= be.MIN_MONTH_ORDERS
    g = charts.gap_runs(m)
    assert len(g) == 1                                   # a szeptember az első megbízható hónap előtt van
    assert g.loc[0, "honapok"] == "2016. november – 2016. december"
    assert g.loc[0, "rendelesek_szoveg"] == "november: 0 · december: 1"      # a 0 rendeléses hónap is
    assert g.loc[0, "kezdet"] == pd.Timestamp("2016-10-17") and g.loc[0, "veg"] == pd.Timestamp("2016-12-16")
    full = m.assign(megbizhato=True)
    assert charts.gap_runs(full).loc[0, "honapok"] == "2016. november"      # csak a valóban üres hónap
    m["kesesi_arany"] = m["kesett"] / m["rendelesek"]
    m["ci_also"], m["ci_felso"] = m["kesesi_arany"] * 0.8, m["kesesi_arany"] * 1.2
    win = pd.DataFrame({"ablak": ["tanító"], "kezdet": [pd.Timestamp("2016-09-15")],
                        "veg": [pd.Timestamp("2017-03-01")], "rendelesek": [2700]})
    spec = charts.monthly_chart(m, win)[0].to_dict()
    gap_rows = next(r for r in spec["datasets"].values() if r and "rendelesek_szoveg" in r[0])
    assert gap_rows[0]["felirat"] == "kevés\nadat"
    band_rows = next(r for r in spec["datasets"].values() if r and "idoszak_szoveg" in r[0])
    assert band_rows[0]["idoszak_szoveg"] == "2016. szept. 15. – 2017. febr. 28."   # a vég kizáró határ


def _marks(spec: dict):
    if "layer" in spec:
        for layer in spec["layer"]:
            yield from _marks(layer)
    elif "mark" in spec:
        yield spec


def test_minden_jelnek_magyar_sugoja_van(synth_db, synth_bundle):
    """A Streamlit témája minden jelnek alapból a nyers mezőneveit mutatja súgóként (pl. „kezdet,
    veg, ablak", angol dátummal) — ezért minden rétegnek saját súgója van, vagy kifejezetten nincs."""
    ov = be.overview(synth_db)
    top, vol = charts.monthly_chart(be.monthly(synth_db), be.windows(synth_db))
    det = be.order_detail(synth_bundle, be.risk_table(synth_bundle)["order_key"].iloc[0])
    sample, expl = be.sample_explanations(synth_bundle, kinds=("lightgbm", "logreg"), n=80)
    res = be.locked_results()
    dims = be.by_dimension("vevo_allam", 50, synth_db)
    all_charts = [
        top, vol,
        charts.dimension_chart(dims, ov["kesesi_arany"], "állam"),
        charts.state_tile_map(dims, ov["kesesi_arany"]), charts.state_tile_map(),
        charts.reasons_chart(det["tenyezok"].head(8)),
        charts.comparison_heatmap(be.model_comparison(det), [NAMES[k] for k in KINDS]),
        charts.pr_auc_forest(be.results_table(res), 0.0361),
        charts.reliability_chart(be.calibration(synth_bundle)),
        charts.importance_heatmap(be.global_importance_table(expl), [NAMES["lightgbm"], NAMES["logreg"]]),
        charts.dependence_chart(be.dependence(sample, expl["lightgbm"], "vallalt_ido_nap"), "idő", False),
        charts.dependence_chart(be.dependence(sample, expl["lightgbm"], "kategoria"), "kategória", True),
    ]
    for ch in all_charts:
        for layer in _marks(ch.to_dict()):
            mark = layer["mark"] if isinstance(layer["mark"], dict) else {"type": layer["mark"]}
            enc = layer.get("encoding", {})
            assert "tooltip" in enc or mark.get("tooltip") is False, (mark.get("type"), sorted(enc))
    # a dobozábra saját rajzolás: nincs angol nyelvű „Q1 of …" súgó
    box = charts.dependence_chart(be.dependence(sample, expl["lightgbm"], "kategoria"), "kategória", True)
    assert "boxplot" not in str(box.to_dict())


def test_elojeles_tartomany():
    assert charts._signed_domain(pd.Series([1.0, 3.0])) == [0.0, pytest.approx(3.66)]
    lo, hi = charts._signed_domain(pd.Series([-2.0, 2.0]))
    assert lo < -2.0 and hi > 2.0


# --------------------------------------------------------------- a felület
@pytest.fixture
def app_env(synth_db, synth_cache, monkeypatch):
    monkeypatch.setenv("GLASSBOX_DB", str(synth_db))
    monkeypatch.setenv("GLASSBOX_CACHE", str(synth_cache))


def _ok(at):
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_a_felulet_minden_oldala_lefut(app_env, synth_bundle):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP), default_timeout=180).run()
    _ok(at)
    assert at.title[0].value == "Áttekintés"
    assert len(at.metric) == 4
    for dim in ("elado_allam", "kategoria", "vevo_allam"):
        at.segmented_control(key="dimenzio").set_value(dim).run()
        _ok(at)
    assert any("Hol vannak ezek az államok" in m.value for m in at.markdown)

    at.switch_page("oldalak/rendeles.py").run()
    _ok(at)
    first = be.risk_table(synth_bundle)["order_key"].iloc[0]
    assert at.query_params["rendeles"] == [first] or at.query_params["rendeles"] == first
    other = be.risk_table(synth_bundle)["order_key"].iloc[5]
    at.text_input(key="kulcs_be").input(other).run()
    _ok(at)
    assert any(other in m.value for m in at.markdown) or any(other in c.value for c in at.caption)
    at.button[0].click().run()                                   # véletlen rendelés
    _ok(at)
    assert any("Mi lenne, ha más határidőt" in m.value for m in at.markdown)
    at.toggle(key="hatarido_negy").set_value(True).run()         # a határidő-görbe mind a négy modellel
    _ok(at)
    at.text_input(key="kulcs_be").input("nincs-ilyen").run()
    _ok(at)
    assert any("Nincs ilyen rendelés" in w.value for w in at.warning)

    at.switch_page("oldalak/modell.py").run()
    _ok(at)
    assert any("Szintetikus" in i.value for i in at.info)
    at.selectbox(key="fuggoseg").select("kategoria").run()
    _ok(at)
    at.selectbox(key="fuggoseg").select(nv.MONTH).run()
    _ok(at)

    at.switch_page("oldalak/kerdezz.py").run()
    _ok(at)

    at.switch_page("oldalak/sugo.py").run()
    _ok(at)
    assert len(at.tabs) == 6
    assert any("Alagoas" in str(df.value.to_dict()) for df in at.dataframe)  # az államtábla


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_tarhaz_nelkul_erheto_hibauzenet(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("GLASSBOX_DB", str(tmp_path / "nincs.duckdb"))
    monkeypatch.setenv("GLASSBOX_CACHE", str(tmp_path / "c.joblib"))
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert any("tárház" in e.value.lower() for e in at.error)
    assert any("demo.py" in c.value for c in at.code)
