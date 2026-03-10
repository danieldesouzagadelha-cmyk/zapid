import os

# =========================
# TELEGRAM
# =========================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# =========================
# BANCO DE DADOS
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")  # PostgreSQL do Render

# =========================
# ESTRATÉGIA
# =========================
TARGET_PROFIT = 0.06     # 6% de lucro alvo
STOP_LOSS = 0.03         # 3% stop loss
FEE_RATE = 0.002         # 0.2% taxa por operação (entrada + saída = 0.4%)
MIN_PROFIT_WITH_FEES = TARGET_PROFIT + (FEE_RATE * 2)  # 6.4%

# =========================
# SCANNER
# =========================
TOP_COINS = 20           # quantas moedas analisar
CACHE_SECONDS = 300      # cache de 5 minutos
BUY_SCORE_MIN = 7        # score mínimo para sinal de compra
SELL_SCORE_MIN = 7       # score mínimo para sinal de venda
