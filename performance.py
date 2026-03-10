import csv

FILE = "trades_log.csv"

def calculate_performance():

    wins = 0
    losses = 0
    total = 0

    try:

        with open(FILE, "r") as f:

            reader = csv.DictReader(f)

            for row in reader:

                if row["result"] == "WIN":
                    wins += 1

                if row["result"] == "LOSS":
                    losses += 1

        total = wins + losses

        if total == 0:
            winrate = 0
        else:
            winrate = round((wins / total) * 100, 2)

        return wins, losses, total, winrate

    except:
        return 0,0,0,0