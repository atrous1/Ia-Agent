# === pp_agent.py - VERSION CLOUD-SAFE ===
import os
import time
import json
import logging
from datetime import datetime
import requests
from fpdf import FPDF
import autogen
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from mcp_client import send_to_mcp

# === LOGGING ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# === CONFIGURATION ENVIRONNEMENT ===
USE_OLLAMA = os.environ.get("USE_OLLAMA", "1") == "1"

llm_config = {
    "model": "mistral",
    "temperature": 0.7,
}

if USE_OLLAMA:
    llm_config.update({
        "model_client": "ollama",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama"
    })
else:
    llm_config.update({
        "model_client": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": os.environ.get("OPENAI_API_KEY", ""),
    })
    if not llm_config["api_key"]:
        logger.warning("❌ OPENAI_API_KEY non défini. Les réponses LLM ne fonctionneront pas sur Cloud.")

# === MÉMOIRE GLOBALE ===
chat_history = []
_vector_db = None
WEB_SEARCH_CACHE = {}

# === Vectorstore FAISS ===
def get_vector_db():
    global _vector_db
    if _vector_db is None:
        try:
            logger.info("Chargement du vectorstore FAISS...")
            start = time.time()
            _vector_db = FAISS.load_local(
                "vectorstore",
                HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"),
                allow_dangerous_deserialization=True
            )
            logger.info(f"✓ Vectorstore chargé en {time.time()-start:.2f}s")
        except Exception as e:
            logger.error(f"Erreur vectorstore: {e}")
            _vector_db = None
    return _vector_db

# === RAG ===
def retrieve_docs(query, k=3):
    db = get_vector_db()
    if db is None:
        return "Erreur: Base de documents indisponible."
    try:
        results = db.similarity_search_with_score(query, k=k)
        if not results:
            return "Aucun document pertinent trouvé."
        parts = []
        for doc, score in sorted(results, key=lambda t: t[1]):
            src = doc.metadata.get("source", "Inconnu")
            parts.append(f"- Source: {src}\n{doc.page_content}")
        return "Source: Document interne\n" + "\n\n".join(parts)
    except Exception as e:
        logger.error(f"Erreur retrieve_docs: {e}")
        return f"Erreur recherche interne: {e}"

# === Recherche web ===
def search_web(query):
    if query in WEB_SEARCH_CACHE:
        return WEB_SEARCH_CACHE[query]
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": os.environ.get("SERPER_API_KEY", ""),
        "Content-Type": "application/json"
    }
    payload = {"q": query}
    try:
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "organic" not in data or not data["organic"]:
            return "Aucun résultat trouvé sur le web."
        top = data["organic"][0]
        result = f"Source: Recherche Web\nTitre: {top.get('title')}\nRésumé: {top.get('snippet')}\nLien: {top.get('link')}"
        WEB_SEARCH_CACHE[query] = result
        return result
    except Exception as e:
        logger.error(f"Erreur search_web: {e}")
        return f"Erreur recherche web: {e}"

# === Export PDF ===
def export_to_pdf(history, dossier="mes_pdfs"):
    dossier_pdf = os.path.join(dossier)
    os.makedirs(dossier_pdf, exist_ok=True)
    filename = f"session_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf"
    path = os.path.join(dossier_pdf, filename)

    def clean(text):
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
        max_consecutive_auto_reply=1,
    )
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        human_input_mode="NEVER",
        function_map={"retrieve_docs": retrieve_docs, "search_web": search_web},
        code_execution_config={"use_docker": False},
    )
    return user_proxy, assistant

# === Répondre à une question ===
def answer_question(user_input, chat_history_local=None):
    global chat_history
    local_history = chat_history_local if chat_history_local else chat_history

    # Log MCP
    send_to_mcp("user_question", {"question": user_input})

    # Mémoire récente
    memory_lines = [f"- Q: {q}\n- R: {r[:300]}" for q, r in local_history[-2:]]
    memory_text = "Historique récent:\n" + "\n".join(memory_lines) if memory_lines else ""

    # RAG
    context = retrieve_docs(user_input)
    used = "RAG"
    if "Erreur" in context or "Aucun document" in context:
        context = search_web(user_input)
        used = "WEB"

    # MCP log
    send_to_mcp("context_used", {"context": context, "used": used})

    # Prompt
    user_prompt = f"""{memory_text}

Contexte:
{context}

Question: {user_input}"""

    _, assistant = create_agents()
    try:
        reply = assistant.generate_reply(messages=[{"role": "user", "content": user_prompt}])
        final = reply.get("content", str(reply)) if isinstance(reply, dict) else str(reply)
    except Exception as e:
        logger.error(f"Erreur génération réponse: {e}")
        final = "❌ Impossible de générer une réponse pour le moment."

    send_to_mcp("agent_response", {"response": final})

    if chat_history_local is None:
        chat_history.append((user_input, final))

    return final
