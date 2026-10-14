"""
A LEZÁRT v3 alapfutás — a teszthalmaz egyetlen, előre rögzített mérése.

A teszthalmazt eddig sokszor láttuk (döntési napló). Innentől a szabály:
minden módszertani döntés a futás ELŐTT, írásban rögzül a protokollban
(docs/v3_protokoll.json), és a futás után nem változik. Ez a modul:

  1. ellenőrzi, hogy a protokoll jóvá van-e hagyva, minden döntés ki van-e
     töltve, és pontosan azt írja-e le, amit a kód csinál (fa-szám szabály,
     magok, hajtások, ablakok, adatforrás) — ha nem, a modellhez sem nyúl;
  2. kiszámolja a protokollfájl ujjlenyomatát (SHA256, egységesített sorvégekkel,
     hogy Windowson és Linuxon ugyanaz legyen); az eredmény ezzel együtt
     mentődik, így utólag ellenőrizhető, melyik protokoll szerint futott;
     és csak akkor indul, ha a protokoll és a kód COMMITOLVA van (a git
     időbélyege bizonyítja, hogy a döntés megelőzte az eredményt);
  3. lefuttatja: bővülő ablakos CV → N_fix → végső modell → validáció és teszt
     → heti blokk-bootstrap intervallumok → páros összevetés a konstans
     előrejelzéssel → tanítási véletlen több maggal (külön jelentve);
  4. az eredményt a docs/ mappába írja (JSON + rövid összefoglaló) — ez a
     repóba kerül, a commit időbélyegzi;
  5. ha már van eredmény, megáll. Ismételt futás csak --ismetles kapcsolóval
     megy, és az eredményben ez látszik.

Futtatás (csak jóváhagyott és commitolt protokollal):
    python -m pipeline.v3_baseline
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from data.db import DB_PATH, WarehouseUnavailable, connect, use_utf8_console
from pipeline import model_selection as ms
from pipeline import train
from pipeline.bootstrap import (METRICS, block_bootstrap, paired_block_bootstrap,
                                week_blocks)
from pipeline.features import LeakageError
from pipeline.split import PLANNED

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL = ROOT / "docs" / "v3_protokoll.json"
RESULT_JSON = ROOT / "docs" / "v3_lezart_eredmeny.json"
RESULT_MD = ROOT / "docs" / "v3_lezart_eredmeny.md"


class ProtocolError(RuntimeError):
    """A protokoll hiányos, nincs jóváhagyva, vagy eltér attól, amit a kód csinál."""


class LockedRunExists(RuntimeError):
    """Már van lezárt eredmény — a teszthez nem nyúlunk újra csendben."""


# ---------------------------------------------------------------- protokoll
def load_protocol(path: Path = PROTOCOL) -> tuple[dict, str]:
    """
    A protokoll és az ujjlenyomata. A sorvégeket egységesítjük (CRLF → LF):
    a git Windowson CRLF-fel, Linuxon LF-fel teszi ki ugyanazt a fájlt, és az
    ujjlenyomatnak mindkettőn egyeznie kell.
    """
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def git_state(path: Path) -> dict:
    """
    Commitolva van-e a protokoll, és tiszta-e a munkapéldány (a követett fájlokban
    nincs commitolatlan módosítás) — vagyis a futás pontosan egy commit állapotát méri-e.
    """
    path = Path(path).resolve()

    def git(*args):
        return subprocess.run(["git", *args], cwd=path.parent, capture_output=True, text=True)

    nincs = {"git": False, "commit": None, "protokoll_commitolva": False,
             "munkapeldany_tiszta": None}
    try:
        if git("rev-parse", "--show-toplevel").returncode != 0:
            return nincs
    except FileNotFoundError:            # nincs telepítve a git
        return nincs
    kovetett = git("ls-files", "--error-unmatch", str(path)).returncode == 0
    valtozott = git("status", "--porcelain", "--", str(path)).stdout.strip() != ""
    piszkos = git("status", "--porcelain", "--untracked-files=no").stdout.strip() != ""
    return {"git": True,
            "commit": git("rev-parse", "--short", "HEAD").stdout.strip() or None,
            "protokoll_commitolva": kovetett and not valtozott,
            "munkapeldany_tiszta": not piszkos}


def check_protocol(p: dict, adatforras: str) -> None:
    """Minden eltérés egyetlen hibaüzenetbe — hogy egyszerre lehessen javítani."""
    hibak = []
    if p.get("allapot") != "jovahagyva":
        hibak.append(f"a protokoll állapota „{p.get('allapot')}\", nem „jovahagyva\"")
    jov = p.get("jovahagyas") or {}
    if not jov.get("ki") or not jov.get("mikor"):
        hibak.append("hiányzik, ki és mikor hagyta jóvá (jovahagyas.ki, jovahagyas.mikor)")
    if not isinstance(p.get("cimke_tisztitas"), bool):
        hibak.append("a címke-tisztítás nincs eldöntve (cimke_tisztitas: true vagy false)")

    # A protokollnak azt kell leírnia, amit a kód ténylegesen csinál.
    mv = p.get("modellvalasztas") or {}
    elvart = {"hajtasok": ms.CV_FOLDS, "magok": list(ms.CV_SEEDS), "n_min": ms.N_MIN,
              "korai_leallitas_kor": train.EARLY_STOPPING_ROUNDS}
    for k, v in elvart.items():
        if mv.get(k) != v:
            hibak.append(f"modellvalasztas.{k} = {mv.get(k)!r}, a kódban {v!r}")
    vm = p.get("vegso_modell") or {}
    if vm.get("kiegyensulyozas") != "none":
        hibak.append("vegso_modell.kiegyensulyozas csak „none\" lehet (okt. 2-i döntés)")
    if vm.get("utolagos_kalibrator") is not False:
        hibak.append("vegso_modell.utolagos_kalibrator csak false lehet (okt. 2-i döntés)")
    if vm.get("learning_rate") != train.PARAMS["learning_rate"]:
        hibak.append(f"vegso_modell.learning_rate = {vm.get('learning_rate')!r}, "
                     f"a kódban {train.PARAMS['learning_rate']!r}")
    if not isinstance(vm.get("mag"), int):
        hibak.append("vegso_modell.mag hiányzik")
    ab = p.get("ablakok") or {}
    for k in ("tanito_vege", "validacio_vege"):
        kod = str(PLANNED["train_end" if k == "tanito_vege" else "valid_end"].date())
        if ab.get(k) != kod:
            hibak.append(f"ablakok.{k} = {ab.get(k)!r}, a kódban {kod!r}")
    if (p.get("adat") or {}).get("forras") != adatforras:
        hibak.append(f"adat.forras = {(p.get('adat') or {}).get('forras')!r}, "
                     f"a tárházban {adatforras!r}")
    tv = p.get("tanitasi_veletlen") or {}
    if not isinstance(tv.get("magok"), list) or len(tv["magok"]) < 2:
        hibak.append("tanitasi_veletlen.magok: legalább két mag kell (a szóráshoz)")
    bs = p.get("bizonytalansag") or {}
    if not isinstance(bs.get("B"), int) or bs["B"] < 100:
        hibak.append("bizonytalansag.B legalább 100 legyen")
    if not isinstance(bs.get("mag"), int):
        hibak.append("bizonytalansag.mag hiányzik")
    if hibak:
        raise ProtocolError("A lezárt futás nem indul — a protokoll:\n  - " + "\n  - ".join(hibak))


# -------------------------------------------------------------------- futás
def _provenance(db_path: Path) -> dict:
    con = connect(db_path, read_only=True)
    mb = con.execute("SELECT * FROM meta_build").df().iloc[0].to_dict()
    src = con.execute("SELECT fajl, sha256, sorok FROM meta_sources ORDER BY fajl").df()
    con.close()
    return {
        "adatforras": str(mb["adatforras"]),
        "tarhaz_epitve": str(mb["epitve"]),
        "rendelesek": int(mb["fact_sorok"]),
        "megfigyelesi_zarnap": str(mb.get("megfigyelesi_zarnap", "")),
        "forrasfajlok": {r.fajl: {"sha256": r.sha256, "sorok": int(r.sorok)}
                         for r in src.itertuples()},
    }


def _seed_sweep(db_path, seeds, n_trees, purge) -> dict:
    """Tanítási véletlen: ugyanaz a protokoll, más mag. A kimenetet elnyeljük."""
    rows = []
    for s in seeds:
        with contextlib.redirect_stdout(io.StringIO()):
            r = train.run(db_path, seed=int(s), tag="v3_lezart_mag", balance="none",
                          write_artifacts=False, trees=int(n_trees), purge=purge)
        rows.append({"mag": int(s), "teszt": r["teszt"], "validacio": r["validacio"]})
    out = {"magok": [int(s) for s in seeds], "fak_szama": int(n_trees), "futasok": rows}
    for ablak in ("teszt", "validacio"):
        out[ablak] = {}
        for k in METRICS:
            v = np.array([r[ablak][k] for r in rows], dtype=float)
            out[ablak][k] = {"atlag": round(float(v.mean()), 5),
                             "szoras": round(float(v.std(ddof=1)), 5) if len(v) > 1 else None,
                             "min": round(float(v.min()), 5), "max": round(float(v.max()), 5)}
    return out


def run_locked(db_path: Path = DB_PATH, protocol_path: Path = PROTOCOL,
               out_json: Path = RESULT_JSON, out_md: Path = RESULT_MD,
               ismetles: bool = False, require_committed: bool = True) -> dict:
    prot, sha = load_protocol(protocol_path)
    prov = _provenance(db_path)
    check_protocol(prot, prov["adatforras"])          # a modellhez csak ezután nyúlunk
    gs = git_state(protocol_path)
    if require_committed and not (gs["protokoll_commitolva"] and gs["munkapeldany_tiszta"]):
        raise ProtocolError(
            "A lezárt futás előtt a jóváhagyott protokollt és a kódot commitolni kell —\n"
            "a commit időbélyege bizonyítja, hogy a döntés megelőzte az eredményt.\n"
            + ("  (Itt nincs git-tároló.)\n" if not gs["git"] else
               f"  protokoll commitolva: {'igen' if gs['protokoll_commitolva'] else 'NEM'} · "
               f"commitolatlan módosítás: {'nincs' if gs['munkapeldany_tiszta'] else 'VAN'}\n")
            + "Teendő:\n  git add -A\n  git commit -m \"v3 protokoll jóváhagyva\"\n  git push\n"
            "majd újra: uv run python -m pipeline.v3_baseline")
    if Path(out_json).exists() and not ismetles:
        raise LockedRunExists(
            f"Már van lezárt eredmény: {out_json}\n"
            "A lezárt futás egyszeri. Ha mégis újra kell futtatni (pl. ellenőrzésként),\n"
            "használd az --ismetles kapcsolót — az eredményben ez látszani fog.")

    purge = bool(prot["cimke_tisztitas"])
    seed = int(prot["vegso_modell"]["mag"])
    bs = prot["bizonytalansag"]
    print(f"Protokoll: {Path(protocol_path).name} · SHA256 {sha[:16]}… · "
          f"jóváhagyta: {prot['jovahagyas']['ki']} ({prot['jovahagyas']['mikor']})")
    print(f"Címke-tisztítás: {'be' if purge else 'nincs'} · végső mag: {seed}\n")

    res = train.run(db_path, seed=seed, tag="v3_lezart", balance="none",
                    write_artifacts=True, trees="cv", purge=purge, return_predictions=True)
    pr = res.pop("elorejelzesek")
    n_fix = int(res["fak_szama"])

    print("\nBIZONYTALANSÁG — heti blokk-bootstrap "
          f"(B = {bs['B']}, ez egy-két percig tart)…")
    te, va = pr["teszt"], pr["valid"]
    bl_te, bl_va = week_blocks(te["ido"]), week_blocks(va["ido"])
    boot_te = block_bootstrap(te["y"], te["p"], bl_te, B=bs["B"], seed=bs["mag"])
    boot_va = block_bootstrap(va["y"], va["p"], bl_va, B=bs["B"], seed=bs["mag"])
    konstans = np.full(len(te["y"]), pr["tanito_arany"])
    paros = paired_block_bootstrap(
        te["y"], te["p"], konstans, bl_te,
        metrics={k: METRICS[k] for k in ("pr_auc", "brier")}, B=bs["B"], seed=bs["mag"])

    print("TANÍTÁSI VÉLETLEN — ugyanez a protokoll "
          f"{len(prot['tanitasi_veletlen']['magok'])} további maggal…")
    sweep = _seed_sweep(db_path, prot["tanitasi_veletlen"]["magok"], n_fix, purge)

    result = {
        "nev": prot.get("nev", "v3 lezárt alapfutás"),
        "protokoll_sha256": sha,
        "protokoll": prot,
        "futas": {
            "idopont_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "ismetles": bool(ismetles),
            "git": gs["commit"] or train.git_hash(),
            "git_allapot": gs,
            "commit_nelkul_engedve": not require_committed,
            "python": platform.python_version(),
            "os": platform.platform(),
            "artefaktumok": Path(res["artifacts"]).name,
        },
        "adat": prov,
        "modellvalasztas": res["modellvalasztas"],
        "cimke_tisztitas": res["cimke_tisztitas"],
        "vegso_modell": {"mag": seed, "fak_szama": n_fix, "jellemzok": res["jellemzok"],
                         "tanito_bazisrata": res["tanito_bazisrata"]},
        "validacio": {"bazisrata": res["validacio_bazisrata"], "bootstrap": boot_va},
        "teszt": {
            "bazisrata": res["bazisrata"],
            "bootstrap": boot_te,
            "paros_a_konstans_elorejelzessel": paros,
            "diagnosztika": res["teszt_diagnosztika"],
            "megbizhatosag_tizedek": None,
        },
        "tanitasi_veletlen": sweep,
    }
    # a tizedes megbízhatósági tábla a train.run metrics.json-jából
    mpath = Path(res["artifacts"]) / "metrics.json"
    if mpath.exists():
        result["teszt"]["megbizhatosag_tizedek"] = json.loads(
            mpath.read_text(encoding="utf-8")).get("megbizhatosag_tizedek")

    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(out_json).write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str),
                              encoding="utf-8")
    Path(out_md).write_text(summary_markdown(result), encoding="utf-8")
    _print_summary(result)
    print(f"\nMentve: {out_json}\n        {out_md}")
    print("Ezeket a fájlokat commitold — a commit a lezárt futás időbélyege.")
    return result


# ------------------------------------------------------------- összefoglaló
_NEV = {"pr_auc": "PR-AUC", "roc_auc": "ROC-AUC", "brier": "Brier",
        "ece": "ECE (egyenlő szélességű sávok)", "ece_egyenlo_elemszam": "ECE (tizedek)"}


def _ci(d: dict) -> str:
    return f"{d['ertek']:.4f} [{d['ci95'][0]:.4f}; {d['ci95'][1]:.4f}]"


def summary_markdown(r: dict) -> str:
    te, va, sw = r["teszt"], r["validacio"], r["tanitasi_veletlen"]
    mv = r["modellvalasztas"]
    sor = []
    for k in METRICS:
        m = sw["teszt"][k]
        sor.append(f"| {_NEV[k]} | {_ci(te['bootstrap'][k])} | {_ci(va['bootstrap'][k])} | "
                   f"{m['atlag']:.4f} ± {m['szoras']:.4f} |")
    ps = te["paros_a_konstans_elorejelzessel"]
    ism = " — **ISMÉTELT FUTÁS**" if r["futas"]["ismetles"] else ""
    return f"""# Lezárt v3 alapfutás — eredmény{ism}

Protokoll: `docs/v3_protokoll.json`, SHA256 `{r['protokoll_sha256']}`
Jóváhagyta: {r['protokoll']['jovahagyas']['ki']} ({r['protokoll']['jovahagyas']['mikor']}).
Futás: {r['futas']['idopont_utc']} UTC · git `{r['futas']['git']}`{' (tiszta munkapéldány, commitolt protokoll)' if r['futas']['git_allapot'].get('munkapeldany_tiszta') and r['futas']['git_allapot'].get('protokoll_commitolva') else ' (NEM commitolt állapot)'} · Python {r['futas']['python']}.
Adat: {r['adat']['adatforras']}, {r['adat']['rendelesek']:,} rendelés.

## Modellválasztás (csak a tanító időszak)
Bővülő ablakos CV, {mv['hajtasok_szama']} hajtás × {len(mv['magok'])} mag, korai leállítás PR-AUC-ra.
Legjobb iterációk mediánja {mv['median']:g} → **N_fix = {mv['n_fix']} fa**
(alsó korlát {mv['n_min']}{', ez döntött' if mv['also_korlat_dontott'] else ''}).
Címke-tisztítás: {'be' if r['cimke_tisztitas']['be'] else 'nincs'}
({r['cimke_tisztitas']['tanito_sorok']:,} tanító sor; {r['cimke_tisztitas']['kizart_tanito_sorok']:,} kimaradt).

## Eredmény
Végső modell: mag {r['vegso_modell']['mag']}, {r['vegso_modell']['fak_szama']} fa, {r['vegso_modell']['jellemzok']} jellemző.
Bázisráta (késési arány): teszt {te['bazisrata']:.4f}, validáció {va['bazisrata']:.4f},
tanító {r['vegso_modell']['tanito_bazisrata']:.4f}.

| mérőszám | teszt [95% CI, heti blokk-bootstrap] | validáció [95% CI] | teszt, {len(sw['magok'])} mag (átlag ± szórás) |
|---|---|---|---|
{chr(10).join(sor)}

Páros összevetés a teszten — a modell és a tanító időszak arányát mondó konstans előrejelzés:
PR-AUC különbség {ps['pr_auc']['kulonbseg']:+.4f} [{ps['pr_auc']['ci95'][0]:+.4f}; {ps['pr_auc']['ci95'][1]:+.4f}],
Brier-különbség {ps['brier']['kulonbseg']:+.5f} [{ps['brier']['ci95'][0]:+.5f}; {ps['brier']['ci95'][1]:+.5f}]
(negatív = a modell jobb).

Az intervallumok a teszt heteinek véletlenségét mérik ({te['bootstrap']['_beallitas']['blokkok']} hét,
B = {te['bootstrap']['_beallitas']['B']}); a magok szórása a tanítási véletlent — a kettő külön forrás.
Az ECE torzított mutató: a bootstrap-intervalluma felfelé tolódik, a pontbecslés a széle közelébe eshet.
"""


def _print_summary(r: dict) -> None:
    te, sw = r["teszt"], r["tanitasi_veletlen"]
    print("\nLEZÁRT v3 ALAPFUTÁS — TESZT (95% CI, heti blokk-bootstrap)")
    for k in METRICS:
        m = sw["teszt"][k]
        print(f"  {_NEV[k]:<32}{_ci(te['bootstrap'][k]):<34}"
              f"{len(sw['magok'])} mag: {m['atlag']:.4f} ± {m['szoras']:.4f}")


def main() -> None:
    use_utf8_console()
    ap = argparse.ArgumentParser(description="Lezárt v3 alapfutás (csak jóváhagyott protokollal)")
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--protokoll", type=Path, default=PROTOCOL)
    ap.add_argument("--ismetles", action="store_true",
                    help="ismételt futás egy meglévő eredmény mellett (az eredményben látszik)")
    ap.add_argument("--commit-nelkul", action="store_true",
                    help="git nélküli ellenőrző futtatás (pl. ZIP-ből); az eredményben látszik")
    a = ap.parse_args()
    try:
        run_locked(a.db, a.protokoll, ismetles=a.ismetles,
                   require_committed=not a.commit_nelkul)
    except (ProtocolError, LockedRunExists, WarehouseUnavailable, LeakageError,
            ValueError, FileNotFoundError) as exc:
        print(f"\nA LEZÁRT FUTÁS NEM INDULT:\n{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
