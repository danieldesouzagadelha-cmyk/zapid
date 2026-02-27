from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import requests
import os
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# ==============================
# CONFIG TWILIO (Render ENV)
# ==============================
account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
twilio_number = os.environ.get("TWILIO_WHATSAPP_NUMBER")

client = Client(account_sid, auth_token)

# ==============================
# CONTROLE VIP (MANUAL POR ENQUANTO)
# Coloque aqui números VIP
# Exemplo: "whatsapp:+5588999999999"
# ==============================
vip_users = [
    # "whatsapp:+5588999999999"
]

# ==============================
# ALERTAS EM MEMÓRIA
# formato: { usuario: [(moeda, preco_alvo), ...] }
# ==============================
alerts = {}

# ==============================
# FUNÇÕES MERCADO
# ==============================
def get_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
    r = requests.get(url).json()
    return {
        "price": float(r["lastPrice"]),
        "change": float(r["priceChangePercent"]),
        "volume": float(r["volume"])
    }

def get_top():
    coins = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    result = "🏆 Top Criptos:\n\n"
    for coin in coins:
        data = get_price(coin)
        name = coin.replace("USDT","")
        result += f"{name} - ${data['price']:,.2f} ({data['change']:.2f}%)\n"
    return result

def get_trending():
    coins = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    data_list = []

    for coin in coins:
        data = get_price(coin)
        data_list.append((coin, data["change"], data["price"]))

    data_list.sort(key=lambda x: x[1], reverse=True)

    result = "🔥 Tendências (24h):\n\n"
    for coin, change, price in data_list:
        name = coin.replace("USDT","")
        result += f"{name} - ${price:,.2f} ({change:.2f}%)\n"

    return result

# ==============================
# VERIFICADOR DE ALERTAS
# ==============================
def check_alerts():
    try:
        for user, user_alerts in list(alerts.items()):
            for alert in user_alerts[:]:
                coin, target = alert
                current = get_price(coin)["price"]

                if current >= target:
                    client.messages.create(
                        body=f"🚨 ALERTA {coin.replace('USDT','')}!\nPreço atual: ${current:,.2f}",
                        from_=twilio_number,
                        to=user
                    )
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
    return "ZapID Market VIP ONLINE 🚀", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.form.get("Body")
    sender = request.form.get("From")

    resp = MessagingResponse()

    if incoming_msg:
        msg = incoming_msg.lower().strip()
        is_vip = sender in vip_users

        # ==========================
        # CONSULTAS
        # ==========================
        if msg == "btc":
            data = get_price("BTCUSDT")
            resp.message(f"💰 BTC\nPreço: ${data['price']:,.2f}\n24h: {data['change']:.2f}%")

        elif msg == "eth":
            data = get_price("ETHUSDT")
            resp.message(f"💎 ETH\nPreço: ${data['price']:,.2f}\n24h: {data['change']:.2f}%")

        elif msg == "sol":
            data = get_price("SOLUSDT")
            resp.message(f"⚡ SOL\nPreço: ${data['price']:,.2f}\n24h: {data['change']:.2f}%")

        elif msg == "top":
            resp.message(get_top())

        elif msg == "tendencias":
            resp.message(get_trending())

        # ==========================
        # CRIAR ALERTA
        # ==========================
        elif msg.startswith("alerta"):
            try:
                parts = msg.split()
                coin = parts[1].upper() + "USDT"
                target = float(parts[2])

                if sender not in alerts:
                    alerts[sender] = []

                # 🔒 Limite Free
                if not is_vip and len(alerts[sender]) >= 1:
                    resp.message(
                        "🔒 Plano Free permite apenas 1 alerta.\n"
                        "Torne-se VIP para alertas ilimitados."
                    )
                    return str(resp)

                alerts[sender].append((coin, target))

                resp.message(
                    f"🔔 Alerta criado!\n"
                    f"Moeda: {coin.replace('USDT','')}\n"
                    f"Preço alvo: ${target:,.2f}"
                )

            except:
                resp.message("Use:\nalerta btc 70000")

        else:
            resp.message(
                "📊 ZapID Market\n\n"
                "btc / eth / sol → preço\n"
                "top → ranking\n"
                "tendencias → em alta\n"
                "alerta btc 70000\n\n"
                "🔒 Free: 1 alerta\n"
                "💎 VIP: ilimitado"
            )

    return str(resp)

# ==============================
# START SERVER
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
