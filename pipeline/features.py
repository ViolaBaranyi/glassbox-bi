"""
M2 — Jellemzőszámítás.  A projekt legkockázatosabb modulja.

Két szabály uralja az egészet:

1. POINT-IN-TIME KORREKTSÉG
   Minden jellemző csak olyan információból származhat, ami a rendelés
   LEADÁSÁNAK pillanatában már ismert volt.

   Ez az előzmény-jellemzőknél két külön feltételt jelent:
     a) csak KORÁBBAN LEADOTT rendelések számíthatnak, és
     b) azoknak is csak a MÁR ISMERT kimenete.

   A b) pont a kényes. Egy tegnap leadott rendelésről ma még nem tudjuk,
   hogy késni fog-e — az csak a kézbesítéskor derül ki. Ezért az eladó
   korábbi késési arányát "as-of" illesztéssel számoljuk: az aktuális
   rendelés pillanatáig MÁR KÉZBESÍTETT rendelésekből. Ugyanígy a korábbi
   feladási időt csak a már futárnak átadott rendelésekből.

   (Az első változat csak az a) feltételt teljesítette — a rendelések
   ~53%-ánál volt olyan "előzmény", aminek kimenete még ismeretlen volt.
   Ezt az önellenőrzés során találtuk meg és javítottuk; a teszt most
   nyers erővel ellenőrzi a b) feltételt is.)

2. UGYANEZ A MODUL FUT TANÍTÁSKOR ÉS KISZOLGÁLÁSKOR
   Ha a két oldal külön kódot használna, a jellemzők csendben elcsúsznának
   (train/serving skew), és a magyarázatok nem a modellt írnák le.

A FEATURES lista a szerződés. Ami nincs benne, az nem kerül a modellbe.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# A megengedett jellemzők — fehérlista. Ez a modul szerződése.
# --------------------------------------------------------------------------
NUMERIC_FEATURES = [
    "tetel_szam",
    "elado_szam",
    "kategoria_szam",
    "kosar_ertek",
    "szallitasi_dij",
    "dij_arany",
    "tavolsag_km",
    "suly_g",
    "terfogat_cm3",
    "vallalt_ido_nap",
    "honap_sin",
    "honap_cos",
    "het_napja",
    "elado_korabbi_keses_arany",
    "elado_korabbi_rendelesek",
    "elado_atlagos_feladas_nap",
    "vevo_korabbi_rendelesek",
]

BOOLEAN_FEATURES = [
    "azonos_allam",
    "unnep_kozeli",
]

CATEGORICAL_FEATURES = [
    "kategoria",
    "elado_allam",
    "vevo_allam",
]

FEATURES = NUMERIC_FEATURES + BOOLEAN_FEATURES + CATEGORICAL_FEATURES
LABEL = "kesett"

# --------------------------------------------------------------------------
# A jellemzőtáblázat — a dolgozat és a README ebből készül, egy teszt pedig
# őrzi, hogy minden jellemzőhöz legyen leírás (a dokumentáció nem csúszhat el).
# (csoport, mit mér, honnan jön — mind a rendelés LEADÁSAKOR ismert)
# --------------------------------------------------------------------------
FEATURE_INFO = {
    "tetel_szam": ("kosár", "a rendelés tételeinek száma (darab)", "fact_order_items"),
    "elado_szam": ("kosár", "hány különböző eladótól jön a rendelés", "fact_order_items"),
    "kategoria_szam": ("kosár", "hány különböző termékkategória van a rendelésben",
                       "fact_order_items + dim_product"),
    "kosar_ertek": ("kosár", "a tételek árának összege (BRL)", "fact_order_items"),
    "szallitasi_dij": ("kosár", "a szállítási díjak összege (BRL)", "fact_order_items"),
    "dij_arany": ("kosár", "szállítási díj / kosárérték", "számított"),
    "tavolsag_km": ("földrajz", "eladó–vevő légvonalbeli távolság az irányítószám-előtagok "
                    "mediánpontja között (közelítés)", "geolokáció"),
    "suly_g": ("termék", "az összes tétel súlyának összege (g)", "fact_order_items + dim_product"),
    "terfogat_cm3": ("termék", "az összes tétel térfogatának összege (cm³)",
                     "fact_order_items + dim_product"),
    "vallalt_ido_nap": ("ígéret", "a platform (Olist) által vállalt szállítási idő (nap)",
                        "orders"),
    "honap_sin": ("naptár", "a rendelés hónapja körön kódolva (szinusz)", "orders"),
    "honap_cos": ("naptár", "a rendelés hónapja körön kódolva (koszinusz)", "orders"),
    "het_napja": ("naptár", "a hét napja (0 = hétfő)", "orders"),
    "elado_korabbi_keses_arany": ("előzmény", "a fő eladó korábbi, MÁR KÉZBESÍTETT rendeléseinek "
                                  "késési aránya (as-of)", "fact_orders"),
    "elado_korabbi_rendelesek": ("előzmény", "a fő eladó korábban leadott rendeléseinek száma",
                                 "fact_orders"),
    "elado_atlagos_feladas_nap": ("előzmény", "a fő eladó átlagos feladási ideje a MÁR futárnak "
                                  "átadott korábbi rendelésein (nap, as-of)", "fact_orders"),
    "vevo_korabbi_rendelesek": ("előzmény", "a vevő (customer_unique_id) korábbi rendeléseinek "
                                "száma", "fact_orders"),
    "azonos_allam": ("földrajz", "az eladó és a vevő ugyanabban az államban van-e", "számított"),
    "unnep_kozeli": ("naptár", "november 20. és december 31. közötti rendelés", "dim_date"),
    "kategoria": ("termék", "a fő tétel (legdrágább tétel) kategóriája", "dim_product"),
    "elado_allam": ("földrajz", "a fő eladó állama", "dim_seller"),
    "vevo_allam": ("földrajz", "a vevő állama", "dim_customer"),
}

# --------------------------------------------------------------------------
# Jellemzőcsoportok az ablációhoz (python -m pipeline.train --drop ...).
# Az abláció a FEATURES szerződést NEM módosítja: a build_features mindig a
# teljes listát adja vissza, a kizárás csak a betanítás előtt történik.
# --------------------------------------------------------------------------
FEATURE_GROUPS = {
    # a naptári hónap kódolása
    "honap": ["honap_sin", "honap_cos"],
    # minden, ami a naptárból jön és évszakhatást hordozhat
    # (az unnep_kozeli a november végét és a decembert jelöli)
    "naptar": ["honap_sin", "honap_cos", "unnep_kozeli"],
}

# --------------------------------------------------------------------------
# Tiltólista — amit soha nem láthat a modell.
# --------------------------------------------------------------------------
# Ezek a rendelés leadása UTÁN keletkeznek. Ha bármelyik bekerül a jellemzők
# közé, a modell a jövőből tanul, és a kiváló eredmény hazugság lesz.
FORBIDDEN_SUBSTRINGS = [
    "kezbesites",     # tényleges kézbesítés dátuma -> ebből készül a címke
    "review",         # az értékelés a kézbesítés után születik
    "ertekeles",
    "kesett",         # maga a címke
    "feladas_datuma", # a tényleges feladás dátuma EZEN a rendelésen
    "delivered",
    "carrier",
]

# Kivételek: olyan nevek, amelyek tartalmaznak tiltott szótöredéket, de
# kizárólag MÁR ISMERT, korábbi kimenetekből számolt aggregátumot jelentenek.
FORBIDDEN_EXCEPTIONS = {
    "elado_atlagos_feladas_nap",
    "elado_korabbi_keses_arany",
}


class LeakageError(AssertionError):
    """Tiltott, a jövőből származó oszlop került a jellemzők közé."""


def assert_no_leakage(columns) -> None:
    """A szivárgásteszt magja. Minden betanítás előtt lefut."""
    offenders = []
    for col in columns:
        if col in FORBIDDEN_EXCEPTIONS:
            continue
        low = str(col).lower()
        for bad in FORBIDDEN_SUBSTRINGS:
            if bad in low:
                offenders.append((col, bad))
                break
    if offenders:
        details = ", ".join(f"{c!r} (tiltott: {b!r})" for c, b in offenders)
        raise LeakageError(
            "ADATSZIVÁRGÁS: a jövőből származó oszlop a jellemzők között: "
            + details
        )

    extra = set(columns) - set(FEATURES)
    if extra:
        raise LeakageError(
            "A fehérlistán kívüli oszlop a jellemzők között: " + ", ".join(sorted(extra))
        )


# --------------------------------------------------------------------------
def load_frame(con) -> pd.DataFrame:
    """A tárházból beolvassa azt a nyers táblát, amiből a jellemzők készülnek."""
    df = con.execute("""
        SELECT
            f.order_key,
            f.rendeles_idopont,
            f.date_key,
            f.tetel_szam,
            f.elado_szam,
            f.kategoria_szam,
            f.kosar_ertek,
            f.szallitasi_dij,
            f.suly_g,
            f.terfogat_cm3,
            f.vallalt_hatarido,
            f.tavolsag_km,
            f.kesett,
            f.feladas_datuma,
            f.kezbesites_datuma,
            f.seller_key,
            f.customer_key,
            s.allam            AS elado_allam,
            c.allam            AS vevo_allam,
            c.customer_unique_key,
            p.kategoria,
            d.unnep_kozeli
        FROM fact_orders f
        LEFT JOIN dim_seller   s ON f.seller_key   = s.seller_key
        LEFT JOIN dim_customer c ON f.customer_key = c.customer_key
        LEFT JOIN dim_product  p ON f.product_key  = p.product_key
        LEFT JOIN dim_date     d ON f.date_key     = d.date_key
        ORDER BY f.rendeles_idopont, f.order_key
    """).df()
    # Egységes időfelbontás: a merge_asof azonos típust vár mindkét oldalon.
    for c in ["rendeles_idopont", "date_key", "vallalt_hatarido",
              "feladas_datuma", "kezbesites_datuma"]:
        df[c] = pd.to_datetime(df[c]).astype("datetime64[ns]")
    return df


def asof_history(df: pd.DataFrame, key: str, known_at: str, value: str):
    """
    Point-in-time előzmény "as-of" illesztéssel.

    Minden rendeléshez a `key` szerinti csoport azon rendeléseinek darabszámát
    és `value` átlagát adja vissza, amelyeknek az értéke a `known_at` időpontban
    vált ismertté — és ez SZIGORÚAN a mostani rendelés leadása előtt történt.

    Az aktuális rendelés soha nem szerepelhet a saját előzményében, mert a
    saját kimenete a saját leadása után válik ismertté.

    Visszaad: (darabszám, átlag) — mindkettő df.index szerint igazítva.
    """
    ev = df[[key, known_at, value]].dropna(subset=[known_at, value]).copy()
    ev = ev.sort_values(known_at, kind="mergesort")
    ev["_n"] = ev.groupby(key).cumcount() + 1
    ev["_sum"] = ev.groupby(key)[value].cumsum()
    ev = ev.rename(columns={known_at: "_t"})[[key, "_t", "_n", "_sum"]]

    left = df[[key, "rendeles_idopont"]].copy()
    left["_row"] = np.arange(len(df))
    left = left.sort_values("rendeles_idopont", kind="mergesort")

    m = pd.merge_asof(
        left, ev,
        left_on="rendeles_idopont", right_on="_t",
        by=key,
        direction="backward",
        allow_exact_matches=False,   # SZIGORÚAN korábban ismert
    ).sort_values("_row")

    n = m["_n"].fillna(0).astype(int).to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = (m["_sum"] / m["_n"]).to_numpy()
    return (pd.Series(n, index=df.index), pd.Series(mean, index=df.index))


def build_features(con) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """
    Visszaadja: (X, y, meta)
      X    – csak a FEATURES listában szereplő oszlopok
      y    – a címke (kesett)
      meta – order_key és rendeles_idopont, a szétvágáshoz és a nyomon követéshez
    """
    df = load_frame(con).reset_index(drop=True)

    # ---------------------------------------------------- egyszerű jellemzők
    # A pénzösszegek a tárházban DECIMAL típusúak; a modellnek lebegőpontos kell.
    for c in ["kosar_ertek", "szallitasi_dij"]:
        df[c] = df[c].astype(float)
    df["dij_arany"] = df["szallitasi_dij"] / df["kosar_ertek"].replace(0, np.nan)
    # A súly és a térfogat a rendelés ÖSSZES tételének összege (a tárház számolja).
    df["azonos_allam"] = (df["elado_allam"] == df["vevo_allam"])
    df["vallalt_ido_nap"] = (df["vallalt_hatarido"] - df["date_key"]).dt.days

    # ---------------------------------------------------- idő
    honap = df["rendeles_idopont"].dt.month
    df["honap_sin"] = np.sin(2 * np.pi * honap / 12)
    df["honap_cos"] = np.cos(2 * np.pi * honap / 12)
    df["het_napja"] = df["rendeles_idopont"].dt.dayofweek
    # Az évet SZÁNDÉKOSAN kihagyjuk: időbeli szétvágásnál a teszthalmaz éve
    # a tanítóban nem fordul elő, tehát a modell nem tudna vele mit kezdeni.

    # ------------------------------------- POINT-IN-TIME előzmény-jellemzők
    # (a) Hány rendelést adtak le korábban ennél az eladónál? — ez a leadáskor
    #     ismert (a platform látja a beérkező rendeléseket).
    df["elado_korabbi_rendelesek"] = df.groupby("seller_key").cumcount()
    df["vevo_korabbi_rendelesek"] = df.groupby("customer_unique_key").cumcount()

    # (b) A korábbi rendelések KIMENETE csak akkor ismert, amikor bekövetkezett.
    #     Késés: a kézbesítéskor derül ki -> known_at = kezbesites_datuma.
    #     (Konzervatív választás: a késés néha már a vállalt határidő elteltével
    #     sejthető, de a kézbesítés dátumával biztosan nem nézünk előre.)
    df["_kesett_num"] = df["kesett"].astype(float)
    _, df["elado_korabbi_keses_arany"] = asof_history(
        df, "seller_key", "kezbesites_datuma", "_kesett_num")

    #     Feladási idő: a futárnak átadáskor derül ki -> known_at = feladas_datuma.
    feladasi_ido = (
        (df["feladas_datuma"] - df["rendeles_idopont"]).dt.total_seconds() / 86400.0
    )
    df["_feladasi_ido_nap"] = feladasi_ido.where(feladasi_ido >= 0)  # hibás sorok -> NaN
    _, df["elado_atlagos_feladas_nap"] = asof_history(
        df, "seller_key", "feladas_datuma", "_feladasi_ido_nap")

    # ---------------------------------------------------- típusok
    for c in CATEGORICAL_FEATURES:
        df[c] = df[c].astype("category")
    for c in BOOLEAN_FEATURES:
        df[c] = df[c].fillna(False).astype(bool)

    X = df[FEATURES].copy()
    y = df[LABEL].astype(int)
    meta = df[["order_key", "rendeles_idopont"]].copy()

    # A szivárgásteszt itt, minden hívásnál lefut — nem csak a CI-ban.
    assert_no_leakage(X.columns)

    return X, y, meta


def suspicious_features(X: pd.DataFrame, y: pd.Series,
                        threshold: float = 0.95, min_rows: int = 200) -> list:
    """
    A szivárgásvédelem MÁSODIK szintje: az AUC-őr.

    A névszűrő (assert_no_leakage) csak azt fogja meg, aminek a neve árulkodó.
    Egy ártatlan nevű, de a jövőből származó oszlopon átsiklana. Ez az őr a
    viselkedést nézi: ha EGY jellemző önmagában 0,95 fölötti AUC-t ad, az
    tabuláris üzleti adaton szinte mindig szivárgás, nem felfedezés.

    Visszaad: [(oszlop, auc), ...] — üres lista, ha minden rendben.
    """
    from sklearn.metrics import roc_auc_score

    hits = []
    for c in X.columns:
        if isinstance(X[c].dtype, pd.CategoricalDtype):
            continue
        v = pd.to_numeric(X[c], errors="coerce").astype(float)
        m = v.notna()
        if m.sum() < min_rows or v[m].nunique() < 2 or y[m].nunique() < 2:
            continue
        auc = roc_auc_score(y[m], v[m])
        auc = max(auc, 1 - auc)
        if auc > threshold:
            hits.append((c, round(float(auc), 3)))
    return hits


def resolve_drop(names) -> list[str]:
    """
    Az ablációhoz kizárandó jellemzők feloldása.

    `names` elemei lehetnek csoportnevek (FEATURE_GROUPS kulcsai) vagy
    jellemzőnevek. Ismeretlen név -> ValueError: egy elgépelt név (pl.
    "honap_szin") különben csendben semmit nem zárna ki, és a „nélküle"
    futás valójában a teljes modell lenne.

    Visszaad: a kizárandó jellemzők listája, a FEATURES sorrendjében.
    """
    wanted: set[str] = set()
    unknown = []
    for raw in names or []:
        name = str(raw).strip()
        if not name:
            continue
        if name in FEATURE_GROUPS:
            wanted.update(FEATURE_GROUPS[name])
        elif name in FEATURES:
            wanted.add(name)
        else:
            unknown.append(name)
    if unknown:
        raise ValueError(
            "Ismeretlen jellemző vagy csoport az ablációban: " + ", ".join(unknown)
            + "\n  csoportok: " + ", ".join(FEATURE_GROUPS)
            + "\n  jellemzők: " + ", ".join(FEATURES))
    if wanted >= set(FEATURES):
        raise ValueError("Az abláció minden jellemzőt kizárna — ez nem modell.")
    return [f for f in FEATURES if f in wanted]


def schema(X: pd.DataFrame) -> dict:
    """A jellemzőséma, amit az online oldal indításkor összevet a sajátjával."""
    return {
        "features": list(X.columns),
        "dtypes": {c: str(X[c].dtype) for c in X.columns},
        "categorical": CATEGORICAL_FEATURES,
        "n_features": X.shape[1],
    }
