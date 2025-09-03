# === Importations ===
import os, time, json, logging, requests  # Gestion fichiers, temps, JSON, logging, requêtes HTTP
from datetime import datetime              # Pour les dates (PDF et logs)
from fpdf import FPDF                      # Génération PDF
import autogen                             # Création des agents AI (Assistant / UserProxy)
from langchain_community.vectorstores import FAISS            # Vectorstore local pour RAG
from langchain_community.embeddings import HuggingFaceEmbeddings  # Embeddings pour transformer texte en vecteurs
from mcp_client import send_to_mcp         # Envoi événements au MCP (monitoring)

# === Logging ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")  # Format des logs
logger = logging.getLogger(__name__)  # Création logger pour ce module

# === Configuration LLM Cloud / Local ===
USE_CLOUD = os.environ.get("USE_CLOUD", "1") == "1"  # True = Mistral Cloud, False = Ollama local
llm_config = {"model": "mistral-medium-2508", "temperature": 0.7}  # Modèle LLM + créativité

if USE_CLOUD:  # Si on utilise Mistral Cloud
    llm_config.update({
        "base_url": "https://api.mistral.ai/v1",                 # URL API Mistral
        "api_key": os.environ.get("MISTRAL_API_KEY", "")         # Récupération clé API depuis l'env
    })
    if not llm_config["api_key"]:
        logger.warning("❌ MISTRAL_API_KEY non défini. LLM ne fonctionnera pas.")  # Warning si clé absente
else:  # Si on utilise Ollama local
    llm_config.update({
        "base_url": "http://localhost:11434/v1",  # URL locale Ollama
        "api_key": "ollama"                        # Clé par défaut pour Ollama
    })

# === Mémoire globale et cache ===
chat_history = []      # Historique global de la session (questions/réponses)
_vector_db = None      # Objet FAISS (chargé à la demande)
WEB_SEARCH_CACHE = {}  # Cache résultats recherche web

# === Chargement Vectorstore FAISS ===
def get_vector_db():
    global _vector_db
    if _vector_db is None:  # Charger FAISS uniquement si pas déjà chargé
        try:
            logger.info("Chargement du vectorstore FAISS...")
            start = time.time()
            _vector_db = FAISS.load_local(
                "vectorstore",  # Dossier contenant le vectorstore FAISS
                HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"),  # Embeddings
                allow_dangerous_deserialization=True  # Permet chargement potentiellement non sécurisé
            )
            logger.info(f"✓ Vectorstore chargé en {time.time()-start:.2f}s")  # Temps de chargement
        except Exception as e:
            logger.error(f"Erreur vectorstore: {e}")  # Log erreur si échec
            _vector_db = None
    return _vector_db  # Retourne le vectorstore

# === RAG : recherche dans les documents internes ===
def retrieve_docs(query, k=3):
    db = get_vector_db()  # Récupération vectorstore
    if db is None: return "Erreur: Base de documents indisponible."
    try:
        results = db.similarity_search_with_score(query, k=k)  # Recherche des k documents les plus proches
        if not results: return "Aucun document pertinent trouvé."
        # Formate les résultats avec source et contenu
        parts = [f"- Source: {doc.metadata.get('source','Inconnu')}\n{doc.page_content}" for doc, score in sorted(results, key=lambda t:t[1])]
        return "Source: Document interne\n" + "\n\n".join(parts)
    except Exception as e:
        logger.error(f"Erreur retrieve_docs: {e}")
        return f"Erreur recherche interne: {e}"

# === Recherche web ===
def search_web(query):
    if query in WEB_SEARCH_CACHE: return WEB_SEARCH_CACHE[query]  # Retour cache si déjà recherché
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": os.environ.get("SERPER_API_KEY",""), "Content-Type":"application/json"}
    payload = {"q": query}
    try:
        resp = requests.post(url, headers=headers, json=payload)  # Requête HTTP
        resp.raise_for_status()  # Vérifie succès HTTP
        data = resp.json()
        if "organic" not in data or not data["organic"]: return "Aucun résultat trouvé sur le web."
        top = data["organic"][0]  # Premier résultat
        result = f"Source: Recherche Web\nTitre: {top.get('title')}\nRésumé: {top.get('snippet')}\nLien: {top.get('link')}"
        WEB_SEARCH_CACHE[query] = result  # Ajoute au cache
        return result
    except Exception as e:
        logger.error(f"Erreur search_web: {e}")
        return f"Erreur recherche web: {e}"

# === Export PDF de l'historique ===
def export_to_pdf(history, dossier="mes_pdfs"):
    os.makedirs(dossier, exist_ok=True)  # Crée dossier si inexistant
    filename = f"session_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf"
    path = os.path.join(dossier, filename)

    def clean(text):
        # Nettoie les caractères non-ASCII (pour PDF)
        return ''.join(c if ord(c)<128 or c in "àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ" else "?" for c in text)

    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    try:
        pdf.add_font("DejaVu","", "DejaVuSansCondensed.ttf", uni=True)  # Police Unicode si dispo
        pdf.set_font("DejaVu", size=12)
    except:
        pdf.set_font("Arial", size=12)  # Police fallback
    for q,r in history:  # Parcours de l’historique
        pdf.multi_cell(0,10,f"Utilisateur: {clean(q)}")
        pdf.multi_cell(0,10,f"Agent: {clean(r)}")
        pdf.ln(5)
    pdf.output(path)
    logger.info(f"PDF généré: {path}")
    return path

# === Création agents Autogen ===
def create_agents():
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
        max_consecutive_auto_reply=1  # Limite réponses automatiques consécutives
    )
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        human_input_mode="NEVER",  # Jamais attendre input manuel
        function_map={"retrieve_docs": retrieve_docs,"search_web": search_web},  # Fonctions accessibles
        code_execution_config={"use_docker": False}  # Pas d’exécution docker
    )
    return user_proxy, assistant

# === Répondre à une question ===
def answer_question(user_input, chat_history_local=None):
    global chat_history
    local_history = chat_history_local if chat_history_local else chat_history  # Historique local si fourni
    send_to_mcp("user_question", {"question": user_input})  # Envoi événement MCP
    memory_lines = [f"- Q: {q}\n- R: {r[:300]}" for q,r in local_history[-2:]]  # Historique récent (2 derniers)
    memory_text = "Historique récent:\n" + "\n".join(memory_lines) if memory_lines else ""
    context = retrieve_docs(user_input)  # Recherche interne d’abord
    used = "RAG"
    if "Erreur" in context or "Aucun document" in context:  # Si RAG échoue
        context = search_web(user_input)  # Recherche web
        used = "WEB"
    send_to_mcp("context_used", {"context": context, "used": used})  # MCP context
    user_prompt = f"""{memory_text}

Contexte:
{context}

Question: {user_input}"""
    _, assistant = create_agents()  # Crée agents Autogen
    try:
        reply = assistant.generate_reply(messages=[{"role":"user","content":user_prompt}])  # Génère réponse
        final = reply.get("content", str(reply)) if isinstance(reply, dict) else str(reply)
    except Exception as e:
        logger.error(f"Erreur génération réponse: {e}")
        final = "❌ Impossible de générer une réponse pour le moment."
    send_to_mcp("agent_response", {"response": final})  # MCP réponse
    if chat_history_local is None: chat_history.append((user_input, final))  # Ajoute historique global
    return final
