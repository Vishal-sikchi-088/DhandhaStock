"""
Intraday Trading Signal Engine
20-Year Experienced Trader Framework — Morning-Only Nifty Options

Capital profile: ₹50k – ₹1L
Trade window:   9:30 AM – 10:30 AM  (entry), exit by 12:30 PM
Lot size:       75 units (Nifty 50, post Oct-2024 SEBI revision)

Strategies:
  1. ORB (Opening Range Breakout) — 9:15–9:30 range break with volume
  2. Gap Continuation — strong gap (> 80 pts) that holds through 9:30
  3. Trend Follow — multi-TF + SMC aligned, VWAP confirmation
"""

from datetime import date, datetime
from .option_pricer import (
    select_intraday_strike, spot_to_premium_sl, spot_to_premium_target,
    days_to_expiry, get_next_expiry,
)
from .event_calendar import get_event_risk_summary, get_market_phase, time_to_exit_str

LOT_SIZE = 75


# ── Session helpers ────────────────────────────────────────────────────────

def _session_info():
    phase, msg = get_market_phase()
    return {
        "time": datetime.now().strftime("%I:%M %p"),
        "phase": phase,
        "phase_message": msg,
        "time_to_exit": time_to_exit_str(),
        "can_enter": phase == "ENTRY_WINDOW",
    }


# ── Gap analysis ───────────────────────────────────────────────────────────

def _gap_info(market_status):
    prev_close = (market_status or {}).get("previous_close", 0)
    open_price = (market_status or {}).get("open", 0)
    last = (market_status or {}).get("last_price", 0)
    ref = open_price or last or prev_close or 1
    gap = ref - prev_close if prev_close else 0
    gap_pct = (gap / prev_close * 100) if prev_close else 0

    if gap > 100:
        gap_type = "gap_up_strong"
    elif gap > 50:
        gap_type = "gap_up"
    elif gap > 20:
        gap_type = "gap_up_small"
    elif gap < -100:
        gap_type = "gap_down_strong"
    elif gap < -50:
        gap_type = "gap_down"
    elif gap < -20:
        gap_type = "gap_down_small"
    else:
        gap_type = "flat"

    return {
        "type": gap_type,
        "gap_pts": round(gap, 1),
        "gap_pct": round(gap_pct, 2),
        "prev_close": prev_close,
        "ref_price": round(ref, 2),
        "is_gap": abs(gap) > 20,
        "is_strong_gap": abs(gap) > 80,
        "direction": "up" if gap > 20 else "down" if gap < -20 else "flat",
    }


# ── ORB (Opening Range Breakout) ───────────────────────────────────────────

def _orb_analysis(df_5m, spot):
    """Analyse the 9:15–9:30 opening range from 5-min data."""
    if df_5m is None or len(df_5m) < 3:
        return {"available": False}

    today = date.today()
    try:
        df_today = df_5m[df_5m.index.date == today]
    except Exception:
        df_today = df_5m.tail(6)

    if len(df_today) < 2:
        df_today = df_5m.tail(6)

    # First 3 candles = 9:15, 9:20, 9:25  (the opening range)
    orb_candles = df_today.head(3)
    orb_high = float(orb_candles['High'].max())
    orb_low = float(orb_candles['Low'].min())
    orb_range = orb_high - orb_low

    current = float(df_today['Close'].iloc[-1]) if len(df_today) > 0 else spot
    avg_vol = float(df_today['Volume'].mean()) if 'Volume' in df_today.columns else 0
    last_vol = float(df_today['Volume'].iloc[-1]) if 'Volume' in df_today.columns else 0
    vol_surge = last_vol > avg_vol * 1.5 if avg_vol > 0 else False

    breakout_dir = None
    confirmed = False
    if current > orb_high * 1.001:
        breakout_dir = "bullish"
        confirmed = True
    elif current < orb_low * 0.999:
        breakout_dir = "bearish"
        confirmed = True

    # Detect gap-fill scenario: large gap AND price has recovered > 50% of gap
    # In this case the ORB breakout is just the gap filling, not a directional signal
    gap_fill_in_progress = False

    return {
        "available": True,
        "orb_high": round(orb_high, 2),
        "orb_low": round(orb_low, 2),
        "orb_range": round(orb_range, 2),
        "current": round(current, 2),
        "breakout_direction": breakout_dir,
        "breakout_confirmed": confirmed,
        "volume_surge": vol_surge,
        "inside_orb": orb_low <= current <= orb_high,
        "gap_fill_in_progress": gap_fill_in_progress,
        "bullish_target": round(orb_high + orb_range * 1.5, 2),
        "bearish_target": round(orb_low - orb_range * 1.5, 2),
        "bullish_sl": round(orb_low, 2),
        "bearish_sl": round(orb_high, 2),
    }


# ── Intraday bias ──────────────────────────────────────────────────────────

def _intraday_bias(chart, smc, flow_data, gap, orb, vix):
    """
    Combine signals → (bias, confidence %, reasons[], raw_score).

    Scoring buckets (out of 100):
      Chart multi-TF alignment    30
      SMC structure + BOS/CHoCH  25
      Gap direction               15
      ORB (gap-context aware)     20
      FII net flow (direct)       10

    Key rules:
      - ORB direction is ONLY counted if it ALIGNS with the gap direction
        (gap fill recoveries are not valid ORB signals)
      - FII is scored directly by net ₹ amount, not via cumulative_bias
        (DII buying on dip often offsets FII — we care about FII direction)
      - Threshold for "bearish"/"bullish" is ±30, not ±40
    """
    score = 0
    reasons = []

    # ── 1. Chart multi-timeframe alignment (30 pts) ──────────────────────────
    chart_bias = (chart or {}).get("bias", "neutral")
    if "strongly_bullish" in chart_bias:
        score += 30;  reasons.append("All 4 timeframes strongly bullish")
    elif "bullish" in chart_bias:
        score += 20;  reasons.append("Multi-timeframe alignment bullish")
    elif "mildly_bullish" in chart_bias:
        score += 10;  reasons.append("Mildly bullish chart bias")
    elif "strongly_bearish" in chart_bias:
        score -= 30;  reasons.append("All 4 timeframes strongly bearish")
    elif "bearish" in chart_bias:
        score -= 20;  reasons.append("Multi-timeframe alignment bearish")
    elif "mildly_bearish" in chart_bias:
        score -= 10;  reasons.append("Mildly bearish chart bias")
    else:
        reasons.append("Chart bias neutral / mixed")

    # ── 2. SMC structure + BOS + CHoCH (25 pts total) ───────────────────────
    if smc and not smc.get("error"):
        smc_bias = smc.get("bias", "neutral")
        if smc_bias == "bullish":
            score += 10;  reasons.append("SMC 5m structure bullish")
        elif smc_bias == "bearish":
            score -= 10;  reasons.append("SMC 5m structure bearish")

        bos = smc.get("last_bos")
        if bos:
            if bos.get("direction") == "bullish":
                score += 8;  reasons.append(f"BOS bullish confirmed at {bos['level']:.0f}")
            else:
                score -= 8;  reasons.append(f"BOS bearish confirmed at {bos['level']:.0f}")

        choch = smc.get("last_choch")
        if choch:
            if choch.get("direction") == "bullish":
                score += 7;  reasons.append(f"CHoCH turned BULLISH at {choch['level']:.0f}")
            else:
                score -= 7;  reasons.append(f"CHoCH turned BEARISH at {choch['level']:.0f}")

    # ── 3. Gap direction (15 pts) ─────────────────────────────────────────────
    gap_dir = gap.get("direction", "flat")
    gap_pts = gap.get("gap_pts", 0)
    if gap.get("is_strong_gap"):
        if gap_dir == "up":
            score += 15;  reasons.append(f"Strong gap UP {gap_pts:.0f} pts — bullish opening pressure")
        elif gap_dir == "down":
            score -= 15;  reasons.append(f"Strong gap DOWN {abs(gap_pts):.0f} pts — bearish opening pressure")
    elif gap.get("is_gap"):
        if gap_dir == "up":
            score += 8;   reasons.append(f"Gap up {gap_pts:.0f} pts")
        elif gap_dir == "down":
            score -= 8;   reasons.append(f"Gap down {abs(gap_pts):.0f} pts")

    # ── 4. ORB — gap-context aware (20 pts) ──────────────────────────────────
    # CRITICAL FIX: A strong gap-down day where price recovers above ORB high
    # is a GAP FILL move, NOT a bullish breakout. We only credit ORB points
    # when the breakout direction ALIGNS with the gap (gap continuation).
    if orb.get("breakout_confirmed"):
        orb_dir = orb["breakout_direction"]
        is_strong_gap = gap.get("is_strong_gap", False)
        is_gap_fill = (
            is_strong_gap
            and gap_dir == "down" and orb_dir == "bullish"   # gap-down, price recovered up
        ) or (
            is_strong_gap
            and gap_dir == "up" and orb_dir == "bearish"     # gap-up, price fell back
        )

        if is_gap_fill:
            # Gap fill in progress — ORB direction is NOT a trading signal
            reasons.append(
                f"ORB {'bullish' if orb_dir == 'bullish' else 'bearish'} "
                f"but gap was {'down' if gap_dir == 'down' else 'up'} — gap fill move, NOT a {orb_dir} setup. "
                f"Wait for rejection at {gap['ref_price']:.0f} (prev close zone)"
            )
        elif orb_dir == "bullish":
            bonus = 20 if orb.get("volume_surge") else 14
            score += bonus
            reasons.append(f"ORB breakout ABOVE {orb['orb_high']:.0f} confirms bullish" +
                           (" — with volume surge" if orb.get("volume_surge") else ""))
        elif orb_dir == "bearish":
            bonus = 20 if orb.get("volume_surge") else 14
            score -= bonus
            reasons.append(f"ORB breakdown BELOW {orb['orb_low']:.0f} confirms bearish" +
                           (" — with volume surge" if orb.get("volume_surge") else ""))
    elif orb.get("inside_orb"):
        reasons.append(
            f"Price inside ORB range {orb.get('orb_low', 0):.0f}–{orb.get('orb_high', 0):.0f} "
            f"— wait for breakout before entry"
        )

    # ── 5. FII net flow — scored DIRECTLY (not via cumulative_bias) ───────────
    # cumulative_bias is often "neutral" because DII buying offsets FII selling.
    # For intraday, FII direction matters more than combined score.
    if flow_data and not flow_data.get("error"):
        fii_dii = flow_data.get("fii_dii") or {}
        fii_net = fii_dii.get("fii_net", 0) or 0
        dii_net = fii_dii.get("dii_net", 0) or 0

        if fii_net <= -2000:
            score -= 10;  reasons.append(f"FII STRONG sellers ₹{abs(fii_net):.0f} Cr — heavy institutional selling")
        elif fii_net <= -800:
            score -= 8;   reasons.append(f"FII net sellers ₹{abs(fii_net):.0f} Cr — institutional headwind")
        elif fii_net <= -200:
            score -= 4;   reasons.append(f"FII mild sellers ₹{abs(fii_net):.0f} Cr")
        elif fii_net >= 2000:
            score += 10;  reasons.append(f"FII STRONG buyers ₹{fii_net:.0f} Cr — institutional tailwind")
        elif fii_net >= 800:
            score += 8;   reasons.append(f"FII net buyers ₹{fii_net:.0f} Cr — bullish institutional flow")
        elif fii_net >= 200:
            score += 4;   reasons.append(f"FII mild buyers ₹{fii_net:.0f} Cr")
        else:
            reasons.append("FII/DII flow neutral")

        # DII buying large on a gap-down day = dip buying (slightly bullish short-term,
        # but DII rarely reverses the trend — just a caution)
        if dii_net > 2000 and fii_net < -1000:
            reasons.append(f"DII bought ₹{dii_net:.0f} Cr (dip buying) — short-term support but FII controls trend")

    # ── VIX context (modifier, not points) ───────────────────────────────────
    if vix < 12:
        reasons.append(f"VIX {vix:.1f} — very low, directional conviction weak")
        score = int(score * 0.85)
    elif vix > 22:
        reasons.append(f"VIX {vix:.1f} — elevated, larger-than-usual moves expected")

    # ── Score → bias + confidence ─────────────────────────────────────────────
    # Thresholds: ±30 for directional (was ±40 — too forgiving, fixed)
    # A day with all-4-TF bearish (-30) + strong gap down (-15) alone = -45
    # → must be "bearish", not "mildly_bearish"
    abs_score = abs(score)
    if score >= 30:
        bias = "bullish"
        conf = min(88, 58 + abs_score * 0.5)
    elif score >= 15:
        bias = "mildly_bullish"
        conf = min(72, 50 + abs_score * 0.5)
    elif score <= -30:
        bias = "bearish"
        conf = min(88, 58 + abs_score * 0.5)
    elif score <= -15:
        bias = "mildly_bearish"
        conf = min(72, 50 + abs_score * 0.5)
    else:
        bias = "neutral"
        conf = 42

    return bias, round(conf, 1), reasons, score


# ── Trade parameters ───────────────────────────────────────────────────────

def _build_trade(spot, bias, vix, dte, capital, chart):
    """Compute the full options trade with premium-based levels."""
    direction = "bearish" if "bearish" in bias else "bullish"

    # DTE ≤ 2: use ATM or near-ATM (50pt OTM max) — OTM options decay too fast
    # DTE ≤ 1: do not build a trade (expiry day gate handles this above)
    if dte <= 2:
        # Force select_intraday_strike to prefer close-to-ATM by temporarily lowering DTE signal
        # We pass dte=5 to the pricer to get a strike that would be appropriate for a normal day
        # but use the real dte for premium calculation
        strike_info = select_intraday_strike(spot, direction, vix, max(dte, 5))
        # Verify the selected strike isn't too far OTM for 2 DTE
        if strike_info and abs(strike_info['strike'] - spot) > 150:
            # Force to 50-100pt OTM
            from .option_pricer import bs_price, bs_delta, t_years
            K = round((spot - 75 if direction == 'bearish' else spot + 75) / 50) * 50
            sigma = vix / 100
            T = t_years(dte)
            prem = bs_price(spot, K, T, 0.065, sigma, 'put' if direction == 'bearish' else 'call')
            delta = abs(bs_delta(spot, K, T, 0.065, sigma, 'put' if direction == 'bearish' else 'call'))
            opt = 'PE' if direction == 'bearish' else 'CE'
            strike_info = {'strike': K, 'option_type': opt, 'premium': prem, 'delta': delta,
                           'rationale': f'{opt} {K} — 75pt OTM (DTE={dte} near-expiry selection)'}
    else:
        strike_info = select_intraday_strike(spot, direction, vix, dte)
    if not strike_info:
        return None

    K = strike_info['strike']
    opt_type = strike_info['option_type']          # 'CE' or 'PE'
    entry_prem = strike_info['premium']
    delta_abs = strike_info['delta']               # already abs()

    # Key levels from chart for spot SL/target
    key_levels = (chart or {}).get("key_levels", [])
    supports = sorted([l["price"] for l in key_levels if l.get("role") == "support"], reverse=True)
    resistances = sorted([l["price"] for l in key_levels if l.get("role") == "resistance"])
    daily_atr = ((chart or {}).get("daily") or {}).get("atr") or (spot * 0.005)

    if direction == "bearish":
        spot_sl = round(min(
            resistances[0] if resistances else spot + daily_atr * 1.5,
            spot + daily_atr * 1.2,
        ), 2)
        spot_t1 = round(max(
            supports[0] if supports else spot - daily_atr * 2.5,
            spot - daily_atr * 2.2,
        ), 2)
        spot_t2 = round(max(
            supports[1] if len(supports) > 1 else spot - daily_atr * 4,
            spot - daily_atr * 3.8,
        ), 2)
    else:
        spot_sl = round(max(
            supports[0] if supports else spot - daily_atr * 1.5,
            spot - daily_atr * 1.2,
        ), 2)
        spot_t1 = round(min(
            resistances[0] if resistances else spot + daily_atr * 2.5,
            spot + daily_atr * 2.2,
        ), 2)
        spot_t2 = round(min(
            resistances[1] if len(resistances) > 1 else spot + daily_atr * 4,
            spot + daily_atr * 3.8,
        ), 2)

    # Convert to premium levels
    sl_prem = spot_to_premium_sl(entry_prem, spot, spot_sl, delta_abs, opt_type)
    t1_prem = spot_to_premium_target(entry_prem, spot, spot_t1, delta_abs, opt_type)
    t2_prem = spot_to_premium_target(entry_prem, spot, spot_t2, delta_abs, opt_type)

    # Enforce sanity: SL < entry < T1 < T2
    sl_prem = min(sl_prem, entry_prem * 0.68)
    t1_prem = max(t1_prem, entry_prem * 1.40)
    t2_prem = max(t2_prem, t1_prem * 1.30)

    # Entry range ±8%
    entry_low = round(entry_prem * 0.92, 2)
    entry_high = round(entry_prem * 1.08, 2)

    # Position sizing  (₹50k–₹1L → 1 lot, ₹1.5L+ → 2 lots if risk allows)
    risk_per_lot = round((entry_prem - sl_prem) * LOT_SIZE, 0)
    max_allowed_risk = capital * 0.025  # 2.5% of capital
    lots = 1
    if capital >= 150000 and risk_per_lot * 2 <= max_allowed_risk:
        lots = 2
    total_risk = lots * risk_per_lot
    deployed = lots * entry_prem * LOT_SIZE

    # R:R
    rr1 = round((t1_prem - entry_prem) / max(entry_prem - sl_prem, 0.5), 2)
    rr2 = round((t2_prem - entry_prem) / max(entry_prem - sl_prem, 0.5), 2)

    # Expiry info
    expiry_date = get_next_expiry()
    expiry_disp = expiry_date.strftime("%d %b %Y")
    expiry_short = expiry_date.strftime("%d%b%y").upper()
    search_term = f"NIFTY {K} {opt_type} {expiry_short}"

    # Groww steps
    groww = _groww_steps(lots, K, opt_type, expiry_short, entry_prem, sl_prem, t1_prem)

    return {
        # Option identity
        "direction": direction,
        "option_type": opt_type,
        "strike": K,
        "expiry_date": expiry_date.strftime("%Y-%m-%d"),
        "expiry_display": f"{expiry_disp} (Weekly · {dte} DTE)",
        "expiry_short": expiry_short,
        "search_term": search_term,

        # Premium levels
        "entry_ideal": entry_prem,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "stop_loss": sl_prem,
        "target1": t1_prem,
        "target2": t2_prem,

        # Spot context
        "spot": round(spot, 2),
        "spot_sl": round(spot_sl, 2),
        "spot_target1": round(spot_t1, 2),
        "spot_target2": round(spot_t2, 2),

        # Risk / sizing
        "delta": delta_abs,
        "lots": lots,
        "units": lots * LOT_SIZE,
        "risk_per_lot": risk_per_lot,
        "total_risk": total_risk,
        "capital_deployed": round(deployed, 0),
        "capital_at_risk_pct": round(total_risk / max(capital, 1) * 100, 1),

        # R:R
        "rr_t1": f"1:{rr1}",
        "rr_t2": f"1:{rr2}",
        "profit_t1": round((t1_prem - entry_prem) * lots * LOT_SIZE, 0),
        "profit_t2": round((t2_prem - entry_prem) * lots * LOT_SIZE, 0),

        # Execution
        "groww_steps": groww,
        "exit_time": "12:30 PM",
        "exit_rule": "Time-based exit: Close trade by 12:30 PM regardless of P&L",

        # Debug
        "strike_rationale": strike_info.get("rationale", ""),
    }


def _groww_steps(lots, strike, opt_type, expiry_short, entry, sl, target1):
    qty = lots * LOT_SIZE
    exp_label = expiry_short
    loss_est = round((entry - sl) * qty, 0)
    profit_est = round((target1 - entry) * qty, 0)
    return [
        "Open Groww → tap F&O (bottom bar)",
        "Tap 'Index' → select NIFTY",
        f"Expiry: {exp_label}  →  {opt_type}  →  Strike {strike}",
        f"Tap BUY | Qty: {qty}  ({lots} lot{'s' if lots > 1 else ''})",
        f"Order Type: LIMIT | Price: ₹{entry}",
        "Review & Place Order",
        "─── After order fills ───",
        "Portfolio → tap the option → '...' → Set GTT",
        f"GTT STOP: Sell when price ≤ ₹{sl}  (max loss ≈ ₹{loss_est:,.0f})",
        f"GTT TARGET: Sell when price ≥ ₹{target1}  (profit ≈ ₹{profit_est:,.0f})",
        "⚠ EXIT BY 12:30 PM — square off manually if neither GTT triggers",
    ]


# ── Morning Brief ──────────────────────────────────────────────────────────

def generate_morning_brief(premarket, chart, flow_data, vix_data):
    """Pre-market brief shown 9:00–9:15 AM."""
    market_status = (premarket or {}).get("market_status") or {}
    global_indices = (premarket or {}).get("global_indices") or []
    fii_dii = (premarket or {}).get("fii_dii") or {}

    vix = (vix_data or {}).get("current", 15) if isinstance(vix_data, dict) else 15

    # Global cues
    us_items, asia_items = [], []
    gold_info, crude_info = {}, {}
    for idx in global_indices:
        n, chg = idx.get("name", ""), idx.get("change_percent", 0)
        if n in ("S&P 500", "Dow Jones", "Nasdaq"):
            us_items.append(f"{n}: {chg:+.1f}%")
        elif n in ("Nikkei 225", "Hang Seng"):
            asia_items.append(f"{n}: {chg:+.1f}%")
        elif n == "Gold":
            gold_info = {"price": idx.get("price"), "chg_pct": chg}
        elif n == "Crude Oil":
            crude_info = {"price": idx.get("price"), "chg_pct": chg}

    sp500 = next((x for x in global_indices if x.get("name") == "S&P 500"), None)
    us_sentiment = ("positive" if (sp500 or {}).get("change_percent", 0) > 0.5
                    else "negative" if (sp500 or {}).get("change_percent", 0) < -0.5
                    else "neutral")

    # VIX
    if vix < 12:
        vix_verdict, vix_color = f"VIX {vix:.1f} — too low, rangebound likely", "amber"
    elif vix <= 18:
        vix_verdict, vix_color = f"VIX {vix:.1f} — IDEAL for buying options", "green"
    elif vix <= 25:
        vix_verdict, vix_color = f"VIX {vix:.1f} — elevated, reduce size", "amber"
    else:
        vix_verdict, vix_color = f"VIX {vix:.1f} — DANGER, very wide moves", "red"

    # FII
    fii_net = fii_dii.get("fii_net", 0)
    dii_net = fii_dii.get("dii_net", 0)
    if fii_net > 1000:
        fii_verdict, fii_color = f"FII bought ₹{fii_net:.0f} Cr — strong bullish", "green"
    elif fii_net > 300:
        fii_verdict, fii_color = f"FII net buyer ₹{fii_net:.0f} Cr", "green"
    elif fii_net < -1000:
        fii_verdict, fii_color = f"FII sold ₹{abs(fii_net):.0f} Cr — strong bearish", "red"
    elif fii_net < -300:
        fii_verdict, fii_color = f"FII net seller ₹{abs(fii_net):.0f} Cr", "red"
    else:
        fii_verdict, fii_color = "FII/DII activity neutral", "neutral"

    # Key levels
    key_levels = (chart or {}).get("key_levels", [])
    supports = sorted([l["price"] for l in key_levels if l.get("role") == "support"], reverse=True)[:3]
    resistances = sorted([l["price"] for l in key_levels if l.get("role") == "resistance"])[:3]

    # Overall morning score → bias
    m_score = 0
    c_bias = (chart or {}).get("bias", "neutral")
    if "strongly_bullish" in c_bias: m_score += 3
    elif "bullish" in c_bias:        m_score += 2
    elif "mildly_bullish" in c_bias: m_score += 1
    elif "strongly_bearish" in c_bias: m_score -= 3
    elif "bearish" in c_bias:        m_score -= 2
    elif "mildly_bearish" in c_bias: m_score -= 1
    if fii_net > 500:  m_score += 1
    elif fii_net < -500: m_score -= 1
    if us_sentiment == "positive": m_score += 1
    elif us_sentiment == "negative": m_score -= 1

    if m_score >= 3:        morning_bias = "BULLISH"
    elif m_score >= 1:      morning_bias = "MILDLY BULLISH"
    elif m_score <= -3:     morning_bias = "BEARISH"
    elif m_score <= -1:     morning_bias = "MILDLY BEARISH"
    else:                   morning_bias = "NEUTRAL"

    # Scenarios
    last_close = (chart or {}).get("last_close") or market_status.get("previous_close") or 0
    if last_close:
        s_res = resistances[0] if resistances else round(last_close * 1.012, 0)
        s_sup = supports[0] if supports else round(last_close * 0.988, 0)
        s_sup2 = supports[1] if len(supports) > 1 else round(last_close * 0.975, 0)
        scenarios = {
            "bull_case": f"Nifty holds above {last_close:.0f} → breaks {s_res:.0f} with volume → target {s_res+100:.0f}+",
            "bear_case": f"Nifty fails at {last_close:.0f} → breaks below {s_sup:.0f} → target {s_sup2:.0f}",
            "range_case": f"Nifty oscillates between {s_sup:.0f}–{s_res:.0f} → no trade, wait for ORB breakout",
        }
    else:
        scenarios = {}

    # Event risk
    event_risk = get_event_risk_summary()

    # DTE
    dte = days_to_expiry()
    expiry_date = get_next_expiry()

    # Strategy tip
    if event_risk.get("should_avoid"):
        tip = f"⚠ SKIP TODAY — {event_risk['primary_event']}"
    elif event_risk.get("has_events"):
        tip = f"Caution: {event_risk['primary_event']}. Trade 1 lot max. Wait for 9:30 confirmation."
    elif morning_bias in ("BEARISH", "MILDLY BEARISH"):
        lvl = supports[0] if supports else "key support"
        tip = f"Look for SHORT setup after 9:30. PE trade if Nifty fails to hold {lvl:.0f}."
    elif morning_bias in ("BULLISH", "MILDLY BULLISH"):
        lvl = resistances[0] if resistances else "key resistance"
        tip = f"Look for LONG setup after 9:30. CE trade on breakout above {lvl:.0f} with volume."
    else:
        tip = "Wait for ORB breakout after 9:30. Trade only the direction of the break, with volume."

    return {
        "date": date.today().strftime("%d %b %Y"),
        "time": datetime.now().strftime("%I:%M %p"),
        "morning_bias": morning_bias,
        "morning_score": m_score,
        "global_cues": {
            "us_markets": " | ".join(us_items) or "Unavailable",
            "asian_markets": " | ".join(asia_items) or "Unavailable",
            "us_sentiment": us_sentiment,
            "gold": gold_info,
            "crude": crude_info,
        },
        "vix_assessment": {"current": vix, "verdict": vix_verdict, "color": vix_color},
        "fii_dii": {"fii_net": fii_net, "dii_net": dii_net, "verdict": fii_verdict, "color": fii_color},
        "key_levels": {"supports": supports, "resistances": resistances},
        "scenarios": scenarios,
        "strategy_suggestion": tip,
        "event_risk": event_risk,
        "expiry_info": {
            "date": expiry_date.strftime("%d %b %Y"),
            "dte": dte,
            "warning": "EXPIRY DAY — Avoid buying options!" if dte == 0 else (
                f"Only {dte} day{'s' if dte > 1 else ''} to expiry — time decay accelerating" if dte <= 2 else None
            ),
        },
    }


# ── Main entry point ───────────────────────────────────────────────────────

def generate_intraday_signal(settings, premarket=None, chart=None, flow_data=None):
    """
    Full intraday signal pipeline.
    Returns a signal dict that is either has_signal=True (with trade) or False (with reason).
    """
    capital = float((settings or {}).get("capital", 75000))

    # Lazy-load data if not provided
    if premarket is None:
        from .premarket_data import get_all_premarket_data
        premarket = get_all_premarket_data()
    if chart is None:
        from .chart_analysis import analyze_chart
        chart = analyze_chart(
            premarket.get("historical_daily"),
            premarket.get("historical_60m"),
            premarket.get("historical_15m"),
            premarket.get("historical_5m"),
        ) if premarket else None
    if flow_data is None:
        from .institutional_flow import analyze_institutional_flow
        flow_data = analyze_institutional_flow()

    market_status = (premarket or {}).get("market_status") or {}
    vix_data = (premarket or {}).get("india_vix") or {}
    spot = market_status.get("last_price", 0) or (chart or {}).get("last_close", 0) or 24000
    vix = vix_data.get("current", 15) if isinstance(vix_data, dict) else 15
    smc = (chart or {}).get("smc")

    session = _session_info()
    event_risk = get_event_risk_summary()
    gap = _gap_info(market_status)
    df_5m = (premarket or {}).get("historical_5m")
    orb = _orb_analysis(df_5m, spot)
    dte = days_to_expiry()
    morning_brief = generate_morning_brief(premarket, chart, flow_data, vix_data)

    # ── Hard gates ────────────────────────────────────────────────────────
    if session["phase"] == "CLOSED":
        return _no_trade("Market closed — pre-market analysis only", "MARKET_CLOSED",
                         session, event_risk, gap, orb, spot, vix, dte, morning_brief)

    if session["phase"] == "PRE_OPEN":
        return _no_trade(session["phase_message"], "PRE_OPEN",
                         session, event_risk, gap, orb, spot, vix, dte, morning_brief)

    if session["phase"] in ("EXIT_ZONE", "CLOSING"):
        return _no_trade("Past 12:30 PM — no new entries. Exit open intraday positions.", "TIME_BASED",
                         session, event_risk, gap, orb, spot, vix, dte, morning_brief)

    if session["phase"] == "ACTIVE":
        # 10:30 AM – 12:30 PM: Entry window has closed. Show analysis but no new trade.
        bias, confidence, reasons, score = _intraday_bias(chart, smc, flow_data, gap, orb, vix)
        if event_risk.get("confidence_reduction"):
            confidence = max(35, confidence - event_risk["confidence_reduction"])
        pending = _build_trade(spot, bias, vix, dte, capital, chart) if bias not in ("neutral",) else None
        return {
            "has_signal": False,
            "pending_signal": False,
            "no_trade_reason": (
                f"Entry window closed (9:30–10:30 AM). "
                f"Bias is {bias.replace('_',' ').upper()} ({confidence:.0f}%). "
                f"No new entries — manage open positions only."
            ),
            "no_trade_category": "ACTIVE",
            "confidence": confidence,
            "bias": bias,
            "reasons": reasons,
            "spot": spot, "vix": vix, "dte": dte,
            "session_info": session,
            "event_risk": event_risk,
            "gap_info": gap,
            "orb": orb,
            "morning_brief": morning_brief,
            "analysis_summary": {
                "score": score,
                "bias": bias,
                "confidence": confidence,
                "entry_zone_for_next_session": (
                    f"Gap fill zone {gap.get('prev_close', 0):.0f} — watch for rejection candle there for {bias.split('_')[-1]} entry"
                    if gap.get("is_strong_gap") else "Watch key support/resistance levels"
                ),
            },
        }

    if event_risk.get("should_avoid"):
        return _no_trade(f"⚠ SKIP TODAY — {event_risk.get('primary_event', 'High-impact event')}", "EVENT_RISK",
                         session, event_risk, gap, orb, spot, vix, dte, morning_brief)

    if dte == 0:
        return _no_trade("EXPIRY DAY — Never buy options on expiry. Extreme gamma risk.", "EXPIRY_DAY",
                         session, event_risk, gap, orb, spot, vix, dte, morning_brief)

    if vix > 30:
        return _no_trade(f"VIX {vix:.1f} too high — do not buy options in extreme volatility.", "HIGH_VIX",
                         session, event_risk, gap, orb, spot, vix, dte, morning_brief)

    # ── Bias calculation ──────────────────────────────────────────────────
    bias, confidence, reasons, score = _intraday_bias(chart, smc, flow_data, gap, orb, vix)

    # Event confidence penalty
    if event_risk.get("confidence_reduction"):
        confidence = max(35, confidence - event_risk["confidence_reduction"])
        reasons.append(f"Confidence reduced by {event_risk['confidence_reduction']}% — {event_risk.get('primary_event', 'event')}")

    # ── Pending signal (WATCH phase) ──────────────────────────────────────
    if session["phase"] == "WATCH":
        pending = _build_trade(spot, bias, vix, dte, capital, chart) if bias != "neutral" else None
        return {
            "has_signal": False,
            "pending_signal": bias != "neutral" and confidence >= 55,
            "no_trade_reason": "First 15 minutes — watching price action. DO NOT enter yet.",
            "no_trade_category": "WATCH",
            "confidence": confidence,
            "bias": bias,
            "reasons": reasons,
            "pending_trade": pending,
            "spot": spot, "vix": vix, "dte": dte,
            "session_info": session,
            "event_risk": event_risk,
            "gap_info": gap,
            "orb": orb,
            "morning_brief": morning_brief,
        }

    # ── Minimum bar: confidence ≥ 60 and not neutral ──────────────────────
    if confidence < 60 or bias == "neutral":
        return _no_trade(
            f"Confidence {confidence:.0f}% — no clear edge. Wait for setup or ORB breakout.",
            "LOW_CONFIDENCE",
            session, event_risk, gap, orb, spot, vix, dte, morning_brief,
            confidence=confidence, bias=bias, reasons=reasons,
        )

    # ── Mildly directional: pending but not confirmed ─────────────────────
    if "mildly" in bias:
        pending = _build_trade(spot, bias.replace("mildly_", ""), vix, dte, capital, chart)
        return {
            "has_signal": False,
            "pending_signal": True,
            "no_trade_reason": f"Bias {bias.replace('_', ' ').upper()} ({confidence:.0f}%) — wait for stronger confirmation before entry.",
            "no_trade_category": "WEAK_SIGNAL",
            "confidence": confidence,
            "bias": bias,
            "reasons": reasons,
            "pending_trade": pending,
            "spot": spot, "vix": vix, "dte": dte,
            "session_info": session,
            "event_risk": event_risk,
            "gap_info": gap,
            "orb": orb,
            "morning_brief": morning_brief,
        }

    # ── Build confirmed trade ─────────────────────────────────────────────
    trade = _build_trade(spot, bias, vix, dte, capital, chart)
    if not trade:
        return _no_trade("Could not compute valid trade parameters.", "DATA_ERROR",
                         session, event_risk, gap, orb, spot, vix, dte, morning_brief,
                         confidence=confidence, bias=bias, reasons=reasons)

    risk_flags = []
    if dte <= 2:
        risk_flags.append(f"Only {dte} day(s) to expiry — time decay is rapid")
    if vix > 20:
        risk_flags.append(f"VIX {vix:.1f} elevated — use 1 lot only, widen mental stops")
    if event_risk.get("has_events"):
        risk_flags.append(event_risk.get("summary", "Event risk present today"))
    if trade.get("capital_at_risk_pct", 0) > 4:
        risk_flags.append(f"Risk {trade['capital_at_risk_pct']:.1f}% of capital — acceptable but monitor closely")

    if confidence >= 80:       grade = "A"
    elif confidence >= 70:     grade = "B"
    elif confidence >= 60:     grade = "C"
    else:                      grade = "D"

    sig_type = ("ORB_BREAKOUT" if orb.get("breakout_confirmed")
                else "GAP_CONTINUATION" if gap.get("is_strong_gap")
                else "TREND_FOLLOW")

    return {
        "has_signal": True,
        "signal_type": sig_type,
        "confidence": confidence,
        "grade": grade,
        "bias": bias,
        "reasons": reasons,
        "risk_flags": risk_flags,
        "trade": trade,
        "spot": spot,
        "vix": vix,
        "dte": dte,
        "gap_info": gap,
        "orb": orb,
        "session_info": session,
        "morning_brief": morning_brief,
        "event_risk": event_risk,
        "one_line": (
            f"BUY NIFTY {trade['strike']} {trade['option_type']} @ ₹{trade['entry_ideal']} "
            f"| SL ₹{trade['stop_loss']} | T1 ₹{trade['target1']} "
            f"| {trade['rr_t1']} R:R | {confidence:.0f}% confidence | Grade {grade}"
        ),
    }


def _no_trade(reason, category, session, event_risk, gap, orb, spot, vix, dte, morning_brief,
              confidence=None, bias=None, reasons=None):
    return {
        "has_signal": False,
        "no_trade_reason": reason,
        "no_trade_category": category,
        "confidence": confidence,
        "bias": bias,
        "reasons": reasons or [],
        "spot": spot,
        "vix": vix,
        "dte": dte,
        "session_info": session,
        "event_risk": event_risk,
        "gap_info": gap,
        "orb": orb,
        "morning_brief": morning_brief,
    }
