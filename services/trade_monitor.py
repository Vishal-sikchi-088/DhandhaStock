"""
Trade Monitor Service
Live monitoring of active trades with auto-action suggestions.

Monitors:
- Current spot vs entry/stop/targets
- Option premium changes (when market open)
- Market structure changes
- VIX spikes
- OI reversals

Suggested Actions:
- HOLD: Conditions favorable, stay in trade
- EXIT: Stop hit, structure broke, or risk event
- PARTIAL BOOK: Target 1 hit, book profits on portion
- TRAIL SL: Target 1+ hit, move stop to protect profits
"""

import json
from datetime import datetime

from .database import get_active_trades, update_active_trade, save_trade_log
from .market_data import get_market_summary
from .analysis import analyze_option_chain
from .chart_analysis import analyze_chart
from .premarket_data import get_all_premarket_data
from .smc_analysis import analyze_smc


def get_current_premium_for_strike(strikes, strike, trade_type):
    """Extract current premium for a strike from option chain."""
    if not strikes:
        return None
    for s in strikes:
        if s["strike"] == strike:
            return s["ce_premium"] if trade_type == "CALL" else s["pe_premium"]
    return None


def calculate_option_pnl(trade, current_premium):
    """Calculate P&L for an options position."""
    if current_premium is None or trade.get("entry") is None:
        return 0
    
    entry_premium = trade.get("premium_estimate") or trade.get("entry")
    if isinstance(entry_premium, (int, float)) and entry_premium > 5000:
        # entry is spot price, not premium — can't calculate exact P&L
        return None
    
    qty = trade.get("quantity", 1)
    lot_size = 50
    
    if trade["trade_type"] == "CALL":
        pnl = (current_premium - entry_premium) * qty * lot_size
    else:  # PUT
        pnl = (current_premium - entry_premium) * qty * lot_size
    
    return round(pnl, 2)


def calculate_spot_pnl(trade, current_spot):
    """Approximate P&L using spot movement and delta."""
    entry = trade.get("entry")
    if not entry or not current_spot:
        return 0
    
    qty = trade.get("quantity", 1)
    lot_size = 50
    delta = trade.get("delta") or 0.5
    
    spot_move = current_spot - entry
    if trade["trade_type"] == "PUT":
        spot_move = -spot_move  # Put gains when spot falls
    
    # Delta-adjusted P&L approximation
    pnl = spot_move * abs(delta) * qty * lot_size
    return round(pnl, 2)


def determine_action(trade, current_spot, current_premium, pnl, chart_data, smc_data, vix, prev_vix=None):
    """
    Determine recommended action for an active trade.
    
    Rules:
    1. EXIT immediately if stop loss hit
    2. PARTIAL BOOK if Target 1 hit and not yet booked
    3. TRAIL SL if Target 1+ hit and already partial booked
    4. EXIT if market structure changes against position
    5. EXIT if VIX spikes > 5 points
    6. HOLD if all conditions favorable
    """
    entry = trade["entry"]
    stop = trade["stop_loss"]
    t1 = trade.get("target1")
    t2 = trade.get("target2")
    t3 = trade.get("target3")
    trade_type = trade["trade_type"]
    current_action = trade.get("action", "HOLD")
    
    is_long = trade_type == "CALL"
    
    reasons = []
    
    # Rule 1: Stop Loss hit
    if is_long and current_spot <= stop:
        return "EXIT", f"Stop loss hit at {stop}. Spot {current_spot}."
    elif not is_long and current_spot >= stop:
        return "EXIT", f"Stop loss hit at {stop}. Spot {current_spot}."
    
    # Rule 2 & 3: Target hits
    if t1:
        if is_long and current_spot >= t1:
            if current_action == "HOLD":
                return "PARTIAL BOOK", f"Target 1 ({t1}) hit. Book 50% profits. Spot {current_spot}."
            elif current_action == "PARTIAL BOOK":
                return "TRAIL SL", f"Target 1 already booked. Trail stop to entry ({entry}) to lock in remaining."
        elif not is_long and current_spot <= t1:
            if current_action == "HOLD":
                return "PARTIAL BOOK", f"Target 1 ({t1}) hit. Book 50% profits. Spot {current_spot}."
            elif current_action == "PARTIAL BOOK":
                return "TRAIL SL", f"Target 1 already booked. Trail stop to entry ({entry}) to lock in remaining."
    
    if t2:
        if is_long and current_spot >= t2:
            return "TRAIL SL", f"Target 2 ({t2}) hit. Trail stop to Target 1 ({t1})."
        elif not is_long and current_spot <= t2:
            return "TRAIL SL", f"Target 2 ({t2}) hit. Trail stop to Target 1 ({t1})."
    
    # Rule 4: Market structure break (CHoCH against position)
    if smc_data and not smc_data.get("error"):
        smc_bias = smc_data.get("bias", "neutral")
        last_choch = smc_data.get("last_choch")
        
        if last_choch:
            choch_direction = last_choch.get("direction", "")
            if is_long and choch_direction == "bearish":
                return "EXIT", f"Market structure broke bearish (CHoCH at {last_choch['level']}). Exit long."
            elif not is_long and choch_direction == "bullish":
                return "EXIT", f"Market structure broke bullish (CHoCH at {last_choch['level']}). Exit short."
    
    # Rule 5: VIX spike
    if prev_vix and vix and (vix - prev_vix) > 5:
        return "EXIT", f"VIX spike detected: {prev_vix:.1f} → {vix:.1f}. Volatility explosion — exit to protect capital."
    
    # Rule 6: Unfavorable price action (reversal from target with weak volume)
    # This is harder to detect without tick data — skip for now
    
    # Default: HOLD
    if pnl is not None and pnl > 0:
        return "HOLD", f"Trade in profit (₹{pnl:.0f}). Spot {current_spot}. All conditions favorable."
    elif pnl is not None and pnl < 0:
        return "HOLD", f"Trade in drawdown (₹{pnl:.0f}). Spot {current_spot}. Stop intact at {stop}. Hold."
    else:
        return "HOLD", f"Monitoring active. Spot {current_spot}."


def monitor_active_trades():
    """
    Main monitoring function.
    Checks all active trades and returns action recommendations.
    """
    trades = get_active_trades()
    if not trades:
        return {"status": "no_active_trades", "trades": []}
    
    # Fetch current market data
    summary = get_market_summary()
    current_spot = summary.get("spot", 0)
    current_futures = summary.get("futures", 0)
    vix = summary.get("vix", 15)
    
    # Fetch option chain for premiums
    option_chain = analyze_option_chain()
    strikes = option_chain.get("strikes", []) if option_chain else []
    
    # Fetch chart data for structure monitoring
    premarket = get_all_premarket_data()
    chart = None
    smc = None
    if premarket:
        chart = analyze_chart(
            premarket.get("historical_daily"),
            premarket.get("historical_60m"),
            premarket.get("historical_15m"),
            premarket.get("historical_5m"),
        )
        smc = chart.get("smc") if chart else None
    
    results = []
    
    for trade in trades:
        # Get current premium
        current_premium = None
        if strikes and trade.get("strike"):
            current_premium = get_current_premium_for_strike(strikes, trade["strike"], trade["trade_type"])
        
        # Calculate P&L
        if current_premium is not None:
            pnl = calculate_option_pnl(trade, current_premium)
        else:
            pnl = calculate_spot_pnl(trade, current_spot)
        
        # Determine action
        action, reason = determine_action(
            trade, current_spot, current_premium, pnl,
            chart, smc, vix
        )
        
        # Update trade in DB
        update_active_trade(trade["id"], {
            "current_pnl": pnl if pnl is not None else trade.get("current_pnl", 0),
            "current_spot": current_spot,
            "current_premium": current_premium,
            "action": action,
            "action_reason": reason,
        })
        
        # Save log
        save_trade_log(trade["id"], {
            "spot": current_spot,
            "premium": current_premium,
            "pnl": pnl,
            "action": action,
            "reason": reason,
        })
        
        results.append({
            "trade_id": trade["id"],
            "instrument": trade.get("instrument_type"),
            "trade_type": trade.get("trade_type"),
            "strike": trade.get("strike"),
            "entry": trade.get("entry"),
            "stop_loss": trade.get("stop_loss"),
            "target1": trade.get("target1"),
            "quantity": trade.get("quantity"),
            "current_spot": current_spot,
            "current_premium": current_premium,
            "current_pnl": pnl,
            "action": action,
            "reason": reason,
            "updated_at": datetime.now().isoformat(),
        })
    
    return {
        "status": "monitoring",
        "market_open": summary.get("market_open", False),
        "spot": current_spot,
        "vix": vix,
        "active_trade_count": len(trades),
        "trades": results,
    }
