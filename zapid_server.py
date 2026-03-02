@app.route("/webhook", methods=["POST"])
def webhook():

    incoming_msg = request.form.get("Body", "")
    msg_lower = incoming_msg.lower()

    # 🔥 PEDIDO EXPLÍCITO DE PREÇO
    if any(p in msg_lower for p in ["preço", "valor", "cotação", "btc agora", "quanto está"]):
        price = get_btc_price()

        if price:
            resposta = f"💰 BTC agora: ${price}"
        else:
            resposta = "Erro ao buscar preço do BTC."

    # 🔥 PEDIDO DE ANÁLISE
    elif any(p in msg_lower for p in ["análise", "analise", "vale a pena", "bom momento", "comprar"]):
        price = get_btc_price()

        analysis_prompt = f"""
O preço atual do BTC é {price}.
Com base nisso, faça uma análise estratégica curta.
Não invente valores.
"""

        resposta = ask_groq(analysis_prompt)

    # 📰 NOTÍCIAS
    elif any(p in msg_lower for p in ["noticia", "notícias", "news"]):
        news = get_news_by_category("crypto")

        if news:
            resposta = f"📰 {news['title']}\n\n{news['description']}"
        else:
            resposta = "Não encontrei notícias recentes."

    # 🤖 CONVERSA NORMAL
    else:
        resposta = ask_groq(incoming_msg) or "Erro ao processar mensagem."

    twilio_response = MessagingResponse()
    twilio_response.message(resposta)

    return str(twilio_response)
