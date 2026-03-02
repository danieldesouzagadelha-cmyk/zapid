import os
import requests
import json
import logging
from flask import Flask
from groq import Groq

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# =========================
# 🔐 VARIÁVEIS
# =========================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

STATE_FILE = "sent_news.json"

# =========================
# 📁 CONTROLE DE ESTADO
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
# 📲 TELEGRAM
# =========================

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }

        response = requests.post(url, data=payload)

        if response.status_code == 200:
            logging.info("Mensagem enviada no Telegram")
            return True
        else:
            logging.error(response.text)
            return False

    except Exception as e:
        logging.error(f"Erro Telegram: {e}")
        return False

# =========================
# 📰 BUSCAR NOTÍCIAS
# =========================

def get_news():
    try:
        query = """
        bitcoin OR cryptocurrency OR ethereum OR
        economy OR inflation OR federal reserve OR
        government OR politics OR
        war OR geopolitics OR global conflict
        """

        url = "https://newsapi.org/v2/everything"

        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 10,
            "apiKey": NEWS_API_KEY
        }

        response = requests.get(url, params=params, timeout=10)
        articles = response.json().get("articles", [])

        if not articles:
            return None

        state = load_sent_news()

        for article in articles:
            if article["url"] not in state["sent_ids"]:
                return {
                    "id": article["url"],
                    "title": article["title"] or "",
                    "description": article["description"] or "",
                    "source": article["source"]["name"]
                }

        return None

    except Exception as e:
        logging.error(f"Erro NewsAPI: {e}")
        return None

# =========================
# 🤖 IA RESUMO
# =========================

def summarize_with_ai(title, description):

    try:
        client = Groq(api_key=GROQ_API_KEY)

        prompt = f"""
        Gere um resumo estratégico em até 250 caracteres.

        Título: {title}
        Descrição: {description}

        Use tom profissional e inclua hashtags relevantes.
        """

        chat = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Você é um analista geopolítico e financeiro."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.6,
            max_tokens=250
        )

        return chat.choices[0].message.content

    except Exception as e:
        logging.error(f"Erro Groq: {e}")
        return None

# =========================
# 🚨 RADAR
# =========================

@app.route("/radar")
def radar():

    news = get_news()

    if not news:
        return "Sem notícias novas."

    summary = summarize_with_ai(news["title"], news["description"])

    if not summary:
        return "Erro ao gerar resumo."

    message = f"""
🚨 *ZAPID GLOBAL RADAR*

{summary}

📰 Fonte: {news['source']}
"""

    if send_telegram(message):

        state = load_sent_news()
        state["sent_ids"].append(news["id"])
        save_sent_news(state)

        return "Radar executado com sucesso."

    else:
        return "Erro ao enviar Telegram."

# =========================
# 🟢 STATUS
# =========================

@app.route("/")
def home():
    return "ZapID Telegram Radar Online 🚀"

# =========================
# 🚀 START
# =========================

if __name__ == "__main__":
    app.run()
