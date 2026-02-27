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
# CONFIG TWILIO
# ==============================
account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
twilio_number = os.environ.get("TWILIO_WHATSAPP_NUMBER")

client = Client(account_sid, auth_token)

# ==============================
# VIP USERS
# ==============================
vip_users = [
    # "whatsapp:+5588999999999"
]

# ==============================
# ALERTAS
# Estrutura:
# { user: [ {type, coin, target, base_price} ] }
# ==============================
alerts = {}

# ==============================
# CACHE
# ==============================
price_cache = {}
CACHE_TIME = 10

def get_price(symbol):
    now = time.time()

    if symbol in price_cache:
        data, timestamp = price_cache[symbol]
        if now - timestamp < CACHE_TIME:
            return data

    try:
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
        r = requests.get(url, timeout=5).json()

        data = {
            "price": float(r["lastPrice"]),
            "change": float(r["priceChangePercent"]),
            "volume": float(r["volume"])
        }

        price_cache[symbol] = (data, now)
        return data

    except:
        return {"price": 0, "change": 0, "volume": 0}

# ==============================
# ALERT CHECKER
# ==============================
def check_alerts():
    try:
        for user, user_alerts in list(alerts.items()):
            for alert in user_alerts[:]:
                data = get_price(alert["coin"])
                current = data["price"]

                if alert["type"] == "price_above":
                    if current >= alert["target"]:
                        send_alert(user, alert, current)
                        user_alerts.remove(alert)

                elif alert["type"] == "price_below":
                    if current <= alert["target"]:
                        send_alert(user, alert, current)
                        user_alerts.remove(alert)

                elif alert["type"] == "percent_up":
                    target_price = alert["base_price"] * (1 + alert["target"]/100)
                    if current >= target_price:
                        send_alert(user, alert, current)
                        user_alerts.remove(alert)

                elif alert["type"] == "percent_down":
                    target_price = alert["base_price"] * (1 - alert["target"]/100)
                    if current <= target_price:
                        send_alert(user, alert, current)
                        user_alerts.remove(alert)

            if not user_alerts:
                del alerts[user]

    except Exception as e:
        print("Erro scheduler:", e)

def send_alert(user, alert, current):
    client.messages.create(
        body=(
            f"🚨 ALERTA {alert['coin'].replace('USDT','')}!\n"
            f"Preço atual: ${current:,.2f}"
        ),
        from_=twilio_number,
        to=user
    )

scheduler = BackgroundScheduler()
scheduler.add_job(check_alerts, "interval", seconds=30)
scheduler.start()

# ==============================
# ROTAS
# ==============================
@app.route("/", methods=["GET"])
def home():
    return "ZapID Market 3.0 ONLINE 🚀", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.form.get("Body", "")
    sender = request.form.get("From")
    resp = MessagingResponse()

    msg = incoming_msg.lower().strip()
    is_vip = sender in vip_users

    # ==========================
    # CONSULTA SIMPLES
    # ==========================
    if "btc" in msg and "alert" not in msg:
        data = get_price("BTCUSDT")
        resp.message(
            f"💰 BTC\n"
            f"Preço: ${data['price']:,.2f}\n"
            f"24h: {data['change']:.2f}%"
        )
        return str(resp)

    # ==========================
    # CRIAR ALERTAS INTELIGENTES
    # ==========================
    coin_map = {
        "btc": "BTCUSDT",
        "eth": "ETHUSDT",
        "sol": "SOLUSDT"
    }

    for key in coin_map:
        if key in msg:
            coin = coin_map[key]
            current_price = get_price(coin)["price"]

            if sender not in alerts:
                alerts[sender] = []

            if not is_vip and len(alerts[sender]) >= 1:
                resp.message("🔒 Free permite apenas 1 alerta.")
                return str(resp)

            # acima de
            match = re.search(r'acima de (\d+)', msg)
            if match:
                target = float(match.group(1))
                alerts[sender].append({
                    "type": "price_above",
                    "coin": coin,
                    "target": target,
                    "base_price": current_price
                })
                resp.message(f"🔔 Alerta criado: {key.upper()} acima de ${target}")
                return str(resp)

            # abaixo de
            match = re.search(r'abaixo de (\d+)', msg)
            if match:
                target = float(match.group(1))
                alerts[sender].append({
                    "type": "price_below",
                    "coin": coin,
                    "target": target,
                    "base_price": current_price
                })
                resp.message(f"🔔 Alerta criado: {key.upper()} abaixo de ${target}")
                return str(resp)

            # cair %
            match = re.search(r'cair (\d+)%', msg)
            if match:
                percent = float(match.group(1))
                alerts[sender].append({
                    "type": "percent_down",
                    "coin": coin,
                    "target": percent,
                    "base_price": current_price
                })
                resp.message(f"🔔 Alerta criado: {key.upper()} cair {percent}%")
                return str(resp)

            # subir %
            match = re.search(r'subir (\d+)%', msg)
            if match:
                percent = float(match.group(1))
                alerts[sender].append({
                    "type": "percent_up",
                    "coin": coin,
                    "target": percent,
                    "base_price": current_price
                })
                resp.message(f"🔔 Alerta criado: {key.upper()} subir {percent}%")
                return str(resp)

    # ==========================
    # MENU
    # ==========================
    resp.message(
        "📊 ZapID Market 3.0\n\n"
        "Exemplos:\n"
        "btc acima de 300000\n"
        "btc abaixo de 250000\n"
        "me avisa quando btc cair 5%\n"
        "btc subir 3%\n\n"
        "🔒 Free: 1 alerta\n"
        "💎 VIP: ilimitado"
    )

    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
