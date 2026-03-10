import requests
from database import get_open_trades, close_trade
from telegram_bot import send_telegram
from config import TARGET_PROFIT, STOP_LOSS, FEE_RATE

# =========================
# PREÇO ATUAL (Binance)
# =========================

def get_price_binance(symbol):
    """Pega preço em tempo real da Binance — mais confiável que CoinGecko para monitoramento"""
    try:
        # normaliza símbolo: "bitcoin" → "BTCUSDT", "BITCOIN" → "BTCUSDT"
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = symbol + "USDT"

        url = "https://api.binance.com/api/v3/ticker/price"
        r = requests.get(url, params={"symbol": symbol}, timeout=5)
        data = r.json()

        if "price" in data:
            return float(data["price"])
        return None

    except Exception as e:
        print(f"❌ Erro preço Binance {symbol}: {e}")
        return None


# =========================
# MONITOR DE TRADES ABERTOS
# =========================

def update_open_trades():
    """
    Verifica todos os trades abertos.
    Se atingiu target (WIN) ou stop (LOSS), fecha e notifica.
    """
    trades = get_open_trades()

    if not trades:
        print("📭 Nenhum trade aberto para monitorar")
        return []

    closed = []

    for trade in trades:
        trade_id  = trade["id"]
        symbol    = trade["symbol"]
        entry     = float(trade["entry_price"])
        target    = float(trade["target_price"])
        stop      = float(trade["stop_price"])

        # calcula target e stop dinâmicos se não existirem
        if not target:
            target = entry * (1 + TARGET_PROFIT + FEE_RATE * 2)
        if not stop:
            stop = entry * (1 - STOP_LOSS)

        current = get_price_binance(symbol)

        if not current:
            print(f"⚠️ Sem preço para {symbol}")
            continue

        profit_pct = ((current - entry) / entry) * 100

        print(f"  {symbol}: entrada=${entry:.4f} | atual=${current:.4f} | {profit_pct:+.2f}%")

        # ======= WIN =======
        if current >= target:
            close_trade(trade_id, current, "WIN")
            msg = (
                f"🟢 TRADE FECHADO — WIN\n\n"
                f"🪙 {symbol}\n"
                f"📥 Entrada: ${entry:.4f}\n"
                f"📤 Saída:   ${current:.4f}\n"
                f"💰 Lucro:   +{profit_pct:.2f}%\n"
                f"🎯 Meta de {TARGET_PROFIT*100:.0f}% atingida!"
            )
            send_telegram(msg)
            closed.append({"trade_id": trade_id, "symbol": symbol, "result": "WIN", "profit": profit_pct})
            print(f"  ✅ WIN — {symbol} +{profit_pct:.2f}%")

        # ======= LOSS =======
        elif current <= stop:
            close_trade(trade_id, current, "LOSS")
            msg = (
                f"🔴 TRADE FECHADO — LOSS\n\n"
                f"🪙 {symbol}\n"
                f"📥 Entrada: ${entry:.4f}\n"
                f"📤 Saída:   ${current:.4f}\n"
                f"📉 Perda:   {profit_pct:.2f}%\n"
                f"🛡️ Stop loss ativado"
            )
            send_telegram(msg)
            closed.append({"trade_id": trade_id, "symbol": symbol, "result": "LOSS", "profit": profit_pct})
            print(f"  ❌ LOSS — {symbol} {profit_pct:.2f}%")

        # ======= ALERTA PRÓXIMO DO STOP =======
        elif profit_pct < -2.0:
            msg = (
                f"⚠️ ALERTA STOP PRÓXIMO\n\n"
                f"🪙 {symbol}\n"
                f"📉 {profit_pct:.2f}% — stop em {-STOP_LOSS*100:.0f}%"
            )
            send_telegram(msg)

    return closed
