import requests
import pandas as pd

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

    r = requests.get(url, params=params)

    data = r.json()

    if not isinstance(data, list):
        return []

    return data


# =========================
# INDICADORES
# =========================

def ema(data, period):
    return data.ewm(span=period, adjust=False).mean()


def rsi(data, period=14):

    delta = data.diff()

    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def macd(data):

    ema12 = ema(data, 12)
    ema26 = ema(data, 26)

    macd_line = ema12 - ema26
    signal = ema(macd_line, 9)

    return macd_line, signal


# =========================
# OHLC
# =========================

def get_ohlc(coin):

    try:

        url = f"https://api.coingecko.com/api/v3/coins/{coin}/ohlc"

        params = {
            "vs_currency": "usd",
            "days": 1
        }

        r = requests.get(url, params=params)

        data = r.json()

        if not isinstance(data, list):
            return None

        df = pd.DataFrame(data, columns=[
            "time",
            "open",
            "high",
            "low",
            "close"
        ])

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

    # tendência
    if price > df["EMA200"].iloc[-1]:
        score += 2

    if df["EMA50"].iloc[-1] > df["EMA200"].iloc[-1]:
        score += 2

    # rsi
    rsi_val = df["RSI"].iloc[-1]

    if 40 < rsi_val < 60:
        score += 1

    if rsi_val < 30:
        score += 2

    # macd
    if macd_line.iloc[-1] > signal.iloc[-1]:
        score += 2

    if macd_line.iloc[-1] > 0:
        score += 1

    return score


# =========================
# SELL SCORE
# =========================

def calculate_sell_score(df):

    close = df["close"]

    df["RSI"] = rsi(close)

    macd_line, signal = macd(close)

    score = 0

    rsi_val = df["RSI"].iloc[-1]

    if rsi_val > 70:
        score += 2

    if macd_line.iloc[-1] < signal.iloc[-1]:
        score += 2

    if macd_line.iloc[-1] < 0:
        score += 1

    return score


# =========================
# RADAR PRINCIPAL
# =========================

def run_radar():

    print("📡 ZAPID PRO MARKET SCANNER")

    coins = get_top_coins()

    signals = []

    if not coins:
        return []

    for coin in coins:

        coin_id = coin.get("id")

        if not coin_id:
            continue

        df = get_ohlc(coin_id)

        if df is None or len(df) < 50:
            continue

        price = df["close"].iloc[-1]

        buy_score = calculate_buy_score(df)
        sell_score = calculate_sell_score(df)

        # =====================
        # COMPRA
        # =====================

        if buy_score >= 10:

            signals.append({
                "type": "BUY",
                "asset": coin_id.upper(),
                "price": round(price, 4)
            })

        # =====================
        # VENDA
        # =====================

        elif sell_score >= 7:

            signals.append({
                "type": "SELL",
                "asset": coin_id.upper(),
                "price": round(price, 4)
            })

        # =====================
        # ESPERAR
        # =====================

        else:

            signals.append({
                "type": "WAIT",
                "asset": coin_id.upper(),
                "price": round(price, 4)
            })

    return signals[:5]

