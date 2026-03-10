import os
import requests
import logging
import threading
import time

from flask import Flask
from market_scanner import run_radar

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(message):

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    requests.post(url, data=payload)


# =========================
# EXECUTAR RADAR
# =========================

def execute_crypto_radar():

    logging.info("📡 Executando radar cripto...")

    signals = run_radar()

    if not signals:
        return

    for s in signals:

        if s["type"] == "BUY":

            message = f"""
🟢 ZAPID AI SIGNAL

AÇÃO: COMPRAR

Moeda: {s['asset']}

Preço: {s['price']}

Alvo: {s['target']} (+6%)

Score técnico: {s['score']}
"""

        else:

            message = f"""
🔴 ZAPID AI SIGNAL

AÇÃO: VENDER

Moeda: {s['asset']}

Preço atual: {s['price']}

Lucro aproximado: +6%
"""

        send_telegram(message)


# =========================
# LOOP AUTOMÁTICO
# =========================

def radar_loop():

    while True:

        try:
            execute_crypto_radar()

        except Exception as e:
            logging.error(e)

        time.sleep(900)


def start_background_radar():

    thread = threading.Thread(target=radar_loop)
    thread.daemon = True
    thread.start()


@app.route("/")
def home():
    return "ZapID Global Radar Online 🚀"


@app.route("/crypto_radar")
def manual_radar():

    execute_crypto_radar()

    return "Radar executado."


if __name__ == "__main__":

    start_background_radar()

    port = int(os.environ.get("PORT", 10000))

    app.run(host="0.0.0.0", port=port)
