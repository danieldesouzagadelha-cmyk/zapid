import os
import time
import threading
from flask import Flask, jsonify, request
from config import TARGET_PROFIT, STOP_LOSS, FEE_RATE

app = Flask(__name__)

# =========================
# INICIALIZAÇÃO
# =========================

def startup():
    """Inicializa banco e bot ao subir o servidor"""
    try:
        from database import setup_db
        setup_db()
    except Exception as e:
        print(f"⚠️ DB setup error: {e}")

    try:
        from telegram_bot import start_bot, send_telegram
        start_bot()
        send_telegram("🚀 <b>ZapID Pro está online!</b>\nUse /radar para escanear o mercado.")
    except Exception as e:
        print(f"⚠️ Telegram start error: {e}")


# =========================
# ROTAS
# =========================

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "engine": "ZapID Pro",
        "version": "2.0",
        "endpoints": ["/radar", "/signals", "/performance", "/trades", "/monitor"]
    })


@app.route("/radar")
def radar():
    """
    Rota principal — chamada pelo GitHub Action a cada hora.
    Escaneia mercado, enriquece com Grok e notifica no Telegram.
    """
    print("🛰️ /radar chamado")

    try:
        from market_scanner import run_radar
        from ai_predictor import enrich_signals
        from database import get_portfolio, log_signal
        from telegram_bot import send_telegram, format_signal
        from trade_monitor import update_open_trades

        # 1. monitorar trades abertos primeiro
        update_open_trades()

        # 2. pegar portfolio atual do banco
        portfolio = get_portfolio()

        # 3. rodar scanner
        signals = run_radar(portfolio)

        # 4. enriquecer com Grok AI
        enriched = enrich_signals(signals)

        # 5. notificar e salvar sinais relevantes
        notified = []

        for s in enriched:
            if s.get("type") in ["BUY", "SELL"]:

                # salvar no banco
                log_signal(
                    signal_type=s["type"],
                    asset=s.get("asset", ""),
                    price=s.get("price", 0),
                    score=s.get("score"),
                    rsi=s.get("rsi"),
                    prediction=s.get("ai_prediction")
                )

                # enviar para o Telegram
                send_telegram(format_signal(s))
                notified.append(s)

        if not notified:
            # só notifica WAIT uma vez por hora para não encher
            if signals and signals[0].get("type") == "WAIT":
                send_telegram(format_signal(signals[0]))

        return jsonify({
            "status": "ok",
            "signals": len(notified),
            "data": enriched
        })

    except Exception as e:
        print(f"❌ Erro /radar: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/signals")
def signals():
    """Últimos sinais do banco"""
    try:
        from database import get_recent_signals
        return jsonify(get_recent_signals(10))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/trades")
def trades():
    """Trades abertos"""
    try:
        from database import get_open_trades
        return jsonify(get_open_trades())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/performance")
def performance():
    """Estatísticas gerais"""
    try:
        from database import get_performance
        return jsonify(get_performance())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/monitor")
def monitor():
    """Atualiza trades abertos manualmente"""
    try:
        from trade_monitor import update_open_trades
        closed = update_open_trades()
        return jsonify({"closed": len(closed), "trades": closed})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/buy", methods=["POST"])
def register_buy():
    """
    Registra uma compra manualmente.
    Body JSON: {"symbol": "BITCOIN", "entry": 95000}
    """
    try:
        from database import log_trade
        from telegram_bot import send_telegram
        from config import TARGET_PROFIT, STOP_LOSS, FEE_RATE

        data   = request.get_json()
        symbol = data.get("symbol", "").upper()
        entry  = float(data.get("entry", 0))

        if not symbol or not entry:
            return jsonify({"error": "symbol e entry são obrigatórios"}), 400

        target = round(entry * (1 + TARGET_PROFIT + FEE_RATE * 2), 6)
        stop   = round(entry * (1 - STOP_LOSS), 6)

        trade_id = log_trade(symbol, entry, target, stop)

        send_telegram(
            f"📥 <b>COMPRA REGISTRADA</b>\n\n"
            f"🪙 {symbol}\n"
            f"💲 Entrada: ${entry:,.4f}\n"
            f"🎯 Target:  ${target:,.4f} (+{TARGET_PROFIT*100:.0f}%)\n"
            f"🛡️ Stop:    ${stop:,.4f} (-{STOP_LOSS*100:.0f}%)\n"
            f"🆔 Trade ID: {trade_id}"
        )

        return jsonify({
            "trade_id": trade_id,
            "symbol": symbol,
            "entry": entry,
            "target": target,
            "stop": stop
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# KEEP-ALIVE (Render free)
# =========================

def keep_alive():
    """
    Render free dorme após 15min de inatividade.
    Esta thread faz uma request interna a cada 10min para manter vivo.
    """
    time.sleep(60)  # aguarda inicialização completa
    while True:
        try:
            import requests as req
            port = os.environ.get("PORT", 10000)
            req.get(f"http://localhost:{port}/", timeout=5)
            print("💓 keep-alive ping")
        except:
            pass
        time.sleep(600)  # 10 minutos


# =========================
# START
# =========================

startup()
threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
