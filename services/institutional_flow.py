"""
Institutional Flow Analysis Service
Analyzes FII/DII activity, futures positioning, and cumulative institutional bias.

Uses NSE India APIs for FII/DII data and futures OI.
Classifies futures positioning using the 4 OI change categories:
- Long Buildup: Price ↑ + OI ↑
- Short Buildup: Price ↓ + OI ↑
- Long Unwinding: Price ↓ + OI ↓
- Short Covering: Price ↑ + OI ↓
"""

import json
from datetime import datetime
from .database import get_connection
from .premarket_data import get_fii_dii_data, get_nifty_futures_ohlc


# Cache for futures snapshots
_FUTURES_SNAPSHOT_CACHE = []
_MAX_CACHE_SIZE = 10


def save_futures_snapshot(futures_data):
    """Save futures snapshot for OI change classification."""
    if not futures_data:
        return
    
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "last_price": futures_data.get("last_price", 0),
        "oi": futures_data.get("oi", 0),
        "volume": futures_data.get("volume", 0),
    }
    
    _FUTURES_SNAPSHOT_CACHE.append(snapshot)
    if len(_FUTURES_SNAPSHOT_CACHE) > _MAX_CACHE_SIZE:
        _FUTURES_SNAPSHOT_CACHE.pop(0)
    
    # Also save to DB
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS futures_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_price REAL,
            oi REAL,
            volume REAL
        )
    """)
    cursor.execute("""
        INSERT INTO futures_snapshots (timestamp, last_price, oi, volume)
        VALUES (?, ?, ?, ?)
    """, (snapshot["timestamp"], snapshot["last_price"], snapshot["oi"], snapshot["volume"]))
    
    # Keep last 200
    cursor.execute("""
        DELETE FROM futures_snapshots WHERE id NOT IN (
            SELECT id FROM futures_snapshots ORDER BY timestamp DESC LIMIT 200
        )
    """)
    conn.commit()
    conn.close()


def get_last_futures_snapshot():
    """Get most recent futures snapshot."""
    if _FUTURES_SNAPSHOT_CACHE:
        return _FUTURES_SNAPSHOT_CACHE[-1]
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM futures_snapshots ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "timestamp": row["timestamp"],
            "last_price": row["last_price"],
            "oi": row["oi"],
            "volume": row["volume"]
        }
    return None


def classify_futures_oi(current, previous):
    """
    Classify futures OI change.
    
    Returns one of: long_buildup, short_buildup, long_unwinding, short_covering
    """
    if not previous or not current:
        return "unknown"
    
    price_change = current.get("last_price", 0) - previous.get("last_price", 0)
    oi_change = current.get("oi", 0) - previous.get("oi", 0)
    
    if price_change > 0 and oi_change > 0:
        return "long_buildup"
    elif price_change < 0 and oi_change > 0:
        return "short_buildup"
    elif price_change < 0 and oi_change < 0:
        return "long_unwinding"
    elif price_change > 0 and oi_change < 0:
        return "short_covering"
    else:
        return "neutral"


def analyze_fii_dii_trend():
    """
    Fetch and analyze FII/DII trend over recent sessions.
    NSE API typically returns last few sessions.
    """
    try:
        data = get_fii_dii_data()
        if not data:
            return {"error": "FII/DII data unavailable"}
        
        fii_net = data.get("fii_net", 0)
        dii_net = data.get("dii_net", 0)
        
        # Determine flow bias
        if fii_net > 1000:
            fii_bias = "strong_buying"
            fii_desc = f"FII strong net buying ₹{fii_net:.0f} cr"
        elif fii_net > 500:
            fii_bias = "buying"
            fii_desc = f"FII net buying ₹{fii_net:.0f} cr"
        elif fii_net < -1000:
            fii_bias = "strong_selling"
            fii_desc = f"FII strong net selling ₹{abs(fii_net):.0f} cr"
        elif fii_net < -500:
            fii_bias = "selling"
            fii_desc = f"FII net selling ₹{abs(fii_net):.0f} cr"
        else:
            fii_bias = "neutral"
            fii_desc = f"FII net flow ₹{fii_net:.0f} cr (neutral)"
        
        if dii_net > 1000:
            dii_bias = "strong_buying"
            dii_desc = f"DII strong net buying ₹{dii_net:.0f} cr"
        elif dii_net > 500:
            dii_bias = "buying"
            dii_desc = f"DII net buying ₹{dii_net:.0f} cr"
        elif dii_net < -500:
            dii_bias = "selling"
            dii_desc = f"DII net selling ₹{abs(dii_net):.0f} cr"
        else:
            dii_bias = "neutral"
            dii_desc = f"DII net flow ₹{dii_net:.0f} cr (neutral)"
        
        # Combined bias
        if fii_bias in ["strong_buying", "buying"] and dii_bias in ["strong_buying", "buying"]:
            combined_bias = "strongly_bullish"
        elif fii_bias in ["strong_selling", "selling"] and dii_bias in ["strong_selling", "selling"]:
            combined_bias = "strongly_bearish"
        elif fii_bias in ["strong_buying", "buying"] and dii_bias == "neutral":
            combined_bias = "bullish"
        elif fii_bias in ["strong_selling", "selling"] and dii_bias == "neutral":
            combined_bias = "bearish"
        elif fii_bias == "neutral" and dii_bias in ["strong_buying", "buying"]:
            combined_bias = "mildly_bullish"
        elif fii_bias == "neutral" and dii_bias in ["strong_selling", "selling"]:
            combined_bias = "mildly_bearish"
        elif fii_bias in ["strong_buying", "buying"] and dii_bias in ["strong_selling", "selling"]:
            combined_bias = "neutral"
        elif fii_bias in ["strong_selling", "selling"] and dii_bias in ["strong_buying", "buying"]:
            combined_bias = "neutral"
        else:
            combined_bias = "neutral"
        
        return {
            "fii_net": fii_net,
            "fii_bias": fii_bias,
            "fii_description": fii_desc,
            "dii_net": dii_net,
            "dii_bias": dii_bias,
            "dii_description": dii_desc,
            "combined_bias": combined_bias,
            "date": data.get("date", ""),
        }
    except Exception as e:
        return {"error": f"FII/DII analysis failed: {str(e)}"}


def analyze_futures_flow():
    """
    Analyze futures positioning using current and previous snapshots.
    """
    current = get_nifty_futures_ohlc()
    if not current:
        return {"error": "Futures data unavailable"}
    
    # Save current snapshot
    save_futures_snapshot(current)
    
    # Get previous for comparison
    previous = get_last_futures_snapshot()
    if previous and previous.get("timestamp") == current.get("timestamp"):
        # We just saved this, get the one before
        if len(_FUTURES_SNAPSHOT_CACHE) >= 2:
            previous = _FUTURES_SNAPSHOT_CACHE[-2]
        else:
            previous = None
    
    classification = classify_futures_oi(current, previous) if previous else "unknown"
    
    # Interpret classification
    interpretations = {
        "long_buildup": "Fresh long positions building. Bulls are confident.",
        "short_buildup": "Fresh short positions building. Bears are aggressive.",
        "long_unwinding": "Longs exiting. Bullish conviction weakening.",
        "short_covering": "Shorts exiting. Bearish pressure easing — potential reversal up.",
        "neutral": "No significant OI change.",
        "unknown": "Insufficient historical data."
    }
    
    return {
        "current_price": current.get("last_price", 0),
        "current_oi": current.get("oi", 0),
        "current_volume": current.get("volume", 0),
        "previous_price": previous.get("last_price", 0) if previous else None,
        "previous_oi": previous.get("oi", 0) if previous else None,
        "classification": classification,
        "interpretation": interpretations.get(classification, "Unknown"),
        "basis": round(current.get("last_price", 0) - current.get("prev_close", 0), 2) if current.get("prev_close") else 0,
    }


def analyze_institutional_flow():
    """
    Main entry point for institutional flow analysis.
    Combines FII/DII, futures positioning, and cumulative bias.
    """
    fii_dii = analyze_fii_dii_trend()
    futures = analyze_futures_flow()
    
    # Cumulative bias scoring
    score = 0
    reasons = []
    
    # FII contribution
    if fii_dii.get("fii_bias") == "strong_buying":
        score += 3
        reasons.append("FII strong buying")
    elif fii_dii.get("fii_bias") == "buying":
        score += 2
        reasons.append("FII net buying")
    elif fii_dii.get("fii_bias") == "strong_selling":
        score -= 3
        reasons.append("FII strong selling")
    elif fii_dii.get("fii_bias") == "selling":
        score -= 2
        reasons.append("FII net selling")
    
    # DII contribution
    if fii_dii.get("dii_bias") == "strong_buying":
        score += 2
        reasons.append("DII strong buying")
    elif fii_dii.get("dii_bias") == "buying":
        score += 1
        reasons.append("DII net buying")
    elif fii_dii.get("dii_bias") == "strong_selling":
        score -= 2
        reasons.append("DII strong selling")
    elif fii_dii.get("dii_bias") == "selling":
        score -= 1
        reasons.append("DII net selling")
    
    # Futures contribution
    futures_class = futures.get("classification", "unknown")
    if futures_class == "long_buildup":
        score += 2
        reasons.append("Futures long buildup")
    elif futures_class == "short_buildup":
        score -= 2
        reasons.append("Futures short buildup")
    elif futures_class == "short_covering":
        score += 1
        reasons.append("Futures short covering")
    elif futures_class == "long_unwinding":
        score -= 1
        reasons.append("Futures long unwinding")
    
    # Determine cumulative bias
    if score >= 4:
        cumulative = "strongly_bullish"
    elif score >= 2:
        cumulative = "bullish"
    elif score <= -4:
        cumulative = "strongly_bearish"
    elif score <= -2:
        cumulative = "bearish"
    else:
        cumulative = "neutral"
    
    return {
        "fii_dii": fii_dii,
        "futures": futures,
        "cumulative_score": score,
        "cumulative_bias": cumulative,
        "reasons": reasons,
        "timestamp": datetime.now().isoformat(),
    }
