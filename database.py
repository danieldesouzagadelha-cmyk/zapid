import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DATABASE_URL

# =========================
# CONEXÃO
# =========================

def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


# =========================
# SETUP — criar tabelas
# =========================

def setup_db():
    conn = get_conn()
    cur = conn.cursor()

    # tabela de trades
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT NOW(),
            symbol TEXT NOT NULL,
            entry_price FLOAT NOT NULL,
            target_price FLOAT NOT NULL,
            stop_price FLOAT NOT NULL,
            current_price FLOAT,
            result TEXT DEFAULT 'OPEN',
            profit_pct FLOAT,
            closed_at TIMESTAMP
        )
    """)

    # tabela de sinais do radar
    cur.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT NOW(),
            signal_type TEXT NOT NULL,
            asset TEXT NOT NULL,
            price FLOAT NOT NULL,
            score INT,
            rsi FLOAT,
            prediction TEXT
        )
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Banco de dados pronto")


# =========================
# TRADES
# =========================

def log_trade(symbol, entry, target, stop):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO trades (symbol, entry_price, target_price, stop_price, current_price, result)
        VALUES (%s, %s, %s, %s, %s, 'OPEN')
        RETURNING id
    """, (symbol, entry, target, stop, entry))

    trade_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return trade_id


def get_open_trades():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM trades WHERE result = 'OPEN' ORDER BY created_at DESC")
    rows = cur.fetchall()

    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def close_trade(trade_id, current_price, result):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT entry_price FROM trades WHERE id = %s", (trade_id,))
    row = cur.fetchone()

    if not row:
        return

    entry = row["entry_price"]
    profit_pct = round(((current_price - entry) / entry) * 100, 2)

    cur.execute("""
        UPDATE trades
        SET result = %s,
            current_price = %s,
            profit_pct = %s,
            closed_at = NOW()
        WHERE id = %s
    """, (result, current_price, profit_pct, trade_id))

    conn.commit()
    cur.close()
    conn.close()


def get_portfolio():
    """Retorna dict {symbol: entry_price} de trades abertos"""
    trades = get_open_trades()
    return {t["symbol"].lower(): t["entry_price"] for t in trades}


# =========================
# SINAIS
# =========================

def log_signal(signal_type, asset, price, score=None, rsi=None, prediction=None):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO signals (signal_type, asset, price, score, rsi, prediction)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (signal_type, asset, price, score, rsi, prediction))

    conn.commit()
    cur.close()
    conn.close()


def get_recent_signals(limit=10):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM signals
        ORDER BY created_at DESC
        LIMIT %s
    """, (limit,))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


# =========================
# PERFORMANCE
# =========================

def get_performance():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE result = 'WIN') AS wins,
            COUNT(*) FILTER (WHERE result = 'LOSS') AS losses,
            COUNT(*) FILTER (WHERE result = 'OPEN') AS open_trades,
            ROUND(AVG(profit_pct) FILTER (WHERE result IN ('WIN','LOSS'))::numeric, 2) AS avg_profit,
            ROUND(SUM(profit_pct) FILTER (WHERE result IN ('WIN','LOSS'))::numeric, 2) AS total_profit
        FROM trades
    """)

    row = cur.fetchone()
    cur.close()
    conn.close()

    data = dict(row)
    total = (data["wins"] or 0) + (data["losses"] or 0)
    data["total_closed"] = total
    data["winrate"] = round((data["wins"] / total * 100), 2) if total > 0 else 0

    return data
