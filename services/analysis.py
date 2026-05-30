"""
Analysis Service
Processes option chain and pre-market data to extract support, resistance, sentiment,
trend strength, key levels, IV analysis, delta estimates, and breakeven calculations.
"""

import math
from .market_data import generate_option_chain, get_market_summary
from .premarket_data import get_all_premarket_data
from .chart_analysis import analyze_chart
from .database import save_iv_history, get_iv_history


def analyze_option_chain():
    """
    Deep analysis of option chain when market is open.
    Returns structured data for the dashboard and AI reasoning.
    """
    data = generate_option_chain()

    if data is None:
        summary = get_market_summary()
        return {
            "spot": summary.get("spot", 0),
            "futures": summary.get("futures", 0),
            "atm_strike": round(summary.get("spot", 22450) / 50) * 50,
            "strikes": [],
            "resistance_wall": summary.get("resistance", 0),
            "support_wall": summary.get("support", 0),
            "short_resistance": summary.get("resistance", 0),
            "short_support": summary.get("support", 0),
            "highest_ce_oi_strike": None,
            "highest_pe_oi_strike": None,
            "ce_writing_strikes": [],
            "pe_writing_strikes": [],
            "pcr": 1.0,
            "pcr_signal": "neutral",
            "pcr_desc": "Option chain unavailable (market closed).",
            "vol_pcr": 1.0,
            "max_pain": summary.get("spot", 0),
            "pain_signal": "neutral",
            "pain_desc": "Max pain unavailable (market closed).",
            "basis": 0,
            "basis_signal": "neutral",
            "basis_desc": "Futures basis unavailable (market closed).",
            "vix": summary.get("vix", 15),
            "iv_env": "moderate",
            "iv_desc": f"VIX at {summary.get('vix', 15)}.",
            "days_to_expiry": summary.get("days_to_expiry", 1),
            "expiry_date": "",
            "timestamp": summary.get("timestamp", ""),
            "market_open": False,
            "iv_analysis": None,
            "delta_analysis": None,
        }

    strikes = data["strikes"]
    spot = data["spot"]
    futures = data["futures"]
    atm = data["atm_strike"]

    # Key OI concentrations
    ce_oi_sorted = sorted(strikes, key=lambda x: x["ce_oi"], reverse=True)[:5]
    pe_oi_sorted = sorted(strikes, key=lambda x: x["pe_oi"], reverse=True)[:5]

    highest_ce_oi_strike = ce_oi_sorted[0]
    highest_pe_oi_strike = pe_oi_sorted[0]

    # Change in OI analysis
    ce_oi_addition = [s for s in strikes if s["ce_oi_change"] > s["ce_oi"] * 0.1]
    pe_oi_addition = [s for s in strikes if s["pe_oi_change"] > s["pe_oi"] * 0.1]

    ce_writing_strikes = sorted(ce_oi_addition, key=lambda x: x["ce_oi_change"], reverse=True)[:3]
    pe_writing_strikes = sorted(pe_oi_addition, key=lambda x: x["pe_oi_change"], reverse=True)[:3]

    resistance_wall = highest_ce_oi_strike["strike"]
    support_wall = highest_pe_oi_strike["strike"]

    short_resistance = ce_writing_strikes[0]["strike"] if ce_writing_strikes else resistance_wall
    short_support = pe_writing_strikes[0]["strike"] if pe_writing_strikes else support_wall

    # ATM data
    atm_strike_data = next((s for s in strikes if s["is_atm"]), None)
    atm_ce_oi = atm_strike_data["ce_oi"] if atm_strike_data else 0
    atm_pe_oi = atm_strike_data["pe_oi"] if atm_strike_data else 0
    atm_ce_iv = atm_strike_data["ce_iv"] if atm_strike_data else 0
    atm_pe_iv = atm_strike_data["pe_iv"] if atm_strike_data else 0

    # IV analysis
    avg_iv = round((atm_ce_iv + atm_pe_iv) / 2, 2) if atm_strike_data else 0
    
    # Save IV for history tracking
    if avg_iv > 0:
        save_iv_history(atm_ce_iv, atm_pe_iv, avg_iv, data.get("vix", 15), data.get("days_to_expiry", 1))
    
    iv_history = get_iv_history(252)
    iv_analysis = _analyze_iv(atm_ce_iv, atm_pe_iv, avg_iv, iv_history)

    # Delta estimation (simplified approximation)
    delta_analysis = _estimate_deltas(strikes, spot, atm)

    # PCR interpretation
    pcr = data["pcr_oi"]
    if pcr > 1.3:
        pcr_signal = "strong_bullish"
        pcr_desc = f"PCR {pcr} indicates heavy put writing; strong support expected."
    elif pcr > 1.1:
        pcr_signal = "bullish"
        pcr_desc = f"PCR {pcr} shows put bias; mild bullish sentiment."
    elif pcr < 0.7:
        pcr_signal = "strong_bearish"
        pcr_desc = f"PCR {pcr} indicates heavy call writing; strong resistance expected."
    elif pcr < 0.9:
        pcr_signal = "bearish"
        pcr_desc = f"PCR {pcr} shows call bias; mild bearish sentiment."
    else:
        pcr_signal = "neutral"
        pcr_desc = f"PCR {pcr} is neutral; no clear directional bias from options."

    # Max Pain vs Spot
    max_pain = data["max_pain"]
    pain_diff = spot - max_pain
    if abs(pain_diff) < 30:
        pain_signal = "neutral"
        pain_desc = f"Spot near max pain ({max_pain}); expiry pin risk exists."
    elif pain_diff > 50:
        pain_signal = "bullish"
        pain_desc = f"Spot {pain_diff:.0f} pts above max pain ({max_pain}); upside bias."
    else:
        pain_signal = "bearish"
        pain_desc = f"Spot {abs(pain_diff):.0f} pts below max pain ({max_pain}); downside bias."

    # Futures basis
    basis = futures - spot
    if basis > 25:
        basis_signal = "bullish"
        basis_desc = f"Futures premium {basis:.1f} pts indicates strong long buildup."
    elif basis < -15:
        basis_signal = "bearish"
        basis_desc = f"Futures discount {abs(basis):.1f} pts indicates short buildup."
    else:
        basis_signal = "neutral"
        basis_desc = f"Futures-spot spread {basis:.1f} pts is normal."

    # Volume analysis
    total_ce_vol = sum(s["ce_volume"] for s in strikes)
    total_pe_vol = sum(s["pe_volume"] for s in strikes)
    vol_pcr = round(total_pe_vol / max(total_ce_vol, 1), 3)

    # IV environment
    vix = data["vix"]
    if vix < 13:
        iv_env = "low"
        iv_desc = f"VIX at {vix} is low; limited expected range, option sellers have edge."
    elif vix > 20:
        iv_env = "high"
        iv_desc = f"VIX at {vix} is elevated; expect larger moves, option buyers may get opportunity."
    else:
        iv_env = "moderate"
        iv_desc = f"VIX at {vix} is moderate; balanced environment."

    # Breakeven for ATM options
    breakeven_analysis = _calculate_breakeven(strikes, atm, spot)

    return {
        "spot": spot,
        "futures": futures,
        "atm_strike": atm,
        "strikes": strikes,
        "resistance_wall": resistance_wall,
        "support_wall": support_wall,
        "short_resistance": short_resistance,
        "short_support": short_support,
        "highest_ce_oi_strike": highest_ce_oi_strike,
        "highest_pe_oi_strike": highest_pe_oi_strike,
        "ce_writing_strikes": ce_writing_strikes,
        "pe_writing_strikes": pe_writing_strikes,
        "pcr": pcr,
        "pcr_signal": pcr_signal,
        "pcr_desc": pcr_desc,
        "vol_pcr": vol_pcr,
        "max_pain": max_pain,
        "pain_signal": pain_signal,
        "pain_desc": pain_desc,
        "basis": basis,
        "basis_signal": basis_signal,
        "basis_desc": basis_desc,
        "vix": vix,
        "iv_env": iv_env,
        "iv_desc": iv_desc,
        "days_to_expiry": data["days_to_expiry"],
        "expiry_date": data["expiry_date"],
        "timestamp": data["timestamp"],
        "market_open": True,
        "iv_analysis": iv_analysis,
        "delta_analysis": delta_analysis,
        "breakeven_analysis": breakeven_analysis,
    }


def _analyze_iv(atm_ce_iv, atm_pe_iv, avg_iv, iv_history):
    """Analyze IV rank and percentile from historical data."""
    if not iv_history or len(iv_history) < 30:
        return {
            "atm_ce_iv": atm_ce_iv,
            "atm_pe_iv": atm_pe_iv,
            "avg_iv": avg_iv,
            "iv_rank": None,
            "iv_percentile": None,
            "assessment": "Insufficient IV history for rank calculation.",
        }
    
    historical_avgs = [row["avg_iv"] for row in iv_history if row["avg_iv"]]
    if not historical_avgs:
        return {"assessment": "No historical IV data available."}
    
    min_iv = min(historical_avgs)
    max_iv = max(historical_avgs)
    
    iv_rank = round((avg_iv - min_iv) / (max_iv - min_iv) * 100, 1) if max_iv > min_iv else 50
    iv_percentile = round(sum(1 for v in historical_avgs if v < avg_iv) / len(historical_avgs) * 100, 1)
    
    if iv_percentile > 70:
        assessment = f"IV at {avg_iv} is high (percentile {iv_percentile}%). Favorable for option selling."
    elif iv_percentile < 30:
        assessment = f"IV at {avg_iv} is low (percentile {iv_percentile}%). Favorable for option buying."
    else:
        assessment = f"IV at {avg_iv} is moderate (percentile {iv_percentile}%)."
    
    return {
        "atm_ce_iv": atm_ce_iv,
        "atm_pe_iv": atm_pe_iv,
        "avg_iv": avg_iv,
        "iv_rank": iv_rank,
        "iv_percentile": iv_percentile,
        "assessment": assessment,
    }


def _estimate_deltas(strikes, spot, atm):
    """Estimate delta for key strikes based on moneyness."""
    results = []
    for s in strikes:
        if s["is_atm"] or s["is_nearby"]:
            moneyness = (s["strike"] - spot) / 50
            # Simplified delta estimation
            if abs(moneyness) <= 0.5:
                ce_delta = round(0.5 - moneyness * 0.1, 2)
                pe_delta = round(-0.5 - moneyness * 0.1, 2)
            elif moneyness > 0:
                ce_delta = round(max(0.05, 0.5 - moneyness * 0.15), 2)
                pe_delta = round(min(-0.05, -0.15 - moneyness * 0.05), 2)
            else:
                ce_delta = round(min(0.95, 0.5 - moneyness * 0.15), 2)
                pe_delta = round(max(-0.95, -0.5 - moneyness * 0.15), 2)
            
            results.append({
                "strike": s["strike"],
                "ce_delta": ce_delta,
                "pe_delta": pe_delta,
                "ce_premium": s["ce_premium"],
                "pe_premium": s["pe_premium"],
            })
    return results


def _calculate_breakeven(strikes, atm, spot):
    """Calculate breakeven points for ATM options."""
    atm_data = next((s for s in strikes if s["strike"] == atm), None)
    if not atm_data:
        return None
    
    ce_premium = atm_data["ce_premium"]
    pe_premium = atm_data["pe_premium"]
    
    ce_breakeven = atm + ce_premium
    pe_breakeven = atm - pe_premium
    
    return {
        "atm_strike": atm,
        "ce_premium": ce_premium,
        "pe_premium": pe_premium,
        "ce_breakeven": round(ce_breakeven, 2),
        "pe_breakeven": round(pe_breakeven, 2),
        "ce_target_for_2x": round(ce_breakeven + ce_premium, 2),
        "pe_target_for_2x": round(pe_breakeven - pe_premium, 2),
    }


def get_trend_analysis(analysis):
    """Summarize overall trend from multiple inputs."""
    signals = [
        analysis["pcr_signal"],
        analysis["pain_signal"],
        analysis["basis_signal"]
    ]

    bullish_count = sum(1 for s in signals if "bullish" in s)
    bearish_count = sum(1 for s in signals if "bearish" in s)
    neutral_count = sum(1 for s in signals if s == "neutral")

    if bullish_count >= 2 and analysis["basis"] > 10 and analysis["pcr"] > 1.0:
        trend = "bullish"
        strength = min(10, 6 + bullish_count)
    elif bearish_count >= 2 and analysis["basis"] < -5 and analysis["pcr"] < 1.0:
        trend = "bearish"
        strength = min(10, 6 + bearish_count)
    elif neutral_count >= 2 and abs(analysis["basis"]) < 15 and 0.9 <= analysis["pcr"] <= 1.1:
        trend = "sideways"
        strength = 5
    else:
        trend = "neutral"
        strength = 4

    reasons = []
    if analysis["basis"] > 15:
        reasons.append("futures at strong premium")
    elif analysis["basis"] < -10:
        reasons.append("futures at discount")
    else:
        reasons.append("futures-spot spread normal")

    if analysis["pcr"] > 1.2:
        reasons.append("PCR elevated suggesting put accumulation")
    elif analysis["pcr"] < 0.8:
        reasons.append("PCR low suggesting call writing")
    else:
        reasons.append("PCR neutral")

    if analysis["spot"] > analysis["max_pain"] + 40:
        reasons.append("spot above max pain")
    elif analysis["spot"] < analysis["max_pain"] - 40:
        reasons.append("spot below max pain")
    else:
        reasons.append("spot near max pain")

    reason_text = f"Trend is {trend.upper()} with strength {strength}/10. Option chain shows " + ", ".join(reasons) + "."

    return {
        "trend": trend,
        "strength": strength,
        "reason": reason_text
    }
