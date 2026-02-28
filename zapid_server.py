from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import requests
import os
from groq import Groq

app = Flask(__name__)

# ================= CONFIG =================
cmc_api_key = os.environ.get("CMC_API_KEY")
groq_api_key = os.environ.get("GROQ_API_KEY")

# ================= BUSCAR DADOS BTC =================
def get_btc_data():
    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        headers = {"X-CMC_PRO_API_KEY": cmc_api_key}
        params = {"symbol": "BTC", "convert": "USD"}

        r = requests.get(url, headers=headers, params=params, timeout=8)
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

        Gere uma análise trader profissional contendo:
        - Tendência
        - Possível entrada
        - Stop sugerido
        - Alvo provável
        - Grau de risco
        """

        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Você é um trader profissional de criptomoedas."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=300
        )

        return response.choices[0].message.content

    except Exception as e:
        print("Erro GROQ:", e)
        return "Erro ao gerar análise."

# ================= WEBHOOK =================
@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.form.get("Body", "").lower().strip()
    resp = MessagingResponse()

    # 🔹 PREÇO BTC
    if "btc" in incoming_msg and "valor" in incoming_msg or incoming_msg == "btc":
        dados = get_btc_data()
        if not dados:
            resp.message("Erro ao buscar dados do BTC.")
            return str(resp)

        resp.message(
            f"💰 BTC\n"
            f"Preço: ${dados['price']:,.2f}\n"
            f"24h: {dados['change_24h']:.2f}%"
        )
        return str(resp)

    # 🔹 ANALISE FLEXIVEL
    if any(p in incoming_msg for p in [
        "analise", "análise", "analize", "entrada", "trade", "trader"
    ]):
        dados = get_btc_data()
        if not dados:
            resp.message("Erro ao buscar dados do BTC.")
            return str(resp)

        analise = gerar_analise_trader(dados)
        resp.message(analise)
        return str(resp)

    resp.message("ZapID Trader PRO está online 🚀")
    return str(resp)

# ================= HOME =================
@app.route("/")
def home():
    return "ZapID Trader PRO STABLE 🚀", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
