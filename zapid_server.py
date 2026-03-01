import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from groq import Groq
import tweepy

app = Flask(__name__)

# =========================
# 🔐 VARIÁVEIS DE AMBIENTE
# =========================

groq_api_key = os.getenv("GROQ_API_KEY")
cmc_api_key = os.getenv("CMC_API_KEY")

X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")

# =========================
# 🟢 STATUS
# =========================

@app.route("/")
def home():
    return "ZapID Máquina de Conteúdo Online 🚀"

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
    try:
        client = Groq(api_key=groq_api_key)

        chat = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Você é um analista profissional de mercado, especialista em cripto, macroeconomia e geopolítica. Gere conteúdo estratégico para Twitter."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="llama-3.1-8b-instant",
            temperature=0.6,
            max_tokens=700
        )

        return chat.choices[0].message.content

    except Exception as e:
        print("Erro GROQ:", e)
        return "Erro ao consultar IA."

# =========================
# 🐦 POSTAR NO X
# =========================

def post_on_x(text):
    try:
        client = tweepy.Client(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_TOKEN_SECRET
        )

        client.create_tweet(text=text)
        return "Postado com sucesso no X 🚀"

    except Exception as e:
        print("Erro X:", e)
        return "Erro ao postar no X."

# =========================
# 🧠 PROCESSAR MENSAGEM
# =========================

def process_message(msg):

    msg_lower = msg.lower()

    # 💰 BTC
    if "btc agora" in msg_lower or "valor btc" in msg_lower:
        price = get_btc_price()
        return f"💰 BTC agora: ${price}"

    # 🐦 Postar manual
    if msg_lower.startswith("poste:"):
        content = msg.replace("poste:", "").strip()
        return post_on_x(content)

    # 📊 3 posts do dia
    if "posts do dia" in msg_lower:

        prompt = """
        Gere 3 posts prontos para Twitter:

        1 sobre Bitcoin
        1 sobre economia global
        1 sobre geopolítica ou macro

        Cada post deve conter:
        - Título forte em CAIXA ALTA
        - Resumo estratégico curto (máx 4 linhas)
        - Hashtags relevantes
        - Linguagem profissional e impactante
        """

        return ask_groq(prompt)

    # 📰 Post específico
    if msg_lower.startswith("post "):
        tema = msg_lower.replace("post ", "")
        prompt = f"""
        Gere um post profissional para Twitter sobre {tema}.

        Inclua:
        - Título forte em CAIXA ALTA
        - Resumo estratégico
        - Hashtags relevantes
        - Linguagem de autoridade
        """

        return ask_groq(prompt)

    # 🤖 Pergunta geral
    return ask_groq(msg)

# =========================
# 📲 WEBHOOK TWILIO
# =========================

@app.route("/webhook", methods=["POST"])
def webhook():

    incoming_msg = request.form.get("Body")

    resposta = process_message(incoming_msg)

    twilio_response = MessagingResponse()
    twilio_response.message(resposta)

    return str(twilio_response)

# =========================
# 🚀 START
# =========================

if __name__ == "__main__":
    app.run()
