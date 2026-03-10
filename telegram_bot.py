import os
import requests
import threading
import time
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# =========================
# ENVIAR MENSAGEM
# =========================

def send_telegram(message, chat_id=None, parse_mode="HTML"):
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ TELEGRAM_BOT_TOKEN não configurado")
        return

    cid = chat_id or TELEGRAM_CHAT_ID
    url = f"{BASE_URL}/sendMessage"

    try:
        r = requests.post(url, json={
            "chat_id": cid,
            "text": message,
            "parse_mode": parse_mode
        }, timeout=10)

        if not r.ok:
            print(f"❌ Telegram erro: {r.text}")

    except Exception as e:
        print(f"❌ Telegram send error: {e}")


# =========================
# FORMATAR SINAIS
# =========================

def format_signal(signal):
    t = signal.get("type")

    if t == "WAIT":
        return (
            f"⏸ <b>AGUARDAR</b>\n"
            f"{signal.get('message', 'Sem oportunidade clara')}\n"
            f"Melhor candidato: {signal.get('top', 'N/A')} (score {signal.get('score', 0)})"
        )

    emoji = "🟢" if t == "BUY" else "🔴"
    action = "COMPRA" if t == "BUY" else "VENDA"

    lines = [
        f"{emoji} <b>SINAL DE {action}</b>",
        f"",
        f"🪙 <b>{signal.get('asset')}</b>",
        f"💲 Preço: ${signal.get('price', 0):,.4f}",
        f"📊 Score: {signal.get('score', 0)}/16",
        f"📈 RSI: {signal.get('rsi', 'N/A')}",
    ]

    if signal.get("profit") is not None:
        lines.append(f"💰 Lucro atual: +{signal['profit']:.2f}%")

    # análise Grok
    if signal.get("ai_prediction"):
        lines += [
            f"",
            f"🤖 <b>Grok AI:</b> {signal['ai_prediction']}",
            f"🎯 Confiança: {signal.get('ai_confidence', 0):.0f}%",
            f"⚠️ Risco: {signal.get('ai_risk', 'N/A')}",
            f"💬 {signal.get('ai_reasoning', '')}",
        ]

        if t == "BUY":
            lines.append(f"🎯 TP sugerido: +{signal.get('ai_tp', 6):.1f}%")
            lines.append(f"🛡️ SL sugerido: -{signal.get('ai_sl', 3):.1f}%")

    return "\n".join(lines)


def format_performance(perf):
    return (
        f"📊 <b>PERFORMANCE ZAPID</b>\n\n"
        f"✅ Wins:    {perf.get('wins', 0)}\n"
        f"❌ Losses:  {perf.get('losses', 0)}\n"
        f"📂 Abertos: {perf.get('open_trades', 0)}\n"
        f"🏆 Winrate: {perf.get('winrate', 0):.1f}%\n"
        f"💰 Lucro médio: {perf.get('avg_profit') or 0:.2f}%\n"
        f"📈 Lucro total:  {perf.get('total_profit') or 0:.2f}%"
    )


# =========================
# RECEBER COMANDOS
# =========================

last_update_id = 0

def get_updates():
    global last_update_id
    try:
        r = requests.get(f"{BASE_URL}/getUpdates", params={
            "offset": last_update_id + 1,
            "timeout": 30
        }, timeout=35)

        data = r.json()
        return data.get("result", [])

    except Exception as e:
        print(f"❌ getUpdates error: {e}")
        return []


def handle_command(text, chat_id):
    """Processa comandos recebidos no Telegram"""
    # importações aqui para evitar circular imports
    from market_scanner import run_radar
    from ai_predictor import enrich_signals
    from database import get_open_trades, get_performance, get_portfolio
    from trade_monitor import update_open_trades

    text = text.strip().lower()
    print(f"📨 Comando recebido: {text}")

    # /start ou /help
    if text in ["/start", "/help"]:
        send_telegram(
            "👋 <b>ZapID Pro — Comandos disponíveis:</b>\n\n"
            "/radar — Escanear mercado agora\n"
            "/carteira — Ver trades abertos\n"
            "/performance — Ver resultados\n"
            "/monitor — Atualizar trades abertos\n"
            "/status — Status do bot",
            chat_id=chat_id
        )

    # /radar
    elif text == "/radar":
        send_telegram("🔍 Escaneando mercado... aguarde ~30s", chat_id=chat_id)
        try:
            portfolio = get_portfolio()
            signals   = run_radar(portfolio)
            enriched  = enrich_signals(signals)

            send_telegram(f"📡 <b>{len(enriched)} sinal(is) encontrado(s):</b>", chat_id=chat_id)
            for s in enriched:
                send_telegram(format_signal(s), chat_id=chat_id)
        except Exception as e:
            send_telegram(f"❌ Erro no radar: {e}", chat_id=chat_id)

    # /carteira
    elif text == "/carteira":
        try:
            trades = get_open_trades()
            if not trades:
                send_telegram("📭 Nenhum trade aberto", chat_id=chat_id)
                return

            msg = "💼 <b>TRADES ABERTOS:</b>\n\n"
            for t in trades:
                msg += (
                    f"🪙 {t['symbol']}\n"
                    f"   Entrada: ${float(t['entry_price']):.4f}\n"
                    f"   Target:  ${float(t['target_price']):.4f}\n"
                    f"   Stop:    ${float(t['stop_price']):.4f}\n\n"
                )
            send_telegram(msg, chat_id=chat_id)
        except Exception as e:
            send_telegram(f"❌ Erro: {e}", chat_id=chat_id)

    # /performance
    elif text == "/performance":
        try:
            perf = get_performance()
            send_telegram(format_performance(perf), chat_id=chat_id)
        except Exception as e:
            send_telegram(f"❌ Erro: {e}", chat_id=chat_id)

    # /monitor
    elif text == "/monitor":
        send_telegram("🔄 Verificando trades abertos...", chat_id=chat_id)
        try:
            closed = update_open_trades()
            if not closed:
                send_telegram("✅ Nenhum trade fechado nesta verificação", chat_id=chat_id)
        except Exception as e:
            send_telegram(f"❌ Erro: {e}", chat_id=chat_id)

    # /status
    elif text == "/status":
        send_telegram(
            "✅ <b>ZapID Pro está online</b>\n"
            "🔄 Radar automático a cada hora\n"
            "📡 CoinGecko + Binance conectados\n"
            "🤖 Grok AI ativo",
            chat_id=chat_id
        )

    else:
        send_telegram("❓ Comando não reconhecido. Use /help", chat_id=chat_id)


def poll_commands():
    """Loop de polling para receber comandos do Telegram"""
    global last_update_id

    print("🤖 Bot Telegram iniciado — aguardando comandos...")

    while True:
        try:
            updates = get_updates()

            for update in updates:
                last_update_id = update["update_id"]
                msg = update.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")

                if text and chat_id:
                    handle_command(text, chat_id)

        except Exception as e:
            print(f"❌ Poll error: {e}")

        time.sleep(2)


def start_bot():
    """Inicia o bot em thread separada"""
    t = threading.Thread(target=poll_commands, daemon=True)
    t.start()
