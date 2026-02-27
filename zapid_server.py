from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import requests
import os
import time
import re
from apscheduler.schedulers.background import BackgroundScheduler

# ==============================
# CONFIGURAÇÃO OPENAI SEGURA
# ==============================
try:
    from openai import OpenAI
except:
    OpenAI = None

app = Flask(__name__)

# ==============================
# VARIÁVEIS DE AMBIENTE
# ==============================
account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
twilio_number = os.environ.get("TWILIO_WHATSAPP_NUMBER")
cmc_api_key = os.environ.get("CMC_API_KEY")
openai_api_key = os.environ.get("OPENAI_API_KEY")

client = Client(account_sid, auth_token)

# ==============================
# INICIALIZA GPT (SEM QUEBRAR)
# ==============================
if OpenAI and openai_api_key:
    gpt = OpenAI()
else:
    gpt = None
    print("⚠ GPT não configurado.")

# ==============================
# CONTROLE
# ==============================
vip_users = []
alerts = {}
price_cache = {}
CACHE_TIME = 20

# ==============================
# FUNÇÃO PREÇO (CoinMarketCap)
# ==============================
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

        if response.status_code != 200:
            print("Erro CMC:", response.text)
            return {"price": 0, "change": 0}

        data_json = response.json()["data"][symbol]["quote"]["USD"]

        data = {
            "price": float(data_json["price"]),
            "change": float(data_json["percent_change_24h"])
        }

        price_cache[symbol] = (data, now)
        return data

    except Exception as e:
        print("Erro CMC:", e)
        return {"price": 0, "change": 0}

# ==============================
# FUNÇÃO GPT
# ==============================
def ask_gpt(question):
    if not gpt:
        return "🤖 IA não configurada no servidor."

    try:
        response = gpt.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é especialista em criptomoedas. Responda de forma clara e objetiva."},
                {"role": "user", "content": question}
            ],
            max_tokens=300
        )

        return response.choices[0].message.content

    except Exception as e:
        print("Erro GPT:", e)
        return "Erro ao consultar IA."

# ==============================
# ALERTAS
# ==============================
def send_alert(user, symbol, current):
    client.messages.create(
        body=f"🚨 ALERTA {symbol}!\nPreço atual: ${current:,.2f}",
        from_=twilio_number,
        to=user
    )

def check_alerts():
    try:
        for user, user_alerts in list(alerts.items()):
            for alert in user_alerts[:]:
                current = get_price(alert["symbol"])["price"]

                if alert["type"] == "above" and current >= alert["target"]:
                    send_alert(user, alert["symbol"], current)
                    user_alerts.remove(alert)

            if not user_alerts:
                del alerts[user]

    except Exception as e:
        print("Erro scheduler:", e)

scheduler = BackgroundScheduler()
scheduler.add_job(check_alerts, "interval", seconds=30)
scheduler.start()

# ==============================
# ROTAS
# ==============================
@app.route("/", methods=["GET"])
def home():
    return "ZapID Market 5.1 ONLINE 🚀", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.form.get("Body", "")
    sender = request.form.get("From")

    resp = MessagingResponse()
    msg = incoming_msg.lower().strip()

    coins = {
        "btc": "BTC",
        "eth": "ETH",
        "sol": "SOL"
    }

    # ==========================
    # CONSULTA PREÇO
    # ==========================
    for key in coins:
        if key in msg:
            symbol = coins[key]
            data = get_price(symbol)

            if data["price"] == 0:
                resp.message("Erro ao consultar preço.")
                return str(resp)

            resp.message(
                f"💰 {symbol}\n"
                f"Preço: ${data['price']:,.2f}\n"
                f"24h: {data['change']:.2f}%"
            )
            return str(resp)

    # ==========================
    # FALLBACK PARA IA
    # ==========================
    ai_response = ask_gpt(incoming_msg)
    resp.message(ai_response)

    return str(resp)

# ==============================
# START
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
