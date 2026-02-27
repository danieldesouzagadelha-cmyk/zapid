from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import requests
import os
import time
import re
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# ==============================
# CONFIGURAÇÕES
# ==============================
account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
twilio_number = os.environ.get("TWILIO_WHATSAPP_NUMBER")
cmc_api_key = os.environ.get("CMC_API_KEY")

client = Client(account_sid, auth_token)

# ==============================
# CONTROLE
# ==============================
vip_users = []
alerts = {}
price_cache = {}
CACHE_TIME = 20  # segundos

# ==============================
# FUNÇÃO PREÇO CMC
# ==============================
def get_price(symbol):
    now = time.time()

    # CACHE
    if symbol in price_cache:
        data, timestamp = price_cache[symbol]
        if now - timestamp < CACHE_TIME:
            return data

    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {
            "X-CMC_PRO_API_KEY": cmc_api_key
        }
        params = {
            "symbol": symbol,
            "convert": "USD"
        }

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
        print("Erro geral CMC:", e)
        return {"price": 0, "change": 0}

# ==============================
# ENVIO ALERTA
# ==============================
def send_alert(user, symbol, current):
    client.messages.create(
        body=f"🚨 ALERTA {symbol}!\nPreço atual: ${current:,.2f}",
        from_=twilio_number,
        to=user
    )

# ==============================
# VERIFICADOR ALERTAS
# ==============================
def check_alerts():
    try:
        for user, user_alerts in list(alerts.items()):
            for alert in user_alerts[:]:
                data = get_price(alert["symbol"])
                current = data["price"]

                if alert["type"] == "above" and current >= alert["target"]:
                    send_alert(user, alert["symbol"], current)
                    user_alerts.remove(alert)

                elif alert["type"] == "below" and current <= alert["target"]:
                    send_alert(user, alert["symbol"], current)
                    user_alerts.remove(alert)

                elif alert["type"] == "percent_up":
                    target_price = alert["base"] * (1 + alert["target"]/100)
                    if current >= target_price:
                        send_alert(user, alert["symbol"], current)
                        user_alerts.remove(alert)

                elif alert["type"] == "percent_down":
                    target_price = alert["base"] * (1 - alert["target"]/100)
                    if current <= target_price:
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
    return "ZapID Market 4.1 ONLINE 🚀", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.form.get("Body", "")
    sender = request.form.get("From")

    resp = MessagingResponse()
    msg = incoming_msg.lower().strip()
    is_vip = sender in vip_users

    coins = {
        "btc": "BTC",
        "eth": "ETH",
        "sol": "SOL"
    }

    for key in coins:
        if key in msg:
            symbol = coins[key]
            data = get_price(symbol)

            if data["price"] == 0:
                resp.message("Erro ao consultar preço. Verifique API.")
                return str(resp)

            # Limite FREE
            if sender not in alerts:
                alerts[sender] = []

            if not is_vip and len(alerts[sender]) >= 1:
                resp.message("🔒 Free permite apenas 1 alerta ativo.")
                return str(resp)

            # ALERTA ACIMA
            match = re.search(r'acima de (\d+)', msg)
            if match:
                target = float(match.group(1))
                alerts[sender].append({
                    "symbol": symbol,
                    "type": "above",
                    "target": target,
                    "base": data["price"]
                })
                resp.message(f"🔔 Alerta criado: {symbol} acima de ${target}")
                return str(resp)

            # ALERTA ABAIXO
            match = re.search(r'abaixo de (\d+)', msg)
            if match:
                target = float(match.group(1))
                alerts[sender].append({
                    "symbol": symbol,
                    "type": "below",
                    "target": target,
                    "base": data["price"]
                })
                resp.message(f"🔔 Alerta criado: {symbol} abaixo de ${target}")
                return str(resp)

            # ALERTA POR %
            match = re.search(r'cair (\d+)%', msg)
            if match:
                percent = float(match.group(1))
                alerts[sender].append({
                    "symbol": symbol,
                    "type": "percent_down",
                    "target": percent,
                    "base": data["price"]
                })
                resp.message(f"🔔 Alerta criado: {symbol} cair {percent}%")
                return str(resp)

            match = re.search(r'subir (\d+)%', msg)
            if match:
                percent = float(match.group(1))
                alerts[sender].append({
                    "symbol": symbol,
                    "type": "percent_up",
                    "target": percent,
                    "base": data["price"]
                })
                resp.message(f"🔔 Alerta criado: {symbol} subir {percent}%")
                return str(resp)

            # CONSULTA SIMPLES
            resp.message(
                f"💰 {symbol}\n"
                f"Preço: ${data['price']:,.2f}\n"
                f"24h: {data['change']:.2f}%"
            )
            return str(resp)

    resp.message(
        "📊 ZapID Market 4.1\n\n"
        "Exemplos:\n"
        "btc\n"
        "btc acima de 300000\n"
        "btc abaixo de 250000\n"
        "btc cair 5%\n"
        "btc subir 3%"
    )

    return str(resp)


# ==============================
# START
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
