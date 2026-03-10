import os
import requests
import json
import logging
import feedparser
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

    requests.post(url, data=payload)

# =========================
# CONTROLE DE NOTÍCIAS
# =========================

def load_sent_news():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"sent_ids": []}

def save_sent_news(data):
    with open(STATE_FILE, "w") as f:
        json.dump(data, f)

# =========================
# BUSCAR RSS
# =========================

def get_recent_news():

    state = load_sent_news()

    now = datetime.utcnow()
    day_ago = now - timedelta(hours=24)

    for feed_url in RSS_FEEDS:

        feed = feedparser.parse(feed_url)

        for entry in feed.entries:

            if not hasattr(entry, "published_parsed"):
                continue

            published = datetime(*entry.published_parsed[:6])

            if published < day_ago:
                continue

            if entry.link in state["sent_ids"]:
                continue

            return {
                "id": entry.link,
                "title": entry.title,
                "description": entry.summary if hasattr(entry, "summary") else "",
                "source": feed.feed.title,
                "date": published.strftime("%Y-%m-%d")
            }

    return None

# =========================
# IA EXPLICA NOTÍCIA
# =========================

def generate_detailed_news(title, description):

    client = Groq(api_key=GROQ_API_KEY)

    prompt = f"""
Explique a notícia abaixo em 3 frases claras.

Título: {title}

Descrição: {description}
"""

    chat = client.chat.completions.create(

        messages=[
            {"role": "system", "content": "Você é analista financeiro."},
            {"role": "user", "content": prompt}
        ],

        model="llama-3.1-8b-instant",
        temperature=0.3,
        max_tokens=200
    )

    return chat.choices[0].message.content

# =========================
# IA POST PARA X
# =========================

def generate_x_post(title, description):

    client = Groq(api_key=GROQ_API_KEY)

    prompt = f"""
Crie um post para X com até 280 caracteres.

Comece com 🚨
Inclua hashtags.

Título: {title}

Descrição: {description}
"""

    chat = client.chat.completions.create(

        messages=[
            {"role": "system", "content": "Você é analista financeiro."},
            {"role": "user", "content": prompt}
        ],

        model="llama-3.1-8b-instant",
        temperature=0.4,
        max_tokens=120
    )

    return chat.choices[0].message.content

# =========================
# RADAR DE NOTÍCIAS
# =========================

@app.route("/radar")
def radar():

    news = get_recent_news()

    if not news:
        return "Sem notícias novas."

    detailed = generate_detailed_news(news["title"], news["description"])

    x_post = generate_x_post(news["title"], news["description"])

    message = f"""
📰 ZAPID GLOBAL RADAR

{detailed}

✂️ Post para X:

{x_post}

Fonte: {news['source']}
Data: {news['date']}
"""

    send_telegram(message)

    state = load_sent_news()

    state["sent_ids"].append(news["id"])

    save_sent_news(state)

    return "Radar executado."

# =========================
# RADAR CRYPTO
# =========================

@app.route("/crypto_radar")
def crypto_radar():

    run_radar()

    return "Crypto radar executado."

# =========================
# HOME
# =========================

@app.route("/")
def home():
    return "ZapID Global Radar Online 🚀"

# =========================
# RUN
# =========================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(host="0.0.0.0", port=port)
