# === mcp_client.py ===
# Module pour enregistrer les événements du Medical Agent IA dans un fichier JSONL (MCP logs)
# Chaque événement est horodaté et contient le type d'événement + données associées

import os           # Pour gérer les chemins de fichiers
import json         # Pour encoder les données en JSON
import datetime     # Pour horodatage UTC

# === CONFIGURATION DU FICHIER DE LOG ===
# On crée un chemin absolu vers le fichier mcp_logs.jsonl dans le même dossier que ce script
MCP_LOG_FILE = os.path.join(os.path.dirname(__file__), "mcp_logs.jsonl")

# === FONCTION PRINCIPALE : ENVOI VERS MCP ===
def send_to_mcp(event_type: str, payload: dict):
    """
    Enregistre un événement dans le fichier MCP logs.
    
    Arguments:
        event_type (str): Type de l'événement (ex : 'user_question', 'agent_response')
        payload (dict): Données associées à l'événement
    """
    # Construire l'entrée de log sous forme de dictionnaire
    log_entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),  # UTC ISO timestamp
        "event_type": event_type,                              # Type d'événement
        "payload": payload                                     # Données associées
    }

    # Écriture sécurisée dans le fichier JSONL (append)
    try:
        with open(MCP_LOG_FILE, "a", encoding="utf-8") as f:
            # Chaque ligne du fichier contient un JSON complet
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        # En cas d'erreur, afficher un message et le traceback complet
        print(f"[MCP ERROR] {e}")
        import traceback
        traceback.print_exc()
