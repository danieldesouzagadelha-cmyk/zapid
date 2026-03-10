import csv
import os
import time

FILE = "trades_log.csv"

def log_trade(symbol, entry, target, stop):

    exists = os.path.isfile(FILE)

    with open(FILE, "a", newline="") as f:

        writer = csv.writer(f)

        if not exists:
            writer.writerow(["time","symbol","entry","target","stop","result"])

        writer.writerow([
            int(time.time()),
            symbol,
            entry,
            target,
            stop,
            "OPEN"
        ])