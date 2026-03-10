import os
import requests
import json

GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

# =========================
# SCORE LOCAL (fallback)
# =========================

def predict_move_local(data):
    """Score local quando Grok não está disponível"""
    score = 0

    trend   = data.get("trend", 0)
    rsi_v   = data.get("rsi", 50)
    pullback= data.get("pullback", 0)
    volume  = data.get("volume", 1)
    whales  = data.get("whales", 0)

    if trend >= 2:    score += 2
    if rsi_v < 40:    score += 1
    if pullback < -0.01: score += 1
    if volume > 1.5:  score += 1
    if whales > 2:    score += 1

    if score >= 4: return "STRONG UP"
    if score == 3: return "UP"
    return "NEUTRAL"


# =========================
# ANÁLISE GROK
# =========================

def analyze_with_grok(signal, market_context=""):
    """
    Envia o sinal para o Grok analisar e confirmar/rejeitar
    signal: dict com type, asset, price, score, rsi
    Retorna: dict com prediction, confidence, reasoning
    """
    if not GROK_API_KEY:
        print("⚠️ GROK_API_KEY não configurada — usando análise local")
        return {
            "prediction": predict_move_local({"trend": signal.get("score", 0), "rsi": signal.get("rsi", 50), "pullback": 0, "volume": 1, "whales": 0}),
            "confidence": signal.get("score", 0) / 16 * 100,
            "reasoning":  "Análise técnica local (Grok não configurado)",
            "source":     "local"
        }

    signal_type = signal.get("type", "WAIT")
    asset       = signal.get("asset", "")
    price       = signal.get("price", 0)
    score       = signal.get("score", 0)
    rsi_val     = signal.get("rsi", 50)
    details     = signal.get("details", [])

    prompt = f"""Você é um analista especialista em criptomoedas. Analise o seguinte sinal técnico e dê sua opinião:

ATIVO: {asset}
SINAL: {signal_type}
PREÇO ATUAL: ${price}
SCORE TÉCNICO: {score}/16
RSI: {rsi_val}
INDICADORES ATIVOS:
{chr(10).join(details) if details else "Sem detalhes"}

{f"CONTEXTO DE MERCADO: {market_context}" if market_context else ""}

Responda SOMENTE em JSON válido com este formato exato:
{{
  "prediction": "COMPRAR" | "VENDER" | "AGUARDAR",
  "confidence": número de 0 a 100,
  "risk": "BAIXO" | "MÉDIO" | "ALTO",
  "reasoning": "explicação em 1 frase curta",
  "tp_suggestion": número percentual de take profit sugerido,
  "sl_suggestion": número percentual de stop loss sugerido
}}"""

    try:
        headers = {
            "Authorization": f"Bearer {GROK_API_KEY}",
            "Content-Type": "application/json"
        }

        body = {
            "model": "grok-3-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "Você é um analista técnico de criptomoedas. Responda SOMENTE com JSON válido, sem explicações adicionais."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 300,
            "temperature": 0.2
        }

        r = requests.post(GROK_API_URL, headers=headers, json=body, timeout=15)
        r.raise_for_status()

        content = r.json()["choices"][0]["message"]["content"].strip()

        # limpar possível markdown
        content = content.replace("```json", "").replace("```", "").strip()

        result = json.loads(content)
        result["source"] = "grok"
        return result

    except json.JSONDecodeError as e:
        print(f"❌ Grok retornou JSON inválido: {e}")
        return _fallback(signal)

    except Exception as e:
        print(f"❌ Erro Grok API: {e}")
        return _fallback(signal)


def _fallback(signal):
    return {
        "prediction": signal.get("type", "AGUARDAR"),
        "confidence": round(signal.get("score", 0) / 16 * 100, 1),
        "risk": "MÉDIO",
        "reasoning": "Análise técnica local (Grok indisponível)",
        "tp_suggestion": 6.0,
        "sl_suggestion": 3.0,
        "source": "local"
    }


# =========================
# ENRIQUECER SINAIS
# =========================

def enrich_signals(signals):
    """Adiciona análise do Grok em cada sinal"""
    enriched = []

    for signal in signals:
        if signal.get("type") == "WAIT":
            enriched.append(signal)
            continue

        analysis = analyze_with_grok(signal)

        enriched.append({
            **signal,
            "ai_prediction":  analysis.get("prediction"),
            "ai_confidence":  analysis.get("confidence"),
            "ai_risk":        analysis.get("risk"),
            "ai_reasoning":   analysis.get("reasoning"),
            "ai_tp":          analysis.get("tp_suggestion"),
            "ai_sl":          analysis.get("sl_suggestion"),
            "ai_source":      analysis.get("source"),
        })

    return enriched
