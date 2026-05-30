"""
Chart Pattern Analysis Service
Performs multi-timeframe technical analysis on Nifty 50:
- Daily, 60-min, 15-min timeframes
- Moving averages (SMA/EMA)
- MACD
- RSI
- ATR (14) for volatility-based stops
- Support/Resistance from swing points
- Pattern detection (double top/bottom, triangles, flags, channels)
- Trend structure analysis across timeframes
"""

import math
import pandas as pd
import numpy as np
from datetime import datetime


def calculate_sma(data, period):
    return data.rolling(window=period).mean()


def calculate_ema(data, period):
    return data.ewm(span=period, adjust=False).mean()


def calculate_rsi(data, period=14):
    delta = data.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(data, fast=12, slow=26, signal=9):
    ema_fast = data.ewm(span=fast, adjust=False).mean()
    ema_slow = data.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_atr(data, period=14):
    high_low = data['High'] - data['Low']
    high_close = np.abs(data['High'] - data['Close'].shift())
    low_close = np.abs(data['Low'] - data['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(window=period).mean()
    return atr


def find_swing_points(data, window=5):
    highs = data['High']
    lows = data['Low']
    swing_highs = []
    swing_lows = []
    for i in range(window, len(data) - window):
        if highs.iloc[i] == highs.iloc[i-window:i+window+1].max():
            swing_highs.append((i, highs.iloc[i]))
        if lows.iloc[i] == lows.iloc[i-window:i+window+1].min():
            swing_lows.append((i, lows.iloc[i]))
    return swing_highs, swing_lows


def detect_double_top(data, swing_highs, tolerance=0.015):
    if len(swing_highs) < 2:
        return None
    recent_highs = swing_highs[-5:]
    for i in range(len(recent_highs) - 1):
        for j in range(i + 1, len(recent_highs)):
            high1 = recent_highs[i]
            high2 = recent_highs[j]
            price_diff = abs(high1[1] - high2[1]) / high1[1]
            if price_diff < tolerance:
                trough_idx = data['Low'].iloc[high1[0]:high2[0]].idxmin()
                trough_price = data['Low'].loc[trough_idx]
                neckline = trough_price
                height = high1[1] - neckline
                if height > 0:
                    return {
                        "pattern": "Double Top",
                        "type": "bearish_reversal",
                        "confidence": round(max(0, 1 - price_diff * 10) * 100, 1),
                        "neckline": round(neckline, 2),
                        "target": round(neckline - height, 2),
                        "description": f"Two peaks near {high1[1]:.0f} with neckline at {neckline:.0f}. Break below targets {neckline - height:.0f}."
                    }
    return None


def detect_double_bottom(data, swing_lows, tolerance=0.015):
    if len(swing_lows) < 2:
        return None
    recent_lows = swing_lows[-5:]
    for i in range(len(recent_lows) - 1):
        for j in range(i + 1, len(recent_lows)):
            low1 = recent_lows[i]
            low2 = recent_lows[j]
            price_diff = abs(low1[1] - low2[1]) / low1[1]
            if price_diff < tolerance:
                peak_idx = data['High'].iloc[low1[0]:low2[0]].idxmax()
                peak_price = data['High'].loc[peak_idx]
                neckline = peak_price
                height = neckline - low1[1]
                if height > 0:
                    return {
                        "pattern": "Double Bottom",
                        "type": "bullish_reversal",
                        "confidence": round(max(0, 1 - price_diff * 10) * 100, 1),
                        "neckline": round(neckline, 2),
                        "target": round(neckline + height, 2),
                        "description": f"Two bottoms near {low1[1]:.0f} with neckline at {neckline:.0f}. Break above targets {neckline + height:.0f}."
                    }
    return None


def detect_triangle(data, swing_highs, swing_lows, lookback=20):
    recent_highs = [h for h in swing_highs if h[0] >= len(data) - lookback]
    recent_lows = [l for l in swing_lows if l[0] >= len(data) - lookback]
    if len(recent_highs) < 2 or len(recent_lows) < 2:
        return None
    high_slope = np.polyfit([h[0] for h in recent_highs], [h[1] for h in recent_highs], 1)[0]
    low_slope = np.polyfit([l[0] for l in recent_lows], [l[1] for l in recent_lows], 1)[0]
    if high_slope < -0.5 and low_slope > 0.5:
        return {"pattern": "Symmetrical Triangle", "type": "continuation", "confidence": 65,
                "description": "Converging support and resistance trendlines. Breakout expected."}
    if abs(high_slope) < 2 and low_slope > 1:
        return {"pattern": "Ascending Triangle", "type": "bullish_continuation", "confidence": 70,
                "description": "Flat resistance with rising support. Bullish breakout expected."}
    if high_slope < -1 and abs(low_slope) < 2:
        return {"pattern": "Descending Triangle", "type": "bearish_continuation", "confidence": 70,
                "description": "Falling resistance with flat support. Bearish breakdown expected."}
    return None


def detect_channel(data, swing_highs, swing_lows, lookback=30):
    recent_highs = [h for h in swing_highs if h[0] >= len(data) - lookback]
    recent_lows = [l for l in swing_lows if l[0] >= len(data) - lookback]
    if len(recent_highs) < 2 or len(recent_lows) < 2:
        return None
    high_slope = np.polyfit([h[0] for h in recent_highs], [h[1] for h in recent_highs], 1)[0]
    low_slope = np.polyfit([l[0] for l in recent_lows], [l[1] for l in recent_lows], 1)[0]
    if abs(high_slope - low_slope) < 1.5:
        if high_slope > 1:
            return {"pattern": "Rising Channel", "type": "bullish", "confidence": 60,
                    "description": "Price in rising parallel channel. Buy near support."}
        elif high_slope < -1:
            return {"pattern": "Falling Channel", "type": "bearish", "confidence": 60,
                    "description": "Price in falling parallel channel. Sell near resistance."}
    return None


def detect_flag(data, lookback=15):
    if len(data) < lookback + 10:
        return None
    recent = data.tail(lookback + 10)
    first_half = recent.head(5)
    second_half = recent.tail(lookback)
    first_range = first_half['High'].max() - first_half['Low'].min()
    second_range = second_half['High'].max() - second_half['Low'].min()
    if first_range > second_range * 2:
        direction = "bull" if first_half['Close'].iloc[-1] > first_half['Open'].iloc[0] else "bear"
        return {"pattern": f"{'Bull' if direction == 'bull' else 'Bear'} Flag",
                "type": f"{direction}ish_continuation", "confidence": 55,
                "description": f"Sharp {'up' if direction == 'bull' else 'down'} move then consolidation. Continuation expected."}
    return None


def analyze_trend_structure(data, lookback=20):
    recent = data.tail(lookback)
    highs = recent['High'].values
    lows = recent['Low'].values
    hh = hl = lh = ll = 0
    for i in range(1, len(highs)):
        if highs[i] > highs[i-1]: hh += 1
        else: lh += 1
        if lows[i] > lows[i-1]: hl += 1
        else: ll += 1
    total = len(highs) - 1
    hh_pct = hh / total * 100
    hl_pct = hl / total * 100
    lh_pct = lh / total * 100
    ll_pct = ll / total * 100

    if hh_pct > 60 and hl_pct > 60: trend = "strong_uptrend"
    elif hh_pct > 50 and hl_pct > 50: trend = "uptrend"
    elif lh_pct > 60 and ll_pct > 60: trend = "strong_downtrend"
    elif lh_pct > 50 and ll_pct > 50: trend = "downtrend"
    else: trend = "sideways"

    return {
        "trend": trend,
        "higher_highs_pct": round(hh_pct, 1),
        "higher_lows_pct": round(hl_pct, 1),
        "lower_highs_pct": round(lh_pct, 1),
        "lower_lows_pct": round(ll_pct, 1),
        "description": _trend_description(trend, hh_pct, hl_pct, lh_pct, ll_pct)
    }


def _trend_description(trend, hh, hl, lh, ll):
    if "uptrend" in trend:
        return f"Higher highs ({hh:.0f}%) and higher lows ({hl:.0f}%). Structure bullish."
    elif "downtrend" in trend:
        return f"Lower highs ({lh:.0f}%) and lower lows ({ll:.0f}%). Structure bearish."
    else:
        return f"Mixed: HH={hh:.0f}%, HL={hl:.0f}%, LH={lh:.0f}%, LL={ll:.0f}%. No clear bias."


def find_key_levels(data, swing_highs, swing_lows):
    levels = []
    for idx, price in swing_highs[-5:]:
        levels.append({"price": round(price, 2), "type": "resistance", "source": "swing_high"})
    for idx, price in swing_lows[-5:]:
        levels.append({"price": round(price, 2), "type": "support", "source": "swing_low"})

    last_close = data['Close'].iloc[-1]
    round_100 = round(last_close / 100) * 100
    levels.append({"price": round_100, "type": "psychological", "source": "round_number"})
    levels.append({"price": round_100 + 100, "type": "psychological", "source": "round_number"})
    levels.append({"price": round_100 - 100, "type": "psychological", "source": "round_number"})

    sma20 = calculate_sma(data['Close'], 20).iloc[-1]
    sma50 = calculate_sma(data['Close'], 50).iloc[-1]
    sma200 = calculate_sma(data['Close'], 200).iloc[-1]

    if not math.isnan(sma20): levels.append({"price": round(sma20, 2), "type": "dynamic", "source": "SMA20"})
    if not math.isnan(sma50): levels.append({"price": round(sma50, 2), "type": "dynamic", "source": "SMA50"})
    if not math.isnan(sma200): levels.append({"price": round(sma200, 2), "type": "dynamic", "source": "SMA200"})

    filtered = []
    for level in sorted(levels, key=lambda x: x["price"]):
        is_dup = False
        for existing in filtered:
            if abs(level["price"] - existing["price"]) / existing["price"] < 0.003:
                is_dup = True
                break
        if not is_dup:
            filtered.append(level)

    for level in filtered:
        if level["price"] > last_close * 1.001: level["role"] = "resistance"
        elif level["price"] < last_close * 0.999: level["role"] = "support"
        else: level["role"] = "pivot"
    return filtered


def analyze_single_timeframe(data, label="daily"):
    """Analyze a single timeframe and return structured results."""
    if data is None or len(data) < 60:
        return {"error": f"Insufficient {label} data"}

    last_close = data['Close'].iloc[-1]
    sma20 = calculate_sma(data['Close'], 20)
    sma50 = calculate_sma(data['Close'], 50)
    sma200 = calculate_sma(data['Close'], 200)
    ema20 = calculate_ema(data['Close'], 20)
    rsi = calculate_rsi(data['Close'], 14)
    macd_line, signal_line, histogram = calculate_macd(data['Close'])
    atr = calculate_atr(data, 14)

    current_rsi = rsi.iloc[-1] if not rsi.empty else 50
    current_macd = macd_line.iloc[-1] if not macd_line.empty else 0
    current_signal = signal_line.iloc[-1] if not signal_line.empty else 0
    current_hist = histogram.iloc[-1] if not histogram.empty else 0
    current_atr = atr.iloc[-1] if not atr.empty else 0

    swing_highs, swing_lows = find_swing_points(data, window=3)
    trend = analyze_trend_structure(data)
    levels = find_key_levels(data, swing_highs, swing_lows)

    patterns = []
    for fn in [detect_double_top, detect_double_bottom, detect_triangle, detect_channel, detect_flag]:
        if fn == detect_double_top: p = fn(data, swing_highs)
        elif fn == detect_double_bottom: p = fn(data, swing_lows)
        elif fn == detect_flag: p = fn(data)
        else: p = fn(data, swing_highs, swing_lows)
        if p: patterns.append(p)

    # MACD interpretation
    macd_signal = "neutral"
    if current_macd > current_signal and current_hist > 0:
        macd_signal = "bullish"
    elif current_macd < current_signal and current_hist < 0:
        macd_signal = "bearish"

    # ATR-based expected move
    atr_move = current_atr * 1.5

    return {
        "timeframe": label,
        "last_close": round(last_close, 2),
        "sma20": round(sma20.iloc[-1], 2) if not math.isnan(sma20.iloc[-1]) else None,
        "sma50": round(sma50.iloc[-1], 2) if not math.isnan(sma50.iloc[-1]) else None,
        "sma200": round(sma200.iloc[-1], 2) if not math.isnan(sma200.iloc[-1]) else None,
        "ema20": round(ema20.iloc[-1], 2) if not math.isnan(ema20.iloc[-1]) else None,
        "rsi": round(current_rsi, 1),
        "macd": round(current_macd, 2),
        "macd_signal": round(current_signal, 2),
        "macd_histogram": round(current_hist, 2),
        "macd_bias": macd_signal,
        "atr": round(current_atr, 2),
        "atr_expected_move": round(atr_move, 2),
        "trend_structure": trend,
        "key_levels": levels,
        "patterns": patterns,
    }


def analyze_chart(historical_df_daily, historical_df_60m=None, historical_df_15m=None):
    """
    Main chart analysis function — multi-timeframe.
    Returns comprehensive technical analysis dict.
    """
    daily = analyze_single_timeframe(historical_df_daily, "daily") if historical_df_daily is not None else None
    tf_60m = analyze_single_timeframe(historical_df_60m, "60min") if historical_df_60m is not None else None
    tf_15m = analyze_single_timeframe(historical_df_15m, "15min") if historical_df_15m is not None else None

    # Multi-timeframe alignment
    daily_trend = daily.get("trend_structure", {}).get("trend", "sideways") if daily else "sideways"
    tf60_trend = tf_60m.get("trend_structure", {}).get("trend", "sideways") if tf_60m else "sideways"
    tf15_trend = tf_15m.get("trend_structure", {}).get("trend", "sideways") if tf_15m else "sideways"

    alignment = "mixed"
    if "uptrend" in daily_trend and "uptrend" in tf60_trend:
        alignment = "bullish_aligned"
    elif "downtrend" in daily_trend and "downtrend" in tf60_trend:
        alignment = "bearish_aligned"
    elif daily_trend == "sideways" and tf60_trend == "sideways":
        alignment = "sideways_aligned"

    # Aggregate patterns from daily
    all_patterns = daily.get("patterns", []) if daily else []

    # Aggregate key levels from daily
    all_levels = daily.get("key_levels", []) if daily else []

    # Volume analysis from daily
    avg_volume = historical_df_daily['Volume'].tail(20).mean() if historical_df_daily is not None else 0
    last_volume = historical_df_daily['Volume'].iloc[-1] if historical_df_daily is not None else 0
    volume_vs_avg = (last_volume / avg_volume - 1) * 100 if avg_volume > 0 else 0

    # Determine primary bias from all timeframes
    bias = "neutral"
    bias_score = 0
    reasons = []

    # Daily trend contribution
    if daily:
        if "strong_uptrend" in daily_trend:
            bias_score += 3
            reasons.append("Daily trend strongly bullish")
        elif "uptrend" in daily_trend:
            bias_score += 2
            reasons.append("Daily trend bullish")
        elif "strong_downtrend" in daily_trend:
            bias_score -= 3
            reasons.append("Daily trend strongly bearish")
        elif "downtrend" in daily_trend:
            bias_score -= 2
            reasons.append("Daily trend bearish")
        else:
            reasons.append("Daily trend sideways")

        # 60m alignment
        if "uptrend" in tf60_trend and "uptrend" in daily_trend:
            bias_score += 1
            reasons.append("60min aligns with daily bullish")
        elif "downtrend" in tf60_trend and "downtrend" in daily_trend:
            bias_score -= 1
            reasons.append("60min aligns with daily bearish")

        # MA contribution
        last_close = daily["last_close"]
        if daily.get("sma20") and last_close > daily["sma20"]:
            bias_score += 1
            reasons.append("Price above 20 SMA")
        elif daily.get("sma20"):
            bias_score -= 1
            reasons.append("Price below 20 SMA")

        if daily.get("sma50") and last_close > daily["sma50"]:
            bias_score += 1
            reasons.append("Price above 50 SMA")
        elif daily.get("sma50"):
            bias_score -= 1
            reasons.append("Price below 50 SMA")

        if daily.get("sma200") and last_close > daily["sma200"]:
            bias_score += 1
            reasons.append("Price above 200 SMA (macro bullish)")
        elif daily.get("sma200"):
            bias_score -= 1
            reasons.append("Price below 200 SMA (macro bearish)")

        # RSI
        rsi = daily["rsi"]
        if rsi > 70:
            bias_score -= 1
            reasons.append(f"RSI overbought ({rsi})")
        elif rsi < 30:
            bias_score += 1
            reasons.append(f"RSI oversold ({rsi})")
        else:
            reasons.append(f"RSI neutral ({rsi})")

        # MACD
        if daily.get("macd_bias") == "bullish":
            bias_score += 1
            reasons.append("MACD bullish crossover")
        elif daily.get("macd_bias") == "bearish":
            bias_score -= 1
            reasons.append("MACD bearish crossover")

        # Patterns
        for p in all_patterns:
            if "bullish" in p["type"]:
                bias_score += 1.5
                reasons.append(f"Bullish pattern: {p['pattern']}")
            elif "bearish" in p["type"]:
                bias_score -= 1.5
                reasons.append(f"Bearish pattern: {p['pattern']}")

        # Volume
        if volume_vs_avg > 50:
            bias_score += 0.5 if bias_score > 0 else -0.5
            reasons.append("Volume above average")
        elif volume_vs_avg < -30:
            reasons.append("Volume below average")

    if bias_score >= 4: bias = "strongly_bullish"
    elif bias_score >= 2: bias = "bullish"
    elif bias_score <= -4: bias = "strongly_bearish"
    elif bias_score <= -2: bias = "bearish"
    elif bias_score > 0: bias = "mildly_bullish"
    elif bias_score < 0: bias = "mildly_bearish"

    return {
        "last_close": daily.get("last_close") if daily else None,
        "daily": daily,
        "tf_60min": tf_60m,
        "tf_15min": tf_15m,
        "multi_timeframe_alignment": alignment,
        "patterns": all_patterns,
        "key_levels": all_levels,
        "volume_vs_avg": round(volume_vs_avg, 1),
        "bias": bias,
        "bias_score": round(bias_score, 1),
        "bias_reasons": reasons,
        "data_points": len(historical_df_daily) if historical_df_daily is not None else 0,
    }
