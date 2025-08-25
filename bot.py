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
is_first_run = True

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, data=data, timeout=10)
        print(f"Message sent: {response.status_code}")
    except Exception as e:
        print(f"Erreur envoi Telegram: {e}")

def get_logements():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        page = requests.get(URL, headers=headers, timeout=15)
        page.raise_for_status()
        soup = BeautifulSoup(page.text, "html.parser")
        
        logements = soup.find_all("div", class_="fr-card")
        results = []
        
        for log in logements:
            # Get title
            titre_elem = log.find("h3")
            if not titre_elem:
                continue
            titre = titre_elem.get_text(strip=True)
            
            # Get link
            lien_elem = log.find("a")
            lien_relatif = lien_elem["href"] if lien_elem else ""
            lien = urljoin(URL, lien_relatif) if lien_relatif else ""
            
            # Get details
            details = [d.get_text(strip=True) for d in log.find_all("p", class_="fr-card__detail")]
            details_txt = " | ".join(details) if details else "Pas de détails"
            
            # Create a more reliable identifier using title + first detail
            # This is more stable than using the full URL
            identifier_parts = [titre]
            if details:
                identifier_parts.append(details[0])  # Add first detail for uniqueness
            identifiant = " - ".join(identifier_parts)
            
            results.append((identifiant, titre, lien, details_txt))
            
        return results
    except Exception as e:
        print(f"Erreur lors du scraping: {e}")
        return []

def check_dispo():
    global seen_logements, is_first_run
    
    logements = get_logements()
    
    if not logements:
        print("Aucun logement trouvé ou erreur de scraping")
        return
    
    if is_first_run:
        # First run: just populate the seen_logements without sending notifications
        for identifiant, titre, lien, details in logements:
            seen_logements.add(identifiant)
        send_telegram_message(f"🔍 Bot initialisé avec {len(seen_logements)} logements existants")
        is_first_run = False
        print(f"Premier run: {len(seen_logements)} logements ajoutés à la liste")
        return
    
    # Check for new logements
    nouveaux = []
    for identifiant, titre, lien, details in logements:
        if identifiant not in seen_logements:
            nouveaux.append((titre, lien, details))
            seen_logements.add(identifiant)
    
    # Send notifications for new logements
    if nouveaux:
        print(f"Trouvé {len(nouveaux)} nouveaux logements")
        for titre, lien, details in nouveaux:
            message = (
                f"🏠 <b>Nouveau logement dispo</b>\n"
                f"📌 {titre}\n"
                f"ℹ️ {details}\n"
                f"🔗 <a href='{lien}'>Voir l'annonce</a>"
            )
            send_telegram_message(message)
            time.sleep(1)  # Small delay between messages to avoid rate limiting
    else:
        print(f"Aucun nouveau logement. Total surveillé: {len(seen_logements)}")

def bot_loop():
    send_telegram_message("🚀 Bot CROUS démarré, je surveille Lille (tools/41)...")
    
    while True:
        try:
            print(f"Vérification à {time.strftime('%H:%M:%S')}")
            check_dispo()
        except Exception as e:
            error_msg = f"⚠️ Erreur du bot : {str(e)}"
            print(error_msg)
            send_telegram_message(error_msg)
        
        time.sleep(CHECK_INTERVAL)

# ----------------------------
# Mini serveur Flask pour Render
# ----------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return f"✅ Bot CROUS en cours d'exécution - {len(seen_logements)} logements surveillés"

@app.route("/status")
def status():
    return {
        "status": "running",
        "seen_logements": len(seen_logements),
        "url": URL,
        "check_interval": CHECK_INTERVAL
    }

if __name__ == "__main__":
    # Lancer le bot dans un thread séparé
    bot_thread = threading.Thread(target=bot_loop, daemon=True)
    bot_thread.start()

    # Lancer le serveur Flask (Render veut un port ouvert)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)