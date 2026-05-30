import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "trades.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            capital REAL DEFAULT 100000,
            max_risk_percent REAL DEFAULT 2.0,
            max_loss_per_day REAL DEFAULT 5000,
            preferred_instrument TEXT DEFAULT 'futures',
            enable_news_check INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)



    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            instrument_type TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry REAL NOT NULL,
            stop_loss REAL NOT NULL,
            target1 REAL NOT NULL,
            target2 REAL,
            quantity INTEGER NOT NULL,
            risk_reward TEXT,
            confidence_score REAL,
            confidence_label TEXT,
            market_trend TEXT,
            pcr REAL,
            max_pain REAL,
            atm_strike REAL,
            spot_price REAL,
            futures_price REAL,
            days_to_expiry INTEGER,
            vix REAL,
            reasons TEXT,
            risk_factors TEXT,
            invalidation_scenarios TEXT,
            status TEXT DEFAULT 'open',
            pnl REAL,
            exited_at TIMESTAMP,
            exit_reason TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS iv_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atm_ce_iv REAL,
            atm_pe_iv REAL,
            avg_iv REAL,
            vix REAL,
            days_to_expiry INTEGER
        )
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO settings (id, capital, max_risk_percent)
        VALUES (1, 100000, 2.0)
    """)

    conn.commit()
    conn.close()


def get_settings():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM settings WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"capital": 100000, "max_risk_percent": 2.0}


def update_settings(data):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE settings SET
            capital = ?,
            max_risk_percent = ?,
            max_loss_per_day = ?,
            preferred_instrument = ?,
            enable_news_check = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
    """, (
        data.get("capital", 100000),
        data.get("max_risk_percent", 2.0),
        data.get("max_loss_per_day", 5000),
        data.get("preferred_instrument", "futures"),
        1 if data.get("enable_news_check", True) else 0
    ))
    conn.commit()
    conn.close()


def save_trade(trade_data):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO trades (
            timestamp, instrument_type, direction, entry, stop_loss,
            target1, target2, quantity, risk_reward, confidence_score,
            confidence_label, market_trend, pcr, max_pain, atm_strike,
            spot_price, futures_price, days_to_expiry, vix,
            reasons, risk_factors, invalidation_scenarios, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        trade_data.get("timestamp", datetime.now().isoformat()),
        trade_data["instrument_type"],
        trade_data["direction"],
        trade_data["entry"],
        trade_data["stop_loss"],
        trade_data["target1"],
        trade_data.get("target2"),
        trade_data["quantity"],
        trade_data.get("risk_reward"),
        trade_data.get("confidence_score"),
        trade_data.get("confidence_label"),
        trade_data.get("market_trend"),
        trade_data.get("pcr"),
        trade_data.get("max_pain"),
        trade_data.get("atm_strike"),
        trade_data.get("spot"),
        trade_data.get("futures"),
        trade_data.get("days_to_expiry"),
        trade_data.get("vix"),
        json.dumps(trade_data.get("reasons", [])),
        json.dumps(trade_data.get("risk_factors", [])),
        json.dumps(trade_data.get("invalidation_scenarios", [])),
        "open"
    ))
    conn.commit()
    conn.close()


def get_trades(limit=100):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_trade_status(trade_id, status, pnl=None, exit_reason=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE trades SET status = ?, pnl = ?, exited_at = CURRENT_TIMESTAMP, exit_reason = ?
        WHERE id = ?
    """, (status, pnl, exit_reason, trade_id))
    conn.commit()
    conn.close()


def save_iv_history(atm_ce_iv, atm_pe_iv, avg_iv, vix, days_to_expiry):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO iv_history (atm_ce_iv, atm_pe_iv, avg_iv, vix, days_to_expiry)
        VALUES (?, ?, ?, ?, ?)
    """, (atm_ce_iv, atm_pe_iv, avg_iv, vix, days_to_expiry))
    conn.commit()
    conn.close()


def get_iv_history(limit=252):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM iv_history ORDER BY timestamp DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
