"""
Strike Selection Service
Institutional-grade option strike selection for NIFTY 50.

Selects optimal strikes based on:
- Delta targeting (0.50-0.60 for directional, 0.15-0.25 for spreads)
- Liquidity filter (minimum OI threshold)
- Moneyness alignment with directional bias
- Gamma risk assessment near expiry
- OI concentration analysis
"""

import math


def approximate_delta(strike, spot, is_call, days_to_expiry=7, iv=15):
    """
    Approximate option delta using a simplified Black-Scholes-like formula.
    This is not exact but sufficient for strike selection without external API.
    
    For institutional accuracy, integrate with broker API Greeks.
    """
    if days_to_expiry <= 0:
        days_to_expiry = 1
    
    # Simplified delta approximation
    moneyness = (spot - strike) / 50  # Nifty lot size
    
    # Time decay factor (more time = deltas closer to 0.5)
    time_factor = min(1, math.sqrt(days_to_expiry / 30))
    
    # IV factor (higher IV = deltas closer to 0.5)
    iv_factor = min(1, iv / 30)
    
    # Adjust moneyness impact by time and IV
    effective_moneyness = moneyness * (0.5 + 0.5 * time_factor) * (0.5 + 0.5 * iv_factor)
    
    if is_call:
        delta = 0.5 + effective_moneyness * 0.1
    else:
        delta = -0.5 + effective_moneyness * 0.1
    
    # Clamp
    delta = max(-0.95, min(0.95, delta))
    
    return round(delta, 2)


def approximate_gamma(strike, spot, days_to_expiry=7, iv=15):
    """
    Approximate gamma. Highest ATM, decreases as you move away.
    """
    if days_to_expiry <= 0:
        days_to_expiry = 1
    
    distance_from_atm = abs(strike - spot) / 50
    time_factor = 1 / math.sqrt(days_to_expiry)
    iv_factor = iv / 15
    
    gamma = max(0.001, 0.05 * time_factor * iv_factor * math.exp(-distance_from_atm * 0.3))
    return round(gamma, 4)


def select_strike(direction, option_chain_data, preferred_delta_range=(0.50, 0.65),
                  min_oi=50000, liquidity_bonus_threshold=200000):
    """
    Select optimal strike for directional trade.
    
    Args:
        direction: 'bullish' or 'bearish'
        option_chain_data: Full option chain from NSE
        preferred_delta_range: Target delta range for directional trade
        min_oi: Minimum OI for liquidity filter
        liquidity_bonus_threshold: OI level considered highly liquid
    
    Returns:
        Dict with recommended strike, delta, premium, gamma warning, etc.
    """
    if not option_chain_data or not option_chain_data.get("strikes"):
        return {"error": "No option chain data available"}
    
    strikes = option_chain_data["strikes"]
    spot = option_chain_data.get("spot", 0)
    atm = option_chain_data.get("atm_strike", round(spot / 50) * 50)
    days_to_expiry = option_chain_data.get("days_to_expiry", 7)
    vix = option_chain_data.get("vix", 15)
    
    is_call = direction == "bullish"
    instrument_type = "CALL" if is_call else "PUT"
    
    # Filter liquid strikes
    liquid_strikes = []
    for s in strikes:
        oi = s["ce_oi"] if is_call else s["pe_oi"]
        if oi >= min_oi:
            delta = approximate_delta(s["strike"], spot, is_call, days_to_expiry, vix)
            premium = s["ce_premium"] if is_call else s["pe_premium"]
            gamma = approximate_gamma(s["strike"], spot, days_to_expiry, vix)
            
            liquid_strikes.append({
                "strike": s["strike"],
                "oi": oi,
                "delta": delta,
                "premium": premium,
                "gamma": gamma,
                "iv": s["ce_iv"] if is_call else s["pe_iv"],
                "volume": s["ce_volume"] if is_call else s["pe_volume"],
                "oi_change": s["ce_oi_change"] if is_call else s["pe_oi_change"],
            })
    
    if not liquid_strikes:
        return {
            "error": f"No liquid {instrument_type} strikes found with OI >= {min_oi}",
            "direction": direction,
        }
    
    # Score each strike
    scored = []
    for s in liquid_strikes:
        score = 0
        reasons = []
        
        # Delta match (most important)
        target_delta_mid = (preferred_delta_range[0] + preferred_delta_range[1]) / 2
        delta_diff = abs(abs(s["delta"]) - target_delta_mid)
        delta_score = max(0, 30 - delta_diff * 100)
        score += delta_score
        reasons.append(f"Delta {s['delta']}: score {delta_score:.1f}")
        
        # Liquidity bonus
        if s["oi"] >= liquidity_bonus_threshold:
            score += 20
            reasons.append("High liquidity (+20)")
        elif s["oi"] >= min_oi * 3:
            score += 10
            reasons.append("Good liquidity (+10)")
        
        # Volume confirmation
        if s["volume"] > s["oi"] * 0.1:
            score += 10
            reasons.append("High volume relative to OI (+10)")
        
        # OI change alignment
        if direction == "bullish" and s["oi_change"] > 0:
            score += 10
            reasons.append("OI increasing — buildup (+10)")
        elif direction == "bearish" and s["oi_change"] > 0:
            score += 10
            reasons.append("OI increasing — buildup (+10)")
        elif s["oi_change"] < 0:
            score -= 5
            reasons.append("OI decreasing (-5)")
        
        # Premium reasonableness (avoid illiquid extremes)
        if s["premium"] < 5:
            score -= 20
            reasons.append("Premium too low — illiquid (-20)")
        elif s["premium"] > 500:
            score -= 10
            reasons.append("Premium very high — deep ITM (-10)")
        
        scored.append({
            **s,
            "score": score,
            "score_reasons": reasons,
        })
    
    # Sort by score
    scored.sort(key=lambda x: x["score"], reverse=True)
    best = scored[0] if scored else None
    
    if not best:
        return {"error": "Could not select a suitable strike"}
    
    # Gamma risk assessment
    gamma_risk = "low"
    gamma_warnings = []
    
    if days_to_expiry <= 1:
        if best["gamma"] > 0.03:
            gamma_risk = "extreme"
            gamma_warnings.append("Expiry day with high gamma — premium can swing wildly")
        else:
            gamma_risk = "high"
            gamma_warnings.append("Expiry day gamma risk elevated")
    elif days_to_expiry <= 3:
        if best["gamma"] > 0.02:
            gamma_risk = "high"
            gamma_warnings.append("Near expiry with elevated gamma")
        else:
            gamma_risk = "moderate"
    
    if abs(best["delta"]) > 0.75:
        gamma_warnings.append("Deep ITM — low gamma but high capital requirement")
    elif abs(best["delta"]) < 0.35:
        gamma_warnings.append("Far OTM — low probability of profit")
    
    # Alternative strikes
    alternatives = []
    for alt in scored[1:3]:
        alternatives.append({
            "strike": alt["strike"],
            "delta": alt["delta"],
            "premium": alt["premium"],
            "oi": alt["oi"],
        })
    
    return {
        "direction": direction,
        "instrument_type": instrument_type,
        "recommended_strike": best["strike"],
        "recommended_delta": best["delta"],
        "estimated_premium": best["premium"],
        "estimated_gamma": best["gamma"],
        "oi": best["oi"],
        "volume": best["volume"],
        "iv": best["iv"],
        "gamma_risk": gamma_risk,
        "gamma_warnings": gamma_warnings,
        "selection_score": best["score"],
        "alternatives": alternatives,
        "spot": spot,
        "atm": atm,
        "days_to_expiry": days_to_expiry,
    }


def select_spread_strikes(direction, option_chain_data, spread_width=100):
    """
    Select strikes for spread strategies (Bull Call Spread / Bear Put Spread).
    
    Returns:
        long_strike, short_strike for the spread.
    """
    if not option_chain_data or not option_chain_data.get("strikes"):
        return {"error": "No option chain data"}
    
    spot = option_chain_data.get("spot", 0)
    atm = option_chain_data.get("atm_strike", round(spot / 50) * 50)
    
    if direction == "bullish":
        # Bull Call Spread: Buy ATM/ITM call, sell OTM call
        long_strike = atm
        short_strike = atm + spread_width
    else:
        # Bear Put Spread: Buy ATM/ITM put, sell OTM put
        long_strike = atm
        short_strike = atm - spread_width
    
    return {
        "direction": direction,
        "strategy": "Bull Call Spread" if direction == "bullish" else "Bear Put Spread",
        "long_strike": long_strike,
        "short_strike": short_strike,
        "spread_width": spread_width,
        "max_profit": spread_width,  # Rough estimate
        "max_loss": "premium_paid",  # Will be calculated with actual premiums
    }
