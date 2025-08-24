import os
import requests
import time
import threading
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from dotenv import load_dotenv
from flask import Flask

# ----------------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
URL = "https://trouverunlogement.lescrous.fr/tools/41/search"
CHECK_INTERVAL = 60  # check every minute
# ----------------------------

seen_logements = set()

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Erreur envoi Telegram: {e}")

def get_logements():
    headers = {"User-Agent": "Mozilla/5.0"}
    page = requests.get(URL, headers=headers, timeout=10)
    soup = BeautifulSoup(page.text, "html.parser")
    
    logements = soup.find_all("div", class_="fr-card")
    results = []
    for log in logements:
        titre = log.find("h3").get_text(strip=True) if log.find("h3") else "Sans titre"
        lien_relatif = log.find("a")["href"] if log.find("a") else ""
        lien = urljoin(URL, lien_relatif)
        details = [d.get_text(strip=True) for d in log.find_all("p", class_="fr-card__detail")]
        details_txt = " | ".join(details) if details else "Pas de détails"
        identifiant = lien if lien else titre
        results.append((identifiant, titre, lien, details_txt))
    return results

def check_dispo():
    global seen_logements
    nouveaux = []
    logements = get_logements()
    for identifiant, titre, lien, details in logements:
        if identifiant not in seen_logements:
            nouveaux.append((titre, lien, details))
            seen_logements.add(identifiant)

    if nouveaux:
        for titre, lien, details in nouveaux:
            send_telegram_message(
                f"🏠 <b>Nouveau logement dispo</b>\n"
                f"📌 {titre}\n"
                f"ℹ️ {details}\n"
                f"🔗 <a href='{lien}'>Voir l'annonce</a>"
            )

def bot_loop():
    send_telegram_message("🚀 Bot CROUS démarré, je surveille Lille (tools/41)...")
    while True:
        try:
            check_dispo()
        except Exception as e:
            send_telegram_message(f"⚠️ Erreur du bot : {e}")
        time.sleep(CHECK_INTERVAL)

# ----------------------------
# Mini serveur Flask pour Render
# ----------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot CROUS en cours d'exécution"

if __name__ == "__main__":
    # Lancer le bot dans un thread séparé
    threading.Thread(target=bot_loop, daemon=True).start()

    # Lancer le serveur Flask (Render veut un port ouvert)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
