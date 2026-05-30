"""
Probability Engine & Trade Quality Scorer
Institutional-grade confluence scoring system.

Weights:
- Market Structure (SMC): 20%
- Multi-Timeframe Alignment: 15%
- Option Chain (OI + PCR): 20%
- Volume / VWAP: 10%
- Institutional Flow: 10%
- Volatility Environment: 10%
- SMC/ICT Setup Quality: 15%

Threshold: >= 70 to emit trade.
"""

import math


def _clamp(val, min_val=0, max_val=100):
    return max(min_val, min(max_val, val))


def score_market_structure(smc_data, chart_data):
    """
    Score market structure quality (SMC concepts).
    0-100 based on clarity of structure, BOS/CHoCH, liquidity sweeps.
    """
    if not smc_data or smc_data.get("error"):
        return 50, ["SMC data unavailable — neutral score"]
    
    score = 50
    details = []
    
    bias = smc_data.get("bias", "neutral")
    structure = smc_data.get("structure", "undefined")
    
    if bias in ["bullish", "bearish"]:
        score = 60
        details.append(f"Clear {bias} bias in market structure")
    else:
        details.append("Market structure unclear or ranging")
        return score, details
    
    # BOS bonus
    last_bos = smc_data.get("last_bos")
    if last_bos and last_bos["direction"] == bias:
        score += 15
        details.append(f"Recent BOS confirms {bias} direction")
    
    # CHoCH penalty if against bias
    last_choch = smc_data.get("last_choch")
    if last_choch and last_choch["direction"] != bias:
        score -= 10
        details.append(f"Recent CHoCH against current bias — caution")
    elif last_choch and last_choch["direction"] == bias:
        score += 10
        details.append(f"CHoCH aligns with {bias} bias")
    
    # Order blocks present
    active_obs = [ob for ob in smc_data.get("order_blocks", []) if not ob.get("mitigated", False)]
    if len(active_obs) >= 2:
        score += 5
        details.append(f"{len(active_obs)} active order blocks provide structure")
    
    # FVGs present
    fvgs = smc_data.get("fair_value_gaps", [])
    if fvgs:
        score += 5
        details.append(f"{len(fvgs)} unfilled FVGs suggest potential targets")
    
    # Liquidity sweeps
    liq = smc_data.get("liquidity_zones", [])
    if liq:
        score += 5
        details.append("Liquidity zones identified")
    
    return _clamp(score), details


def score_multi_timeframe(chart_data):
    """
    Score multi-timeframe alignment.
    0-100 based on how many timeframes agree.
    """
    if not chart_data or chart_data.get("error"):
        return 50, ["Chart data unavailable"]
    
    score = 50
    details = []
    
    daily = chart_data.get("daily", {})
    tf60 = chart_data.get("tf_60min", {})
    tf15 = chart_data.get("tf_15min", {})
    tf5 = chart_data.get("tf_5min", {})
    
    daily_trend = daily.get("trend_structure", {}).get("trend", "sideways") if daily else "sideways"
    tf60_trend = tf60.get("trend_structure", {}).get("trend", "sideways") if tf60 else "sideways"
    tf15_trend = tf15.get("trend_structure", {}).get("trend", "sideways") if tf15 else "sideways"
    tf5_trend = tf5.get("trend_structure", {}).get("trend", "sideways") if tf5 else "sideways"
    
    trends = [daily_trend, tf60_trend, tf15_trend, tf5_trend]
    
    # Count bullish/bearish alignments
    bullish_count = sum(1 for t in trends if "uptrend" in t)
    bearish_count = sum(1 for t in trends if "downtrend" in t)
    
    if bullish_count >= 3:
        score = 85
        details.append(f"Strong bullish alignment: {bullish_count}/4 timeframes bullish")
    elif bullish_count >= 2:
        score = 70
        details.append(f"Moderate bullish alignment: {bullish_count}/4 timeframes bullish")
    elif bearish_count >= 3:
        score = 85
        details.append(f"Strong bearish alignment: {bearish_count}/4 timeframes bearish")
    elif bearish_count >= 2:
        score = 70
        details.append(f"Moderate bearish alignment: {bearish_count}/4 timeframes bearish")
    else:
        score = 45
        details.append("Timeframes mixed — no clear alignment")
    
    # Bonus for strong trends
    strong_count = sum(1 for t in trends if "strong" in t)
    if strong_count >= 2:
        score += 10
        details.append(f"{strong_count} timeframes show strong trend")
    
    # MACD alignment
    macd_align = 0
    for tf in [daily, tf60, tf15, tf5]:
        if tf and tf.get("macd_bias") == "bullish":
            macd_align += 1
        elif tf and tf.get("macd_bias") == "bearish":
            macd_align -= 1
    
    if abs(macd_align) >= 3:
        score += 5
        details.append("MACD aligned across timeframes")
    
    return _clamp(score), details


def score_option_chain(oi_data, analysis_data):
    """
    Score option chain analysis.
    0-100 based on OI buildup, PCR, walls clarity.
    """
    if not analysis_data or not analysis_data.get("market_open"):
        # Market closed — use pre-market signals
        return 50, ["Market closed — option chain unavailable, using pre-market proxy"]
    
    score = 50
    details = []
    
    # PCR signal
    pcr = analysis_data.get("pcr", 1.0)
    pcr_signal = analysis_data.get("pcr_signal", "neutral")
    
    if "strong_bullish" in pcr_signal:
        score += 15
        details.append(f"PCR {pcr:.2f}: Strong bullish (heavy put writing)")
    elif "bullish" in pcr_signal:
        score += 10
        details.append(f"PCR {pcr:.2f}: Bullish bias")
    elif "strong_bearish" in pcr_signal:
        score -= 15
        details.append(f"PCR {pcr:.2f}: Strong bearish (heavy call writing)")
    elif "bearish" in pcr_signal:
        score -= 10
        details.append(f"PCR {pcr:.2f}: Bearish bias")
    else:
        details.append(f"PCR {pcr:.2f}: Neutral")
    
    # OI buildup analysis
    if oi_data and not oi_data.get("error"):
        oi_bias = oi_data.get("oi_buildup", {}).get("oi_bias", "neutral")
        if oi_bias == "bullish":
            score += 10
            details.append("OI buildup confirms bullish bias")
        elif oi_bias == "bearish":
            score -= 10
            details.append("OI buildup confirms bearish bias")
        
        # Wall strength
        walls = oi_data.get("walls", {})
        support = walls.get("support")
        resistance = walls.get("resistance")
        if support and resistance:
            if support.get("strength_score", 0) > 3 and resistance.get("strength_score", 0) > 3:
                score += 10
                details.append("Strong OI walls on both sides — clear range")
            elif support.get("strength_score", 0) > 3:
                score += 5
                details.append("Strong support wall")
            elif resistance.get("strength_score", 0) > 3:
                score -= 5
                details.append("Strong resistance wall")
    
    # Max pain alignment
    max_pain = analysis_data.get("max_pain", 0)
    spot = analysis_data.get("spot", 0)
    if spot and max_pain:
        pain_diff = spot - max_pain
        if abs(pain_diff) > 50:
            if pain_diff > 0:
                score += 5
                details.append(f"Spot {spot:.0f} above max pain {max_pain:.0f} (bullish)")
            else:
                score -= 5
                details.append(f"Spot {spot:.0f} below max pain {max_pain:.0f} (bearish)")
        else:
            details.append(f"Spot near max pain {max_pain:.0f} — pin risk")
    
    # Futures basis
    basis = analysis_data.get("basis", 0)
    if basis > 20:
        score += 5
        details.append(f"Futures premium {basis:.1f} — long buildup")
    elif basis < -15:
        score -= 5
        details.append(f"Futures discount {abs(basis):.1f} — short buildup")
    
    return _clamp(score), details


def score_volume_vwap(vwap_data):
    """
    Score volume and VWAP analysis.
    0-100 based on VWAP position, volume delta, volume profile.
    """
    if not vwap_data or vwap_data.get("error"):
        return 50, ["VWAP/Volume data unavailable"]
    
    score = 50
    details = []
    
    vwap = vwap_data.get("vwap")
    vol_delta = vwap_data.get("volume_delta")
    vol_profile = vwap_data.get("volume_profile")
    
    if vwap:
        deviation = vwap.get("deviation", 0)
        if deviation > 2:
            score -= 10
            details.append(f"Price extended +{deviation:.1f}σ above VWAP — mean reversion risk")
        elif deviation < -2:
            score += 10
            details.append(f"Price extended {deviation:.1f}σ below VWAP — mean reversion opportunity")
        elif deviation > 0.5:
            score += 5
            details.append("Price above VWAP — bullish intraday")
        elif deviation < -0.5:
            score -= 5
            details.append("Price below VWAP — bearish intraday")
        else:
            details.append("Price near VWAP — balanced")
    
    if vol_delta:
        bias = vol_delta.get("delta_bias", "neutral")
        recent = vol_delta.get("recent_bias", "neutral")
        if bias == "buying" and recent == "buying":
            score += 10
            details.append("Consistent buying pressure in volume delta")
        elif bias == "selling" and recent == "selling":
            score -= 10
            details.append("Consistent selling pressure in volume delta")
        elif bias != recent:
            details.append(f"Volume delta shift: {bias} → {recent}")
    
    if vol_profile:
        if vol_profile.get("in_value_area"):
            score += 5
            details.append("Price inside Value Area — normal activity")
        elif vol_profile.get("current_position") == "above_poc":
            score += 3
            details.append("Price above POC — bullish volume structure")
        elif vol_profile.get("current_position") == "below_poc":
            score -= 3
            details.append("Price below POC — bearish volume structure")
    
    return _clamp(score), details


def score_institutional_flow(flow_data):
    """
    Score institutional flow analysis.
    0-100 based on FII/DII and futures positioning.
    """
    if not flow_data or flow_data.get("error"):
        return 50, ["Institutional flow data unavailable"]
    
    score = 50
    details = []
    
    cumulative = flow_data.get("cumulative_bias", "neutral")
    
    if cumulative == "strongly_bullish":
        score = 85
        details.append("Strongly bullish institutional flow")
    elif cumulative == "bullish":
        score = 70
        details.append("Bullish institutional flow")
    elif cumulative == "mildly_bullish":
        score = 60
        details.append("Mildly bullish institutional flow")
    elif cumulative == "strongly_bearish":
        score = 15
        details.append("Strongly bearish institutional flow")
    elif cumulative == "bearish":
        score = 30
        details.append("Bearish institutional flow")
    elif cumulative == "mildly_bearish":
        score = 40
        details.append("Mildly bearish institutional flow")
    else:
        details.append("Neutral institutional flow")
    
    # Futures classification detail
    futures = flow_data.get("futures", {})
    f_class = futures.get("classification", "unknown")
    if f_class == "long_buildup":
        score += 5
        details.append("Futures long buildup confirms bullish flow")
    elif f_class == "short_buildup":
        score -= 5
        details.append("Futures short buildup confirms bearish flow")
    elif f_class == "short_covering":
        score += 3
        details.append("Futures short covering — bears exiting")
    elif f_class == "long_unwinding":
        score -= 3
        details.append("Futures long unwinding — bulls exiting")
    
    return _clamp(score), details


def score_volatility(analysis_data, vix_data):
    """
    Score volatility environment.
    0-100 based on VIX, DTE, IV percentile.
    """
    score = 50
    details = []
    
    vix = analysis_data.get("vix", 15)
    days_to_expiry = analysis_data.get("days_to_expiry", 7)
    iv_analysis = analysis_data.get("iv_analysis")
    
    # VIX environment
    if vix > 22:
        score -= 10
        details.append(f"VIX {vix} elevated — wider stops needed, directional moves possible")
    elif vix > 18:
        score -= 5
        details.append(f"VIX {vix} moderately high")
    elif vix < 12:
        score -= 5
        details.append(f"VIX {vix} very low — breakouts may fail, rangebound likely")
    elif 12 <= vix <= 18:
        score += 10
        details.append(f"VIX {vix} in sweet spot for directional trades")
    
    # DTE
    if days_to_expiry is not None:
        if days_to_expiry <= 1:
            score -= 20
            details.append("Expiry day — extreme theta decay, avoid directional options")
        elif days_to_expiry <= 3:
            score -= 10
            details.append(f"DTE {days_to_expiry} — high time decay risk")
        elif days_to_expiry <= 7:
            score -= 5
            details.append(f"DTE {days_to_expiry} — moderate time decay")
        else:
            score += 5
            details.append(f"DTE {days_to_expiry} — comfortable for directional trades")
    
    # IV analysis
    if iv_analysis:
        iv_pct = iv_analysis.get("iv_percentile")
        if iv_pct is not None:
            if iv_pct > 70:
                score -= 5
                details.append(f"IV percentile {iv_pct}% high — option selling favored")
            elif iv_pct < 30:
                score += 5
                details.append(f"IV percentile {iv_pct}% low — option buying favored")
            else:
                details.append(f"IV percentile {iv_pct}% moderate")
    
    return _clamp(score), details


def score_smc_setup(smc_data, chart_data):
    """
    Score SMC/ICT setup quality.
    0-100 based on liquidity sweeps, OB quality, FVG alignment.
    """
    if not smc_data or smc_data.get("error"):
        return 50, ["SMC data unavailable"]
    
    score = 50
    details = []
    
    bias = smc_data.get("bias", "neutral")
    current_price = smc_data.get("current_price", 0)
    
    if bias == "neutral":
        return score, ["No clear SMC bias"]
    
    score = 60
    details.append(f"SMC bias is {bias}")
    
    # Order blocks near price
    active_obs = [ob for ob in smc_data.get("order_blocks", []) if not ob.get("mitigated", False)]
    
    if bias == "bullish":
        # Look for bullish OB below price
        bull_obs = [ob for ob in active_obs if ob["type"] == "bullish_ob" and ob["high"] < current_price]
        if bull_obs:
            nearest = max(bull_obs, key=lambda x: x["high"])
            score += 15
            details.append(f"Bullish Order Block at {nearest['low']:.2f}-{nearest['high']:.2f} provides support")
        
        # Check if sell-side liquidity was swept
        sell_liq = [z for z in smc_data.get("liquidity_zones", []) if z["type"] == "sellside_liquidity"]
        if sell_liq:
            score += 10
            details.append("Sell-side liquidity identified — potential target above")
    
    elif bias == "bearish":
        # Look for bearish OB above price
        bear_obs = [ob for ob in active_obs if ob["type"] == "bearish_ob" and ob["low"] > current_price]
        if bear_obs:
            nearest = min(bear_obs, key=lambda x: x["low"])
            score += 15
            details.append(f"Bearish Order Block at {nearest['low']:.2f}-{nearest['high']:.2f} provides resistance")
        
        # Check if buy-side liquidity was swept
        buy_liq = [z for z in smc_data.get("liquidity_zones", []) if z["type"] == "buyside_liquidity"]
        if buy_liq:
            score += 10
            details.append("Buy-side liquidity identified — potential target below")
    
    # FVGs as targets
    fvgs = smc_data.get("fair_value_gaps", [])
    if fvgs:
        score += 5
        details.append(f"{len(fvgs)} unfilled FVGs provide targets")
    
    # Inducement levels
    inducements = smc_data.get("inducements", [])
    if inducements:
        score += 5
        details.append(f"{len(inducements)} inducement levels identified")
    
    return _clamp(score), details


def calculate_probability(smc_data, chart_data, oi_data, analysis_data, vwap_data, flow_data, vix_data):
    """
    Main probability calculation.
    Returns probability (0-100), breakdown, and decision.
    """
    scores = {}
    details = {}
    
    # 1. Market Structure (SMC) — 20%
    s, d = score_market_structure(smc_data, chart_data)
    scores["market_structure"] = s
    details["market_structure"] = d
    
    # 2. Multi-Timeframe — 15%
    s, d = score_multi_timeframe(chart_data)
    scores["multi_timeframe"] = s
    details["multi_timeframe"] = d
    
    # 3. Option Chain — 20%
    s, d = score_option_chain(oi_data, analysis_data)
    scores["option_chain"] = s
    details["option_chain"] = d
    
    # 4. Volume / VWAP — 10%
    s, d = score_volume_vwap(vwap_data)
    scores["volume_vwap"] = s
    details["volume_vwap"] = d
    
    # 5. Institutional Flow — 10%
    s, d = score_institutional_flow(flow_data)
    scores["institutional_flow"] = s
    details["institutional_flow"] = d
    
    # 6. Volatility — 10%
    s, d = score_volatility(analysis_data, vix_data)
    scores["volatility"] = s
    details["volatility"] = d
    
    # 7. SMC Setup Quality — 15%
    s, d = score_smc_setup(smc_data, chart_data)
    scores["smc_setup"] = s
    details["smc_setup"] = d
    
    # Weighted average
    weights = {
        "market_structure": 0.20,
        "multi_timeframe": 0.15,
        "option_chain": 0.20,
        "volume_vwap": 0.10,
        "institutional_flow": 0.10,
        "volatility": 0.10,
        "smc_setup": 0.15,
    }
    
    probability = sum(scores[k] * weights[k] for k in weights)
    probability = _clamp(probability)
    
    # Determine direction from highest contributing factors
    direction = "neutral"
    if chart_data:
        bias = chart_data.get("bias", "neutral")
        if "bullish" in bias:
            direction = "bullish"
        elif "bearish" in bias:
            direction = "bearish"
    
    return {
        "probability": round(probability, 1),
        "direction": direction,
        "decision": "GO" if probability >= 70 else "NO_TRADE",
        "scores": scores,
        "details": details,
        "threshold": 70,
    }


def calculate_trade_quality_score(probability_result, entry, stop, target1, target2=None, 
                                   chart_data=None, flow_data=None, event_risk=False, days_to_expiry=None):
    """
    Calculate Trade Quality Score (0-100).
    
    Base: Probability score
    Bonuses/Penalties applied.
    """
    score = probability_result["probability"]
    reasons = []
    
    # R:R bonus
    risk = abs(entry - stop)
    reward1 = abs(target1 - entry)
    rr = reward1 / risk if risk > 0 else 0
    
    if rr >= 2.5:
        score += 10
        reasons.append(f"R:R 1:{rr:.1f} excellent (+10)")
    elif rr >= 2.0:
        score += 7
        reasons.append(f"R:R 1:{rr:.1f} very good (+7)")
    elif rr >= 1.5:
        score += 5
        reasons.append(f"R:R 1:{rr:.1f} good (+5)")
    elif rr < 1.2:
        score -= 15
        reasons.append(f"R:R 1:{rr:.1f} poor — below minimum (-15)")
    
    # Timeframe alignment bonus
    if chart_data:
        alignment = chart_data.get("multi_timeframe_alignment", "mixed")
        if "aligned" in alignment and "mixed" not in alignment:
            score += 5
            reasons.append("All timeframes aligned (+5)")
    
    # Institutional flow bonus
    if flow_data:
        cumulative = flow_data.get("cumulative_bias", "neutral")
        if cumulative in ["bullish", "strongly_bullish"] and probability_result["direction"] == "bullish":
            score += 5
            reasons.append("Institutional flow confirms direction (+5)")
        elif cumulative in ["bearish", "strongly_bearish"] and probability_result["direction"] == "bearish":
            score += 5
            reasons.append("Institutional flow confirms direction (+5)")
    
    # Event risk penalty
    if event_risk:
        score -= 10
        reasons.append("High-impact event risk detected (-10)")
    
    # Expiry day gamma penalty
    if days_to_expiry is not None and days_to_expiry <= 1:
        score -= 10
        reasons.append("Expiry day gamma risk (-10)")
    elif days_to_expiry is not None and days_to_expiry <= 3:
        score -= 5
        reasons.append("Near expiry theta risk (-5)")
    
    final_score = _clamp(score)
    
    return {
        "trade_quality_score": round(final_score, 1),
        "base_probability": probability_result["probability"],
        "rr": round(rr, 2),
        "reasons": reasons,
        "grade": "A" if final_score >= 85 else "B" if final_score >= 75 else "C" if final_score >= 65 else "D" if final_score >= 55 else "F",
    }
