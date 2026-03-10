import requests
import pandas as pd
import numpy as np
import time
from config import TARGET_PROFIT, STOP_LOSS, FEE_RATE

# =========================
# CONFIG
# =========================

MIN_SCORE_TO_SIGNAL = 10   # sinal só sai se score >= 10/15
SCAN_LIMIT          = 20   # top 20 CoinGecko

# mapeamento CoinGecko → Binance symbol
COINGECKO_TO_BINANCE = {
    "bitcoin":       "BTCUSDT",
    "ethereum":      "ETHUSDT",
    "tether":        None,          # stablecoin — ignora
    "binancecoin":   "BNBUSDT",
    "solana":        "SOLUSDT",
    "ripple":        "XRPUSDT",
    "usd-coin":      None,
    "dogecoin":      "DOGEUSDT",
    "cardano":       "ADAUSDT",
    "tron":          "TRXUSDT",
    "avalanche-2":   "AVAXUSDT",
    "chainlink":     "LINKUSDT",
    "polkadot":      "DOTUSDT",
    "polygon":       "MATICUSDT",
    "litecoin":      "LTCUSDT",
    "shiba-inu":     "SHIBUSDT",
    "uniswap":       "UNIUSDT",
    "stellar":       "XLMUSDT",
    "bitcoin-cash":  "BCHUSDT",
    "near":          "NEARUSDT",
    "internet-computer": "ICPUSDT",
    "aptos":         "APTUSDT",
    "arbitrum":      "ARBUSDT",
    "optimism":      "OPUSDT",
    "sui":           "SUIUSDT",
}


# =========================
# DADOS — BINANCE KLINES
# =========================

def get_klines(symbol, interval="4h", limit=200):
    """
    Busca candles da Binance.
    interval: 4h para análise principal, 1d para confirmação
    limit: 200 candles = ~33 dias em 4h
    """
    url = "https://api.binance.com/api/v3/klines"
    try:
        r = requests.get(url, params={
            "symbol":   symbol,
            "interval": interval,
            "limit":    limit
        }, timeout=10)

        if not r.ok:
            return None

        raw = r.json()
        df = pd.DataFrame(raw, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])

        df["close"]  = df["close"].astype(float)
        df["high"]   = df["high"].astype(float)
        df["low"]    = df["low"].astype(float)
        df["open"]   = df["open"].astype(float)
        df["volume"] = df["volume"].astype(float)

        return df

    except Exception as e:
        print(f"⚠️ Binance klines error {symbol}: {e}")
        return None


# =========================
# INDICADORES TÉCNICOS
# =========================

def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def calc_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_g = gain.ewm(com=period - 1, adjust=False).mean()
    avg_l = loss.ewm(com=period - 1, adjust=False).mean()
    rs    = avg_g / avg_l
    return 100 - (100 / (1 + rs))


def calc_macd(series, fast=12, slow=26, signal=9):
    ema_fast   = calc_ema(series, fast)
    ema_slow   = calc_ema(series, slow)
    macd_line  = ema_fast - ema_slow
    signal_line = calc_ema(macd_line, signal)
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram


def calc_bollinger(series, period=20, std=2):
    ma    = series.rolling(period).mean()
    sigma = series.rolling(period).std()
    upper = ma + std * sigma
    lower = ma - std * sigma
    return upper, ma, lower


def calc_atr(df, period=14):
    high_low   = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close  = (df["low"]  - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean()


def calc_obv(df):
    direction = df["close"].diff().apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)
    return (direction * df["volume"]).cumsum()


def calc_stoch_rsi(rsi, period=14, smooth_k=3, smooth_d=3):
    min_rsi = rsi.rolling(period).min()
    max_rsi = rsi.rolling(period).max()
    stoch   = (rsi - min_rsi) / (max_rsi - min_rsi + 1e-10) * 100
    k = stoch.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return k, d


def calc_adx(df, period=14):
    """Average Directional Index — mede força da tendência"""
    high  = df["high"]
    low   = df["low"]
    close = df["close"]

    plus_dm  = high.diff()
    minus_dm = -low.diff()
    plus_dm[plus_dm  < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_dm[plus_dm < minus_dm]  = 0
    minus_dm[minus_dm < plus_dm] = 0

    tr        = calc_atr(df, period)
    plus_di   = 100 * (plus_dm.ewm(com=period-1, adjust=False).mean() / tr)
    minus_di  = 100 * (minus_dm.ewm(com=period-1, adjust=False).mean() / tr)
    dx        = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)) * 100
    adx       = dx.ewm(com=period-1, adjust=False).mean()
    return adx, plus_di, minus_di


# =========================
# ANÁLISE COMPLETA — 4H
# =========================

def analyze_asset(symbol):
    """
    Análise técnica completa em 4h com confirmação diária.
    Score máximo: 15 pontos
    Sinal só sai se score >= 10
    """

    # --- candles 4h (200 candles = ~33 dias) ---
    df = get_klines(symbol, interval="4h", limit=200)
    if df is None or len(df) < 60:
        return None

    close  = df["close"]
    price  = close.iloc[-1]

    # --- indicadores ---
    ema20  = calc_ema(close, 20)
    ema50  = calc_ema(close, 50)
    ema200 = calc_ema(close, 200)
    rsi    = calc_rsi(close, 14)
    macd_line, signal_line, histogram = calc_macd(close)
    bb_upper, bb_mid, bb_lower = calc_bollinger(close, 20, 2)
    atr    = calc_atr(df, 14)
    obv    = calc_obv(df)
    k, d   = calc_stoch_rsi(rsi)
    adx, plus_di, minus_di = calc_adx(df, 14)

    # valores atuais
    rsi_now    = rsi.iloc[-1]
    rsi_prev   = rsi.iloc[-2]
    macd_now   = macd_line.iloc[-1]
    macd_prev  = macd_line.iloc[-2]
    sig_now    = signal_line.iloc[-1]
    sig_prev   = signal_line.iloc[-2]
    hist_now   = histogram.iloc[-1]
    hist_prev  = histogram.iloc[-2]
    obv_now    = obv.iloc[-1]
    obv_ma     = obv.rolling(20).mean().iloc[-1]
    k_now      = k.iloc[-1]
    d_now      = d.iloc[-1]
    adx_now    = adx.iloc[-1]
    plus_now   = plus_di.iloc[-1]
    minus_now  = minus_di.iloc[-1]
    atr_now    = atr.iloc[-1]
    bb_low_now = bb_lower.iloc[-1]
    bb_mid_now = bb_mid.iloc[-1]

    # --- confirmação diária ---
    df_daily = get_klines(symbol, interval="1d", limit=60)
    daily_trend = "neutral"
    if df_daily is not None and len(df_daily) >= 50:
        close_d = df_daily["close"]
        ema50_d = calc_ema(close_d, 50)
        ema200_d = calc_ema(close_d, 200)
        if close_d.iloc[-1] > ema50_d.iloc[-1] > ema200_d.iloc[-1]:
            daily_trend = "bullish"
        elif close_d.iloc[-1] < ema50_d.iloc[-1]:
            daily_trend = "bearish"

    # ================================================
    # SISTEMA DE SCORE — BUY (máx 15 pts)
    # ================================================
    score      = 0
    indicators = []

    # [3 pts] Tendência principal
    if price > ema200.iloc[-1]:
        score += 1
        indicators.append("✅ Preço acima EMA200")
    if ema50.iloc[-1] > ema200.iloc[-1]:
        score += 1
        indicators.append("✅ Golden Cross EMA50/200")
    if daily_trend == "bullish":
        score += 1
        indicators.append("✅ Tendência diária bullish")

    # [3 pts] Momentum RSI + StochRSI
    if 40 <= rsi_now <= 60:
        score += 1
        indicators.append(f"✅ RSI neutro ({rsi_now:.0f})")
    elif rsi_now < 35:
        score += 2
        indicators.append(f"✅ RSI sobrevenda ({rsi_now:.0f}) +2")
    if k_now < 20 and k_now > d_now and k_now > k.iloc[-2]:
        score += 1
        indicators.append(f"✅ StochRSI saindo de sobrevenda ({k_now:.0f})")

    # [3 pts] MACD
    if macd_now > sig_now and macd_prev <= sig_prev:
        score += 2
        indicators.append("✅ MACD crossover bullish +2")
    elif macd_now > sig_now:
        score += 1
        indicators.append("✅ MACD acima do sinal")
    if hist_now > 0 and hist_now > hist_prev:
        score += 1
        indicators.append("✅ Histograma crescendo")

    # [2 pts] Bollinger Bands
    if price <= bb_low_now * 1.01:
        score += 2
        indicators.append("✅ Preço na banda inferior BB +2")
    elif price < bb_mid_now:
        score += 1
        indicators.append("✅ Preço abaixo da média BB")

    # [2 pts] ADX — força da tendência
    if adx_now > 25 and plus_now > minus_now:
        score += 2
        indicators.append(f"✅ ADX forte bullish ({adx_now:.0f}) +2")
    elif adx_now > 20:
        score += 1
        indicators.append(f"✅ ADX moderado ({adx_now:.0f})")

    # [2 pts] OBV — volume confirma
    if obv_now > obv_ma:
        score += 1
        indicators.append("✅ OBV acima da média (volume bullish)")
    if obv_now > obv.iloc[-5]:
        score += 1
        indicators.append("✅ OBV em alta nos últimos 5 candles")

    # ================================================
    # CALCULAR ENTRADA, TARGET E STOP
    # ================================================
    entry  = round(price, 6)
    target = round(entry * (1 + TARGET_PROFIT + FEE_RATE * 2), 6)
    stop   = round(entry * (1 - STOP_LOSS), 6)
    rr     = round(TARGET_PROFIT / STOP_LOSS, 2)  # risk/reward ratio

    # ================================================
    # RETORNAR RESULTADO
    # ================================================
    if score >= MIN_SCORE_TO_SIGNAL:
        signal_type = "BUY"
    else:
        signal_type = "WAIT"

    return {
        "type":       signal_type,
        "asset":      symbol,
        "price":      entry,
        "score":      score,
        "max_score":  15,
        "rsi":        round(rsi_now, 1),
        "adx":        round(adx_now, 1),
        "atr":        round(atr_now, 6),
        "macd":       round(macd_now, 6),
        "daily_trend": daily_trend,
        "entry":      entry,
        "target":     target,
        "stop":       stop,
        "rr_ratio":   rr,
        "indicators": indicators,
    }


# =========================
# SCAN TOP 20
# =========================

def get_top20():
    """Busca top 20 moedas do CoinGecko"""
    fallback = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
                "DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT"]
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order":       "market_cap_desc",
                "per_page":    30,
                "page":        1,
                "sparkline":   False
            },
            timeout=10
        )

        data = r.json()

        # CoinGecko retornou erro (ex: rate limit) — usa fallback
        if not isinstance(data, list):
            print(f"⚠️ CoinGecko resposta inesperada: {data}")
            return fallback

        result = []
        for c in data:
            if not isinstance(c, dict):
                continue
            cg_id  = c.get("id", "")
            symbol = COINGECKO_TO_BINANCE.get(cg_id)
            if symbol:
                result.append(symbol)
            if len(result) >= 20:
                break

        return result if result else fallback

    except Exception as e:
        print(f"⚠️ CoinGecko error: {e}")
        return fallback


# =========================
# RADAR PRINCIPAL
# =========================

def run_radar(portfolio=None):
    """
    Escaneia top 20, retorna lista de sinais.
    Só emite BUY se score >= 10/15.
    """
    print("📡 ZAPID PRO — iniciando scan...")

    symbols    = get_top20()
    signals    = []
    best_score = 0
    best_asset = None

    for symbol in symbols:
        # pula se já temos posição aberta
        if portfolio and symbol in portfolio:
            continue

        try:
            result = analyze_asset(symbol)
            if result is None:
                continue

            if result["type"] == "BUY":
                signals.append(result)
                print(f"🟢 SINAL BUY: {symbol} — score {result['score']}/15")
            else:
                if result["score"] > best_score:
                    best_score = result["score"]
                    best_asset = result

            time.sleep(0.3)  # evitar rate limit Binance

        except Exception as e:
            print(f"⚠️ Erro {symbol}: {e}")

    # ordena por score
    signals.sort(key=lambda x: x["score"], reverse=True)

    if not signals:
        print(f"⏸ Sem sinais fortes. Melhor candidato: {best_asset['asset'] if best_asset else 'N/A'} score {best_score}/15")
        return [{
            "type":    "WAIT",
            "message": f"Nenhum ativo atingiu score mínimo ({MIN_SCORE_TO_SIGNAL}/15)",
            "top":     best_asset["asset"] if best_asset else "N/A",
            "score":   best_score
        }]

    print(f"✅ Scan concluído — {len(signals)} sinal(is) BUY encontrado(s)")
    return signals

