from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import requests
import os
from apscheduler.schedulers.background import BackgroundScheduler
from groq import Groq

app = Flask(__name__)

# ================= CONFIG =================
account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
twilio_number = os.environ.get("TWILIO_WHATSAPP_NUMBER")
cmc_api_key = os.environ.get("CMC_API_KEY")
groq_api_key = os.environ.get("GROQ_API_KEY")

client = Client(account_sid, auth_token)

MEU_NUMERO = "whatsapp:+55SEUNUMERO"  # 🔥 COLOQUE SEU NUMERO

ALERTA_QUEDA_PERCENTUAL = -4  # alerta se cair mais que -4%

# ================= CMC BTC DATA =================
def get_btc_data():
    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": cmc_api_key}
        params = {"symbol": "BTC", "convert": "USD"}

        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()["data"]["BTC"]["quote"]["USD"]

        return {
            "price": data["price"],
            "change_24h": data["percent_change_24h"],
            "volume_24h": data["volume_24h"],
            "market_cap": data["market_cap"]
        }

    except Exception as e:
        print("Erro CMC:", e)
        return None

# ================= IA ANALISE =================
def gerar_analise_trader(dados):
    try:
        if not groq_api_key:
            return "GROQ_API_KEY não configurada."

        groq_client = Groq(api_key=groq_api_key)

        prompt = f"""
        Dados atuais do Bitcoin:
        Preço: {dados['price']}
        Variação 24h: {dados['change_24h']}%
        Volume 24h: {dados['volume_24h']}
        Market Cap: {dados['market_cap']}

        Gere:
        - Tendência atual
        - Possível entrada
        - Stop sugerido
        - Alvo provável
        - Grau de risco (baixo, médio, alto)
        - Breve cenário macro
        """

        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Você é um analista trader profissional."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=400
        )

        return response.choices[0].message.content

    except Exception as e:
        print("Erro GROQ:", e)
        return "Erro ao gerar análise."

# ================= RELATORIO DIARIO =================
def enviar_relatorio_diario():
    dados = get_btc_data()
    if not dados:
        return

    analise = gerar_analise_trader(dados)

    mensagem = f"""
📊 RELATÓRIO TRADER PRO - BTC

Preço: ${dados['price']:,.2f}
24h: {dados['change_24h']:.2f}%

{analise}
"""

    client.messages.create(
        body=mensagem,
        from_=twilio_number,
        to=MEU_NUMERO
    )

# ================= ALERTA QUEDA =================
def verificar_queda():
    dados = get_btc_data()
    if not dados:
        return

    if dados["change_24h"] <= ALERTA_QUEDA_PERCENTUAL:
        client.messages.create(
            body=f"🚨 ALERTA BTC\nQueda de {dados['change_24h']:.2f}% nas últimas 24h!",
            from_=twilio_number,
            to=MEU_NUMERO
        )

# ================= SCHEDULER =================
scheduler = BackgroundScheduler()
scheduler.add_job(enviar_relatorio_diario, "cron", hour=8, minute=0)
scheduler.add_job(verificar_queda, "interval", minutes=15)
scheduler.start()

# ================= WEBHOOK =================
@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.form.get("Body", "").lower().strip()
    resp = MessagingResponse()

    # 🔹 PREÇO BTC
    if "valor btc" in incoming_msg or incoming_msg == "btc":
        dados = get_btc_data()
        if not dados:
            resp.message("Erro ao buscar dados.")
            return str(resp)

        resp.message(
            f"💰 BTC\nPreço: ${dados['price']:,.2f}\n24h: {dados['change_24h']:.2f}%"
        )
        return str(resp)

    # 🔹 ANALISE FLEXIVEL
    if any(palavra in incoming_msg for palavra in [
        "analise", "análise", "analize", "analisar",
        "entrada", "trade", "trader"
    ]):
        dados = get_btc_data()
        if not dados:
            resp.message("Erro ao buscar dados do BTC.")
            return str(resp)

        analise = gerar_analise_trader(dados)
        resp.message(analise)
        return str(resp)

    resp.message("ZapID Trader PRO ativo 🚀")
    return str(resp)

# ================= HOME =================
@app.route("/")
def home():
    return "ZapID Trader PRO ONLINE 🚀", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
