import os
import requests
import json
import logging
import feedparser
from datetime import datetime, timedelta
from flask import Flask
from groq import Groq

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
# CONTROLE DE ESTADO
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
# BUSCAR RSS
# =========================

def get_recent_news():
    state = load_sent_news()
    now = datetime.utcnow()
    twenty_four_hours_ago = now - timedelta(hours=24)

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            if not hasattr(entry, "published_parsed"):
                continue

            published_at = datetime(*entry.published_parsed[:6])

            if published_at < twenty_four_hours_ago:
                continue

            if entry.link in state["sent_ids"]:
                continue

            return {
                "id": entry.link,
                "title": entry.title,
                "description": entry.summary if hasattr(entry, "summary") else "",
                "source": feed.feed.title,
                "date": published_at.strftime("%Y-%m-%d")
            }

    return None

# =========================
# IA VIRAL CONTROLADA
# =========================

def generate_post(title, description):

    client = Groq(api_key=GROQ_API_KEY)

    prompt = f"""
Crie um post para X usando APENAS as informações abaixo.
Não invente fatos.

Regras:
- Comece com 🚨
- Linguagem direta
- Até 280 caracteres
- Final com pergunta estratégica
- Inclua hashtags relevantes

Título: {title}
Descrição: {description}
"""

    chat = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "Você é um analista financeiro profissional."},
            {"role": "user", "content": prompt}
        ],
        model="llama-3.1-8b-instant",
        temperature=0.4,
        max_tokens=280
    )

    return chat.choices[0].message.content

# =========================
# RADAR
# =========================

@app.route("/radar")
def radar():

    news = get_recent_news()

    if not news:
        return "Sem notícias recentes nas últimas 24h."

    post = generate_post(news["title"], news["description"])

    message = f"""
🚨 ZAPID GLOBAL RADAR

{post}

📰 Fonte: {news['source']}
📅 {news['date']}
"""

    send_telegram(message)

    state = load_sent_news()
    state["sent_ids"].append(news["id"])
    save_sent_news(state)

    return "Radar executado com sucesso."

@app.route("/")
def home():
    return "ZapID RSS Radar Online 🚀"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
