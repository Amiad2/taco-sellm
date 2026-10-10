# ruff: noqa: E501  (the page is one HTML string)
"""A small local web UI for the lab: start runs, watch them, tune knobs, extend runs, export results.

    scripts/lab ui            (or: uv run python -m sellm.lab ui [--port 8765] [--no-browser])

Listens on 127.0.0.1 only. Runs are started as their own processes (they keep going when the UI
stops) with the same command line as `scripts/lab`; their output goes to runs/lab/nohup-*.log and
their results to the run folder as usual. No arena calls; the `llm` agent and `--reader llm` call
your LLM key.
"""

import csv
import gzip
import io
import json
import os
import signal
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs" / "lab"
JOBS = RUNS / "ui-jobs.json"
COMMANDS = {"search", "compare", "stress"}
CSV_FIELDS = ["strategy", "knobs", "scenario", "kind", "pool", "type", "goal", "tags", "archetypes", "seed",
              "score", "deal", "end", "rounds", "seconds", "timeouts", "rejected", "broken", "worse", "crash"]  # fmt: skip


def _jobs():
    try:
        return json.loads(JOBS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save_jobs(jobs):
    RUNS.mkdir(parents=True, exist_ok=True)
    JOBS.write_text(json.dumps(jobs, indent=1), encoding="utf-8")


def _alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:  # a finished child stays a zombie until reaped
        return os.waitpid(pid, os.WNOHANG) == (0, 0)
    except ChildProcessError:
        return True


def _run_folder(log):
    try:
        for line in Path(log).read_text(encoding="utf-8").splitlines()[:5]:
            if line.startswith("run folder: "):
                return line.split("run folder: ", 1)[1].split()[0]
    except OSError:
        pass
    return None


def argv_for(cmd, o):
    """The `python -m sellm.lab` command line for a start request (typed, no shell)."""
    if cmd not in COMMANDS:
        raise ValueError(f"unknown command {cmd}")
    args = [cmd]
    if cmd == "search":
        args += ["--minutes", str(float(o.get("minutes") or 10)), "--start", str(int(o.get("start") or 64))]
    if cmd == "compare":
        agents = [a.strip() for a in (o.get("agents") or "naive,calc").split(",") if a.strip()]
        args += agents
    if cmd == "stress":
        args += ["--agent", o.get("agent") or "calc", "--n", str(int(o.get("n") or 120))]
        args += ["--per-edge", str(int(o.get("per_edge") or 6))]
    else:
        args += ["--invented", str(int(o.get("invented") or 160)), "--test", str(int(o.get("test") or 80))]
    if o.get("knobs") and cmd != "search":
        json.loads(o["knobs"]) if o["knobs"].strip().startswith("{") else None
        args += ["--knobs", o["knobs"]]
    args += ["--seeds", str(int(o.get("seeds") or 2)), "--mode", o.get("mode") or "parallel"]
    args += ["--wave-cap", str(float(o.get("wave_cap") if o.get("wave_cap") not in (None, "") else 480))]
    args += ["--think", str(float(o.get("think") if o.get("think") not in (None, "") else 2.0))]
    args += ["--reader", o.get("reader") or "keywords", "--supplier", o.get("supplier") or "engine"]
    if o.get("no_clock"):
        args.append("--no-clock")
    if o.get("fixed_twins"):
        args.append("--fixed-twins")
    if o.get("invent_seed"):
        args += ["--invent-seed", str(int(o["invent_seed"]))]
    label = "".join(c for c in (o.get("label") or "") if c.isalnum() or c in "-_")
    if label:
        args += ["--label", label]
    return args


def start(cmd, o):
    args = argv_for(cmd, o)
    RUNS.mkdir(parents=True, exist_ok=True)
    log = RUNS / f"nohup-{time.strftime('%Y%m%d-%H%M%S')}-{cmd}.log"
    with open(log, "w", encoding="utf-8") as fh:
        p = subprocess.Popen(
            [sys.executable, "-m", "sellm.lab", *args], cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT,
            start_new_session=True,
        )  # fmt: skip
    job = {"id": f"{int(time.time() * 1000)}", "cmd": cmd, "args": args, "options": o, "pid": p.pid,
           "log": str(log), "started": time.strftime("%Y-%m-%d %H:%M:%S")}  # fmt: skip
    _save_jobs(_jobs() + [job])
    return job


def jobs():
    out = []
    for j in reversed(_jobs()[-40:]):
        j = {**j, "running": _alive(j["pid"]), "folder": _run_folder(j["log"])}
        try:
            j["tail"] = "".join(Path(j["log"]).read_text(encoding="utf-8").splitlines(keepends=True)[-12:])
        except OSError:
            j["tail"] = ""
        out.append(j)
    return out


def stop(job_id):
    for j in _jobs():
        if j["id"] == job_id and _alive(j["pid"]):
            os.killpg(os.getpgid(j["pid"]), signal.SIGTERM)
            return True
    return False


def runs():
    """Every run folder, newest first, with what it holds."""
    out = []
    running = {j["folder"] for j in jobs() if j["running"] and j["folder"]}
    for p in sorted((x for x in RUNS.glob("*/") if x.is_dir()), reverse=True):
        rel = str(p.relative_to(ROOT))
        logs = sorted(p.rglob("progress.log"))
        tail = ""
        if logs:
            tail = "".join(logs[-1].read_text(encoding="utf-8").splitlines(keepends=True)[-15:])
        out.append({
            "name": p.name, "path": rel, "report": (p / "report.md").exists(), "best": (p / "best.json").exists(),
            "rows": any(p.rglob("rows.jsonl.gz")), "running": rel in running or str(p) in running, "progress": tail,
        })  # fmt: skip
    return out


def _folder(name):
    p = (RUNS / name).resolve()
    if not p.is_relative_to(RUNS.resolve()) or not p.is_dir():
        raise FileNotFoundError(name)
    return p


def best(name):
    p = _folder(name) / "best.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def rows_csv(name):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    w.writeheader()
    for path in sorted(_folder(name).rglob("rows.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                r["knobs"] = json.dumps(r.get("knobs") or {}, sort_keys=True)
                r["tags"], r["archetypes"] = ",".join(r.get("tags") or []), ",".join(r.get("archetypes") or [])
                w.writerow(r)
    return buf.getvalue()


def zipped(name):
    folder, buf = _folder(name), io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in folder.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(folder.parent))
    return buf.getvalue()


def agent_snippet(name, rank=1):
    """The knobs of a run's rank-n variant as the KNOBS block of sellm/agent.py."""
    b = best(name)
    if not b:
        return "# this run has no best.json"
    entry = b[min(rank, len(b)) - 1]
    knobs = entry.get("knobs") or {}
    test = entry.get("test")
    score = test if isinstance(test, float) and test == test else entry.get("mean") or 0  # NaN: no test pool
    lines = [f"# {name}, rank {rank}: score {100 * score:.1f} (on its test pool if it had one)", "KNOBS = dict("]
    lines += [f"    {k}={v!r}," for k, v in sorted(knobs.items())]
    return "\n".join(lines + [")"]) + "\n"


def meta():
    from . import twins
    from .invent import EDGES
    from .strategies import DEFAULTS, SPACE

    return {
        "agents": ["naive", "calc", "sellm.agent:make_agent", "llm"],
        "space": SPACE,
        "defaults": DEFAULTS,
        "twins": [s.name for s in twins.load()],
        "edges": EDGES,
    }


def play(o):
    """One negotiation, printed like `python -m sellm.lab play`."""
    args = [sys.executable, "-m", "sellm.lab", "play", o.get("scenario") or "P01", "--agent", o.get("agent") or "calc"]
    if o.get("knobs"):
        args += ["--knobs", o["knobs"]]
    args += ["--mode", o.get("mode") or "parallel", "--seed", str(int(o.get("seed") or 0))]
    args += ["--supplier", o.get("supplier") or "engine"]
    if o.get("no_clock"):
        args.append("--no-clock")
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=600)
    return r.stdout + (("\n" + r.stderr[-3000:]) if r.returncode else "")


def create_app():
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

    app = FastAPI(title="sellm lab")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return PAGE

    @app.get("/api/meta")
    def api_meta():
        return meta()

    @app.get("/api/runs")
    def api_runs():
        return {"runs": runs(), "jobs": jobs()}

    @app.post("/api/start")
    async def api_start(request: Request):
        body = await request.json()
        try:
            return start(body.get("cmd"), body.get("options") or {})
        except (ValueError, TypeError) as e:
            raise HTTPException(400, str(e)) from None

    @app.post("/api/stop/{job_id}")
    def api_stop(job_id: str):
        return {"stopped": stop(job_id)}

    @app.post("/api/play")
    async def api_play(request: Request):
        return PlainTextResponse(play(await request.json()))

    def _get(fn, *a):
        try:
            return fn(*a)
        except FileNotFoundError:
            raise HTTPException(404, "no such run") from None

    @app.get("/api/run/{name}/report")
    def api_report(name: str):
        p = _get(_folder, name) / "report.md"
        reports = [p] if p.exists() else sorted(_get(_folder, name).rglob("report.md"))
        return PlainTextResponse("\n\n".join(r.read_text(encoding="utf-8") for r in reports) or "no report yet")

    @app.get("/api/run/{name}/best")
    def api_best(name: str):
        return JSONResponse(_get(best, name))

    @app.get("/api/run/{name}/snippet")
    def api_snippet(name: str, rank: int = 1):
        return PlainTextResponse(_get(agent_snippet, name, rank))

    @app.get("/api/run/{name}/export/{what}")
    def api_export(name: str, what: str):
        folder = _get(_folder, name)
        if what == "report.md":
            data, kind = (folder / "report.md").read_bytes(), "text/markdown"
        elif what == "best.json":
            data, kind = (folder / "best.json").read_bytes(), "application/json"
        elif what == "rows.csv":
            data, kind = rows_csv(name).encode(), "text/csv"
        elif what == "run.zip":
            data, kind = zipped(name), "application/zip"
        else:
            raise HTTPException(404, what)
        return Response(data, media_type=kind, headers={"Content-Disposition": f'attachment; filename="{name}-{what}"'})

    return app


def serve(port=8765, browser=True):
    import threading
    import webbrowser

    import uvicorn

    url = f"http://127.0.0.1:{port}"
    print(f"lab UI on {url}  (Ctrl+C stops the UI; runs it started keep going)", flush=True)
    if browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>sellm lab</title>
<script defer src="https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"></script>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c1e21;--mute:#666;--line:#dde1e6;--acc:#2457d6;--ok:#1d8a4b;--warn:#b25b00}
@media (prefers-color-scheme:dark){:root{--bg:#141518;--card:#1d1f23;--ink:#e8e8ea;--mute:#a0a3a8;--line:#33363c;--acc:#7aa2ff;--ok:#4cc38a;--warn:#f0a050}}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--ink)}
header{display:flex;gap:8px;align-items:center;padding:10px 16px;border-bottom:1px solid var(--line);background:var(--card);position:sticky;top:0;z-index:2}
header b{margin-right:12px}.tab{border:1px solid var(--line);background:none;color:var(--ink);padding:6px 12px;border-radius:6px;cursor:pointer}
.tab.on{background:var(--acc);color:#fff;border-color:var(--acc)}main{padding:16px;max-width:1300px;margin:auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px;margin-bottom:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px}
label{display:flex;flex-direction:column;gap:3px;font-size:12px;color:var(--mute)}
input,select,textarea{font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:6px}
textarea{width:100%;min-height:70px;font-family:ui-monospace,monospace;font-size:12px}
button.go{background:var(--acc);color:#fff;border:0;border-radius:6px;padding:8px 14px;cursor:pointer;font-weight:600}
button.sm{background:none;border:1px solid var(--line);color:var(--ink);border-radius:6px;padding:4px 9px;cursor:pointer;font-size:12px}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.mute{color:var(--mute);font-size:12px}
.split{display:grid;grid-template-columns:330px 1fr;gap:14px}@media (max-width:800px){.split{grid-template-columns:1fr}}
.item{padding:8px;border:1px solid var(--line);border-radius:6px;margin-bottom:6px;cursor:pointer}.item.on{border-color:var(--acc)}
.badge{font-size:11px;padding:1px 6px;border-radius:9px;border:1px solid var(--line)}.run{color:var(--warn);border-color:var(--warn)}.done{color:var(--ok);border-color:var(--ok)}
pre{white-space:pre-wrap;word-break:break-word;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:10px;font-size:12px;max-height:520px;overflow:auto}
.md table{border-collapse:collapse;font-size:12px;display:block;overflow-x:auto}.md td,.md th{border:1px solid var(--line);padding:3px 6px;white-space:nowrap}
.md h1{font-size:18px}.md h2{font-size:15px;margin-top:18px}
#knobtable{display:none}#knobtable.show{display:grid}.hidden{display:none}
</style></head><body>
<header><b>sellm lab</b><button class="tab on" data-t="start">Start</button><button class="tab" data-t="runs">Runs</button><button class="tab" data-t="play">Play one</button>
<span class="mute" style="margin-left:auto">local only · no arena calls · quota untouched</span></header>
<main>
<section id="start">
 <div class="card"><div class="row" style="margin-bottom:10px">
  <label>What<select id="cmd"><option value="search">search - find the best knobs</option><option value="compare">compare - agents side by side</option><option value="stress">stress - can it break?</option></select></label>
  <label class="f-search">Minutes<input id="minutes" type="number" value="10" min="1"></label>
  <label class="f-search">Variants to start<input id="start_n" type="number" value="64"></label>
  <label class="f-compare">Agents (comma separated)<input id="agents" value="naive,calc,sellm.agent:make_agent" size="36"></label>
  <label class="f-stress">Agent<input id="agent" value="sellm.agent:make_agent" size="26"></label>
  <label>Label<input id="label" placeholder="optional"></label></div>
  <div class="grid">
   <label class="f-ts">Generated scenarios (train)<input id="invented" type="number" value="160"></label>
   <label class="f-ts">Generated scenarios (test)<input id="test" type="number" value="80"></label>
   <label class="f-stress">Generated scenarios<input id="n" type="number" value="120"></label>
   <label class="f-stress">Per edge case<input id="per_edge" type="number" value="6"></label>
   <label>Seeds per scenario<input id="seeds" type="number" value="2"></label>
   <label>Runner<select id="mode"><option value="parallel">one loop per thread</option><option value="sequential">kit play() (one at a time)</option></select></label>
   <label>Wave cap (s, 0 = none)<input id="wave_cap" type="number" value="480"></label>
   <label>Our seconds per move<input id="think" type="number" value="2" step="0.5"></label>
   <label>Suppliers played by<select id="supplier"><option value="engine">engine: calibrated rules (fast, free)</option><option value="llm">LLM inside the engine's limits (realistic, costs tokens)</option></select></label>
   <label>Engine reads e-mails by<select id="reader"><option value="keywords">keywords (free)</option><option value="llm">LLM (costs calls)</option></select></label>
   <label>Scenario seed<input id="invent_seed" type="number" value="1"></label>
   <label><span><input type="checkbox" id="no_clock"> no clock</span><span><input type="checkbox" id="fixed_twins"> fitted twins only</span></label>
  </div></div>
 <div class="card f-knobs"><div class="row"><b>Knobs</b><span class="mute">for <code>calc</code> (compare) or the stress agent; empty = defaults</span>
   <button class="sm" onclick="toggleKnobs()">edit as table</button>
   <select id="fromrun"><option value="">load from a run's best.json ...</option></select><input id="rank" type="number" value="1" min="1" style="width:60px">
   <button class="sm" onclick="loadKnobs()">load</button><button class="sm" onclick="knobs.value=''">clear</button></div>
   <div id="knobtable" class="grid" style="margin-top:10px"></div>
   <textarea id="knobs" placeholder='{"steps": 8, "structure": "joint"}' style="margin-top:8px"></textarea></div>
 <div class="row"><button class="go" onclick="startRun()">Start in the background</button><span id="startmsg" class="mute"></span></div>
</section>
<section id="runs" class="hidden"><div class="split">
 <div><div class="row" style="margin-bottom:8px"><b>Runs</b><button class="sm" onclick="refresh()">refresh</button></div><div id="runlist"></div></div>
 <div id="detail" class="card"><span class="mute">Pick a run on the left.</span></div></div></section>
<section id="play" class="hidden"><div class="card"><div class="grid">
 <label>Scenario<input id="p_scen" value="P01" list="scenlist"><datalist id="scenlist"></datalist></label>
 <label>Agent<input id="p_agent" value="sellm.agent:make_agent" list="agentlist"><datalist id="agentlist"></datalist></label>
 <label>Runner<select id="p_mode"><option value="parallel">one loop per thread</option><option value="sequential">kit play()</option></select></label>
 <label>Seed<input id="p_seed" type="number" value="0"></label>
 <label>Supplier played by<select id="p_supplier"><option value="llm">LLM (realistic, ~7 calls)</option><option value="engine">engine (free)</option></select></label></div>
 <label style="margin-top:8px">Knobs (JSON, optional)<textarea id="p_knobs"></textarea></label>
 <div class="row" style="margin-top:8px"><button class="go" onclick="playOne()">Play</button><span class="mute">Twins: P01 ... D02. Generated: X&lt;seed&gt;-&lt;n&gt;, e.g. X01-007.</span></div></div>
 <pre id="transcript" class="hidden"></pre></section>
</main>
<script>
const $=id=>document.getElementById(id);let META=null,SEL=null,TIMER=null;
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===b));
 ['start','runs','play'].forEach(t=>$(t).classList.toggle('hidden',t!==b.dataset.t));if(b.dataset.t==='runs')refresh();});
function showFields(){const c=$('cmd').value;document.querySelectorAll('.f-search').forEach(e=>e.style.display=c==='search'?'':'none');
 document.querySelectorAll('.f-compare').forEach(e=>e.style.display=c==='compare'?'':'none');
 document.querySelectorAll('.f-stress').forEach(e=>e.style.display=c==='stress'?'':'none');
 document.querySelectorAll('.f-ts').forEach(e=>e.style.display=c==='stress'?'none':'');
 document.querySelectorAll('.f-knobs').forEach(e=>e.style.display=c==='search'?'none':'');}
$('cmd').onchange=showFields;showFields();
async function j(u,o){const r=await fetch(u,o);if(!r.ok)throw new Error(await r.text());return r.headers.get('content-type')?.includes('json')?r.json():r.text();}
async function init(){META=await j('/api/meta');
 $('scenlist').innerHTML=META.twins.map(t=>`<option value="${t}">`).join('')+[...Array(10).keys()].map(i=>`<option value="X01-00${i}">`).join('');
 $('agentlist').innerHTML=META.agents.map(a=>`<option value="${a}">`).join('');
 $('knobtable').innerHTML=Object.entries(META.space).map(([k,vals])=>`<label>${k}<select data-k="${k}"><option value="">(default ${META.defaults[k]})</option>${vals.map(v=>`<option value='${JSON.stringify(v)}'>${v}</option>`).join('')}</select></label>`).join('');
 $('knobtable').querySelectorAll('select').forEach(s=>s.onchange=tableToJson);refresh();}
function toggleKnobs(){$('knobtable').classList.toggle('show');jsonToTable();}
function tableToJson(){const o={};$('knobtable').querySelectorAll('select').forEach(s=>{if(s.value!=='')o[s.dataset.k]=JSON.parse(s.value)});$('knobs').value=Object.keys(o).length?JSON.stringify(o):'';}
function jsonToTable(){let o={};try{o=JSON.parse($('knobs').value||'{}')}catch(e){}$('knobtable').querySelectorAll('select').forEach(s=>{s.value=s.dataset.k in o?JSON.stringify(o[s.dataset.k]):''});}
async function loadKnobs(){const run=$('fromrun').value;if(!run)return;const b=await j(`/api/run/${run}/best`);const e=b[Math.min(+$('rank').value,b.length)-1];$('knobs').value=JSON.stringify(e.knobs||{});jsonToTable();}
function opts(){const o={};['minutes','agents','agent','label','invented','test','n','per_edge','seeds','mode','wave_cap','think','reader','supplier','invent_seed','knobs'].forEach(k=>o[k]=$(k).value);
 o.start=$('start_n').value;o.no_clock=$('no_clock').checked;o.fixed_twins=$('fixed_twins').checked;return o;}
async function startRun(){$('startmsg').textContent='starting ...';try{const job=await j('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd:$('cmd').value,options:opts()})});
 $('startmsg').textContent=`started: ${job.args.join(' ')}`;SEL={job:job.id};document.querySelector('.tab[data-t=runs]').click();}catch(e){$('startmsg').textContent='error: '+e.message}}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
async function refresh(){const d=await j('/api/runs');const items=[];
 d.jobs.filter(x=>x.running).forEach(x=>items.push({key:'job:'+x.id,label:`${x.cmd} ${x.options.label||''}`,sub:`started ${x.started}`,running:true,job:x}));
 d.runs.forEach(r=>items.push({key:'run:'+r.name,label:r.name,sub:(r.report?'report':'')+(r.best?' · best':'')+(r.rows?' · rows':''),running:r.running,run:r}));
 $('runlist').innerHTML=items.map(i=>`<div class="item ${SEL&&(SEL.key===i.key||(SEL.job&&i.job&&i.job.id===SEL.job))?'on':''}" onclick='pick(${JSON.stringify(i.key)})'><div class="row"><b style="font-size:13px">${esc(i.label)}</b><span class="badge ${i.running?'run':'done'}">${i.running?'running':'done'}</span></div><div class="mute">${esc(i.sub)}</div></div>`).join('')||'<span class="mute">no runs yet</span>';
 $('fromrun').innerHTML='<option value="">load from a run\'s best.json ...</option>'+d.runs.filter(r=>r.best).map(r=>`<option>${r.name}</option>`).join('');
 window._items=items;if(SEL&&SEL.job){const it=items.find(i=>i.job&&i.job.id===SEL.job);if(it){SEL.key=it.key}else{const jb=d.jobs.find(x=>x.id===SEL.job);if(jb&&jb.folder)SEL.key='run:'+jb.folder.split('/').pop()}}
 if(SEL&&SEL.key)render(items.find(i=>i.key===SEL.key));clearTimeout(TIMER);if(items.some(i=>i.running))TIMER=setTimeout(refresh,3000);}
function pick(key){SEL={key};refresh();}
async function render(it){if(!it){return}const D=$('detail');
 if(it.job){D.innerHTML=`<div class="row"><b>${esc(it.label)}</b><span class="badge run">running</span><button class="sm" onclick="stopJob('${it.job.id}')">stop</button></div><p class="mute">${esc(it.job.args.join(' '))}</p><pre>${esc(it.job.tail)}</pre>`;return;}
 const r=it.run,n=encodeURIComponent(r.name);let rep='';if(r.report){const t=await j(`/api/run/${n}/report`);rep=window.marked?marked.parse(t):`<pre>${esc(t)}</pre>`;}
 D.innerHTML=`<div class="row"><b>${esc(r.name)}</b><span class="badge ${r.running?'run':'done'}">${r.running?'running':'done'}</span></div>
 <div class="row" style="margin:8px 0">${r.report?`<a class="sm" href="/api/run/${n}/export/report.md">report.md</a>`:''} ${r.best?`<a class="sm" href="/api/run/${n}/export/best.json">best.json</a>`:''}
 ${r.rows?`<a class="sm" href="/api/run/${n}/export/rows.csv">rows.csv</a>`:''} <a class="sm" href="/api/run/${n}/export/run.zip">run.zip</a>
 ${r.best?`<button class="sm" onclick="useKnobs('${r.name}',1)">use #1 knobs</button><button class="sm" onclick="extend('${r.name}')">extend this run</button><button class="sm" onclick="stressBest('${r.name}')">stress-test #1</button><button class="sm" onclick="snippet('${r.name}')">#1 as sellm/agent.py KNOBS</button>`:''}</div>
 <pre id="snip" class="hidden"></pre>${r.progress?`<details ${r.running?'open':''}><summary class="mute">progress</summary><pre>${esc(r.progress)}</pre></details>`:''}<div class="md">${rep}</div>`;}
async function stopJob(id){await j('/api/stop/'+id,{method:'POST'});setTimeout(refresh,800);}
async function useKnobs(name,rank){$('fromrun').value=name;$('rank').value=rank;await loadKnobs();$('cmd').value='compare';showFields();document.querySelector('.tab[data-t=start]').click();}
async function extend(name){const m=name.match(/-(search|compare|stress)/);const cmd=m?m[1]:'search';$('cmd').value=cmd;showFields();
 $('minutes').value=Math.max(+$('minutes').value*2,30);$('seeds').value=+$('seeds').value+1;$('invented').value=+$('invented').value+160;$('test').value=+$('test').value+80;$('label').value='extended';
 if(cmd!=='search'){$('fromrun').value=name;await loadKnobs();}document.querySelector('.tab[data-t=start]').click();$('startmsg').textContent='more minutes, seeds and scenarios filled in: check and start';}
async function stressBest(name){$('cmd').value='stress';showFields();$('agent').value='calc';$('fromrun').value=name;$('rank').value=1;await loadKnobs();await startRun();}
async function snippet(name){const t=await j(`/api/run/${encodeURIComponent(name)}/snippet?rank=1`);const s=$('snip');s.textContent=t;s.classList.remove('hidden');}
async function playOne(){const T=$('transcript');T.classList.remove('hidden');T.textContent='playing ...';
 T.textContent=await j('/api/play',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario:$('p_scen').value,agent:$('p_agent').value,knobs:$('p_knobs').value,mode:$('p_mode').value,seed:$('p_seed').value,supplier:$('p_supplier').value})});}
init();
</script></body></html>
"""
