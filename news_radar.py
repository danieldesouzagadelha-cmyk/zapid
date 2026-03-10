import os
import requests
import feedparser
import time

# =========================
# FONTES RSS
# =========================

RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://coindesk.com/arc/outboundfeeds/rss/",
    "https://decrypt.co/feed",
    "https://bitcoinmagazine.com/.rss/full/",
    "https://cryptonews.com/news/feed/",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.marketwatch.com/rss/topstories",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.reuters.com/reuters/worldNews",
]

KEYWORDS_IMPACT = [
    "bitcoin", "btc", "ethereum", "eth", "crypto", "blockchain",
    "solana", "ripple", "binance", "altcoin", "defi",
    "fed", "federal reserve", "interest rate", "inflation", "recession",
    "dollar", "economy", "market", "stock", "nasdaq", "oil", "gold",
    "war", "sanction", "conflict", "nato", "russia", "china", "taiwan",
    "government", "president", "regulation", "law", "ban", "central bank",
]

KEYWORDS_BULLISH = [
    "surge", "rally", "record", "bull", "breakout", "adoption", "approval",
    "growth", "rise", "gain", "agreement", "peace", "deal", "stimulus"
]

KEYWORDS_BEARISH = [
    "crash", "dump", "ban", "war", "attack", "sanction", "hack", "fraud",
    "recession", "crisis", "collapse", "fear", "drop", "conflict", "default"
]

GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_API_URL = "https://api.x.ai/v1/chat/completions"


# =========================
# CACHE — evita repetição
# =========================

def get_posted_links():
    """Busca links já postados do banco de dados"""
    try:
        from database import get_conn
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS news_cache (
                        id         SERIAL PRIMARY KEY,
                        link       TEXT UNIQUE NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                conn.commit()
                cur.execute("SELECT link FROM news_cache WHERE created_at > NOW() - INTERVAL '24 hours'")
                return {row["link"] for row in cur.fetchall()}
    except Exception as e:
        print(f"⚠️ Cache error: {e}")
        return set()


def mark_as_posted(link):
    """Marca link como postado"""
    try:
        from database import get_conn
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO news_cache (link) VALUES (%s) ON CONFLICT DO NOTHING", (link,))
            conn.commit()
    except Exception as e:
        print(f"⚠️ Mark posted error: {e}")


# =========================
# BUSCAR NOTÍCIAS
# =========================

def fetch_news():
    posted = get_posted_links()
    news   = []

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                title   = entry.get("title", "").strip()
                link    = entry.get("link", "").strip()
                summary = entry.get("summary", "").strip()[:400]

                if not title or not link:
                    continue
                if link in posted:
                    continue

                # filtra só notícias com impacto no mercado
                text = (title + " " + summary).lower()
                if not any(kw in text for kw in KEYWORDS_IMPACT):
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
# SENTIMENTO
# =========================

def analyze_sentiment(title, summary):
    text    = (title + " " + summary).lower()
    bullish = sum(1 for kw in KEYWORDS_BULLISH if kw in text)
    bearish = sum(1 for kw in KEYWORDS_BEARISH if kw in text)
    if bullish > bearish:
        return "bullish"
    elif bearish > bullish:
        return "bearish"
    return "neutral"


# =========================
# GROK — PROCESSAR NOTÍCIA
# =========================

def process_news_with_grok(news_item, sentiment):
    """
    Grok retorna JSON com:
    - titulo_pt: título traduzido
    - resumo_pt: resumo em português
    - post_x: texto pronto para copiar no X
    """
    if not GROK_API_KEY:
        return None

    prompt = f"""Você é um especialista em criptomoedas e mercados financeiros.

Analise esta notícia e responda em JSON válido:

TÍTULO: {news_item['title']}
RESUMO: {news_item['summary']}
SENTIMENTO: {sentiment}

Retorne EXATAMENTE este JSON (sem markdown, sem explicações):
{{
  "titulo_pt": "título traduzido para português natural",
  "resumo_pt": "resumo em 2 frases em português explicando o que aconteceu e o impacto no mercado cripto",
  "post_x": "post pronto para o X em português com emojis, máximo 240 caracteres, termine com #Bitcoin #Cripto e mais 1 hashtag relevante"
}}"""

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
                "max_tokens":  300,
                "temperature": 0.5
            },
            timeout=20
        )
        r.raise_for_status()

        import json
        text = r.json()["choices"][0]["message"]["content"].strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)

    except Exception as e:
        print(f"❌ Erro Grok: {e}")
        return None


# =========================
# ENVIAR PARA TELEGRAM
# =========================

def send_news_to_telegram(news_item, grok_result, sentiment):
    from telegram_bot import send_telegram

    emoji = "🟢" if sentiment == "bullish" else "🔴" if sentiment == "bearish" else "📰"
    label = "ALTA 🚀" if sentiment == "bullish" else "QUEDA ⚠️" if sentiment == "bearish" else "NEUTRO"

    if grok_result:
        titulo  = grok_result.get("titulo_pt", news_item["title"])
        resumo  = grok_result.get("resumo_pt", "")
        post_x  = grok_result.get("post_x", "")

        # garante que o post tem o link
        if news_item["link"] not in post_x:
            post_x = f"{post_x}\n\n{news_item['link']}"
    else:
        # fallback sem Grok
        titulo = news_item["title"]
        resumo = news_item["summary"][:200]
        post_x = f"{emoji} {titulo[:180]}\n\n{news_item['link']}\n\n#Bitcoin #Cripto #Mercado"

    msg = (
        f"{emoji} <b>NOTÍCIA — {label}</b>\n"
        f"📰 {news_item['source']}\n\n"
        f"<b>{titulo}</b>\n\n"
        f"📝 {resumo}\n\n"
        f"─────────────────\n"
        f"✂️ <b>Copie e poste no X:</b>\n\n"
        f"<code>{post_x}</code>"
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
        sentiment   = analyze_sentiment(news["title"], news["summary"])
        grok_result = process_news_with_grok(news, sentiment)

        send_news_to_telegram(news, grok_result, sentiment)
        mark_as_posted(news["link"])

        posted += 1
        time.sleep(15)

        if posted >= 3:
            break

    print(f"✅ News radar — {posted} notícia(s) enviada(s)")
    return posted
