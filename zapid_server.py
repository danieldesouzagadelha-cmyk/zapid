import os
import requests
import json
import logging
from datetime import datetime
from flask import Flask
from groq import Groq

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

STATE_FILE = "sent_news.json"

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

    response = requests.post(url, data=payload)

    if response.status_code == 200:
        logging.info("Mensagem enviada")
        return True
    else:
        logging.error(response.text)
        return False

# =========================
# BUSCAR NOTÍCIAS DE HOJE
# =========================

def get_today_news():
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")

        query = """
        bitcoin OR cryptocurrency OR ethereum OR
        inflation OR economy OR federal reserve OR
        geopolitics OR war OR government
        """

        url = "https://newsapi.org/v2/everything"

        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20,
            "apiKey": NEWS_API_KEY
        }

        response = requests.get(url, params=params, timeout=10)
        articles = response.json().get("articles", [])

        state = load_sent_news()

        for article in articles:
            if not article["publishedAt"].startswith(today):
                continue

            if article["url"] in state["sent_ids"]:
                continue

            if not article["title"] or not article["description"]:
                continue

            return {
                "id": article["url"],
                "title": article["title"],
                "description": article["description"],
                "source": article["source"]["name"],
                "date": article["publishedAt"]
            }

        return None

    except Exception as e:
        logging.error(f"Erro NewsAPI: {e}")
        return None

# =========================
# IA CONTROLADA (SEM INVENTAR)
# =========================

def generate_safe_viral_post(title, description):

    client = Groq(api_key=GROQ_API_KEY)

    prompt = f"""
Crie um post para X usando APENAS as informações abaixo.
NÃO adicione fatos novos.
NÃO extrapole.
NÃO invente contexto.

Regras:
- Comece com 🚨
- Linguagem direta
- Até 280 caracteres
- Final com pergunta estratégica
- Use hashtags relacionadas

Título: {title}
Descrição: {description}
"""

    chat = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "Você é um jornalista financeiro responsável."},
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

    news = get_today_news()

    if not news:
        return "Sem notícias novas de hoje."

    post = generate_safe_viral_post(news["title"], news["description"])

    message = f"""
🚨 ZAPID GLOBAL RADAR

{post}

📰 Fonte: {news['source']}
📅 {news['date'][:10]}
"""

    if send_telegram(message):
        state = load_sent_news()
        state["sent_ids"].append(news["id"])
        save_sent_news(state)
        return "Radar executado com sucesso."

    return "Erro ao enviar."

# =========================
# STATUS
# =========================

@app.route("/")
def home():
    return "ZapID Telegram Radar Seguro Online 🚀"

# =========================
# START
# =========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
