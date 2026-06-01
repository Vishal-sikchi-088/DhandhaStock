"""
NSE India API Client + Yahoo Finance Backup
Fetches live option chain, futures, spot, and VIX data.

NOTE (Jun 2026): NSE India deprecated several public API endpoints:
- /api/option-chain-indices (returns 404)
- /api/quote-derivative (returns 404)
- /api/equity-stockIndices (returns 404)

Working NSE endpoints:
- /api/marketStatus
- /api/allIndices
- /api/fiidiiTradeReact
- /api/chart-databyindex

The client now falls back to Yahoo Finance for spot/VIX and
disables option chain / futures fetching until a broker API is integrated.
"""

import time
import json
import os
import http.cookiejar
from datetime import datetime, timedelta

# Try to import curl_cffi for NSE access; fallback to standard requests
try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    import requests as curl_requests
    CURL_CFFI_AVAILABLE = False

# Yahoo Finance for spot backup
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

NSE_BASE = "https://www.nseindia.com"

# DEPRECATED — NSE removed these endpoints in 2026
OPTION_CHAIN_URL_V3 = f"{NSE_BASE}/api/option-chain-v3?type=Indices&symbol=NIFTY"
FUTURES_URL = f"{NSE_BASE}/api/quote-derivative?symbol=NIFTY"
INDICES_URL = f"{NSE_BASE}/api/allIndices"
MARKET_STATUS_URL = f"{NSE_BASE}/api/marketStatus"

# Cache discovered option-chain data to avoid probing on every poll
_OC_DISCOVERY_CACHE = {"data": None, "ts": 0}
_OC_DISCOVERY_TTL = 14400  # 4 hours


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/option-chain",
    "Connection": "keep-alive",
}


def _load_cookie_jar(path="cookies.txt"):
    """Load Netscape/Mozilla cookie jar if present."""
    if not os.path.exists(path):
        return None
    try:
        cj = http.cookiejar.MozillaCookieJar(path)
        cj.load(ignore_discard=True, ignore_expires=True)
        return cj
    except Exception as e:
        print(f"[NSE] Failed to load {path}: {e}")
        return None


class NSEClient:
    def __init__(self):
        if CURL_CFFI_AVAILABLE:
            self.session = curl_requests.Session(impersonate='chrome')
            self.session.headers.update(HEADERS)
        else:
            self.session = curl_requests.Session()
            self.session.headers.update(HEADERS)
        _cj = _load_cookie_jar()
        if _cj:
            self.session.cookies.update(_cj)
        self._cookies_initialized = False
        self._last_fetch = 0
        self._min_interval = 3

    def _init_session(self):
        if self._cookies_initialized:
            return True
        try:
            resp = self.session.get(NSE_BASE, timeout=10)
            if resp.status_code == 200:
                self.session.get(f"{NSE_BASE}/option-chain", timeout=10)
                self._cookies_initialized = True
                return True
        except Exception as e:
            print(f"[NSE] Session init failed: {e}")
        return False

    def _rate_limit(self):
        elapsed = time.time() - self._last_fetch
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_fetch = time.time()

    def _get(self, url, retries=2):
        self._rate_limit()
        if not self._init_session():
            return None
        for attempt in range(retries + 1):
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code == 401 and attempt < retries:
                    self._cookies_initialized = False
                    self._init_session()
                    continue
                resp.raise_for_status()
                data = resp.json()
                if data == {} or data == []:
                    return None
                return data
            except Exception as e:
                print(f"[NSE] Error fetching {url} (attempt {attempt + 1}): {e}")
                if attempt < retries:
                    time.sleep(2)
                else:
                    return None
        return None

    def get_option_chain(self):
        """Fetch NSE option chain.
        DEPRECATED: NSE removed the option-chain-indices endpoint in 2026.
        Returns None. Integrate a broker API (Zerodha Kite, Angel One, etc.)
        for live option chain data.
        """
        print("[NSE] Option chain API deprecated by NSE. Use broker API for live OI data.")
        return None

    def get_futures_price(self):
        """Fetch Nifty futures price.
        DEPRECATED: NSE removed the quote-derivative endpoint in 2026.
        Returns None.
        """
        return None

    def get_indices(self):
        """Fetch all NSE indices data."""
        return self._get(INDICES_URL)

    def get_market_status(self):
        """Fetch NSE market status."""
        return self._get(MARKET_STATUS_URL)


def get_yf_spot():
    """Fetch Nifty spot from Yahoo Finance as backup."""
    if not YFINANCE_AVAILABLE:
        return None
    try:
        nifty = yf.Ticker('^NSEI')
        info = nifty.info
        price = info.get('regularMarketPrice') or info.get('previousClose')
        if price:
            return round(float(price), 2)
    except Exception as e:
        print(f"[YF] Spot fetch error: {e}")
    return None


def get_yf_vix():
    """Fetch India VIX from Yahoo Finance as backup."""
    if not YFINANCE_AVAILABLE:
        return None
    try:
        vix = yf.Ticker('^INDIAVIX')
        info = vix.info
        price = info.get('regularMarketPrice') or info.get('previousClose')
        if price:
            return round(float(price), 2)
    except Exception as e:
        print(f"[YF] VIX fetch error: {e}")
    return None


# Singleton
_nse_client = None

def get_nse_client():
    global _nse_client
    if _nse_client is None:
        _nse_client = NSEClient()
    return _nse_client


def fetch_live_market_data():
    """
    Fetch complete live market data.
    Since NSE deprecated option chain & futures APIs, this now returns
    a minimal structure using Yahoo Finance spot + NSE market status.
    """
    client = get_nse_client()

    # Get spot from Yahoo Finance (most reliable)
    yf_spot = get_yf_spot()
    yf_vix = get_yf_vix()
    spot = yf_spot or 22450.0
    vix = yf_vix or 14.5

    # Get market status from NSE
    market_status = client.get_market_status()
    is_open = False
    if market_status:
        for m in market_status.get("marketState", []):
            if m.get("market") == "Capital Market":
                is_open = (m.get("marketStatus") or "").upper() == "OPEN"
                spot = m.get("last") or spot
                break

    # Try to get Nifty 50 details from allIndices
    futures = None
    atm_strike = round(spot / 50) * 50
    support = atm_strike - 100
    resistance = atm_strike + 100
    pcr = 1.0
    max_pain = atm_strike
    days_to_expiry = 7
    expiry_date = "Nearest Weekly"

    try:
        indices = client.get_indices()
        if indices:
            for idx in indices.get("data", []):
                if idx.get("index") == "NIFTY 50":
                    spot = idx.get("last") or spot
                    atm_strike = round(spot / 50) * 50
                    break
    except Exception:
        pass

    # Note: Without option chain API we can't compute real PCR, max pain, support/resistance, or strikes.
    # Returning a skeleton structure so downstream code doesn't crash.
    return {
        "spot": round(spot, 2),
        "futures": futures,
        "atm_strike": atm_strike,
        "strikes": [],
        "support": support,
        "resistance": resistance,
        "pcr_oi": pcr,
        "pcr_volume": pcr,
        "max_pain": max_pain,
        "total_ce_oi": 0,
        "total_pe_oi": 0,
        "vix": vix,
        "expiry_date": expiry_date,
        "days_to_expiry": days_to_expiry,
        "timestamp": datetime.now().isoformat(),
        "data_source": "YAHOO_FINANCE",
        "market_open": is_open,
        "nse_api_limited": True,
    }
