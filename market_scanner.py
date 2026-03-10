
import requests
import pandas as pd
import numpy as np
import time

CACHE = []
LAST_SCAN = 0

# =========================
# PEGAR TOP MOEDAS
# =========================
def get_top_coins():

    url = "https://api.coingecko.com/api/v3/coins/markets"

    params = {
        "vs_currency": "usd",
        "order": "volume_desc",
        "per_page": 25,
        "page": 1
    }

    try:

        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        if not isinstance(data, list):
            return []

        return data[:20]

    except Exception as e:

        print("Erro CoinGecko:", e)
        return []

# =========================
# INDICADORES
# =========================

def ema(data, period):
    return data.ewm(span=period, adjust=False).mean()

def rsi(data, period=14):

    delta = data.diff()

    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)

    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))

def macd(data):

    ema12 = ema(data, 12)
    ema26 = ema(data, 26)

    macd_line = ema12 - ema26
    signal = ema(macd_line, 9)

    return macd_line, signal

def bearish_divergence(price, indicator):

    if len(price) < 10:
        return False

    price_recent = price.iloc[-5:]
    ind_recent = indicator.iloc[-5:]

    return price_recent.iloc[-1] > price_recent.iloc[0] and \
           ind_recent.iloc[-1] < ind_recent.iloc[0]

# =========================
# OHLC
# =========================

def get_ohlc(coin):

    try:

        url = f"https://api.coingecko.com/api/v3/coins/{coin}/ohlc"

        params = {
            "vs_currency": "usd",
            "days": 30
        }

        r = requests.get(url, params=params, timeout=10)

        data = r.json()

        if not isinstance(data, list) or len(data) < 50:
            return None

        df = pd.DataFrame(data, columns=[
            "time",
            "open",
            "high",
            "low",
            "close"
        ])

        # proxy volume
        df["volume"] = df["close"].diff().abs()

        return df

    except:

        return None

# =========================
# BUY SCORE
# =========================

def calculate_buy_score(df):

    close = df["close"]

    df["EMA20"] = ema(close, 20)
    df["EMA50"] = ema(close, 50)
    df["EMA200"] = ema(close, 200)

    df["RSI"] = rsi(close)

    macd_line, signal = macd(close)

    score = 0

    price = close.iloc[-1]

    e20 = df["EMA20"].iloc[-1]
    e50 = df["EMA50"].iloc[-1]
    e200 = df["EMA200"].iloc[-1]

    rsi_val = df["RSI"].iloc[-1]

    if pd.notna(e200) and price > e200:
        score += 2

    if pd.notna(e50) and pd.notna(e200) and e50 > e200:
        score += 2

    if pd.notna(rsi_val):

        if 40 < rsi_val < 60:
            score += 1

        if rsi_val < 30:
            score += 2

    if pd.notna(macd_line.iloc[-1]) and macd_line.iloc[-1] > signal.iloc[-1]:
        score += 2

    if pd.notna(macd_line.iloc[-1]) and macd_line.iloc[-1] > 0:
        score += 1

    return score, rsi_val

# =========================
# SELL SCORE
# =========================

def calculate_sell_score(df, buy_price=None):

    close = df["close"]

    df["RSI"] = rsi(close)

    macd_line, signal = macd(close)

    score = 0

    price = close.iloc[-1]

    rsi_val = df["RSI"].iloc[-1]

    profit_ok = True

    if buy_price:

        profit_pct = ((price - buy_price) / buy_price) * 100

        if profit_pct >= 6.4:
            score += 2
        else:
            profit_ok = False

    if pd.notna(rsi_val):

        if rsi_val > 70:
            score += 2

        if rsi_val > 80:
            score += 1

    if macd_line.iloc[-1] < signal.iloc[-1]:
        score += 2

    if macd_line.iloc[-1] < 0:
        score += 1

    if bearish_divergence(close, df["RSI"]):
        score += 2

    return score, profit_ok

# =========================
# RADAR PRINCIPAL
# =========================

def run_radar(portfolio={}):

    global CACHE, LAST_SCAN

    # cache 5 minutos
    if time.time() - LAST_SCAN < 300:
        return CACHE

    LAST_SCAN = time.time()

    print("📡 ZAPID PRO MARKET SCANNER")

    coins = get_top_coins()

    if not coins:
        return []

    scored = []

    for coin in coins:

        coin_id = coin.get("id")

        if not coin_id:
            continue

        df = get_ohlc(coin_id)

        if df is None:
            continue

        price = df["close"].iloc[-1]

        buy_price = portfolio.get(coin_id)

        buy_score, rsi_val = calculate_buy_score(df)
        sell_score, profit_ok = calculate_sell_score(df, buy_price)

        scored.append({
            "coin": coin_id,
            "price": price,
            "buy_score": buy_score,
            "sell_score": sell_score,
            "rsi": rsi_val,
            "profit_ok": profit_ok
        })

    # ranking
    scored.sort(key=lambda x: max(x["buy_score"], x["sell_score"]), reverse=True)

    signals = []

    for s in scored[:5]:

        if s["buy_score"] >= 9:

            signals.append({
                "type": "BUY",
                "asset": s["coin"].upper(),
                "price": round(s["price"], 4),
                "score": s["buy_score"]
            })

        elif s["sell_score"] >= 7 and s["profit_ok"]:

            signals.append({
                "type": "SELL",
                "asset": s["coin"].upper(),
                "price": round(s["price"], 4),
                "score": s["sell_score"]
            })

    # nenhum sinal
    if not signals:

        signals.append({
            "type": "WAIT",
            "message": "Mercado sem oportunidade clara no momento"
        })

    CACHE = signals

    return signals
