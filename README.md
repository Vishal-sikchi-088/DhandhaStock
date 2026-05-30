# Nifty 50 Options & Futures Analysis Dashboard

A research and risk-control assistant for Nifty 50 options and futures analysis. The app **only uses live/real data** — no demo mode, no simulated data. When markets are open, it analyzes real option chains from NSE India. When markets are closed, it performs deep pre-market analysis using technical patterns, global cues, news sentiment, and AI-driven narrative generation to set up trades for the next session.

> **SEBI Warning:** 93% of individual F&O traders lost money in FY22–FY24. This software is a research and risk-control assistant only. It does not guarantee profits or provide investment advice. Trading in derivatives carries substantial risk of loss.

## What Makes This Different

- **No Demo Mode:** Every number you see is from real market data
- **Pre-Market Intelligence:** When NSE is closed, the system still analyzes global markets, chart patterns, news, and macro cues to predict the next session's opening and set up limit-order trades
- **Chart Pattern AI:** Automatically detects double tops/bottoms, triangles, channels, flags, and trend structure from 6 months of real Nifty 50 historical data
- **Multi-Factor Scoring:** Only emits trades when technicals, global cues, news sentiment, and chart patterns all align

## Features

### When Market is OPEN (Mon-Fri, 9:15–3:30 PM IST)
- **Live Option Chain** from NSE India: Strike-wise CE/PE OI, change in OI, volume, IV, premiums
- **Trend Panel:** Bullish/bearish/sideways with strength meter, PCR, max pain, futures basis
- **AI Trade Panel:** Entry, stop loss, target 1, target 2, quantity, R:R, estimated probability
- **Support/Resistance:** From highest OI concentrations and change in OI

### When Market is CLOSED (Evenings, Weekends, Holidays)
- **Pre-Market Narrative:** AI-generated briefing on expected opening gap, global cues, and technical context
- **Global Cues Panel:** S&P 500, Dow, Nasdaq, Nikkei, Hang Seng, FTSE, DAX, Gold, Crude Oil — all live
- **Chart Pattern Analysis:**
  - Moving averages (SMA 20/50/200, EMA 20)
  - RSI (14-period)
  - Pattern detection: Double Top/Bottom, Ascending/Descending/Symmetrical Triangles, Rising/Falling Channels, Bull/Bear Flags
  - Key support/resistance from swing points, round numbers, and MAs
  - Volume vs average analysis
- **News & Sentiment AI:** Contextual headlines generated from real market conditions with sentiment scoring and event-risk detection
- **Next-Session Trade Setup:** Limit orders and bracket orders positioned at key technical levels for the upcoming open

### Always Available
- **Trade History:** Saved trades with market conditions, performance summary, review capability
- **Settings:** Capital, max risk per trade, daily loss limit, instrument preference
- **Risk Management:** Auto-calculated position sizing, R:R validation, max risk enforcement

## Tech Stack

- **Backend:** Python Flask
- **Live Data Sources:**
  - NSE India API (option chain, futures, market status, advances/declines) via `curl_cffi`
  - Yahoo Finance (Nifty 50 spot + historical OHLC, global indices, India VIX, crude oil)
- **Analysis:** Pandas + NumPy for technical indicators and pattern detection
- **Database:** SQLite
- **Frontend:** HTML, CSS, JavaScript (vanilla, mobile-responsive dark theme)

## How to Run

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the app:**
   ```bash
   python app.py
   ```

3. **Open in browser:**
   ```
   http://127.0.0.1:5050
   ```

## Project Structure

```
.
├── app.py                      # Flask application & API routes
├── requirements.txt            # Python dependencies
├── services/
│   ├── database.py             # SQLite operations
│   ├── nse_client.py           # NSE India API client
│   ├── premarket_data.py       # Global indices, NSE status, macro data
│   ├── chart_analysis.py       # Technical analysis & pattern detection
│   ├── news_ai.py              # News generation, sentiment, AI narrative
│   ├── market_data.py          # Routes live vs pre-market data
│   ├── analysis.py             # Option chain analysis
│   ├── ai_reasoning.py         # Trade generation engine (open + pre-market)
│   └── risk_manager.py         # Risk validation & position sizing
├── templates/
│   ├── base.html               # Base layout
│   ├── dashboard.html          # Main dashboard
│   ├── history.html            # Trade history page
│   └── settings.html           # Settings page
├── static/
│   ├── css/style.css           # Dark theme, mobile-friendly
│   └── js/dashboard.js         # Frontend interactivity
└── data/
    └── trades.db               # SQLite database (auto-created)
```

## How the Analysis Works

### Open Market Mode
1. Fetches live option chain from NSE India
2. Analyzes OI concentration, change in OI, PCR, max pain
3. Checks futures-spot basis for directional bias
4. Validates against VIX and expiry risk
5. Scores setup (0-100). Trade only if score ≥ 55.

### Pre-Market Mode
1. Fetches Nifty 50 close, global indices, futures, VIX
2. Downloads 6 months of historical data from Yahoo Finance
3. Runs technical analysis: MAs, RSI, swing points, patterns
4. Generates contextual news from market conditions
5. AI narrative synthesizes: estimated opening gap, key levels, directional bias
6. Scores setup (0-100) using technicals + globals + news. Trade only if score ≥ 55.
7. Trade is set as LIMIT/BRACKET order for next session

### Trade Rejection Rules
The system says **NO TRADE** when:
- Signals conflict (e.g., bullish tech + bearish news)
- Risk-reward below 1:1.2
- Option-chain levels unclear (open market)
- Large gap expected (>100 pts) with high slippage risk (pre-market)
- Event/news risk too high
- Expiry-day gamma risk excessive

## Data Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   NSE India     │     │  Yahoo Finance  │     │  AI Engine      │
│  (Option Chain) │     │ (Spot + Global) │     │ (Reasoning)     │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                      market_data.py (Router)                     │
│  Market OPEN → Live option chain + all pre-market data          │
│  Market CLOSED → Pre-market analysis only                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ai_reasoning.py (Engine)                      │
│  Open mode: OI + PCR + Max Pain + Basis + VIX scoring           │
│  Pre-market: Chart + Global + News + Gap estimation scoring     │
└─────────────────────────────────────────────────────────────────┘
```

## Risk Management

- Set your **capital** and **max risk per trade** in Settings
- The system calculates suggested **quantity** so your stop-loss hit stays within your risk limit
- Every trade shows **estimated probability** (heuristic score based on rule alignment, NOT a guarantee)
- Each recommendation includes **invalidation scenarios**
- Pre-market trades are marked as **LIMIT / BRACKET** orders for the next session

## Disclaimer

This application is for **educational and research purposes only**. Past performance does not guarantee future results. Always do your own analysis and consult a SEBI-registered investment advisor before trading.
