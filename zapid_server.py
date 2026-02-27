from flask import Flask, request
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)

lembretes = []

def verificar_lembretes():
    while True:
        agora = datetime.now()
        for lembrete in lembretes[:]:
            horario, numero, mensagem = lembrete
            if agora >= horario:
                print(f"🔔 Enviar para {numero}: {mensagem}")
                lembretes.remove(lembrete)
        time.sleep(1)

threading.Thread(target=verificar_lembretes, daemon=True).start()

@app.route("/webhook", methods=["POST"])
def webhook():
    mensagem = request.form.get("Body")
    numero = request.form.get("From")

    print("📩 Mensagem recebida:", mensagem)

    if mensagem and mensagem.startswith("lembrar"):
        try:
            partes = mensagem.split()
            segundos = int(partes[-1])
            texto = " ".join(partes[1:-1])
            horario = datetime.now() + timedelta(seconds=segundos)
            lembretes.append((horario, numero, texto))
            return "✅ Lembrete agendado!"
        except:
            return "❌ Use: lembrar <mensagem> <segundos>"

    return "🤖 ZapID ativo!"

if __name__ == "__main__":
    app.run(port=5000)