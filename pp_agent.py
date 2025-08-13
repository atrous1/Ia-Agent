# === Importation des bibliothèques nécessaires ===
import os
import json
import requests
import autogen
from datetime import datetime
from fpdf import FPDF
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from autogen import OpenAIWrapper
from langchain_community.chat_models import ChatOpenAI

from langchain.schema import HumanMessage

# === Configuration de l'environnement pour Ollama ===
os.environ["OPENAI_API_BASE"] = "http://localhost:11434/v1"
os.environ["OPENAI_API_KEY"] = "ollama"

# === Configuration du modèle à utiliser via Ollama ===
config_list = [
    {
        "model": "mistral",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "price": [0.0, 0.0],
    }
]
llm_config = {
    "config_list": config_list,
    "cache_seed": 42,
}

llm = OpenAIWrapper(config=llm_config)

# === Mémoire conversationnelle ===
chat_history = []

# === Fonction : Recherche web via Serper.dev ===
def search_web(query, max_results=1):
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": "8eef4a7e0baed98c9676e4380e3d611630ab6314",
        "Content-Type": "application/json"
    }
    payload = {"q": query}

    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()

        if "organic" not in data or not data["organic"]:
            return None

        top = data["organic"][0]
        title = top.get("title", "Titre non disponible")
        snippet = top.get("snippet", "Aucun résumé disponible")
        link = top.get("link", "Lien non disponible")
        return title, snippet, link

    except Exception as e:
        print(f"[ERREUR Serper] {e}")
        return None

# === Fonction : Enrichir la réponse web ou RAG avec le LLM (sans limite) ===
def enrich_response_with_llm(snippet, link=None, query=None):
    prompt = f"Voici une information utile :\n{snippet}"
    if query:
        prompt = f"Question : {query}\n\n{prompt}"
    if link:
        prompt += f"\n\nLien source : {link}"
    prompt += "\n\nPeux-tu reformuler cette réponse pour qu'elle soit plus complète, cohérente et naturelle ? Inclue les faits importants et développe la réponse sans limite de longueur."

    try:
        # Si la librairie supporte max_new_tokens à la place de max_tokens, essaye avec ça
        response = llm.complete(prompt=prompt, max_tokens=2000)  # ou max_new_tokens=2000
        # Sinon, envisager de récupérer en streaming ou de fractionner la réponse
        return response.strip()
    except Exception as e:
        print(f"[ERREUR LLM enrichissement] {e}")
        if link:
            return f"{snippet}\nLien source : {link}"
        else:
            return snippet

# === Fonction : Recherche dans les documents FAISS ===
def retrieve_docs(query, k=3, max_distance=0.7):
    db = FAISS.load_local(
        "vectorstore",
        HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"),
        allow_dangerous_deserialization=True,
    )
    results = db.similarity_search_with_score(query, k=k)
    print("DEBUG: Scores des documents trouvés:")
    for doc, score in results:
        print(f"  Source: {doc.metadata.get('source', 'Inconnu')}, Score: {score}")

    filtered = [doc for doc, score in results if score <= max_distance]

    if not filtered:
        return None

    doc = filtered[0]
    source = doc.metadata.get("source", "Document inconnu")
    return f"Extrait du document '{source}':\n{doc.page_content}"

# === Fonction : Construction du contexte MCP ===
def build_mcp_context(user_input, tools_used, memory):
    return {
        "context": {
            "user_input": user_input,
            "memory": memory,
            "tools": [
                {"name": name, "description": desc} for name, desc in tools_used.items()
            ],
        },
        "message": user_input,
    }

# === Fonction : Sauvegarde des logs MCP ===
def save_mcp_log(mcp, log_file="mcp_logs.jsonl"):
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(mcp, ensure_ascii=False) + "\n")

# === Fonction : Répondre à une question utilisateur (MCP) avec priorisation RAG ===
def answer_question(user_input):
    memory_text = "\n".join([f"Utilisateur : {q}\nAgent : {r}" for q, r in chat_history[-5:]])
    tools = {
        "retrieve_docs": "Cherche des documents internes par similarité vectorielle",
        "search_web": "Fait une recherche web avec Google via Serper.dev"
    }
    mcp = build_mcp_context(user_input, tools, memory_text)

    # Recherche prioritaire dans RAG
    doc_answer = retrieve_docs(user_input)
    if doc_answer:
        mcp["context"]["source_used"] = "retrieve_docs"
        response = enrich_response_with_llm(snippet=doc_answer, query=user_input)
    else:
        web_result = search_web(user_input)
        if web_result:
            title, snippet, link = web_result
            mcp["context"]["source_used"] = "search_web"
            response = enrich_response_with_llm(snippet=snippet, link=link, query=user_input)
        else:
            mcp["context"]["source_used"] = "none"
            response = "Désolé, je n'ai pas trouvé d'information pertinente."

    save_mcp_log(mcp)
    print("[DEBUG MCP]\n", json.dumps(mcp, indent=2, ensure_ascii=False))
    return response

# === Fonction : Exporter la conversation en PDF ===
def export_to_pdf(history, dossier="mes_pdfs"):
    def clean_text(text):
        return text.translate(str.maketrans({
            '—': '-', '–': '-', '“': '"', '”': '"', '’': "'", '•': '-', '\u2026': '...'
        }))

    dossier_pdf = os.path.join("C:/Users/USER/Desktop/Agent IA", dossier)
    os.makedirs(dossier_pdf, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"session_{timestamp}.pdf"
    chemin_complet = os.path.join(dossier_pdf, filename)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for user_msg, agent_msg in history:
        pdf.multi_cell(0, 10, f"Utilisateur : {clean_text(user_msg)}", align="L")
        pdf.multi_cell(0, 10, f"Agent : {clean_text(agent_msg)}", align="L")
        pdf.ln(5)

    pdf.output(chemin_complet)
    print(f"[✅] Conversation enregistrée dans : {chemin_complet}")

# === Définition de l'agent Autogen ===
assistant = autogen.AssistantAgent(
    name="rag_agent",
    system_message="Tu es un assistant médical intelligent utilisant la recherche locale, web, et la mémoire pour répondre avec précision.",
    llm_config=llm_config,
    function_map={
        "search_web": search_web,
        "retrieve_docs": retrieve_docs,
    },
)

# === Boucle principale ===
if __name__ == "__main__":
    while True:
        user_input = input("Utilisateur : ").strip()
        if user_input.lower() in ["exit", "quit"]:
            print("Au revoir et merci !")
            break
        elif user_input.lower() == "pdf":
            export_to_pdf(chat_history)
            continue

        response = answer_question(user_input)
        print(f"\nRéponse :\n{response}\n")
        chat_history.append((user_input, response))
