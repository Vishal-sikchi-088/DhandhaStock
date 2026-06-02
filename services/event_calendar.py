"""
Event Risk Calendar
Flags high-impact events that affect trade confidence or warrant skipping.
Also determines current market phase (PRE_OPEN / WATCH / ENTRY_WINDOW / etc.)
"""

from datetime import date, datetime, timedelta


# ── Scheduled high-impact events (keep updated monthly) ───────────────────
# Format: (YYYY-MM-DD, name, impact)  impact: CRITICAL / HIGH / MEDIUM
SCHEDULED_EVENTS = [
    # RBI policy dates 2026
    ("2026-06-05", "RBI Monetary Policy Decision", "HIGH"),
    ("2026-06-06", "RBI Policy Press Conference", "HIGH"),
    ("2026-08-06", "RBI Monetary Policy Decision", "HIGH"),
    ("2026-10-08", "RBI Monetary Policy Decision", "HIGH"),
    ("2026-12-04", "RBI Monetary Policy Decision", "HIGH"),

    # US Fed 2026 (impacts globally)
    ("2026-06-11", "US Fed FOMC Decision", "HIGH"),
    ("2026-07-29", "US Fed FOMC Decision", "HIGH"),
    ("2026-09-17", "US Fed FOMC Decision", "HIGH"),
    ("2026-11-05", "US Fed FOMC Decision", "HIGH"),
    ("2026-12-17", "US Fed FOMC Decision", "HIGH"),

    # Budget / macro
    ("2026-02-01", "Union Budget Presentation", "CRITICAL"),
    ("2026-07-01", "Q1 GDP Data", "MEDIUM"),
    ("2026-10-01", "Q2 GDP Data", "MEDIUM"),
]


# ── Market phase ───────────────────────────────────────────────────────────

def get_market_phase():
    """
    Returns (phase_code, human_message) based on current time.

    Phases:
      PRE_OPEN    : before 9:15 AM
      WATCH       : 9:15 – 9:30 (first candle, don't trade yet)
      ENTRY_WINDOW: 9:30 – 10:30 (best window for entries)
      ACTIVE      : 10:30 – 12:30 (trail existing, no new entries)
      EXIT_ZONE   : 12:30 – 15:15 (force-exit intraday positions)
      CLOSING     : 15:15 – 15:30 (last 15 minutes)
      CLOSED      : after 15:30 or weekend
    """
    now = datetime.now()
    if now.weekday() >= 5:  # Saturday / Sunday
        return "CLOSED", "Weekend — market closed"

    hm = now.hour * 100 + now.minute

    if hm < 900:
        return "PRE_OPEN", "Market opens at 9:15 AM — review morning brief"
    if hm < 915:
        return "PRE_OPEN", "Pre-open session (9:00–9:15) — do not trade yet"
    if hm < 930:
        return "WATCH", "First 15 minutes — watch direction, NO entry yet"
    if hm < 1030:
        return "ENTRY_WINDOW", "Entry window (9:30–10:30) — execute confirmed setups"
    if hm < 1230:
        return "ACTIVE", "Active hours — monitor open trades, no new entries"
    if hm < 1515:
        return "EXIT_ZONE", "Past 12:30 PM — exit all intraday positions NOW"
    if hm < 1530:
        return "CLOSING", "Closing — force-exit any remaining intraday trades"
    return "CLOSED", "Market closed (after 3:30 PM)"


def time_to_exit_str():
    """Human-readable countdown to 12:30 PM intraday exit."""
    now = datetime.now()
    exit_dt = now.replace(hour=12, minute=30, second=0, microsecond=0)
    if now >= exit_dt:
        return "PAST EXIT TIME"
    td = exit_dt - now
    h = td.seconds // 3600
    m = (td.seconds % 3600) // 60
    return f"{h}h {m}m" if h > 0 else f"{m}m"


# ── Event detection ────────────────────────────────────────────────────────

def get_todays_events():
    """Return list of event dicts for today."""
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    tomorrow_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    events = []

    # Weekly expiry — every Thursday
    if today.weekday() == 3:
        events.append({
            "type": "WEEKLY_EXPIRY",
            "name": "Nifty Weekly Expiry Day",
            "impact": "HIGH",
            "description": "Thursday expiry — extreme gamma risk. Avoid buying options today.",
            "avoid_trading": True,
            "reduce_size": True,
        })

    # Monthly expiry — last Thursday of the month
    last_thursday = _last_thursday_of_month(today)
    if today == last_thursday:
        events.append({
            "type": "MONTHLY_EXPIRY",
            "name": "Nifty Monthly Expiry Day",
            "impact": "HIGH",
            "description": "Monthly expiry — volatility spike near close. Trade with caution.",
            "avoid_trading": True,
            "reduce_size": True,
        })

    # Month-end rebalancing
    next_weekday = today + timedelta(days=1)
    while next_weekday.weekday() >= 5:
        next_weekday += timedelta(days=1)
    if next_weekday.month != today.month:
        events.append({
            "type": "MONTH_END",
            "name": "Month End",
            "impact": "MEDIUM",
            "description": "Month-end — institutional rebalancing possible.",
            "avoid_trading": False,
            "reduce_size": False,
        })

    # Scheduled events today
    for ds, name, impact in SCHEDULED_EVENTS:
        if ds == today_str:
            events.append({
                "type": "SCHEDULED",
                "name": name,
                "impact": impact,
                "description": f"{name} — Avoid directional trades. Hold cash.",
                "avoid_trading": impact == "CRITICAL",
                "reduce_size": True,
            })

    # Pre-event warning for tomorrow's high-impact event
    for ds, name, impact in SCHEDULED_EVENTS:
        if ds == tomorrow_str and impact in ("HIGH", "CRITICAL"):
            events.append({
                "type": "PRE_EVENT",
                "name": f"Tomorrow: {name}",
                "impact": "MEDIUM",
                "description": f"Day before {name} — reduce position size today.",
                "avoid_trading": False,
                "reduce_size": True,
            })

    return events


def _last_thursday_of_month(d):
    """Return the last Thursday of d's month."""
    import calendar
    last_day = calendar.monthrange(d.year, d.month)[1]
    last = date(d.year, d.month, last_day)
    # Walk back to Thursday
    offset = (last.weekday() - 3) % 7
    return last - timedelta(days=offset)


# ── Summary ────────────────────────────────────────────────────────────────

def get_event_risk_summary():
    """
    Aggregate today's events into a single risk summary dict.
    Used by intraday_engine to gate trades and adjust confidence.
    """
    events = get_todays_events()
    if not events:
        return {
            "has_events": False,
            "should_avoid": False,
            "reduce_size": False,
            "highest_impact": None,
            "primary_event": None,
            "events": [],
            "summary": None,
            "confidence_reduction": 0,
        }

    impact_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    should_avoid = any(e.get("avoid_trading") for e in events)
    reduce_size = any(e.get("reduce_size") for e in events)
    top = max(events, key=lambda e: impact_rank.get(e["impact"], 0))

    conf_cut = 0
    for e in events:
        if e["impact"] == "CRITICAL":
            conf_cut = max(conf_cut, 30)
        elif e["impact"] == "HIGH":
            conf_cut = max(conf_cut, 15)
        elif e["impact"] == "MEDIUM":
            conf_cut = max(conf_cut, 5)

    return {
        "has_events": True,
        "should_avoid": should_avoid,
        "reduce_size": reduce_size,
        "highest_impact": top["impact"],
        "primary_event": top["name"],
        "events": events,
        "summary": top["description"],
        "confidence_reduction": conf_cut,
    }
