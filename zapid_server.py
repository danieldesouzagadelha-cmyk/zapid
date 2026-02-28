from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import requests
import os
import time
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from groq import Groq

app = Flask(__name__)

# ==============================
# CONFIG
# ==============================
account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
twilio_number = os.environ.get("TWILIO_WHATSAPP_NUMBER")
cmc_api_key = os.environ.get("CMC_API_KEY")
groq_api_key = os.environ.get("GROQ_API_KEY")

client = Client(account_sid, auth_token)

# ==============================
# SEU NÚMERO (coloque o seu)
# ==============================
MEU_NUMERO = "whatsapp:+5585SEUNUMERO"

# ==============================
# CACHE DE PREÇO
# ==============================
price_cache = {}
CACHE_TIME = 30

def get_price(symbol):
    now = time.time()

    if symbol in price_cache:
        data, timestamp = price_cache[symbol]
        if now - timestamp < CACHE_TIME:
            return data

    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": cmc_api_key}
        params = {"symbol": symbol, "convert": "USD"}

        response = requests.get(url, headers=headers, params=params, timeout=5)
        data_json = response.json()["data"][symbol]["quote"]["USD"]

        data = {
            "price": float(data_json["price"]),
            "change": float(data_json["percent_change_24h"])
        }

        price_cache[symbol] = (data, now)
        return data

    except:
        return {"price": 0, "change": 0}

# ==============================
# ALERTA AUTOMÁTICO (queda 5%)
# ==============================
def check_market_drop():
    moedas = ["BTC", "ETH", "SOL", "BNB", "XRP"]

    for symbol in moedas:
        data = get_price(symbol)

        if data["change"] <= -5:
            client.messages.create(
                body=f"📉 ALERTA!\n{symbol} caiu {data['change']:.2f}%\nPreço: ${data['price']:,.2f}",
                from_=twilio_number,
                to=MEU_NUMERO
            )

# ==============================
# LEMBRETE
# ==============================
def agendar_lembrete(numero, hora, mensagem):
    hora_obj = datetime.strptime(hora, "%H:%M")

    scheduler.add_job(
        enviar_lembrete,
        'cron',
        hour=hora_obj.hour,
        minute=hora_obj.minute,
        args=[numero, mensagem]
    )

def enviar_lembrete(numero, mensagem):
    client.messages.create(
        body=f"⏰ LEMBRETE:\n{mensagem}",
        from_=twilio_number,
        to=numero
    )

# ==============================
# IA GROQ (CORRIGIDO)
# ==============================
def ask_groq(question):
    try:
        if not groq_api_key:
            return "GROQ_API_KEY não configurada."

        client_groq = Groq(api_key=groq_api_key)

        chat_completion = client_groq.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Você é especialista em criptomoedas. Responda de forma clara e direta."
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            model="llama3-8b-8192",
            temperature=0.5,
            max_tokens=300,
        )

        return chat_completion.choices[0].message.content

    except Exception as e:
        print("ERRO GROQ:", e)
        return "Erro ao consultar IA."

# ==============================
# SCHEDULER
# ==============================
scheduler = BackgroundScheduler()
scheduler.add_job(check_market_drop, "interval", minutes=10)
scheduler.start()

# ==============================
# WEBHOOK
# ==============================
@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.form.get("Body", "")
    sender = request.form.get("From")

    resp = MessagingResponse()
    msg = incoming_msg.lower().strip()

    moedas_map = {
        "btc": "BTC",
        "bitcoin": "BTC",
        "eth": "ETH",
        "ethereum": "ETH",
        "sol": "SOL",
        "solana": "SOL",
        "bnb": "BNB",
        "xrp": "XRP"
    }

    # ==========================
    # LEMBRETE
    # ==========================
    if msg.startswith("lembrete"):
        try:
            partes = msg.split(" ", 2)
            hora = partes[1]
            mensagem = partes[2]
            agendar_lembrete(sender, hora, mensagem)
            resp.message("⏰ Lembrete agendado!")
        except:
            resp.message("Use: lembrete 21:00 estudar cripto")
        return str(resp)

    palavras = msg.split()

    # ==========================
    # PREÇO (mensagem curta)
    # ==========================
    if len(palavras) <= 2:
        for palavra, simbolo in moedas_map.items():
            if palavra in msg:
                data = get_price(simbolo)

                resp.message(
                    f"💰 {simbolo}\n"
                    f"Preço: ${data['price']:,.2f}\n"
                    f"24h: {data['change']:.2f}%"
                )
                return str(resp)

    # ==========================
    # IA GROQ
    # ==========================
    resposta = ask_groq(incoming_msg)
    resp.message(resposta)
    return str(resp)

# ==============================
# HOME
# ==============================
@app.route("/", methods=["GET"])
def home():
    return "ZapID GROQ ATIVO 🚀", 200

# ==============================
# START
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
