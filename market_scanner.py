import requests

from config import SYMBOLS, TARGET_PROFIT, STOP_LOSS, FEE_RATE
from ai_predictor import predict_move
from telegram_bot import send_telegram

TARGET_WITH_FEES = TARGET_PROFIT + FEE_RATE


# ==========================
# DATA
# ==========================

def get_klines(symbol, interval="5m", limit=120):

    url = "https://api.binance.com/api/v3/klines"

    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    try:

        r = requests.get(url, params=params, timeout=10)

        data = r.json()

        if not isinstance(data, list):
            print("Erro Binance:", data)
            return [], []

        closes = [float(c[4]) for c in data]
        volumes = [float(c[5]) for c in data]

        return closes, volumes

    except Exception as e:

        print("Erro API Binance:", e)

        return [], []


def get_recent_trades(symbol):

    url = "https://api.binance.com/api/v3/trades"

    params = {"symbol": symbol, "limit": 100}

    try:

        r = requests.get(url, params=params, timeout=10)

        data = r.json()

        if not isinstance(data, list):
            return []

        values = []

        for t in data:

            price = float(t["price"])
            qty = float(t["qty"])

            values.append(price * qty)

        return values

    except:

        return []


# ==========================
# INDICATORS
# ==========================

def moving_average(data, period):

    if len(data) < period:
        return 0

    return sum(data[-period:]) / period


def calculate_rsi(prices, period=14):

    if len(prices) < period + 1:
        return 50

    gains = []
    losses = []

    for i in range(1, len(prices)):

        diff = prices[i] - prices[i-1]

        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            losses.append(abs(diff))
            gains.append(0)

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


# ==========================
# WHALES
# ==========================

def detect_whales(symbol):

    trades = get_recent_trades(symbol)

    whales = [t for t in trades if t > 100000]

    return len(whales)


# ==========================
# TREND
# ==========================

def analyze_trend(symbol):

    prices5, volumes5 = get_klines(symbol, "5m")
    prices1h, _ = get_klines(symbol, "1h")
    prices4h, _ = get_klines(symbol, "4h")

    if not prices5 or not prices1h or not prices4h:
        return 0, [], []

    ma20 = moving_average(prices5, 20)
    ma50 = moving_average(prices5, 50)

    ma20_1h = moving_average(prices1h, 20)
    ma50_1h = moving_average(prices1h, 50)

    ma20_4h = moving_average(prices4h, 20)
    ma50_4h = moving_average(prices4h, 50)

    trend = 0

    if ma20 > ma50:
        trend += 1

    if ma20_1h > ma50_1h:
        trend += 1

    if ma20_4h > ma50_4h:
        trend += 1

    return trend, prices5, volumes5


# ==========================
# ANALYSIS
# ==========================

def analyze_market(symbol):

    trend, prices, volumes = analyze_trend(symbol)

    if not prices or len(prices) < 50:
        return None

    price = prices[-1]

    ma20 = moving_average(prices, 20)

    rsi = calculate_rsi(prices)

    pullback = (price - ma20) / ma20 if ma20 > 0 else 0

    avg_volume = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else 0
    volume_now = volumes[-1]

    volume_strength = volume_now / avg_volume if avg_volume > 0 else 0

    whales = detect_whales(symbol)

    score = 0

    if trend >= 2:
        score += 2

    if rsi < 40:
        score += 2

    if pullback < -0.01:
        score += 2

    if volume_strength > 1.5:
        score += 1

    if whales > 3:
        score += 1

    confidence = score * 12

    prediction = predict_move({
        "trend": trend,
        "rsi": rsi,
        "pullback": pullback,
        "volume": volume_strength,
        "whales": whales
    })

    return {
        "symbol": symbol,
        "price": price,
        "trend": trend,
        "volume": volume_strength,
        "whales": whales,
        "confidence": confidence,
        "prediction": prediction
    }


# ==========================
# TELEGRAM SIGNAL
# ==========================

def send_signal(data):

    symbol = data["symbol"]
    price = data["price"]

    entry = round(price, 4)
    target = round(price * (1 + TARGET_WITH_FEES), 4)
    stop = round(price * (1 + STOP_LOSS), 4)

    confidence = data["confidence"]
    prediction = data["prediction"]

    signal = "BUY" if "UP" in prediction else "SELL"

    msg = f"""
🚨 AI RADAR SIGNAL

🪙 {symbol}

SIGNAL: {signal}

Entry: {entry}
Target: {target}
Stop: {stop}

Confidence: {confidence}%
"""

    send_telegram(msg)


# ==========================
# RADAR RUN
# ==========================

def run_radar():

    print("📡 AI MARKET SCANNER RUNNING")

    for symbol in SYMBOLS:

        data = analyze_market(symbol)

        if data is None:
            continue

        print(symbol, "confidence:", data["confidence"])

        if data["confidence"] >= 75:

            send_signal(data)
