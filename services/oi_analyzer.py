"""
Deep Open Interest Analysis Service
Institutional-grade OI interpretation for NIFTY 50 options.

Analyzes:
- OI Change Classification: Long Buildup, Short Buildup, Long Unwinding, Short Covering
- PCR trend and momentum
- OI Concentration Heatmap
- Support/Resistance strength from OI walls
- Strike-wise buildup analysis

Requires TWO snapshots of option chain data to classify OI changes.
"""

import json
import time
from datetime import datetime
from .database import get_connection


# In-memory cache for OI snapshots (last 5 snapshots)
_OI_SNAPSHOT_CACHE = []
_MAX_CACHE_SIZE = 5


def save_oi_snapshot(strikes_data, spot, futures, timestamp=None):
    """
    Save an OI snapshot to database for historical comparison.
    """
    if not strikes_data:
        return
    
    ts = timestamp or datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    
    # Ensure table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oi_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            spot REAL,
            futures REAL,
            strike_data TEXT
        )
    """)
    
    # Store simplified strike data
    simplified = []
    for s in strikes_data:
        simplified.append({
            "strike": s["strike"],
            "ce_oi": s["ce_oi"],
            "pe_oi": s["pe_oi"],
            "ce_volume": s.get("ce_volume", 0),
            "pe_volume": s.get("pe_volume", 0),
            "ce_premium": s.get("ce_premium", 0),
            "pe_premium": s.get("pe_premium", 0),
        })
    
    cursor.execute("""
        INSERT INTO oi_snapshots (timestamp, spot, futures, strike_data)
        VALUES (?, ?, ?, ?)
    """, (ts, spot, futures, json.dumps(simplified)))
    
    # Keep only last 100 snapshots
    cursor.execute("""
        DELETE FROM oi_snapshots WHERE id NOT IN (
            SELECT id FROM oi_snapshots ORDER BY timestamp DESC LIMIT 100
        )
    """)
    
    conn.commit()
    conn.close()
    
    # Update cache
    _OI_SNAPSHOT_CACHE.append({
        "timestamp": ts,
        "spot": spot,
        "futures": futures,
        "strikes": simplified
    })
    if len(_OI_SNAPSHOT_CACHE) > _MAX_CACHE_SIZE:
        _OI_SNAPSHOT_CACHE.pop(0)


def get_last_oi_snapshot():
    """
    Get the most recent OI snapshot from DB.
    """
    # Check cache first
    if _OI_SNAPSHOT_CACHE:
        return _OI_SNAPSHOT_CACHE[-1]
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oi_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            spot REAL,
            futures REAL,
            strike_data TEXT
        )
    """)
    cursor.execute("SELECT * FROM oi_snapshots ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "timestamp": row["timestamp"],
            "spot": row["spot"],
            "futures": row["futures"],
            "strikes": json.loads(row["strike_data"]) if row["strike_data"] else []
        }
    return None


def classify_oi_change(current_strike, previous_strike, spot):
    """
    Classify OI change for a single strike.
    
    Uses price change + OI change to determine market participant behavior:
    - Long Buildup: Price ↑ + OI ↑ → Fresh longs entering
    - Short Buildup: Price ↓ + OI ↑ → Fresh shorts entering
    - Long Unwinding: Price ↓ + OI ↓ → Longs exiting
    - Short Covering: Price ↑ + OI ↓ → Shorts exiting
    """
    if not previous_strike:
        return "unknown"
    
    # Determine if strike is ITM/ATM/OTM for CE and PE
    moneyness = (current_strike["strike"] - spot) / 50  # Nifty lot size approximation
    
    # Price proxy: use premium change as proxy for underlying directional move at this strike
    ce_premium_change = current_strike.get("ce_premium", 0) - previous_strike.get("ce_premium", 0)
    pe_premium_change = current_strike.get("pe_premium", 0) - previous_strike.get("pe_premium", 0)
    
    ce_oi_change = current_strike["ce_oi"] - previous_strike["ce_oi"]
    pe_oi_change = current_strike["pe_oi"] - previous_strike["pe_oi"]
    
    # Classify CE side
    ce_classification = "neutral"
    if abs(ce_oi_change) > 1000:  # Minimum threshold to avoid noise
        if ce_premium_change > 0 and ce_oi_change > 0:
            ce_classification = "long_buildup"
        elif ce_premium_change < 0 and ce_oi_change > 0:
            ce_classification = "short_buildup"
        elif ce_premium_change < 0 and ce_oi_change < 0:
            ce_classification = "long_unwinding"
        elif ce_premium_change > 0 and ce_oi_change < 0:
            ce_classification = "short_covering"
    
    # Classify PE side
    pe_classification = "neutral"
    if abs(pe_oi_change) > 1000:
        if pe_premium_change > 0 and pe_oi_change > 0:
            pe_classification = "long_buildup"
        elif pe_premium_change < 0 and pe_oi_change > 0:
            pe_classification = "short_buildup"
        elif pe_premium_change < 0 and pe_oi_change < 0:
            pe_classification = "long_unwinding"
        elif pe_premium_change > 0 and pe_oi_change < 0:
            pe_classification = "short_covering"
    
    return {
        "strike": current_strike["strike"],
        "moneyness": round(moneyness, 1),
        "ce_oi_change": ce_oi_change,
        "pe_oi_change": pe_oi_change,
        "ce_premium_change": round(ce_premium_change, 2),
        "pe_premium_change": round(pe_premium_change, 2),
        "ce_classification": ce_classification,
        "pe_classification": pe_classification,
    }


def analyze_oi_buildup(current_strikes, previous_strikes, spot):
    """
    Analyze OI buildup across all strikes and return classified data.
    """
    if not previous_strikes or not current_strikes:
        return {"error": "Insufficient OI history for classification"}
    
    prev_by_strike = {s["strike"]: s for s in previous_strikes}
    
    buildup_data = []
    totals = {
        "ce_long_buildup": 0, "ce_short_buildup": 0,
        "ce_long_unwinding": 0, "ce_short_covering": 0,
        "pe_long_buildup": 0, "pe_short_buildup": 0,
        "pe_long_unwinding": 0, "pe_short_covering": 0,
    }
    
    for curr in current_strikes:
        strike = curr["strike"]
        prev = prev_by_strike.get(strike)
        
        classification = classify_oi_change(curr, prev, spot)
        if isinstance(classification, dict):
            buildup_data.append(classification)
            
            # Tally totals
            if classification["ce_classification"] == "long_buildup":
                totals["ce_long_buildup"] += classification["ce_oi_change"]
            elif classification["ce_classification"] == "short_buildup":
                totals["ce_short_buildup"] += classification["ce_oi_change"]
            elif classification["ce_classification"] == "long_unwinding":
                totals["ce_long_unwinding"] += abs(classification["ce_oi_change"])
            elif classification["ce_classification"] == "short_covering":
                totals["ce_short_covering"] += abs(classification["ce_oi_change"])
            
            if classification["pe_classification"] == "long_buildup":
                totals["pe_long_buildup"] += classification["pe_oi_change"]
            elif classification["pe_classification"] == "short_buildup":
                totals["pe_short_buildup"] += classification["pe_oi_change"]
            elif classification["pe_classification"] == "long_unwinding":
                totals["pe_long_unwinding"] += abs(classification["pe_oi_change"])
            elif classification["pe_classification"] == "short_covering":
                totals["pe_short_covering"] += abs(classification["pe_oi_change"])
    
    # Determine overall bias from OI changes
    ce_net_buildup = totals["ce_long_buildup"] - totals["ce_long_unwinding"]
    pe_net_buildup = totals["pe_long_buildup"] - totals["pe_long_unwinding"]
    
    # Short side interpretation
    ce_short_interest = totals["ce_short_buildup"] - totals["ce_short_covering"]
    pe_short_interest = totals["pe_short_buildup"] - totals["pe_short_covering"]
    
    if ce_net_buildup < 0 and pe_net_buildup > 0:
        oi_bias = "bullish"
        oi_reason = "PE long buildup + CE unwinding suggests bullish positioning"
    elif ce_net_buildup > 0 and pe_net_buildup < 0:
        oi_bias = "bearish"
        oi_reason = "CE long buildup + PE unwinding suggests bearish positioning"
    elif ce_short_interest > 0 and pe_short_interest < 0:
        oi_bias = "bullish"
        oi_reason = "Heavy CE writing (short buildup) + PE short covering suggests bullish bias"
    elif ce_short_interest < 0 and pe_short_interest > 0:
        oi_bias = "bearish"
        oi_reason = "Heavy PE writing (short buildup) + CE short covering suggests bearish bias"
    else:
        oi_bias = "neutral"
        oi_reason = "Mixed OI signals — no clear directional bias"
    
    return {
        "strike_classifications": buildup_data,
        "totals": totals,
        "ce_net_buildup": ce_net_buildup,
        "pe_net_buildup": pe_net_buildup,
        "ce_short_interest": ce_short_interest,
        "pe_short_interest": pe_short_interest,
        "oi_bias": oi_bias,
        "oi_reason": oi_reason,
    }


def analyze_pcr_trend(current_pcr, previous_snapshots=None):
    """
    Analyze PCR trend from current value and optional historical snapshots.
    """
    if previous_snapshots is None:
        previous_snapshots = []
    
    trend = "neutral"
    strength = "weak"
    
    if len(previous_snapshots) >= 2:
        recent_pcr = [s.get("pcr", current_pcr) for s in previous_snapshots[-5:]]
        if len(recent_pcr) >= 2:
            if recent_pcr[-1] > recent_pcr[0] * 1.05:
                trend = "rising"
                strength = "strong" if recent_pcr[-1] > recent_pcr[0] * 1.15 else "moderate"
            elif recent_pcr[-1] < recent_pcr[0] * 0.95:
                trend = "falling"
                strength = "strong" if recent_pcr[-1] < recent_pcr[0] * 0.85 else "moderate"
            else:
                trend = "flat"
                strength = "weak"
    
    # Interpretation
    if current_pcr > 1.3:
        signal = "extreme_bullish"
        desc = f"PCR {current_pcr:.2f} is very high. Heavy put writing / put buying. Extreme bullish contrarian signal or hedging."
    elif current_pcr > 1.1:
        signal = "bullish"
        desc = f"PCR {current_pcr:.2f} is elevated. Put bias suggests support building."
    elif current_pcr < 0.7:
        signal = "extreme_bearish"
        desc = f"PCR {current_pcr:.2f} is very low. Heavy call writing. Extreme bearish contrarian signal."
    elif current_pcr < 0.9:
        signal = "bearish"
        desc = f"PCR {current_pcr:.2f} is low. Call bias suggests resistance building."
    else:
        signal = "neutral"
        desc = f"PCR {current_pcr:.2f} is neutral."
    
    return {
        "current_pcr": round(current_pcr, 3),
        "trend": trend,
        "trend_strength": strength,
        "signal": signal,
        "description": desc,
    }


def build_oi_heatmap(strikes):
    """
    Build OI concentration data for heatmap visualization.
    Returns top strikes by CE and PE OI.
    """
    if not strikes:
        return {"error": "No strike data"}
    
    ce_sorted = sorted(strikes, key=lambda x: x["ce_oi"], reverse=True)[:10]
    pe_sorted = sorted(strikes, key=lambda x: x["pe_oi"], reverse=True)[:10]
    
    ce_heatmap = []
    max_ce = ce_sorted[0]["ce_oi"] if ce_sorted else 1
    for s in ce_sorted:
        ce_heatmap.append({
            "strike": s["strike"],
            "oi": s["ce_oi"],
            "intensity": round(s["ce_oi"] / max(max_ce, 1), 2),
            "type": "ce"
        })
    
    pe_heatmap = []
    max_pe = pe_sorted[0]["pe_oi"] if pe_sorted else 1
    for s in pe_sorted:
        pe_heatmap.append({
            "strike": s["strike"],
            "oi": s["pe_oi"],
            "intensity": round(s["pe_oi"] / max(max_pe, 1), 2),
            "type": "pe"
        })
    
    return {
        "ce_heatmap": ce_heatmap,
        "pe_heatmap": pe_heatmap,
        "max_ce_oi": max_ce,
        "max_pe_oi": max_pe,
    }


def find_strongest_walls(strikes):
    """
    Find the strongest support and resistance walls based on OI concentration.
    Adds a 'strength score' based on OI magnitude relative to average.
    """
    if not strikes:
        return {"support": None, "resistance": None}
    
    avg_ce_oi = sum(s["ce_oi"] for s in strikes) / len(strikes)
    avg_pe_oi = sum(s["pe_oi"] for s in strikes) / len(strikes)
    
    ce_sorted = sorted(strikes, key=lambda x: x["ce_oi"], reverse=True)
    pe_sorted = sorted(strikes, key=lambda x: x["pe_oi"], reverse=True)
    
    resistance = None
    if ce_sorted:
        r = ce_sorted[0]
        resistance = {
            "strike": r["strike"],
            "oi": r["ce_oi"],
            "strength_score": round(r["ce_oi"] / max(avg_ce_oi, 1), 1),
            "type": "resistance_wall"
        }
    
    support = None
    if pe_sorted:
        s = pe_sorted[0]
        support = {
            "strike": s["strike"],
            "oi": s["pe_oi"],
            "strength_score": round(s["pe_oi"] / max(avg_pe_oi, 1), 1),
            "type": "support_wall"
        }
    
    return {
        "support": support,
        "resistance": resistance,
        "avg_ce_oi": round(avg_ce_oi, 0),
        "avg_pe_oi": round(avg_pe_oi, 0),
    }


def analyze_deep_oi(option_chain_data):
    """
    Main entry point for deep OI analysis.
    Requires current option chain data. Will fetch previous snapshot automatically.
    """
    if not option_chain_data or not option_chain_data.get("strikes"):
        return {"error": "No option chain data available", "market_open": False}
    
    strikes = option_chain_data["strikes"]
    spot = option_chain_data.get("spot", 0)
    futures = option_chain_data.get("futures", 0)
    pcr = option_chain_data.get("pcr_oi", 1.0)
    
    # Save current snapshot
    save_oi_snapshot(strikes, spot, futures)
    
    # Get previous snapshot
    prev = get_last_oi_snapshot()
    
    # Buildup analysis
    if prev and prev.get("strikes"):
        buildup = analyze_oi_buildup(strikes, prev["strikes"], spot)
    else:
        buildup = {"error": "No previous OI snapshot for comparison"}
    
    # PCR trend
    pcr_analysis = analyze_pcr_trend(pcr)
    
    # Heatmap
    heatmap = build_oi_heatmap(strikes)
    
    # Walls
    walls = find_strongest_walls(strikes)
    
    return {
        "market_open": True,
        "spot": spot,
        "futures": futures,
        "pcr": pcr,
        "pcr_analysis": pcr_analysis,
        "oi_buildup": buildup,
        "oi_heatmap": heatmap,
        "walls": walls,
        "timestamp": datetime.now().isoformat(),
    }
