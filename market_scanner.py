import requests
import pandas as pd
import numpy as np
import time

CACHE = []
LAST_SCAN = 0

# =========================
# TOP MOEDAS (CoinGecko)
# =========================

def get_top_coins(limit=20):
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "volume_desc",
        "per_page": limit,
        "page": 1
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ Erro CoinGecko markets: {e}")
        return []


# =========================
# OHLC — 30 dias para EMA200
# =========================

def get_ohlc(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        params = {"vs_currency": "usd", "days": 30}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()

        if not isinstance(data, list) or len(data) < 50:
            return None

        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close"])
        df["volume"] = df["close"].diff().abs().fillna(0)
        return df

    except Exception as e:
        print(f"❌ Erro OHLC {coin_id}: {e}")
        return None


# =========================
# INDICADORES
# =========================

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(series):
    ema12 = ema(series, 12)
    ema26 = ema(series, 26)
    macd_line = ema12 - ema26
    signal_line = ema(macd_line, 9)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def obv(df):
    direction = df["close"].diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return (direction * df["volume"]).cumsum()


def bearish_divergence(price, indicator, window=5):
    """Preço faz topo maior, indicador faz topo menor = exaustão de alta"""
    if len(price) < window * 2:
        return False
    p = price.iloc[-window:]
    i = indicator.iloc[-window:]
    return float(p.iloc[-1]) > float(p.iloc[0]) and float(i.iloc[-1]) < float(i.iloc[0])


def bullish_divergence(price, indicator, window=5):
    """Preço faz fundo menor, indicador faz fundo maior = reversão de baixa"""
    if len(price) < window * 2:
        return False
    p = price.iloc[-window:]
    i = indicator.iloc[-window:]
    return float(p.iloc[-1]) < float(p.iloc[0]) and float(i.iloc[-1]) > float(i.iloc[0])


# =========================
# BUY SCORE (máx ~16 pts)
# =========================

def calculate_buy_score(df):
    df = df.copy()
    close = df["close"]

    df["EMA20"]  = ema(close, 20)
    df["EMA50"]  = ema(close, 50)
    df["EMA200"] = ema(close, 200)
    df["RSI"]    = rsi(close)
    df["OBV"]    = obv(df)

    macd_line, signal_line, histogram = macd(close)

    score = 0
    details = []

    price  = float(close.iloc[-1])
    e20    = float(df["EMA20"].iloc[-1])
    e50    = float(df["EMA50"].iloc[-1])
    e200   = float(df["EMA200"].iloc[-1])
    rsi_v  = float(df["RSI"].iloc[-1])
    macd_v = float(macd_line.iloc[-1])
    sig_v  = float(signal_line.iloc[-1])

    # --- Tendência ---
    if pd.notna(e200) and price > e200:
        score += 2
        details.append("✅ Preço > EMA200")

    if pd.notna(e50) and pd.notna(e200) and e50 > e200:
        score += 2
        details.append("✅ Golden Cross (EMA50 > EMA200)")

    if pd.notna(e20) and price > e20:
        score += 1
        details.append("✅ Preço > EMA20")

    # --- RSI ---
    if pd.notna(rsi_v):
        if 40 < rsi_v < 60:
            score += 1
            details.append(f"✅ RSI neutro ({rsi_v:.1f})")
        if rsi_v < 30:
            score += 2
            details.append(f"✅ RSI sobrevenda ({rsi_v:.1f})")
        if bullish_divergence(close, df["RSI"]):
            score += 2
            details.append("✅ Divergência bullish RSI")

    # --- MACD ---
    if pd.notna(macd_v):
        if macd_v > sig_v:
            score += 2
            details.append("✅ MACD bullish crossover")
        if macd_v > 0:
            score += 1
            details.append("✅ MACD acima de zero")

    # --- OBV ---
    obv_series = df["OBV"]
    if len(obv_series) > 5:
        obv_trend = float(obv_series.iloc[-1]) > float(obv_series.iloc[-5])
        if obv_trend:
            score += 1
            details.append("✅ OBV em alta")

    return score, rsi_v, details


# =========================
# SELL SCORE (máx ~14 pts)
# =========================

def calculate_sell_score(df, buy_price=None):
    df = df.copy()
    close = df["close"]

    df["RSI"] = rsi(close)
    df["OBV"] = obv(df)

    macd_line, signal_line, histogram = macd(close)

    score = 0
    details = []
    profit_pct = None
    profit_ok = True

    price  = float(close.iloc[-1])
    rsi_v  = float(df["RSI"].iloc[-1])
    macd_v = float(macd_line.iloc[-1])
    sig_v  = float(signal_line.iloc[-1])

    # --- Lucro mínimo 6% + taxas ---
    if buy_price:
        profit_pct = ((price - buy_price) / buy_price) * 100
        if profit_pct >= 6.4:
            score += 2
            details.append(f"✅ Lucro {profit_pct:.1f}% (meta atingida)")
        else:
            profit_ok = False
            details.append(f"⏳ Lucro {profit_pct:.1f}% (aguardando 6.4%)")

    # --- RSI sobrecomprado ---
    if pd.notna(rsi_v):
        if rsi_v > 70:
            score += 2
            details.append(f"✅ RSI sobrecomprado ({rsi_v:.1f})")
        if rsi_v > 80:
            score += 1
            details.append(f"✅ RSI extremo ({rsi_v:.1f})")
        if bearish_divergence(close, df["RSI"]):
            score += 2
            details.append("✅ Divergência bearish RSI")

    # --- MACD ---
    if pd.notna(macd_v):
        if macd_v < sig_v:
            score += 2
            details.append("✅ MACD bearish crossover")
        if macd_v < 0:
            score += 1
            details.append("✅ MACD abaixo de zero")

    # --- OBV divergindo ---
    obv_series = df["OBV"]
    if len(obv_series) > 5:
        price_up = float(close.iloc[-1]) > float(close.iloc[-5])
        obv_down = float(obv_series.iloc[-1]) < float(obv_series.iloc[-5])
        if price_up and obv_down:
            score += 2
            details.append("✅ OBV divergindo (exaustão)")

    return score, profit_ok, profit_pct, details


# =========================
# RADAR PRINCIPAL
# =========================

def run_radar(portfolio={}):
    """
    portfolio: dict {coin_id: entry_price}
    ex: {"bitcoin": 95000, "ethereum": 3200}
    Retorna lista de sinais ordenados por score
    """
    global CACHE, LAST_SCAN

    # cache 5 minutos para não estourar rate limit CoinGecko
    if time.time() - LAST_SCAN < 300 and CACHE:
        print("📦 Usando cache do scanner")
        return CACHE

    LAST_SCAN = time.time()
    print("📡 ZAPID PRO — iniciando scan...")

    coins = get_top_coins()
    if not coins:
        return []

    scored = []

    for coin in coins:
        coin_id = coin.get("id")
        if not coin_id:
            continue

        # pequena pausa para não bater rate limit
        time.sleep(1.2)

        df = get_ohlc(coin_id)
        if df is None or len(df) < 50:
            continue

        price     = float(df["close"].iloc[-1])
        buy_price = portfolio.get(coin_id)

        buy_score,  rsi_val, buy_details  = calculate_buy_score(df)
        sell_score, profit_ok, profit_pct, sell_details = calculate_sell_score(df, buy_price)

        scored.append({
            "coin_id":     coin_id,
            "symbol":      coin_id.upper(),
            "price":       round(price, 6),
            "buy_score":   buy_score,
            "sell_score":  sell_score,
            "rsi":         round(rsi_val, 1) if pd.notna(rsi_val) else None,
            "profit_pct":  round(profit_pct, 2) if profit_pct else None,
            "profit_ok":   profit_ok,
            "buy_details": buy_details,
            "sell_details":sell_details,
        })

    # ordenar pelo maior score
    scored.sort(key=lambda x: max(x["buy_score"], x["sell_score"]), reverse=True)

    signals = []

    for s in scored[:10]:

        # VENDA tem prioridade — proteger capital em aberto
        if s["sell_score"] >= 7 and s["profit_ok"] and s["coin_id"] in portfolio:
            signals.append({
                "type":    "SELL",
                "asset":   s["symbol"],
                "price":   s["price"],
                "score":   s["sell_score"],
                "rsi":     s["rsi"],
                "profit":  s["profit_pct"],
                "details": s["sell_details"],
            })

        elif s["buy_score"] >= 7:
            signals.append({
                "type":    "BUY",
                "asset":   s["symbol"],
                "price":   s["price"],
                "score":   s["buy_score"],
                "rsi":     s["rsi"],
                "details": s["buy_details"],
            })

    if not signals:
        signals.append({
            "type":    "WAIT",
            "message": "Mercado sem oportunidade clara no momento",
            "top":     scored[0]["symbol"] if scored else "N/A",
            "score":   scored[0]["buy_score"] if scored else 0,
        })

    CACHE = signals
    print(f"✅ Scan concluído — {len(signals)} sinal(is) gerado(s)")
    return signals
