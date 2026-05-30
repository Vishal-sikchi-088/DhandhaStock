"""
AI Reasoning Service — Institutional Options Trading Engine
6-Step Professional Framework:

1. Market Structure Analysis (SMC/ICT)
2. Multi-Timeframe Analysis (Daily, 1H, 15M, 5M)
3. Option Chain Deep Analysis (OI, PCR, Buildup, Walls)
4. Volatility Analysis (VIX, IV, DTE)
5. Institutional Activity (FII/DII, Futures OI)
6. Trade Decision (Probability >= 70%, Quality Score, Risk Management)

Trade is ONLY emitted when probability >= 70% and all conditions align.
"""

import random
from datetime import datetime

from .analysis import analyze_option_chain, get_trend_analysis
from .market_data import get_market_summary
from .premarket_data import get_all_premarket_data
from .chart_analysis import analyze_chart
from .news_ai import generate_market_news_context, analyze_news_sentiment, get_ai_market_narrative
from .database import get_settings

# New institutional engines
from .smc_analysis import analyze_smc
from .volume_profile_vwap import analyze_vwap_and_profile
from .oi_analyzer import analyze_deep_oi, save_oi_snapshot
from .institutional_flow import analyze_institutional_flow
from .probability_engine import calculate_probability, calculate_trade_quality_score
from .strike_selector import select_strike, approximate_delta
from .strategy_selector import recommend_strategy_for_conditions
from .risk_manager import calculate_position_size


def _calculate_rr(entry, stop, target):
    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk == 0:
        return 0
    return round(reward / risk, 2)


def _confidence_label(score):
    if score >= 85:
        return "High"
    elif score >= 70:
        return "Moderate"
    elif score >= 55:
        return "Low"
    return "Very Low"


def generate_trade_idea(settings):
    """Main trade generation with full 6-layer institutional analysis."""
    settings = settings or {"capital": 100000, "max_risk_percent": 2.0}
    summary = get_market_summary()
    premarket = get_all_premarket_data()
    
    # Fetch all analysis data
    chart = analyze_chart(
        premarket.get("historical_daily"),
        premarket.get("historical_60m"),
        premarket.get("historical_15m"),
        premarket.get("historical_5m"),
    ) if premarket else None
    
    vwap_profile = chart.get("vwap_profile") if chart else None
    smc = chart.get("smc") if chart else None
    
    # Option chain analysis
    analysis = analyze_option_chain()
    oi_data = analyze_deep_oi(analysis) if analysis and analysis.get("market_open") else None
    
    # Institutional flow
    flow_data = analyze_institutional_flow()
    
    # VIX data
    vix_data = premarket.get("india_vix", {}) if premarket else {}
    
    # Probability calculation
    probability_result = calculate_probability(
        smc, chart, oi_data, analysis, vwap_profile, flow_data, vix_data
    )
    
    # Route to appropriate handler
    if analysis and analysis.get("market_open"):
        return _generate_open_market_trade(
            settings, summary, premarket, analysis, chart, oi_data, 
            vwap_profile, smc, flow_data, probability_result
        )
    else:
        return _generate_premarket_trade(
            settings, summary, premarket, chart, vwap_profile, smc,
            flow_data, probability_result
        )


def _generate_open_market_trade(settings, summary, premarket, analysis, chart, oi_data,
                                 vwap_profile, smc, flow_data, probability_result):
    """Trade logic when market is open with full institutional analysis."""
    capital = float(settings.get("capital", 100000))
    max_risk_pct = float(settings.get("max_risk_percent", 2.0))
    
    spot = analysis["spot"]
    futures = analysis["futures"]
    vix = analysis["vix"]
    days_to_expiry = analysis["days_to_expiry"]
    
    # Step 1-5 summaries
    market_structure = _summarize_market_structure(smc, chart)
    multi_tf = _summarize_multi_timeframe(chart)
    option_chain_summary = _summarize_option_chain(oi_data, analysis)
    volatility_summary = _summarize_volatility(analysis)
    institutional_summary = _summarize_institutional(flow_data)
    
    # Step 6: Decision
    probability = probability_result["probability"]
    direction = probability_result["direction"]
    
    if probability < 70:
        return _build_no_trade_output(
            probability, direction, market_structure, multi_tf, option_chain_summary,
            volatility_summary, institutional_summary, 
            "Probability below 70% threshold. Edge not present.",
            analysis, chart, oi_data, vwap_profile, smc, flow_data, probability_result,
            market_open=True
        )
    
    if direction == "neutral":
        return _build_no_trade_output(
            probability, direction, market_structure, multi_tf, option_chain_summary,
            volatility_summary, institutional_summary,
            "Direction is neutral. No clear directional bias.",
            analysis, chart, oi_data, vwap_profile, smc, flow_data, probability_result,
            market_open=True
        )
    
    # Strategy selection
    strategy = recommend_strategy_for_conditions(analysis, chart, probability_result)
    
    # Strike selection
    strike_selection = select_strike(direction, analysis)
    if strike_selection.get("error"):
        # Fallback to ATM strike
        atm = analysis["atm_strike"]
        strike_selection = {
            "recommended_strike": atm,
            "recommended_delta": 0.5,
            "estimated_premium": 100,
            "instrument_type": "CALL" if direction == "bullish" else "PUT",
        }
    
    # Build trade parameters
    supports = chart.get("key_levels", []) if chart else []
    support_prices = sorted([l["price"] for l in supports if l.get("role") == "support"], reverse=True)
    resistance_prices = sorted([l["price"] for l in supports if l.get("role") == "resistance"])
    
    # ATR for stop calculation
    daily = chart.get("daily", {}) if chart else {}
    atr = daily.get("atr", spot * 0.004)
    
    # Entry: use futures for futures trades, or spot for options
    is_options = strategy.get("type") in ["directional", "directional_spread"]
    
    if is_options and strike_selection:
        entry = round(strike_selection["recommended_strike"], 2)
        # For options, entry is the strike, but we track spot for SL/target
        spot_entry = round(futures, 2)
    else:
        entry = round(futures, 2)
        spot_entry = entry
    
    if direction == "bullish":
        stop = round(max(
            (support_prices[0] if support_prices else entry * 0.995),
            spot_entry - atr * 1.5
        ), 2)
        target1 = round(min(
            (resistance_prices[0] if resistance_prices else entry * 1.015),
            spot_entry + atr * 2.5
        ), 2)
        target2 = round(min(
            (resistance_prices[1] if len(resistance_prices) > 1 else entry * 1.03),
            spot_entry + atr * 4
        ), 2)
        target3 = round(min(
            (resistance_prices[2] if len(resistance_prices) > 2 else entry * 1.045),
            spot_entry + atr * 5.5
        ), 2)
        trade_direction = "LONG"
    else:
        stop = round(min(
            (resistance_prices[0] if resistance_prices else entry * 1.005),
            spot_entry + atr * 1.5
        ), 2)
        target1 = round(max(
            (support_prices[0] if support_prices else entry * 0.985),
            spot_entry - atr * 2.5
        ), 2)
        target2 = round(max(
            (support_prices[1] if len(support_prices) > 1 else entry * 0.97),
            spot_entry - atr * 4
        ), 2)
        target3 = round(max(
            (support_prices[2] if len(support_prices) > 2 else entry * 0.955),
            spot_entry - atr * 5.5
        ), 2)
        trade_direction = "SHORT"
    
    # Risk management
    rr1 = _calculate_rr(spot_entry, stop, target1)
    rr2 = _calculate_rr(spot_entry, stop, target2)
    rr3 = _calculate_rr(spot_entry, stop, target3)
    
    if rr1 < 1.2:
        return _build_no_trade_output(
            probability, direction, market_structure, multi_tf, option_chain_summary,
            volatility_summary, institutional_summary,
            f"R:R {rr1} below 1:1.2 minimum. Risk management prevents entry.",
            analysis, chart, oi_data, vwap_profile, smc, flow_data, probability_result,
            market_open=True
        )
    
    # Position sizing
    point_value = 50  # Nifty lot size
    risk_per_point = abs(spot_entry - stop)
    
    if is_options:
        # For options, risk is premium + some buffer
        premium = strike_selection.get("estimated_premium", 100)
        # Simplified: max loss is premium paid, but we also set a spot SL
        # Use spot-based SL for quantity calculation
        max_risk_rupees = capital * max_risk_pct / 100
        # For options, quantity = max_risk / (premium * lot_size)
        # But we also consider delta-adjusted notional
        delta = abs(strike_selection.get("recommended_delta", 0.5))
        effective_risk_per_lot = premium * point_value
        quantity = max(1, int(max_risk_rupees / effective_risk_per_lot))
        total_risk = quantity * effective_risk_per_lot
    else:
        max_risk_rupees = capital * max_risk_pct / 100
        risk_per_lot = risk_per_point * point_value
        quantity = max(1, int(max_risk_rupees / risk_per_lot))
        total_risk = quantity * risk_per_lot
    
    # Trade Quality Score
    news_analysis = summary.get("news_analysis", {})
    event_risks = len(news_analysis.get("event_risks", [])) > 0
    
    quality = calculate_trade_quality_score(
        probability_result, spot_entry, stop, target1, target2,
        chart, flow_data, event_risks, days_to_expiry
    )
    
    # Build trade output
    instrument = "NIFTY"
    trade_type = strike_selection.get("instrument_type", "CALL" if direction == "bullish" else "PUT")
    strike = strike_selection.get("recommended_strike", analysis["atm_strike"])
    expiry = analysis.get("expiry_date", "Nearest Weekly")
    
    trade = {
        "instrument_type": instrument,
        "trade_type": trade_type,
        "direction": trade_direction,
        "strike": strike,
        "expiry": expiry,
        "entry": spot_entry,
        "stop_loss": stop,
        "target1": target1,
        "target2": target2,
        "target3": target3,
        "quantity": quantity,
        "risk_reward": f"1:{rr1}" + (f" / 1:{rr2}" if rr2 else ""),
        "risk_reward_3": f"1:{rr3}" if rr3 else "N/A",
        "estimated_probability": f"{probability:.1f}%",
        "expected_holding_time": "30-90 Minutes" if days_to_expiry and days_to_expiry <= 3 else "2-4 Hours",
        "total_risk": round(total_risk, 2),
        "order_type": "MARKET / BRACKET",
        "session": "CURRENT_SESSION",
        "strategy": strategy.get("strategy_name", "Long Option"),
        "delta": strike_selection.get("recommended_delta"),
        "premium_estimate": strike_selection.get("estimated_premium"),
    }
    
    return _build_trade_output(
        trade, direction, probability, quality, market_structure, multi_tf,
        option_chain_summary, volatility_summary, institutional_summary,
        analysis, chart, oi_data, vwap_profile, smc, flow_data, probability_result,
        strategy, market_open=True
    )


def _generate_premarket_trade(settings, summary, premarket, chart, vwap_profile, smc,
                               flow_data, probability_result):
    """Trade logic when market is closed — pre-market analysis."""
    capital = float(settings.get("capital", 100000))
    max_risk_pct = float(settings.get("max_risk_percent", 2.0))
    
    last_close = premarket.get("market_status", {}).get("last_price", 0)
    vix = premarket.get("india_vix", {}).get("current", 15)
    
    # Step summaries (simplified for pre-market)
    market_structure = _summarize_market_structure(smc, chart)
    multi_tf = _summarize_multi_timeframe(chart)
    option_chain_summary = {"summary": "Market closed — option chain unavailable", "pcr": None}
    volatility_summary = _summarize_volatility({"vix": vix, "days_to_expiry": None, "iv_analysis": None})
    institutional_summary = _summarize_institutional(flow_data)
    
    probability = probability_result["probability"]
    direction = probability_result["direction"]
    
    if probability < 70:
        return _build_no_trade_output(
            probability, direction, market_structure, multi_tf, option_chain_summary,
            volatility_summary, institutional_summary,
            "Pre-market probability below 70%. Edge not present.",
            None, chart, None, vwap_profile, smc, flow_data, probability_result,
            market_open=False
        )
    
    if direction == "neutral":
        return _build_no_trade_output(
            probability, direction, market_structure, multi_tf, option_chain_summary,
            volatility_summary, institutional_summary,
            "Pre-market direction unclear. No trade.",
            None, chart, None, vwap_profile, smc, flow_data, probability_result,
            market_open=False
        )
    
    # Pre-market uses simplified strike (ATM estimate)
    atm = round(last_close / 50) * 50 if last_close else 22450
    
    supports = chart.get("key_levels", []) if chart else []
    support_prices = sorted([l["price"] for l in supports if l.get("role") == "support"], reverse=True)
    resistance_prices = sorted([l["price"] for l in supports if l.get("role") == "resistance"])
    
    daily = chart.get("daily", {}) if chart else {}
    atr = daily.get("atr", last_close * 0.004) if last_close else 100
    
    if direction == "bullish":
        entry = round(support_prices[0] if support_prices else last_close * 0.995, 2)
        stop = round(max(
            (support_prices[1] if len(support_prices) > 1 else entry * 0.99),
            entry - atr * 1.5
        ), 2)
        target1 = round(resistance_prices[0] if resistance_prices else entry * 1.015, 2)
        target2 = round(resistance_prices[1] if len(resistance_prices) > 1 else entry * 1.025, 2)
        target3 = round(resistance_prices[2] if len(resistance_prices) > 2 else entry * 1.04, 2)
        trade_direction = "LONG"
        trade_type = "CALL"
    else:
        entry = round(resistance_prices[0] if resistance_prices else last_close * 1.005, 2)
        stop = round(min(
            (resistance_prices[1] if len(resistance_prices) > 1 else entry * 1.01),
            entry + atr * 1.5
        ), 2)
        target1 = round(support_prices[0] if support_prices else entry * 0.985, 2)
        target2 = round(support_prices[1] if len(support_prices) > 1 else entry * 0.975, 2)
        target3 = round(support_prices[2] if len(support_prices) > 2 else entry * 0.96, 2)
        trade_direction = "SHORT"
        trade_type = "PUT"
    
    rr1 = _calculate_rr(entry, stop, target1)
    rr2 = _calculate_rr(entry, stop, target2)
    rr3 = _calculate_rr(entry, stop, target3)
    
    if rr1 < 1.2:
        return _build_no_trade_output(
            probability, direction, market_structure, multi_tf, option_chain_summary,
            volatility_summary, institutional_summary,
            f"Pre-market R:R {rr1} below minimum. No trade.",
            None, chart, None, vwap_profile, smc, flow_data, probability_result,
            market_open=False
        )
    
    # Position sizing (pre-market estimate)
    max_risk_rupees = capital * max_risk_pct / 100
    risk_per_point = abs(entry - stop)
    point_value = 50
    
    # For pre-market, assume ATM premium ~ 1.5x ATR in points
    estimated_premium = atr * 1.5
    effective_risk_per_lot = estimated_premium * point_value
    quantity = max(1, int(max_risk_rupees / effective_risk_per_lot))
    total_risk = quantity * effective_risk_per_lot
    
    quality = calculate_trade_quality_score(
        probability_result, entry, stop, target1, target2,
        chart, flow_data, False, None
    )
    
    trade = {
        "instrument_type": "NIFTY",
        "trade_type": trade_type,
        "direction": trade_direction,
        "strike": atm,
        "expiry": "Nearest Weekly",
        "entry": entry,
        "stop_loss": stop,
        "target1": target1,
        "target2": target2,
        "target3": target3,
        "quantity": quantity,
        "risk_reward": f"1:{rr1}" + (f" / 1:{rr2}" if rr2 else ""),
        "risk_reward_3": f"1:{rr3}" if rr3 else "N/A",
        "estimated_probability": f"{probability:.1f}%",
        "expected_holding_time": "Next Session",
        "total_risk": round(total_risk, 2),
        "order_type": "LIMIT / BRACKET",
        "session": "NEXT_SESSION",
        "strategy": "Pre-Market Directional",
        "delta": 0.5,
        "premium_estimate": round(estimated_premium, 2),
    }
    
    return _build_trade_output(
        trade, direction, probability, quality, market_structure, multi_tf,
        option_chain_summary, volatility_summary, institutional_summary,
        None, chart, None, vwap_profile, smc, flow_data, probability_result,
        {"strategy_name": "Pre-Market Directional"}, market_open=False
    )


# ---- Summarizers ----

def _summarize_market_structure(smc, chart):
    """Step 1 summary."""
    if not smc or smc.get("error"):
        return {"bias": "neutral", "confidence": 0, "details": ["SMC data unavailable"]}
    
    bias = smc.get("bias", "neutral")
    structure = smc.get("structure", "undefined")
    
    confidence = 60 if bias != "neutral" else 30
    if smc.get("last_bos"):
        confidence += 10
    if smc.get("last_choch"):
        confidence += 10
    
    details = [
        f"Market structure: {structure}",
        f"SMC bias: {bias}",
    ]
    if smc.get("last_bos"):
        details.append(f"Last BOS: {smc['last_bos']['type']} at {smc['last_bos']['level']}")
    if smc.get("last_choch"):
        details.append(f"Last CHoCH: {smc['last_choch']['type']} at {smc['last_choch']['level']}")
    
    return {"bias": bias, "confidence": min(100, confidence), "details": details}


def _summarize_multi_timeframe(chart):
    """Step 2 summary."""
    if not chart or chart.get("error"):
        return {"alignment": "unknown", "confidence": 0, "details": ["Chart data unavailable"]}
    
    alignment = chart.get("multi_timeframe_alignment", "mixed")
    bias = chart.get("bias", "neutral")
    score = chart.get("bias_score", 0)
    
    daily = chart.get("daily", {})
    tf60 = chart.get("tf_60min", {})
    tf15 = chart.get("tf_15min", {})
    tf5 = chart.get("tf_5min", {})
    
    confidence = 50 + abs(score) * 5
    confidence = min(100, max(0, confidence))
    
    details = chart.get("bias_reasons", [])
    details.insert(0, f"Multi-timeframe alignment: {alignment}")
    
    # Support/Resistance from all timeframes
    levels = chart.get("key_levels", [])
    supports = sorted([l["price"] for l in levels if l.get("role") == "support"], reverse=True)[:3]
    resistances = sorted([l["price"] for l in levels if l.get("role") == "resistance"])[:3]
    
    return {
        "alignment": alignment,
        "bias": bias,
        "confidence": round(confidence, 1),
        "details": details,
        "supports": supports,
        "resistances": resistances,
        "daily_trend": daily.get("trend_structure", {}).get("trend", "sideways") if daily else "unknown",
        "tf60_trend": tf60.get("trend_structure", {}).get("trend", "sideways") if tf60 else "unknown",
        "tf15_trend": tf15.get("trend_structure", {}).get("trend", "sideways") if tf15 else "unknown",
        "tf5_trend": tf5.get("trend_structure", {}).get("trend", "sideways") if tf5 else "unknown",
    }


def _summarize_option_chain(oi_data, analysis):
    """Step 3 summary."""
    if not analysis or not analysis.get("market_open"):
        return {"summary": "Market closed", "pcr": None, "details": ["Option chain unavailable"]}
    
    pcr = analysis.get("pcr", 1.0)
    pcr_signal = analysis.get("pcr_signal", "neutral")
    max_pain = analysis.get("max_pain", 0)
    spot = analysis.get("spot", 0)
    
    details = [
        f"PCR: {pcr:.2f} ({pcr_signal})",
        f"Max Pain: {max_pain}",
        f"Spot vs Max Pain: {spot - max_pain:+.0f} pts",
    ]
    
    if oi_data and not oi_data.get("error"):
        buildup = oi_data.get("oi_buildup", {})
        if buildup:
            details.append(f"OI Bias: {buildup.get('oi_bias', 'neutral')}")
            details.append(buildup.get("oi_reason", ""))
        
        walls = oi_data.get("walls", {})
        if walls.get("support"):
            details.append(f"Support Wall: {walls['support']['strike']} (strength {walls['support']['strength_score']})")
        if walls.get("resistance"):
            details.append(f"Resistance Wall: {walls['resistance']['strike']} (strength {walls['resistance']['strength_score']})")
    
    return {
        "pcr": pcr,
        "pcr_signal": pcr_signal,
        "max_pain": max_pain,
        "details": details,
    }


def _summarize_volatility(analysis):
    """Step 4 summary."""
    vix = analysis.get("vix", 15) if analysis else 15
    days_to_expiry = analysis.get("days_to_expiry", 7) if analysis else 7
    iv_analysis = analysis.get("iv_analysis") if analysis else None
    
    details = [f"VIX: {vix}"]
    
    if days_to_expiry is not None:
        details.append(f"Days to Expiry: {days_to_expiry}")
    
    if iv_analysis:
        iv_pct = iv_analysis.get("iv_percentile")
        if iv_pct is not None:
            details.append(f"IV Percentile: {iv_pct}%")
    
    if vix > 20:
        env = "high"
        details.append("Elevated VIX — wider stops, expect larger moves")
    elif vix < 12:
        env = "low"
        details.append("Low VIX — breakouts may fail, rangebound likely")
    else:
        env = "moderate"
        details.append("Moderate VIX — balanced environment")
    
    return {"vix": vix, "dte": days_to_expiry, "environment": env, "details": details}


def _summarize_institutional(flow_data):
    """Step 5 summary."""
    if not flow_data or flow_data.get("error"):
        return {"bias": "neutral", "details": ["Institutional data unavailable"]}
    
    bias = flow_data.get("cumulative_bias", "neutral")
    score = flow_data.get("cumulative_score", 0)
    reasons = flow_data.get("reasons", [])
    
    fii_dii = flow_data.get("fii_dii", {})
    futures = flow_data.get("futures", {})
    
    details = reasons.copy()
    if fii_dii:
        details.insert(0, f"FII Net: ₹{fii_dii.get('fii_net', 0):.0f} cr")
        details.insert(1, f"DII Net: ₹{fii_dii.get('dii_net', 0):.0f} cr")
    if futures:
        details.append(f"Futures: {futures.get('classification', 'unknown')}")
    
    return {"bias": bias, "score": score, "details": details}


# ---- Output Builders ----

def _build_trade_output(trade, direction, probability, quality, market_structure, multi_tf,
                         option_chain_summary, volatility_summary, institutional_summary,
                         analysis, chart, oi_data, vwap_profile, smc, flow_data, probability_result,
                         strategy, market_open=True):
    """Build the exact institutional trade output format."""
    
    # Determine risk level
    vix = volatility_summary.get("vix", 15)
    dte = volatility_summary.get("dte", 7)
    if vix > 20 or (dte and dte <= 1):
        risk_level = "High"
    elif vix > 16 or (dte and dte <= 3):
        risk_level = "Medium"
    else:
        risk_level = "Low"
    
    # Build reasoning
    trend_reasoning = " | ".join(multi_tf.get("details", [])[:4])
    oi_reasoning = " | ".join(option_chain_summary.get("details", [])[:3])
    vol_reasoning = " | ".join(volatility_summary.get("details", [])[:3])
    inst_reasoning = " | ".join(institutional_summary.get("details", [])[:3])
    
    vwap_reasoning = ""
    if vwap_profile and not vwap_profile.get("error"):
        vwap_signals = vwap_profile.get("vwap_signals", [])
        if vwap_signals:
            vwap_reasoning = vwap_signals[0]
    
    # Build probability breakdown
    scores = probability_result.get("scores", {})
    
    return {
        # Core trade object
        "trade": trade,
        
        # Market Bias
        "market_bias": direction.upper(),
        "confidence": round(probability, 1),
        "confidence_label": _confidence_label(probability),
        
        # Best Trade (detailed)
        "instrument": trade["instrument_type"],
        "trade_type": trade["trade_type"],
        "strike": trade["strike"],
        "expiry": trade["expiry"],
        "entry": trade["entry"],
        "stop_loss": trade["stop_loss"],
        "target1": trade["target1"],
        "target2": trade["target2"],
        "target3": trade["target3"],
        "risk_reward": trade["risk_reward"],
        "expected_holding_time": trade["expected_holding_time"],
        "probability": trade["estimated_probability"],
        
        # Trade Reasoning
        "trend_analysis": trend_reasoning,
        "option_chain_confirmation": oi_reasoning,
        "volume_confirmation": vwap_reasoning,
        "vwap_confirmation": vwap_reasoning,
        "institutional_confirmation": inst_reasoning,
        
        # Risk Assessment
        "risk_level": risk_level,
        "invalidation_level": trade["stop_loss"],
        "max_capital_risk_percent": 1.0,
        "position_size_recommendation": f"{trade['quantity']} lot(s)",
        
        # Scores
        "trade_quality_score": quality["trade_quality_score"],
        "trade_quality_grade": quality["grade"],
        "market_sentiment": direction.upper(),
        "best_action": f"BUY {trade['trade_type']}",
        "one_line_summary": (
            f"{trade['trade_type']} NIFTY {trade['strike']} — "
            f"{direction.upper()} bias, {probability:.0f}% probability, "
            f"Quality {quality['grade']} ({quality['trade_quality_score']:.0f}/100). "
            f"Entry {trade['entry']}, SL {trade['stop_loss']}, T1 {trade['target1']}. "
            f"R:R {trade['risk_reward']}."
        ),
        
        # Extended data for frontend
        "market_structure": market_structure,
        "multi_timeframe": multi_tf,
        "option_chain_summary": option_chain_summary,
        "volatility_summary": volatility_summary,
        "institutional_summary": institutional_summary,
        "strategy": strategy,
        "quality": quality,
        "probability_breakdown": scores,
        
        # Market data
        "spot": analysis["spot"] if analysis else None,
        "futures": analysis["futures"] if analysis else None,
        "pcr": analysis["pcr"] if analysis else None,
        "max_pain": analysis["max_pain"] if analysis else None,
        "vix": volatility_summary.get("vix"),
        "days_to_expiry": volatility_summary.get("dte"),
        "market_open": market_open,
        
        # Raw data for advanced users
        "layers": {
            "market_structure": market_structure,
            "multi_timeframe": multi_tf,
            "option_chain": option_chain_summary,
            "volatility": volatility_summary,
            "institutional": institutional_summary,
            "probability": probability_result,
        },
        
        # Invalidation scenarios
        "invalidation_scenarios": [
            f"Price closes beyond stop loss at {trade['stop_loss']}",
            f"Market structure changes (CHoCH against {direction} bias)",
            f"VIX spikes above {vix + 5:.0f} unexpectedly",
            f"Major support/resistance level at {trade['target1']} rejected with weak volume",
            "Institutional flow reverses (FII heavy selling/buying against position)",
        ],
        
        # Risk factors
        "risk_factors": [
            f"VIX at {vix} — {'elevated' if vix > 20 else 'moderate' if vix > 12 else 'low'} volatility environment",
            f"Days to expiry: {dte if dte else 'Unknown'} — {'gamma risk high' if dte and dte <= 1 else 'theta decay manageable' if dte and dte > 3 else 'moderate time decay'}",
            "Overnight/event risk until next session" if not market_open else "Intraday volatility risk",
        ],
        
        # Reasons
        "reasons": quality.get("reasons", []),
    }


def _build_no_trade_output(probability, direction, market_structure, multi_tf,
                            option_chain_summary, volatility_summary, institutional_summary,
                            reason, analysis, chart, oi_data, vwap_profile, smc, flow_data,
                            probability_result, market_open=True):
    """Build NO TRADE output with full analysis context."""
    
    last_close = chart.get("last_close") if chart else (analysis["spot"] if analysis else 0)
    
    no_trade = {
        "instrument_type": "NO_TRADE",
        "trade_type": "NONE",
        "direction": "NONE",
        "strike": None,
        "expiry": None,
        "entry": None,
        "stop_loss": None,
        "target1": None,
        "target2": None,
        "target3": None,
        "quantity": 0,
        "risk_reward": "N/A",
        "expected_holding_time": "N/A",
        "estimated_probability": "N/A",
        "total_risk": 0,
        "order_type": "N/A",
        "session": "N/A",
        "strategy": "NO_TRADE",
        "delta": None,
        "premium_estimate": None,
    }
    
    return {
        "trade": no_trade,
        "market_bias": direction.upper() if direction != "neutral" else "NEUTRAL",
        "confidence": round(probability, 1),
        "confidence_label": _confidence_label(probability),
        "instrument": "NIFTY",
        "trade_type": "NO TRADE",
        "entry": None,
        "stop_loss": None,
        "target1": None,
        "target2": None,
        "target3": None,
        "risk_reward": "N/A",
        "expected_holding_time": "N/A",
        "probability": f"{probability:.1f}%",
        "trend_analysis": " | ".join(multi_tf.get("details", [])[:3]) if multi_tf else "N/A",
        "option_chain_confirmation": " | ".join(option_chain_summary.get("details", [])[:3]) if option_chain_summary else "N/A",
        "volume_confirmation": "N/A",
        "vwap_confirmation": "N/A",
        "institutional_confirmation": " | ".join(institutional_summary.get("details", [])[:3]) if institutional_summary else "N/A",
        "risk_level": "N/A",
        "invalidation_level": None,
        "max_capital_risk_percent": 0,
        "position_size_recommendation": "0 lots",
        "trade_quality_score": 0,
        "trade_quality_grade": "F",
        "market_sentiment": "NEUTRAL",
        "best_action": "WAIT",
        "one_line_summary": f"NO TRADE — {reason} (Probability: {probability:.0f}%)",
        "market_structure": market_structure,
        "multi_timeframe": multi_tf,
        "option_chain_summary": option_chain_summary,
        "volatility_summary": volatility_summary,
        "institutional_summary": institutional_summary,
        "strategy": {"strategy_name": "NO_TRADE"},
        "quality": {"trade_quality_score": 0, "grade": "F", "reasons": [reason]},
        "probability_breakdown": probability_result.get("scores", {}) if probability_result else {},
        "spot": analysis["spot"] if analysis else last_close,
        "futures": analysis["futures"] if analysis else last_close,
        "pcr": analysis["pcr"] if analysis else None,
        "max_pain": analysis["max_pain"] if analysis else None,
        "vix": volatility_summary.get("vix"),
        "days_to_expiry": volatility_summary.get("dte"),
        "market_open": market_open,
        "layers": {
            "market_structure": market_structure,
            "multi_timeframe": multi_tf,
            "option_chain": option_chain_summary,
            "volatility": volatility_summary,
            "institutional": institutional_summary,
            "probability": probability_result,
        },
        "invalidation_scenarios": [reason],
        "risk_factors": ["No trade taken — capital protected"],
        "reasons": [reason],
    }
