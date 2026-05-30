"""
NSE India API Client + Yahoo Finance Backup
Fetches live option chain, futures, spot, and VIX data.

Strategy:
1. Try NSE India API using curl_cffi (bypasses Cloudflare protection).
2. Use Yahoo Finance as backup for spot price.
3. On weekends/market holidays when NSE returns empty data, fall back to demo mode.
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
OPTION_CHAIN_URL_V3 = f"{NSE_BASE}/api/option-chain-v3?type=Indices&symbol=NIFTY"
FUTURES_URL = f"{NSE_BASE}/api/quote-derivative?symbol=NIFTY"
INDICES_URL = f"{NSE_BASE}/api/allIndices"

# Cache discovered option-chain data to avoid probing on every poll
_OC_DISCOVERY_CACHE = {"data": None, "ts": 0}
_OC_DISCOVERY_TTL = 14400  # 4 hours


def _option_chain_v3_url(expiry):
    return f"{OPTION_CHAIN_URL_V3}&expiry={expiry}"


def _discover_option_chain(client):
    """Probe a few upcoming dates to find a valid expiry and return the raw response."""
    global _OC_DISCOVERY_CACHE
    now = time.time()
    cached = _OC_DISCOVERY_CACHE.get("data")
    if cached and (now - _OC_DISCOVERY_CACHE.get("ts", 0)) < _OC_DISCOVERY_TTL:
        return cached

    today = datetime.now()
    for i in range(7):
        candidate = today + timedelta(days=i)
        expiry_str = candidate.strftime("%d-%b-%Y")
        url = _option_chain_v3_url(expiry_str)
        data = client._get(url)
        if data and data.get("records", {}).get("data"):
            _OC_DISCOVERY_CACHE = {"data": data, "ts": now}
            return data

    return None

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
            # curl_cffi impersonate supplies browser headers, but we merge
            # our custom Referer / Accept so NSE sees the right context.
            self.session.headers.update(HEADERS)
        else:
            self.session = curl_requests.Session()
            self.session.headers.update(HEADERS)
        # Inject saved cookies if available
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
            # Prime the base domain
            resp = self.session.get(NSE_BASE, timeout=10)
            if resp.status_code == 200:
                # NSE option-chain API often needs cookies from the option-chain page itself
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
                # NSE returns {} on weekends/holidays
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
        data = _discover_option_chain(self)
        if not data or "records" not in data:
            return None

        records = data["records"]
        underlying = records.get("underlyingValue", 0)
        expiry_dates = records.get("expiryDates", [])
        all_data = records.get("data", [])

        if not expiry_dates or not all_data:
            return None

        nearest_expiry = expiry_dates[0]
        # v3 uses "expiryDates" (plural) at the item level instead of "expiryDate"
        expiry_data = [d for d in all_data if d.get("expiryDates") == nearest_expiry]
        if not expiry_data:
            return None

        expiry_data.sort(key=lambda x: x.get("strikePrice", 0))
        strikes = []
        total_ce_oi = 0
        total_pe_oi = 0
        total_ce_vol = 0
        total_pe_vol = 0

        atm_strike = round(underlying / 50) * 50

        for item in expiry_data:
            strike = item.get("strikePrice", 0)
            ce = item.get("CE", {}) or {}
            pe = item.get("PE", {}) or {}

            ce_oi = ce.get("openInterest", 0) or 0
            ce_oi_change = ce.get("changeinOpenInterest", 0) or 0
            ce_volume = ce.get("totalTradedVolume", 0) or 0
            ce_iv = ce.get("impliedVolatility", 0) or 0
            ce_premium = ce.get("lastPrice", 0) or 0

            pe_oi = pe.get("openInterest", 0) or 0
            pe_oi_change = pe.get("changeinOpenInterest", 0) or 0
            pe_volume = pe.get("totalTradedVolume", 0) or 0
            pe_iv = pe.get("impliedVolatility", 0) or 0
            pe_premium = pe.get("lastPrice", 0) or 0

            total_ce_oi += ce_oi
            total_pe_oi += pe_oi
            total_ce_vol += ce_volume
            total_pe_vol += pe_volume

            strikes.append({
                "strike": strike,
                "ce_oi": ce_oi,
                "ce_oi_change": ce_oi_change,
                "ce_volume": ce_volume,
                "ce_iv": round(ce_iv, 2),
                "ce_premium": round(ce_premium, 2),
                "pe_oi": pe_oi,
                "pe_oi_change": pe_oi_change,
                "pe_volume": pe_volume,
                "pe_iv": round(pe_iv, 2),
                "pe_premium": round(pe_premium, 2),
                "is_atm": strike == atm_strike,
                "is_nearby": abs(strike - atm_strike) <= 200
            })

        sorted_ce = sorted(strikes, key=lambda x: x["ce_oi"], reverse=True)
        sorted_pe = sorted(strikes, key=lambda x: x["pe_oi"], reverse=True)
        resistance = sorted_ce[0]["strike"] if sorted_ce else atm_strike + 100
        support = sorted_pe[0]["strike"] if sorted_pe else atm_strike - 100

        # Max pain
        max_pain_strike = atm_strike
        min_diff = float('inf')
        for test_strike in [s["strike"] for s in strikes]:
            total_value = 0
            for opt in strikes:
                if opt["strike"] <= test_strike:
                    total_value += opt["ce_oi"] * max(0, test_strike - opt["strike"])
                if opt["strike"] >= test_strike:
                    total_value += opt["pe_oi"] * max(0, opt["strike"] - test_strike)
            if total_value < min_diff:
                min_diff = total_value
                max_pain_strike = test_strike

        pcr_oi = round(total_pe_oi / max(total_ce_oi, 1), 3)
        pcr_vol = round(total_pe_vol / max(total_ce_vol, 1), 3)

        try:
            exp_dt = datetime.strptime(nearest_expiry, "%d-%b-%Y")
            now = datetime.now()
            days_to_expiry = max(1, (exp_dt - now).days)
        except Exception:
            days_to_expiry = 7

        return {
            "spot": round(underlying, 2),
            "futures": None,
            "atm_strike": atm_strike,
            "strikes": strikes,
            "support": support,
            "resistance": resistance,
            "pcr_oi": pcr_oi,
            "pcr_volume": pcr_vol,
            "max_pain": max_pain_strike,
            "total_ce_oi": total_ce_oi,
            "total_pe_oi": total_pe_oi,
            "vix": None,
            "expiry_date": nearest_expiry,
            "days_to_expiry": days_to_expiry,
            "timestamp": datetime.now().isoformat(),
            "data_source": "NSE_LIVE"
        }

    def get_futures_price(self):
        data = self._get(FUTURES_URL)
        if not data:
            return None
        try:
            fut_data = data.get("futures", [])
            if fut_data:
                nearest = min(fut_data, key=lambda x: x.get("expiryDate", "9999-12-31"))
                return round(float(nearest.get("lastPrice", 0)), 2)
        except Exception as e:
            print(f"[NSE] Futures parse error: {e}")
        return None

    def get_indices(self):
        return self._get(INDICES_URL)


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
    Tries NSE first; uses Yahoo Finance for missing pieces; returns None if no option chain.
    """
    client = get_nse_client()
    chain = client.get_option_chain()

    if chain is None:
        print("[MarketData] NSE option chain unavailable (market closed or API blocked).")
        return None

    # Supplementary data
    futures = client.get_futures_price()
    yf_spot = get_yf_spot()
    yf_vix = get_yf_vix()

    spot = chain["spot"] or yf_spot
    if spot is None:
        spot = 22450.0

    if futures is None:
        futures = round(spot + 15.0, 2)

    vix = chain["vix"] or yf_vix
    if vix is None:
        vix = 14.5

    chain["spot"] = spot
    chain["futures"] = futures
    chain["vix"] = vix

    return chain
