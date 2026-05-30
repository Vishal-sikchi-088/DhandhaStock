"""
Options Strategy Selector
Recommends the best options strategy based on market conditions.

Strategies:
Directional:
- Long Call (Bullish, low-medium IV)
- Long Put (Bearish, low-medium IV)
- Bull Call Spread (Bullish, high IV)
- Bear Put Spread (Bearish, high IV)

Non-Directional:
- Short Straddle (Very high IV, expecting contraction)
- Short Strangle (High IV, wider range)
- Iron Condor (High IV, rangebound market)
"""


STRATEGIES = {
    "long_call": {
        "name": "Long Call",
        "type": "directional",
        "direction": "bullish",
        "description": "Buy ATM/ITM Call option. Unlimited upside, limited risk to premium paid.",
        "when_to_use": "Bullish bias, low to moderate IV, clear trend.",
        "max_profit": "Unlimited",
        "max_loss": "Premium paid",
        "breakeven": "Strike + Premium",
        "ideal_vix_range": (12, 18),
        "ideal_dte": (5, 21),
    },
    "long_put": {
        "name": "Long Put",
        "type": "directional",
        "direction": "bearish",
        "description": "Buy ATM/ITM Put option. Unlimited downside profit, limited risk to premium paid.",
        "when_to_use": "Bearish bias, low to moderate IV, clear trend.",
        "max_profit": "Substantial (strike - premium)",
        "max_loss": "Premium paid",
        "breakeven": "Strike - Premium",
        "ideal_vix_range": (12, 18),
        "ideal_dte": (5, 21),
    },
    "bull_call_spread": {
        "name": "Bull Call Spread",
        "type": "directional_spread",
        "direction": "bullish",
        "description": "Buy ATM/ITM Call, sell OTM Call. Reduces cost but caps upside.",
        "when_to_use": "Bullish but IV is elevated. Cheaper than naked call.",
        "max_profit": "Spread width - Net premium",
        "max_loss": "Net premium paid",
        "breakeven": "Long strike + Net premium",
        "ideal_vix_range": (16, 24),
        "ideal_dte": (7, 21),
    },
    "bear_put_spread": {
        "name": "Bear Put Spread",
        "type": "directional_spread",
        "direction": "bearish",
        "description": "Buy ATM/ITM Put, sell OTM Put. Reduces cost but caps upside.",
        "when_to_use": "Bearish but IV is elevated. Cheaper than naked put.",
        "max_profit": "Spread width - Net premium",
        "max_loss": "Net premium paid",
        "breakeven": "Long strike - Net premium",
        "ideal_vix_range": (16, 24),
        "ideal_dte": (7, 21),
    },
    "short_straddle": {
        "name": "Short Straddle",
        "type": "non_directional",
        "direction": "neutral",
        "description": "Sell ATM Call and ATM Put. Profit if market stays in a tight range.",
        "when_to_use": "Very high IV expecting contraction. Rangebound with strong support/resistance.",
        "max_profit": "Total premium received",
        "max_loss": "Unlimited",
        "breakeven": "ATM ± Total premium",
        "ideal_vix_range": (20, 35),
        "ideal_dte": (3, 10),
    },
    "short_strangle": {
        "name": "Short Strangle",
        "type": "non_directional",
        "direction": "neutral",
        "description": "Sell OTM Call and OTM Put. Wider profit range than straddle.",
        "when_to_use": "High IV, expecting rangebound but with some room for movement.",
        "max_profit": "Total premium received",
        "max_loss": "Unlimited",
        "breakeven": "OTM strikes ± premium",
        "ideal_vix_range": (20, 35),
        "ideal_dte": (5, 14),
    },
    "iron_condor": {
        "name": "Iron Condor",
        "type": "non_directional",
        "direction": "neutral",
        "description": "Sell OTM Call Spread + Sell OTM Put Spread. Defined risk non-directional trade.",
        "when_to_use": "High IV, rangebound, want defined risk.",
        "max_profit": "Net premium received",
        "max_loss": "Spread width - Net premium",
        "breakeven": "Between short strikes",
        "ideal_vix_range": (18, 30),
        "ideal_dte": (7, 21),
    },
}


def score_strategy_fit(strategy_key, vix, iv_percentile, days_to_expiry, 
                       trend_strength, probability, direction, is_rangebound=False):
    """
    Score how well a strategy fits current conditions.
    Returns score 0-100.
    """
    s = STRATEGIES[strategy_key]
    score = 50
    
    # VIX fit
    vix_min, vix_max = s["ideal_vix_range"]
    if vix_min <= vix <= vix_max:
        score += 15
    elif vix < vix_min:
        score -= 10
    elif vix > vix_max:
        score -= 5
    
    # DTE fit
    dte_min, dte_max = s["ideal_dte"]
    if dte_min <= days_to_expiry <= dte_max:
        score += 10
    elif days_to_expiry < dte_min:
        score -= 10
    elif days_to_expiry > dte_max * 2:
        score -= 5
    
    # Directional alignment
    if s["type"] == "directional":
        if s["direction"] == direction:
            score += 15
        else:
            score -= 30  # Wrong direction is terrible
        
        # Trend strength bonus
        if trend_strength in ["strong", "moderate"]:
            score += 10
    
    elif s["type"] == "directional_spread":
        if s["direction"] == direction:
            score += 10
        else:
            score -= 20
        
        # Spreads better when IV is high
        if iv_percentile and iv_percentile > 60:
            score += 10
    
    elif s["type"] == "non_directional":
        if is_rangebound or trend_strength == "weak":
            score += 15
        else:
            score -= 15  # Non-directional in trending market is bad
        
        # Needs high IV
        if iv_percentile and iv_percentile > 60:
            score += 10
        elif iv_percentile and iv_percentile < 40:
            score -= 15
    
    # Probability filter
    if probability >= 75:
        score += 5
    elif probability < 60:
        score -= 10
    
    return max(0, min(100, score))


def select_strategy(vix, iv_percentile, days_to_expiry, trend_strength, 
                    probability, direction, is_rangebound=False):
    """
    Main strategy selection function.
    
    Returns the best strategy and runner-ups.
    """
    scores = {}
    for key in STRATEGIES:
        scores[key] = score_strategy_fit(
            key, vix, iv_percentile, days_to_expiry,
            trend_strength, probability, direction, is_rangebound
        )
    
    # Filter out low scores
    valid = {k: v for k, v in scores.items() if v >= 40}
    
    if not valid:
        return {
            "recommendation": "NO STRATEGY",
            "reason": "No strategy fits current conditions well.",
            "all_scores": scores,
        }
    
    best_key = max(valid, key=valid.get)
    best = STRATEGIES[best_key]
    
    # Determine if it's a directional or non-directional recommendation
    if best["type"] == "non_directional":
        trade_direction = "NEUTRAL"
    else:
        trade_direction = best["direction"].upper()
    
    return {
        "strategy_key": best_key,
        "strategy_name": best["name"],
        "type": best["type"],
        "direction": trade_direction,
        "description": best["description"],
        "when_to_use": best["when_to_use"],
        "max_profit": best["max_profit"],
        "max_loss": best["max_loss"],
        "breakeven": best["breakeven"],
        "score": valid[best_key],
        "all_scores": scores,
    }


def recommend_strategy_for_conditions(analysis_data, chart_data, probability_result):
    """
    Convenience function that extracts needed values and calls select_strategy.
    """
    vix = analysis_data.get("vix", 15)
    iv_analysis = analysis_data.get("iv_analysis", {})
    iv_percentile = iv_analysis.get("iv_percentile", 50)
    days_to_expiry = analysis_data.get("days_to_expiry", 7)
    
    trend_strength = "weak"
    if chart_data:
        bias = chart_data.get("bias", "neutral")
        if "strong" in bias:
            trend_strength = "strong"
        elif bias in ["bullish", "bearish"]:
            trend_strength = "moderate"
    
    direction = probability_result.get("direction", "neutral")
    probability = probability_result.get("probability", 0)
    
    # Determine if market is rangebound
    is_rangebound = chart_data.get("multi_timeframe_alignment") == "sideways_aligned" if chart_data else False
    
    return select_strategy(vix, iv_percentile, days_to_expiry, trend_strength,
                          probability, direction, is_rangebound)
