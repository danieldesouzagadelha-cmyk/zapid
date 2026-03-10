import os
import requests
import feedparser
import time

# =========================
# FONTES RSS — CRYPTO + MACRO
# =========================

RSS_FEEDS = [
    # Crypto
    "https://cointelegraph.com/rss",
    "https://coindesk.com/arc/outboundfeeds/rss/",
    "https://decrypt.co/feed",
    "https://bitcoinmagazine.com/.rss/full/",
    "https://cryptonews.com/news/feed/",

    # Mercado global / economia
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.investing.com/rss/news.rss",
    "https://www.marketwatch.com/rss/topstories",

    # Geopolítica / mundo
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.reuters.com/reuters/worldNews",
    "https://feeds.skynews.com/feeds/rss/world.xml",
]

# palavras que indicam impacto no mercado financeiro
KEYWORDS_IMPACT = [
    # cripto direto
    "bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain",
    "solana", "ripple", "binance", "altcoin", "defi", "nft",
    # economia
    "fed", "federal reserve", "interest rate", "inflation", "gdp",
    "recession", "dollar", "treasury", "debt", "economy", "market",
    "stock", "nasdaq", "s&p", "oil", "gold", "commodity",
    # geopolítica
    "war", "sanction", "conflict", "nato", "russia", "ukraine",
    "china", "taiwan", "iran", "north korea", "middle east",
    "trade war", "tariff", "embargo",
    # governo / regulação
    "government", "president", "congress", "senate", "election",
    "regulation", "law", "ban", "policy", "central bank",
    "imf", "world bank", "g7", "g20",
]

KEYWORDS_BULLISH = [
    "surge", "rally", "record high", "bull", "breakout", "adoption",
    "approval", "growth", "rise", "gain", "positive", "agreement",
    "peace", "deal", "partnership", "stimulus", "cut rate"
]

KEYWORDS_BEARISH = [
    "crash", "dump", "ban", "war", "attack", "sanction", "hack",
    "fraud", "recession", "crisis", "collapse", "fear", "drop",
    "investigation", "arrest", "conflict", "escalation", "default"
]

posted_cache = set()

GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_API_URL = "https://api.x.ai/v1/chat/completions"


# =========================
# BUSCAR NOTÍCIAS
# =========================

def fetch_news():
    news = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                title   = entry.get("title", "")
                link    = entry.get("link", "")
                summary = entry.get("summary", "")[:300]

                if not title or not link:
                    continue
                if link in posted_cache:
                    continue

                news.append({
                    "title":   title,
                    "link":    link,
                    "summary": summary,
                    "source":  feed.feed.get("title", "News")
                })
        except Exception as e:
            print(f"⚠️ Erro feed {feed_url}: {e}")
    return news


# =========================
# RELEVÂNCIA + SENTIMENTO
# =========================

def analyze_news(title, summary):
    text = (title + " " + summary).lower()

    # verifica se tem impacto no mercado
    has_impact = any(kw in text for kw in KEYWORDS_IMPACT)
    if not has_impact:
        return None

    bullish = sum(1 for kw in KEYWORDS_BULLISH if kw in text)
    bearish = sum(1 for kw in KEYWORDS_BEARISH if kw in text)

    if bullish > bearish:
        return "bullish"
    elif bearish > bullish:
        return "bearish"
    return "neutral"


# =========================
# GROK — CRIAR POST PARA O X
# =========================

def create_x_post(news_item, sentiment):
    emoji = "🟢" if sentiment == "bullish" else "🔴" if sentiment == "bearish" else "📰"

    if not GROK_API_KEY:
        return (
            f"{emoji} {news_item['title'][:200]}\n\n"
            f"{news_item['link']}\n\n"
            f"#Crypto #Mercado #Economia"
        )

    prompt = f"""Você é um analista financeiro especialista em criptomoedas e mercados globais.

Crie um post para o X (Twitter) sobre esta notícia e explique como ela pode impactar o mercado cripto:

TÍTULO: {news_item['title']}
RESUMO: {news_item['summary']}
SENTIMENTO: {sentiment}
FONTE: {news_item['source']}

Regras OBRIGATÓRIAS:
- Escreva em português do Brasil
- Máximo 240 caracteres (sem contar o link)
- Use emojis relevantes
- Conecte a notícia ao impacto no Bitcoin/cripto quando relevante
- Termine com 2-3 hashtags como #Bitcoin #Crypto #Mercado
- NÃO inclua o link no texto
- NÃO use aspas nem explicações extras

Responda APENAS com o texto do post."""

    try:
        r = requests.post(
            GROK_API_URL,
            headers={
                "Authorization": f"Bearer {GROK_API_KEY}",
                "Content-Type":  "application/json"
            },
            json={
                "model":       "grok-3-mini",
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  150,
                "temperature": 0.8
            },
            timeout=15
        )
        r.raise_for_status()
        post_text = r.json()["choices"][0]["message"]["content"].strip()

        if len(post_text) > 240:
            post_text = post_text[:237] + "..."

        return f"{post_text}\n\n{news_item['link']}"

    except Exception as e:
        print(f"❌ Erro Grok news: {e}")
        return (
            f"{emoji} {news_item['title'][:200]}\n\n"
            f"{news_item['link']}\n\n"
            f"#Bitcoin #Crypto #Mercado"
        )


# =========================
# ENVIAR PARA TELEGRAM
# =========================

def send_news_to_telegram(post_text, sentiment, source, title):
    from telegram_bot import send_telegram

    emoji = "🟢" if sentiment == "bullish" else "🔴" if sentiment == "bearish" else "📰"
    label = "ALTA 🚀" if sentiment == "bullish" else "QUEDA ⚠️" if sentiment == "bearish" else "NEUTRO"

    msg = (
        f"{emoji} <b>NOTÍCIA — {label}</b>\n"
        f"📰 {source}\n\n"
        f"<b>{title}</b>\n\n"
        f"─────────────────\n"
        f"✂️ <b>Copie e poste no X:</b>\n\n"
        f"{post_text}"
    )

    send_telegram(msg)


# =========================
# RADAR PRINCIPAL
# =========================

def run_news_radar():
    print("📰 News radar iniciando...")

    news_list = fetch_news()
    if not news_list:
        print("📭 Sem notícias novas")
        return 0

    posted = 0

    for news in news_list:
        sentiment = analyze_news(news["title"], news["summary"])

        # posta bullish e bearish, ignora sem impacto
        if sentiment not in ["bullish", "bearish"]:
            continue

        post_text = create_x_post(news, sentiment)
        send_news_to_telegram(post_text, sentiment, news["source"], news["title"])

        posted_cache.add(news["link"])
        posted += 1

        time.sleep(15)

        if posted >= 3:
            break

    print(f"✅ News radar — {posted} notícia(s) enviada(s)")
    return posted
