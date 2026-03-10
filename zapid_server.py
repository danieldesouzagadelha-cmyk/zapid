
import os
import time
import threading
from flask import Flask, jsonify, request
from config import TARGET_PROFIT, STOP_LOSS, FEE_RATE

app = Flask(__name__)

# =========================
# LÓGICA CENTRAL DO SCAN
# =========================

def run_scan():
    try:
        from market_scanner import run_radar
        from ai_predictor import enrich_signals
        from database import get_portfolio, log_signal
        from telegram_bot import send_telegram, format_signal
        from trade_monitor import update_open_trades

        update_open_trades()
        portfolio = get_portfolio()
        signals   = run_radar(portfolio)
        enriched  = enrich_signals(signals)

        notified = []
        for s in enriched:
            if s.get("type") in ["BUY", "SELL"]:
                log_signal(s)
                send_telegram(format_signal(s))
                notified.append(s)

        if not notified and signals and signals[0].get("type") == "WAIT":
            send_telegram(format_signal(signals[0]))

        print(f"✅ Scan concluído — {len(notified)} sinal(is)")
        return {"status": "ok", "signals": len(notified), "data": enriched}

    except Exception as e:
        print(f"❌ Erro no scan: {e}")
        return {"status": "error", "message": str(e)}


# =========================
# ROTAS
# =========================

@app.route("/")
def home():
    return jsonify({
        "status":    "online",
        "engine":    "ZapID Pro",
        "version":   "2.0",
        "endpoints": ["/radar", "/news", "/signals", "/performance", "/trades", "/monitor"]
    })

@app.route("/radar")
def radar():
    return jsonify(run_scan())

@app.route("/news")
def news():
    try:
        from news_radar import run_news_radar
        posted = run_news_radar()
        return jsonify({"status": "ok", "posted": posted})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/signals")
def signals():
    try:
        from database import get_recent_signals
        return jsonify(get_recent_signals(10))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/trades")
def trades():
    try:
        from database import get_open_trades
        return jsonify(get_open_trades())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/performance")
def performance():
    try:
        from database import get_performance
        return jsonify(get_performance())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/monitor")
def monitor():
    try:
        from trade_monitor import update_open_trades
        closed = update_open_trades()
        return jsonify({"closed": len(closed), "trades": closed})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/buy", methods=["POST"])
def register_buy():
    try:
        from database import log_trade
        from telegram_bot import send_telegram

        data   = request.get_json()
        symbol = data.get("symbol", "").upper()
        entry  = float(data.get("entry", 0))

        if not symbol or not entry:
            return jsonify({"error": "symbol e entry obrigatórios"}), 400

        target   = round(entry * (1 + TARGET_PROFIT + FEE_RATE * 2), 6)
        stop     = round(entry * (1 - STOP_LOSS), 6)
        trade_id = log_trade(symbol, entry, target, stop)

        send_telegram(
            f"📥 <b>COMPRA REGISTRADA</b>\n\n"
            f"🪙 {symbol}\n"
            f"💲 Entrada: ${entry:,.4f}\n"
            f"🎯 Target:  ${target:,.4f}\n"
            f"🛡️ Stop:    ${stop:,.4f}\n"
            f"🆔 Trade ID: {trade_id}"
        )
        return jsonify({"trade_id": trade_id, "symbol": symbol, "entry": entry, "target": target, "stop": stop})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# THREADS
# =========================

def auto_radar():
    time.sleep(30)
    while True:
        print("⏰ Auto-radar de mercado disparado!")
        run_scan()
        time.sleep(3600)

def auto_news():
    time.sleep(1800)
    while True:
        print("📰 Auto-radar de notícias disparado!")
        try:
            from news_radar import run_news_radar
            run_news_radar()
        except Exception as e:
            print(f"❌ Erro auto_news: {e}")
        time.sleep(3600)

def keep_alive():
    time.sleep(120)
    while True:
        try:
            import requests as req
            port = os.environ.get("PORT", 10000)
            req.get(f"http://localhost:{port}/", timeout=5)
            print("💓 keep-alive ping")
        except:
            pass
        time.sleep(600)


# =========================
# STARTUP — roda ao importar
# =========================

def startup():
    try:
        from database import setup_db
        setup_db()
    except Exception as e:
        print(f"⚠️ DB setup error: {e}")

    try:
        from telegram_bot import send_telegram
        send_telegram(
            "🚀 <b>ZapID Pro está online!</b>\n"
            "📊 Radar de mercado: a cada 1h\n"
            "📰 Radar de notícias: a cada 1h\n"
        )
    except Exception as e:
        print(f"⚠️ Telegram error: {e}")

    threading.Thread(target=auto_radar, daemon=True).start()
    threading.Thread(target=auto_news,  daemon=True).start()
    threading.Thread(target=keep_alive, daemon=True).start()
    print("🟢 Threads iniciadas")

# chama startup direto na importação pelo gunicorn
startup()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
