"""
Market Data Service
Provides Nifty 50 data from live sources only.

When markets are OPEN: fetches real option chain from NSE.
When markets are CLOSED: fetches pre-market data (Nifty summary, global cues, chart analysis, news).
"""

import time
from datetime import datetime

from .nse_client import fetch_live_market_data
from .premarket_data import get_all_premarket_data
from .chart_analysis import analyze_chart
from .news_ai import generate_market_news_context, analyze_news_sentiment, get_ai_market_narrative

# Simple TTL cache for live option chain to avoid hammering NSE on every poll
_OPTION_CHAIN_CACHE = {"data": None, "ts": 0}
_OPTION_CHAIN_TTL = 10  # seconds

def generate_option_chain():
    """
    Fetch live option chain from NSE India.
    Returns None when market is closed or NSE is unreachable.
    Cached for {_OPTION_CHAIN_TTL}s to reduce API load.

    NOTE (Jun 2026): NSE deprecated option-chain-indices API.
    This now returns Yahoo Finance spot data with empty strikes
    when market is open but NSE option chain is unavailable.
    """
    global _OPTION_CHAIN_CACHE
    now = time.time()
    if _OPTION_CHAIN_CACHE["data"] is not None and (now - _OPTION_CHAIN_CACHE["ts"]) < _OPTION_CHAIN_TTL:
        return _OPTION_CHAIN_CACHE["data"]

    try:
        live_data = fetch_live_market_data()
        if live_data is not None:
            _OPTION_CHAIN_CACHE = {"data": live_data, "ts": now}
            return live_data
    except Exception as e:
        print(f"[MarketData] Live option chain error: {e}")

    _OPTION_CHAIN_CACHE = {"data": None, "ts": now}
    return None


def get_news_headlines():
    """Generate contextual news from actual market data."""
    premarket = get_all_premarket_data()
    market_status = premarket.get("market_status") or {}
    global_indices = premarket.get("global_indices", [])

    # Basic chart analysis for context
    historical = premarket.get("historical")
    chart = analyze_chart(historical) if historical is not None else {"bias": "neutral", "patterns": [], "rsi": 50}

    return generate_market_news_context(market_status, global_indices, chart)


def get_market_summary():
    """
    Get comprehensive market summary.
    When open: includes option chain data.
    When closed: includes pre-market analysis.
    """
    premarket = get_all_premarket_data()
    market_status = premarket.get("market_status")
    global_indices = premarket.get("global_indices", [])
    futures = premarket.get("nifty_futures")
    vix = premarket.get("india_vix")
    ad = premarket.get("advances_declines")
    historical = premarket.get("historical")

    # Chart analysis
    chart = analyze_chart(
        premarket.get("historical_daily"),
        premarket.get("historical_60m"),
        premarket.get("historical_15m")
    ) if premarket else None

    # News
    news = generate_market_news_context(market_status, global_indices, chart or {})
    news_analysis = analyze_news_sentiment(news)

    # AI narrative
    narrative = get_ai_market_narrative(premarket, chart or {}, news_analysis)

    is_open = market_status.get("is_open", False) if market_status else False

    if is_open:
        # Market is open - try to get option chain too
        chain = generate_option_chain()
        if chain and chain.get("strikes"):
            # Full option chain available
            spot = chain.get("spot", 0)
            futures_price = chain.get("futures", 0) or (futures.get("last_price") if futures else spot)
            pcr = chain.get("pcr_oi", 1.0)

            if futures_price > spot + 20 and pcr > 1.1:
                trend = "bullish"
            elif futures_price < spot - 20 and pcr < 0.8:
                trend = "bearish"
            elif abs(futures_price - spot) < 15 and 0.9 <= pcr <= 1.1:
                trend = "sideways"
            else:
                trend = "neutral"

            return {
                "trend": trend,
                "trend_reason": f"Live market: futures-spot basis and PCR analysis. {narrative['narrative'][:200]}...",
                "spot": spot,
                "futures": futures_price,
                "change_spot": market_status.get("change", 0) if market_status else 0,
                "change_percent": market_status.get("change_percent", 0) if market_status else 0,
                "pcr": pcr,
                "vix": chain.get("vix", vix.get("current") if vix else 15),
                "days_to_expiry": chain.get("days_to_expiry", 1),
                "max_pain": chain.get("max_pain", 0),
                "support": chain.get("support", 0),
                "resistance": chain.get("resistance", 0),
                "timestamp": chain.get("timestamp", datetime.now().isoformat()),
                "data_source": "LIVE",
                "market_open": True,
                "premarket": {k: v for k, v in premarket.items() if not k.startswith("historical_")},
                "chart": chart,
                "news": news,
                "news_analysis": news_analysis,
                "narrative": narrative,
            }
        else:
            # Market is open but NSE option chain API unavailable
            last = market_status.get("last_price", 0) if market_status else 0
            futures_price = futures.get("last_price") if futures else narrative.get("estimated_open", last)

            tech_bias = chart.get("bias", "neutral") if chart else "neutral"
            news_label = news_analysis.get("label", "neutral")
            gap_type = narrative.get("gap_type", "flat_to_mild")

            if "bullish" in tech_bias and news_label in ["positive", "neutral"]:
                trend = "bullish"
            elif "bearish" in tech_bias and news_label in ["negative", "neutral"]:
                trend = "bearish"
            elif tech_bias == "neutral":
                trend = "sideways"
            else:
                trend = "neutral"

            trend_reason = f"Market is OPEN. NSE option chain API deprecated. Using technical bias ({tech_bias}) and news ({news_label})."

            return {
                "trend": trend,
                "trend_reason": trend_reason,
                "spot": last,
                "futures": futures_price,
                "change_spot": market_status.get("change", 0) if market_status else 0,
                "change_percent": market_status.get("change_percent", 0) if market_status else 0,
                "pcr": None,
                "vix": vix.get("current") if vix else 15,
                "days_to_expiry": None,
                "max_pain": None,
                "support": narrative.get("supports", [0])[0] if narrative.get("supports") else (chart.get("key_levels", [])[0].get("price") if chart and chart.get("key_levels") else last - 200),
                "resistance": narrative.get("resistances", [0])[0] if narrative.get("resistances") else (chart.get("key_levels", [])[-1].get("price") if chart and chart.get("key_levels") else last + 200),
                "timestamp": datetime.now().isoformat(),
                "data_source": "NSE_API_LIMITED",
                "market_open": True,
                "premarket": {k: v for k, v in premarket.items() if not k.startswith("historical_")},
                "chart": chart,
                "news": news,
                "news_analysis": news_analysis,
                "narrative": narrative,
            }

    # Market is closed or option chain unavailable - use pre-market analysis
    last = market_status.get("last_price", 0) if market_status else 0
    prev = market_status.get("previous_close", 0) if market_status else 0
    change = market_status.get("change", 0) if market_status else 0
    change_pct = market_status.get("change_percent", 0) if market_status else 0

    # Use futures price if available, else estimate from narrative
    futures_price = futures.get("last_price") if futures else narrative.get("estimated_open", last)

    # Determine trend from pre-market analysis
    tech_bias = chart.get("bias", "neutral") if chart else "neutral"
    news_label = news_analysis.get("label", "neutral")
    gap_type = narrative.get("gap_type", "flat_to_mild")

    if "bullish" in tech_bias and news_label in ["positive", "neutral"] and "gap_up" in gap_type:
        trend = "bullish"
    elif "bearish" in tech_bias and news_label in ["negative", "neutral"] and "gap_down" in gap_type:
        trend = "bearish"
    elif gap_type == "flat_to_mild" and tech_bias == "neutral":
        trend = "sideways"
    else:
        trend = "neutral"

    trend_reason = f"Pre-market analysis: Technical bias is {tech_bias}. News sentiment is {news_label}. Expected gap: {narrative['gap_estimate']:+.1f} pts."

    return {
        "trend": trend,
        "trend_reason": trend_reason,
        "spot": last,
        "futures": futures_price,
        "change_spot": change,
        "change_percent": change_pct,
        "pcr": None,  # unavailable when closed
        "vix": vix.get("current") if vix else 15,
        "days_to_expiry": None,
        "max_pain": None,
        "support": narrative.get("supports", [0])[0] if narrative.get("supports") else (chart.get("key_levels", [])[0].get("price") if chart and chart.get("key_levels") else last - 200),
        "resistance": narrative.get("resistances", [0])[0] if narrative.get("resistances") else (chart.get("key_levels", [])[-1].get("price") if chart and chart.get("key_levels") else last + 200),
        "timestamp": datetime.now().isoformat(),
        "data_source": "PRE-MARKET",
        "market_open": False,
        "premarket": {k: v for k, v in premarket.items() if not k.startswith("historical_")},
        "chart": chart,
        "news": news,
        "news_analysis": news_analysis,
        "narrative": narrative,
    }
