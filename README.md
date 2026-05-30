# Nifty 50 Professional Options Trading AI

An **institutional-grade** research and risk-control assistant for Nifty 50 options and futures analysis. Built for serious traders who demand professional-grade analysis, risk management, and trade execution discipline.

> **SEBI Warning:** 93% of individual F&O traders lost money in FY22–FY24. This software is a research and risk-control assistant only. It does not guarantee profits or provide investment advice. Trading in derivatives carries substantial risk of loss.

---

## What Makes This Different

- **No Demo Mode:** Every number you see is from real market data (NSE India + Yahoo Finance)
- **Institutional Analysis Framework:** Smart Money Concepts (SMC/ICT), Volume Profile, VWAP, Deep OI Analysis
- **6-Step Decision Engine:** Market Structure → Multi-Timeframe → Option Chain → Volatility → Institutional Flow → Trade Decision
- **Probability Engine:** Weighted confluence scoring across 7 factors. Trade ONLY emitted when probability ≥ 70%
- **Live Trade Monitoring:** Auto-track P&L, suggest HOLD/EXIT/PARTIAL BOOK/TRAIL SL based on real-time conditions
- **Pre-Market Intelligence:** When NSE is closed, analyzes global markets, chart patterns, news sentiment, and AI narrative

---

## Features

### When Market is OPEN (Mon-Fri, 9:15–3:30 PM IST)
- **Live Option Chain** from NSE India: Strike-wise CE/PE OI, change in OI, volume, IV, premiums
- **Deep OI Analysis:** Long Buildup, Short Buildup, Long Unwinding, Short Covering classification per strike
- **SMC / ICT Analysis:** Market Structure (BOS/CHoCH), Order Blocks, Fair Value Gaps, Liquidity Zones, Inducement
- **Volume Profile & VWAP:** POC, Value Area, VWAP with standard deviation bands, Volume Delta
- **Institutional Flow:** FII/DII trends, Futures OI classification, cumulative bias scoring
- **Probability Engine:** 7-factor weighted scoring. Trade only if score ≥ 70
- **Strike Selector:** Delta-optimized strike selection with liquidity filter and gamma risk assessment
- **Strategy Selector:** Recommends Long CE/PE, Spreads, Straddles, Iron Condor based on VIX + DTE + bias
- **AI Trade Panel:** Entry, stop loss, target 1/2/3, quantity, R:R, estimated probability, trade quality score

### When Market is CLOSED (Evenings, Weekends, Holidays)
- **Pre-Market Narrative:** AI-generated briefing on expected opening gap, global cues, technical context
- **Global Cues Panel:** S&P 500, Dow, Nasdaq, Nikkei, Hang Seng, FTSE, DAX, Gold, Crude Oil — all live
- **Chart Pattern Analysis:** Moving averages, RSI, MACD, ATR, pattern detection across 4 timeframes (Daily, 1H, 15M, 5M)
- **News & Sentiment AI:** Contextual headlines with sentiment scoring and event-risk detection
- **Next-Session Trade Setup:** Limit orders and bracket orders positioned at key technical levels

### Always Available
- **Trade History:** Saved trades with market conditions, performance summary, review capability
- **Settings:** Capital, max risk per trade, daily loss limit, instrument preference
- **Risk Management:** Auto-calculated position sizing, R:R validation, max risk enforcement
- **Live Trade Monitor:** Track active trades, auto-suggest actions, P&L tracking

---

## Tech Stack

- **Backend:** Python Flask
- **Live Data Sources:**
  - NSE India API (option chain, futures, market status, FII/DII) via `curl_cffi`
  - Yahoo Finance (Nifty 50 spot + historical OHLC 5m/15m/1h/1d, global indices, India VIX, crude oil)
- **Analysis:** Pandas + NumPy for technical indicators, pattern detection, volume profile, VWAP
- **Database:** SQLite (trades, active trades, trade logs, OI snapshots, futures snapshots, IV history)
- **Frontend:** HTML, CSS, JavaScript (vanilla, mobile-responsive dark theme)

---

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

---

## Project Structure

```
.
├── app.py                          # Flask application & API routes
├── requirements.txt                # Python dependencies
├── services/
│   ├── database.py                 # SQLite operations (trades, active_trades, logs, snapshots)
│   ├── nse_client.py               # NSE India API client
│   ├── premarket_data.py           # Global indices, NSE status, macro data, historical OHLC
│   ├── chart_analysis.py           # Technical analysis & pattern detection (4 timeframes)
│   ├── smc_analysis.py             # Smart Money Concepts / ICT (BOS, CHoCH, OB, FVG, Liquidity)
│   ├── volume_profile_vwap.py      # VWAP, Volume Profile, Volume Delta
│   ├── oi_analyzer.py              # Deep OI analysis (buildup classification, PCR trend, walls)
│   ├── institutional_flow.py       # FII/DII trends, futures OI classification
│   ├── news_ai.py                  # News generation, sentiment, AI narrative
│   ├── market_data.py              # Routes live vs pre-market data
│   ├── analysis.py                 # Option chain analysis
│   ├── ai_reasoning.py             # 6-step institutional trade engine
│   ├── probability_engine.py       # Confluence scoring & trade quality
│   ├── strike_selector.py          # Optimal strike selection with delta/liquidity/gamma
│   ├── strategy_selector.py        # Options strategy recommendation
│   ├── trade_monitor.py            # Live trade monitoring & action engine
│   └── risk_manager.py             # Risk validation & position sizing
├── templates/
│   ├── base.html                   # Base layout
│   ├── dashboard.html              # Main dashboard (institutional layout)
│   ├── history.html                # Trade history page
│   └── settings.html               # Settings page
├── static/
│   ├── css/style.css               # Dark terminal theme
│   └── js/dashboard.js             # Frontend interactivity
└── data/
    └── trades.db                   # SQLite database (auto-created)
```

---

## The 6-Step Analysis Framework

### Step 1: Market Structure (SMC/ICT)
- Break of Structure (BOS) and Change of Character (CHoCH)
- Order Blocks, Fair Value Gaps, Liquidity Zones
- Swing point analysis and inducement detection

### Step 2: Multi-Timeframe Analysis
- Daily, 1 Hour, 15 Minute, 5 Minute timeframes
- Trend alignment scoring across all timeframes
- MACD, RSI, SMA/EMA confluence

### Step 3: Option Chain Deep Analysis
- Maximum Call/Put OI with strength scoring
- OI Change Classification: Long Buildup, Short Buildup, Long Unwinding, Short Covering
- PCR trend, Max Pain, OI walls

### Step 4: Volatility Analysis
- India VIX environment assessment
- Implied Volatility percentile
- Days-to-expiry risk (gamma/theta)

### Step 5: Institutional Activity
- FII/DII net flow trends
- Futures OI classification
- Cumulative institutional bias score

### Step 6: Trade Decision
- **Probability Engine:** 7-factor weighted scoring (0-100)
- **Threshold:** Trade ONLY emitted when probability ≥ 70%
- **Trade Quality Score:** 0-100 with A/B/C/D/F grading
- **Risk Management:** Auto position sizing, R:R validation (min 1:1.2)

---

## Trade Output Format

The system produces institutional-grade trade recommendations:

```
Market Bias: BULLISH / BEARISH / NEUTRAL
Confidence: XX%

Best Trade:
  Instrument: NIFTY
  Trade Type: CALL / PUT
  Strike: XXXXX
  Expiry: Nearest Weekly
  Entry: XXXXX
  Stop Loss: XXXXX
  Target 1: XXXXX
  Target 2: XXXXX
  Target 3: XXXXX
  Risk Reward: 1:X
  Expected Holding Time: XX Minutes
  Probability: XX%

Trade Quality Score: XX/100 (Grade: X)
Best Action: BUY CALL / BUY PUT / WAIT
```

---

## Live Trade Monitoring

After activating a trade:
- **Auto-tracking:** Monitors spot, premium, P&L every 30 seconds
- **Smart Actions:**
  - **HOLD:** Conditions favorable
  - **EXIT:** Stop loss hit, structure broke, or VIX spike
  - **PARTIAL BOOK:** Target 1 hit — book 50% profits
  - **TRAIL SL:** Target 1+ hit — move stop to protect remaining

---

## Data Limitations (Transparent)

1. **Intraday data:** Yahoo Finance provides 15-minute delayed 5m/15m/1h data
2. **VWAP/Volume Profile:** Calculated on available 5m data, not tick-level
3. **OI Classification:** Requires comparing two snapshots; classified on 30-second polling
4. **Probability:** Heuristic confluence scoring — transparent, explainable, not backtested ML
5. **Option Greeks:** Delta is approximated (not from broker API). For exact Greeks, integrate with broker API

---

## Risk Management Rules

1. Never trade below 70% probability
2. Never take R:R below 1:1.2
3. Max 1-2% capital risk per trade
4. Never average losing trades
5. Never move stop loss further away
6. Protect capital first

---

## Disclaimer

This application is for **educational and research purposes only**. Past performance does not guarantee future results. Always do your own analysis and consult a SEBI-registered investment advisor before trading.
