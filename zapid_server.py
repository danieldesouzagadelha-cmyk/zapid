import os
import requests
import json
import logging
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from groq import Groq

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# =========================
# 🔐 VARIÁVEIS
# =========================

groq_api_key = os.getenv("GROQ_API_KEY")
cmc_api_key = os.getenv("CMC_API_KEY")
news_api_key = os.getenv("NEWS_API_KEY")

twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_whatsapp = os.getenv("TWILIO_WHATSAPP_NUMBER")
meu_whatsapp = os.getenv("MY_WHATSAPP_NUMBER")

STATE_FILE = "sent_news.json"

# =========================
# 📁 CONTROLE DE NOTÍCIAS
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
# 💰 PREÇO BTC REAL
# =========================

def get_btc_price():
    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": cmc_api_key}
        params = {"symbol": "BTC", "convert": "USD"}

        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()

        price = data["data"]["BTC"]["quote"]["USD"]["price"]
        return round(price, 2)

    except Exception as e:
        logging.error(f"Erro BTC: {e}")
        return None

# =========================
# 📰 BUSCAR NOTÍCIAS POR CATEGORIA
# =========================

def get_news_by_category(category="crypto"):
    try:
        queries = {
            "crypto": "bitcoin OR cryptocurrency OR ethereum",
            "politica": "politics OR government OR election",
            "economia": "economy OR inflation OR federal reserve",
            "geopolitica": "geopolitics OR war OR global tensions"
        }

        url = "https://newsapi.org/v2/everything"
        params = {
            "q": queries.get(category, queries["crypto"]),
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 5,
            "apiKey": news_api_key
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
                    "description": article["description"] or ""
                }

        return None

    except Exception as e:
        logging.error(f"Erro NewsAPI: {e}")
        return None

# =========================
# 🤖 IA PARA ANÁLISE
# =========================

def ask_groq(prompt):
    try:
        client = Groq(api_key=groq_api_key)

        chat = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Você é um analista profissional. Nunca invente preços ou dados atuais. Use apenas para análise ou opinião."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="llama-3.1-8b-instant",
            temperature=0.6,
            max_tokens=300
        )

        return chat.choices[0].message.content

    except Exception as e:
        logging.error(f"Erro Groq: {e}")
        return None

# =========================
# 📲 ENVIAR WHATSAPP
# =========================

def send_whatsapp(message):
    try:
        client = Client(twilio_sid, twilio_token)

        msg = client.messages.create(
            body=message,
            from_=f"whatsapp:{twilio_whatsapp}",
            to=f"whatsapp:{meu_whatsapp}"
        )

        logging.info(f"Mensagem enviada SID: {msg.sid}")
        return True

    except Exception as e:
        logging.error(f"Erro WhatsApp: {e}")
        return False

# =========================
# 🚨 RADAR AUTOMÁTICO
# =========================

@app.route("/radar")
def radar():

    news = get_news_by_category("crypto")

    if not news:
        return "Sem notícias novas."

    prompt = f"""
🚨 ALERTA ZAPID

Resumo estratégico em até 280 caracteres:

Título: {news['title']}
Descrição: {news['description']}
"""

    post = ask_groq(prompt)

    if not post:
        return "Erro ao gerar post."

    post = post[:280]

    if not send_whatsapp(post):
        return "Erro ao enviar WhatsApp."

    state = load_sent_news()
    state["sent_ids"].append(news["id"])
    save_sent_news(state)

    return "Radar executado com sucesso."

# =========================
# 📲 WEBHOOK INTELIGENTE
# =========================

@app.route("/webhook", methods=["POST"])
def webhook():

    incoming_msg = request.form.get("Body", "")
    msg_lower = incoming_msg.lower()

    # 🔥 PREÇO BTC
    if any(p in msg_lower for p in ["btc", "bitcoin"]):
        price = get_btc_price()

        if price:
            resposta = f"💰 BTC agora: ${price}"
        else:
            resposta = "Erro ao buscar preço do BTC."

    # 📰 NOTÍCIAS
    elif any(p in msg_lower for p in ["noticia", "notícias", "news"]):

        if "politica" in msg_lower:
            category = "politica"
        elif "economia" in msg_lower:
            category = "economia"
        elif "geopolitica" in msg_lower:
            category = "geopolitica"
        else:
            category = "crypto"

        news = get_news_by_category(category)

        if news:
            resposta = f"📰 {news['title']}\n\n{news['description']}"
        else:
            resposta = "Não encontrei notícias recentes."

    # 🤖 CONVERSA NORMAL
    else:
        resposta = ask_groq(incoming_msg) or "Erro ao processar mensagem."

    twilio_response = MessagingResponse()
    twilio_response.message(resposta)

    return str(twilio_response)

# =========================
# 🚀 START
# =========================

if __name__ == "__main__":
    app.run()
