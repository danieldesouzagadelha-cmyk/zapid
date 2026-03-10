import os
import requests
import json
import logging
import feedparser
import threading
import time

from datetime import datetime, timedelta
from flask import Flask
from groq import Groq

from market_scanner import run_radar

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

STATE_FILE = "sent_news.json"

RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.coindesk.com/arc/outboundfeeds/rss/"
]

# =========================
# TELEGRAM
# =========================

def send_telegram(message):

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        logging.error(f"Erro Telegram: {e}")

# =========================
# RADAR CRYPTO
# =========================

def execute_crypto_radar():

    logging.info("📡 Executando radar cripto...")

    trades = run_radar()

    if not trades:
        logging.info("Nenhuma oportunidade encontrada.")
        return

    for trade in trades:

        message = f"""
🚨 ZAPID AI SPOT TRADE

Asset: {trade['asset']}

Entry: {trade['entry']}
Target: {trade['target']}
Stop: {trade['stop']}

Expected Profit: ~6%

Confidence: {trade['confidence']}%
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
            logging.error(f"Erro radar: {e}")

        # espera 15 minutos
        time.sleep(900)

# =========================
# START LOOP
# =========================

def start_background_radar():

    thread = threading.Thread(target=radar_loop)
    thread.daemon = True
    thread.start()

# =========================
# ROTAS
# =========================

@app.route("/")
def home():

    return "ZapID Global Radar Online 🚀"

@app.route("/crypto_radar")
def manual_radar():

    execute_crypto_radar()

    return "Radar executado manualmente."

# =========================
# RUN
# =========================

if __name__ == "__main__":

    start_background_radar()

    port = int(os.environ.get("PORT", 10000))

    app.run(host="0.0.0.0", port=port)
