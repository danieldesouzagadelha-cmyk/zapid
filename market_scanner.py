import requests
import time

from ai_predictor import predict_move
from telegram_bot import send_telegram
from config import SYMBOLS, TARGET_PROFIT, STOP_LOSS, FEE_RATE

from trades import log_trade
from trade_monitor import update_trades
from performance import calculate_performance

TARGET_WITH_FEES = TARGET_PROFIT + FEE_RATE

entries = {}

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

    r = requests.get(url, params=params)

    data = r.json()

    closes = [float(c[4]) for c in data]
    volumes = [float(c[5]) for c in data]

    return closes, volumes


def get_recent_trades(symbol):

    url = "https://api.binance.com/api/v3/trades"

    params = {"symbol": symbol, "limit": 100}

    r = requests.get(url, params=params)

    data = r.json()

    values = []

    for t in data:

        price = float(t["price"])
        qty = float(t["qty"])

        values.append(price * qty)

    return values


# ==========================
# INDICATORS
# ==========================

def moving_average(data, period):

    return sum(data[-period:]) / period


def calculate_rsi(prices, period=14):

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

    price = prices[-1]

    ma20 = moving_average(prices, 20)

    rsi = calculate_rsi(prices)

    pullback = (price - ma20) / ma20

    avg_volume = sum(volumes[-20:]) / 20
    volume_now = volumes[-1]

    volume_strength = volume_now / avg_volume

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

    if "UP" in prediction:
        signal = "BUY"
        icon = "🟢"
    else:
        signal = "SELL"
        icon = "🔴"

    msg = f"""
🚨 AI RADAR SIGNAL

🪙 {symbol}

{icon} SIGNAL: {signal}

Entry: {entry}
Target: {target}
Stop: {stop}

Confidence: {confidence}%
"""

    send_telegram(msg)

    log_trade(symbol, entry, target, stop)


# ==========================
# PERFORMANCE MESSAGE
# ==========================

def send_performance():

    wins, losses, total, winrate = calculate_performance()

    msg = f"""
📊 RADAR PERFORMANCE

Trades: {total}
Wins: {wins}
Losses: {losses}

Win Rate: {winrate}%
"""

    send_telegram(msg)


# ==========================
# MAIN LOOP
# ==========================

while True:

    print("\n📡 AI MARKET SCANNER RUNNING\n")

    market = []

    for symbol in SYMBOLS:

        data = analyze_market(symbol)

        market.append(data)

        print(symbol, "confidence:", data["confidence"])

        if data["confidence"] >= 75 and symbol not in entries:

            entries[symbol] = data["price"]

            send_signal(data)

    print("\n🏆 MARKET RANKING\n")

    ranked = sorted(market, key=lambda x: x["confidence"], reverse=True)

    for r in ranked[:5]:

        print(r["symbol"], "confidence:", r["confidence"])

    update_trades()

    send_performance()

    time.sleep(300)