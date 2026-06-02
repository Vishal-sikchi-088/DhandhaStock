"""
Black-Scholes Option Pricing
Builds synthetic option chain when NSE API is unavailable.
No external dependencies — uses only stdlib math.
"""

import math
from datetime import date, timedelta


# ── Normal CDF via Horner's method ─────────────────────────────────────────

def _norm_cdf(x):
    a1, a2, a3, a4, a5 = 0.31938153, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    L = abs(x)
    K = 1.0 / (1.0 + 0.2316419 * L)
    w = 1.0 - (1.0 / math.sqrt(2 * math.pi)) * math.exp(-L * L / 2.0) * (
        a1*K + a2*K**2 + a3*K**3 + a4*K**4 + a5*K**5
    )
    return w if x >= 0 else 1.0 - w


# ── Core Greeks ────────────────────────────────────────────────────────────

def bs_price(S, K, T, r, sigma, option_type='call'):
    """Black-Scholes option price."""
    if T <= 0:
        intrinsic = max(0.0, S - K) if option_type == 'call' else max(0.0, K - S)
        return round(intrinsic, 2)
    sigma = max(sigma, 0.01)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type == 'call':
        price = S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    else:
        price = K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)
    return round(max(0.0, price), 2)


def bs_delta(S, K, T, r, sigma, option_type='call'):
    """Black-Scholes delta."""
    if T <= 0:
        if option_type == 'call':
            return 1.0 if S > K else 0.0
        return -1.0 if S < K else 0.0
    sigma = max(sigma, 0.01)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    if option_type == 'call':
        return round(_norm_cdf(d1), 4)
    return round(_norm_cdf(d1) - 1.0, 4)


def bs_gamma(S, K, T, r, sigma):
    """Black-Scholes gamma."""
    if T <= 0 or sigma <= 0:
        return 0.0
    sigma = max(sigma, 0.01)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    phi = math.exp(-d1**2 / 2.0) / math.sqrt(2 * math.pi)
    return round(phi / (S * sigma * math.sqrt(T)), 6)


# ── Expiry helpers ─────────────────────────────────────────────────────────

def get_next_expiry():
    """Next Nifty weekly Thursday expiry."""
    today = date.today()
    days = (3 - today.weekday()) % 7
    if days == 0 and today.weekday() == 3:
        days = 7
    return today + timedelta(days=days)


def days_to_expiry(expiry_date=None):
    if expiry_date is None:
        expiry_date = get_next_expiry()
    delta = (expiry_date - date.today()).days
    return max(0, delta)


def t_years(dte):
    return max(0.0003, dte / 365.25)


# ── Synthetic option chain ─────────────────────────────────────────────────

def build_synthetic_option_chain(spot, vix, dte=None, r=0.065):
    """
    Build a synthetic Nifty option chain using Black-Scholes.
    vix is India VIX (annualised 30-day IV in % terms → sigma = vix/100).
    """
    if dte is None:
        dte = days_to_expiry()
    sigma = vix / 100.0
    T = t_years(dte)
    atm = round(spot / 50) * 50

    strikes = []
    for K in range(int(atm - 1000), int(atm + 1050), 50):
        ce = bs_price(spot, K, T, r, sigma, 'call')
        pe = bs_price(spot, K, T, r, sigma, 'put')
        ce_d = bs_delta(spot, K, T, r, sigma, 'call')
        pe_d = bs_delta(spot, K, T, r, sigma, 'put')
        g = bs_gamma(spot, K, T, r, sigma)

        dist = abs(K - atm)
        oi_w = max(0.05, 1 - dist / 1200)
        ce_oi = int(800000 * oi_w * (1.0 if K >= atm else 0.7))
        pe_oi = int(800000 * oi_w * (0.7 if K >= atm else 1.0))

        # Simple vol skew: OTM PEs get ~5% IV premium
        skew = 1.0 + (0.05 if K < atm else 0.0)
        strikes.append({
            "strike": K,
            "is_atm": K == atm,
            "is_nearby": dist <= 150,
            "ce_premium": ce,
            "pe_premium": pe,
            "ce_delta": ce_d,
            "pe_delta": pe_d,
            "gamma": g,
            "ce_iv": round(vix * (1 + dist / (spot * 3)), 1),
            "pe_iv": round(vix * skew * (1 + dist / (spot * 3)), 1),
            "ce_oi": ce_oi,
            "pe_oi": pe_oi,
            "ce_oi_change": 0,
            "pe_oi_change": 0,
            "ce_volume": 0,
            "pe_volume": 0,
            "data_source": "BLACK_SCHOLES",
        })

    return {
        "spot": spot,
        "atm_strike": atm,
        "strikes": strikes,
        "vix": vix,
        "dte": dte,
        "data_source": "BLACK_SCHOLES",
        "synthetic": True,
    }


# ── Strike selection for intraday ──────────────────────────────────────────

def select_intraday_strike(spot, bias, vix, dte, r=0.065):
    """
    Pick the best intraday strike for ₹50k-₹1L capital.
    Targets OTM options with premium ₹30-100 and delta ~0.30-0.45.
    """
    sigma = vix / 100.0
    T = t_years(dte)
    atm = round(spot / 50) * 50
    opt = 'put' if bias == 'bearish' else 'call'
    sign = -1 if bias == 'bearish' else 1

    best = None
    for offset in [50, 100, 150, 200, 250, 300]:
        # bearish → OTM put = strike BELOW spot
        # bullish → OTM call = strike ABOVE spot
        K = round((spot - offset if bias == 'bearish' else spot + offset) / 50) * 50
        prem = bs_price(spot, K, T, r, sigma, opt)
        d = abs(bs_delta(spot, K, T, r, sigma, opt))
        if prem < 5:
            continue
        # Scoring: prefer delta 0.30-0.45 AND premium 35-90
        delta_score = max(0, 10 - abs(d - 0.38) * 50)
        prem_score = 10 if 35 <= prem <= 90 else (5 if 20 <= prem <= 130 else 0)
        score = delta_score + prem_score
        if best is None or score > best['score']:
            best = {
                'strike': K, 'option_type': 'PE' if bias == 'bearish' else 'CE',
                'premium': prem, 'delta': d, 'offset': offset, 'score': score,
                'rationale': f"{'PE' if bias == 'bearish' else 'CE'} {K} — {offset}pt OTM, Δ={d:.2f}, ₹{prem}",
            }

    if best is None:
        # Absolute fallback: ATM option
        K = atm
        prem = bs_price(spot, K, T, r, sigma, opt)
        d = abs(bs_delta(spot, K, T, r, sigma, opt))
        best = {
            'strike': K, 'option_type': 'PE' if bias == 'bearish' else 'CE',
            'premium': prem, 'delta': d, 'offset': 0, 'score': 0,
            'rationale': f"ATM fallback {K}",
        }
    return best


# ── Spot ↔ Premium conversion ──────────────────────────────────────────────

def spot_to_premium_sl(entry_prem, spot_entry, spot_sl, delta_abs, option_type):
    """
    Translate a spot stop-loss level to option premium SL.
    Uses delta approximation + a 15% gamma buffer.
    """
    spot_adverse = abs(spot_sl - spot_entry)
    if option_type == 'PE':
        # SL is above entry spot for a put trade
        # As spot rises, put premium falls
        prem_loss = delta_abs * spot_adverse * 1.15
        sl_prem = entry_prem - prem_loss
    else:
        # SL is below entry spot for a call trade
        prem_loss = delta_abs * spot_adverse * 1.15
        sl_prem = entry_prem - prem_loss
    # Floor: at least 45% of entry (max ~55% loss on premium for intraday)
    return round(max(sl_prem, entry_prem * 0.45), 2)


def spot_to_premium_target(entry_prem, spot_entry, spot_target, delta_abs, option_type):
    """
    Translate spot target to option premium target.
    Uses delta approximation + 20% gamma boost for favorable moves.
    """
    spot_move = abs(spot_target - spot_entry)
    prem_gain = delta_abs * spot_move * 1.20  # gamma boosts the gain
    target_prem = entry_prem + prem_gain
    return round(max(target_prem, entry_prem * 1.35), 2)
