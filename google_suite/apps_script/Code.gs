function doGet() {
  return HtmlService
    .createHtmlOutputFromFile('Index')
    .setTitle('Kronos-TH Portfolio')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function _cachePut(key, value, ttl) {
  try {
    CacheService.getScriptCache().put(key, value, ttl || 60);
  } catch (e) {
    console.error('Cache put failed (quota?): ' + e.message);
  }
}

function _cacheRemove(key) {
  try {
    CacheService.getScriptCache().remove(key);
  } catch (e) {
    console.error('Cache remove failed: ' + e.message);
  }
}

function _cacheGet(key) {
  try {
    return CacheService.getScriptCache().get(key);
  } catch (e) {
    console.error('Cache get failed: ' + e.message);
    return null;
  }
}

function _log(action, detail) {
  try {
    console.log(JSON.stringify({ time: new Date().toISOString(), action: action, detail: detail }));
  } catch (e) {
    // silent fail
  }
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
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var hit = _cacheGet('all_data');
  if (hit) {
    _log('getAllData', 'cache_hit');
    return JSON.parse(hit);
  }
  _log('getAllData', 'cache_miss');

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
    health:          getHealthCheck(),
  };

  var json = JSON.stringify(data);
  if (json.length < 100000) _cachePut('all_data', json, 60);
  return data;
}

function refreshAllData() {
  _cacheRemove('all_data');
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
  _cacheRemove('all_data');
  _log('submitFills', { updated: updates.length });
  return { ok: true, updated: updates.length };
}

function submitTradeEdit(index, newShares, newPrice) {
  // Validate input
  if (!Number.isInteger(index) || index < 0) {
    return { ok: false, msg: 'Invalid trade index' };
  }
  if (!Number.isInteger(newShares) || newShares <= 0 || newShares % 100 !== 0) {
    return { ok: false, msg: 'Shares must be a positive multiple of 100' };
  }
  if (typeof newPrice !== 'number' || newPrice <= 0) {
    return { ok: false, msg: 'Price must be a positive number' };
  }

  // Verify the trade exists in the Trade Log sheet
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ws = ss.getSheetByName('Trade Log');
  var data = ws.getDataRange().getValues();
  if (data.length <= 1 || index >= data.length - 1) {
    return { ok: false, msg: 'Trade index out of range' };
  }
  var ticker = data[index + 1][1];  // col 1 (0-indexed) is ticker

  // Append to Trade Edits staging sheet
  var editsWs = ss.getSheetByName('Trade Edits');
  var editsData = editsWs.getDataRange().getValues();
  if (editsData.length === 0) {
    editsWs.appendRow(['date','action','index','ticker','shares','price','ref_id','requested_at']);
  }
  editsWs.appendRow([
    new Date().toISOString().slice(0, 10),
    'edit',
    index,
    ticker,
    newShares,
    newPrice,
    '',
    new Date().toISOString(),
  ]);

  // Invalidate cache
  _cacheRemove('all_data');
  _log('submitTradeEdit', { index: index, ticker: ticker, newShares: newShares, newPrice: newPrice });
  return { ok: true, status: 'edit queued — please re-run Colab Cell 9b' };
}

function submitTradeDelete(index) {
  if (!Number.isInteger(index) || index < 0) {
    return { ok: false, msg: 'Invalid trade index' };
  }
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ws = ss.getSheetByName('Trade Log');
  var data = ws.getDataRange().getValues();
  if (data.length <= 1 || index >= data.length - 1) {
    return { ok: false, msg: 'Trade index out of range' };
  }
  var tradeId = data[index + 1][8];  // col 8 is the trade_id

  var editsWs = ss.getSheetByName('Trade Edits');
  var editsData = editsWs.getDataRange().getValues();
  if (editsData.length === 0) {
    editsWs.appendRow(['date','action','index','ticker','shares','price','ref_id','requested_at']);
  }
  editsWs.appendRow([
    new Date().toISOString().slice(0, 10),
    'CANCEL',
    index,
    data[index + 1][1],
    '',
    '',
    tradeId,
    new Date().toISOString(),
  ]);

  _cacheRemove('all_data');
  _log('submitTradeDelete', { index: index, tradeId: tradeId });
  return { ok: true, status: 'delete queued — please re-run Colab Cell 9b' };
}

function getPendingEdits() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ws = ss.getSheetByName('Trade Edits');
  if (!ws) return { count: 0, edits: [] };
  var data = ws.getDataRange().getValues();
  if (data.length <= 1) return { count: 0, edits: [] };
  var headers = data[0];
  var edits = data.slice(1).map(function(r) {
    var obj = {};
    headers.forEach(function(h, i) { obj[h] = r[i]; });
    return obj;
  }).filter(function(e) { return e.action; });
  return { count: edits.length, edits: edits };
}

function resetCapital(newCapital, confirmText) {
  if (typeof newCapital !== 'number' || newCapital < 1 || newCapital > 100000000) {
    return { ok: false, msg: 'Capital must be between 1 and 100,000,000 THB' };
  }
  if (confirmText !== 'RESET' && confirmText !== 'SETUP') {
    return { ok: false, msg: 'Confirmation text must be RESET (destructive) or SETUP (first run)' };
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ws = ss.getSheetByName('Capital Reset');
  var data = ws.getDataRange().getValues();
  if (data.length === 0) {
    ws.appendRow(['date','action','capital','confirm_text','requested_at']);
  }
  ws.appendRow([
    new Date().toISOString().slice(0, 10),
    confirmText === 'RESET' ? 'reset' : 'setup',
    newCapital,
    confirmText,
    new Date().toISOString(),
  ]);

  _cacheRemove('all_data');
  _log('resetCapital', { newCapital: newCapital, confirmText: confirmText });
  return {
    ok: true,
    status: confirmText === 'RESET'
      ? 'reset queued — please re-run Colab Cell 4b (DESTRUCTIVE: clears all trades)'
      : 'setup queued — please re-run Colab Cell 4b',
  };
}

function getSetupStatus() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var portfolioWs = ss.getSheetByName('Portfolio');
  var tradeLogWs = ss.getSheetByName('Trade Log');
  var portfolioRows = portfolioWs ? portfolioWs.getDataRange().getValues() : [];
  var tradeLogRows  = tradeLogWs ? tradeLogWs.getDataRange().getValues() : [];
  var hasPortfolio = portfolioRows.length > 1;
  var hasTrades = tradeLogRows.length > 1;
  var currentCapital = hasPortfolio ? Number(portfolioRows[1][0]) || 0 : 0;
  return {
    isFirstRun: !hasPortfolio,
    hasTrades: hasTrades,
    currentCapital: currentCapital,
  };
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

function getHealthCheck() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ws = ss.getSheetByName('Calibration');
  if (!ws) return { status: 'unknown', coverage: null, target: 0.90, divergence: 0,
                    recommendation: 'Run the pipeline to compute calibration.' };
  var lastRow = ws.getLastRow();
  if (lastRow <= 1) return { status: 'unknown', coverage: null, target: 0.90,
                              divergence: 0, recommendation: 'Calibration sheet is empty.' };
  var headers = ws.getRange(1, 1, 1, ws.getLastColumn()).getValues()[0];
  var values  = ws.getRange(lastRow, 1, 1, ws.getLastColumn()).getValues()[0];
  var row = {};
  headers.forEach(function(h, i) { row[h] = values[i]; });
  var coverage = Number(row.coverage) || 0;
  var target = 0.90;  // P5/P95 band target for a well-calibrated model
  var divergence = coverage - target;
  var status = String(row.status || 'unknown');
  var recommendation;
  if (status === 'diverged' || coverage < 0.80) {
    recommendation = 'Coverage is well below the 90% target. Consider halving position sizes.';
  } else if (status === 'monitor' || coverage < 0.85) {
    recommendation = 'Coverage is below the 90% target. Monitor closely.';
  } else if (status === 'overconfident' || coverage > 0.95) {
    recommendation = 'Coverage exceeds 95% — bands may be too wide. Model is underconfident.';
  } else if (status === 'insufficient_data') {
    recommendation = 'Need at least 10 resolved forecasts. Keep running the pipeline daily.';
  } else {
    recommendation = 'On track — model calibration is within 5pp of the 90% target.';
  }
  return {
    coverage: coverage,
    target: target,
    divergence: divergence,
    status: status,
    recommendation: recommendation,
    n_samples: Number(row.n_samples) || 0,
    date: row.date || null,
  };
}
