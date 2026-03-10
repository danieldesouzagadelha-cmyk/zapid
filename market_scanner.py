import requests
import pandas as pd
import numpy as np

# moedas monitoradas
COINS = [
    "bitcoin",
    "ethereum",
    "solana",
    "binancecoin",
    "chainlink",
    "avalanche-2",
    "injective-protocol",
    "arbitrum",
    "optimism",
    "render-token"
]

# -----------------------------
# INDICADORES
# -----------------------------

def calculate_rsi(data, period=14):

    delta = data.diff()

    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return rsi


def ema(data, period):

    return data.ewm(span=period, adjust=False).mean()


# -----------------------------
# OHLC DATA
# -----------------------------

def get_ohlc(coin):

    url = f"https://api.coingecko.com/api/v3/coins/{coin}/ohlc"

    params = {
        "vs_currency": "usd",
        "days": 1
    }

    try:

        r = requests.get(url, params=params, timeout=10)

        data = r.json()

        df = pd.DataFrame(data, columns=[
            "time",
            "open",
            "high",
            "low",
            "close"
        ])

        return df

    except Exception as e:

        print("Erro OHLC:", e)

        return None


# -----------------------------
# ANALISADOR DE TRADE
# -----------------------------

def analyze_coin(coin):

    df = get_ohlc(coin)

    if df is None or len(df) < 50:
        return None

    close = df["close"]

    df["EMA20"] = ema(close, 20)
    df["EMA50"] = ema(close, 50)

    df["RSI"] = calculate_rsi(close)

    last = df.iloc[-1]

    price = last["close"]
    ema20 = last["EMA20"]
    ema50 = last["EMA50"]
    rsi = last["RSI"]

    score = 0

    # tendência
    if ema20 > ema50:
        score += 2

    # pullback
    if price <= ema20 * 1.01:
        score += 2

    # rsi recuperação
    if rsi < 45:
        score += 2

    confidence = score * 15

    if confidence >= 60:

        entry = price
        target = price * 1.06
        stop = price * 0.97

        return {
            "asset": coin,
            "entry": round(entry, 2),
            "target": round(target, 2),
            "stop": round(stop, 2),
            "confidence": confidence
        }

    return None


# -----------------------------
# RADAR PRINCIPAL
# -----------------------------

def run_radar():

    print("📡 ZAPID AI SPOT TRADING SCANNER")

    opportunities = []

    for coin in COINS:

        trade = analyze_coin(coin)

        if trade:
            opportunities.append(trade)

    return opportunities
