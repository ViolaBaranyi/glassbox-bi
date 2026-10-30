"""
A K1 géphatás (docs/k1_protokoll_gepvaltas.json, tools/k1_gepvaltas.py, tools/gepvaltas_futtat.py).

A protokoll az elemző eszközt ujjlenyomattal rögzíti; a korábbi futások mind a saját helyükre illenek (és
az ① idejük a gépük osztályáé); a már közölt összevetéseket az eszköz pontosan visszaadja; az új futások a
gép mappájában a gep.json-nal számítanak, gépenként háromszor (a sorszám az indítás sorrendje; a negyedik
teljes futás hiba, nem választ), a kihagyott gép (laptop) nem számít és nem futtat; az ismételhetőség, a megismétlés és a gépek
közti összevetés a megfelelő párokat veti össze; a futtató receptjei a pár szerinti protokollt és kérdéssort adják,
a félbeszakadt futást folytatja (nem kezd újat), a kész futást a gép mappájába teszi, és nem indul, ha
valami nem a protokoll szerinti.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from narrative import meres  # noqa: E402


def _mod(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


gv = _mod("k1_gepvaltas")
fu = _mod("gepvaltas_futtat")
v4p = _mod("v4_protokoll")

P = json.loads((ROOT / "docs" / "k1_protokoll_gepvaltas.json").read_text(encoding="utf-8"))
KUSZOB = P["gep_azonositas"]["kuszob_ms"]
MERES = ROOT / "logs" / "meres"
SRC = MERES / "20261022_1902_qwen3.5-4b"          # m3-v5-4b, violapc, teljes


def _pub(name: str) -> dict:
    return json.loads((ROOT / "docs" / f"{name}.json").read_text(encoding="utf-8"))["eredmeny"]["fo"]


def test_a_protokoll_rogziti_az_eszkozt_es_a_parokat():
    assert P["allapot"] == "jovahagyva" and P["ismetles_futas"]["szam"] == 3
    assert P["elemzes"]["sha256"] == meres.sha256_text(ROOT / "tools" / "k1_gepvaltas.py")
    ids = [p["id"] for p in P["parok"]]
    assert len(ids) == len(set(ids)) == 10 and set(ids) == set(fu.RECEPTEK)
    assert list(P["gepek"]) == ["violapc"] and list(P["kimarad"]) == ["laptop"]
    for p in P["parok"]:
        assert meres.sha256_text(ROOT / p["kerdessor"]["fajl"]) == p["kerdessor"]["sha256"]
        assert fu.RECEPTEK[p["id"]]["kod"] == p["kod"]["verzio"] and p["modell"] in P["modellfajlok"]
    gepek, hely, foreign = gv.slots(P, MERES)
    assert list(gepek) == ["violapc"] and not foreign
    for p in P["parok"]:
        assert list(p["korabbi"]) == ["violapc"]
        s = hely[p["id"]]["violapc"]
        name = p["korabbi"]["violapc"]
        if name:
            assert s["korabbi"]["allapot"] == "megvan", (p["id"], s["korabbi"]["megjegyzes"])
        else:
            assert s["korabbi"] is None
        assert s["uj"]["allapot"] == "hiányzik"
    assert sum(bool(p["korabbi"]["violapc"]) for p in P["parok"]) == 5
    for k in P["kovetkeztetesek"]:
        assert all(pid in ids for pid in k.get("futasok", [k.get("a"), k.get("b")]))
    todo = fu.Futtato("violapc").terv()             # körökben: mind a tíz egyszer, aztán másodszor, harmadszor
    assert todo == ids * 3


def test_a_meglevo_futasok_ideje_a_gepuk_osztalya():
    by = {r["path"].name: r["osztaly_ido_szerint"] for r in gv.scan(MERES, KUSZOB)}
    for p in P["parok"]:
        for g, name in p["korabbi"].items():
            if name and name in by:
                assert by[name] == P["gepek"][g]["osztaly"], (name, g)


def test_a_kozolt_osszeveteseket_pontosan_visszaadja():
    res = gv.analyze(rejudge=False)
    assert not any(res["gepek_kozott"].values()) and set(res["gepek"]) == {"violapc"}
    k = {x["id"]: x for x in res["kovetkeztetesek"]}
    for kid, doc in (("K-e", "k1_9b_eredmeny"), ("K-g", "k1_v3_eredmeny")):
        got, pub = k[kid]["keszletenkent"]["violapc (korábbi)"], _pub(doc)
        assert (got["kulonbseg"], got["also"], got["felso"]) == (pub["kulonbseg"], pub["also"], pub["felso"]), kid
    assert k["K-a"]["keszletenkent"]["violapc (korábbi)"] is None       # az 1. mérésnek nincs korábbi violapc-futása
    # a közölt gépváltás-pár (laptop – violapc) a két-futásos eszközzel, ahogy a dolgozat közli
    par = next(p for p in P["parok"] if p["id"] == "m2-v4-4b")
    a, b = gv.v2.Run(MERES / "20261022_1040_qwen3.5-4b", "violapc"), gv.v2.Run(MERES / "20261020_1300_qwen3.5-4b", "laptop")
    res2 = gv.fo.compare(a, b, gv._questions(par, ROOT), gv._proto(par, par["bootstrap"]))
    assert res2["fo"] == _pub("k1_v2_gepvaltas") and res2["egyezes"]["azonos_ertelmezes"] == 44
    assert gv.independent({"a": {"kulonbseg": 0.1, "also": 0.02, "felso": 0.2},
                           "b": {"kulonbseg": 0.05, "also": -0.01, "felso": 0.1}}) is False
    assert gv.independent({"a": {"kulonbseg": 0.1, "also": -0.02, "felso": 0.2}, "b": None}) is None
    assert gv.report_md(res, P).count("## ") == 8


def _registry(d: Path, gep: str, gepnev: str, osztaly: str = "videokartya") -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{gep}.json").write_text(json.dumps({"gep": gep, "gepnev": gepnev, "osztaly": osztaly}), encoding="utf-8")


def _gep_json(run: Path, gep: str, par: str, gepnev: str, kezdes: str = "2026-10-31T10:00:00") -> None:
    (run / "gep.json").write_text(json.dumps({"gep": gep, "par": par, "inditasok": [{"gepnev": gepnev, "kezdes": kezdes}]}),
                                  encoding="utf-8")


def _replica(meres_dir: Path, i: int, gep: str = "gepx", gepnev: str = "GEPX") -> Path:
    run = meres_dir / gep / f"2026103{i}_1000_qwen3.5-4b"
    shutil.copytree(SRC, run)
    _gep_json(run, gep, "m3-v5-4b", gepnev, f"2026-10-3{i}T10:00:00")
    return run


def test_uj_futasok_a_gep_mappajaban_haromszor(tmp_path):
    meres_dir, gepek = tmp_path / "meres", tmp_path / "gepek"
    _registry(gepek, "gepx", "GEPX")
    runs = [_replica(meres_dir, i) for i in (3, 1)]                    # a sorszám az indítás sorrendje
    g, hely, _ = gv.slots(P, meres_dir, gepek)
    assert list(g) == ["violapc", "gepx"]
    u = hely["m3-v5-4b"]["gepx"]["uj"]
    assert u["allapot"] == "részben" and u["megjegyzes"] == "2/3" and [c["path"] for c in u["futasok"]] == runs[::-1]
    assert hely["m3-v4-4b"]["gepx"]["uj"]["allapot"] == "hiányzik"
    third = _replica(meres_dir, 2)
    rows = (SRC / "sorok.jsonl").read_text(encoding="utf-8").splitlines()
    (third / "sorok.jsonl").write_text("\n".join(rows[:20]) + "\n", encoding="utf-8")
    u = gv.slots(P, meres_dir, gepek)[1]["m3-v5-4b"]["gepx"]["uj"]
    assert u["allapot"] == "részben" and "folyamatban" in u["megjegyzes"] and "20/50" in u["megjegyzes"]
    shutil.copyfile(SRC / "sorok.jsonl", third / "sorok.jsonl")
    assert gv.slots(P, meres_dir, gepek)[1]["m3-v5-4b"]["gepx"]["uj"]["allapot"] == "megvan"
    # négy teljes futás három helyére: hiba, nem választ
    fourth = _replica(meres_dir, 4)
    u = gv.slots(P, meres_dir, gepek)[1]["m3-v5-4b"]["gepx"]["uj"]
    assert u["allapot"] == "hiba" and "4 teljes futás" in u["megjegyzes"]
    # rossz vagy hiányzó gep.json: hiba
    _gep_json(fourth, "gepx", "m3-v5-4b", "MASGEP")
    assert "gépnév más" in gv.slots(P, meres_dir, gepek)[1]["m3-v5-4b"]["gepx"]["uj"]["megjegyzes"]
    (fourth / "gep.json").unlink()
    assert "nincs mellette gep.json" in gv.slots(P, meres_dir, gepek)[1]["m3-v5-4b"]["gepx"]["uj"]["megjegyzes"]
    shutil.rmtree(fourth)
    # a kihagyott gép (laptop) futásai nem számítanak, akkor sem, ha felvennék: a jelentésben külön látszanak
    shutil.copytree(SRC, meres_dir / "laptop" / SRC.name)
    _registry(gepek, "laptop", "LAPTOP", "processzor")
    g, hely, foreign = gv.slots(P, meres_dir, gepek)
    assert "laptop" not in g and foreign == {"(nem számító gép)": ["laptop"]}


def test_ismetelhetoseg_megismetles_es_gepek_kozott(tmp_path):
    meres_dir, gepek = tmp_path / "meres", tmp_path / "gepek"
    meres_dir.mkdir()
    for d in MERES.iterdir():
        if (d / "fej.json").exists():
            (meres_dir / d.name).symlink_to(d, target_is_directory=True)
    _registry(gepek, "gepx", "GEPX")
    for i in (1, 2, 3):
        _replica(meres_dir, i)
    res = gv.analyze(meres_dir=meres_dir, gepek_dir=gepek, rejudge=False)
    ism = res["ismetelhetoseg"]["m3-v5-4b"]["gepx"]
    assert [(x["a"], x["b"]) for x in ism["parok"]] == [(1, 2), (1, 3), (2, 3)]
    assert ism["mind_azonos"] == {"k": 50, "n": 50, "futasok": 3}
    assert all(t["k"] == t["n"] > 0 for x in ism["parok"] for t in x["azonos_szoveg"].values())
    vx = res["gepek_kozott"]["m3-v5-4b"]["violapc|gepx"]             # a violapcnek itt csak korábbi futása van
    assert [(x["a"], x["b"]) for x in vx] == [(gv.K, 1), (gv.K, 2), (gv.K, 3)]
    assert all(x["eredmeny"]["egyezes"]["azonos_ertelmezes"] == 50 and not x["eltero_ertelmezes"] for x in vx)
    assert res["osszesitve"]["ismetlesek"]["gepx"]["azonos_ertelmezes"]["k"] == 150
    k = {x["id"]: x for x in res["kovetkeztetesek"]}
    assert set(k["K-h"]["keszletenkent"]) == {"violapc (korábbi)", "gepx #1", "gepx #2", "gepx #3"}
    assert k["K-h"]["keszletenkent"]["gepx #1"] is None and k["K-h"]["keszletenkent"]["violapc (korábbi)"] is not None
    assert gv.pairings([1, 2, 3], [gv.K, 1, 2]) == [(1, 1), (2, 2)]
    assert gv.pairings([gv.K], [gv.K, 1]) == [(gv.K, gv.K), (gv.K, 1)]
    md = gv.report_md(res, P)
    assert "m3-v5-4b · gepx #1 → #2 | 50/50" in md and "violapc korábbi → gepx #3 | 50/50" in md
    json.loads(gv.to_json(res))


def test_a_receptek_a_par_szerinti_protokollt_es_kerdessort_adjak():
    for pid, rec in fu.RECEPTEK.items():
        par = next(p for p in P["parok"] if p["id"] == pid)
        want = par["futas_protokoll"]["sha256"]
        if rec.get("szarmaztat"):
            src = json.loads((ROOT / "docs" / "k1_protokoll_v3.json").read_text(encoding="utf-8"))
            assert v4p.sha256(src) == want, pid
        elif rec["kod"] == "v5":
            assert meres.sha256_text(ROOT / rec["protokoll"]) == want, pid
        else:
            (src,) = [s for s, d in rec["masol"].items() if d == rec["protokoll"]]
            assert meres.sha256_text(ROOT / src) == want, pid
        assert bool(rec.get("kapcsolo")) == (rec["kod"] != "v3"), pid     # a v3 kód csak az alap protokollfájlt olvassa


class _Gep:
    """Álgép a futtató teszteléséhez: git, ollama és a mérőprogram helyett."""

    def __init__(self, root: Path, commit: dict[str, str]):
        self.root, self.commit, self.calls = root, commit, []

    def adatok(self):
        return {"gepnev": "GEPX", "osztaly": "videokartya", "processzor": "teszt", "memoria_gb": 16.0,
                "videokartyak": ["NVIDIA teszt, 1.0, 8188 MiB"], "ollama": "ollama version is 0.0.0",
                "modellek": {"qwen3.5:4b": "d8b0f5e9760c", "qwen3.5:2b": "0689d44085e0"}}

    def kimenet(self, cmd, cwd):
        self.calls.append(("ki", cmd, cwd))
        if cmd[:2] == ["ollama", "ps"]:
            return "NAME          ID              SIZE      PROCESSOR    UNTIL\nqwen3.5:4b    d8b0f5e9760c    5.1 GB    100% GPU     29 minutes from now"
        if cmd[:3] == ["git", "worktree", "add"]:
            (self.root / cmd[3]).mkdir(parents=True)
            (self.root / cmd[3] / "data").mkdir()
            return ""
        if cmd[:3] == ["git", "rev-parse", "HEAD"]:
            return self.commit.get(Path(cwd).name)
        return ""

    def parancs(self, cmd, cwd, figyel=None):
        self.calls.append(("fut", cmd, cwd))
        if cmd[:2] == ["uv", "sync"]:
            return 0
        if "tools/v4_protokoll.py" in cmd:
            v4p.main([cmd[-1]])
            return 0
        logs = Path(cwd) / "logs" / "meres"
        rows = (SRC / "sorok.jsonl").read_text(encoding="utf-8").splitlines(keepends=True)
        if "--folytat" in cmd:
            run = Path(cmd[cmd.index("--folytat") + 1])
            figyel()
            with (run / "sorok.jsonl").open("a", encoding="utf-8") as f:
                f.writelines(rows[20:])
            shutil.copyfile(SRC / "osszegzes.json", run / "osszegzes.json")
            figyel()
            return 0
        run = logs / "20261030_2000_qwen3.5-4b"
        run.mkdir(parents=True)
        shutil.copyfile(SRC / "fej.json", run / "fej.json")
        (run / "sorok.jsonl").write_text("".join(rows[:20]), encoding="utf-8")
        figyel()
        return 130                                   # megszakadt


def _fake_root(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    for rel in ["docs/k1_protokoll_gepvaltas.json", "docs/k1_protokoll.json", "docs/k1_protokoll_v1_9b.json",
                "docs/k1_protokoll_v2.json", "docs/k1_protokoll_v2_9b.json", "docs/k1_protokoll_v3.json",
                "eval/meresi_kerdessor.toml", "eval/meresi_kerdessor_v2.toml", "eval/meresi_kerdessor_v3.toml"]:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, root / rel)
    (root / "data").mkdir()
    (root / "data" / "warehouse.duckdb").write_bytes(b"")
    (root / "logs" / "meres").mkdir(parents=True)
    return root


def test_a_futtato_folytatja_a_felbeszakadt_futast_es_a_gep_mappajaba_teszi(tmp_path):
    root = _fake_root(tmp_path)
    gep = _Gep(root, {})
    f = fu.Futtato("gepx", root=root, gepadatok=gep.adatok, futo=lambda: [], kimenet=gep.kimenet, parancs=gep.parancs)
    assert f.terv() == [p["id"] for p in P["parok"]] * 3      # új gép: mind a tíz, háromszor, körökben
    with pytest.raises(fu.Megall, match="megszakadt"):
        f.futtat_par("m3-v5-4b")
    part = root / "logs" / "meres" / "20261030_2000_qwen3.5-4b"
    gj = json.loads((part / "gep.json").read_text(encoding="utf-8"))
    assert gj["gep"] == "gepx" and gj["par"] == "m3-v5-4b" and gj["inditasok"][0]["kilepes"] == 130
    assert f.felbehagyott("m3-v5-4b", root) == part and f.terv(["m3-v5-4b"]) == ["m3-v5-4b"] * 3
    dest = f.futtat_par("m3-v5-4b")                    # ugyanaz a parancs: folytat, nem kezd újat
    assert dest == root / "logs" / "meres" / "gepx" / part.name and not part.exists()
    starts = [c[1] for c in gep.calls if c[0] == "fut" and "narrative.meres" in c[1]]
    assert starts[0] == ["uv", "run", "python", "-m", "narrative.meres", "--protokoll", "docs/k1_protokoll_v3.json",
                         "--modell", "qwen3.5:4b"]
    assert starts[1] == starts[0] + ["--folytat", str(part)]
    gj = json.loads((dest / "gep.json").read_text(encoding="utf-8"))
    assert [i["folytatas"] for i in gj["inditasok"]] == [False, True] and gj["modellfajl"] == "d8b0f5e9760c"
    assert "100% GPU" in gj["ollama_ps_utana"] and gv._proc_split(gj["ollama_ps_utana"]) == "100% GPU"
    _registry(root / "docs" / "gepvaltas_gepek", "gepx", "GEPX")
    s = gv.slots(P, root / "logs" / "meres", root / "docs" / "gepvaltas_gepek")[1]["m3-v5-4b"]["gepx"]["uj"]
    assert s["allapot"] == "részben" and s["megjegyzes"] == "1/3"
    assert f.terv(["m3-v5-4b"]) == ["m3-v5-4b"] * 2


def test_a_futtato_a_regi_kodot_kulon_munkamappaban_keszit_elo(tmp_path):
    root = _fake_root(tmp_path)
    gep = _Gep(root, {"v3_kod": P["kodok"]["v3"]["commit"], "v4_kod": P["kodok"]["v4"]["commit"]})
    f = fu.Futtato("gepx", root=root, gepadatok=gep.adatok, futo=lambda: [], kimenet=gep.kimenet, parancs=gep.parancs)
    code, cmd = f.elokeszit("m1-9b")
    assert code == root / "v3_kod" and cmd[-2:] == ["--modell", "qwen3.5:9b"] and "--protokoll" not in cmd
    assert meres.sha256_text(code / "docs" / "k1_protokoll.json") == meres.sha256_text(ROOT / "docs" / "k1_protokoll_v1_9b.json")
    assert (code / "data" / "warehouse.duckdb").exists() and (code / "eval" / "meresi_kerdessor.toml").exists()
    code, cmd = f.elokeszit("m2-v3-4b")             # ugyanaz a munkamappa, a 2. mérés protokolljával
    assert meres.sha256_text(code / "docs" / "k1_protokoll.json") == meres.sha256_text(ROOT / "docs" / "k1_protokoll_v2.json")
    code, cmd = f.elokeszit("m3-v4-4b")             # a v4 kód a 3. mérés származtatott protokolljával
    assert code == root / "v4_kod" and cmd[5:7] == ["--protokoll", "docs/k1_protokoll_v3.json"]
    assert [c[1][:3] for c in gep.calls if c[1][:2] == ["git", "worktree"]] == [["git", "worktree", "prune"],
                                                                                ["git", "worktree", "add"]] * 2
    assert sum(c[1] == ["uv", "sync"] for c in gep.calls) == 2      # munkamappánként egyszer
    gep.commit["v4_kod"] = "mas"
    f2 = fu.Futtato("gepx", root=root, gepadatok=gep.adatok, futo=lambda: [], kimenet=gep.kimenet, parancs=gep.parancs)
    with pytest.raises(fu.Megall, match="nem a v4 kód commitján"):
        f2.elokeszit("m2-v4-2b")


def test_a_futtato_nem_indul_ha_valami_nem_a_protokoll_szerinti(tmp_path, monkeypatch):
    root = _fake_root(tmp_path)
    gep = _Gep(root, {})
    monkeypatch.setattr(fu, "tarhaz_ujjlenyomat", lambda db: "mas")
    f = fu.Futtato("gepx", root=root, gepadatok=gep.adatok, futo=lambda: ["1234 python -m narrative.meres"],
                   kimenet=gep.kimenet, parancs=gep.parancs)
    msgs = " | ".join(f.elofeltetelek(["m1-4b"]))
    assert "még nincs felvéve" in msgs
    _registry(root / "docs" / "gepvaltas_gepek", "gepx", "MASIKGEP")
    msgs = " | ".join(f.elofeltetelek(["m1-4b", "m1-9b", "m2-v4-2b"]))
    for want in ("ez nem a(z) gepx gép", "a tárház tartalma nem a protokoll szerinti", "ollama pull qwen3.5:9b",
                 "most is fut mérés"):
        assert want in msgs, want
    assert "qwen3.5:4b" not in msgs and "qwen3.5:2b" not in msgs
    with pytest.raises(fu.Megall, match="kimarad"):
        fu.Futtato("laptop", root=root, gepadatok=gep.adatok, kimenet=gep.kimenet, parancs=gep.parancs)
    with pytest.raises(fu.Megall, match="kimarad"):
        fu.felvesz("laptop", root=root, gepadatok=gep.adatok)


def test_a_tarhaz_ujjlenyomata_a_protokolle():
    db = ROOT / "data" / "warehouse.duckdb"
    if not db.exists():
        pytest.skip("nincs tárház (uv run python inditas.py)")
    assert fu.tarhaz_ujjlenyomat(db) == P["tarhaz"]["ujjlenyomat"]


def test_segedek_es_a_bat():
    assert fu.ollama_list("NAME  ID  SIZE  MODIFIED\nqwen3.5:4b    d8b0f5e9760c    3.4 GB    2 weeks ago\n") == \
        {"qwen3.5:4b": "d8b0f5e9760c"}
    assert gv._proc_split("NAME ID SIZE PROCESSOR UNTIL\nqwen3.5:9b  56671c2ab938  8.2 GB  48%/52% CPU/GPU  4 minutes") \
        == "48%/52% CPU/GPU"
    raw = (ROOT / "tools" / "gepvaltas.bat").read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")
    text = raw.decode("ascii")
    assert "tools\\gepvaltas_futtat.py %*" in text and 'set "VIRTUAL_ENV="' in text
    assert not (ROOT / "tools" / "gepvaltas_laptop.bat").exists()
