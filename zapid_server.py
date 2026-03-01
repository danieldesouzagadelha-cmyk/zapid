from flask import Flask
import os
import requests
import tweepy
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

app = Flask(__name__)

# ================== ENV ==================
CMC_API_KEY = os.environ.get("CMC_API_KEY")

X_CONSUMER_KEY = os.environ.get("X_CONSUMER_KEY")
X_CONSUMER_SECRET = os.environ.get("X_CONSUMER_SECRET")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN")
X_ACCESS_TOKEN_SECRET = os.environ.get("X_ACCESS_TOKEN_SECRET")

# ================== TWITTER AUTH ==================
auth = tweepy.OAuth1UserHandler(
    X_CONSUMER_KEY,
    X_CONSUMER_SECRET,
    X_ACCESS_TOKEN,
    X_ACCESS_TOKEN_SECRET
)

twitter = tweepy.API(auth)

# ================== FUNÇÕES ==================

def get_btc():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}
    params = {"symbol": "BTC", "convert": "USD"}

    r = requests.get(url, headers=headers, params=params)
    data = r.json()["data"]["BTC"]["quote"]["USD"]

    return data["price"], data["percent_change_24h"]


def post_btc_report():
    try:
        price, change = get_btc()

        tweet = f"""
📊 BTC Daily Report

💰 Price: ${price:,.2f}
📉 24h Change: {change:.2f}%

#Bitcoin #Crypto
        """

        twitter.update_status(tweet)
        print("BTC report posted")

    except Exception as e:
        print("Erro BTC:", e)


def post_economy_news():
    try:
        tweet = """
🌍 Global Economy Update

Markets remain sensitive to inflation data and interest rate expectations.

Stay alert to macro volatility.

#Economy #Markets
        """

        twitter.update_status(tweet)
        print("Economy news posted")

    except Exception as e:
        print("Erro Economy:", e)


def post_geopolitics():
    try:
        tweet = """
🌐 Geopolitical Watch

Ongoing global tensions continue impacting energy and commodity markets.

Macro risk remains elevated.

#Geopolitics #GlobalMarkets
        """

        twitter.update_status(tweet)
        print("Geopolitics posted")

    except Exception as e:
        print("Erro Geopolitics:", e)

# ================== SCHEDULER ==================

scheduler = BackgroundScheduler()

scheduler.add_job(post_btc_report, "cron", hour=8, minute=0)
scheduler.add_job(post_economy_news, "cron", hour=14, minute=0)
scheduler.add_job(post_geopolitics, "cron", hour=20, minute=0)

scheduler.start()

# ================== SERVER ==================

@app.route("/")
def home():
    return "ZapID Content Machine ONLINE 🚀", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
