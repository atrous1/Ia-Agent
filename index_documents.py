# === pp_agent.py - VERSION DÉFINITIVE AVEC RAG FONCTIONNEL ===
# Fichier principal de l'agent médical IA

# --- Import des bibliothèques ---
import os                   # Permet de gérer les chemins de fichiers et variables d'environnement
import json                 # Pour lire/écrire des fichiers JSON (conversations, logs)
import requests             # Pour effectuer des requêtes HTTP (ex: recherche web)
import autogen               # Pour gérer les agents LLM (AssistantAgent et UserProxyAgent)
from datetime import datetime  # Pour gérer les dates et horodatages
from fpdf import FPDF       # Pour créer des fichiers PDF à partir de texte
from langchain_community.vectorstores import FAISS  # Pour le stockage et la recherche vectorielle
from langchain_huggingface import HuggingFaceEmbeddings  # Pour convertir texte en vecteurs (embeddings)
import time                 # Pour mesurer le temps d'exécution (debug / performance)
import logging              # Pour suivre l'exécution et afficher les erreurs ou informations

# --- Configurer le logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')  # Format des messages de log
logger = logging.getLogger(__name__)  # Crée un logger pour ce module

# --- Configuration de l'environnement Ollama ---
os.environ["OPENAI_API_BASE"] = "http://localhost:11434/v1"  # URL locale du serveur Ollama
os.environ["OPENAI_API_KEY"] = "ollama"                       # Clé API fictive pour accès local

# --- Configuration du modèle LLM ---
config_list = [
    {
        "model": "mistral",                # Nom du modèle LLM local
        "base_url": "http://localhost:11434/v1",  # URL du serveur Ollama
        "api_key": "ollama",               # Clé API
        "price": [0.0, 0.0],               # Prix fictif car local
    }
]

# Paramètres globaux LLM
llm_config = {
    "config_list": config_list,          # Liste des configurations de modèles
    "cache_seed": 42,                     # Pour rendre les réponses reproductibles
    "functions": [                        # Fonctions exposées au modèle LLM
        {
            "name": "retrieve_docs",     # Nom de la fonction accessible par le LLM
            "description": "Cherche des documents internes par similarité vectorielle",
            "parameters": {              # Structure attendue des paramètres
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "La requête de recherche"}
                },
                "required": ["query"]   # Le champ "query" est obligatoire
            }
        },
        {
            "name": "search_web",        # Fonction de recherche web
            "description": "Fait une recherche web avec Google via Serper.dev",
            "parameters": {              # Paramètres attendus
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "La requête de recherche"}
                },
                "required": ["query"]
            }
        }
    ]
}

# --- Mémoire conversationnelle globale ---
chat_history = []  # Liste contenant les tuples (question utilisateur, réponse agent)

# --- Variables globales pour le cache ---
_cached_agents = None        # Pour stocker les instances d'agents Autogen
_cached_memory_text = ""     # Historique court pour mémoire conversationnelle
_vector_db = None            # Stockage FAISS chargé en mémoire pour accélérer les recherches

# --- Fonction : Charger le vectorstore FAISS ---
def get_vector_db():
    """Charge le vectorstore en mémoire une seule fois pour toutes les sessions"""
    global _vector_db  # Permet de modifier la variable globale
    if _vector_db is None:  # Si le vectorstore n'a pas encore été chargé
        logger.info("Chargement du vectorstore...")
        start_time = time.time()  # Pour mesurer le temps de chargement
        try:
            _vector_db = FAISS.load_local(
                "vectorstore",  # Chemin du vectorstore sur le disque
                HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"),  # Modèle d'embeddings
                allow_dangerous_deserialization=True,  # Autorise la désérialisation même si non sécurisée
            )
            logger.info(f"Vectorstore chargé en {time.time() - start_time:.2f}s")  # Affiche le temps de chargement
        except Exception as e:
            logger.error(f"Impossible de charger le vectorstore: {e}")  # Erreur si échec
            _vector_db = None
    return _vector_db  # Retourne l'objet vectorstore (FAISS)

# --- Cache pour recherches web et documents internes ---
WEB_SEARCH_CACHE = {}  # Cache des résultats de recherche web pour éviter les appels répétitifs
DOC_SEARCH_CACHE = {}  # Cache des résultats RAG pour les mêmes requêtes

# --- Fonction : Recherche web via Serper.dev ---
def search_web(query, max_results=1):
    """
    Requête Web avec Serper.dev
    Retourne un dictionnaire {content: ...} compatible Autogen
    """
    url = "https://google.serper.dev/search"  # URL API Serper
    headers = {"X-API-KEY": "API_KEY", "Content-Type": "application/json"}  # Clé API + type JSON
    payload = {"q": query}  # Corps de la requête JSON

    try:
        start_time = time.time()
        response = requests.post(url, headers=headers, json=payload)  # Envoi de la requête POST
        response.raise_for_status()  # Lève une exception si code HTTP != 200
        data = response.json()  # Convertit la réponse en dictionnaire Python
        logger.info(f"Recherche web terminée en {time.time() - start_time:.2f}s")

        if "organic" not in data or not data["organic"]:  # Pas de résultats
            result = {"content": "Aucun résultat trouvé sur le web."}
            WEB_SEARCH_CACHE[query] = result
            return result

        top = data["organic"][0]  # Premier résultat
        result = {"content": f"Source: Recherche Web\nTitre: {top.get('title')}\nRésumé: {top.get('snippet')}\nLien: {top.get('link')}"}
        WEB_SEARCH_CACHE[query] = result  # Mettre en cache
        return result

    except Exception as e:
        logger.error(f"Erreur recherche web: {e}")  # Log de l'erreur
        result = {"content": f"Erreur lors de la recherche web: {str(e)}"}
        WEB_SEARCH_CACHE[query] = result
        return result

# --- Fonction : Recherche RAG dans FAISS ---
def retrieve_docs(query, k=3, max_distance=1.5):
    """
    Recherche des documents internes pertinents via FAISS
    Retourne un dict {content: ...} compatible Autogen
    """
    if query in DOC_SEARCH_CACHE:  # Vérifie si le résultat est déjà en cache
        logger.info(f"Utilisation du cache pour la recherche RAG: '{query}'")
        return DOC_SEARCH_CACHE[query]

    vector_db = get_vector_db()  # Charge ou récupère le vectorstore en mémoire
    if vector_db is None:
        return {"content": "Erreur: Base de documents non disponible."}

    try:
        start_time = time.time()
        results = vector_db.similarity_search_with_score(query, k=k)  # Recherche les k documents les plus similaires
        logger.info(f"Recherche RAG terminée en {time.time() - start_time:.2f}s")
        filtered = [doc for doc, score in results if score <= max_distance]  # Filtrer par score de similarité
        if not filtered:  # Si aucun résultat ne passe le seuil
            filtered = [doc for doc, score in results if score <= 2.0]  # Augmenter seuil
            if not filtered:
                return {"content": "Aucun document pertinent trouvé dans la base interne."}

        doc = filtered[0]  # Prendre le premier document filtré
        source = doc.metadata.get("source", "Document inconnu")
        result = {"content": f"Source: Document Interne ({source})\n{doc.page_content}"}
        DOC_SEARCH_CACHE[query] = result  # Mettre en cache
        return result
    except Exception as e:
        logger.exception("Erreur RAG")  # Trace complète de l'erreur
        result = {"content": f"Erreur lors de la recherche dans la base: {str(e)}"}
        DOC_SEARCH_CACHE[query] = result
        return result

# --- Fonction : Export PDF ---
def export_to_pdf(history, dossier="mes_pdfs"):
    """
    Exporte la conversation en PDF
    Nettoie les caractères Unicode problématiques
    """
    def clean_text(text):
        replacements = {'œ': 'oe', 'Œ': 'Oe', '–': '-', '—': '-', '“': '"', '”': '"', '’': "'", '•': '-', '\u2026': '...', '€': 'EUR'}
        for old, new in replacements.items():
            text = text.replace(old, new)
        return ''.join(c for c in text if ord(c) < 128)  # Supprime tous les caractères non ASCII

    dossier_pdf = os.path.join("C:/Users/USER/Desktop/Agent IA", dossier)
    os.makedirs(dossier_pdf, exist_ok=True)  # Crée le dossier s'il n'existe pas
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    pdf_path = os.path.join(dossier_pdf, f"session_{timestamp}.pdf")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)  # Active les sauts de page automatique
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for user_msg, agent_msg in history:  # Parcours de chaque échange
        pdf.multi_cell(0, 10, f"Utilisateur : {clean_text(user_msg)}")
        pdf.multi_cell(0, 10, f"Agent : {clean_text(agent_msg)}")
        pdf.ln(5)  # Ligne vide entre échanges
    pdf.output(pdf_path)  # Sauvegarde le PDF
    return pdf_path

# --- Fonction : Créer agents Autogen ---
def create_agents():
    """
    Retourne user_proxy et assistant Autogen configurés pour RAG
    """
    assistant = autogen.AssistantAgent(
        name="medical_agent",
        system_message="""Tu es un assistant médical expert...
        {memory}""",  # {memory} sera remplacé par l'historique récent
        llm_config=llm_config,
        max_consecutive_auto_reply=1,  # Ne fait qu'une réponse à la fois
    )
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        human_input_mode="NEVER",  # Pas d'entrée humaine directe
        max_consecutive_auto_reply=0,
        function_map={"retrieve_docs": retrieve_docs, "search_web": search_web},  # Fonctions exposées
        code_execution_config=False,
    )
    return user_proxy, assistant

# --- Fonction : Répondre à une question (Streamlit friendly) ---
def answer_question(user_input, chat_history_local=None):
    """
    Retourne la réponse de l'agent en utilisant RAG et l'historique
    """
    global chat_history
    local_history = chat_history_local if chat_history_local else chat_history  # Historique à utiliser
    memory_text = ""
    if local_history:
        recent_history = local_history[-3:]  # Ne prendre que les 3 derniers échanges
        memory_text = "\n".join([f"Q:{q}\nR:{r}" for q,r in recent_history])  # Formater mémoire pour le LLM

    user_proxy, assistant = create_agents()  # Crée les agents
    assistant.update_system_message(assistant.system_message.replace("{memory}", memory_text))  # Ajoute mémoire

    try:
        response = assistant.generate_reply([{"role": "user", "content": user_input}])  # Génère la réponse
        content = response.get("content", str(response)) if isinstance(response, dict) else str(response)
        if chat_history_local is None:  # Mettre à jour l'historique global seulement si pas local
            chat_history.append((user_input, content))
        return content
    except Exception as e:
        if chat_history_local is None:
            chat_history.append((user_input, f"Erreur: {e}"))
        return f"Désolé, une erreur est survenue: {str(e)}"
