# === pp_agent.py - VERSION ULTRA DÉTAILLÉE ===
# Ce fichier contient toutes les fonctions backend pour l'Agent Médical IA.
# Fonctions principales :
# 1. Charger un LLM local via Ollama
# 2. Effectuer des recherches RAG (vectorstore FAISS)
# 3. Recherche web via Serper.dev
# 4. Gérer l'historique des conversations
# 5. Exporter les conversations en PDF
# 6. Communiquer avec MCP (Model Context Protocol)

# === IMPORTS ===
import os          # Pour la gestion des chemins et variables d'environnement
import time        # Pour mesurer les temps de chargement
import json        # Lecture / écriture de fichiers JSON
import requests    # Pour faire des requêtes HTTP (API Serper.dev)
import logging     # Pour journaliser actions et erreurs
from datetime import datetime  # Pour horodatage précis
from fpdf import FPDF         # Pour générer des fichiers PDF
import autogen                 # Pour créer et gérer les agents LLM
from langchain_community.vectorstores import FAISS  # Vectorstore FAISS pour RAG
from langchain_community.embeddings import HuggingFaceEmbeddings

from mcp_client import send_to_mcp  # Pour envoyer logs et données au MCP

# === CONFIG LOGGING ===
logging.basicConfig(
    level=logging.INFO,  # Niveau minimum INFO (affiche INFO, WARNING, ERROR)
    format="%(asctime)s - %(levelname)s - %(message)s"  # Format des logs
)
logger = logging.getLogger(__name__)  # Logger principal pour ce module

# === CONFIGURATION OLLAMA ===
os.environ["OPENAI_API_BASE"] = "http://localhost:11434/v1"  # Serveur Ollama local
os.environ["OPENAI_API_KEY"] = "ollama"  # Clé API pour Ollama

# === CONFIGURATION LLM ===
# Paramètres pour utiliser le modèle Mistral via Ollama
config_list = [{
    "model": "mistral",
    "base_url": "http://localhost:11434/v1",
    "api_key": "ollama",
    "price": [0.0, 0.0],  # Prix fictif pour suivi
}]
llm_config = {
    "config_list": config_list,
    "cache_seed": 42,  # Seed pour reproductibilité
    "model": "mistral",          # modèle installé avec ollama pull mistral
    "model_client": "ollama",    # force Autogen à utiliser Ollama (pas OpenAI)
    "base_url": "http://localhost:11434/v1",
    "api_key": "ollama",
    "temperature": 0.7,
    
}

# === MÉMOIRE GLOBALE ===
chat_history = []  # Historique complet de la session
_vector_db = None  # Référence globale au vectorstore FAISS (chargé une seule fois)
WEB_SEARCH_CACHE = {}  # Cache local pour éviter requêtes web répétées

# === FONCTION : Charger le vectorstore FAISS ===
def get_vector_db():
    """
    Charge le vectorstore FAISS contenant les embeddings des documents.
    Si déjà chargé, renvoie la référence globale.
    """
    global _vector_db  # Permet de modifier la variable globale
    if _vector_db is None:  # Ne pas recharger si déjà chargé
        try:
            logger.info("Chargement du vectorstore...")
            start = time.time()
            _vector_db = FAISS.load_local(
                "vectorstore",  # Chemin local où FAISS est sauvegardé
                HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"),
                allow_dangerous_deserialization=True,  # Permet la désérialisation
            )
            logger.info(f"✓ Vectorstore chargé en {time.time()-start:.2f}s")
        except Exception as e:
            logger.error(f"Erreur chargement vectorstore: {e}")
            _vector_db = None
    return _vector_db  # Renvoie le vectorstore

# === FONCTION : RAG (retrieval-augmented generation) ===
def retrieve_docs(query, k=3):
    """
    Recherche les documents les plus pertinents pour la requête dans FAISS.
    Retourne une concaténation du contenu et des sources.
    """
    logger.info(f"🔍 RAG pour: {query!r}")
    db = get_vector_db()  # Charger le vectorstore
    if db is None:
        return "Erreur: Base de documents indisponible."

    try:
        results = db.similarity_search_with_score(query, k=k)  # Recherche par similarité
        if not results:
            return "Aucun document pertinent trouvé."

        parts = []
        for doc, score in sorted(results, key=lambda t: t[1]):  # Trier par score
            src = doc.metadata.get("source", "Inconnu")
            parts.append(f"- Source: {src}\n{doc.page_content}")
        return "Source: Document interne\n" + "\n\n".join(parts)
    except Exception as e:
        logger.error(f"Erreur retrieve_docs: {e}")
        return f"Erreur recherche interne: {e}"

# === FONCTION : Recherche web via Serper.dev ===
def search_web(query):
    """
    Recherche sur le web via l'API Serper.dev.
    Retourne titre, snippet et lien du premier résultat.
    Utilise un cache pour éviter les requêtes répétées.
    """
    if query in WEB_SEARCH_CACHE:
        logger.info("⚡ Cache web utilisé")
        return WEB_SEARCH_CACHE[query]

    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": "8eef4a7e0baed98c9676e4380e3d611630ab6314",
        "Content-Type": "application/json"
    }
    payload = {"q": query}

    try:
        logger.info(f"🔍 Recherche web: {query}")
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()  # Lève une erreur si code HTTP != 200
        data = resp.json()

        if "organic" not in data or not data["organic"]:
            return "Aucun résultat trouvé sur le web."

        top = data["organic"][0]
        result = f"Source: Recherche Web\nTitre: {top.get('title')}\nRésumé: {top.get('snippet')}\nLien: {top.get('link')}"
        WEB_SEARCH_CACHE[query] = result  # Sauvegarde dans cache
        return result
    except Exception as e:
        logger.error(f"Erreur search_web: {e}")
        return f"Erreur recherche web: {e}"

# === FONCTION : Exporter l'historique en PDF ===
def export_to_pdf(history, dossier="mes_pdfs"):
    """
    Génère un PDF avec toutes les questions et réponses de la session.
    history: liste de tuples (question, réponse)
    """
    dossier_pdf = os.path.join("C:/Users/USER/Desktop/Agent IA", dossier)
    os.makedirs(dossier_pdf, exist_ok=True)
    filename = f"session_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf"
    path = os.path.join(dossier_pdf, filename)

    def clean(text):
        """Nettoie caractères non-ASCII pour éviter erreur PDF"""
        return ''.join(c if ord(c) < 128 or c in "àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ" else "?" for c in text)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    try:
        pdf.add_font("DejaVu", "", "DejaVuSansCondensed.ttf", uni=True)
        pdf.set_font("DejaVu", size=12)
    except:
        pdf.set_font("Arial", size=12)

    for q, r in history:
        pdf.multi_cell(0, 10, f"Utilisateur: {clean(q)}")
        pdf.multi_cell(0, 10, f"Agent: {clean(r)}")
        pdf.ln(5)

    pdf.output(path)
    logger.info(f"PDF généré: {path}")
    return path

# === FONCTION : Création des agents Autogen ===
def create_agents():
    """
    Crée les agents UserProxyAgent et AssistantAgent pour la session.
    """
    assistant = autogen.AssistantAgent(
        name="medical_agent",
        system_message="""Tu es un assistant médical. 
        
        Règles:
        - Utilise d'abord retrieve_docs.
        - Si aucun document interne, utilise search_web.
        - Ne jamais inventer d'informations.
        - Réponds clairement en citant la source.
        - Termine toujours par: "Souhaitez-vous des informations complémentaires sur ce sujet ?"
        {memory}""",
        llm_config=llm_config,
        max_consecutive_auto_reply=1,
    )
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        human_input_mode="NEVER",
        function_map={"retrieve_docs": retrieve_docs, "search_web": search_web},
        code_execution_config={"use_docker": False},
    )
    return user_proxy, assistant

# === FONCTION : Répondre à une question ===
def answer_question(user_input, chat_history_local=None):
    """
    Génère une réponse à une question utilisateur.
    Combine mémoire locale, RAG et recherche web si nécessaire.
    """
    logger.info("="*50)
    logger.info(f"Question: {user_input}")
    logger.info("="*50)

    global chat_history
    local_history = chat_history_local if chat_history_local is not None else chat_history

    # --- MCP : log question utilisateur ---
    send_to_mcp("user_question", {"question": user_input})

    # --- Préparer la mémoire récente (2 derniers échanges) ---
    memory_lines = [f"- Q: {q}\n- R: {r[:300]}" for q, r in local_history[-2:]]
    memory_text = "Historique récent:\n" + "\n".join(memory_lines) if memory_lines else ""

    # --- RAG d'abord ---
    context = retrieve_docs(user_input)
    used = "RAG"
    if "Erreur" in context or "Aucun document" in context:
        context = search_web(user_input)
        used = "WEB"

    # --- MCP : log contexte utilisé ---
    send_to_mcp("context_used", {"context": context, "used": used})

    # --- Préparer le prompt pour l'agent ---
    user_prompt = f"""{memory_text}

Contexte:
{context}

Question: {user_input}"""

    _, assistant = create_agents()
    reply = assistant.generate_reply(messages=[{"role": "user", "content": user_prompt}])
    final = reply.get("content", str(reply)) if isinstance(reply, dict) else str(reply)

    # --- MCP : log réponse finale ---
    send_to_mcp("agent_response", {"response": final})

    # Ajouter à l'historique global si pas de chat local
    if chat_history_local is None:
        chat_history.append((user_input, final))

    logger.info(f"Réponse prête ({used})")
    return final

# === TESTS RAPIDES ===
if __name__ == "__main__":
    print("=== TEST pp_agent.py ===")
    print("→ Test retrieve_docs:")
    print(retrieve_docs("symptômes grippe")[:300])
    print("\n→ Test search_web:")
    print(search_web("symptômes grippe")[:300])
    print("\n→ Test answer_question:")
    print(answer_question("Quels sont les symptômes de la grippe ?")[:300])
