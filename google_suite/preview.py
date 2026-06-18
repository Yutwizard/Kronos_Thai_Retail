#!/usr/bin/env python3
"""Local preview harness for the Google Suite Apps Script SPA (Index.html).

Apps Script's `google.script.run` and `google.visualization` only exist inside
a deployed web app. This script injects a mock runtime into a copy of
Index.html so you can click through the whole UI locally — no Google account,
no clasp, no deploy — using the MOCK fixture already defined in Index.html.

What the mock covers:
  * google.script.run.<fn>(...)  → returns canned responses asynchronously
      - getAllData / refreshAllData → window.MOCK (the in-page fixture)
      - getSetupStatus, getPendingEdits, getExportCsv
      - submitTradeEdit / submitTradeDelete / submitFills / resetCapital → ok
  * google.charts / google.visualization → offline stub; LineChart.draw()
      renders a small inline SVG so the equity curve is still visible.

Usage:
    python google_suite/preview.py            # build + serve at :8770
    python google_suite/preview.py --port 9000
    python google_suite/preview.py --no-serve # just write preview.html

The generated preview.html is gitignored-style throwaway; re-run after editing
Index.html to pick up changes. It is NEVER deployed.
"""
import argparse
import re
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE / "apps_script" / "Index.html"
OUT = HERE / "preview.html"

MOCK_RUNTIME = r"""
<!-- ===== LOCAL PREVIEW MOCK RUNTIME (injected by preview.py — not in production) ===== -->
<script>
(function () {
  window.google = window.google || {};

  // --- google.script.run: chainable, async, canned responses ---
  function makeRunner() {
    var ok = null, fail = null;
    var ctx = {
      withSuccessHandler: function (f) { ok = f; return ctx; },
      withFailureHandler: function (f) { fail = f; return ctx; },
      withUserObject:     function ()  { return ctx; },
    };
    // server function name -> () => response. Reads window.MOCK lazily (it is
    // defined later, inside Index.html's own script).
    // Patch the in-page MOCK fixture so the demo renders cleanly without
    // editing the production Index.html: freshen the pipeline timestamp and
    // backfill riskMetrics.equity/cash (present in the real RiskMetrics sheet,
    // omitted from the fixture) so Total Capital isn't NaN.
    function freshData() {
      var m = window.MOCK || {};
      try {
        if (m.pipeline) m.pipeline.last_run_timestamp = new Date().toISOString();
        if (m.riskMetrics && m.riskMetrics.length && m.equityCurve && m.equityCurve.length) {
          var eq = m.equityCurve[m.equityCurve.length - 1];
          var rm = m.riskMetrics[m.riskMetrics.length - 1];
          if (rm.equity == null) rm.equity = eq.equity;
          if (rm.cash == null) rm.cash = eq.cash;
        }
      } catch (e) { /* fixture optional */ }
      return m;
    }
    var handlers = {
      getAllData:      function () { return freshData(); },
      refreshAllData:  function () { return freshData(); },
      getSetupStatus:  function () { return { isFirstRun: false, hasTrades: true, currentCapital: 500000 }; },
      getPendingEdits: function () { return { count: 0, edits: [] }; },
      getExportCsv:    function () {
        return '# LOCAL PREVIEW export\nticker,action,shares,est_cost_thb,rationale\n'
             + 'ADVANC.BK,buy,500,113000,demo signal\n';
      },
      submitTradeEdit:   function () { return { ok: true, status: 'edit queued (mock — no Colab in preview)' }; },
      submitTradeDelete: function () { return { ok: true, status: 'delete queued (mock)' }; },
      submitFills:       function (fills) { return { ok: true, updated: (fills && fills.length) || 0 }; },
      resetCapital:      function () { return { ok: true, status: 'queued (mock)' }; },
    };
    Object.keys(handlers).forEach(function (name) {
      ctx[name] = function () {
        var args = arguments;
        setTimeout(function () {
          try { var r = handlers[name].apply(null, args); if (ok) ok(r); }
          catch (e) { if (fail) fail(e); else console.error(e); }
        }, 60);  // small delay mimics the async round-trip
      };
    });
    return ctx;
  }
  window.google.script = {
    host: { close: function () {}, setHeight: function () {}, setWidth: function () {},
            editor: { focus: function () {} } },
  };
  // fresh runner per `.run` access (matches Apps Script semantics)
  Object.defineProperty(window.google.script, 'run', { get: makeRunner });

  // --- google.charts / google.visualization: offline stub ---
  window.google.charts = {
    load: function () { return { then: function (cb) { if (cb) cb(); } }; },
    setOnLoadCallback: function (cb) { setTimeout(cb, 0); },
  };
  function DataTable() { this._cols = []; this._rows = []; }
  DataTable.prototype.addColumn = function (t, label) { this._cols.push(label); };
  DataTable.prototype.addRow    = function (row) { this._rows.push(row); };
  DataTable.prototype.addRows   = function (rows) { Array.prototype.push.apply(this._rows, rows); };
  DataTable.prototype.getNumberOfRows = function () { return this._rows.length; };

  function LineChart(el) { this._el = el; }
  LineChart.prototype.draw = function (dt) {
    // rows: [label, portfolio, initialCapital]
    var rows = dt._rows || [];
    if (!this._el || rows.length < 1) return;
    var W = 760, H = 260, padL = 64, padR = 16, padT = 12, padB = 40;
    var port = rows.map(function (r) { return Number(r[1]); });
    var init = rows.map(function (r) { return Number(r[2]); });
    var all = port.concat(init);
    var minV = Math.min.apply(null, all), maxV = Math.max.apply(null, all);
    var range = (maxV - minV) || 1;
    var n = rows.length;
    var x = function (i) { return padL + (n === 1 ? 0 : i * (W - padL - padR) / (n - 1)); };
    var y = function (v) { return padT + (1 - (v - minV) / range) * (H - padT - padB); };
    var pathOf = function (vals) {
      return vals.map(function (v, i) { return (i ? 'L' : 'M') + x(i).toFixed(1) + ',' + y(v).toFixed(1); }).join(' ');
    };
    var grid = '';
    for (var g = 0; g <= 4; g++) {
      var gv = minV + range * g / 4, gy = y(gv);
      grid += '<line x1="' + padL + '" y1="' + gy.toFixed(1) + '" x2="' + (W - padR) + '" y2="' + gy.toFixed(1) +
              '" stroke="#e0e0e0"/>' +
              '<text x="' + (padL - 6) + '" y="' + (gy + 3).toFixed(1) + '" text-anchor="end" font-size="10" fill="#888">฿' +
              Math.round(gv).toLocaleString() + '</text>';
    }
    var labs = '';
    [0, Math.floor((n - 1) / 2), n - 1].forEach(function (i) {
      if (i < 0) return;
      labs += '<text x="' + x(i).toFixed(1) + '" y="' + (H - padB + 18) + '" text-anchor="middle" font-size="10" fill="#888">' +
              String(rows[i][0]) + '</text>';
    });
    this._el.innerHTML =
      '<div style="font-size:11px;color:#c5221f;margin-bottom:4px">⚠ preview: inline SVG stub (real Google Charts only in deployed app)</div>' +
      '<svg viewBox="0 0 ' + W + ' ' + H + '" style="width:100%;height:auto">' + grid +
      '<path d="' + pathOf(init) + '" fill="none" stroke="#dadce0" stroke-width="2" stroke-dasharray="4 4"/>' +
      '<path d="' + pathOf(port) + '" fill="none" stroke="#4285f4" stroke-width="2"/>' + labs + '</svg>';
  };
  window.google.visualization = { DataTable: DataTable, LineChart: LineChart,
    events: { addListener: function () {} } };

  console.info('[preview] mock google.script.run + charts stub active — data is from window.MOCK');
})();
</script>
<!-- ===== END MOCK RUNTIME ===== -->
"""


def build() -> Path:
    if not INDEX.exists():
        raise SystemExit(f"Index.html not found at {INDEX}")
    html = INDEX.read_text(encoding="utf-8")

    # Drop the gstatic Charts loader so the offline stub isn't overwritten.
    html = re.sub(r'\s*<script src="https://www\.gstatic\.com/charts/loader\.js"></script>',
                  "\n<!-- gstatic charts loader removed by preview.py (offline stub used) -->",
                  html)

    # Inject the mock runtime just before </head> so it runs before the SPA script.
    if "</head>" in html:
        html = html.replace("</head>", MOCK_RUNTIME + "</head>", 1)
    else:  # no <head> (Apps Script HtmlService fragment) — prepend
        html = MOCK_RUNTIME + html

    OUT.write_text(html, encoding="utf-8")
    return OUT


def serve(port: int) -> None:
    handler = partial(SimpleHTTPRequestHandler, directory=str(HERE))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/preview.html"
    print(f"Serving Google Suite preview at {url}\n(Ctrl-C to stop; re-run after editing Index.html)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


def main() -> None:
    ap = argparse.ArgumentParser(description="Local preview harness for the Google Suite SPA")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--no-serve", action="store_true", help="only build preview.html, do not serve")
    args = ap.parse_args()
    out = build()
    print(f"Built {out}")
    if not args.no_serve:
        serve(args.port)


if __name__ == "__main__":
    main()
