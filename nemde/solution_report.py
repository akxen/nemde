"""Single-file interactive HTML view of one model solution: dispatch targets,
regional prices and interconnector flows, with no NEMDE comparison anywhere.

`report.py` answers "does the model agree with NEMDE?". This answers "what did
the model just do?" -- the question that remains once the casefile has been
edited and NEMDE's published solution no longer describes the same problem.
Same visual language (it borrows report.py's stylesheet), same standalone-HTML
shape, different question.
"""

import html as html_lib
import string
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from nemde.backtest import run_artefact_dir
from nemde.report import MUTED_GRID, MUTED_TEXT, PLOTLY_CDN, REPORT_CSS

# Categorical slots 1 and 2 of the reference palette, in their light-mode steps:
# readable on both the light and the dark report surface, which a Plotly figure
# needs because its colours are baked into the figure JSON rather than themed by
# CSS. SERIES_1 also carries the "forward" pole of the interconnector flow chart
# and SERIES_2 the "reverse" pole -- a warm/cool pair, deliberately not the
# red/green status colours, which mean pass/fail elsewhere in these reports.
SERIES_1 = "#2a78d6"
SERIES_2 = "#eb6834"

GOOD = "#0ca30c"
CRITICAL = "#d03b3b"

# Trade types in the order they appear on a trader/region row: raise services
# first, then lower, each from the shortest response window to the slowest.
FCAS_TRADER_FIELDS = [
    ("R1", "@R1Target"),
    ("R6", "@R6Target"),
    ("R60", "@R60Target"),
    ("R5", "@R5Target"),
    ("R5Reg", "@R5RegTarget"),
    ("L1", "@L1Target"),
    ("L6", "@L6Target"),
    ("L60", "@L60Target"),
    ("L5", "@L5Target"),
    ("L5Reg", "@L5RegTarget"),
]

FCAS_REGION_FIELDS = [
    ("R1", "@R1Dispatch"),
    ("R6", "@R6Dispatch"),
    ("R60", "@R60Dispatch"),
    ("R5", "@R5Dispatch"),
    ("R5Reg", "@R5RegDispatch"),
    ("L1", "@L1Dispatch"),
    ("L6", "@L6Dispatch"),
    ("L60", "@L60Dispatch"),
    ("L5", "@L5Dispatch"),
    ("L5Reg", "@L5RegDispatch"),
]

TRADER_VIOLATION_FIELDS = [
    "@R6Violation",
    "@R60Violation",
    "@R5Violation",
    "@R5RegViolation",
    "@L6Violation",
    "@L60Violation",
    "@L5Violation",
    "@L5RegViolation",
]

# Rendered as the violation pill row. Every one of these is zero in a clean
# solve, so a non-zero value is the first thing worth seeing on the page.
PERIOD_VIOLATION_FIELDS = [
    ("Interconnector", "@TotalInterconnectorViolation"),
    ("Generic constraint", "@TotalGenericViolation"),
    ("Ramp rate", "@TotalRampRateViolation"),
    ("Unit MW capacity", "@TotalUnitMWCapacityViolation"),
    ("Fast start", "@TotalFastStartViolation"),
    ("MNSP ramp rate", "@TotalMNSPRampRateViolation"),
    ("MNSP offer", "@TotalMNSPOfferViolation"),
    ("MNSP capacity", "@TotalMNSPCapacityViolation"),
    ("UIGF", "@TotalUIGFViolation"),
]


def solution_context(casefile: dict) -> dict:
    """Labels for the solution's traders and interconnectors, read off the
    casefile that produced it.

    The solution dict carries ids and numbers only, so region, trader type,
    initial MW and interconnector orientation have to come from the inputs. All
    of it is presentation -- the report renders without a context -- so optional
    attributes are read with .get() rather than the strict indexing model.py
    requires of the case dict.
    """

    inputs = casefile["NEMSPDCaseFile"]["NemSpdInputs"]
    period = inputs["PeriodCollection"]["Period"]

    trader_types = {
        i["@TraderID"]: i.get("@TraderType", "") for i in inputs["TraderCollection"]["Trader"]
    }
    initial_mw = {
        i["@TraderID"]: {
            j["@InitialConditionID"]: j["@Value"]
            for j in i["TraderInitialConditionCollection"]["TraderInitialCondition"]
        }.get("InitialMW")
        for i in inputs["TraderCollection"]["Trader"]
    }

    traders = {
        i["@TraderID"]: {
            "region_id": i.get("@RegionID", ""),
            "trader_type": trader_types.get(i["@TraderID"], ""),
            "initial_mw": _to_float(initial_mw.get(i["@TraderID"])),
        }
        for i in period["TraderPeriodCollection"]["TraderPeriod"]
    }

    interconnectors = {
        i["@InterconnectorID"]: {
            "from_region": i.get("@FromRegion", ""),
            "to_region": i.get("@ToRegion", ""),
            "lower_limit": _to_float(i.get("@LowerLimit")),
            "upper_limit": _to_float(i.get("@UpperLimit")),
            "mnsp": i.get("@MNSP", "0") == "1",
        }
        for i in period["InterconnectorPeriodCollection"]["InterconnectorPeriod"]
    }

    return {
        "case_id": inputs["Case"]["@CaseID"],
        "period_id": period.get("@PeriodID", ""),
        "traders": traders,
        "interconnectors": interconnectors,
    }


def _to_float(value) -> float | None:
    if value is None:
        return None
    return float(value)


def _fmt(value, dp: int = 3) -> str:
    """A number as it appears in a cell: grouped thousands, fixed decimals."""

    if value is None or value == "":
        return "—"
    if isinstance(value, str):
        return html_lib.escape(value)
    return f"{value:,.{dp}f}"


def _num_cell(value, dp: int = 3, cls: str = "") -> str:
    """A right-aligned numeric cell. The raw value rides along in data-value so
    the sort comparator never has to unpick the grouped thousands separators."""

    classes = " ".join(filter(None, ["num", cls]))
    if value is None:
        return f'<td class="{classes}" data-value="">—</td>'
    return f'<td class="{classes}" data-value="{value!r}">{_fmt(value, dp)}</td>'


def _text_cell(value: str, cls: str = "") -> str:
    attr = f' class="{cls}"' if cls else ""
    return f"<td{attr}>{html_lib.escape(str(value))}</td>"


def numeric_class(kind: str) -> str:
    return ' class="num"' if kind == "number" else ""


def _header_row(columns: list[tuple[str, str]]) -> str:
    """columns: (label, kind) where kind is "text" or "number"."""

    cells = "".join(
        f'<th data-sort="{kind}"{numeric_class(kind)}>{html_lib.escape(label)}</th>'
        for label, kind in columns
    )
    return f"<thead><tr>{cells}</tr></thead>"


def _table_card(
    *, title: str, table_id: str, columns: list[tuple[str, str]], rows: list[str], toolbar: str = ""
) -> str:
    return f"""
<div class="table-card">
  <div class="table-toolbar">{toolbar}
    <span class="muted row-count">{len(rows)} rows</span>
  </div>
  <div class="table-scroll">
    <table id="{table_id}" class="sortable" aria-label="{html_lib.escape(title)}">
      {_header_row(columns)}
      <tbody>{"".join(rows)}</tbody>
    </table>
  </div>
</div>
"""


def _stat_tile(label: str, value: str, unit: str = "", tone: str = "") -> str:
    cls = f"stat-tile stat-{tone}" if tone else "stat-tile"
    unit_html = f'<span class="stat-unit">{html_lib.escape(unit)}</span>' if unit else ""
    return (
        f'<div class="{cls}"><div class="stat-label">{html_lib.escape(label)}</div>'
        f'<div class="stat-value">{html_lib.escape(value)}{unit_html}</div></div>'
    )


def _violation_pill(label: str, value: float) -> str:
    """Violation totals ship as icon + label + number, never colour alone."""

    ok = abs(value) < 1e-6
    cls = "ok" if ok else "fail"
    icon = "✓" if ok else "!"
    return (
        f'<div class="pill-card pill-{cls}"><span class="pill-icon">{icon}</span>'
        f'<div><div class="pill-label">{html_lib.escape(label)}</div>'
        f'<div class="pill-detail">{value:,.6g}</div></div></div>'
    )


def _figure_html(fig, div_id: str, height: int) -> str:
    fig.update_layout(
        height=height,
        margin=dict(t=30, l=60, r=30, b=40),
        font=dict(
            size=11, color=MUTED_TEXT, family="system-ui, -apple-system, 'Segoe UI', sans-serif"
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        bargap=0.35,
        bargroupgap=0.14,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hoverlabel=dict(font_size=11),
    )
    fig.update_xaxes(showgrid=True, gridcolor=MUTED_GRID, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=MUTED_GRID, zeroline=False)
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        div_id=div_id,
        config={"responsive": True, "displaylogo": False},
    )


def _padded_range(values: list[float]) -> list[float]:
    """Axis range with room for the value labels drawn past the end of a bar."""

    lo, hi = min(values + [0.0]), max(values + [0.0])
    pad = (hi - lo) * 0.12 or 1.0
    return [lo - pad if lo < 0 else 0, hi + pad]


def _region_dispatch_chart(regions: list[dict]) -> str:
    """Dispatched generation against cleared demand, per region."""

    regions = sorted(regions, key=lambda i: i["@RegionID"])
    ids = [i["@RegionID"] for i in regions]
    fig = go.Figure(
        [
            go.Bar(
                x=ids,
                y=[i["@DispatchedGeneration"] for i in regions],
                name="dispatched generation",
                marker_color=SERIES_1,
                hovertemplate="%{x}<br>dispatched generation %{y:,.1f} MW<extra></extra>",
            ),
            go.Bar(
                x=ids,
                y=[i["@ClearedDemand"] for i in regions],
                name="cleared demand",
                marker_color=SERIES_2,
                hovertemplate="%{x}<br>cleared demand %{y:,.1f} MW<extra></extra>",
            ),
        ]
    )
    fig.update_yaxes(title_text="MW")
    return _figure_html(fig, "region-dispatch-plot", height=280)


def _region_price_chart(regions: list[dict]) -> str:
    """Energy price per region. One series, so the values are labelled directly
    and the chart carries no legend."""

    regions = sorted(regions, key=lambda i: i["@RegionID"])
    ids = [i["@RegionID"] for i in regions]
    prices = [i["@EnergyPrice"] for i in regions]
    fig = go.Figure(
        go.Bar(
            x=ids,
            y=prices,
            marker_color=SERIES_1,
            text=[f"{p:,.2f}" for p in prices],
            textposition="outside",
            textfont=dict(color=MUTED_TEXT),
            hovertemplate="%{x}<br>%{y:,.2f} per MWh<extra></extra>",
        )
    )
    fig.update_yaxes(title_text="price ($/MWh)", range=_padded_range(prices))
    fig.update_traces(cliponaxis=False)
    return _figure_html(fig, "region-price-plot", height=280)


def _interconnector_flow_chart(interconnectors: list[dict], context: dict) -> str:
    """Signed flow per interconnector: a diverging pair, warm against cool, so
    the direction of the flow reads before the label does."""

    meta = context.get("interconnectors", {})
    # Reversed because a horizontal bar chart stacks its first category at the
    # bottom, and the table above reads alphabetically top-down.
    interconnectors = sorted(interconnectors, key=lambda i: i["@InterconnectorID"], reverse=True)
    labels = []
    for row in interconnectors:
        info = meta.get(row["@InterconnectorID"], {})
        arrow = (
            f" ({info['from_region']}→{info['to_region']})"
            if info.get("from_region") and info.get("to_region")
            else ""
        )
        labels.append(row["@InterconnectorID"] + arrow)

    flows = [i["@Flow"] for i in interconnectors]
    fig = go.Figure(
        [
            go.Bar(
                y=labels,
                x=[f if f >= 0 else None for f in flows],
                orientation="h",
                name="forward (from → to)",
                marker_color=SERIES_1,
                hovertemplate="%{y}<br>%{x:,.1f} MW<extra></extra>",
            ),
            go.Bar(
                y=labels,
                x=[f if f < 0 else None for f in flows],
                orientation="h",
                name="reverse (to → from)",
                marker_color=SERIES_2,
                hovertemplate="%{y}<br>%{x:,.1f} MW<extra></extra>",
            ),
        ]
    )
    fig.update_xaxes(title_text="flow (MW)")
    fig.update_layout(barmode="relative")
    return _figure_html(fig, "interconnector-plot", height=max(60 + 34 * len(labels), 220))


def _trader_target_chart(traders: list[dict], context: dict, n: int = 20) -> str:
    """The n largest energy targets by magnitude. The tail is thousands of
    zeros; the table below is where every trader is reachable."""

    ranked = sorted(traders, key=lambda i: abs(i["@EnergyTarget"]), reverse=True)[:n]
    ranked = [i for i in ranked if abs(i["@EnergyTarget"]) > 0][::-1]
    if not ranked:
        return '<p class="muted">No trader has a non-zero energy target.</p>'

    meta = context.get("traders", {})
    labels = [
        f"{i['@TraderID']} ({meta.get(i['@TraderID'], {}).get('region_id', '')})".replace(" ()", "")
        for i in ranked
    ]
    values = [i["@EnergyTarget"] for i in ranked]
    fig = go.Figure(
        go.Bar(
            y=labels,
            x=values,
            orientation="h",
            marker_color=SERIES_1,
            text=[f"{v:,.1f}" for v in values],
            textposition="outside",
            textfont=dict(color=MUTED_TEXT),
            hovertemplate="%{y}<br>%{x:,.3f} MW<extra></extra>",
        )
    )
    fig.update_xaxes(title_text="energy target (MW)", range=_padded_range(values))
    fig.update_traces(cliponaxis=False)
    return _figure_html(fig, "trader-plot", height=max(60 + 26 * len(labels), 220))


def _region_table(regions: list[dict]) -> str:
    columns = (
        [("region", "string"), ("price ($/MWh)", "number")]
        + [
            (label, "number")
            for label in [
                "dispatched gen",
                "dispatched load",
                "fixed demand",
                "cleared demand",
                "net export",
                "surplus gen",
            ]
        ]
        + [(label, "number") for label, _ in FCAS_REGION_FIELDS]
    )

    rows = []
    for r in sorted(regions, key=lambda i: i["@RegionID"]):
        cells = [
            _text_cell(r["@RegionID"]),
            _num_cell(r["@EnergyPrice"], 2),
            _num_cell(r["@DispatchedGeneration"]),
            _num_cell(r["@DispatchedLoad"]),
            _num_cell(r["@FixedDemand"]),
            _num_cell(r["@ClearedDemand"]),
            _num_cell(r["@NetExport"]),
            _num_cell(r["@SurplusGeneration"], 4, "bad" if r["@SurplusGeneration"] else ""),
        ] + [_num_cell(r[field]) for _, field in FCAS_REGION_FIELDS]
        rows.append(f"<tr>{''.join(cells)}</tr>")

    return _table_card(title="Region solution", table_id="region-table", columns=columns, rows=rows)


def _interconnector_table(interconnectors: list[dict], context: dict) -> str:
    meta = context.get("interconnectors", {})
    columns = [
        ("interconnector", "string"),
        ("from", "string"),
        ("to", "string"),
        ("flow (MW)", "number"),
        ("losses (MW)", "number"),
        ("lower limit", "number"),
        ("upper limit", "number"),
        ("deficit", "number"),
    ]

    rows = []
    for r in sorted(interconnectors, key=lambda i: i["@InterconnectorID"]):
        info = meta.get(r["@InterconnectorID"], {})
        cells = [
            _text_cell(r["@InterconnectorID"]),
            _text_cell(info.get("from_region", "")),
            _text_cell(info.get("to_region", "")),
            _num_cell(r["@Flow"]),
            _num_cell(r["@Losses"]),
            _num_cell(info.get("lower_limit"), 1),
            _num_cell(info.get("upper_limit"), 1),
            _num_cell(r["@Deficit"], 4, "bad" if r["@Deficit"] else ""),
        ]
        rows.append(f"<tr>{''.join(cells)}</tr>")

    return _table_card(
        title="Interconnector solution",
        table_id="interconnector-table",
        columns=columns,
        rows=rows,
    )


def _trader_table(traders: list[dict], context: dict) -> str:
    """Every trader, one row each: energy target, the move from InitialMW, and
    the ten FCAS targets.

    Most traders are dispatched to zero in every service, so the toolbar hides
    those by default -- with the count of what is hidden, and a checkbox to
    bring them back.
    """

    meta = context.get("traders", {})
    columns = (
        [
            ("trader", "string"),
            ("region", "string"),
            ("type", "string"),
            ("initial MW", "number"),
            ("energy target", "number"),
            ("change", "number"),
        ]
        + [(label, "number") for label, _ in FCAS_TRADER_FIELDS]
        + [
            ("ramp up", "number"),
            ("ramp dn", "number"),
            ("FS mode", "string"),
            ("violation", "number"),
        ]
    )

    rows = []
    for t in sorted(traders, key=lambda i: i["@TraderID"]):
        info = meta.get(t["@TraderID"], {})
        initial_mw = info.get("initial_mw")
        energy_target = t["@EnergyTarget"]
        change = None if initial_mw is None else energy_target - initial_mw
        violation = sum(t[field] for field in TRADER_VIOLATION_FIELDS)
        dispatched = abs(energy_target) > 0 or any(
            abs(t[field]) > 0 for _, field in FCAS_TRADER_FIELDS
        )

        cells = (
            [
                _text_cell(t["@TraderID"]),
                _text_cell(info.get("region_id", "")),
                _text_cell(info.get("trader_type", "")),
                _num_cell(initial_mw),
                _num_cell(energy_target),
                _num_cell(change),
            ]
            + [_num_cell(t[field]) for _, field in FCAS_TRADER_FIELDS]
            + [
                _num_cell(t.get("@RampUpRate")),
                _num_cell(t.get("@RampDnRate")),
                _text_cell(t.get("@FSTargetMode", "")),
                _num_cell(violation, 4, "bad" if violation else ""),
            ]
        )
        row_cls = ' class="row-violation"' if violation else ""
        rows.append(
            f'<tr{row_cls} data-region="{html_lib.escape(info.get("region_id", ""))}" '
            f'data-zero="{0 if dispatched else 1}">{"".join(cells)}</tr>'
        )

    # Nothing dispatched at all (a stress-tested or heavily edited casefile) would
    # leave the default view empty, so the toggle starts on when there is nothing
    # to hide.
    n_dispatched = sum(1 for row in rows if 'data-zero="0"' in row)
    checked = "" if n_dispatched else " checked"

    regions = sorted({info.get("region_id", "") for info in meta.values() if info.get("region_id")})
    options = "".join(
        f'<option value="{html_lib.escape(r)}">{html_lib.escape(r)}</option>' for r in regions
    )
    toolbar = f"""
    <input type="search" class="filter-input" data-target="trader-table" placeholder="Filter trader / region / type…">
    <select class="region-filter" data-target="trader-table"><option value="">All regions</option>{options}</select>
    <label class="check"><input type="checkbox" class="zero-toggle" data-target="trader-table"{checked}> show traders dispatched to zero</label>
"""
    return _table_card(
        title="Trader solution",
        table_id="trader-table",
        columns=columns,
        rows=rows,
        toolbar=toolbar,
    )


def _constraint_table(constraints: list[dict]) -> str:
    """Generic constraints, with the violated ones first and shown by default.

    A casefile carries around a thousand of these; the handful with a non-zero
    deficit are the ones that explain a surprising dispatch, so they lead and
    the rest are behind the checkbox.
    """

    columns = [("constraint", "string"), ("RHS", "number"), ("deficit", "number")]
    ranked = sorted(constraints, key=lambda i: (-abs(i["@Deficit"]), i["@ConstraintID"]))

    rows = []
    for c in ranked:
        deficit = c["@Deficit"]
        row_cls = ' class="row-violation"' if deficit else ""
        cells = [
            _text_cell(c["@ConstraintID"]),
            _num_cell(c["@RHS"]),
            _num_cell(deficit, 4, "bad" if deficit else ""),
        ]
        rows.append(f'<tr{row_cls} data-zero="{0 if deficit else 1}">{"".join(cells)}</tr>')

    # A clean solve violates nothing, which would render an empty table; in that
    # case the full list is the only useful view, so the toggle starts on.
    n_violated = sum(1 for c in constraints if c["@Deficit"])
    checked = "" if n_violated else " checked"
    toolbar = f"""
    <input type="search" class="filter-input" data-target="constraint-table" placeholder="Filter constraint id…">
    <label class="check"><input type="checkbox" class="zero-toggle" data-target="constraint-table"{checked}> show constraints with no deficit</label>
    <span class="muted">{n_violated} of {len(constraints)} constraints carry a deficit</span>
"""
    return _table_card(
        title="Generic constraint solution",
        table_id="constraint-table",
        columns=columns,
        rows=rows,
        toolbar=toolbar,
    )


_SOLUTION_CSS = """
.stat-row { display: flex; flex-wrap: wrap; gap: 10px; margin: 14px 0 4px; }
.stat-tile { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 10px 14px; min-width: 150px; }
.stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }
.stat-value { font-size: 20px; font-weight: 600; margin-top: 2px; }
.stat-unit { font-size: 12px; color: var(--text-secondary); font-weight: 400; margin-left: 4px; }
.stat-bad .stat-value { color: var(--critical); }
.chart-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 14px; margin-bottom: 14px; }
/* Plotly writes an explicit pixel width onto its own div, so without min-width:0
   the grid track stretches to whatever width it first measured and the two cards
   overlap instead of sharing the row. */
.chart-grid > .plot-card { margin-bottom: 0; min-width: 0; }
.plot-card > div { max-width: 100%; }
.chart-title { font-size: 12px; color: var(--text-secondary); font-weight: 600; padding: 6px 8px 0; }
.check { font-size: 12px; color: var(--text-secondary); display: inline-flex; align-items: center; gap: 5px; }
.region-filter { padding: 6px 8px; border-radius: 6px; border: 1px solid var(--border); background: var(--page); color: var(--text-primary); font-size: 12px; }
td.bad { color: var(--critical); font-weight: 600; }
tr.row-violation { background: var(--critical-bg); }
.section-note { color: var(--text-muted); font-size: 12px; margin: 0 0 10px; }
.pill-heading { font-size: 13px; font-weight: 600; margin: 14px 0 2px; }
"""

# Sorting reads data-value rather than the rendered text, so grouped thousands
# separators can stay in the cells. Filtering is one pass over the three
# controls a card may carry (search box, region select, zero-row checkbox), so
# they compose instead of overriding one another.
_SOLUTION_JS = """
function cellValue(cell, type) {
  if (type === 'number') {
    var raw = cell.getAttribute('data-value');
    var n = parseFloat(raw === null ? cell.textContent : raw);
    return isNaN(n) ? -Infinity : n;
  }
  return cell.textContent.trim().toLowerCase();
}

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
        var av = cellValue(a.children[idx], type);
        var bv = cellValue(b.children[idx], type);
        if (av < bv) return dir === 'asc' ? -1 : 1;
        if (av > bv) return dir === 'asc' ? 1 : -1;
        return 0;
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
    });
  });
});

function applyFilters(tableId) {
  var table = document.getElementById(tableId);
  var card = table.closest('.table-card');
  var search = card.querySelector('.filter-input');
  var region = card.querySelector('.region-filter');
  var zeroToggle = card.querySelector('.zero-toggle');
  var query = search ? search.value.trim().toLowerCase() : '';
  var wanted = region ? region.value : '';
  var showZero = zeroToggle ? zeroToggle.checked : true;
  var rows = table.querySelectorAll('tbody tr');
  var shown = 0;
  rows.forEach(function (row) {
    var visible = query === '' || row.textContent.toLowerCase().indexOf(query) !== -1;
    if (visible && wanted) visible = row.getAttribute('data-region') === wanted;
    if (visible && !showZero) visible = row.getAttribute('data-zero') !== '1';
    row.style.display = visible ? '' : 'none';
    if (visible) shown++;
  });
  var counter = card.querySelector('.row-count');
  if (counter) counter.textContent = shown + ' of ' + rows.length + ' rows shown';
}

document.querySelectorAll('[data-target]').forEach(function (control) {
  var event = control.tagName === 'INPUT' && control.type !== 'checkbox' ? 'input' : 'change';
  control.addEventListener(event, function () { applyFilters(control.getAttribute('data-target')); });
});

document.querySelectorAll('table.sortable').forEach(function (table) { applyFilters(table.id); });

// Plotly sizes a figure to its container at script-execution time, which for the
// first chart in a two-column grid is *before* the second chart's card exists --
// so the track is still full width and the figure is drawn twice as wide as the
// card it ends up in. One resize once the document is laid out settles them all.
window.addEventListener('load', function () {
  document.querySelectorAll('.plotly-graph-div').forEach(function (div) {
    if (window.Plotly) { window.Plotly.Plots.resize(div); }
  });
});
"""

_PAGE_TEMPLATE = string.Template("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>NEMDE dispatch solution — $case_id</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%232f6feb'%3E%3Cpath d='M13 2 3 14h7l-1 8 10-12h-7l1-8z'/%3E%3C/svg%3E">
<script src="$plotly_cdn"></script>
<style>$css</style>
</head>
<body>
<div class="page">
  <header>
    <h1>Dispatch solution <span class="overall-badge $status_cls">$status</span></h1>
    <div class="meta">casefile <code>$case_id</code> &middot; period <code>$period_id</code>
      &middot; intervention <code>$intervention</code> &middot; run <code>$run_id</code>
      &middot; git <code>$git_sha</code> &middot; generated $timestamp</div>
    <div class="disclaimer-banner"><strong>Approximation, not AEMO's model.</strong> This is a reverse-engineered
      reconstruction of NEMDE built from publicly available documentation, not AEMO's own source. It will not match
      NEMDE exactly. Provided as-is, with absolutely no warranty.</div>
    <div class="stat-row">$stats</div>
    <h2 class="pill-heading">Constraint violations</h2>
    <p class="section-note">Each figure is the model's constraint-violation (slack)
      variable for that constraint family, in MW -- how far the solution had to relax
      the constraint to stay feasible. All zero in a clean solve; a non-zero value
      flags a constraint the model could not fully satisfy.</p>
    <div class="pill-row">$violation_pills</div>
  </header>

  <section class="entity-section">
    <h2>Regions</h2>
    <div class="chart-grid">
      <div class="plot-card"><div class="chart-title">Dispatched generation vs cleared demand (MW)</div>$region_dispatch_plot</div>
      <div class="plot-card"><div class="chart-title">Energy price by region</div>$region_price_plot</div>
    </div>
    $region_table
  </section>

  <section class="entity-section">
    <h2>Interconnectors</h2>
    <p class="section-note">Positive flow runs from the interconnector's from-region to its to-region.</p>
    <div class="plot-card">$interconnector_plot</div>
    $interconnector_table
  </section>

  <section class="entity-section">
    <h2>Traders</h2>
    <div class="plot-card"><div class="chart-title">Largest energy targets (MW)</div>$trader_plot</div>
    $trader_table
  </section>

  <section class="entity-section">
    <h2>Generic constraints</h2>
    $constraint_table
  </section>

</div>
<script>$js</script>
</body>
</html>
""")


def build_solution_report(
    *,
    solution: dict,
    context: dict | None = None,
    run_id: str = "",
    git_sha: str = "",
) -> str:
    """Render one model solution as a standalone HTML page.

    `solution` is run_model()'s output. `context` is solution_context(casefile)
    when the casefile is to hand -- it supplies the region/type/InitialMW
    labels the solution dict does not carry; without it those columns render
    empty and everything else is unchanged.
    """

    context = context or {}
    regions = solution["RegionSolution"]
    traders = solution["TraderSolution"]
    interconnectors = solution["InterconnectorSolution"]
    period = solution["PeriodSolution"]
    solver_info = solution.get("SolverInfo", {})

    termination = solver_info.get("termination_condition", "unknown")
    total_violation = sum(abs(period[field]) for _, field in PERIOD_VIOLATION_FIELDS)
    n_dispatched = sum(1 for t in traders if abs(t["@EnergyTarget"]) > 0)

    stats = "".join(
        [
            _stat_tile(
                "Dispatched generation",
                f"{sum(r['@DispatchedGeneration'] for r in regions):,.1f}",
                "MW",
            ),
            _stat_tile("Cleared demand", f"{sum(r['@ClearedDemand'] for r in regions):,.1f}", "MW"),
            _stat_tile("Traders dispatched", f"{n_dispatched:,} of {len(traders):,}"),
            _stat_tile(
                "Total violation",
                f"{total_violation:,.4f}",
                tone="bad" if total_violation > 1e-6 else "",
            ),
            _stat_tile("Solve time", f"{solver_info.get('solve_seconds', 0):,.1f}", "s"),
        ]
    )

    violation_pills = "".join(
        _violation_pill(label, period[field]) for label, field in PERIOD_VIOLATION_FIELDS
    )

    return _PAGE_TEMPLATE.substitute(
        case_id=html_lib.escape(str(period["@CaseID"])),
        period_id=html_lib.escape(str(context.get("period_id", "") or "—")),
        intervention=html_lib.escape(str(period["@Intervention"])),
        run_id=html_lib.escape(run_id) or "—",
        git_sha=html_lib.escape(git_sha[:12]) or "unknown",
        timestamp=pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        status=html_lib.escape(str(termination)).upper(),
        status_cls="ok" if termination == "optimal" else "fail",
        stats=stats,
        violation_pills=violation_pills,
        plotly_cdn=PLOTLY_CDN,
        css=REPORT_CSS + _SOLUTION_CSS,
        js=_SOLUTION_JS,
        region_dispatch_plot=_region_dispatch_chart(regions),
        region_price_plot=_region_price_chart(regions),
        region_table=_region_table(regions),
        interconnector_plot=_interconnector_flow_chart(interconnectors, context),
        interconnector_table=_interconnector_table(interconnectors, context),
        trader_plot=_trader_target_chart(traders, context),
        trader_table=_trader_table(traders, context),
        constraint_table=_constraint_table(solution["ConstraintSolution"]),
    )


def solution_frames(solution: dict, context: dict | None = None) -> dict:
    """The three tabular views of a solution as DataFrames: one row per region,
    per interconnector and per trader, with the casefile labels joined on.

    The HTML page renders these same numbers; these are for the caller who
    wants to diff two runs in pandas, or open a CSV in a spreadsheet, without
    scraping the page.
    """

    context = context or {}
    trader_meta = context.get("traders", {})
    interconnector_meta = context.get("interconnectors", {})

    regions = pd.DataFrame(solution["RegionSolution"])

    interconnectors = pd.DataFrame(solution["InterconnectorSolution"]).assign(
        from_region=lambda df_: df_["@InterconnectorID"].map(
            lambda i: interconnector_meta.get(i, {}).get("from_region", "")
        ),
        to_region=lambda df_: df_["@InterconnectorID"].map(
            lambda i: interconnector_meta.get(i, {}).get("to_region", "")
        ),
    )

    traders = pd.DataFrame(solution["TraderSolution"]).assign(
        region_id=lambda df_: df_["@TraderID"].map(
            lambda i: trader_meta.get(i, {}).get("region_id", "")
        ),
        trader_type=lambda df_: df_["@TraderID"].map(
            lambda i: trader_meta.get(i, {}).get("trader_type", "")
        ),
        initial_mw=lambda df_: df_["@TraderID"].map(
            lambda i: trader_meta.get(i, {}).get("initial_mw")
        ),
    )
    traders["target_minus_initial"] = traders["@EnergyTarget"] - traders["initial_mw"]

    return {
        "region": regions.sort_values("@RegionID"),
        "interconnector": interconnectors.sort_values("@InterconnectorID"),
        "trader": traders.sort_values("@TraderID"),
    }


def persist_solution(
    *,
    solution: dict,
    html_report: str,
    casefile_id: str,
    run_id: str,
    file_service,
    frames: dict | None = None,
) -> str:
    """Write one solve's artefacts through `file_service` and return the
    directory they landed in, relative to the file service's root.

    Same `output/<date>/<run>/` layout as a backtest run, so both kinds of run
    sit in one chronologically-sorted tree.
    """

    run_dir = run_artefact_dir(casefile_id=casefile_id, run_id=run_id)
    frames = frames if frames is not None else solution_frames(solution)

    artefacts = {
        "solution_report.html": html_report,
        "solution.json": solution,
        "region_solution.csv": frames["region"].round(4),
        "interconnector_solution.csv": frames["interconnector"].round(4),
        "trader_solution.csv": frames["trader"].round(4),
    }

    for name, data in artefacts.items():
        file_service.save_artefact(data=data, relative_path=Path(f"output/{run_dir}/{name}"))

    return run_dir
