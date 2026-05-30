"""
Nifty 50 Options & Futures Analysis Dashboard
Flask backend with SQLite storage.
Institutional-grade trading AI with SMC, VWAP, Deep OI, and Live Monitoring.
"""

import os
from datetime import datetime
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)
app.secret_key = os.urandom(24)


def sanitize_for_json(obj):
    """Recursively convert numpy/pandas types to native Python types for JSON serialization."""
    import numpy as np
    import pandas as pd
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient='records')
    elif isinstance(obj, pd.Series):
        return obj.tolist()
    return obj


from services.database import init_db, get_settings, update_settings, save_trade, get_trades
from services.database import create_active_trade, get_active_trades, update_active_trade, save_trade_log
from services.analysis import analyze_option_chain, get_trend_analysis
from services.ai_reasoning import generate_trade_idea
from services.risk_manager import validate_trade
from services.market_data import get_market_summary, get_news_headlines
from services.premarket_data import get_all_premarket_data
from services.chart_analysis import analyze_chart
from services.news_ai import generate_market_news_context, analyze_news_sentiment, get_ai_market_narrative

# New institutional engines
from services.smc_analysis import analyze_smc
from services.volume_profile_vwap import analyze_vwap_and_profile
from services.oi_analyzer import analyze_deep_oi
from services.institutional_flow import analyze_institutional_flow
from services.probability_engine import calculate_probability
from services.strike_selector import select_strike
from services.strategy_selector import recommend_strategy_for_conditions
from services.trade_monitor import monitor_active_trades

init_db()


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/history")
def history():
    return render_template("history.html")


@app.route("/settings")
def settings_page():
    return render_template("settings.html")


# ---- API Routes ----

@app.route("/api/market-summary")
def api_market_summary():
    return jsonify(get_market_summary())


@app.route("/api/option-chain")
def api_option_chain():
    analysis = analyze_option_chain()
    return jsonify({
        "spot": analysis["spot"],
        "futures": analysis["futures"],
        "atm_strike": analysis["atm_strike"],
        "strikes": analysis["strikes"],
        "pcr": analysis["pcr"],
        "max_pain": analysis["max_pain"],
        "support": analysis["support_wall"],
        "resistance": analysis["resistance_wall"],
        "vix": analysis["vix"],
        "days_to_expiry": analysis["days_to_expiry"],
        "expiry_date": analysis["expiry_date"],
        "timestamp": analysis["timestamp"],
        "market_open": analysis["market_open"],
    })


@app.route("/api/trend")
def api_trend():
    analysis = analyze_option_chain()
    trend = get_trend_analysis(analysis)
    return jsonify(trend)


@app.route("/api/trade-idea")
def api_trade_idea():
    settings = get_settings()
    idea = generate_trade_idea(settings)
    return jsonify(sanitize_for_json(idea))


@app.route("/api/premarket")
def api_premarket():
    data = get_all_premarket_data()
    # Exclude raw DataFrames from JSON response — frontend uses analyzed endpoints
    clean = {k: v for k, v in data.items() if not hasattr(v, 'to_dict')}
    return jsonify(clean)


@app.route("/api/chart-analysis")
def api_chart_analysis():
    premarket = get_all_premarket_data()
    historical = premarket.get("historical_daily")
    historical_60m = premarket.get("historical_60m")
    historical_15m = premarket.get("historical_15m")
    historical_5m = premarket.get("historical_5m")
    if historical is not None:
        result = analyze_chart(historical, historical_60m, historical_15m, historical_5m)
        return jsonify(sanitize_for_json(result))
    return jsonify({"error": "Historical data unavailable"})


@app.route("/api/news-ai")
def api_news_ai():
    summary = get_market_summary()
    news = summary.get("news", [])
    analysis = analyze_news_sentiment(news)
    narrative = summary.get("narrative", {})
    return jsonify({
        "news": news,
        "analysis": analysis,
        "narrative": narrative
    })


@app.route("/api/save-trade", methods=["POST"])
def api_save_trade():
    data = request.get_json() or {}
    settings = get_settings()
    trade = data.get("trade")

    if not trade or trade.get("instrument_type") == "NO_TRADE":
        return jsonify({"success": False, "message": "No trade to save."})

    validation = validate_trade(trade, settings)
    if not validation["approved"]:
        return jsonify({"success": False, "message": "Trade failed risk validation.", "details": validation["messages"]})

    trade_record = {
        "timestamp": datetime.now().isoformat(),
        "instrument_type": trade["instrument_type"],
        "direction": trade["direction"],
        "entry": trade["entry"],
        "stop_loss": trade["stop_loss"],
        "target1": trade["target1"],
        "target2": trade.get("target2"),
        "quantity": trade["quantity"],
        "risk_reward": trade.get("risk_reward"),
        "confidence_score": data.get("confidence_score"),
        "confidence_label": data.get("confidence_label"),
        "market_trend": data.get("market_trend"),
        "pcr": data.get("pcr"),
        "max_pain": data.get("max_pain"),
        "atm_strike": data.get("atm_strike"),
        "spot": data.get("spot"),
        "futures": data.get("futures"),
        "days_to_expiry": data.get("days_to_expiry"),
        "vix": data.get("vix"),
        "reasons": data.get("reasons", []),
        "risk_factors": data.get("risk_factors", []),
        "invalidation_scenarios": data.get("invalidation_scenarios", [])
    }

    save_trade(trade_record)
    return jsonify({"success": True, "message": "Trade saved."})


@app.route("/api/trades")
def api_trades():
    limit = request.args.get("limit", 100, type=int)
    return jsonify(get_trades(limit))


@app.route("/api/news")
def api_news():
    return jsonify(get_news_headlines())


@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    return jsonify(get_settings())


@app.route("/api/settings", methods=["POST"])
def api_settings_post():
    data = request.get_json() or {}
    update_settings(data)
    return jsonify({"success": True})


# ---- NEW INSTITUTIONAL API ROUTES ----

@app.route("/api/smc-analysis")
def api_smc_analysis():
    premarket = get_all_premarket_data()
    df_5m = premarket.get("historical_5m")
    if df_5m is not None and len(df_5m) >= 30:
        result = analyze_smc(df_5m)
        return jsonify(sanitize_for_json(result))
    return jsonify({"error": "Insufficient 5-minute data for SMC analysis"})


@app.route("/api/volume-profile")
def api_volume_profile():
    premarket = get_all_premarket_data()
    df_5m = premarket.get("historical_5m")
    df_daily = premarket.get("historical_daily")
    if df_5m is not None and len(df_5m) >= 10:
        result = analyze_vwap_and_profile(df_5m, df_daily)
        return jsonify(sanitize_for_json(result))
    return jsonify({"error": "Insufficient data for Volume Profile analysis"})


@app.route("/api/deep-oi")
def api_deep_oi():
    analysis = analyze_option_chain()
    if analysis and analysis.get("market_open"):
        return jsonify(analyze_deep_oi(analysis))
    return jsonify({"error": "Option chain unavailable — market may be closed", "market_open": False})


@app.route("/api/institutional-flow")
def api_institutional_flow():
    return jsonify(analyze_institutional_flow())


@app.route("/api/probability-score")
def api_probability_score():
    """Calculate full probability score with all components."""
    summary = get_market_summary()
    premarket = get_all_premarket_data()
    analysis = analyze_option_chain()
    
    chart = analyze_chart(
        premarket.get("historical_daily"),
        premarket.get("historical_60m"),
        premarket.get("historical_15m"),
        premarket.get("historical_5m"),
    ) if premarket else None
    
    vwap_profile = chart.get("vwap_profile") if chart else None
    smc = chart.get("smc") if chart else None
    oi_data = analyze_deep_oi(analysis) if analysis and analysis.get("market_open") else None
    flow_data = analyze_institutional_flow()
    vix_data = premarket.get("india_vix", {}) if premarket else {}
    
    result = calculate_probability(smc, chart, oi_data, analysis, vwap_profile, flow_data, vix_data)
    return jsonify(sanitize_for_json(result))


@app.route("/api/strike-recommendation")
def api_strike_recommendation():
    """Get optimal strike recommendation for a direction."""
    direction = request.args.get("direction", "bullish")
    analysis = analyze_option_chain()
    if analysis and analysis.get("market_open"):
        result = select_strike(direction, analysis)
        return jsonify(result)
    return jsonify({"error": "Option chain unavailable", "market_open": False})


@app.route("/api/strategy-recommendation")
def api_strategy_recommendation():
    """Get options strategy recommendation."""
    summary = get_market_summary()
    premarket = get_all_premarket_data()
    analysis = analyze_option_chain()
    
    chart = analyze_chart(
        premarket.get("historical_daily"),
        premarket.get("historical_60m"),
        premarket.get("historical_15m"),
        premarket.get("historical_5m"),
    ) if premarket else None
    
    # Get probability for direction
    smc = chart.get("smc") if chart else None
    vwap_profile = chart.get("vwap_profile") if chart else None
    oi_data = analyze_deep_oi(analysis) if analysis and analysis.get("market_open") else None
    flow_data = analyze_institutional_flow()
    vix_data = premarket.get("india_vix", {}) if premarket else {}
    
    probability_result = calculate_probability(smc, chart, oi_data, analysis, vwap_profile, flow_data, vix_data)
    strategy = recommend_strategy_for_conditions(analysis, chart, probability_result)
    
    return jsonify(sanitize_for_json({
        "strategy": strategy,
        "probability": probability_result["probability"],
        "direction": probability_result["direction"],
    }))


# ---- ACTIVE TRADE MONITORING ----

@app.route("/api/active-trades", methods=["GET"])
def api_active_trades_get():
    return jsonify(get_active_trades())


@app.route("/api/active-trades", methods=["POST"])
def api_active_trades_post():
    """Create a new active trade from the current trade idea."""
    data = request.get_json() or {}
    trade = data.get("trade")
    
    if not trade or trade.get("instrument_type") == "NO_TRADE":
        return jsonify({"success": False, "message": "No trade to activate."})
    
    settings = get_settings()
    validation = validate_trade(trade, settings)
    if not validation["approved"]:
        return jsonify({"success": False, "message": "Trade failed risk validation.", "details": validation["messages"]})
    
    trade_id = create_active_trade({
        "instrument_type": trade.get("instrument_type"),
        "trade_type": trade.get("trade_type"),
        "strike": trade.get("strike"),
        "expiry": trade.get("expiry"),
        "entry": trade["entry"],
        "stop_loss": trade["stop_loss"],
        "target1": trade.get("target1"),
        "target2": trade.get("target2"),
        "target3": trade.get("target3"),
        "quantity": trade["quantity"],
        "risk_reward": trade.get("risk_reward"),
        "estimated_probability": trade.get("estimated_probability"),
        "strategy": trade.get("strategy"),
        "market_bias": data.get("market_bias"),
        "confidence_score": data.get("confidence_score"),
        "trade_quality_score": data.get("trade_quality_score"),
    })
    
    return jsonify({"success": True, "trade_id": trade_id, "message": "Trade activated for monitoring."})


@app.route("/api/monitor-action", methods=["POST"])
def api_monitor_action():
    """Apply an action to an active trade (exit, partial book, trail SL)."""
    data = request.get_json() or {}
    trade_id = data.get("trade_id")
    action = data.get("action")  # EXIT, PARTIAL_BOOK, TRAIL_SL
    reason = data.get("reason", "Manual action")
    
    if not trade_id or not action:
        return jsonify({"success": False, "message": "Trade ID and action required."})
    
    updates = {"action": action, "action_reason": reason}
    
    if action == "EXIT":
        updates["status"] = "exited"
        updates["final_pnl"] = data.get("pnl", 0)
        updates["exit_reason"] = reason
    elif action == "PARTIAL_BOOK":
        updates["action_reason"] = f"Partial booking: {reason}"
    elif action == "TRAIL_SL":
        updates["action_reason"] = f"Stop loss trailed: {reason}"
    
    update_active_trade(trade_id, updates)
    
    save_trade_log(trade_id, {
        "spot": data.get("spot"),
        "premium": data.get("premium"),
        "pnl": data.get("pnl"),
        "action": action,
        "reason": reason,
    })
    
    return jsonify({"success": True, "message": f"Action {action} applied to trade {trade_id}."})


@app.route("/api/monitor-update")
def api_monitor_update():
    """Run monitoring on all active trades and return updated status."""
    results = monitor_active_trades()
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5050)
