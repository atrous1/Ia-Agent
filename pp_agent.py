import os
import autogen
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from duckduckgo_search import DDGS
from fpdf import FPDF 
from datetime import datetime

os.environ["OPENAI_API_BASE"] = "http://localhost:11434/v1"
os.environ["OPENAI_API_KEY"] = "ollama"

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

# --- Mémoire conversationnelle ---
chat_history = []

# --- Fonction recherche web avec filtrage ---
def search_web(query, max_results=1):
    with DDGS() as ddgs:
        results = ddgs.text(query)
        if not results:
            return None
        r = results[0]
        return f"{r['title']}\n{r['body']}\nLien source : {r['href']}"

# --- Fonction recherche docs avec seuil ---
def retrieve_docs(query, k=3, max_distance=0.7):
    db = FAISS.load_local(
        "vectorstore",
        HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"),
        allow_dangerous_deserialization=True,
    )
    results = db.similarity_search_with_score(query, k=k)
    print("DEBUG: Scores des documents trouvés:")
    for doc, score in results:
        print(f"  Source: {doc.metadata.get('source', 'Inconnu')}, Score (distance): {score}")

    # Ici score est une distance (FAISS), donc plus petit = meilleur
    filtered = [doc for doc, score in results if score <= max_distance]

    if not filtered:
        return None

    doc = filtered[0]
    source = doc.metadata.get("source", "Document inconnu")
    return f"Extrait du document '{source}':\n{doc.page_content}"

# --- Fonction principale pour répondre à une question ---
def answer_question(query):
    doc_answer = retrieve_docs(query)
    if doc_answer is not None:
        return doc_answer
    else:
        web_answer = search_web(query)
        if web_answer:
            return web_answer
        else:
            return "Désolé, je n'ai pas trouvé d'information pertinente."


def export_to_pdf(history, dossier="mes_pdfs"):
    import os
    from datetime import datetime
    from fpdf import FPDF

    def clean_text(text):
        replacements = {
            '—': '-',  # tiret long → tiret simple
            '–': '-',  # tiret moyen → tiret simple
            '“': '"',  # guillemets typographiques → guillemets simples
            '”': '"',
            '’': "'",  # apostrophe typographique → apostrophe simple
            '•': '-',  # puce → tiret simple
            '\u2026': '...',  # points de suspension
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    dossier_pdf = os.path.join("C:/Users/USER/Desktop/Agent IA", dossier)
    print(f"[DEBUG] Chemin dossier PDF : {dossier_pdf}")

    try:
        os.makedirs(dossier_pdf, exist_ok=True)
        print(f"[DEBUG] Dossier créé ou déjà existant.")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"session_{timestamp}.pdf"
        chemin_complet = os.path.join(dossier_pdf, filename)
        print(f"[DEBUG] Chemin complet du fichier PDF : {chemin_complet}")

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", size=12)

        for i, (user_msg, agent_msg) in enumerate(history):
            pdf.multi_cell(0, 10, f"Utilisateur : {clean_text(user_msg)}", align="L")
            pdf.multi_cell(0, 10, f"Agent : {clean_text(agent_msg)}", align="L")
            pdf.ln(5)

        pdf.output(chemin_complet)
        print(f"[✅] Conversation enregistrée dans : {chemin_complet}")
    except Exception as e:
        print(f"[❌ ERREUR] Impossible d'enregistrer le PDF : {e}")

# --- Fonction pour construire le prompt (optionnel) ---
def build_prompt(user_question):
    prompt = f"""
Tu es un agent intelligent capable d'utiliser deux outils : une recherche documentaire locale et une recherche web.

Ta tâche : répondre à la question suivante de manière claire, précise et naturelle.

Tu peux utiliser :
- La fonction 'retrieve_docs' pour chercher dans les documents internes.
- La fonction 'search_web' pour chercher sur le web.

Choisis intelligemment quels outils utiliser, et explique brièvement dans ta réponse ce que tu as utilisé.

Question : {user_question}
"""
    return prompt.strip()

assistant = autogen.AssistantAgent(
    name="rag_agent",
    system_message="Tu es un assistant RAG intelligent qui utilise la mémoire, la recherche web et documentaire pour répondre clairement.",
    llm_config=llm_config,
    function_map={
        "search_web": search_web,
        "retrieve_docs": retrieve_docs,
    },
)

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