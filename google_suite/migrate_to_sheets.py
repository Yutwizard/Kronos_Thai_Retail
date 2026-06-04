"""One-time migration: data/positions/ JSON + CSV to Google Sheets.

Usage:
  python google_suite/migrate_to_sheets.py --id <SPREADSHEET_ID>

  First run opens a browser OAuth window. Credentials are saved to
  ~/.config/gspread/authorized_user.json for future runs.
"""
import json, csv, hashlib, argparse
from pathlib import Path

PORTFOLIO_JSON = Path('data/positions/paper_portfolio.json')
TRADE_LOG_CSV  = Path('data/positions/trade_log.csv')


def migrate(spreadsheet_id: str):
    import gspread
    gc = gspread.oauth()
    sh = gc.open_by_key(spreadsheet_id)
    print(f"Connected to: {sh.title}")

    if PORTFOLIO_JSON.exists():
        pf = json.loads(PORTFOLIO_JSON.read_text())

        ws = sh.worksheet('Portfolio')
        from kth.trading.portfolio import MODEL_VERSION
        ws.update('A1:E2', [
            ['cash', 'initial_capital', 'mode', 'model_version', 'forecast_date'],
            [pf['cash'], pf['initial_capital'], pf.get('mode', 'paper'),
             pf.get('model_version', MODEL_VERSION),
             str(pf['equity_curve'][-1]['date']) if pf.get('equity_curve') else ''],
        ])

        eq_ws = sh.worksheet('Equity Curve')
        eq_ws.clear()
        eq_ws.append_row(['date', 'equity', 'cash', 'invested'])
        rows = [[e['date'], e['value'], '', ''] for e in pf.get('equity_curve', [])]
        if rows:
            eq_ws.append_rows(rows)
        print(f"Portfolio migrated. Equity curve: {len(rows)} rows.")

    if TRADE_LOG_CSV.exists():
        tl_ws = sh.worksheet('Trade Log')
        tl_ws.clear()
        tl_ws.append_row([
            'timestamp','ticker','action','shares','price','rationale',
            'friction_cost','model_version','id','ref_id',
        ])
        new_rows = []
        with open(TRADE_LOG_CSV) as f:
            for trade in csv.DictReader(f):
                raw  = f"{trade['date']}_{trade['ticker']}_{trade['action']}"
                hex4 = hashlib.md5(raw.encode()).hexdigest()[:4]
                tid  = f"{trade['date'].replace('-','')}_{trade['ticker']}_{trade['action']}_{hex4}"
                new_rows.append([
                    trade['date'], trade['ticker'], trade['action'],
                    trade['shares'], trade['price'], trade.get('rationale', ''),
                    trade.get('friction_cost', ''), trade.get('model_version', ''),
                    tid, '',
                ])
        if new_rows:
            tl_ws.append_rows(new_rows)
        print(f"Trade Log migrated: {len(new_rows)} trades.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate Kronos-TH data to Google Sheets')
    parser.add_argument('--id', required=True, help='Google Spreadsheet ID from the URL')
    args = parser.parse_args()
    migrate(args.id)
