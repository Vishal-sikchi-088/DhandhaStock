"""
Nifty 50 Options & Futures Analysis Dashboard
Flask backend with SQLite storage.
"""

import os
from datetime import datetime
from flask import Flask, render_template, jsonify, request

from services.database import init_db, get_settings, update_settings, save_trade, get_trades
from services.analysis import analyze_option_chain, get_trend_analysis
from services.ai_reasoning import generate_trade_idea
from services.risk_manager import validate_trade
from services.market_data import get_market_summary, get_news_headlines
from services.premarket_data import get_all_premarket_data
from services.chart_analysis import analyze_chart
from services.news_ai import generate_market_news_context, analyze_news_sentiment, get_ai_market_narrative

app = Flask(__name__)
app.secret_key = os.urandom(24)

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
    # Convert any remaining non-serializable objects
    return jsonify(idea)


@app.route("/api/premarket")
def api_premarket():
    return jsonify(get_all_premarket_data())


@app.route("/api/chart-analysis")
def api_chart_analysis():
    premarket = get_all_premarket_data()
    historical = premarket.get("historical_daily")
    historical_60m = premarket.get("historical_60m")
    historical_15m = premarket.get("historical_15m")
    if historical is not None:
        return jsonify(analyze_chart(historical, historical_60m, historical_15m))
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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5050)
