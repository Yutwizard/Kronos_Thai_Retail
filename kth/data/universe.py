"""
The investable universe for a Thai retail investor (as of 2025-2026).

Each asset class lists what a Thai retail investor can realistically buy
through Thai-licensed brokers/exchanges, with the corresponding yfinance
ticker.

Notes:
- Thai stocks (.BK): full retail access via any Thai broker.
- US stocks/ETFs: accessible since 2022 via DIME!, Liberator, Jitta Wealth,
  Phillip, Kim Eng, Bualuang, etc. Fractional shares legal.
- Crypto: Thailand has approved 5-year capital gains tax exemption
  (2025-2029) for trades via licensed exchanges (Bitkub, Binance TH,
  Orbix, etc.). yfinance prices are vs USD; investors trade vs THB.
- Gold: Thai gold savings accounts at BBL/KBank track international spot.
  GLD ETF is the cleanest proxy. GC=F is futures.
- Thai mutual funds: most popular retail vehicle BUT no clean free API.
  We exclude them from the model and instead use their underlying
  benchmarks as proxies (e.g. for a "global gold equity fund" -> use GDX).

Excluded by design:
- Thai mutual funds: NAV-only, no free API, daily-lagged data
- Bonds: thin retail secondary market, irregular prices
- TFEX derivatives: outside retail scope for forecasting tool
"""

# Asset class -> list of (yfinance_ticker, display_name, notes)
UNIVERSE = {
    "thai_equity": [
        ("PTT.BK",     "PTT",                "Energy major"),
        ("KBANK.BK",   "Kasikornbank",       "Top 3 bank"),
        ("SCB.BK",     "SCB X",              "Top 3 bank"),
        ("BBL.BK",     "Bangkok Bank",       "Top 3 bank"),
        ("CPALL.BK",   "CP All",             "7-Eleven Thailand"),
        ("DELTA.BK",   "Delta Electronics",  "Largest SET mkt cap"),
        ("ADVANC.BK",  "AIS",                "Telecom"),
        ("AOT.BK",     "Airports of TH",     "Tourism proxy"),
        ("BDMS.BK",    "Bangkok Dusit Med",  "Healthcare"),
        ("GULF.BK",    "Gulf Energy",        "Power"),
        ("PTTEP.BK",   "PTT Exploration",    "Oil/gas E&P"),
        ("CPN.BK",     "Central Pattana",    "Retail property"),
        ("MINT.BK",    "Minor International","Hospitality"),
        ("BH.BK",      "Bumrungrad",         "Medical tourism"),
        ("IVL.BK",     "Indorama Ventures",  "Petrochem global"),
        ("BGRIM.BK",   "B.Grimm Power",      "Energy"),
        ("GPSC.BK",    "Global Power Synergy","Energy"),
        ("TOP.BK",     "Thai Oil",           "Energy"),
        ("IRPC.BK",    "IRPC",               "Petrochemical"),
        ("BANPU.BK",   "Banpu",              "Coal/energy"),
        ("BCP.BK",     "Bangchak Corp",      "Energy"),
        ("RATCH.BK",   "Ratch Group",        "Energy"),
        ("KTB.BK",     "Krung Thai Bank",    "Banking"),
        ("TISCO.BK",   "TISCO Financial",    "Banking"),
        ("TCAP.BK",    "Thanachart Capital", "Banking"),
        ("KKP.BK",     "Kiatnakin Phatra",   "Banking"),
        ("MEGA.BK",    "Mega Lifesciences",  "Commerce"),
        ("LH.BK",      "Land & Houses",      "Property"),
        ("QH.BK",      "Quality Houses",     "Property"),
        ("AP.BK",      "AP Thailand",        "Property"),
        ("ORI.BK",     "Origin Property",    "Property"),
        ("SCC.BK",     "Siam Cement",        "Construction"),
        ("HMPRO.BK",   "Home Product Center","Retail"),
        ("SIRI.BK",    "Sansiri",            "Property"),
        ("PSH.BK",     "Prinsiri",           "Property"),
        ("CPF.BK",     "Charoen Pokphand Foods","Food"),
        ("OSP.BK",     "Osotspa",            "Beverage"),
        ("ICHI.BK",    "Ichitan Group",      "Beverage"),
        ("CRC.BK",     "Central Retail",     "Retail"),
        ("GLOBAL.BK",  "Siam Global House",  "Retail"),
        ("DOHOME.BK",  "Dohome",             "Retail"),
        ("CENTEL.BK",  "Central Plaza Hotel","Hospitality"),
        ("ERW.BK",     "Erawan Group",       "Hospitality"),
        ("BCH.BK",     "Bangkok Chain Hospital","Healthcare"),
        ("CHG.BK",     "Chularat Hospital",  "Healthcare"),
        ("BEM.BK",     "Bangkok Expressway", "Logistics"),
        ("BTS.BK",     "BTS Group",          "Logistics"),
        ("TRUE.BK",    "True Corp",          "Telecom"),
        ("JMART.BK",   "J Mart",             "Tech"),
        ("HANA.BK",    "Hana Microelectronic","Tech"),
    ],

    "thai_index": [
        ("^SET.BK",    "SET Index",          "Thailand benchmark"),
    ],

    "us_equity": [
        ("AAPL",  "Apple",     "Mega-cap tech"),
        ("MSFT",  "Microsoft", "Mega-cap tech"),
        ("NVDA",  "NVIDIA",    "AI"),
        ("GOOGL", "Alphabet",  "Mega-cap tech"),
        ("AMZN",  "Amazon",    "Mega-cap tech"),
        ("META",  "Meta",      "Mega-cap tech"),
        ("TSLA",  "Tesla",     "EV/auto"),
        ("BRK-B", "Berkshire", "Diversified"),
        ("JPM",   "JPMorgan",  "Bank"),
        ("V",     "Visa",      "Payments"),
        ("COST",  "Costco",    "Retail/warehouse"),
        ("WMT",   "Walmart",   "Retail"),
        ("NFLX",  "Netflix",   "Streaming"),
        ("AMD",   "AMD",       "Semiconductor"),
        ("DIS",   "Disney",    "Media"),
        ("KO",    "Coca-Cola", "Beverage"),
        ("PEP",   "PepsiCo",   "Beverage"),
    ],

    "etf_global": [
        ("SPY", "S&P 500",                  "US large-cap"),
        ("QQQ", "Nasdaq 100",               "US tech-heavy"),
        ("VTI", "Vanguard Total Mkt",       "US whole market"),
        ("VWO", "Vanguard Emerging",        "EM exposure"),
        ("VEA", "Vanguard Developed ex-US", "DM ex-US"),
        ("IEMG","iShares EM",               "EM alt"),
        ("EWY", "iShares S.Korea",          "Korea single-country"),
        ("EWJ", "iShares Japan",            "Japan single-country"),
        ("FXI", "iShares China L-Cap",      "China A-shares proxy"),
    ],

    "commodity": [
        ("GLD",  "SPDR Gold ETF",     "Cleanest gold daily price"),
        ("GC=F", "Gold Futures",      "Backup gold series"),
        ("SLV",  "Silver ETF",        "Silver"),
        ("USO",  "US Oil Fund ETF",   "Crude oil proxy"),
    ],

    "crypto": [
        ("BTC-USD",  "Bitcoin",   "Largest cap"),
        ("ETH-USD",  "Ethereum",  "Smart contracts"),
        ("SOL-USD",  "Solana",    "High-performance L1"),
        ("ADA-USD",  "Cardano",   "Proof-of-stake L1"),
        ("AVAX-USD", "Avalanche", "Subnet L1"),
        ("LINK-USD", "Chainlink", "Oracle network"),
        ("DOGE-USD", "Dogecoin",  "Meme coin"),
        ("DOT-USD",  "Polkadot",  "Parachain L0"),
        ("LTC-USD",  "Litecoin",  "OG payment coin"),
        ("NEAR-USD", "NEAR",      "Sharded L1"),
        ("VET-USD",  "VeChain",   "Supply chain L1"),
        ("MATIC-USD","Polygon",   "Ethereum L2"),
    ],

    "bond_proxy": [
        ("TLT",  "20Y+ Treasury ETF", "Long-duration safe-haven"),
        ("IEF",  "7-10Y Treasury",    "Mid-duration"),
        ("HYG",  "High-yield bonds",  "Credit risk proxy"),
    ],

    "reit": [
        ("VNQ",       "US REITs ETF",  "US property"),
        ("CPNREIT.BK","CPN Retail Growth REIT", "Thai retail REIT"),
    ],

    "fx_macro": [
        ("THB=X", "USDTHB",        "FX exposure on USD assets"),
        ("DX-Y.NYB", "DXY",        "USD strength index"),
    ],
}


def get_all_tickers():
    """Flat list of every ticker in the universe."""
    return [t for cls in UNIVERSE.values() for (t, _, _) in cls]


def get_ticker_class(ticker):
    """Reverse lookup: which asset class does this ticker belong to?"""
    for cls, items in UNIVERSE.items():
        if any(t == ticker for (t, _, _) in items):
            return cls
    return None


def get_display_name(ticker):
    for items in UNIVERSE.values():
        for (t, name, _) in items:
            if t == ticker:
                return name
    return ticker


# Trading frictions per asset class (used by backtester)
# These are typical Thai-retail effective costs, round-trip.
FRICTION = {
    # Thai equity: ~0.157% commission online + 7% VAT on commission + 0.001% SET fee
    #             = ~0.168% one-way, ~0.336% round-trip. Plus 0.1% slippage assumed.
    "thai_equity":  {"commission_oneway": 0.00168, "slippage_oneway": 0.0010},
    "thai_index":   {"commission_oneway": 0.00168, "slippage_oneway": 0.0010},
    "reit":         {"commission_oneway": 0.00168, "slippage_oneway": 0.0015},

    # US stocks via Thai brokers: ~0.20%-0.30% commission, FX spread baked in.
    # Use 0.30% one-way as conservative.
    "us_equity":    {"commission_oneway": 0.0030, "slippage_oneway": 0.0005},
    "etf_global":   {"commission_oneway": 0.0030, "slippage_oneway": 0.0005},
    "bond_proxy":   {"commission_oneway": 0.0030, "slippage_oneway": 0.0005},
    "commodity":    {"commission_oneway": 0.0030, "slippage_oneway": 0.0010},

    # Crypto via Thai licensed exchanges: 0.25% maker/taker typical (Bitkub).
    # Capital gains tax-exempt 2025-2029.
    "crypto":       {"commission_oneway": 0.0025, "slippage_oneway": 0.0020},

    # FX: not directly investable, used only as feature/benchmark
    "fx_macro":     {"commission_oneway": 0.0000, "slippage_oneway": 0.0000},
}


if __name__ == "__main__":
    print(f"Total asset classes: {len(UNIVERSE)}")
    print(f"Total tickers:       {len(get_all_tickers())}")
    for cls, items in UNIVERSE.items():
        print(f"  {cls:14s} {len(items):3d} tickers")
