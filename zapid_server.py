import os
import requests
import json
from datetime import datetime
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from groq import Groq

app = Flask(__name__)

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

# =========================
# 📁 CONTROLE DE ESTADO
# =========================

STATE_FILE = "sent_news.json"

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
# 🟢 STATUS
# =========================

@app.route("/")
def home():
    return "ZapID Radar Online 🚀"

# =========================
# 💰 BTC REAL TIME
# =========================

def get_btc_price():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"X-CMC_PRO_API_KEY": cmc_api_key}
    params = {"symbol": "BTC", "convert": "USD"}

    response = requests.get(url, headers=headers, params=params)
    data = response.json()

    price = data["data"]["BTC"]["quote"]["USD"]["price"]
    return round(price, 2)

# =========================
# 🤖 GROQ IA
# =========================

def ask_groq(prompt):
    client = Groq(api_key=groq_api_key)

    chat = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "Você é um analista profissional de mercado, especialista em cripto, macroeconomia e geopolítica. Gere posts estratégicos de até 280 caracteres para Twitter."
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

# =========================
# 📰 BUSCAR NOTÍCIA
# =========================

def get_latest_news():
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": "bitcoin OR crypto OR macroeconomy OR federal reserve OR geopolitics",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 5,
        "apiKey": news_api_key
    }

    response = requests.get(url, params=params)
    articles = response.json().get("articles", [])

    if not articles:
        return None

    first = articles[0]

    return {
        "id": first["url"],
        "title": first["title"],
        "description": first["description"]
    }

# =========================
# 📲 ENVIAR WHATSAPP DIRETO
# =========================

def send_whatsapp(message):
    client = Client(twilio_sid, twilio_token)

    client.messages.create(
        body=message,
        from_=f"whatsapp:{twilio_whatsapp}",
        to=f"whatsapp:{meu_whatsapp}"
    )

# =========================
# 🚨 RADAR AUTOMÁTICO
# =========================

@app.route("/radar")
def radar():

    news = get_latest_news()

    if not news:
        return "Sem notícias relevantes."

    state = load_sent_news()

    if news["id"] in state["sent_ids"]:
        return "Notícia já enviada."

    prompt = f"""
    Baseado na notícia abaixo, gere um post de até 280 caracteres.

    Estrutura obrigatória:
    🚨 ALERTA ZAPID
    Resumo estratégico objetivo
    Hashtags relevantes

    Título: {news['title']}
    Descrição: {news['description']}
    """

    post = ask_groq(prompt)

    post = post[:280]

    send_whatsapp(post)

    state["sent_ids"].append(news["id"])
    save_sent_news(state)

    return "Radar executado com sucesso."

# =========================
# 📲 WEBHOOK TWILIO
# =========================

@app.route("/webhook", methods=["POST"])
def webhook():

    incoming_msg = request.form.get("Body")
    msg_lower = incoming_msg.lower()

    if "btc agora" in msg_lower:
        price = get_btc_price()
        resposta = f"💰 BTC agora: ${price}"
    else:
        resposta = ask_groq(incoming_msg)

    twilio_response = MessagingResponse()
    twilio_response.message(resposta)

    return str(twilio_response)

# =========================
# 🚀 START
# =========================

if __name__ == "__main__":
    app.run()
