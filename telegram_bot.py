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
        return
    cid = chat_id or TELEGRAM_CHAT_ID
    try:
        requests.post(f"{BASE_URL}/sendMessage", json={
            "chat_id":    cid,
            "text":       message,
            "parse_mode": parse_mode
        }, timeout=10)
    except Exception as e:
        print(f"❌ Telegram send error: {e}")


# =========================
# FORMATAR SINAL
# =========================

def format_signal(signal):
    t = signal.get("type")

    if t == "WAIT":
        return (
            f"⏸ <b>SEM SINAL FORTE</b>\n\n"
            f"Nenhum ativo atingiu score mínimo (10/15)\n\n"
            f"Melhor candidato: <b>{signal.get('top', 'N/A')}</b>\n"
            f"Score: {signal.get('score', 0)}/15\n\n"
            f"⏳ Próxima análise em 1h"
        )

    if t == "BUY":
        score      = signal.get("score", 0)
        max_score  = signal.get("max_score", 15)
        score_bar  = "🟩" * score + "⬜" * (max_score - score)

        # força do sinal
        if score >= 13:
            strength = "🔥 MUITO FORTE"
        elif score >= 11:
            strength = "💪 FORTE"
        else:
            strength = "✅ MODERADO"

        # indicadores que passaram
        indicators = signal.get("indicators", [])
        ind_text   = "\n".join(indicators) if indicators else "N/A"

        lines = [
            f"🟢 <b>SINAL DE COMPRA — SPOT BINANCE</b>",
            f"",
            f"🪙 <b>{signal.get('asset')}</b>",
            f"",
            f"📊 Score: <b>{score}/{max_score}</b> {strength}",
            f"{score_bar}",
            f"",
            f"💲 <b>Entrada:</b>  ${signal.get('entry', 0):,.4f}",
            f"🎯 <b>Target:</b>   ${signal.get('target', 0):,.4f}  (+6%)",
            f"🛡️ <b>Stop Loss:</b> ${signal.get('stop', 0):,.4f}  (-3%)",
            f"⚖️ <b>Risco/Retorno:</b> 1:{signal.get('rr_ratio', 2)}",
            f"",
            f"📈 Indicadores confirmados:",
            f"{ind_text}",
            f"",
            f"📉 RSI: {signal.get('rsi', 'N/A')} | ADX: {signal.get('adx', 'N/A')}",
            f"🌍 Tendência diária: {signal.get('daily_trend', 'N/A')}",
        ]

        if signal.get("ai_prediction"):
            lines += [
                f"",
                f"🤖 <b>Grok AI:</b> {signal['ai_prediction']}",
                f"🎯 Confiança: {signal.get('ai_confidence', 0):.0f}%",
                f"💬 {signal.get('ai_reasoning', '')}",
            ]

        lines += [
            f"",
            f"⚠️ <i>Este é um sinal técnico, não conselho financeiro.</i>",
            f"📝 Registrado no histórico para análise de acerto."
        ]

        return "\n".join(lines)

    return str(signal)


# =========================
# FORMATAR PERFORMANCE
# =========================

def format_performance(perf):
    wins   = perf.get("wins", 0)
    losses = perf.get("losses", 0)
    total  = wins + losses
    open_t = perf.get("open_trades", 0)

    # barra visual de winrate
    wr = perf.get("winrate", 0)
    filled = int(wr / 10)
    wr_bar = "🟩" * filled + "⬜" * (10 - filled)

    return (
        f"📊 <b>HISTÓRICO DE SINAIS — 30 DIAS</b>\n\n"
        f"✅ Wins:     {wins}\n"
        f"❌ Losses:   {losses}\n"
        f"📂 Abertos:  {open_t}\n"
        f"📋 Total:    {total}\n\n"
        f"🏆 <b>Winrate: {wr:.1f}%</b>\n"
        f"{wr_bar}\n\n"
        f"💰 Lucro médio por trade: {perf.get('avg_profit') or 0:.2f}%\n"
        f"📈 Lucro acumulado 30d:   {perf.get('total_profit') or 0:.2f}%\n\n"
        f"{'🟢 Performance positiva!' if wr >= 60 else '🔴 Ainda calibrando o modelo...'}"
    )
