# Ticket 16: SET / emerging-market strategy evidence beyond arXiv (TODO, optional)

STATUS: DONE 2026-09-22. 5 papers fully verified (primary page or full text opened); several others are unverified leads only (search-summary, not opened). No candidate is tested on SET data by this ticket -- see 'Rule for anything found' below.

## Why
The arXiv pass (ticket 08) found no tradable Thai strategy paper and no compliant low-vol, reversal or equity-seasonality paper. Journals, SSRN and Thai institutions are where most of that literature lives.

## Sources to search (primary pages only)
- SSRN and journal pages: Journal of Finance/RFS/JFE anomaly replications with international or emerging-market samples; Pacific-Basin Finance Journal; Emerging Markets Review; Journal of Banking & Finance; Asia-Pacific Journal of Financial Studies.
- Thai sources: SET research/`SET Note`, the Bank of Thailand discussion papers, Chulalongkorn, NIDA, Thammasat and other Thai university working papers on SET momentum, reversal, size, low-volatility, seasonality.
- Search terms: SET momentum, Thai stock anomalies, ASEAN low-volatility, SET turn-of-month, SET calendar effects, Thai retail investor performance.

## Rubric (same as ticket 08)
Point-in-time rigor first (out-of-sample, costs, multiple years, honest benchmark), then long-only or separable long leg, daily/monthly price-only inputs, code or data released, sample includes SET or ASEAN. Paper needs the full text opened, not only the abstract; say which for every entry.

## Output
A ranked list (aim 10-20) with the same columns as ticket 08 plus "sample includes SET: yes/no", appended below or in `17-...` if long. Exclusions listed with reasons.

## Rule for anything found
There is no clean unseen SET history left (see PLAN). A promising candidate is not backtested on 2018-2026 again; it is written up with a pre-committed rule and added to the forward paper track only if the user decides so.

## Result

### Verified papers (primary page or full text opened)
| # | Paper | Sample | Design | Fit under our rubric | Verified |
|---|---|---|---|---|---|
| 1 | Saengchote (2020), "Profitability, Investment and Asset Pricing: Reconciling the Valuation and the q-Theory Approaches in the Thai Stock Market", PIER Discussion Paper 124 (Chulalongkorn Business School; Puey Ungphakorn Institute for Economic Research, Bank-of-Thailand-affiliated) | SET + MAI, July 2000 - June 2019 (19 years), Refinitiv Datastream, penny stocks (<0.90 THB) and non-continuously-traded names screened out | 10 long-short factor-mimicking portfolios (Fama-French 6-factor and Hou-Xue-Zhang q-5), annual (June) and monthly rebalance, value-weighted, double/triple sorts. In-sample only, no transaction costs, no OOS split. | UMD (momentum, price-only, 2-12 month skip-1): mean **+0.8%/month, t = 2.47** (significant at 95%). HML (value, needs book equity): **+0.6%/month, t = 2.93** (99%, the only FF factor besides MKT to pass). ROE (profitability, needs financial statements): **+1.3%/month, t = 5.79**, the only factor of 10 to clear the stricter Harvey-Liu-Zhu t>3 hurdle. Value/profitability need fundamentals (reference-only under ticket 08's rule); momentum (UMD) is price-only and computable from our cache. | Full text (10 pages read, incl. Tables 1-3) |
| 2 | Saengchote (2017), "The Low-Risk Anomaly: Evidence from the Thai Stock Market", Asian Academy of Management Journal of Accounting and Finance (AAMJAF) 13(1) | SET, 2004-2015 | Beta-sort long-short portfolio (long low-beta, short high-beta); beta is price-computable (no fundamentals needed) | Monthly four-factor alpha **+1.26%**; in-sample, no transaction costs, long leg not isolated. | Abstract page (ideas.repec.org) |
| 3 | Tharavanij, Siraprapasiri & Rajchamaha (2015), "Performance of technical trading rules: evidence from Southeast Asian stock markets" | 5 SE Asian markets incl. **SET index**, Jan 2000 - Dec 2013 (14 years) | RSI, Stochastic, MACD, DMI, OBV; long-only tested; **costs incorporated, Thailand round-trip 0.5%** (comparable to our 0.268% one-way = 0.536% round trip); benchmark buy-and-hold; optimized vs standard parameters, no explicit out-of-sample split | Thailand: **"strong performance"**, MACD/DMI/OBV profitable net of costs. Other SE Asian markets mostly failed net of costs; Singapore failed entirely. Closest fit to our rubric of anything found (long-only, price-only, real SET-comparable costs), but weak on out-of-sample/data-snooping controls. | Full text via PMC (open access) |
| 4 | Huynh & Khoa (2025), "Regional asymmetry in financial markets: Pricing of skewness risk in the Thai stock market", PLOS ONE | SET, 2005-2024 (daily data, all listed stocks with >=24 months history) | Decile portfolios on lagged monthly skewness; long-short (long lowest-skewness decile, short highest) | Spread **+1.017%/month, t = 3.94, p<0.01**, robust across CAPM/FF3/Carhart4/FF5. Long leg alone only **+0.127%/month** (weak). Explicitly "frictionless... transaction costs are negligible" (their own acknowledged limitation). In-sample. | Full text (open access) |
| 5 | Wuthisatian (2022), "An examination of calendar anomalies: evidence from the Thai stock market", Journal of Economic Studies 49(3) | SET composite indexes, Mar 2014 - Mar 2019 | Regression on day-of-week and January dummies | Monday returns significantly negative; January returns significantly positive. No magnitude, cost or OOS information available (abstract only; full text paywalled). | Abstract (Emerald primary page) |

### Reading
- Momentum (finding 1's UMD) is the one price-only, long-short-but-separable result with a positive, significant t-statistic on a 19-year SET sample (2000-2019) that does not overlap our own 2018-2026 tests. It does not confirm our own momentum finding (different design: factor-mimicking portfolio vs top-10 selection, in-sample vs our out-of-sample, no costs vs our 0.268% friction) but is at least directionally consistent, unlike the classic 1990s cross-Asia momentum literature (Chui/Titman/Wei-style studies reporting no Asian momentum in 1979-1994 samples) -- NOT independently verified here (search-summary only, primary pages 403'd); not cited as fact.
- Value (HML) and profitability (ROE) are the strongest SET factors found in this search, both needing financial-statement fundamentals -- out of scope for our price-only rule (ticket 08), listed for reference only.
- The technical-trading-rules paper (#3) is the closest fit to our hard filters (long-only, price-only, real comparable SET costs) of anything found across both this search and the arXiv pass (ticket 08), but its out-of-sample discipline is weaker than our own bar (ticket 06/09/10's pre-registration and holdout-window standard).
- Every SET-specific paper found is in-sample only; none pre-registers a discovery/holdout split the way this project's own tickets do. None reports a friction-adjusted, out-of-sample Sharpe or CAGR comparable to what tickets 06/09/10 require.

### Unverified leads (search-summary only; NOT opened; do not cite as fact)
Company Size Effect in the Stock Market of Thailand (Hussaini); Value Investing in the Stock Market of Thailand; Pojanavatee (2020) four-factor SET study; the "q-factor approach for the Thai market" ScienceDirect/PBFJ version (likely the published form of verified paper #1, not independently confirmed); Chui/Titman/Wei-style historical Asian momentum studies reporting no Thai momentum in 1979-1994 samples; "Empirical evidence of profitability anomaly in the Thai stock market" (2002-2019). Each was 403-blocked or PDF-unreadable on every route tried (direct fetch, ResearchGate, IDEAS/RePEc, Semantic Scholar). Stopped chasing these once returns diminished, per the standing rule against citing search summaries as fact.

### Excluded, reference only
Everything needing financial-statement fundamentals (HML, RMW, CMA, ROE, EG, size/value studies generally) -- out of scope per ticket 08's price-only rule. The 2025 Fama-French SET/MAI paper (Kitkanasiri, Palahan & Pan-urai, Journal of Applied Economics and Management Strategy, SET+MAI 2012-2021, confirms significant size and book-to-market factors) is the same family and excluded for the same reason.

## Rule for anything found (per PLAN-next-research.md)
No unseen SET history remains for a 2018-2026 backtest (see the multiple-testing register). Nothing here is pre-registered or tested. If the user later wants to act on any of these -- most plausibly the UMD-style price-only momentum evidence or the technical-trading-rules paper -- the next step is a written pre-committed rule added to the forward paper track (ticket 11 style), not another historical backtest.

## Closure
Diminishing returns: the Thai academic literature on SET anomalies is dominated by long-short, fundamentals-based factor studies (value, profitability, low-risk, size), almost none of which fit the price-only, long-only rubric this project needs, and none pre-registers an out-of-sample test to this project's standard. Five papers were verified; several further leads were 403-blocked on every route tried and are listed as unverified rather than chased indefinitely. No new candidate is proposed for testing.
