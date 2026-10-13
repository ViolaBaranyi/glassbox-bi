"""
A felület grafikonjai (Altair / Vega-Lite) — Streamlit nélkül is építhetők és tesztelhetők.

Közös szabályok: magyar tizedesvessző a tengelyeken, a hibasáv mindenhol 95%-os
intervallum, a kockázatot NÖVELŐ hatás piros, a CSÖKKENTŐ kék (színtévesztőknek
is megkülönböztethető pár; a felirat és az előjel is jelzi).

Világos és sötét téma: a Streamlit témája a tengelyeket színezi, a szöveg- és
vonaljeleket nem (azok alapból feketék, sötét háttéren láthatatlanok). Ezért a
feliratok és a hibasávok színét az `ink` paraméter adja (ink_for(téma)); a
hőtérképek cellafelirata a cella sötétségéhez igazodik, nem a témához.
"""

from __future__ import annotations

from dataclasses import dataclass

import altair as alt
import pandas as pd

from xai import labels
from xai import narrative as nv

UP, DOWN = "#c44e52", "#4c72b0"          # növeli / csökkenti
WINDOW_COLORS = {"tanító": "#4c72b0", "validációs": "#dd8452", "teszt": "#55a868"}


@dataclass(frozen=True)
class Ink:
    """A szöveg- és vonaljelek színei egy témához."""
    text: str        # sáv végi és vonal melletti feliratok
    rule: str        # hibasávok, nullvonal
    muted: str       # referencia-vonalak (átló, véletlen szint)


LIGHT = Ink(text="#31333f", rule="#31333f", muted="#808495")
DARK = Ink(text="#e8e8ec", rule="#c9cbd3", muted="#9a9db0")


def ink_for(theme_type: str | None) -> Ink:
    """A Streamlit témájához (st.context.theme.type: 'light' | 'dark' | None) illő színek."""
    return DARK if theme_type == "dark" else LIGHT


# A hőtérképek cellafelirata: a sötét cellán fehér, a világoson sötét — bármely témában.
# A küszöb a színskálán az a pont, ahol a fehér felirat kontrasztja már jobb a sötétnél
# (redblue: a fél-tartomány kb. 60%-a, oranges: a tartomány kb. 75%-a).
_ON_DARK, _ON_LIGHT = "#ffffff", "#1a1a1a"


def _cell_text_color(field: str, threshold: float, absolute: bool) -> alt.condition:
    value = f"abs(datum['{field}'])" if absolute else f"datum['{field}']"
    return alt.condition(f"{value} > {threshold:.6g}", alt.value(_ON_DARK), alt.value(_ON_LIGHT))

# A Vega-tengelyfelirat tizedespontját vesszőre cseréljük (egy tizedesjel van).
_COMMA = "replace(datum.label, '.', ',')"
# Ezres tagolás: „8,000" → „8 000" (a magyarban a vessző tizedesjel lenne).
_THOUSANDS = "replace(datum.label, regexp(',', 'g'), ' ')"


def _pct_axis(title: str, fmt: str = ".0%") -> alt.Axis:
    return alt.Axis(title=title, format=fmt, labelExpr=_COMMA)


def _dt(t: pd.Timestamp) -> alt.DateTime:
    return alt.DateTime(year=t.year, month=t.month, date=t.day)


# ------------------------------------------------------------- áttekintés
_Y_EXTENT = 64      # rögzített y-tengelyszélesség: a két egymás alatti grafikon így egy vonalba esik


def gap_runs(m: pd.DataFrame) -> pd.DataFrame:
    """
    A megbízható hónapok KÖZÖTTI hiányzó (0 rendeléses) vagy kevés rendeléses hónapok
    összefüggő szakaszai — ezeken a havi grafikon szürke „kevés adat" sávot mutat.
    (Az Olist-adatban 2016. okt. 22. és 2017. jan. 5. között egyetlen rendelés van:
    dec. 23-án; novemberben egy sem.)
    """
    cols = ["kezdet", "veg", "kozep", "honapok", "rendelesek_szoveg"]
    ok = pd.to_datetime(m.loc[m["megbizhato"], "honap"])
    if ok.empty:
        return pd.DataFrame(columns=cols)
    counts = {pd.Timestamp(t): int(n) for t, n in zip(m["honap"], m["rendelesek"])}
    reliable = set(ok)
    runs, cur = [], []
    for t in pd.date_range(ok.min(), ok.max(), freq="MS"):
        if t in reliable:
            if cur:
                runs.append(cur)
            cur = []
        else:
            cur.append(t)
    rows = []
    for run in runs:
        start, end = run[0] - pd.Timedelta(days=15), run[-1] + pd.Timedelta(days=15)
        names = [f"{t.year}. {nv.MONTHS[t.month - 1]}" for t in run]
        rows.append({"kezdet": start, "veg": end, "kozep": start + (end - start) / 2,
                     "honapok": names[0] if len(names) == 1 else f"{names[0]} – {names[-1]}",
                     "rendelesek_szoveg": " · ".join(f"{nv.MONTHS[t.month - 1]}: "
                                                     f"{nv.fmt_num(counts.get(t, 0), 0)}" for t in run)})
    return pd.DataFrame(rows, columns=cols)


def monthly_chart(m: pd.DataFrame, win: pd.DataFrame,
                  ink: Ink = LIGHT) -> tuple[alt.LayerChart, alt.Chart]:
    """
    Két egymás alá teendő grafikon közös időtengellyel:
      1. havi késési arány 95%-os sávval, háttérben a tanító / validációs / teszt ablak,
         a hiányzó vagy kevés rendeléses hónapokon szürke „kevés adat" sávval;
      2. a havi rendelésszám.
    (Egy vconcat-ábra nem követi a konténer szélességét, ezért két külön ábra.)
    Minden rétegnek magyar súgója van: a Streamlit témája különben a nyers mezőneveket
    mutatná (kezdet, veg, ablak …) angol dátumokkal.
    """
    d = m[m["megbizhato"]].copy()
    # Hiányzó (vagy kihagyott) hónapnál a vonal megszakad: nem húzunk vonalat ott, ahol
    # nincs adat (2016 novemberében egy rendelés sincs, decemberben egy).
    month_no = d["honap"].dt.year * 12 + d["honap"].dt.month
    d["szakasz"] = (month_no.diff().fillna(1) > 1).cumsum().astype(int)
    d["arany_szoveg"] = [nv.fmt_pct(v) for v in d["kesesi_arany"]]
    d["ci_szoveg"] = [f"{nv.fmt_pct(a)} – {nv.fmt_pct(b)}" for a, b in zip(d["ci_also"], d["ci_felso"])]
    d["db_szoveg"] = [nv.fmt_num(v, 0) for v in d["rendelesek"]]
    lo = d["honap"].min() - pd.Timedelta(days=15)
    hi = d["honap"].max() + pd.Timedelta(days=31)
    xs = alt.Scale(domain=[_dt(lo), _dt(hi)])
    x = alt.X("honap:T", title=None, scale=xs, axis=alt.Axis(format="%Y. %m.", labelAngle=0))

    w = win.copy()
    w["felirat"] = [labels.WINDOW_LABELS.get(a, a) for a in w["ablak"]]
    # a vég kizáró határ (a következő időszak első napja 0:00) → a kiírt utolsó nap egy nappal korábbi
    w["idoszak_szoveg"] = [f"{nv.fmt_date(a)} – {nv.fmt_date(pd.Timestamp(b) - pd.Timedelta(seconds=1))}"
                           for a, b in zip(w["kezdet"], w["veg"])]
    w["db_szoveg"] = [nv.fmt_num(v, 0) for v in w["rendelesek"]]
    w["mire"] = [labels.WINDOW_PLAIN.get(a, "") for a in w["ablak"]]
    w["kezdet"] = w["kezdet"].clip(lower=lo, upper=hi)
    w["veg"] = w["veg"].clip(lower=lo, upper=hi)
    w["kozep"] = w["kezdet"] + (w["veg"] - w["kezdet"]) / 2
    window_tip = [alt.Tooltip("felirat:N", title="időszak"),
                  alt.Tooltip("idoszak_szoveg:N", title="mettől meddig"),
                  alt.Tooltip("db_szoveg:N", title="kézbesített rendelések"),
                  alt.Tooltip("mire:N", title="mire szolgált")]
    wc = alt.Chart(w)
    colors = alt.Scale(domain=list(WINDOW_COLORS), range=list(WINDOW_COLORS.values()))
    bands = wc.mark_rect(opacity=0.12).encode(
        x="kezdet:T", x2="veg:T", color=alt.Color("ablak:N", scale=colors, legend=None),
        tooltip=window_tip)
    band_text = wc.mark_text(baseline="top", dy=4, fontSize=11).encode(
        x="kozep:T", y=alt.value(0), text="felirat:N",
        color=alt.Color("ablak:N", scale=colors, legend=None), tooltip=window_tip)

    gaps = gap_runs(m)
    gap_layers = []
    if len(gaps):
        gaps["felirat"] = "kevés\nadat"
        gaps["miert"] = ("ezekben a hónapokban (szinte) nincs rendelés az adatban, ezért itt nem "
                         "számolunk késési arányt — a vonal ezért szakad meg")
        gap_tip = [alt.Tooltip("honapok:N", title="hónap"),
                   alt.Tooltip("rendelesek_szoveg:N", title="rendelések"),
                   alt.Tooltip("miert:N", title="miért nincs pont")]
        gc = alt.Chart(gaps)
        # középszürke, áttetsző: világos témán halványszürke, sötéten sötétszürke sáv lesz
        gap_layers = [gc.mark_rect(color="#888888", opacity=0.28).encode(
                          x="kezdet:T", x2="veg:T", tooltip=gap_tip),
                      gc.mark_text(fontSize=10, lineBreak="\n", color=ink.muted).encode(
                          x="kozep:T", y=alt.value(150), text="felirat:N", tooltip=gap_tip)]

    d["honap_szoveg"] = [f"{t.year}. {nv.MONTHS[t.month - 1]}" for t in d["honap"]]
    tip = [alt.Tooltip("honap_szoveg:N", title="hónap"),
           alt.Tooltip("db_szoveg:N", title="rendelések"),
           alt.Tooltip("kesett:Q", title="ebből késett"),
           alt.Tooltip("arany_szoveg:N", title="késési arány"),
           alt.Tooltip("ci_szoveg:N", title="valószínű tartomány (95%)")]
    base = alt.Chart(d)
    ci = base.mark_area(opacity=0.25, color=UP).encode(
        x=x, y="ci_also:Q", y2="ci_felso:Q", detail="szakasz:N", tooltip=tip)
    line = base.mark_line(point=True, color=UP).encode(
        x=x, tooltip=tip, detail="szakasz:N",
        y=alt.Y("kesesi_arany:Q", axis=alt.Axis(title="késési arány", format=".0%", labelExpr=_COMMA,
                                                 minExtent=_Y_EXTENT, maxExtent=_Y_EXTENT)))
    top = alt.layer(bands, band_text, *gap_layers, ci, line).properties(height=300)
    volume = base.mark_bar(color="#8c8c8c").encode(
        x=x, tooltip=tip,
        y=alt.Y("rendelesek:Q", axis=alt.Axis(title="rendelések", tickCount=3, format=",d",
                                               labelExpr=_THOUSANDS,
                                               minExtent=_Y_EXTENT, maxExtent=_Y_EXTENT))
    ).properties(height=140)
    return top, volume


def dimension_chart(df: pd.DataFrame, overall: float, label: str,
                    ink: Ink = LIGHT) -> alt.LayerChart:
    """Vízszintes oszlopok: késési arány dimenzióértékenként, Wilson-hibasávval, átlagvonallal."""
    d = df.copy()
    if "megnevezes" not in d:
        d["megnevezes"] = d["ertek"].astype(str)
    d["arany_szoveg"] = [nv.fmt_pct(v) for v in d["kesesi_arany"]]
    d["ci_szoveg"] = [f"{nv.fmt_pct(a)} – {nv.fmt_pct(b)}" for a, b in zip(d["ci_also"], d["ci_felso"])]
    d["db_szoveg"] = [nv.fmt_num(v, 0) for v in d["rendelesek"]]
    order = list(d["megnevezes"])
    y = alt.Y("megnevezes:N", sort=order, title=None, axis=alt.Axis(labelLimit=300))
    tip = [alt.Tooltip("megnevezes:N", title=label)]
    if "regio" in d:
        tip.append(alt.Tooltip("regio:N", title="régió"))
    tip += [alt.Tooltip("db_szoveg:N", title="rendelések"),
            alt.Tooltip("kesett:Q", title="ebből késett"),
            alt.Tooltip("arany_szoveg:N", title="késési arány"),
            alt.Tooltip("ci_szoveg:N", title="valószínű tartomány (95%)")]
    base = alt.Chart(d)
    bars = base.mark_bar(color=UP, opacity=0.75).encode(
        y=y, x=alt.X("kesesi_arany:Q", axis=_pct_axis("késési arány")), tooltip=tip)
    err = base.mark_rule(color=ink.rule).encode(y=y, x="ci_also:Q", x2="ci_felso:Q", tooltip=tip)
    avg = alt.Chart(pd.DataFrame({"x": [overall], "felirat": [f"összesen {nv.fmt_pct(overall)}"],
                                  "magyarazat": [f"az összes rendelés késési aránya: {nv.fmt_pct(overall)}"]}))
    avg_tip = [alt.Tooltip("magyarazat:N", title="szaggatott vonal")]
    rule = avg.mark_rule(strokeDash=[4, 4], color=ink.rule).encode(x="x:Q", tooltip=avg_tip)
    text = avg.mark_text(align="left", dx=4, dy=-6, color=ink.text).encode(
        x="x:Q", y=alt.value(0), text="felirat:N", tooltip=avg_tip)
    return alt.layer(bars, err, rule, text).properties(height=alt.Step(22))


# Régiók színei a négyzetrácsos térképen (világos árnyalatok: a sötét felirat mindkét
# témában olvasható rajtuk).
REGION_COLORS = {"Észak": "#a6d4a0", "Északkelet": "#f6b98a", "Közép-Nyugat": "#ecd98b",
                 "Délkelet": "#9cc7e4", "Dél": "#cdb4dc"}
NO_DATA = "#c8c8c8"


def state_tile_map(df: pd.DataFrame | None = None, overall: float | None = None,
                   count_title: str = "rendelések", cell: int = 46) -> alt.LayerChart:
    """
    Brazília 27 állama egyszerűsített „négyzetrácsos térképen" (labels.TILE_GRID): minden
    állam egy egyforma négyzet, a helye nagyjából a valódi elhelyezkedés.

    df (a by_dimension kimenete, ertek = államkód) és overall (az összes rendelés késési
    aránya) megadásával a négyzet színe a késési arány: piros, ha az átlagnál több, kék, ha
    kevesebb (a középpont az átlag); a küszöb alatti államok szürkék. df nélkül a négyzetek
    a régió szerint színeződnek (tájékozódáshoz, a Súgóban).
    """
    rows = []
    for code, (col, row) in labels.TILE_GRID.items():
        rows.append({"kod": code, "nev": labels.state_name(code),
                     "regio": labels.state_region(code), "oszlop": col, "sor": row})
    d = pd.DataFrame(rows)
    by_value = df is not None
    if by_value:
        stats = df.set_index("ertek")[["rendelesek", "kesett", "kesesi_arany"]].astype(float)
        d = d.join(stats, on="kod")                     # a küszöb alatti államoknál NaN
        d["adat"] = d["kesesi_arany"].notna()
        d["arany_szoveg"] = [nv.fmt_pct(v) if ok else "" for v, ok in zip(d["kesesi_arany"], d["adat"])]
        d["db_szoveg"] = [nv.fmt_num(v, 0) if ok else "kevés (a küszöb alatt)"
                          for v, ok in zip(d["rendelesek"], d["adat"])]
    x = alt.X("oszlop:O", axis=None, scale=alt.Scale(domain=list(range(6)), paddingInner=0.08))
    y = alt.Y("sor:O", axis=None, scale=alt.Scale(domain=list(range(8)), paddingInner=0.08))
    base = alt.Chart(d).encode(x=x, y=y)
    tip = [alt.Tooltip("nev:N", title="állam"), alt.Tooltip("kod:N", title="rövidítés"),
           alt.Tooltip("regio:N", title="régió")]
    if by_value:
        mid = float(overall) if overall is not None else float(d["kesesi_arany"].mean())
        dev = float((d["kesesi_arany"] - mid).abs().max()) if d["adat"].any() else 0.0
        dev = dev or 0.01
        tip += [alt.Tooltip("db_szoveg:N", title=count_title),
                alt.Tooltip("arany_szoveg:N", title="késési arány")]
        # Két réteg: alul minden állam szürkén (a küszöb alattiak így is látszanak), felül a
        # színezett négyzetek. (Egy feltételes szín nem elég: a Vega-Lite a hiányzó értékű
        # sorokat a folytonos színskálánál kiszűri, a négyzet el is tűnne.)
        valid = "isValid(datum.kesesi_arany)"
        rects = [base.mark_rect(cornerRadius=4, color=NO_DATA).encode(tooltip=tip),
                 base.transform_filter(valid).mark_rect(cornerRadius=4).encode(
                     color=alt.Color("kesesi_arany:Q", title="késési arány",
                                     scale=alt.Scale(scheme="redblue", reverse=True, domainMid=mid,
                                                     domain=[max(0.0, mid - dev), mid + dev]),
                                     legend=alt.Legend(orient="bottom", format=".0%",
                                                       labelExpr=_COMMA,
                                                       gradientLength=min(6 * cell, 240))),
                     tooltip=tip)]
        text_color = alt.condition(f"{valid} && abs(datum.kesesi_arany - {mid:.6g}) > {0.6 * dev:.6g}",
                                   alt.value(_ON_DARK), alt.value(_ON_LIGHT))
    else:
        rects = [base.mark_rect(cornerRadius=4).encode(
            color=alt.Color("regio:N", title="régió",
                            scale=alt.Scale(domain=list(REGION_COLORS),
                                            range=list(REGION_COLORS.values())),
                            legend=alt.Legend(orient="bottom", columns=3)),
            tooltip=tip)]
        text_color = alt.value(_ON_LIGHT)
    code = base.mark_text(fontSize=13, fontWeight="bold", dy=-6 if by_value else 0).encode(
        text="kod:N", color=text_color, tooltip=tip)
    layers = [*rects, code]
    if by_value:
        layers.append(base.mark_text(fontSize=10, dy=9).encode(
            text="arany_szoveg:N", color=text_color, tooltip=tip))
    return alt.layer(*layers).properties(width=6 * cell, height=8 * cell)


# ------------------------------------------------------- rendelés-magyarázat
def reasons_chart(frame: pd.DataFrame, ink: Ink = LIGHT) -> alt.LayerChart:
    """Egy rendelés tényezői: előjeles hatás százalékpontban (a frame sorrendjében)."""
    d = frame.copy()
    d["cimke"] = [f"{n}: {v}" for n, v in zip(d["nev"], d["ertek"])]
    d["irany"] = ["növeli" if v >= 0 else "csökkenti" for v in d["hatas_pp"]]
    d["hatas_szoveg"] = [nv.fmt_pp(v, 2) + " pp" for v in d["hatas_pp"]]
    y = alt.Y("cimke:N", sort=list(d["cimke"]), title=None, axis=alt.Axis(labelLimit=320))
    color = alt.Color("irany:N", title="a kockázatot",
                      scale=alt.Scale(domain=["növeli", "csökkenti"], range=[UP, DOWN]),
                      legend=alt.Legend(orient="top"))
    base = alt.Chart(d)
    reason_tip = [alt.Tooltip("nev:N", title="tényező"), alt.Tooltip("ertek:N", title="érték"),
                  alt.Tooltip("hatas_szoveg:N", title="hatás"),
                  alt.Tooltip("irany:N", title="a kockázatot")]
    bars = base.mark_bar().encode(
        y=y, x=alt.X("hatas_pp:Q", title="hatás a becslésre (százalékpont)",
                     axis=alt.Axis(labelExpr=_COMMA)),
        color=color, tooltip=reason_tip)
    # a felirat a sáv végére: pozitívnál jobbra, negatívnál balra igazítva
    pos = base.transform_filter("datum.hatas_pp >= 0").mark_text(align="left", dx=4, color=ink.text)
    neg = base.transform_filter("datum.hatas_pp < 0").mark_text(align="right", dx=-4, color=ink.text)
    labels = [t.encode(y=y, x="hatas_pp:Q", text="hatas_szoveg:N", tooltip=reason_tip) for t in (pos, neg)]
    zero = alt.Chart(pd.DataFrame({"x": [0.0]})).mark_rule(color=ink.rule, tooltip=False).encode(x="x:Q")
    bars = bars.encode(x=alt.X("hatas_pp:Q", title="hatás a becslésre (százalékpont)",
                               scale=alt.Scale(domain=_signed_domain(d["hatas_pp"])),
                               axis=alt.Axis(labelExpr=_COMMA, tickCount=8)))
    return alt.layer(bars, zero, *labels).properties(height=alt.Step(28), padding={"left": 12})


def _signed_domain(v: pd.Series, room: float = 0.22) -> list[float]:
    """A 0-t tartalmazó tartomány, mindkét irányban helyet hagyva a sáv végi feliratnak."""
    lo, hi = min(0.0, float(v.min())), max(0.0, float(v.max()))
    span = (hi - lo) or 1.0
    return [lo - room * span if lo < 0 else lo, hi + room * span if hi > 0 else hi]


def comparison_heatmap(long: pd.DataFrame, model_order: list[str]) -> alt.LayerChart:
    """Tényező × modell hőtérkép: ugyanannak a rendelésnek a magyarázata négy modellel."""
    d = long.copy()
    d["hatas_szoveg"] = [nv.fmt_pp(v, 1) for v in d["hatas_pp"]]
    lim = max(0.5, float(d["hatas_pp"].abs().max()))
    order = list(dict.fromkeys(d["nev"]))
    base = alt.Chart(d).encode(
        x=alt.X("modell:N", sort=model_order, title=None, axis=alt.Axis(labelAngle=0, labelLimit=220)),
        y=alt.Y("nev:N", sort=order, title=None, axis=alt.Axis(labelLimit=260)))
    cell_tip = [alt.Tooltip("modell:N", title="módszer"), alt.Tooltip("nev:N", title="tényező"),
                alt.Tooltip("hatas_szoveg:N", title="hatás (százalékpont)")]
    rect = base.mark_rect().encode(
        color=alt.Color("hatas_pp:Q", title="százalékpont",
                        scale=alt.Scale(scheme="redblue", reverse=True, domain=[-lim, lim]),
                        legend=alt.Legend(labelExpr=_COMMA)),
        tooltip=cell_tip)
    text = base.mark_text(fontSize=12).encode(
        text="hatas_szoveg:N", color=_cell_text_color("hatas_pp", 0.6 * lim, absolute=True),
        tooltip=cell_tip)
    return alt.layer(rect, text).properties(height=alt.Step(30))


# ----------------------------------------------------------------- modell
def pr_auc_forest(res: pd.DataFrame, base_rate: float, ink: Ink = LIGHT) -> alt.LayerChart:
    """PR-AUC pont + 95% CI modellenként; a szaggatott vonal a véletlen rangsor szintje."""
    d = res.copy()
    d["szoveg"] = [f"{nv.fmt_num(v, 3)} [{nv.fmt_num(a, 3)}; {nv.fmt_num(b, 3)}]"
                   for v, a, b in zip(d["pr_auc"], d["pr_auc_also"], d["pr_auc_felso"])]
    y = alt.Y("modell:N", sort=list(d["modell"]), title=None, axis=alt.Axis(labelLimit=260))
    d["ci_szoveg"] = [f"{nv.fmt_num(a, 3)} – {nv.fmt_num(b, 3)}"
                      for a, b in zip(d["pr_auc_also"], d["pr_auc_felso"])]
    d["pont_szoveg"] = [nv.fmt_num(v, 3) for v in d["pr_auc"]]
    forest_tip = [alt.Tooltip("modell:N", title="módszer"),
                  alt.Tooltip("pont_szoveg:N", title="rangsorolási pontszám (PR-AUC)"),
                  alt.Tooltip("ci_szoveg:N", title="valószínű tartomány (95%)")]
    base = alt.Chart(d)
    err = base.mark_rule(strokeWidth=2, color=ink.rule).encode(y=y, x="pr_auc_also:Q", x2="pr_auc_felso:Q",
                                                               tooltip=forest_tip)
    pts = base.mark_point(filled=True, size=90, color=UP).encode(
        y=y, x=alt.X("pr_auc:Q", title="rangsorolási pontszám (PR-AUC) — a nagyobb a jobb",
                     scale=alt.Scale(zero=True), axis=alt.Axis(labelExpr=_COMMA)),
        tooltip=forest_tip)
    ref = alt.Chart(pd.DataFrame({"x": [base_rate],
                                  "felirat": [f"vaktában rangsorolva ({nv.fmt_pct(base_rate)})"],
                                  "magyarazat": ["ennyit érne el egy találomra sorba rendező módszer "
                                                 f"(a késések aránya, {nv.fmt_pct(base_rate)})"]}))
    ref_tip = [alt.Tooltip("magyarazat:N", title="szaggatott vonal")]
    rule = ref.mark_rule(strokeDash=[4, 4], color=ink.muted).encode(x="x:Q", tooltip=ref_tip)
    text = ref.mark_text(align="left", dx=4, dy=-6, color=ink.muted).encode(
        x="x:Q", y=alt.value(0), text="felirat:N", tooltip=ref_tip)
    return alt.layer(err, pts, rule, text).properties(height=alt.Step(44))


def reliability_chart(cal: pd.DataFrame, ink: Ink = LIGHT) -> alt.LayerChart:
    """Megbízhatósági ábra: átlagos becslés vs tényleges arány tizedenként, Wilson-hibasávval."""
    d = cal.copy()
    d["becsles_szoveg"] = [nv.fmt_pct(v) for v in d["atlag_becsles"]]
    d["arany_szoveg"] = [nv.fmt_pct(v) for v in d["tenyleges_arany"]]
    hi = float(max(d["atlag_becsles"].max(), d["ci_felso"].max())) * 1.08
    sc = alt.Scale(domain=[0, hi])
    d["db_szoveg"] = [nv.fmt_num(v, 0) for v in d["rendelesek"]]
    d["ci_szoveg"] = [f"{nv.fmt_pct(a)} – {nv.fmt_pct(b)}" for a, b in zip(d["ci_also"], d["ci_felso"])]
    rel_tip = [alt.Tooltip("sav:N", title="becslési sáv"), alt.Tooltip("db_szoveg:N", title="rendelések"),
               alt.Tooltip("becsles_szoveg:N", title="a modell átlagosan ennyit mondott"),
               alt.Tooltip("arany_szoveg:N", title="ténylegesen ennyi késett"),
               alt.Tooltip("ci_szoveg:N", title="valószínű tartomány (95%)")]
    base = alt.Chart(d)
    diag = alt.Chart(pd.DataFrame({"a": [0.0, hi], "b": [0.0, hi],
                                   "magyarazat": ["itt lennének a pontok, ha a becslés pontosan egyezne "
                                                  "a valósággal"] * 2})).mark_line(
        strokeDash=[4, 4], color=ink.muted).encode(x=alt.X("a:Q", scale=sc), y=alt.Y("b:Q", scale=sc),
                                                   tooltip=[alt.Tooltip("magyarazat:N", title="átló")])
    err = base.mark_rule(color=ink.rule).encode(
        x=alt.X("atlag_becsles:Q", scale=sc), y=alt.Y("ci_also:Q", scale=sc), y2="ci_felso:Q",
        tooltip=rel_tip)
    pts = base.mark_point(filled=True, size=70, color=UP).encode(
        x=alt.X("atlag_becsles:Q", scale=sc, axis=_pct_axis("a modell átlagos becslése a sávban", ".1%")),
        y=alt.Y("tenyleges_arany:Q", scale=sc, axis=_pct_axis("tényleges késési arány", ".1%")),
        tooltip=rel_tip)
    return alt.layer(diag, err, pts).properties(height=340)


def importance_heatmap(gi: pd.DataFrame, model_order: list[str], top: int = 12) -> alt.LayerChart:
    """Átlagos |hatás| (pp) tényezőnként és modellenként; a sorrend az első modell rangsora."""
    first = gi[gi["modell"] == model_order[0]].sort_values("rang")
    keep = list(first["nev"].head(top))
    d = gi[gi["nev"].isin(keep)].copy()
    d["szoveg"] = [nv.fmt_num(v, 2) for v in d["atlag_abs_pp"]]
    d["minta_szoveg"] = [f"{nv.fmt_num(v, 0)} rendelés" for v in d["minta"]]
    d["rang_szoveg"] = [f"{int(v)}." for v in d["rang"]]
    imp_tip = [alt.Tooltip("modell:N", title="módszer"), alt.Tooltip("nev:N", title="tényező"),
               alt.Tooltip("szoveg:N", title="átlagos hatás (százalékpont, előjel nélkül)"),
               alt.Tooltip("rang_szoveg:N", title="fontossági sorrend"),
               alt.Tooltip("minta_szoveg:N", title="ennyi rendelésen mérve")]
    base = alt.Chart(d).encode(
        x=alt.X("modell:N", sort=model_order, title=None, axis=alt.Axis(labelAngle=0, labelLimit=220)),
        y=alt.Y("nev:N", sort=keep, title=None, axis=alt.Axis(labelLimit=260)))
    rect = base.mark_rect().encode(
        color=alt.Color("atlag_abs_pp:Q", title="átlagos hatás (százalékpont)",
                        scale=alt.Scale(scheme="oranges"), legend=alt.Legend(labelExpr=_COMMA)),
        tooltip=imp_tip)
    lo, hi = float(d["atlag_abs_pp"].min()), float(d["atlag_abs_pp"].max())
    text = base.mark_text(fontSize=12).encode(
        text="szoveg:N", color=_cell_text_color("atlag_abs_pp", lo + 0.75 * (hi - lo), absolute=False),
        tooltip=imp_tip)
    return alt.layer(rect, text).properties(height=alt.Step(28))


def _box_stats(d: pd.DataFrame) -> pd.DataFrame:
    """Kategóriánként: n, alsó/felső kvartilis, medián, és a „bajusz" (Tukey: a kvartilisektől
    legfeljebb 1,5 × IQR-re lévő legszélső érték)."""
    rows = []
    for value, g in d.groupby("ertek", sort=False):
        v = g["hatas_pp"].to_numpy(dtype=float)
        q1, med, q3 = (float(x) for x in pd.Series(v).quantile([0.25, 0.5, 0.75]))
        iqr = q3 - q1
        inside = v[(v >= q1 - 1.5 * iqr) & (v <= q3 + 1.5 * iqr)]
        rows.append({"ertek": value, "n": len(v), "q1": q1, "median": med, "q3": q3,
                     "also": float(inside.min()), "felso": float(inside.max())})
    return pd.DataFrame(rows)


def dependence_chart(dep: pd.DataFrame, name: str, categorical: bool, top_n: int = 15,
                     order: list[str] | None = None, ink: Ink = LIGHT,
                     percent: bool = False) -> alt.LayerChart:
    """Függőségi ábra: a tényező értéke és a hatása (pp) a mintán.

    Kategóriánál dobozábra a `top_n` leggyakoribb értékre (a doboz a középső fél, a vonás a
    medián, a vékony vonal a szokásos tartomány); a sorrend a megadott (pl. naptári) vagy a
    medián hatás szerint csökkenő. Saját rajzolás a Vega-Lite boxplot helyett, hogy a súgó
    magyar legyen. `percent`: az érték arány (0–1), a tengely százalékban.
    """
    d = dep.dropna(subset=["ertek"]).copy()
    y_title = "hatás a becslésre (százalékpont)"
    zero = alt.Chart(pd.DataFrame({"y": [0.0]})).mark_rule(color=ink.muted, tooltip=False).encode(y="y:Q")
    if categorical:
        d["ertek"] = d["ertek"].astype(str)
        keep = d["ertek"].value_counts().head(top_n).index
        d = d[d["ertek"].isin(keep)]
        st = _box_stats(d)
        if order is None:
            order = list(st.sort_values("median", ascending=False)["ertek"])
        else:
            order = [o for o in order if o in set(st["ertek"])]
        st["db_szoveg"] = [f"{nv.fmt_num(v, 0)} rendelés" for v in st["n"]]
        st["median_szoveg"] = [f"{nv.fmt_pp(v, 2)} pp" for v in st["median"]]
        st["kozep_szoveg"] = [f"{nv.fmt_pp(a, 2)} … {nv.fmt_pp(b, 2)} pp" for a, b in zip(st["q1"], st["q3"])]
        st["tartomany_szoveg"] = [f"{nv.fmt_pp(a, 2)} … {nv.fmt_pp(b, 2)} pp"
                                  for a, b in zip(st["also"], st["felso"])]
        box_tip = [alt.Tooltip("ertek:N", title=name), alt.Tooltip("db_szoveg:N", title="a mintában"),
                   alt.Tooltip("median_szoveg:N", title="jellemző (középső) hatás"),
                   alt.Tooltip("kozep_szoveg:N", title="a rendelések fele ebben a sávban"),
                   alt.Tooltip("tartomany_szoveg:N", title="a szokásos tartomány")]
        x = alt.X("ertek:N", sort=order, title=name, axis=alt.Axis(labelAngle=-40))
        y = alt.Y("also:Q", title=y_title, axis=alt.Axis(labelExpr=_COMMA))
        base = alt.Chart(st)
        whisker = base.mark_rule(color=UP).encode(x=x, y=y, y2="felso:Q", tooltip=box_tip)
        box = base.mark_bar(size=18, color=UP, opacity=0.35, stroke=UP).encode(
            x=x, y=alt.Y("q1:Q", title=y_title), y2="q3:Q", tooltip=box_tip)
        median = base.mark_tick(color=UP, thickness=3, size=20).encode(
            x=x, y=alt.Y("median:Q", title=y_title), tooltip=box_tip)
        return alt.layer(zero, whisker, box, median).properties(height=320)
    y = alt.Y("hatas_pp:Q", title=y_title, axis=alt.Axis(labelExpr=_COMMA))
    if "ertek_szoveg" not in d:
        d["ertek_szoveg"] = [nv.fmt_pct(v) if percent else nv.fmt_num(v, 0 if float(v).is_integer() else 1)
                             for v in d["ertek"]]
    d["hatas_szoveg"] = [nv.fmt_pp(v, 2) for v in d["hatas_pp"]]
    base = alt.Chart(d)
    axis = alt.Axis(labelExpr=_COMMA, format=".0%") if percent else alt.Axis(labelExpr=_COMMA)
    pts = base.mark_circle(size=18, opacity=0.35, color=UP).encode(
        x=alt.X("ertek:Q", title=name, axis=axis), y=y,
        tooltip=[alt.Tooltip("ertek_szoveg:N", title=name),
                 alt.Tooltip("hatas_szoveg:N", title="hatás (százalékpont)")])
    return alt.layer(zero, pts).properties(height=320)
