function doGet() {
  return HtmlService
    .createHtmlOutputFromFile('Index')
    .setTitle('Kronos-TH Portfolio')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function _rowToObj(headers, row) {
  var obj = {};
  headers.forEach(function(h, i) {
    var v = row[i];
    if (v === '' || v === null || v === undefined) {
      obj[h] = null;
    } else if (v instanceof Date) {
      obj[h] = Utilities.formatDate(v, 'Asia/Bangkok', 'yyyy-MM-dd');
    } else if (!isNaN(Number(v))) {
      obj[h] = Number(v);
    } else {
      obj[h] = v;
    }
  });
  return obj;
}

function _readSheet(ss, name) {
  var sheet = ss.getSheetByName(name);
  var data  = sheet.getDataRange().getValues();
  if (data.length <= 1) return [];
  var headers = data[0];
  return data.slice(1).map(function(r) { return _rowToObj(headers, r); });
}

function _readSheetLimited(ss, name, maxRows) {
  var sheet   = ss.getSheetByName(name);
  var lastRow = sheet.getLastRow();
  if (lastRow <= 1) return [];
  var startRow = Math.max(2, lastRow - maxRows + 1);
  var numRows  = lastRow - startRow + 1;
  var numCols  = sheet.getLastColumn();
  var headers  = sheet.getRange(1, 1, 1, numCols).getValues()[0];
  var values   = sheet.getRange(startRow, 1, numRows, numCols).getValues();
  return values.map(function(r) { return _rowToObj(headers, r); });
}

function _csvField(v) {
  var s = (v == null) ? '' : String(v);
  return (s.indexOf(',') >= 0 || s.indexOf('"') >= 0 || s.indexOf('\n') >= 0)
    ? '"' + s.replace(/"/g, '""') + '"'
    : s;
}

function getAllData() {
  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var cache = CacheService.getScriptCache();
  var hit   = cache.get('all_data');
  if (hit) return JSON.parse(hit);

  var pipelineRows = _readSheet(ss, 'Pipeline Status');
  var data = {
    pipeline:        pipelineRows.length ? pipelineRows[0] : null,
    portfolio:       _readSheet(ss, 'Portfolio'),
    equityCurve:     _readSheetLimited(ss, 'Equity Curve',      90),
    positions:       _readSheet(ss, 'Positions'),
    tradeLog:        _readSheetLimited(ss, 'Trade Log',        200),
    forecasts:       _readSheet(ss, 'Forecasts'),
    forecastHistory: _readSheetLimited(ss, 'Forecast History', 180),
    ticket:          _readSheet(ss, 'Trade Ticket'),
    riskMetrics:     _readSheetLimited(ss, 'Risk Metrics',     365),
  };

  var json = JSON.stringify(data);
  if (json.length < 100000) cache.put('all_data', json, 300);
  return data;
}

function refreshAllData() {
  CacheService.getScriptCache().remove('all_data');
  return getAllData();
}

function submitFills(fills) {
  // fills = [{ticker, filled_price, filled_shares, fill_timestamp}, ...]
  // Writes fill data to the Trade Ticket sheet columns 8-10 and clears cache
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ws = ss.getSheetByName('Trade Ticket');
  var data = ws.getDataRange().getValues();
  if (data.length <= 1) return { ok: false, msg: 'Trade Ticket sheet is empty' };

  var headers  = data[0];
  var tickerCol = headers.indexOf('ticker');
  var fpCol     = headers.indexOf('filled_price');
  var fsCol     = headers.indexOf('filled_shares');
  var ftCol     = headers.indexOf('fill_timestamp');
  if (fpCol === -1) return { ok: false, msg: 'filled_price column not found — check sheet headers' };

  // Collect all updates and write in one batch to minimise API calls
  var updates = [];
  fills.forEach(function(fill) {
    for (var i = 1; i < data.length; i++) {
      if (String(data[i][tickerCol]) === String(fill.ticker)) {
        updates.push({ row: i + 1, fp: fill.filled_price,
                       fs: fill.filled_shares, ft: fill.fill_timestamp });
        break;
      }
    }
  });

  updates.forEach(function(u) {
    ws.getRange(u.row, fpCol + 1).setValue(u.fp);
    ws.getRange(u.row, fsCol + 1).setValue(u.fs);
    ws.getRange(u.row, ftCol + 1).setValue(u.ft);
  });

  // Invalidate cache so next getAllData() returns fresh data with fills
  CacheService.getScriptCache().remove('all_data');
  return { ok: true, updated: updates.length };
}

function getExportCsv() {
  var ss      = SpreadsheetApp.getActiveSpreadsheet();
  var status  = _readSheet(ss, 'Pipeline Status');
  var lastRun = (status.length && status[0].last_run_timestamp)
                ? new Date(status[0].last_run_timestamp) : null;
  var hoursAgo = lastRun ? (Date.now() - lastRun.getTime()) / 3600000 : 999;
  var warning  = hoursAgo > 24
    ? '# WARNING: Pipeline last ran ' + Math.round(hoursAgo) + ' hours ago. Data may be stale.\n'
    : '';
  var ticket = _readSheet(ss, 'Trade Ticket');
  var header = '# Execute at next market open (Bangkok time, UTC+7).\n'
             + '# Prices are previous close estimates.\n'
             + '# After execution: enter fills in the Trade Ticket sheet cols 8-10.\n';
  var rows = ticket.map(function(r) {
    return [r.ticker, r.action, r.shares, r.est_cost_thb, _csvField(r.rationale)].join(',');
  });
  return warning + header + 'ticker,action,shares,est_cost_thb,rationale\n' + rows.join('\n');
}
