import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone

DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# =========================
# SETUP
# =========================

def setup_db():
    with get_conn() as conn:
        with conn.cursor() as cur:

            # tabela de sinais (histórico completo)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id          SERIAL PRIMARY KEY,
                    created_at  TIMESTAMPTZ DEFAULT NOW(),
                    symbol      TEXT NOT NULL,
                    signal_type TEXT NOT NULL,       -- BUY / SELL / WAIT
                    price       NUMERIC,
                    score       INTEGER,
                    rsi         NUMERIC,
                    adx         NUMERIC,
                    entry       NUMERIC,
                    target      NUMERIC,
                    stop        NUMERIC,
                    daily_trend TEXT,
                    indicators  TEXT,               -- JSON array
                    ai_prediction TEXT,
                    outcome     TEXT DEFAULT 'OPEN', -- OPEN / WIN / LOSS / MANUAL
                    profit_pct  NUMERIC             -- preenchido quando fecha
                )
            """)

            # tabela de trades abertos
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id           SERIAL PRIMARY KEY,
                    created_at   TIMESTAMPTZ DEFAULT NOW(),
                    symbol       TEXT NOT NULL,
                    entry_price  NUMERIC NOT NULL,
                    target_price NUMERIC NOT NULL,
                    stop_price   NUMERIC NOT NULL,
                    signal_id    INTEGER REFERENCES signals(id),
                    status       TEXT DEFAULT 'OPEN'  -- OPEN / WIN / LOSS
                )
            """)

        conn.commit()
    print("✅ Banco de dados pronto")


# =========================
# SINAIS
# =========================

def log_signal(signal):
    """Salva sinal no histórico"""
    import json
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO signals
                    (symbol, signal_type, price, score, rsi, adx,
                     entry, target, stop, daily_trend, indicators, ai_prediction)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (
                signal.get("asset", ""),
                signal.get("type", ""),
                signal.get("price"),
                signal.get("score"),
                signal.get("rsi"),
                signal.get("adx"),
                signal.get("entry"),
                signal.get("target"),
                signal.get("stop"),
                signal.get("daily_trend"),
                json.dumps(signal.get("indicators", [])),
                signal.get("ai_prediction")
            ))
            row = cur.fetchone()
        conn.commit()
    return row["id"]


def get_recent_signals(limit=10):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, created_at, symbol, signal_type, price,
                       score, rsi, adx, entry, target, stop,
                       outcome, profit_pct
                FROM signals
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            return [dict(r) for r in cur.fetchall()]


def update_signal_outcome(signal_id, outcome, profit_pct):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE signals
                SET outcome = %s, profit_pct = %s
                WHERE id = %s
            """, (outcome, profit_pct, signal_id))
        conn.commit()


# =========================
# TRADES
# =========================

def log_trade(symbol, entry, target, stop, signal_id=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO trades (symbol, entry_price, target_price, stop_price, signal_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (symbol, entry, target, stop, signal_id))
            row = cur.fetchone()
        conn.commit()
    return row["id"]


def get_open_trades():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM trades WHERE status = 'OPEN'
                ORDER BY created_at DESC
            """)
            return [dict(r) for r in cur.fetchall()]


def close_trade(trade_id, status, profit_pct=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE trades SET status = %s WHERE id = %s
                RETURNING signal_id
            """, (status, trade_id))
            row = cur.fetchone()
        conn.commit()

    # atualiza o sinal vinculado
    if row and row["signal_id"] and profit_pct is not None:
        update_signal_outcome(row["signal_id"], status, profit_pct)


def get_portfolio():
    trades = get_open_trades()
    return {t["symbol"] for t in trades}


# =========================
# PERFORMANCE 30 DIAS
# =========================

def get_performance():
    with get_conn() as conn:
        with conn.cursor() as cur:

            # sinais dos últimos 30 dias
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE outcome = 'WIN')  AS wins,
                    COUNT(*) FILTER (WHERE outcome = 'LOSS') AS losses,
                    COUNT(*) FILTER (WHERE outcome = 'OPEN') AS open_signals,
                    AVG(profit_pct) FILTER (WHERE outcome IN ('WIN','LOSS')) AS avg_profit,
                    SUM(profit_pct) FILTER (WHERE outcome IN ('WIN','LOSS')) AS total_profit
                FROM signals
                WHERE signal_type = 'BUY'
                  AND created_at >= NOW() - INTERVAL '30 days'
            """)
            row = dict(cur.fetchone())

            # trades abertos
            cur.execute("SELECT COUNT(*) AS cnt FROM trades WHERE status = 'OPEN'")
            row["open_trades"] = cur.fetchone()["cnt"]

        wins   = row.get("wins") or 0
        losses = row.get("losses") or 0
        total  = wins + losses
        row["winrate"] = (wins / total * 100) if total > 0 else 0.0

        return row
