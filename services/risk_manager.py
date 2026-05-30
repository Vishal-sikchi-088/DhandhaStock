"""
Risk Management Service
Validates trades against user-defined capital and risk limits.
"""

from .database import get_settings


def validate_trade(trade, settings=None):
    """
    Check if a proposed trade respects risk limits.
    Returns dict with approved=True/False and messages.
    """
    if settings is None:
        settings = get_settings()

    capital = float(settings.get("capital", 100000))
    max_risk_pct = float(settings.get("max_risk_percent", 2.0))
    max_risk = capital * max_risk_pct / 100

    messages = []
    approved = True

    if trade is None or trade.get("instrument_type") == "NO_TRADE":
        return {"approved": False, "messages": ["No active trade to validate."]}

    total_risk = trade.get("total_risk", 0)
    if total_risk > max_risk * 1.1:
        messages.append(f"Trade risk Rs {total_risk:.0f} exceeds max allowed Rs {max_risk:.0f}.")
        approved = False
    else:
        messages.append(f"Trade risk Rs {total_risk:.0f} is within limit Rs {max_risk:.0f}.")

    rr = trade.get("risk_reward", "N/A")
    if "N/A" in str(rr):
        messages.append("No risk-reward data available.")
    else:
        # Parse primary RR
        try:
            parts = str(rr).split(":")
            if len(parts) >= 2:
                rr_val = float(parts[1].split("/")[0].strip())
                if rr_val < 1.0:
                    messages.append("Risk-reward is below 1:1. Not recommended.")
                    approved = False
                elif rr_val < 1.5:
                    messages.append("Risk-reward is marginal (below 1:1.5).")
                else:
                    messages.append(f"Risk-reward {rr} is acceptable.")
        except Exception:
            messages.append("Could not parse risk-reward.")

    return {"approved": approved, "messages": messages}


def calculate_position_size(entry, stop, capital, max_risk_pct, lot_size=50):
    """
    Calculate quantity for a given risk limit.
    """
    risk_per_point = abs(entry - stop)
    if risk_per_point == 0:
        return 0
    max_risk = capital * max_risk_pct / 100
    qty = int(max_risk / (risk_per_point * lot_size))
    return max(0, qty)
