"""
Smart Money Concepts (SMC) / ICT Analysis Service
Rule-based institutional market structure analysis.

Concepts implemented:
- Market Structure: Break of Structure (BOS), Change of Character (CHoCH)
- Liquidity Zones: Equal highs/lows, previous day high/low, swing point clusters
- Order Blocks: Bullish/Bearish OBs (last opposing candle before impulsive move)
- Fair Value Gaps (FVG): Imbalance zones where price is likely to return
- Inducement: Minor swing points that get swept to trap retail traders

All concepts are rule-based to ensure consistency and avoid discretion.
"""

import pandas as pd
import numpy as np


def find_swing_points_detailed(data, window=5):
    """
    Find swing highs and lows with detailed metadata.
    Returns list of dicts with index, price, type, and strength.
    """
    highs = data['High'].values
    lows = data['Low'].values
    closes = data['Close'].values
    
    swing_highs = []
    swing_lows = []
    
    for i in range(window, len(data) - window):
        # Swing high: current high is highest in window
        if highs[i] == max(highs[i-window:i+window+1]):
            # Strength based on how much higher than neighbors
            left_diff = highs[i] - highs[i-window:i].max()
            right_diff = highs[i] - highs[i+1:i+window+1].max()
            strength = min(left_diff, right_diff)
            swing_highs.append({
                "index": i,
                "price": float(highs[i]),
                "type": "swing_high",
                "strength": float(round(strength, 2)),
                "timestamp": data.index[i] if hasattr(data.index[i], 'isoformat') else i
            })
        
        # Swing low: current low is lowest in window
        if lows[i] == min(lows[i-window:i+window+1]):
            left_diff = lows[i-window:i].min() - lows[i]
            right_diff = lows[i+1:i+window+1].min() - lows[i]
            strength = min(left_diff, right_diff)
            swing_lows.append({
                "index": i,
                "price": float(lows[i]),
                "type": "swing_low",
                "strength": float(round(strength, 2)),
                "timestamp": data.index[i] if hasattr(data.index[i], 'isoformat') else i
            })
    
    return swing_highs, swing_lows


def detect_market_structure(data, swing_highs, swing_lows):
    """
    Detect Break of Structure (BOS) and Change of Character (CHoCH).
    
    BOS: In an uptrend, price breaks above the previous swing high (continuation).
    CHoCH: In an uptrend, price breaks below the previous swing low (trend change).
    
    Returns structure events and current market bias.
    """
    if len(swing_highs) < 3 or len(swing_lows) < 3:
        return {
            "bias": "neutral",
            "structure": "undefined",
            "last_bos": None,
            "last_choch": None,
            "events": []
        }
    
    # Sort by index
    highs = sorted(swing_highs, key=lambda x: x["index"])
    lows = sorted(swing_lows, key=lambda x: x["index"])
    
    events = []
    bias = "neutral"
    last_bos = None
    last_choch = None
    
    # Merge swing points chronologically
    all_swings = []
    for h in highs:
        all_swings.append({**h, "swing_type": "high"})
    for l in lows:
        all_swings.append({**l, "swing_type": "low"})
    all_swings.sort(key=lambda x: x["index"])
    
    # Need at least 4 swing points to determine structure
    if len(all_swings) < 4:
        return {
            "bias": "neutral",
            "structure": "undefined",
            "last_bos": None,
            "last_choch": None,
            "events": []
        }
    
    # Determine initial bias from first two major swings
    recent_swings = all_swings[-12:]  # Look at last 12 swing points
    
    # Find higher highs and higher lows for uptrend
    hh_count = 0
    hl_count = 0
    ll_count = 0
    lh_count = 0
    
    for i in range(1, min(len(recent_swings), 8)):
        prev = recent_swings[-(i+1)]
        curr = recent_swings[-i]
        
        if prev["swing_type"] == "high" and curr["swing_type"] == "high":
            if curr["price"] > prev["price"]:
                hh_count += 1
            else:
                lh_count += 1
        elif prev["swing_type"] == "low" and curr["swing_type"] == "low":
            if curr["price"] > prev["price"]:
                hl_count += 1
            else:
                ll_count += 1
    
    # Determine bias
    if hh_count >= 2 and hl_count >= 2:
        bias = "bullish"
        structure = "uptrend"
    elif lh_count >= 2 and ll_count >= 2:
        bias = "bearish"
        structure = "downtrend"
    else:
        bias = "neutral"
        structure = "ranging"
    
    # Detect latest BOS/CHoCH from the most recent swings
    last_swing_highs = [s for s in recent_swings if s["swing_type"] == "high"][-3:]
    last_swing_lows = [s for s in recent_swings if s["swing_type"] == "low"][-3:]
    
    current_price = float(data['Close'].iloc[-1])
    
    if len(last_swing_highs) >= 2:
        prev_high = last_swing_highs[-2]["price"]
        recent_high = last_swing_highs[-1]["price"]
        
        if recent_high > prev_high and bias in ["bullish", "neutral"]:
            last_bos = {
                "type": "BOS",
                "direction": "bullish",
                "level": round(recent_high, 2),
                "description": f"Price broke above previous swing high at {prev_high:.2f}"
            }
            events.append(last_bos)
        elif recent_high < prev_high and bias == "bullish":
            # This is actually CHoCH on the high side (lower high after uptrend)
            pass  # Will be caught by lows
    
    if len(last_swing_lows) >= 2:
        prev_low = last_swing_lows[-2]["price"]
        recent_low = last_swing_lows[-1]["price"]
        
        if recent_low > prev_low and bias in ["bullish", "neutral"]:
            # Higher low in uptrend — continuation
            pass
        elif recent_low < prev_low and bias == "bullish":
            last_choch = {
                "type": "CHoCH",
                "direction": "bearish",
                "level": round(recent_low, 2),
                "description": f"Price broke below previous swing low at {prev_low:.2f} — trend may be changing"
            }
            events.append(last_choch)
            bias = "bearish"
            structure = "downtrend"
        elif recent_low < prev_low and bias in ["bearish", "neutral"]:
            last_bos = {
                "type": "BOS",
                "direction": "bearish",
                "level": round(recent_low, 2),
                "description": f"Price broke below previous swing low at {prev_low:.2f}"
            }
            events.append(last_bos)
        elif recent_low > prev_low and bias == "bearish":
            last_choch = {
                "type": "CHoCH",
                "direction": "bullish",
                "level": round(recent_low, 2),
                "description": f"Price broke above previous swing low at {prev_low:.2f} — trend may be changing"
            }
            events.append(last_choch)
            bias = "bullish"
            structure = "uptrend"
    
    return {
        "bias": bias,
        "structure": structure,
        "last_bos": last_bos,
        "last_choch": last_choch,
        "events": events,
        "recent_swing_highs": [{"price": s["price"], "strength": s["strength"]} for s in last_swing_highs],
        "recent_swing_lows": [{"price": s["price"], "strength": s["strength"]} for s in last_swing_lows],
    }


def find_liquidity_zones(data, swing_highs, swing_lows, tolerance=0.003):
    """
    Find liquidity zones where stops are likely clustered.
    
    Types:
    - Equal highs/lows (double tops/bottoms within tolerance)
    - Previous day high/low (if daily data)
    - Major swing point clusters
    """
    zones = []
    last_close = float(data['Close'].iloc[-1])
    
    # Equal highs — places where retail stops are above
    high_prices = [s["price"] for s in swing_highs]
    for i, h1 in enumerate(high_prices[-8:]):
        for h2 in high_prices[-8+i+1:]:
            if h1 == 0:
                continue
            diff = abs(h1 - h2) / h1
            if diff < tolerance:
                zones.append({
                    "price": round((h1 + h2) / 2, 2),
                    "type": "sellside_liquidity",
                    "description": f"Equal highs near {h1:.2f} — sell-side liquidity pool",
                    "strength": "high" if diff < tolerance * 0.5 else "medium"
                })
    
    # Equal lows — places where retail stops are below
    low_prices = [s["price"] for s in swing_lows]
    for i, l1 in enumerate(low_prices[-8:]):
        for l2 in low_prices[-8+i+1:]:
            if l1 == 0:
                continue
            diff = abs(l1 - l2) / l1
            if diff < tolerance:
                zones.append({
                    "price": round((l1 + l2) / 2, 2),
                    "type": "buyside_liquidity",
                    "description": f"Equal lows near {l1:.2f} — buy-side liquidity pool",
                    "strength": "high" if diff < tolerance * 0.5 else "medium"
                })
    
    # Previous session high/low (for intraday data)
    if len(data) >= 2:
        prev_high = float(data['High'].iloc[-2])
        prev_low = float(data['Low'].iloc[-2])
        zones.append({
            "price": round(prev_high, 2),
            "type": "sellside_liquidity",
            "description": f"Previous session high at {prev_high:.2f}",
            "strength": "high"
        })
        zones.append({
            "price": round(prev_low, 2),
            "type": "buyside_liquidity",
            "description": f"Previous session low at {prev_low:.2f}",
            "strength": "high"
        })
    
    # Deduplicate zones that are too close
    filtered = []
    for z in sorted(zones, key=lambda x: x["price"]):
        is_dup = False
        for existing in filtered:
            if existing["type"] == z["type"] and abs(z["price"] - existing["price"]) / max(existing["price"], 1) < tolerance:
                is_dup = True
                break
        if not is_dup:
            filtered.append(z)
    
    return filtered


def find_order_blocks(data, swing_highs, swing_lows, impulse_threshold=0.008):
    """
    Find Order Blocks — the last opposing candle before a strong impulsive move.
    
    Bullish OB: Last bearish candle before a strong bullish move (higher high).
    Bearish OB: Last bullish candle before a strong bearish move (lower low).
    """
    obs = []
    highs = data['High'].values
    lows = data['Low'].values
    opens = data['Open'].values
    closes = data['Close'].values
    
    # Look for impulsive moves in recent data
    lookback = min(60, len(data) - 5)
    
    for i in range(len(data) - lookback, len(data) - 3):
        # Measure the move from i to i+2
        move_pct = abs(closes[i+2] - closes[i]) / max(closes[i], 1)
        
        if move_pct < impulse_threshold:
            continue
        
        is_bullish_impulse = closes[i+2] > closes[i] and (closes[i+2] - opens[i+2]) > 0
        is_bearish_impulse = closes[i+2] < closes[i] and (closes[i+2] - opens[i+2]) < 0
        
        if is_bullish_impulse:
            # Look back for the last bearish candle before the move
            for j in range(i, max(i-5, 0), -1):
                if closes[j] < opens[j]:  # Bearish candle
                    ob = {
                        "type": "bullish_ob",
                        "index": j,
                        "high": float(highs[j]),
                        "low": float(lows[j]),
                        "open": float(opens[j]),
                        "close": float(closes[j]),
                        "description": f"Bullish Order Block at {opens[j]:.2f}-{closes[j]:.2f}. Last selling before strong bullish move.",
                        "strength": float(round(move_pct * 100, 2))
                    }
                    obs.append(ob)
                    break
        
        elif is_bearish_impulse:
            # Look back for the last bullish candle before the move
            for j in range(i, max(i-5, 0), -1):
                if closes[j] > opens[j]:  # Bullish candle
                    ob = {
                        "type": "bearish_ob",
                        "index": j,
                        "high": float(highs[j]),
                        "low": float(lows[j]),
                        "open": float(opens[j]),
                        "close": float(closes[j]),
                        "description": f"Bearish Order Block at {opens[j]:.2f}-{closes[j]:.2f}. Last buying before strong bearish move.",
                        "strength": float(round(move_pct * 100, 2))
                    }
                    obs.append(ob)
                    break
    
    # Keep only the most recent and strongest OBs
    obs = sorted(obs, key=lambda x: x["index"], reverse=True)[:6]
    
    # Mark OBs as mitigated if price has returned and traded through them
    current_price = float(closes[-1])
    for ob in obs:
        if ob["type"] == "bullish_ob":
            ob["mitigated"] = current_price < ob["low"]
            ob["role"] = "support" if not ob["mitigated"] else "mitigated"
        else:
            ob["mitigated"] = current_price > ob["high"]
            ob["role"] = "resistance" if not ob["mitigated"] else "mitigated"
    
    return obs


def find_fair_value_gaps(data, min_gap_pct=0.0015):
    """
    Find Fair Value Gaps (FVG) — imbalance zones where price may return.
    
    Bullish FVG: Previous candle's high < Current candle's low (gap up).
    Bearish FVG: Previous candle's low > Current candle's high (gap down).
    """
    highs = data['High'].values
    lows = data['Low'].values
    closes = data['Close'].values
    
    fvgs = []
    
    for i in range(2, len(data)):
        # Bullish FVG: candle i-2 high < candle i low
        gap = lows[i] - highs[i-2]
        gap_pct = gap / max(highs[i-2], 1)
        
        if gap > 0 and gap_pct >= min_gap_pct:
            # Check if the move was bullish (candle i is bullish)
            if closes[i] > data['Open'].values[i]:
                fvgs.append({
                    "type": "bullish_fvg",
                    "top": float(round(lows[i], 2)),
                    "bottom": float(round(highs[i-2], 2)),
                    "gap_size": float(round(gap, 2)),
                    "gap_pct": float(round(gap_pct * 100, 3)),
                    "description": f"Bullish FVG: {highs[i-2]:.2f} to {lows[i]:.2f} ({gap_pct*100:.2f}%). Price may return to fill.",
                    "filled": bool(closes[-1] < highs[i-2])  # Filled if price retraced into it
                })
        
        # Bearish FVG: candle i-2 low > candle i high
        gap = lows[i-2] - highs[i]
        gap_pct = gap / max(lows[i-2], 1)
        
        if gap > 0 and gap_pct >= min_gap_pct:
            if closes[i] < data['Open'].values[i]:
                fvgs.append({
                    "type": "bearish_fvg",
                    "top": float(round(lows[i-2], 2)),
                    "bottom": float(round(highs[i], 2)),
                    "gap_size": float(round(gap, 2)),
                    "gap_pct": float(round(gap_pct * 100, 3)),
                    "description": f"Bearish FVG: {highs[i]:.2f} to {lows[i-2]:.2f} ({gap_pct*100:.2f}%). Price may return to fill.",
                    "filled": bool(closes[-1] > lows[i-2])
                })
    
    # Keep unfilled FVGs and the most recent ones
    unfilled = [f for f in fvgs if not f["filled"]]
    return sorted(unfilled, key=lambda x: x["gap_pct"], reverse=True)[:6]


def find_inducement_levels(data, swing_highs, swing_lows, structure_bias):
    """
    Find inducement levels — minor swing points that are likely to be swept
    before the main move continues.
    
    In an uptrend: minor swing lows that might be taken out to trap bears.
    In a downtrend: minor swing highs that might be taken out to trap bulls.
    """
    inducements = []
    
    if structure_bias == "bullish":
        # Look for minor swing lows that haven't been swept
        lows = sorted(swing_lows, key=lambda x: x["index"])[-5:]
        for i, low in enumerate(lows[:-1]):
            # If there's a higher low after it, the earlier one might be swept
            if lows[i+1]["price"] > low["price"]:
                inducements.append({
                    "price": round(low["price"], 2),
                    "type": "inducement_low",
                    "description": f"Minor low at {low['price']:.2f} may be swept to trap sellers before continuation up.",
                    "swept": float(data['Close'].iloc[-1]) < low["price"]
                })
    
    elif structure_bias == "bearish":
        highs = sorted(swing_highs, key=lambda x: x["index"])[-5:]
        for i, high in enumerate(highs[:-1]):
            if highs[i+1]["price"] < high["price"]:
                inducements.append({
                    "price": round(high["price"], 2),
                    "type": "inducement_high",
                    "description": f"Minor high at {high['price']:.2f} may be swept to trap buyers before continuation down.",
                    "swept": float(data['Close'].iloc[-1]) > high["price"]
                })
    
    return inducements


def analyze_smc(data):
    """
    Main SMC analysis function.
    Returns comprehensive Smart Money Concepts analysis.
    """
    if data is None or len(data) < 30:
        return {"error": "Insufficient data for SMC analysis"}
    
    swing_highs, swing_lows = find_swing_points_detailed(data, window=3)
    structure = detect_market_structure(data, swing_highs, swing_lows)
    liquidity = find_liquidity_zones(data, swing_highs, swing_lows)
    obs = find_order_blocks(data, swing_highs, swing_lows)
    fvgs = find_fair_value_gaps(data)
    inducements = find_inducement_levels(data, swing_highs, swing_lows, structure["bias"])
    
    current_price = float(data['Close'].iloc[-1])
    
    # Find nearest unmitigated OBs
    active_obs = [ob for ob in obs if not ob.get("mitigated", False)]
    nearest_support_ob = None
    nearest_resistance_ob = None
    
    for ob in active_obs:
        if ob["type"] == "bullish_ob" and ob["low"] < current_price:
            if nearest_support_ob is None or current_price - ob["low"] < current_price - nearest_support_ob["low"]:
                nearest_support_ob = ob
        elif ob["type"] == "bearish_ob" and ob["high"] > current_price:
            if nearest_resistance_ob is None or ob["high"] - current_price < nearest_resistance_ob["high"] - current_price:
                nearest_resistance_ob = ob
    
    # Find nearest unfilled FVGs
    nearest_bullish_fvg = None
    nearest_bearish_fvg = None
    for fvg in fvgs:
        if fvg["type"] == "bullish_fvg" and fvg["bottom"] < current_price:
            if nearest_bullish_fvg is None or current_price - fvg["bottom"] < current_price - nearest_bullish_fvg["bottom"]:
                nearest_bullish_fvg = fvg
        elif fvg["type"] == "bearish_fvg" and fvg["top"] > current_price:
            if nearest_bearish_fvg is None or fvg["top"] - current_price < nearest_bearish_fvg["top"] - current_price:
                nearest_bearish_fvg = fvg
    
    # Find nearest liquidity pools
    buy_liq = [z for z in liquidity if z["type"] == "buyside_liquidity"]
    sell_liq = [z for z in liquidity if z["type"] == "sellside_liquidity"]
    
    nearest_buy_liq = min(buy_liq, key=lambda x: abs(x["price"] - current_price)) if buy_liq else None
    nearest_sell_liq = min(sell_liq, key=lambda x: abs(x["price"] - current_price)) if sell_liq else None
    
    return {
        "current_price": round(current_price, 2),
        "bias": structure["bias"],
        "structure": structure["structure"],
        "last_bos": structure["last_bos"],
        "last_choch": structure["last_choch"],
        "swing_highs_count": len(swing_highs),
        "swing_lows_count": len(swing_lows),
        "liquidity_zones": liquidity,
        "order_blocks": obs,
        "fair_value_gaps": fvgs,
        "inducements": inducements,
        "nearest_support_ob": nearest_support_ob,
        "nearest_resistance_ob": nearest_resistance_ob,
        "nearest_bullish_fvg": nearest_bullish_fvg,
        "nearest_bearish_fvg": nearest_bearish_fvg,
        "nearest_buy_liquidity": nearest_buy_liq,
        "nearest_sell_liquidity": nearest_sell_liq,
        "structure_events": structure["events"],
    }
