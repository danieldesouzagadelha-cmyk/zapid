import os
import time
import threading
from flask import Flask, jsonify

app = Flask(__name__)

# -----------------------------
# STATUS DO RADAR
# -----------------------------

radar_status = {
    "status": "online",
    "engine": "ZapID AI Radar",
    "version": "1.0",
    "signals": []
}

# -----------------------------
# COLETOR SIMULADO DE SINAIS
# -----------------------------

def radar_collector():
    while True:
        signal = {
            "market": "BTC",
            "action": "monitoring",
            "confidence": 0.73
        }

        radar_status["signals"].append(signal)

        # mantém só últimos 10 sinais
        radar_status["signals"] = radar_status["signals"][-10:]

        time.sleep(10)

# thread do radar
threading.Thread(target=radar_collector, daemon=True).start()

# -----------------------------
# ROTAS
# -----------------------------

@app.route("/")
def home():
    return "🚀 ZapID AI Radar is running"

@app.route("/status")
def status():
    return jsonify(radar_status)

@app.route("/signals")
def signals():
    return jsonify(radar_status["signals"])

# -----------------------------
# START SERVER
# -----------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
