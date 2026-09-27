"""Single-file interactive HTML report for a backtest run: actual-vs-model
scatter grids (Plotly) plus sortable/filterable mismatch tables, covering the
region/trader/interconnector comparisons from a backtest run — viewable
standalone in a browser without touching the CSV artefacts.
"""

import html as html_lib
import os
import string
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"

GOOD = "#0ca30c"
CRITICAL = "#d03b3b"
MUTED_GRID = "rgba(137, 135, 129, 0.35)"
MUTED_TEXT = "#75736c"
SURFACE_RING = "rgba(255, 255, 255, 0.7)"

REGION_FIELDS = [
    "@EnergyPrice",
    "@FixedDemand",
    "@NetExport",
    "@SurplusGeneration",
    "@R1Dispatch",
    "@R6Dispatch",
    "@R60Dispatch",
    "@R5Dispatch",
    "@R5RegDispatch",
    "@L1Dispatch",
    "@L6Dispatch",
    "@L60Dispatch",
    "@L5Dispatch",
    "@L5RegDispatch",
]

TRADER_FIELDS = [
    "@EnergyTarget",
    "@R5RegTarget",
    "@L5RegTarget",
    "@R5Target",
    "@L5Target",
    "@R60Target",
    "@L60Target",
    "@R6Target",
    "@L6Target",
    "@R1Target",
    "@L1Target",
]

INTERCONNECTOR_FIELDS = ["@Flow", "@Losses", "@Deficit"]


def resolve_git_sha() -> str:
    """Sha to stamp in a report's footer, for every caller that builds one.

    Prefers NEMDE_GIT_SHA, which the Docker build bakes in because the image
    carries no .git; otherwise asks git, which is how a checkout answers. Both
    can come up empty -- an unstamped report beats a failed run -- and the
    footer renders "unknown" when they do. Deliberately not GitPython: that
    shells out to the git binary on import, so merely importing it fails in a
    container that has no git.
    """

    sha = os.environ.get("NEMDE_GIT_SHA", "")
    if sha:
        return sha
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return completed.stdout.strip()


def _status_legend_traces() -> list:
    return [
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(
                size=8, color=GOOD, symbol="circle", line=dict(width=0.5, color=SURFACE_RING)
            ),
            name="within tolerance",
            legendgroup="status",
            showlegend=True,
        ),
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(
                size=8, color=CRITICAL, symbol="x", line=dict(width=0.5, color=SURFACE_RING)
            ),
            name="mismatch",
            legendgroup="status",
            showlegend=True,
        ),
    ]


def _scatter_grid_html(
    comparison: pd.DataFrame,
    fields: list,
    id_col: str,
    tolerance: float,
    div_id: str,
    ncols: int,
) -> str:
    nrows = -(-len(fields) // ncols)
    fig = make_subplots(
        rows=nrows,
        cols=ncols,
        subplot_titles=[f.lstrip("@") for f in fields],
        vertical_spacing=min(0.5 / nrows, 0.12),
        horizontal_spacing=0.05,
    )

    for trace in _status_legend_traces():
        fig.add_trace(trace, row=1, col=1)

    for i, field in enumerate(fields):
        row, col = divmod(i, ncols)
        row, col = row + 1, col + 1

        df = comparison.loc[comparison["name"].eq(field)].dropna(subset=["actual", "estimated"])
        if df.empty:
            continue

        within = df["actual_minus_estimated"].abs() <= tolerance
        colors = np.where(within, GOOD, CRITICAL)
        symbols = np.where(within, "circle", "x")
        hover = (
            id_col.replace("_", " ")
            + "="
            + df[id_col].astype(str)
            + "<br>intervention="
            + df["intervention"].astype(str)
            + "<br>actual="
            + df["actual"].round(3).astype(str)
            + "<br>estimated="
            + df["estimated"].round(3).astype(str)
            + "<br>diff="
            + df["actual_minus_estimated"].round(3).astype(str)
        )

        lo = float(min(df["actual"].min(), df["estimated"].min()))
        hi = float(max(df["actual"].max(), df["estimated"].max()))
        pad = (hi - lo) * 0.05 or 1.0

        fig.add_trace(
            go.Scatter(
                x=[lo - pad, hi + pad],
                y=[lo - pad, hi + pad],
                mode="lines",
                line=dict(color=MUTED_GRID, dash="dash", width=1),
                hoverinfo="skip",
                showlegend=False,
            ),
            row=row,
            col=col,
        )
        fig.add_trace(
            go.Scatter(
                x=df["actual"],
                y=df["estimated"],
                mode="markers",
                marker=dict(
                    size=7,
                    color=colors,
                    symbol=symbols,
                    opacity=0.85,
                    line=dict(width=0.5, color=SURFACE_RING),
                ),
                text=hover,
                hoverinfo="text",
                legendgroup="status",
                showlegend=False,
            ),
            row=row,
            col=col,
        )

    fig.update_layout(
        height=max(290 * nrows, 290),
        margin=dict(t=50, l=55, r=20, b=55),
        font=dict(
            size=11, color=MUTED_TEXT, family="system-ui, -apple-system, 'Segoe UI', sans-serif"
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_xaxes(
        title_text="actual",
        title_font=dict(size=10, color=MUTED_TEXT),
        title_standoff=8,
        automargin=True,
        showgrid=True,
        gridcolor=MUTED_GRID,
        zeroline=False,
    )
    fig.update_yaxes(
        title_text="model estimate",
        title_font=dict(size=10, color=MUTED_TEXT),
        title_standoff=8,
        automargin=True,
        showgrid=True,
        gridcolor=MUTED_GRID,
        zeroline=False,
    )

    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        div_id=div_id,
        config={"responsive": True, "displaylogo": False},
    )


def _mismatch_table_html(
    comparison: pd.DataFrame, id_col: str, tolerance: float, table_id: str
) -> str:
    df = (
        comparison.dropna(subset=["actual_minus_estimated"])
        .assign(
            trade_type=lambda d: d["name"].str.lstrip("@"),
            abs_diff=lambda d: d["actual_minus_estimated"].abs(),
        )
        .sort_values("abs_diff", ascending=False)
    )

    n_mismatch = int((df["abs_diff"] > tolerance).sum())

    rows = []
    for r in df.itertuples(index=False):
        status = "mismatch" if r.abs_diff > tolerance else "ok"
        entity = html_lib.escape(str(getattr(r, id_col)))
        intervention = html_lib.escape(str(r.intervention))
        trade_type = html_lib.escape(r.trade_type)
        rows.append(
            f'<tr class="row-{status}">'
            f"<td>{entity}</td><td>{intervention}</td><td>{trade_type}</td>"
            f'<td class="num">{r.actual:.3f}</td><td class="num">{r.estimated:.3f}</td>'
            f'<td class="num">{r.actual_minus_estimated:.3f}</td>'
            f'<td><span class="status-chip status-{status}">{"MISMATCH" if status == "mismatch" else "OK"}</span></td>'
            f"</tr>"
        )

    id_label = html_lib.escape(id_col.replace("_", " "))
    return f"""
<div class="table-card">
  <div class="table-toolbar">
    <input type="search" class="filter-input" data-target="{table_id}" placeholder="Filter {id_label} / trade type…">
    <span class="muted">{n_mismatch} of {len(df)} rows exceed tolerance ({tolerance:g})</span>
  </div>
  <div class="table-scroll">
    <table id="{table_id}" class="sortable">
      <thead><tr>
        <th data-sort="string">{id_label}</th>
        <th data-sort="string">intervention</th>
        <th data-sort="string">trade type</th>
        <th data-sort="number" class="num">actual</th>
        <th data-sort="number" class="num">estimated</th>
        <th data-sort="number" class="num">diff</th>
        <th data-sort="string">status</th>
      </tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </div>
</div>
"""


def _model_only_table_html(model_only: pd.DataFrame, id_col: str, table_id: str) -> str:
    """Table for fields the model estimates but NEMDE's own solution never
    publishes (@DispatchedGeneration, @DispatchedLoad, @ClearedDemand for
    regions) -- there is no "actual" to plot or diff against, so these get a
    plain estimate-only listing instead of a spot in the scatter grid.
    """

    df = model_only.assign(trade_type=lambda d: d["name"].str.lstrip("@")).sort_values(
        [id_col, "intervention", "trade_type"]
    )

    rows = [
        f"<tr><td>{html_lib.escape(str(getattr(r, id_col)))}</td>"
        f"<td>{html_lib.escape(str(r.intervention))}</td>"
        f"<td>{html_lib.escape(r.trade_type)}</td>"
        f'<td class="num">{r.estimated:.3f}</td></tr>'
        for r in df.itertuples(index=False)
    ]

    id_label = html_lib.escape(id_col.replace("_", " "))
    return f"""
<div class="table-card">
  <div class="table-toolbar">
    <span class="muted">not published by NEMDE -- model estimate only, no actual to compare against</span>
  </div>
  <div class="table-scroll">
    <table id="{table_id}" class="sortable">
      <thead><tr>
        <th data-sort="string">{id_label}</th>
        <th data-sort="string">intervention</th>
        <th data-sort="string">trade type</th>
        <th data-sort="number" class="num">estimated</th>
      </tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </div>
</div>
"""


def _status_pill(label: str, ok: bool, detail: str) -> str:
    cls = "ok" if ok else "fail"
    icon = "✓" if ok else "✗"
    return (
        f'<div class="pill-card pill-{cls}"><span class="pill-icon">{icon}</span>'
        f'<div><div class="pill-label">{html_lib.escape(label)}</div>'
        f'<div class="pill-detail">{html_lib.escape(detail)}</div></div></div>'
    )


REPORT_CSS = """
:root {
  --surface: #fcfcfb;
  --page: #f9f9f7;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --text-muted: #898781;
  --grid: #e1e0d9;
  --border: rgba(11,11,11,0.10);
  --good: #0ca30c;
  --critical: #d03b3b;
  --good-bg: rgba(12,163,12,0.08);
  --critical-bg: rgba(208,59,59,0.08);
  --warn: #9a6b00;
  --warn-bg: rgba(154,107,0,0.08);
  --warn-border: rgba(154,107,0,0.25);
}
@media (prefers-color-scheme: dark) {
  :root {
    --surface: #1a1a19;
    --page: #0d0d0d;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted: #898781;
    --grid: #2c2c2a;
    --border: rgba(255,255,255,0.10);
    --critical: #e66767;
    --good-bg: rgba(12,163,12,0.14);
    --critical-bg: rgba(230,103,103,0.14);
    --warn: #e0b84d;
    --warn-bg: rgba(224,184,77,0.10);
    --warn-border: rgba(224,184,77,0.28);
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--text-primary); font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
.page { max-width: 1400px; margin: 0 auto; padding: 24px 20px 60px; }
h1 { font-size: 20px; margin: 0 0 4px; }
.meta { color: var(--text-secondary); font-size: 13px; margin-bottom: 14px; }
.meta code { background: var(--surface); border: 1px solid var(--border); border-radius: 4px; padding: 1px 5px; }
.disclaimer-banner { background: var(--warn-bg); border: 1px solid var(--warn-border); border-radius: 10px; padding: 10px 14px; font-size: 12.5px; line-height: 1.5; color: var(--text-primary); margin: 4px 0 14px; }
.disclaimer-banner strong { color: var(--warn); }
.pill-row { display: flex; flex-wrap: wrap; gap: 10px; margin: 14px 0 4px; }
.pill-card { display: flex; align-items: center; gap: 8px; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 8px 12px; min-width: 190px; }
.pill-icon { font-size: 16px; }
.pill-ok .pill-icon { color: var(--good); }
.pill-fail .pill-icon { color: var(--critical); }
.pill-label { font-size: 12px; font-weight: 600; }
.pill-detail { font-size: 11px; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
.entity-section { margin-top: 32px; }
.entity-section h2 { font-size: 15px; margin: 0 0 10px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
.plot-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 6px; margin-bottom: 14px; }
.table-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 12px; }
.table-toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }
.filter-input { flex: 0 0 260px; padding: 6px 10px; border-radius: 6px; border: 1px solid var(--border); background: var(--page); color: var(--text-primary); font-size: 12px; }
.muted { color: var(--text-muted); font-size: 12px; }
.table-scroll { overflow-x: auto; max-height: 420px; overflow-y: auto; }
table { border-collapse: collapse; width: 100%; font-size: 12px; }
.obj-table { width: auto; }
.obj-note { font-size: 12px; color: var(--text-secondary); max-width: 760px; margin: 0 0 10px; }
thead th { position: sticky; top: 0; background: var(--surface); text-align: left; padding: 6px 8px; color: var(--text-secondary); font-weight: 600; cursor: pointer; user-select: none; border-bottom: 1px solid var(--border); white-space: nowrap; }
thead th.num, td.num { text-align: right; font-variant-numeric: tabular-nums; }
thead th::after { content: ""; margin-left: 4px; opacity: 0.4; }
thead th[data-dir="asc"]::after { content: "\\25B2"; opacity: 1; }
thead th[data-dir="desc"]::after { content: "\\25BC"; opacity: 1; }
tbody td { padding: 5px 8px; border-bottom: 1px solid var(--grid); }
tr.row-mismatch { background: var(--critical-bg); }
.status-chip { font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; }
.status-ok { background: var(--good-bg); color: var(--good); }
.status-mismatch { background: var(--critical-bg); color: var(--critical); }
"""

REPORT_JS = """
document.querySelectorAll('table.sortable').forEach(function (table) {
  var tbody = table.querySelector('tbody');
  table.querySelectorAll('thead th').forEach(function (th, idx) {
    th.addEventListener('click', function () {
      var dir = th.getAttribute('data-dir') === 'asc' ? 'desc' : 'asc';
      table.querySelectorAll('thead th').forEach(function (h) { h.removeAttribute('data-dir'); });
      th.setAttribute('data-dir', dir);
      var type = th.getAttribute('data-sort');
      var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
      rows.sort(function (a, b) {
        var av = a.children[idx].textContent.trim();
        var bv = b.children[idx].textContent.trim();
        if (type === 'number') {
          av = parseFloat(av) || 0;
          bv = parseFloat(bv) || 0;
        }
        if (av < bv) return dir === 'asc' ? -1 : 1;
        if (av > bv) return dir === 'asc' ? 1 : -1;
        return 0;
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
    });
  });
});

document.querySelectorAll('.filter-input').forEach(function (input) {
  input.addEventListener('input', function () {
    var table = document.getElementById(input.getAttribute('data-target'));
    var q = input.value.toLowerCase();
    table.querySelectorAll('tbody tr').forEach(function (row) {
      row.style.display = row.textContent.toLowerCase().indexOf(q) === -1 ? 'none' : '';
    });
  });
});
"""

_PAGE_TEMPLATE = string.Template("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>NEMDE backtest report — $casefile_id</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%232f6feb'%3E%3Cpath d='M13 2 3 14h7l-1 8 10-12h-7l1-8z'/%3E%3C/svg%3E">
<script src="$plotly_cdn"></script>
<style>$css</style>
</head>
<body>
<div class="page">
  <header>
    <h1>NEMDE backtest report</h1>
    <div class="meta">casefile <code>$casefile_id</code> &middot; run <code>$run_id</code> &middot; git <code>$git_sha</code> &middot; generated $timestamp</div>
    <div class="disclaimer-banner"><strong>Approximation, not AEMO's model.</strong> This is a reverse-engineered
      reconstruction of NEMDE built from publicly available documentation, not AEMO's own source. It will not match
      NEMDE exactly, and known gaps are open and unresolved (see the objective-value note below). Provided as-is,
      with absolutely no warranty.</div>
    <div class="pill-row">$pills</div>
  </header>

  <section class="entity-section">
    <h2>Objective value</h2>
    <div class="obj-note">Objective-value mismatches on recent casefiles are a known, open gap under
      investigation, not necessarily a sign that this solution is wrong — the cause hasn't been
      pinned down yet (candidates include a fixed offset in the model or an artefact of the solver /
      variable initialisation). It is far less pronounced on older casefiles. Use the region, trader
      and interconnector comparisons below to judge solution quality instead of this number.</div>
    <div class="table-card">
      <table class="obj-table">
        <thead><tr><th>actual</th><th>estimated</th><th>rel diff</th></tr></thead>
        <tbody><tr><td class="num">$actual_obj</td><td class="num">$estimated_obj</td><td class="num">$obj_rel_diff</td></tr></tbody>
      </table>
    </div>
  </section>

  <section class="entity-section">
    <h2>Region solution</h2>
    <div class="plot-card">$region_plot</div>
    $region_table
    $region_model_only_table
  </section>

  <section class="entity-section">
    <h2>Trader solution</h2>
    <div class="plot-card">$trader_plot</div>
    $trader_table
  </section>

  <section class="entity-section">
    <h2>Interconnector solution</h2>
    <div class="plot-card">$interconnector_plot</div>
    $interconnector_table
  </section>
</div>
<script>$js</script>
</body>
</html>
""")


def build_html_report(
    *,
    result: dict,
    run_id: str,
    git_sha: str,
    tolerance: float,
    obj_rel_tolerance: float,
    energy_price_tolerance: float,
    region_comparison: pd.DataFrame,
    region_model_only: pd.DataFrame,
    trader_comparison: pd.DataFrame,
    interconnector_comparison: pd.DataFrame,
) -> str:
    region_plot = _scatter_grid_html(
        region_comparison, REGION_FIELDS, "region_id", tolerance, "region-plot", ncols=4
    )
    trader_plot = _scatter_grid_html(
        trader_comparison, TRADER_FIELDS, "trader_id", tolerance, "trader-plot", ncols=3
    )
    interconnector_plot = _scatter_grid_html(
        interconnector_comparison,
        INTERCONNECTOR_FIELDS,
        "interconnector_id",
        tolerance,
        "interconnector-plot",
        ncols=2,
    )

    region_table = _mismatch_table_html(region_comparison, "region_id", tolerance, "region-table")
    region_model_only_table = _model_only_table_html(
        region_model_only, "region_id", "region-model-only-table"
    )
    trader_table = _mismatch_table_html(trader_comparison, "trader_id", tolerance, "trader-table")
    interconnector_table = _mismatch_table_html(
        interconnector_comparison, "interconnector_id", tolerance, "interconnector-table"
    )

    pills = "".join(
        [
            _status_pill(
                "Region",
                result["region"],
                f"max err {result['region_max_err']:.4f} MW (tol {tolerance:g})",
            ),
            _status_pill(
                "Energy price",
                result["energy_price"],
                f"max err {result['energy_price_max_err']:.4f} $/MWh (tol {energy_price_tolerance:g})",
            ),
            _status_pill(
                "Trader",
                result["trader"],
                f"max err {result['trader_max_err']:.4f} MW (tol {tolerance:g})",
            ),
            _status_pill(
                "Interconnector",
                result["interconnect"],
                f"max err {result['interconnect_max_err']:.4f} MW (tol {tolerance:g})",
            ),
            _status_pill(
                "Objective",
                result["objective"],
                f"rel diff {result['obj_rel_diff']:.2%} (tol {obj_rel_tolerance:.0%})",
            ),
        ]
    )

    return _PAGE_TEMPLATE.substitute(
        casefile_id=html_lib.escape(str(result["casefile_id"])),
        run_id=html_lib.escape(run_id),
        git_sha=html_lib.escape(git_sha[:12]) or "unknown",
        timestamp=pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        pills=pills,
        plotly_cdn=PLOTLY_CDN,
        css=REPORT_CSS,
        js=REPORT_JS,
        actual_obj=f"{result['actual_obj']:.3f}",
        estimated_obj=f"{result['estimated_obj']:.3f}",
        obj_rel_diff=f"{result['obj_rel_diff']:.2%}",
        region_plot=region_plot,
        region_table=region_table,
        region_model_only_table=region_model_only_table,
        trader_plot=trader_plot,
        trader_table=trader_table,
        interconnector_plot=interconnector_plot,
        interconnector_table=interconnector_table,
    )
