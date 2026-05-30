"""
Pre-Market Data Service
Fetches market status, Nifty 50 summary, global indices, macro data,
and pre-market cues for analysis when NSE option chain is unavailable.
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
    """Fetch NSE market status and Nifty 50 summary."""
    try:
        session = _get_nse_session()
        url = f"{NSE_BASE}/api/equity-stockIndices?index=NIFTY%2050"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        market_status = data.get("marketStatus", {})
        metadata = data.get("metadata", {})
        index_data = data.get("data", [])

        nifty_info = None
        for item in index_data:
            if item.get("symbol") == "NIFTY 50":
                nifty_info = item
                break

        if nifty_info is None:
            nifty_info = metadata

        return {
            "is_open": market_status.get("marketStatus", "Close").upper() == "OPEN",
            "market_message": market_status.get("marketStatusMessage", "Unknown"),
            "trade_date": market_status.get("tradeDate", ""),
            "last_price": nifty_info.get("lastPrice") or metadata.get("last", 0),
            "previous_close": nifty_info.get("previousClose") or metadata.get("previousClose", 0),
            "open": nifty_info.get("open") or metadata.get("open", 0),
            "day_high": nifty_info.get("dayHigh") or metadata.get("high", 0),
            "day_low": nifty_info.get("dayLow") or metadata.get("low", 0),
            "change": nifty_info.get("change") or metadata.get("change", 0),
            "change_percent": nifty_info.get("pChange") or metadata.get("percChange", 0),
            "volume": nifty_info.get("totalTradedVolume") or metadata.get("totalTradedVolume", 0),
            "value": nifty_info.get("totalTradedValue") or metadata.get("totalTradedValue", 0),
            "year_high": nifty_info.get("yearHigh") or metadata.get("yearHigh", 0),
            "year_low": nifty_info.get("yearLow") or metadata.get("yearLow", 0),
            "near_52w_high": nifty_info.get("nearWKH", 0),
            "near_52w_low": nifty_info.get("nearWKL", 0),
            "per_change_30d": nifty_info.get("perChange30d") or metadata.get("perChange30d", 0),
            "per_change_365d": nifty_info.get("perChange365d") or metadata.get("perChange365d", 0),
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
                last_close = hist["Close"].iloc[-1]
                prev_close = hist["Close"].iloc[-2]
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
    """Fetch Nifty futures data from NSE."""
    try:
        session = _get_nse_session()
        url = f"{NSE_BASE}/api/quote-derivative?symbol=NIFTY"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        fut_data = data.get("futures", [])
        if fut_data:
            nearest = min(fut_data, key=lambda x: x.get("expiryDate", "9999-12-31"))
            return {
                "last_price": round(float(nearest.get("lastPrice", 0)), 2),
                "open": round(float(nearest.get("openPrice", 0)), 2),
                "high": round(float(nearest.get("highPrice", 0)), 2),
                "low": round(float(nearest.get("lowPrice", 0)), 2),
                "prev_close": round(float(nearest.get("prevClose", 0)), 2),
                "volume": nearest.get("numberOfContractsTraded", 0),
                "oi": nearest.get("openInterest", 0),
                "change": round(float(nearest.get("change", 0)), 2),
                "change_percent": round(float(nearest.get("pChange", 0)), 2),
                "expiry": nearest.get("expiryDate", ""),
            }
    except Exception as e:
        print(f"[PreMarket] Nifty futures error: {e}")
    return None


def get_advances_declines():
    """Fetch Nifty 50 advances/declines from NSE."""
    try:
        session = _get_nse_session()
        url = f"{NSE_BASE}/api/equity-stockIndices?index=NIFTY%2050"
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        advance = data.get("advance", {})
        if advance:
            return {
                "advances": advance.get("advances", 0),
                "declines": advance.get("declines", 0),
                "unchanged": advance.get("unchanged", 0),
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
            last = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2]
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
        # Yahoo's USDINR=X seems to have odd values, try a different approach
        # Use NSE API for USDINR if possible, otherwise skip
        ticker = yf.Ticker("USDINR=X")
        info = ticker.info
        price = info.get("regularMarketPrice")
        prev = info.get("previousClose")
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
            latest = data[0]
            return {
                "fii_buy": latest.get("fiiBuy", 0),
                "fii_sell": latest.get("fiiSell", 0),
                "fii_net": latest.get("fiiNet", 0),
                "dii_buy": latest.get("diiBuy", 0),
                "dii_sell": latest.get("diiSell", 0),
                "dii_net": latest.get("diiNet", 0),
                "date": latest.get("date", ""),
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
        "timestamp": datetime.now().isoformat(),
    }
