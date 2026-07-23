"""Central configuration for the economic dashboard data pipeline.

Everything the pipeline fetches is declared here so the data set can be
tuned without touching the fetch logic. Tickers use Yahoo Finance symbols
(that is what ``yfinance`` speaks). Any ticker that fails to return data is
skipped gracefully and reported in the dashboard's "data notes" section, so
it is safe to add speculative symbols here.

Field reference for an instrument entry:
    label    : human-readable name shown on the dashboard
    ticker   : Yahoo Finance symbol
    unit      : suffix shown after the value ("", "%", "$", "₩" ...)
    decimals : how many decimals to show for the latest value
"""

# --- Global stock indices (time-series + tiles) ---------------------------
GLOBAL_INDICES = {
    "SP500":       {"label": "S&P 500",      "ticker": "^GSPC", "unit": "", "decimals": 2},
    "DOW":         {"label": "Dow Jones",    "ticker": "^DJI",  "unit": "", "decimals": 2},
    "NASDAQ":      {"label": "Nasdaq Comp.", "ticker": "^IXIC", "unit": "", "decimals": 2},
    "RUSSELL2000": {"label": "Russell 2000", "ticker": "^RUT",  "unit": "", "decimals": 2},
}

# --- FX & the Dollar index -------------------------------------------------
# NOTE: "KRW=X" is quoted as USD -> KRW (won per one US dollar).
FX_DOLLAR = {
    "DXY":    {"label": "Dollar Index (DXY)", "ticker": "DX-Y.NYB", "unit": "",  "decimals": 2},
    "USDKRW": {"label": "USD / KRW",          "ticker": "KRW=X",    "unit": "₩", "decimals": 1},
    "EURUSD": {"label": "EUR / USD",          "ticker": "EURUSD=X", "unit": "",  "decimals": 4},
    "USDJPY": {"label": "USD / JPY",          "ticker": "JPY=X",    "unit": "",  "decimals": 2},
    "USDCNY": {"label": "USD / CNY",          "ticker": "CNY=X",    "unit": "",  "decimals": 4},
}

# --- Commodities -----------------------------------------------------------
COMMODITIES = {
    "WTI":    {"label": "WTI Crude",   "ticker": "CL=F", "unit": "$", "decimals": 2},
    "BRENT":  {"label": "Brent Crude", "ticker": "BZ=F", "unit": "$", "decimals": 2},
    "GOLD":   {"label": "Gold",        "ticker": "GC=F", "unit": "$", "decimals": 1},
    "SILVER": {"label": "Silver",      "ticker": "SI=F", "unit": "$", "decimals": 2},
    "COPPER": {"label": "Copper",      "ticker": "HG=F", "unit": "$", "decimals": 3},
    "NATGAS": {"label": "Natural Gas", "ticker": "NG=F", "unit": "$", "decimals": 3},
}

# --- Global 10-year government bond yields ---------------------------------
# Yahoo coverage of foreign sovereign yields is patchy; missing ones are
# skipped and reported. Values are treated as percent.
GLOBAL_BONDS = {
    "US10Y": {"label": "US 10Y",      "ticker": "^TNX",     "unit": "%", "decimals": 3},
    "DE10Y": {"label": "Germany 10Y", "ticker": "^DE10Y",   "unit": "%", "decimals": 3},
    "JP10Y": {"label": "Japan 10Y",   "ticker": "^JP10Y",   "unit": "%", "decimals": 3},
    "GB10Y": {"label": "UK 10Y",      "ticker": "^GB10Y",   "unit": "%", "decimals": 3},
    "KR10Y": {"label": "Korea 10Y",   "ticker": "^KR10Y",   "unit": "%", "decimals": 3},
}

# --- Korean stock indices --------------------------------------------------
# KOSDAQ 150 has no reliable Yahoo index symbol, so the KODEX KOSDAQ150 ETF
# (229200.KS) is used as a proxy for its level/return.
KOREA_INDICES = {
    "KOSPI":    {"label": "KOSPI",        "ticker": "^KS11",     "unit": "", "decimals": 2},
    "KOSDAQ":   {"label": "KOSDAQ",       "ticker": "^KQ11",     "unit": "", "decimals": 2},
    "KOSPI200": {"label": "KOSPI 200",    "ticker": "^KS200",    "unit": "", "decimals": 2},
    "KOSDAQ150": {"label": "KOSDAQ 150*",  "ticker": "229200.KS", "unit": "", "decimals": 2},
}

# --- US Treasury yield curve (shape + trend) ------------------------------
# Yahoo exposes these constant-maturity points as indices. Some symbols quote
# the yield x10 (e.g. 42.5 for 4.25%); the pipeline normalizes that.
US_YIELD_CURVE = [
    {"label": "3M",  "ticker": "^IRX", "years": 0.25},
    {"label": "5Y",  "ticker": "^FVX", "years": 5},
    {"label": "10Y", "ticker": "^TNX", "years": 10},
    {"label": "30Y", "ticker": "^TYX", "years": 30},
]

# --- US sector map (SPDR Select Sector ETFs) ------------------------------
US_SECTORS = [
    {"name": "Technology",         "ticker": "XLK"},
    {"name": "Financials",         "ticker": "XLF"},
    {"name": "Health Care",        "ticker": "XLV"},
    {"name": "Cons. Discretionary","ticker": "XLY"},
    {"name": "Communication Svcs", "ticker": "XLC"},
    {"name": "Industrials",        "ticker": "XLI"},
    {"name": "Cons. Staples",      "ticker": "XLP"},
    {"name": "Energy",             "ticker": "XLE"},
    {"name": "Utilities",          "ticker": "XLU"},
    {"name": "Materials",          "ticker": "XLB"},
    {"name": "Real Estate",        "ticker": "XLRE"},
]

# --- Korea sector map (KODEX sector ETFs as proxies) ----------------------
# KRX does not publish free per-sector index history, so liquid KODEX sector
# ETFs stand in for the KOSPI/KOSDAQ industry groups. Edit freely; unknown
# codes are skipped and reported.
KR_SECTORS = [
    {"name": "Semiconductors",   "ticker": "091160.KS"},
    {"name": "Banks",            "ticker": "091170.KS"},
    {"name": "Autos",            "ticker": "091180.KS"},
    {"name": "Securities",       "ticker": "102970.KS"},
    {"name": "Energy & Chem.",   "ticker": "117460.KS"},
    {"name": "Transportation",   "ticker": "140710.KS"},
    {"name": "EV Battery",       "ticker": "305720.KS"},
    {"name": "Insurance",        "ticker": "140700.KS"},
    {"name": "Media & Telecom",  "ticker": "266360.KS"},
    {"name": "Machinery/Equip.", "ticker": "102960.KS"},
]

# --- Korean government bond yield curve via Bank of Korea ECOS -------------
# Optional. Set the ECOS_API_KEY environment variable (free key from
# https://ecos.bok.or.kr) to enable. Item codes belong to ECOS statistic
# table 817Y002 (market interest rates, daily). If disabled or the call
# fails, the Korean curve section is simply omitted.
ECOS_STAT_CODE = "817Y002"
ECOS_KR_CURVE = [
    {"label": "1Y",  "item": "010200000", "years": 1},
    {"label": "3Y",  "item": "010210000", "years": 3},
    {"label": "5Y",  "item": "010220000", "years": 5},
    {"label": "10Y", "item": "010230000", "years": 10},
    {"label": "20Y", "item": "010240000", "years": 20},
    {"label": "30Y", "item": "010250000", "years": 30},
]

# History window pulled from Yahoo for every ticker (drives sparklines,
# 7-day series and the yield-curve "week ago / month ago" trend lines).
HISTORY_PERIOD = "3mo"
