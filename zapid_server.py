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
# 🔐 VARIÁVEIS DE AMBIENTE
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
        logging.error(f"Erro ao buscar BTC: {e}")
        return None

# =========================
# 🤖 GROQ IA
# =========================

def ask_groq(prompt):
    try:
        client = Groq(api_key=groq_api_key)

        chat = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Você é um analista profissional de mercado. Nunca invente preços de ativos financeiros. Se não tiver dados reais, informe que precisa consultar API."
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
        logging.error(f"Erro no Groq: {e}")
        return None

# =========================
# 📰 BUSCAR NOTÍCIA
# =========================

def get_latest_news():
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": "bitcoin OR crypto OR macroeconomy OR federal reserve OR geopolitics",
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
        logging.error(f"Erro ao buscar notícia: {e}")
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
        logging.error(f"Erro ao enviar WhatsApp: {e}")
        return False

# =========================
# 🚨 RADAR
# =========================

@app.route("/radar")
def radar():

    news = get_latest_news()

    if not news:
        return "Sem notícias novas."

    prompt = f"""
🚨 ALERTA ZAPID

Resumo estratégico da notícia abaixo em até 280 caracteres.

Título: {news['title']}
Descrição: {news['description']}
"""

    post = ask_groq(prompt)

    if not post:
        return "Erro ao gerar post."

    post = post[:280]

    success = send_whatsapp(post)

    if not success:
        return "Erro ao enviar WhatsApp."

    state = load_sent_news()
    state["sent_ids"].append(news["id"])
    save_sent_news(state)

    return "Radar executado com sucesso."

# =========================
# 📲 WEBHOOK TWILIO
# =========================

@app.route("/webhook", methods=["POST"])
def webhook():

    incoming_msg = request.form.get("Body", "")
    msg_lower = incoming_msg.lower()

    # 🔥 DETECÇÃO INTELIGENTE DE BTC
    if any(p in msg_lower for p in ["btc", "bitcoin"]):
        price = get_btc_price()

        if price:
            resposta = f"💰 BTC agora: ${price}"
        else:
            resposta = "Erro ao buscar preço do BTC."

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
