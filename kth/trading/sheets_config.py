"""Single source of truth for Google Sheets schemas and tab names.

Apps Script (Code.gs) and Index.html must mirror these definitions manually.
"""

# --- Tab names ---
PORTFOLIO = 'Portfolio'
EQUITY_CURVE = 'Equity Curve'
POSITIONS = 'Positions'
TRADE_LOG = 'Trade Log'
FORECASTS = 'Forecasts'
FORECAST_HISTORY = 'Forecast History'
TRADE_TICKET = 'Trade Ticket'
RISK_METRICS = 'Risk Metrics'
PIPELINE_STATUS = 'Pipeline Status'
CALIBRATION = 'Calibration'

STAGING_SUFFIX = '_staging'
TRADE_EDITS = 'Trade Edits'
CAPITAL_RESET = 'Capital Reset'
MANUAL_TRADES = 'Manual Trades'

# --- Header schemas ---
PORTFOLIO_HEADERS = ['cash', 'initial_capital', 'mode', 'model_version', 'forecast_date']
EQUITY_CURVE_HEADERS = ['date', 'equity', 'cash', 'invested']
POSITIONS_HEADERS = ['ticker', 'shares', 'avg_cost', 'entry_date', 'sector',
                     'current_price', 'pnl', 'pnl_pct', 'pct_to_stoploss',
                     'underlying_ticker', 'premium_pct']
TRADE_LOG_HEADERS = ['timestamp', 'ticker', 'action', 'shares', 'price', 'rationale',
                     'friction_cost', 'model_version', 'id', 'ref_id']
FORECASTS_HEADERS = ['date_updated', 'ticker', 'rank_score', 'exp_ret', 'band_width',
                     'confidence', 'net_return', 'p5', 'p50', 'p95', 'sector']
FORECAST_HISTORY_HEADERS = ['date', 'ticker', 'predicted_direction', 'predicted_return',
                            'entry_close', 'actual_return', 'was_correct']
TRADE_TICKET_HEADERS = ['ticker', 'action', 'shares', 'est_cost_thb', 'rationale',
                        'sector', 'confidence', 'filled_price', 'filled_shares', 'fill_timestamp']
RISK_METRICS_HEADERS = ['date', 'equity', 'cash', 'deployed_pct', 'trailing_sharpe_12w',
                        'max_drawdown_pct', 'mtd_pnl_pct', 'trade_win_rate', 'calmar_ratio',
                        'sortino_ratio', 'drawdown_velocity', 'allocation_band', 'allocation_pct',
                        'market_state', 'is_frozen', 'bootstrap_p_value',
                        'friction_ytd_pct', 'friction_ytd_thb']
PIPELINE_STATUS_HEADERS = ['last_run_timestamp', 'status', 'duration_seconds',
                           'error_message', 'sheets_updated']
CALIBRATION_HEADERS = ['date', 'coverage', 'n_samples', 'status']
TRADE_EDITS_HEADERS = ['date', 'action', 'index', 'ticker', 'shares', 'price', 'ref_id', 'requested_at', 'new_date']
CAPITAL_RESET_HEADERS = ['date', 'action', 'capital', 'confirm_text', 'requested_at']
MANUAL_TRADES_HEADERS = ['date', 'action', 'ticker', 'shares', 'price', 'requested_at']

ALL_HEADERS = {
    PORTFOLIO: PORTFOLIO_HEADERS,
    EQUITY_CURVE: EQUITY_CURVE_HEADERS,
    POSITIONS: POSITIONS_HEADERS,
    TRADE_LOG: TRADE_LOG_HEADERS,
    FORECASTS: FORECASTS_HEADERS,
    FORECAST_HISTORY: FORECAST_HISTORY_HEADERS,
    TRADE_TICKET: TRADE_TICKET_HEADERS,
    RISK_METRICS: RISK_METRICS_HEADERS,
    PIPELINE_STATUS: PIPELINE_STATUS_HEADERS,
    CALIBRATION: CALIBRATION_HEADERS,
    TRADE_EDITS: TRADE_EDITS_HEADERS,
    CAPITAL_RESET: CAPITAL_RESET_HEADERS,
    MANUAL_TRADES: MANUAL_TRADES_HEADERS,
}

ALL_SHEETS = list(ALL_HEADERS.keys()) + [s + STAGING_SUFFIX for s in [
    PORTFOLIO, POSITIONS, FORECASTS, TRADE_TICKET, RISK_METRICS, EQUITY_CURVE,
]]
