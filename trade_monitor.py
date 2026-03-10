import csv
import requests

FILE = "trades_log.csv"

def get_price(symbol):

    url = "https://api.binance.com/api/v3/ticker/price"

    params = {"symbol": symbol}

    r = requests.get(url, params=params)

    data = r.json()

    return float(data["price"])


def update_trades():

    rows = []

    with open(FILE, "r") as f:

        reader = csv.DictReader(f)

        for row in reader:

            if row["result"] == "OPEN":

                symbol = row["symbol"]

                price = get_price(symbol)

                target = float(row["target"])
                stop = float(row["stop"])

                if price >= target:

                    row["result"] = "WIN"

                elif price <= stop:

                    row["result"] = "LOSS"

            rows.append(row)

    with open(FILE, "w", newline="") as f:

        writer = csv.DictWriter(
            f,
            fieldnames=["time","symbol","entry","target","stop","result"]
        )

        writer.writeheader()

        writer.writerows(rows)