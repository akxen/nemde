"""FastAPI app for local/Docker use."""

from xml.parsers.expat import ExpatError

from fastapi import FastAPI, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool
from ulid import ULID

from nemde.backtest import run_backtest
from nemde.casefile_io import normalize_casefile
from nemde.report import resolve_git_sha
from nemde.service import solve
from nemde.solution_report import build_solution_report, solution_context

app = FastAPI(title="NEMDE dispatch model")

GIT_SHA = resolve_git_sha()

UPLOAD_PAGE = """<!doctype html>
<title>NEMDE dispatch model</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%232f6feb'%3E%3Cpath d='M13 2 3 14h7l-1 8 10-12h-7l1-8z'/%3E%3C/svg%3E">
<style>
  :root {
    color-scheme: light dark;
    --bg: #f4f5f7;
    --surface: #ffffff;
    --border: #e2e4e9;
    --text: #16181d;
    --muted: #6b7280;
    --accent: #2f6feb;
    --accent-contrast: #ffffff;
    --drop-bg: #fafbfc;
    --shadow: 0 1px 2px rgba(16, 24, 40, 0.04), 0 8px 24px rgba(16, 24, 40, 0.06);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0e1015;
      --surface: #161923;
      --border: #2a2e3a;
      --text: #e7e9ee;
      --muted: #9aa1b0;
      --accent: #5b8dfa;
      --accent-contrast: #0e1015;
      --drop-bg: #12141c;
      --shadow: 0 1px 2px rgba(0, 0, 0, 0.3), 0 12px 32px rgba(0, 0, 0, 0.35);
    }
  }
  * { box-sizing: border-box; }
  body {
    font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    margin: 0;
    padding: 3rem 1rem;
    display: flex;
    justify-content: center;
  }
  .card {
    width: 100%;
    max-width: 34rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    box-shadow: var(--shadow);
    padding: 2rem 2.25rem 2.25rem;
  }
  .kicker {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--accent);
    margin: 0 0 0.6rem;
  }
  .kicker::before {
    content: "";
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent);
  }
  h1 { font-size: 1.5rem; margin: 0 0 0.35rem; letter-spacing: -0.01em; }
  .lede { color: var(--muted); margin: 0 0 1.75rem; }
  .disclaimer {
    background: var(--drop-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.7rem 0.85rem;
    font-size: 12.5px;
    line-height: 1.5;
    color: var(--muted);
    margin: 0 0 1.5rem;
  }
  .disclaimer strong { color: var(--text); }

  .dropzone {
    display: block;
    border: 1.5px dashed var(--border);
    border-radius: 12px;
    background: var(--drop-bg);
    padding: 1.75rem 1rem;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.15s ease, background 0.15s ease;
  }
  .dropzone:hover, .dropzone.drag { border-color: var(--accent); }
  .dropzone input[type="file"] { display: none; }
  .dropzone .icon { font-size: 1.6rem; margin-bottom: 0.4rem; }
  .dropzone .primary { font-weight: 500; }
  .dropzone .primary em { color: var(--accent); font-style: normal; }
  .dropzone .hint { color: var(--muted); font-size: 13px; margin-top: 0.2rem; }
  .filename {
    margin-top: 0.6rem;
    font-size: 13px;
    color: var(--text);
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    word-break: break-all;
  }

  fieldset {
    border: 1px solid var(--border);
    border-radius: 10px;
    margin: 1.5rem 0 0;
    padding: 0.9rem 1rem 1rem;
  }
  legend {
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    color: var(--muted);
    padding: 0 0.35rem;
  }
  label.mode {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    padding: 0.4rem 0.25rem;
    border-radius: 8px;
    cursor: pointer;
  }
  label.mode:hover { background: var(--drop-bg); }
  label.mode input { margin-top: 0.2rem; accent-color: var(--accent); }
  label.mode .title { font-weight: 500; }
  label.mode span.desc { color: var(--muted); font-size: 13px; display: block; }

  button#go {
    width: 100%;
    margin-top: 1.5rem;
    padding: 0.75rem 1rem;
    border: none;
    border-radius: 10px;
    background: var(--accent);
    color: var(--accent-contrast);
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s ease, transform 0.05s ease;
  }
  button#go:hover { opacity: 0.92; }
  button#go:active { transform: scale(0.99); }
  button#go:disabled { opacity: 0.55; cursor: not-allowed; }

  #status {
    margin-top: 1rem;
    color: var(--muted);
    font-size: 13.5px;
    min-height: 1.2em;
  }
  #status.error { color: #d1453b; }
  .spinner {
    display: inline-block;
    width: 12px;
    height: 12px;
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;
    margin-right: 0.4rem;
    vertical-align: -1px;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
<div class="card">
  <p class="kicker">NEMDE dispatch model</p>
  <h1>Run a casefile</h1>
  <p class="lede">Upload a casefile, solve it, and view the result as an HTML report.</p>

  <p class="disclaimer"><strong>Approximation, not AEMO's model.</strong> This is a
    reverse-engineered reconstruction of NEMDE built from publicly available documentation, not
    AEMO's own source code. It will not match NEMDE exactly. Provided as-is, with absolutely no
    warranty.</p>

  <label class="dropzone" id="dropzone" for="file">
    <div class="icon">&#128193;</div>
    <div class="primary">Drop a casefile here or <em>browse</em></div>
    <div class="hint">.loaded, .xml, or .json</div>
    <div class="filename" id="filename"></div>
    <input type="file" id="file" accept=".loaded,.xml,.json">
  </label>

  <fieldset>
    <legend>What to produce</legend>
    <label class="mode">
      <input type="radio" name="mode" value="solve" checked>
      <span><span class="title">Dispatch solution</span>
        <span class="desc">Targets, prices and flows from this casefile alone.</span></span>
    </label>
    <label class="mode">
      <input type="radio" name="mode" value="backtest">
      <span><span class="title">Backtest</span>
        <span class="desc">Also compare against the NEMDE solution carried in the casefile.</span></span>
    </label>
  </fieldset>

  <button id="go">Run</button>
  <div id="status"></div>
</div>
<script>
  const status = document.getElementById("status");
  const fileInput = document.getElementById("file");
  const dropzone = document.getElementById("dropzone");
  const filename = document.getElementById("filename");
  const goButton = document.getElementById("go");

  function setStatus(text, isError) {
    status.textContent = text;
    status.classList.toggle("error", !!isError);
  }

  function showFile() {
    const file = fileInput.files[0];
    filename.textContent = file ? file.name : "";
  }
  fileInput.addEventListener("change", showFile);

  ["dragenter", "dragover"].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.add("drag"); })
  );
  ["dragleave", "drop"].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.remove("drag"); })
  );
  dropzone.addEventListener("drop", (e) => {
    const dropped = e.dataTransfer.files;
    if (dropped.length) { fileInput.files = dropped; showFile(); }
  });

  goButton.onclick = async () => {
    const file = fileInput.files[0];
    if (!file) { setStatus("Choose a casefile first.", true); return; }
    const mode = document.querySelector("input[name=mode]:checked").value;
    goButton.disabled = true;
    setStatus("");
    status.innerHTML = '<span class="spinner"></span>Solving \u2014 this takes about a minute for a full casefile...';
    const type = file.name.endsWith(".json") ? "application/json" : "application/xml";
    let res;
    try {
      res = await fetch("/" + mode, {
        method: "POST",
        headers: { "Content-Type": type, "Accept": "text/html" },
        body: file,
      });
    } catch (err) {
      goButton.disabled = false;
      setStatus("Failed: " + err, true);
      return;
    }
    if (!res.ok) {
      goButton.disabled = false;
      setStatus("Failed: " + (await res.text()), true);
      return;
    }
    const html = await res.text();
    document.open(); document.write(html); document.close();
  };
</script>
"""


async def _read_casefile(request: Request):
    """Pull the casefile off the request body in whichever shape it arrived."""

    content_type = request.headers.get("content-type", "")
    if "xml" in content_type:
        return await request.body()
    if "json" in content_type:
        return await request.json()
    raise HTTPException(415, "Content-Type must be application/xml or application/json")


@app.get("/", response_class=Response)
async def index():
    return Response(content=UPLOAD_PAGE, media_type="text/html")


@app.post("/solve")
async def solve_case(request: Request):
    """Solve the casefile and return the solution.

    Returns the standalone HTML solution report for `Accept: text/html`,
    otherwise the solution as JSON. Nothing here reads NemSpdOutputs, so an
    edited casefile is solved and reported on its own terms.
    """

    try:
        data = normalize_casefile(await _read_casefile(request))
    except ExpatError as exc:
        raise HTTPException(400, f"Casefile is not well-formed XML: {exc}") from exc
    except TypeError as exc:
        raise HTTPException(422, str(exc)) from exc

    # Offload the long-running, CPU-bound solve so it doesn't block the event loop.
    solution = await run_in_threadpool(solve, data)

    if "text/html" in request.headers.get("accept", ""):
        report = build_solution_report(
            solution=solution,
            context=solution_context(data),
            run_id=str(ULID()),
            git_sha=GIT_SHA,
        )
        return Response(content=report, media_type="text/html")
    return solution


@app.post("/backtest")
async def backtest_case(
    request: Request,
    tolerance: float = 0.1,
    obj_tolerance: float = 0.05,
    energy_price_tolerance: float = 1.0,
):
    """Solve the casefile and compare it against the NEMDE solution it carries.

    Returns the HTML report for `Accept: text/html`, otherwise the run summary
    as JSON.
    """

    try:
        data = normalize_casefile(await _read_casefile(request))
    except ExpatError as exc:
        raise HTTPException(400, f"Casefile is not well-formed XML: {exc}") from exc
    except TypeError as exc:
        raise HTTPException(422, str(exc)) from exc

    # A casefile submitted for dispatch need not carry NemSpdOutputs; without it
    # there is nothing to compare against, and the gates would fail deep inside
    # the comparison on a KeyError rather than at the edge.
    if "NemSpdOutputs" not in data.get("NEMSPDCaseFile", {}):
        raise HTTPException(
            422, "Casefile has no NemSpdOutputs section, so it carries no NEMDE solution."
        )

    backtest = await run_in_threadpool(
        run_backtest,
        casefile=data,
        git_sha=GIT_SHA,
        tolerance=tolerance,
        obj_rel_tolerance=obj_tolerance,
        energy_price_tolerance=energy_price_tolerance,
    )

    if "text/html" in request.headers.get("accept", ""):
        return Response(content=backtest.html_report, media_type="text/html")
    return backtest.summary
