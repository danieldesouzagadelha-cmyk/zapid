import requests

# Top 10 moedas monitoradas
TOP_COINS = [
    "bitcoin",
    "ethereum",
    "solana",
    "binancecoin",
    "chainlink",
    "avalanche-2",
    "injective-protocol",
    "arbitrum",
    "optimism",
    "render-token"
]

def run_radar():

    print("📡 AI MARKET SCANNER RUNNING")

    url = "https://api.coingecko.com/api/v3/coins/markets"

    params = {
        "vs_currency": "usd",
        "ids": ",".join(TOP_COINS),
        "sparkline": "false"
    }

    try:

        response = requests.get(url, params=params, timeout=10)
        data = response.json()

    except Exception as e:

        print("Erro CoinGecko:", e)
        return []

    opportunities = []

    for coin in data:

        try:

            name = coin["symbol"].upper()
            price = coin["current_price"]
            volume = coin["total_volume"]
            change = coin["price_change_percentage_24h"]

            score = 0

            # tendência positiva
            if change and change > 2:
                score += 2

            # volume forte
            if volume and volume > 500000000:
                score += 2

            # movimento forte
            if change and change > 5:
                score += 3

            confidence = score * 12

            if confidence >= 60:

                signal = {
                    "asset": name,
                    "price": price,
                    "confidence": confidence
                }

                opportunities.append(signal)

        except Exception as e:
            print("Erro processamento moeda:", e)

    return opportunities
