"""2025 precompute + walkforward with n_samples=50 (offline)."""
import os; os.environ['HF_HUB_OFFLINE'] = '1'
import time
from pathlib import Path
from kth.data.universe import UNIVERSE
from kth.models.kronos_wrapper import KronosTH
from kth.backtest.walkforward import BacktestConfig, precompute_forecasts, run_walkforward

tickers = [x for x, _, _ in UNIVERSE['thai_equity']]
k = KronosTH.from_pretrained('NeoQuasar/Kronos-small', device='cuda')

c = BacktestConfig(start_date='2025-01-01', end_date='2025-12-31',
                   lookback=400, pred_len=20, n_samples=50,
                   position_sizing='equal', max_positions=5,
                   min_ticker_history=20)

print(f'2025: {len(tickers)} tickers, n_samples=50, offline', flush=True)
t0 = time.time()
precompute_forecasts(k, tickers, start_date=c.start_date, end_date=c.end_date,
                     pred_len=c.pred_len, n_samples=c.n_samples, lookback=c.lookback)
print(f'PRECOMPUTE: {(time.time()-t0)/3600:.1f} hrs', flush=True)

r = run_walkforward(c, k, tickers)
o = Path('data/backtest_results/thai_equity_2025_n50')
o.mkdir(parents=True, exist_ok=True)
r.save(str(o))
m = r.metrics
print(f'DONE: Ret={(r.equity_curve.iloc[-1]/r.equity_curve.iloc[0]-1):+.2%} Sharpe={m["sharpe"]:.2f} MaxDD={m["max_drawdown"]:.2%} p={m["p_value"]:.3f}')
