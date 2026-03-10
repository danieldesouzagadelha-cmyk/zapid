def predict_move(data):

    trend = data["trend"]
    rsi = data["rsi"]
    pullback = data["pullback"]
    volume = data["volume"]
    whales = data["whales"]

    score = 0

    if trend >= 2:
        score += 2

    if rsi < 40:
        score += 1

    if pullback < -0.01:
        score += 1

    if volume > 1.5:
        score += 1

    if whales > 2:
        score += 1

    if score >= 4:
        return "STRONG UP"

    if score == 3:
        return "UP"

    return "NEUTRAL"