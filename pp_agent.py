import os
import autogen
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from duckduckgo_search import DDGS


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

# --- MEMOIRE A COURT TERME ---
chat_history = []


def search_web(query, max_results=3):
    with DDGS() as ddgs:
        results = ddgs.text(query)
        summaries = []
        for i, r in enumerate(results):
            if i >= max_results:
                break
            summaries.append(f"{r['title']}: {r['body']} (lien: {r['href']})")
        return "\n".join(summaries)


def retrieve_docs(query, k=3):
    db = FAISS.load_local(
        "vectorstore",
        HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"),
        allow_dangerous_deserialization=True,
    )
    results = db.similarity_search(query, k=k)
    return results


def enrich_prompt_with_docs_and_web(query):
    docs = retrieve_docs(query)
    doc_context = "\n\n".join([doc.page_content for doc in docs]) if docs else "Aucun document trouvé."

    web_results = search_web(query)
    web_context = web_results if web_results else "Aucun résultat web trouvé."

    return f"""Tu dois répondre à la question suivante en utilisant les informations ci-dessous.

--- CONTENU DES DOCUMENTS ---
{doc_context}

--- CONTENU DU WEB ---
{web_context}

Question : {query}
"""

assistant = autogen.AssistantAgent(
    name="hello",
    system_message="Tu es un assistant utile. Utilise les documents et la recherche web pour répondre avec précision.",
    llm_config=llm_config,
)


user_proxy = autogen.UserProxyAgent(
    name="user",
    code_execution_config=False,
    function_map={  
        "search_web": search_web
    }
)


# --- BOUCLE PRINCIPALE ---
if __name__ == "__main__":
    print("Votre assistant médical est prêt. Tape 'exit' pour quitter.\n")
    while True:
        user_input = input("Utilisateur : ")
        if user_input.lower() in ["exit", "quit"]:
            print("Au revoir et merci !")
            break

        enriched = enrich_prompt_with_docs_and_web(user_input)
        chat_history.append({"role": "user", "content": enriched})  # STM

        response = assistant.generate_reply(messages=chat_history)

        chat_history.append({"role": "assistant", "content": str(response)})  # STM
        print(f"\nAssistant : {response}\n")
