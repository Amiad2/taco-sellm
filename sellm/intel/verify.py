"""Automated checks V1-V10 of the dossiers (local plan, section 13): `python -m sellm.intel verify`."""

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from arena_kit.data import DataPackage

from . import build
from .extract import Source, number
from .schema import validate

ROOT = Path(__file__).resolve().parents[2]
CODE = Path(__file__).resolve().parent
CASES = ROOT / "sellm" / "lab" / "cases"
RUNS = ROOT / "runs"
ID_RE = re.compile(r"\b(?:idx|quote|offer|sc|qn|po|cost|fc|news|doc|ctr):[\w.:@#/-]*\w")
PSEUDO = ("below", "skonto", "group", "opening", "briefing")
FORBIDDEN_CALLS = re.compile(r"\b(httpx|requests|ArenaClient|llm_from_env|openai|anthropic)\b")
PRACTICE_NAMES = re.compile(r"sup:7\d{4}|case:[PDS]\d\d|Brandlhuber|Wimbacher|Nordmark|Dralveck")
MAX_BYTES = 2_000_000


def _files(out):
    return sorted(p for p in Path(out).glob("*.json") if p.name != "index.json")


def _load(out):
    return {
        json.loads(p.read_text(encoding="utf-8"))["supplier_id"]: json.loads(p.read_text(encoding="utf-8"))
        for p in _files(out)
    }


def v1_static(data, out):
    code = sorted(x for x in CODE.glob("*.py") if x.name != "verify.py")  # this file holds the patterns
    calls = [
        f"{p.name}:{i}"
        for p in code
        for i, line in enumerate(p.read_text().splitlines(), 1)
        if FORBIDDEN_CALLS.search(line)
    ]
    names = [
        f"{p.name}:{i}"
        for p in code
        for i, line in enumerate(p.read_text().splitlines(), 1)
        if PRACTICE_NAMES.search(line)
    ]
    lint = subprocess.run([sys.executable, "-m", "ruff", "check", str(CODE)], capture_output=True, text=True)
    ok = not calls and not names and lint.returncode == 0
    return (
        ok,
        f"network/LLM {calls or 'none'}, practice IDs or names {names or 'none'}, "
        f"ruff {'clean' if lint.returncode == 0 else lint.stdout[-300:]}",
    )


def v2_schema(data, out):
    ds = _load(out)
    bad = {sid: errs[:2] for sid, d in ds.items() if (errs := validate(d))}
    idx = json.loads((Path(out) / "index.json").read_text(encoding="utf-8"))
    idx_ok = idx.get("schema_version") == 1 and set(idx.get("suppliers", {})) == set(ds)
    return not bad and idx_ok, f"{len(ds) - len(bad)}/{len(ds)} valid, index {'ok' if idx_ok else 'wrong'} {bad or ''}"


def _digest(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(folder).glob("*.json"))}


def v3_determinism(data, out):
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        build.write_all(build.build_all(DataPackage(data)), a)
        build.write_all(build.build_all(DataPackage(data)), b)
        same, current = _digest(a) == _digest(b), _digest(a) == _digest(out)
    return (
        same and current,
        f"two builds {'identical' if same else 'DIFFER'}, "
        f"committed files {'current' if current else 'OUTDATED: run build'}",
    )


def v4_completeness(data, out):
    src, ds = Source(DataPackage(data)), _load(out)
    ids = src.detailed_ids()
    parts = len(
        src.q("SELECT so.part_id FROM sourcing so JOIN suppliers s ON s.id = so.supplier_id WHERE s.detail = 'full'")
    )
    docs = sum(len(src.documents(s)) for s in ids)
    news = sum(len(src.news(s)) for s in ids)
    market = {n["id"] for n in src.market_news()}
    got = (len(ds), sum(len(d["parts"]) for d in ds.values()), sum(len(d["documents"]) for d in ds.values()))
    got_news = sum(len(d["news"]) for d in ds.values())
    leaked = sorted({n["id"] for d in ds.values() for n in d["news"]} & market)
    size = sum(p.stat().st_size for p in Path(out).glob("*.json"))
    ok = set(ds) == set(ids) and got == (len(ids), parts, docs) and got_news == news and not leaked and size < MAX_BYTES
    return (
        ok,
        f"suppliers {len(ds)}/{len(ids)}, parts {got[1]}/{parts}, documents {got[2]}/{docs}, "
        f"news {got_news}/{news}, market news leaked {leaked or 'none'}, {size / 1e6:.2f} MB",
    )


def v5_numbers(data, out):
    """Every supplier and part recomputed with plain SQL, independently of derive.py."""
    src, ds, wrong = Source(DataPackage(data)), _load(out), []
    for sid, d in ds.items():
        spend = {
            r["fiscal_year"]: round(r["s"], 2)
            for r in src.q(
                "SELECT fiscal_year, sum(spend_eur) s FROM spend_cube WHERE supplier_id = ? GROUP BY 1", (sid,)
            )
        }
        if spend != d["economics"]["our_spend_eur"]:
            wrong.append(f"{sid} spend")
        late = src.one(
            "SELECT avg(julianday(paid_date) - julianday(due_date)) v, count(*) n FROM invoices WHERE supplier_id = ?",
            (sid,),
        )
        if late["n"] and round(late["v"], 1) != d["economics"]["we_pay_late_days"]:
            wrong.append(f"{sid} late days")
        for pid, part in d["parts"].items():
            price = src.one(
                "SELECT price FROM price_conditions WHERE supplier_id = ? AND part_id = ? AND valid_to IS NULL",
                (sid, pid),
            )
            if price and (part["current_price"] or {}).get("price") != round(price["price"], 2):
                wrong.append(f"{sid} {pid} price")
            own = src.one("SELECT id FROM should_cost WHERE part_id = ? AND supplier_id = ?", (pid, sid))
            generic = src.one(
                "SELECT id FROM should_cost WHERE part_id = ? AND (supplier_id IS NULL OR supplier_id = '')", (pid,)
            )
            expected = (own or generic or {}).get("id")
            if (part["should_cost"] or {}).get("id") != expected:
                wrong.append(
                    f"{sid} {pid} should-cost {part['should_cost'] and part['should_cost']['id']} != {expected}"
                )
    n = sum(len(d["parts"]) for d in ds.values())
    return not wrong, f"{len(ds)} suppliers, {n} parts recomputed, wrong {wrong[:5] or 'none'}"


def v6_citations(data, out):
    pkg, ds = DataPackage(data), _load(out)
    unknown, windows = set(), []
    for d in ds.values():
        for ref in ID_RE.findall(json.dumps(d, ensure_ascii=False)):
            if pkg.lookup(ref):
                continue
            base, _, suffix = ref.partition("#")
            if not (suffix in PSEUDO and pkg.lookup(base)):
                unknown.add(ref)
        for pid, part in d["parts"].items():
            for drv in part["drivers"]:
                for ids in (drv["ids_12m"], drv["ids_6m"]):
                    if ids:
                        a, b = (x.split("@")[1] for x in ids)
                        span = (int(b[:4]) - int(a[:4])) * 12 + int(b[5:]) - int(a[5:])
                        if span > 12 or b != drv["last_month"]:
                            windows.append(f"{d['supplier_id']} {pid} {drv['series']}")
    contradicted = _check_citable(pkg, ds)
    ok = not unknown and not windows and not contradicted
    return (
        ok,
        f"unknown IDs {sorted(unknown)[:5] or 'none'}, bad index windows {windows[:3] or 'none'}, "
        f"citable contradicted {contradicted or 'none'}",
    )


def _check_citable(pkg, ds):
    entries = [(d, c) for d in ds.values() for c in d["citable"] if c.get("statement")]
    if not entries:
        return []
    from sellm.lab.claims import ClaimChecker

    bad = []
    for d, c in entries:
        parts = sorted(d["parts"])
        drivers = [drv["series"] for p in d["parts"].values() for drv in p["drivers"]]
        case = {"parts": parts, "suppliers": [d["supplier_id"]], "term_options": {}, "buyer": {"index_paths": {}}}
        res = ClaimChecker(pkg.facts, case, drivers).check(d["supplier_id"], c["statement"], c.get("ids") or ())
        if any(r["result"] == "contradicted" for r in res):
            bad.append(f"{d['supplier_id']}: {c['statement'][:60]}")
    return bad


def v7_rules(data, out):
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            str(ROOT / "tests" / "test_intel.py"),
            "-k",
            "golden or noise or signals_and",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    last = (run.stdout.strip().splitlines() or ["no output"])[-1]
    return run.returncode == 0 and " passed" in last, f"golden tests: {last}"


def v8_overlay(data, out):
    from . import dossier

    pkg, times, bad, n = DataPackage(data), [], [], 0
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CASES.glob("*.json"))]
    sessions = []
    for f in sorted(RUNS.glob("practice/*/*.json")) + sorted(RUNS.glob("sandbox/*/*.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(s, dict) and "threads" in s:
            sessions.append((s["case"], s["threads"]))
    for case, threads in [(c, None) for c in cases] + sessions:
        for sid in case.get("suppliers", []):
            dossier(sid, case["parts"], case=case, opening=threads, package=pkg)
            t0 = time.perf_counter()
            d = dossier(sid, case["parts"], case=case, opening=threads, package=pkg)
            times.append(time.perf_counter() - t0)
            n += 1
            if validate(d) or any("failed" in w or "overlay:" in w or "opening e-mail:" in w for w in d["warnings"]):
                bad.append(f"{case.get('case_id')} {sid}: {(validate(d) + d['warnings'])[:2]}")
    stranger = dossier(
        "sup:0",
        ["part:0"],
        case={"facts": [{"id": "cost:0", "part": "part:0", "supplier": "sup:0", "unit_cost": 1.0}]},
        package=pkg,
    )
    if (
        validate(stranger)
        or stranger["coverage"] != "case_only"
        or stranger["parts"]["part:0"]["floor_estimate"]["value"] != 1.0
    ):
        bad.append("stranger")
    times.sort()
    p95 = times[max(0, int(len(times) * 0.95) - 1)] if times else 0
    return not bad and p95 < 0.1, f"{n} case x supplier calls, p95 {p95 * 1000:.1f} ms, problems {bad[:3] or 'none'}"


def v9_sunday(data, out):
    """A simulated release: a new letter for the first detailed supplier appears in its dossier and only there."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "package"
        shutil.copytree(data, root, ignore=shutil.ignore_patterns("release-sunday"))
        before = build.build_all(DataPackage(root))
        sid = sorted(before)[0]
        rel = root / "release-sunday"
        (rel / "data").mkdir(parents=True)
        (rel / "correspondence").mkdir()
        ref = f"doc:29991231-{number(sid)}-V9"
        (rel / "facts.json").write_text(json.dumps({ref: {"supplier": sid, "date": "2026-10-11", "type": "email"}}))
        (rel / "data" / "documents.csv").write_text(
            f"id,date,kind,supplier_id,part_ids,subject,author,file\n{ref},2026-10-11,email,{sid},,Payment,x,correspondence/v9.md\n"
        )
        (rel / "correspondence" / "v9.md").write_text(
            "# Payment\n\nemail - 2026-10-11 - x\n\nCould you pay our invoices within 10 days?"
        )
        after = build.build_all(DataPackage(root))
    doc_in = ref in {x["id"] for x in after[sid]["documents"]}
    signal = any(ref in s["evidence"] for s in after[sid]["signals"] if s["kind"] == "cash_short")

    def strip(d):
        return {k: v for k, v in d.items() if k != "built_from"}

    others = all(strip(after[s]) == strip(before[s]) for s in before if s != sid)
    flag = after[sid]["built_from"]["sunday_release"] is True
    ok = doc_in and signal and others and flag
    return (
        ok,
        f"new letter in {sid}: {doc_in}, cash_short cites it: {signal}, others unchanged: {others}, "
        f"release flag: {flag}",
    )


def v10_consumer(data, out):
    from . import dossier

    pkg, problems, floors, n = DataPackage(data), [], 0, 0
    for p in sorted(CASES.glob("*.json")):
        case = json.loads(p.read_text(encoding="utf-8"))
        if not case.get("hosted"):
            continue
        for sid in case["suppliers"]:
            d = dossier(sid, case["parts"], case=case, package=pkg)
            if not (0 < d["economics"]["cost_of_money"] <= 1) or not d["standard_terms"]:
                problems.append(f"{case['case_id']} {sid}")
            for pid in case["parts"]:
                n += 1
                fl = d["parts"][pid]["floor_estimate"]
                floors += fl is not None
                if fl is not None and not fl.get("basis"):
                    problems.append(f"{sid} {pid} floor without basis")
    return (
        not problems,
        f"{n} supplier x part pairs of the hosted cases, {floors} with a floor estimate, problems {problems or 'none'}",
    )


CHECKS = (
    ("V1 static", v1_static),
    ("V2 schema", v2_schema),
    ("V3 determinism", v3_determinism),
    ("V4 completeness", v4_completeness),
    ("V5 numbers", v5_numbers),
    ("V6 citations", v6_citations),
    ("V7 rules", v7_rules),
    ("V8 overlay", v8_overlay),
    ("V9 sunday", v9_sunday),
    ("V10 consumer", v10_consumer),
)


def run(data, out, checks=CHECKS):
    src = Source(DataPackage(data))
    print(
        f"sellm.intel verify  (package {src.version}, facts {src.facts_sha256[:8]}, dossiers {len(_files(out))}, "
        f"release: {'yes' if src.pkg.release else 'no'})"
    )
    results = []
    for name, check in checks:
        try:
            ok, detail = check(data, out)
        except Exception as e:
            ok, detail = False, f"{type(e).__name__}: {e}"
        results.append(ok)
        print(f"{name:.<22} {'PASS' if ok else 'FAIL'}  {detail}")
    print(f"RESULT: {'PASS' if all(results) else 'FAIL'}")
    return 0 if all(results) else 1
