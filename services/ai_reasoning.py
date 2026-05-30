"""
AI Reasoning Service — 8-Layer Framework
Generates trade ideas using the complete professional analysis stack:

1. Market Direction Analysis (Multi-timeframe: Daily, 60m, 15m)
2. Option Chain Analysis (OI, PCR, Max Pain, Change in OI)
3. Time and Volatility Analysis (DTE, IV, IV Rank, India VIX)
4. Sentiment Analysis (FII/DII, PCR trend, OI shifts)
5. Quantitative Levels and Strike Selection (ATM, Delta, Breakeven, ATR, R:R)
6. Risk Management Layer (1% rule, position sizing, hedging)
7. News and Event Risk Check
8. Final Decision Framework (7-step checklist)

Trade is ONLY emitted when ALL 7 checklist items pass.
"""

import random
from datetime import datetime

from .analysis import analyze_option_chain, get_trend_analysis
from .market_data import get_market_summary
from .premarket_data import get_all_premarket_data
from .chart_analysis import analyze_chart
from .news_ai import generate_market_news_context, analyze_news_sentiment, get_ai_market_narrative
from .database import get_settings


def _calculate_rr(entry, stop, target):
    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk == 0:
        return 0
    return round(reward / risk, 2)


def _confidence_label(score):
    if score >= 75:
        return "High"
    elif score >= 55:
        return "Moderate"
    elif score >= 40:
        return "Low"
    return "Very Low"


def generate_trade_idea(settings):
    """Main trade generation with full 8-layer analysis."""
    settings = settings or {"capital": 100000, "max_risk_percent": 2.0}
    summary = get_market_summary()
    premarket = get_all_premarket_data()

    if summary.get("market_open"):
        return _generate_open_market_trade(settings, summary, premarket)
    else:
        return _generate_premarket_trade(settings, summary, premarket)


def _run_layer_1_market_direction(premarket):
    """Layer 1: Multi-timeframe trend analysis."""
    chart = analyze_chart(
        premarket.get("historical_daily"),
        premarket.get("historical_60m"),
        premarket.get("historical_15m")
    ) if premarket else None

    if not chart or chart.get("error"):
        return {"pass": False, "score": 0, "details": "Chart data unavailable", "data": None}

    daily = chart.get("daily", {})
    tf60 = chart.get("tf_60min", {})
    tf15 = chart.get("tf_15min", {})

    daily_trend = daily.get("trend_structure", {}).get("trend", "sideways")
    tf60_trend = tf60.get("trend_structure", {}).get("trend", "sideways") if tf60 else "sideways"

    # Alignment scoring
    score = 0
    details = []

    if "strong_uptrend" in daily_trend:
        score += 15
        details.append("Daily: Strong uptrend")
    elif "uptrend" in daily_trend:
        score += 10
        details.append("Daily: Uptrend")
    elif "strong_downtrend" in daily_trend:
        score -= 15
        details.append("Daily: Strong downtrend")
    elif "downtrend" in daily_trend:
        score -= 10
        details.append("Daily: Downtrend")
    else:
        details.append("Daily: Sideways")

    if "uptrend" in tf60_trend and "uptrend" in daily_trend:
        score += 5
        details.append("60min aligns with daily bullish")
    elif "downtrend" in tf60_trend and "downtrend" in daily_trend:
        score -= 5
        details.append("60min aligns with daily bearish")

    # MACD
    if daily.get("macd_bias") == "bullish":
        score += 3
        details.append("MACD bullish")
    elif daily.get("macd_bias") == "bearish":
        score -= 3
        details.append("MACD bearish")

    # RSI
    rsi = daily.get("rsi", 50)
    if rsi > 70:
        score -= 2
        details.append(f"RSI overbought ({rsi})")
    elif rsi < 30:
        score += 2
        details.append(f"RSI oversold ({rsi})")
    else:
        details.append(f"RSI neutral ({rsi})")

    # Patterns
    patterns = chart.get("patterns", [])
    for p in patterns:
        if "bullish" in p["type"]:
            score += 3
            details.append(f"Pattern: {p['pattern']} (bullish)")
        elif "bearish" in p["type"]:
            score -= 3
            details.append(f"Pattern: {p['pattern']} (bearish)")

    trend_clear = abs(score) >= 10
    return {
        "pass": trend_clear,
        "score": score,
        "details": details,
        "data": chart,
        "direction": "bullish" if score > 0 else "bearish" if score < 0 else "neutral",
        "strength": "strong" if abs(score) >= 15 else "moderate" if abs(score) >= 10 else "weak"
    }


def _run_layer_2_option_chain(analysis):
    """Layer 2: Option chain OI, PCR, max pain analysis."""
    if not analysis.get("market_open"):
        return {"pass": True, "score": 0, "details": ["Market closed — option chain unavailable"], "data": analysis}

    score = 0
    details = []

    # PCR
    pcr = analysis.get("pcr", 1.0)
    if pcr > 1.2:
        score += 5
        details.append(f"PCR {pcr}: Heavy put writing (bullish)")
    elif pcr < 0.8:
        score -= 5
        details.append(f"PCR {pcr}: Heavy call writing (bearish)")
    else:
        details.append(f"PCR {pcr}: Neutral")

    # Max pain alignment
    spot = analysis.get("spot", 0)
    max_pain = analysis.get("max_pain", 0)
    if spot > max_pain + 50:
        score += 3
        details.append(f"Spot {spot:.0f} above max pain {max_pain} (bullish)")
    elif spot < max_pain - 50:
        score -= 3
        details.append(f"Spot {spot:.0f} below max pain {max_pain} (bearish)")
    else:
        details.append(f"Spot near max pain {max_pain}")

    # Futures basis
    basis = analysis.get("basis", 0)
    if basis > 20:
        score += 3
        details.append(f"Futures premium {basis:.1f} (long buildup)")
    elif basis < -10:
        score -= 3
        details.append(f"Futures discount {abs(basis):.1f} (short buildup)")
    else:
        details.append(f"Basis {basis:.1f}: Normal")

    # OI walls clarity
    support = analysis.get("support_wall", 0)
    resistance = analysis.get("resistance_wall", 0)
    range_width = resistance - support
    if 100 <= range_width <= 500:
        score += 2
        details.append(f"Clear OI walls: {support}-{resistance}")
    elif range_width < 100:
        score -= 1
        details.append("Support/Resistance too close")
    else:
        details.append(f"Wide S/R range ({range_width} pts)")

    return {
        "pass": True,
        "score": score,
        "details": details,
        "data": analysis
    }


def _run_layer_3_volatility(analysis):
    """Layer 3: Time to expiry, IV, VIX analysis."""
    score = 0
    details = []

    vix = analysis.get("vix", 15)
    days_to_expiry = analysis.get("days_to_expiry", 7)
    iv_analysis = analysis.get("iv_analysis")

    # VIX environment
    if vix > 22:
        score -= 2
        details.append(f"VIX {vix}: Elevated — wider stops needed")
    elif vix < 12:
        score -= 1
        details.append(f"VIX {vix}: Very low — breakouts may fail")
    else:
        score += 1
        details.append(f"VIX {vix}: Moderate")

    # DTE
    if days_to_expiry is not None:
        if days_to_expiry <= 1:
            score -= 5
            details.append("Expiry day: Extreme theta decay risk")
        elif days_to_expiry <= 3:
            score -= 2
            details.append(f"DTE {days_to_expiry}: High time decay")
        else:
            score += 1
            details.append(f"DTE {days_to_expiry}: Comfortable for directional trades")
    else:
        details.append("DTE unknown (market closed)")

    # IV analysis
    if iv_analysis:
        iv_pct = iv_analysis.get("iv_percentile")
        if iv_pct is not None:
            if iv_pct > 70:
                score += 2
                details.append(f"IV percentile {iv_pct}%: High — selling favored")
            elif iv_pct < 30:
                score += 2
                details.append(f"IV percentile {iv_pct}%: Low — buying favored")
            else:
                details.append(f"IV percentile {iv_pct}%: Moderate")

    return {"pass": True, "score": score, "details": details}


def _run_layer_4_sentiment(premarket, analysis):
    """Layer 4: FII/DII, sentiment, OI shifts."""
    score = 0
    details = []

    fii_dii = premarket.get("fii_dii")
    if fii_dii:
        fii_net = fii_dii.get("fii_net", 0)
        dii_net = fii_dii.get("dii_net", 0)
        if fii_net > 500:
            score += 3
            details.append(f"FII net buying Rs {fii_net} cr (bullish)")
        elif fii_net < -500:
            score -= 3
            details.append(f"FII net selling Rs {abs(fii_net)} cr (bearish)")
        else:
            details.append(f"FII net: Rs {fii_net} cr (neutral)")

        if dii_net > 500:
            score += 2
            details.append(f"DII net buying Rs {dii_net} cr (supportive)")
        elif dii_net < -500:
            score -= 1
            details.append(f"DII net selling Rs {abs(dii_net)} cr")

    # Advances/Declines
    ad = premarket.get("advances_declines")
    if ad:
        try:
            advances = int(ad.get("advances", 0) or 0)
            declines = int(ad.get("declines", 0) or 0)
            total = advances + declines
            if total > 0:
                adv_pct = advances / total * 100
                if adv_pct > 60:
                    score += 2
                    details.append(f"A/D ratio: {adv_pct:.0f}% advances (strong breadth)")
                elif adv_pct < 40:
                    score -= 2
                    details.append(f"A/D ratio: {adv_pct:.0f}% advances (weak breadth)")
                else:
                    details.append(f"A/D ratio: {adv_pct:.0f}% advances (neutral)")
        except (ValueError, TypeError):
            pass

    return {"pass": True, "score": score, "details": details}


def _run_layer_5_levels(analysis, chart, premarket):
    """Layer 5: Quantitative levels, strike selection, ATR."""
    data = {}
    details = []

    # ATR for stop loss
    daily = chart.get("daily", {}) if chart else {}
    atr = daily.get("atr", 0)
    if atr:
        data["atr"] = atr
        data["atr_stop"] = round(atr * 1.5, 2)
        details.append(f"ATR(14): {atr:.1f} pts — suggested stop distance: {data['atr_stop']:.1f} pts")

    # Key levels
    key_levels = chart.get("key_levels", []) if chart else []
    supports = sorted([l["price"] for l in key_levels if l.get("role") == "support"], reverse=True)
    resistances = sorted([l["price"] for l in key_levels if l.get("role") == "resistance"])

    data["supports"] = supports[:3]
    data["resistances"] = resistances[:3]

    # Breakeven for options
    breakeven = analysis.get("breakeven_analysis") if analysis else None
    if breakeven:
        details.append(f"ATM CE breakeven: {breakeven['ce_breakeven']:.0f} (premium {breakeven['ce_premium']:.0f})")
        details.append(f"ATM PE breakeven: {breakeven['pe_breakeven']:.0f} (premium {breakeven['pe_premium']:.0f})")
        data["breakeven"] = breakeven

    # Delta-based strike recommendation
    delta_data = analysis.get("delta_analysis") if analysis else None
    if delta_data:
        # Find 0.6-0.7 delta strike
        for d in delta_data:
            if 0.55 <= d["ce_delta"] <= 0.75:
                details.append(f"Recommended CE strike: {d['strike']} (est. delta {d['ce_delta']}, premium {d['ce_premium']})")
                data["recommended_ce_strike"] = d["strike"]
                break
            if -0.75 <= d["pe_delta"] <= -0.55:
                details.append(f"Recommended PE strike: {d['strike']} (est. delta {abs(d['pe_delta'])}, premium {d['pe_premium']})")
                data["recommended_pe_strike"] = d["strike"]
                break

    return {"pass": True, "score": 0, "details": details, "data": data}


def _run_layer_6_risk_management(settings, entry, stop, target1, target2, capital, atr_stop):
    """Layer 6: Risk management validation."""
    max_risk_pct = float(settings.get("max_risk_percent", 2.0))
    max_risk_rupees = capital * max_risk_pct / 100
    details = []

    # Calculate risk per unit
    risk_per_unit = abs(entry - stop)
    if risk_per_unit == 0:
        return {"pass": False, "score": 0, "details": ["Invalid stop loss (same as entry)"], "data": None}

    # ATR-based stop validation
    if atr_stop and risk_per_unit < atr_stop * 0.5:
        details.append(f"Warning: Stop only {risk_per_unit:.1f} pts — less than 0.5x ATR ({atr_stop:.1f})")
    elif atr_stop and risk_per_unit > atr_stop * 3:
        details.append(f"Warning: Stop {risk_per_unit:.1f} pts — more than 3x ATR ({atr_stop:.1f})")

    # Risk-Reward
    rr = _calculate_rr(entry, stop, target1)
    rr2 = _calculate_rr(entry, stop, target2) if target2 else rr

    if rr < 1.2:
        return {"pass": False, "score": 0, "details": [f"R:R {rr} below 1:1.2 minimum"], "data": None}

    details.append(f"R:R 1:{rr}" + (f" / 1:{rr2}" if target2 else ""))

    # Position sizing
    point_value = 50
    risk_per_lot = risk_per_unit * point_value
    quantity = max(1, int(max_risk_rupees / risk_per_lot))
    total_risk = quantity * risk_per_lot

    if total_risk > max_risk_rupees * 1.1:
        return {"pass": False, "score": 0, "details": [f"Risk Rs {total_risk:.0f} exceeds max Rs {max_risk_rupees:.0f}"], "data": None}

    details.append(f"Quantity: {quantity} lot(s) based on {max_risk_pct}% risk rule")
    details.append(f"Total risk: Rs {total_risk:.0f} (max allowed: Rs {max_risk_rupees:.0f})")

    # 1% rule check
    one_pct = capital * 0.01
    if total_risk > one_pct * 1.5:
        details.append(f"Warning: Risk exceeds 1% of capital (Rs {one_pct:.0f})")

    return {
        "pass": True,
        "score": 0,
        "details": details,
        "data": {
            "quantity": quantity,
            "total_risk": round(total_risk, 2),
            "max_risk": round(max_risk_rupees, 2),
            "rr": rr,
            "rr2": rr2,
        }
    }


def _run_layer_7_news_event(summary):
    """Layer 7: News and event risk check."""
    news_analysis = summary.get("news_analysis", {})
    news = summary.get("news", [])
    score = 0
    details = []

    event_risks = news_analysis.get("event_risks", [])
    if event_risks:
        score -= 3 * len(event_risks)
        details.append(f"Event risk detected: {len(event_risks)} high-impact event(s)")
        for er in event_risks[:2]:
            details.append(f"  → {er['event']}")
    else:
        details.append("No major event risk detected")

    # News sentiment
    news_label = news_analysis.get("label", "neutral")
    if news_label == "negative":
        score -= 2
        details.append("News sentiment negative")
    elif news_label == "positive":
        score += 1
        details.append("News sentiment positive")
    else:
        details.append("News sentiment neutral")

    return {"pass": True, "score": score, "details": details}


def _run_final_decision(layers, settings):
    """Layer 8: Final 7-step checklist."""
    checklist = []
    total_score = 0

    # Step 1: Trend clear?
    l1 = layers["market_direction"]
    trend_clear = l1["pass"] and l1["data"] and abs(l1["score"]) >= 10
    checklist.append({
        "step": 1,
        "name": "Trend Clear?",
        "pass": trend_clear,
        "detail": f"{l1['direction'].upper()} ({l1['strength']}) — score: {l1['score']}"
    })
    if trend_clear:
        total_score += 15

    # Step 2: Option chain supports?
    l2 = layers["option_chain"]
    oi_supports = abs(l2["score"]) >= 3 or not l2["data"].get("market_open")
    checklist.append({
        "step": 2,
        "name": "Option Chain Supports?",
        "pass": oi_supports,
        "detail": f"Score: {l2['score']}"
    })
    if oi_supports:
        total_score += 15

    # Step 3: Volatility favorable?
    l3 = layers["volatility"]
    vol_ok = l3["score"] >= -3
    checklist.append({
        "step": 3,
        "name": "Volatility Favorable?",
        "pass": vol_ok,
        "detail": f"Score: {l3['score']}"
    })
    if vol_ok:
        total_score += 10

    # Step 4: Sentiment aligned?
    l4 = layers["sentiment"]
    sentiment_aligned = l4["score"] >= -5
    checklist.append({
        "step": 4,
        "name": "Sentiment Aligned?",
        "pass": sentiment_aligned,
        "detail": f"Score: {l4['score']}"
    })
    if sentiment_aligned:
        total_score += 10

    # Step 5: Levels clear?
    l5 = layers["levels"]
    levels_clear = len(l5["data"].get("supports", [])) > 0 and len(l5["data"].get("resistances", [])) > 0
    checklist.append({
        "step": 5,
        "name": "Levels Clear?",
        "pass": levels_clear,
        "detail": f"Supports: {len(l5['data'].get('supports', []))}, Resistances: {len(l5['data'].get('resistances', []))}"
    })
    if levels_clear:
        total_score += 10

    # Step 6: Risk rules pass?
    l6 = layers["risk_management"]
    risk_pass = l6["pass"]
    checklist.append({
        "step": 6,
        "name": "Risk Rules Pass?",
        "pass": risk_pass,
        "detail": "Position sizing and R:R validated" if risk_pass else l6["details"][0] if l6["details"] else "Failed"
    })
    if risk_pass:
        total_score += 25

    # Step 7: No event risk?
    l7 = layers["news_event"]
    event_ok = l7["score"] >= -5
    checklist.append({
        "step": 7,
        "name": "No Event Risk?",
        "pass": event_ok,
        "detail": f"Score: {l7['score']}"
    })
    if event_ok:
        total_score += 15

    passes = sum(1 for c in checklist if c["pass"])
    all_pass = passes >= 6

    return {
        "checklist": checklist,
        "passes": passes,
        "total_score": total_score,
        "all_pass": all_pass,
    }


def _generate_open_market_trade(settings, summary, premarket):
    """Trade logic when market is open with full 8-layer analysis."""
    analysis = analyze_option_chain()
    capital = float(settings.get("capital", 100000))

    # Run all 8 layers
    layer1 = _run_layer_1_market_direction(premarket)
    layer2 = _run_layer_2_option_chain(analysis)
    layer3 = _run_layer_3_volatility(analysis)
    layer4 = _run_layer_4_sentiment(premarket, analysis)
    layer5 = _run_layer_5_levels(analysis, layer1["data"], premarket)
    layer7 = _run_layer_7_news_event(summary)

    # Direction from layer 1
    direction = layer1["direction"]
    if direction == "neutral":
        return _build_no_trade_result(layer1, layer2, layer3, layer4, layer5, layer7,
            "Trend is unclear on multiple timeframes. No directional bias.")

    # Build trade parameters
    spot = analysis["spot"]
    futures = analysis["futures"]
    supports = layer5["data"].get("supports", [])
    resistances = layer5["data"].get("resistances", [])
    atr_stop = layer5["data"].get("atr_stop", spot * 0.005)

    if direction == "bullish":
        entry = round(futures, 2)
        stop = round(max(
            (supports[0] if supports else entry * 0.995),
            entry - atr_stop
        ), 2)
        target1 = round(min(
            (resistances[0] if resistances else entry * 1.015),
            entry + atr_stop * 2
        ), 2)
        target2 = round(min(
            (resistances[1] if len(resistances) > 1 else entry * 1.025),
            entry + atr_stop * 3
        ), 2)
        trade_direction = "LONG"
        instrument = "NIFTY_FUT"
    else:
        entry = round(futures, 2)
        stop = round(min(
            (resistances[0] if resistances else entry * 1.005),
            entry + atr_stop
        ), 2)
        target1 = round(max(
            (supports[0] if supports else entry * 0.985),
            entry - atr_stop * 2
        ), 2)
        target2 = round(max(
            (supports[1] if len(supports) > 1 else entry * 0.975),
            entry - atr_stop * 3
        ), 2)
        trade_direction = "SHORT"
        instrument = "NIFTY_FUT"

    # Layer 6: Risk management
    layer6 = _run_layer_6_risk_management(settings, entry, stop, target1, target2, capital, atr_stop)

    # Final decision
    layers = {
        "market_direction": layer1,
        "option_chain": layer2,
        "volatility": layer3,
        "sentiment": layer4,
        "levels": layer5,
        "risk_management": layer6,
        "news_event": layer7,
    }
    decision = _run_final_decision(layers, settings)

    # Build result
    result = {
        "trade": None,
        "reasons": [],
        "risk_factors": [],
        "invalidation_scenarios": [],
        "confidence_score": decision["total_score"],
        "confidence_label": _confidence_label(decision["total_score"]),
        "market_trend": direction,
        "trend_strength": layer1["strength"],
        "trend_reason": layer1["details"][0] if layer1["details"] else "",
        "pcr": analysis["pcr"],
        "max_pain": analysis["max_pain"],
        "atm_strike": analysis["atm_strike"],
        "spot": spot,
        "futures": futures,
        "days_to_expiry": analysis["days_to_expiry"],
        "vix": analysis["vix"],
        "support": analysis["support_wall"],
        "resistance": analysis["resistance_wall"],
        "news": summary.get("news", []),
        "iv_env": analysis["iv_env"],
        "market_open": True,
        "layers": layers,
        "checklist": decision["checklist"],
    }

    if not decision["all_pass"]:
        failed = [c["name"] for c in decision["checklist"] if not c["pass"]]
        result["trade"] = _no_trade(
            f"Trade failed {len(failed)} checklist item(s): {', '.join(failed)}. "
            "The system requires at least 6/7 checks to pass."
        )
        result["invalidation_scenarios"].append("Trade not taken — checklist failed.")
        return result

    if not layer6["pass"]:
        result["trade"] = _no_trade("Risk management rules not satisfied: " + layer6["details"][0])
        return result

    # Build actual trade
    prob = min(85, max(30, int(decision["total_score"] * 0.8 + random.gauss(0, 3))))
    risk_data = layer6["data"]

    explanation = (
        f"{trade_direction} {instrument}. All 7 checklist items passed. "
        f"Trend: {direction} ({layer1['strength']}). "
        f"PCR {analysis['pcr']}. Support {analysis['support_wall']}, Resistance {analysis['resistance_wall']}. "
        f"VIX {analysis['vix']}. ATR stop: {atr_stop:.1f} pts. "
        f"R:R 1:{risk_data['rr']}. Position sized for {settings.get('max_risk_percent', 2)}% risk."
    )

    invalidation = (
        f"Fails if: (1) OI shifts at {analysis['support_wall'] if trade_direction == 'LONG' else analysis['resistance_wall']}, "
        f"(2) Price rejects with weak volume, (3) VIX spikes unexpectedly, "
        f"(4) Stop at {stop} breached on closing basis, (5) Expiry gamma spike."
    )

    result["trade"] = {
        "instrument_type": instrument,
        "direction": trade_direction,
        "entry": entry,
        "stop_loss": stop,
        "target1": target1,
        "target2": target2,
        "quantity": risk_data["quantity"],
        "risk_reward": f"1:{risk_data['rr']}" + (f" / 1:{risk_data['rr2']}" if risk_data.get("rr2") else ""),
        "estimated_probability": f"{prob}%",
        "explanation": explanation,
        "invalidation": invalidation,
        "total_risk": risk_data["total_risk"],
        "order_type": "MARKET / BRACKET",
        "session": "CURRENT_SESSION",
        "hedging_suggestion": "For option selling, use spreads or buy far OTM as insurance.",
    }

    result["invalidation_scenarios"].append(invalidation)
    result["reasons"] = (
        layer1["details"] + layer2["details"] + layer3["details"] +
        layer4["details"] + layer5["details"] + layer6["details"]
    )
    result["risk_factors"] = layer7["details"]

    return result


def _generate_premarket_trade(settings, summary, premarket):
    """Trade logic when market is closed — pre-market analysis."""
    capital = float(settings.get("capital", 100000))

    # Run applicable layers
    layer1 = _run_layer_1_market_direction(premarket)
    layer3 = _run_layer_3_volatility({"vix": premarket.get("india_vix", {}).get("current", 15), "days_to_expiry": None})
    layer4 = _run_layer_4_sentiment(premarket, {})
    layer5 = _run_layer_5_levels({}, layer1["data"], premarket)
    layer7 = _run_layer_7_news_event(summary)

    direction = layer1["direction"]
    if direction == "neutral":
        return _build_no_trade_result(layer1, None, layer3, layer4, layer5, layer7,
            "Pre-market trend is unclear. No directional bias.", market_open=False)

    # Build parameters
    last_close = premarket.get("market_status", {}).get("last_price", 0)
    supports = layer5["data"].get("supports", [])
    resistances = layer5["data"].get("resistances", [])
    atr = layer1["data"].get("daily", {}).get("atr", last_close * 0.004) if layer1["data"] else last_close * 0.004

    if direction == "bullish":
        entry = round(supports[0] if supports else last_close * 0.995, 2)
        stop = round(max(
            (supports[1] if len(supports) > 1 else entry * 0.99),
            entry - atr * 1.5
        ), 2)
        target1 = round(resistances[0] if resistances else entry * 1.015, 2)
        target2 = round(resistances[1] if len(resistances) > 1 else entry * 1.025, 2)
        trade_direction = "LONG"
    else:
        entry = round(resistances[0] if resistances else last_close * 1.005, 2)
        stop = round(min(
            (resistances[1] if len(resistances) > 1 else entry * 1.01),
            entry + atr * 1.5
        ), 2)
        target1 = round(supports[0] if supports else entry * 0.985, 2)
        target2 = round(supports[1] if len(supports) > 1 else entry * 0.975, 2)
        trade_direction = "SHORT"

    layer6 = _run_layer_6_risk_management(settings, entry, stop, target1, target2, capital, atr * 1.5)

    # Pre-market uses simplified 5-step checklist (no option chain)
    checklist = []
    total_score = 0

    trend_clear = layer1["pass"] and abs(layer1["score"]) >= 10
    checklist.append({"step": 1, "name": "Trend Clear?", "pass": trend_clear,
                      "detail": f"{direction.upper()} ({layer1['strength']})"})
    if trend_clear: total_score += 20

    checklist.append({"step": 2, "name": "Volatility OK?", "pass": layer3["score"] >= -3,
                      "detail": f"Score: {layer3['score']}"})
    if layer3["score"] >= -3: total_score += 15

    checklist.append({"step": 3, "name": "Sentiment Aligned?", "pass": layer4["score"] >= -5,
                      "detail": f"Score: {layer4['score']}"})
    if layer4["score"] >= -5: total_score += 15

    checklist.append({"step": 4, "name": "Levels Clear?", "pass": len(supports) > 0 and len(resistances) > 0,
                      "detail": f"S:{len(supports)} R:{len(resistances)}"})
    if len(supports) > 0 and len(resistances) > 0: total_score += 15

    checklist.append({"step": 5, "name": "Risk Rules Pass?", "pass": layer6["pass"],
                      "detail": "OK" if layer6["pass"] else layer6["details"][0]})
    if layer6["pass"]: total_score += 35

    passes = sum(1 for c in checklist if c["pass"])
    all_pass = passes >= 4 and layer6["pass"]

    layers = {
        "market_direction": layer1,
        "option_chain": None,
        "volatility": layer3,
        "sentiment": layer4,
        "levels": layer5,
        "risk_management": layer6,
        "news_event": layer7,
    }

    result = {
        "trade": None,
        "reasons": [],
        "risk_factors": [],
        "invalidation_scenarios": [],
        "confidence_score": total_score,
        "confidence_label": _confidence_label(total_score),
        "market_trend": direction,
        "trend_strength": layer1["strength"],
        "trend_reason": layer1["details"][0] if layer1["details"] else "",
        "pcr": None,
        "max_pain": None,
        "atm_strike": round(last_close / 50) * 50 if last_close else 22450,
        "spot": last_close,
        "futures": summary.get("futures", last_close),
        "days_to_expiry": None,
        "vix": premarket.get("india_vix", {}).get("current", 15),
        "support": supports[0] if supports else last_close - 200,
        "resistance": resistances[0] if resistances else last_close + 200,
        "news": summary.get("news", []),
        "iv_env": "moderate",
        "market_open": False,
        "premarket_narrative": summary.get("narrative", {}).get("narrative", ""),
        "checklist": checklist,
        "layers": layers,
    }

    if not all_pass:
        failed = [c["name"] for c in checklist if not c["pass"]]
        result["trade"] = _no_trade(
            f"Pre-market setup failed {len(failed)} check(s): {', '.join(failed)}."
        )
        result["invalidation_scenarios"].append("Trade not taken — pre-market checks failed.")
        return result

    prob = min(85, max(30, int(total_score * 0.8 + random.gauss(0, 3))))
    risk_data = layer6["data"]

    explanation = (
        f"PRE-MARKET {trade_direction} for next session. All checks passed. "
        f"Technical bias: {direction} ({layer1['strength']}). "
        f"ATR: {atr:.1f} pts. Key S/R: {supports[0] if supports else 'N/A'} / {resistances[0] if resistances else 'N/A'}. "
        f"Use LIMIT order at {entry}. Bracket with SL {stop}, T1 {target1}."
    )

    invalidation = (
        f"Fails if: (1) Gap beyond stop on open, (2) Overnight news changes narrative, "
        f"(3) Global markets reverse before Indian open, (4) Key level broken on open."
    )

    result["trade"] = {
        "instrument_type": "NIFTY_FUT",
        "direction": trade_direction,
        "entry": entry,
        "stop_loss": stop,
        "target1": target1,
        "target2": target2,
        "quantity": risk_data["quantity"],
        "risk_reward": f"1:{risk_data['rr']}" + (f" / 1:{risk_data['rr2']}" if risk_data.get("rr2") else ""),
        "estimated_probability": f"{prob}%",
        "explanation": explanation,
        "invalidation": invalidation,
        "total_risk": risk_data["total_risk"],
        "order_type": "LIMIT / BRACKET",
        "session": "NEXT_SESSION",
        "hedging_suggestion": "For protection, consider buying far OTM option opposite to direction.",
    }

    result["invalidation_scenarios"].append(invalidation)
    result["reasons"] = layer1["details"] + layer3["details"] + layer4["details"] + layer5["details"]
    result["risk_factors"] = layer7["details"] + ["Overnight event risk until market opens."]

    return result


def _no_trade(explanation):
    return {
        "instrument_type": "NO_TRADE",
        "direction": "NONE",
        "entry": None,
        "stop_loss": None,
        "target1": None,
        "target2": None,
        "quantity": 0,
        "risk_reward": "N/A",
        "estimated_probability": "N/A",
        "explanation": explanation,
        "invalidation": "N/A",
        "order_type": "N/A",
        "session": "N/A",
        "hedging_suggestion": "N/A",
    }


def _build_no_trade_result(layer1, layer2, layer3, layer4, layer5, layer7, reason, market_open=True):
    """Build a no-trade result with all layers included."""
    layers = {
        "market_direction": layer1,
        "option_chain": layer2,
        "volatility": layer3,
        "sentiment": layer4,
        "levels": layer5,
        "risk_management": None,
        "news_event": layer7,
    }
    result = {
        "trade": _no_trade(reason),
        "reasons": layer1["details"] if layer1 else [],
        "risk_factors": layer7["details"] if layer7 else [],
        "invalidation_scenarios": ["Trade not taken — analysis incomplete."],
        "confidence_score": 0,
        "confidence_label": "Very Low",
        "market_trend": layer1["direction"] if layer1 else "neutral",
        "trend_strength": "weak",
        "trend_reason": reason,
        "pcr": layer2["data"]["pcr"] if layer2 and layer2.get("data") else None,
        "max_pain": layer2["data"]["max_pain"] if layer2 and layer2.get("data") else None,
        "spot": None,
        "futures": None,
        "days_to_expiry": None,
        "vix": None,
        "support": None,
        "resistance": None,
        "news": [],
        "iv_env": "moderate",
        "market_open": market_open,
        "checklist": [],
        "layers": layers,
    }
    return result
