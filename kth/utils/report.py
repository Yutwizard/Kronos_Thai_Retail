"""Daily decision report: signal table builder, Markdown/HTML renderer."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from kth.data.universe import get_ticker_class, get_display_name

# Fallback band-width thresholds — PER ASSET CLASS (not global)
BAND_THRESHOLDS = {
    "thai_equity":   (0.15, 0.30),
    "thai_index":    (0.15, 0.30),
    "us_equity":     (0.15, 0.30),
    "etf_global":    (0.15, 0.30),
    "commodity":     (0.20, 0.35),
    "crypto":        (0.30, 0.50),
    "bond_proxy":    (0.10, 0.20),
    "reit":          (0.10, 0.20),
    "fx_macro":      (0.05, 0.15),
}
DEFAULT_THRESHOLD = (0.15, 0.30)


def _compute_band_width(result) -> float:
    """Compute (p95 - p5) / abs(p50) for the 20d horizon. Returns inf if p50=0."""
    h = result.horizons[20]
    p5 = h.summary["p5"].iloc[-1]
    p95 = h.summary["p95"].iloc[-1]
    p50 = h.summary["p50"].iloc[-1]
    if abs(p50) < 1e-10:
        return float("inf")
    return float((p95 - p5) / abs(p50))


def _get_confidence(
    ticker: str,
    result,
    backtest_result=None,
    per_ticker_hit_rates: dict[str, float] | None = None,
) -> tuple[str, float]:
    """
    Returns (flag_emoji, flag_weight).
    Priority: per-ticker hit_rate > per-class hit_rate > band-width fallback.
    """
    # 1. Per-ticker calibration (highest priority)
    if per_ticker_hit_rates and ticker in per_ticker_hit_rates:
        hit_rate = per_ticker_hit_rates[ticker]
        if hit_rate >= 0.60:
            return f"\U0001F7E2 ({hit_rate:.0%})", 1.0
        elif hit_rate >= 0.50:
            return f"\U0001F7E1 ({hit_rate:.0%})", 0.5
        else:
            return f"\U0001F534 ({hit_rate:.0%})", 0.1

    # 2. Per-class calibration
    if backtest_result is not None:
        attr = backtest_result.per_class_attribution
        cls = get_ticker_class(ticker) or "unknown"
        cls_row = attr[attr["asset_class"] == cls]
        if len(cls_row) > 0:
            hit_rate = float(cls_row["hit_rate"].iloc[0])
            if hit_rate >= 0.60:
                return f"\U0001F7E2 ({hit_rate:.0%})", 1.0
            elif hit_rate >= 0.50:
                return f"\U0001F7E1 ({hit_rate:.0%})", 0.5
            else:
                return f"\U0001F534 ({hit_rate:.0%})", 0.1

    # 3. Fallback: band-width based (PER CLASS thresholds)
    cls = get_ticker_class(ticker) or "unknown"
    green_max, yellow_max = BAND_THRESHOLDS.get(cls, DEFAULT_THRESHOLD)
    bw = _compute_band_width(result)
    if bw < green_max:
        return "\U0001F7E2 (band)", 1.0
    elif bw < yellow_max:
        return "\U0001F7E1 (band)", 0.5
    else:
        return "\U0001F534 (band)", 0.1


def build_report_table(
    forecasts: dict[str, object],
    last_closes: dict[str, float],
    backtest_result=None,
    per_ticker_hit_rates: dict[str, float] | None = None,
    long_threshold: float = 0.01,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (confidence_adjusted_table, raw_forecast_table).
    last_closes: REQUIRED. Actual close price per ticker.
    """
    rows = []
    for ticker, result in forecasts.items():
        cls = get_ticker_class(ticker) or "unknown"
        name = get_display_name(ticker)

        if ticker not in last_closes:
            continue
        last_close = last_closes[ticker]

        h5 = result.horizons[5]
        h20 = result.horizons[20]

        p50_1d = float((h5.summary["p50"].iloc[0] / last_close - 1) * 100)
        p50_5d = float((h5.summary["p50"].iloc[-1] / last_close - 1) * 100)
        p50_20d = float((h20.summary["p50"].iloc[-1] / last_close - 1) * 100)

        band_20 = float(h20.summary["p95"].iloc[-1] - h20.summary["p5"].iloc[-1])
        p5_p95_band = float((band_20 / last_close) * 100)

        confidence, flag_weight = _get_confidence(ticker, result, backtest_result, per_ticker_hit_rates)
        score = p50_20d * flag_weight

        signal = "LONG" if p50_20d > long_threshold else "FLAT"
        is_red = confidence.startswith("\U0001F534")

        rows.append({
            "Ticker": ticker,
            "Name": name,
            "Class": cls,
            "1d p50": round(p50_1d, 2),
            "5d p50": round(p50_5d, 2),
            "20d p50": round(p50_20d, 2),
            "P5-P95 band": round(p5_p95_band, 2),
            "Signal": "FLAT" if is_red else signal,
            "Confidence": confidence,
            "Score": round(score, 2),
        })

    raw_table = pd.DataFrame(rows).sort_values("20d p50", ascending=False)
    adj_table = pd.DataFrame(rows).sort_values("Score", ascending=False)

    return adj_table, raw_table


def render_markdown(table: pd.DataFrame) -> str:
    """Returns a Markdown-formatted string for Jupyter display."""
    lines = []
    lines.append("### Kronos-TH Daily Report")
    lines.append("")
    lines.append(f"*Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")
    lines.append("| Ticker | Name | Class | 1d p50 | 5d p50 | 20d p50 | P5-P95 band | Signal | Confidence |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |")

    for _, row in table.iterrows():
        lines.append(
            f"| {row['Ticker']} | {row['Name']} | {row['Class']} | "
            f"{row['1d p50']:+.1f}% | {row['5d p50']:+.1f}% | {row['20d p50']:+.1f}% | "
            f"{row['P5-P95 band']:.1f}% | **{row['Signal']}** | {row['Confidence']} |"
        )

    lines.append("")
    lines.append("*This is research output, not financial advice.*")
    return "\n".join(lines)


def _table_to_html(table: pd.DataFrame) -> str:
    """Convert report DataFrame to an HTML table with colour-coded confidence cells."""
    rows = ["<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse'>"]
    cols = ["Ticker", "Name", "Class", "1d p50", "5d p50", "20d p50", "P5-P95 band", "Signal", "Confidence"]
    rows.append("<thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead>")
    rows.append("<tbody>")
    for _, row in table.iterrows():
        conf = str(row["Confidence"])
        if "\U0001F7E2" in conf:
            bg = "#e8f5e9"
        elif "\U0001F7E1" in conf:
            bg = "#fffde7"
        else:
            bg = "#ffebee"
        signal_style = "font-weight:bold;color:#1565C0" if row["Signal"] == "LONG" else "color:#999"
        cells = (
            f"<td>{row['Ticker']}</td>"
            f"<td>{row['Name']}</td>"
            f"<td>{row['Class']}</td>"
            f"<td align='right'>{row['1d p50']:+.1f}%</td>"
            f"<td align='right'>{row['5d p50']:+.1f}%</td>"
            f"<td align='right'>{row['20d p50']:+.1f}%</td>"
            f"<td align='right'>{row['P5-P95 band']:.1f}%</td>"
            f"<td style='{signal_style}'>{row['Signal']}</td>"
            f"<td style='background:{bg}'>{conf}</td>"
        )
        rows.append(f"<tr>{cells}</tr>")
    rows.append("</tbody></table>")
    return "\n".join(rows)


def render_html(
    tables: tuple[pd.DataFrame, pd.DataFrame],
    path: str,
    model_name: str,
    generated_at: "pd.Timestamp",
) -> str:
    """
    Write a standalone HTML report to `path`.
    `tables` is the (confidence_adjusted_table, raw_forecast_table) tuple.
    Returns `path` for chaining.
    """
    adj_table, raw_table = tables
    date_str = generated_at.strftime("%Y-%m-%d")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Kronos-TH Daily Report — {date_str}</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 40px auto; padding: 0 20px; }}
    h1 {{ color: #1565C0; }} h2 {{ color: #333; margin-top: 40px; }}
    p.meta {{ color: #666; font-size: 0.9em; }}
    .disclaimer {{ background: #f5f5f5; padding: 16px; border-left: 4px solid #ccc; margin-top: 40px; }}
  </style>
</head>
<body>
  <h1>Kronos-TH Daily Report — {date_str}</h1>
  <p class="meta">Model: {model_name} &nbsp;|&nbsp; Generated: {generated_at.strftime("%Y-%m-%d %H:%M")}</p>

  <h2>Signal Table (Confidence-Adjusted)</h2>
  <p>Sorted by score = 20d p50 x confidence weight. Red-flagged assets are forced to FLAT.</p>
  {_table_to_html(adj_table)}

  <h2>Raw Model Forecasts — not filtered by historical accuracy</h2>
  <p>Sorted by 20d p50 only. No signal suppression applied.</p>
  {_table_to_html(raw_table)}

  <div class="disclaimer">
    <h2>Disclaimer</h2>
    <p>This is research output from a forecasting model, not financial advice.
    Past model accuracy does not guarantee future performance. All investments carry risk.
    The confidence flags are derived from historical backtests and may not reflect
    future model behaviour, especially after regime changes or model updates.</p>
  </div>
</body>
</html>"""

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)
