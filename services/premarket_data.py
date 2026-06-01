"""
Pre-Market Data Service
Fetches market status, Nifty 50 summary, global indices, macro data,
and pre-market cues for analysis.

NOTE (Jun 2026): NSE India deprecated several public API endpoints:
- /api/equity-stockIndices (returns 404)
- /api/quote-derivative (returns 404)
- /api/option-chain-indices (returns 404)

Working NSE endpoints used:
- /api/marketStatus
- /api/allIndices
- /api/fiidiiTradeReact
- /api/chart-databyindex

For option chain and futures, the app falls back to Yahoo Finance
spot price + estimates when NSE APIs are unavailable.
"""

import yfinance as yf
from curl_cffi import requests as curl_requests
from datetime import datetime, timedelta

NSE_BASE = "https://www.nseindia.com"

# Singleton session
_nse_session = None

def _get_nse_session():
    global _nse_session
    if _nse_session is None:
        _nse_session = curl_requests.Session(impersonate='chrome')
    return _nse_session


def get_nse_market_status():
    """Fetch NSE market status and Nifty 50 summary from working endpoints."""
    try:
        session = _get_nse_session()

        # Use the working marketStatus endpoint
        url = f"{NSE_BASE}/api/marketStatus"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        market_states = data.get("marketState", [])
        capital_market = None
        for m in market_states:
            if m.get("market") == "Capital Market":
                capital_market = m
                break

        if capital_market is None and market_states:
            capital_market = market_states[0]

        # Also fetch allIndices for additional Nifty 50 data
        nifty_detail = {}
        try:
            resp2 = session.get(f"{NSE_BASE}/api/allIndices", timeout=15)
            if resp2.status_code == 200:
                indices = resp2.json()
                for idx in indices.get("data", []):
                    if idx.get("index") == "NIFTY 50":
                        nifty_detail = idx
                        break
        except Exception:
            pass

        last = capital_market.get("last", 0) or nifty_detail.get("last", 0)
        prev = nifty_detail.get("previousClose", 0)
        change = capital_market.get("variation", 0) or (last - prev if last and prev else 0)
        change_pct = capital_market.get("percentChange", 0) or ((change / prev) * 100 if prev else 0)

        return {
            "is_open": (capital_market.get("marketStatus", "") or "").upper() == "OPEN",
            "market_message": capital_market.get("marketStatusMessage", "Unknown"),
            "trade_date": capital_market.get("tradeDate", ""),
            "last_price": last,
            "previous_close": prev,
            "open": nifty_detail.get("open", 0),
            "day_high": nifty_detail.get("high", 0),
            "day_low": nifty_detail.get("low", 0),
            "change": change,
            "change_percent": change_pct,
            "volume": nifty_detail.get("totalTradedVolume", 0),
            "value": 0,
            "year_high": nifty_detail.get("yearHigh", 0),
            "year_low": nifty_detail.get("yearLow", 0),
            "near_52w_high": nifty_detail.get("nearWKH", 0),
            "near_52w_low": nifty_detail.get("nearWKL", 0),
            "per_change_30d": nifty_detail.get("perChange30d", 0),
            "per_change_365d": nifty_detail.get("perChange365d", 0),
            "advances": nifty_detail.get("advances", 0),
            "declines": nifty_detail.get("declines", 0),
            "unchanged": nifty_detail.get("unchanged", 0),
            "pe": nifty_detail.get("pe", 0),
            "pb": nifty_detail.get("pb", 0),
        }
    except Exception as e:
        print(f"[PreMarket] NSE market status error: {e}")
        return None


def get_global_indices():
    """Fetch global market cues from Yahoo Finance."""
    symbols = {
        "S&P 500": "^GSPC",
        "Dow Jones": "^DJI",
        "Nasdaq": "^IXIC",
        "Nikkei 225": "^N225",
        "Hang Seng": "^HSI",
        "FTSE 100": "^FTSE",
        "DAX": "^GDAXI",
        "Gold": "GC=F",
        "Crude Oil": "CL=F",
    }

    results = []
    for name, symbol in symbols.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            if not hist.empty and len(hist) >= 2:
                last_close = float(hist["Close"].iloc[-1])
                prev_close = float(hist["Close"].iloc[-2])
                change = last_close - prev_close
                change_pct = (change / prev_close) * 100
                results.append({
                    "name": name,
                    "symbol": symbol,
                    "price": round(last_close, 2),
                    "change": round(change, 2),
                    "change_percent": round(change_pct, 2),
                    "trend": "up" if change > 0 else "down" if change < 0 else "flat"
                })
        except Exception as e:
            print(f"[PreMarket] {name} fetch error: {e}")

    return results


def get_nifty_futures_ohlc():
    """Fetch Nifty futures data from NSE.
    NOTE: NSE deprecated /api/quote-derivative in 2026. Returns None.
    """
    # NSE deprecated this endpoint. Futures data now requires broker API or paid data feed.
    # Returning None lets upstream code fall back to spot + estimated basis.
    return None


def get_advances_declines():
    """Fetch Nifty 50 advances/declines from working NSE endpoint."""
    try:
        session = _get_nse_session()
        url = f"{NSE_BASE}/api/allIndices"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("data", []):
            if item.get("index") == "NIFTY 50":
                return {
                    "advances": item.get("advances", 0),
                    "declines": item.get("declines", 0),
                    "unchanged": item.get("unchanged", 0),
                }
    except Exception as e:
        print(f"[PreMarket] A/D error: {e}")
    return None


def get_nifty_historical(period="6mo", interval="1d"):
    """Fetch Nifty 50 historical OHLC data from Yahoo Finance."""
    try:
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period=period, interval=interval)
        if not hist.empty:
            return hist
    except Exception as e:
        print(f"[PreMarket] Historical data error: {e}")
    return None


def get_india_vix():
    """Fetch India VIX from Yahoo Finance."""
    try:
        vix = yf.Ticker("^INDIAVIX")
        hist = vix.history(period="5d")
        if not hist.empty and len(hist) >= 2:
            last = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            return {
                "current": round(last, 2),
                "previous": round(prev, 2),
                "change": round(last - prev, 2),
                "change_percent": round(((last - prev) / prev) * 100, 2),
            }
    except Exception as e:
        print(f"[PreMarket] VIX error: {e}")
    return None


def get_usdinr():
    """Fetch USD/INR from Yahoo Finance."""
    try:
        ticker = yf.Ticker("USDINR=X")
        info = ticker.info
        price = info.get("regularMarketPrice")
        prev = info.get("previousClose")
        if price is not None:
            price = float(price)
        if prev is not None:
            prev = float(prev)
        if price and prev:
            # Sanity check - actual USD/INR is ~83-87
            if 70 < price < 110:
                return {
                    "current": round(price, 3),
                    "previous": round(prev, 3),
                    "change": round(price - prev, 3),
                    "change_percent": round(((price - prev) / prev) * 100, 2),
                }
    except Exception as e:
        print(f"[PreMarket] USDINR error: {e}")
    return None


def get_fii_dii_data():
    """Fetch FII/DII activity from NSE."""
    try:
        session = _get_nse_session()
        url = f"{NSE_BASE}/api/fiidiiTradeReact"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data and len(data) > 0:
            # Find FII and DII entries
            fii = next((x for x in data if "FII" in x.get("category", "")), None)
            dii = next((x for x in data if "DII" in x.get("category", "")), None)
            return {
                "fii_buy": float(fii.get("buyValue", 0)) if fii else 0,
                "fii_sell": float(fii.get("sellValue", 0)) if fii else 0,
                "fii_net": float(fii.get("netValue", 0)) if fii else 0,
                "dii_buy": float(dii.get("buyValue", 0)) if dii else 0,
                "dii_sell": float(dii.get("sellValue", 0)) if dii else 0,
                "dii_net": float(dii.get("netValue", 0)) if dii else 0,
                "date": fii.get("date", "") if fii else "",
            }
    except Exception as e:
        print(f"[PreMarket] FII/DII error: {e}")
    return None


def get_all_premarket_data():
    """Aggregate all pre-market data into a single dict."""
    market_status = get_nse_market_status()
    global_indices = get_global_indices()
    futures = get_nifty_futures_ohlc()
    ad = get_advances_declines()
    vix = get_india_vix()
    usdinr = get_usdinr()
    fii_dii = get_fii_dii_data()
    historical_daily = get_nifty_historical("6mo", "1d")
    historical_60m = get_nifty_historical("1mo", "60m")
    historical_15m = get_nifty_historical("5d", "15m")
    historical_5m = get_nifty_historical("5d", "5m")

    return {
        "market_status": market_status,
        "global_indices": global_indices,
        "nifty_futures": futures,
        "advances_declines": ad,
        "india_vix": vix,
        "usdinr": usdinr,
        "fii_dii": fii_dii,
        "historical_daily": historical_daily,
        "historical_60m": historical_60m,
        "historical_15m": historical_15m,
        "historical_5m": historical_5m,
        "timestamp": datetime.now().isoformat(),
    }
