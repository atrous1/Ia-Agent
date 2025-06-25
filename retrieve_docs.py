from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

def retrieve_docs(query, k=3):
    db = FAISS.load_local(
        "vectorstore",
        HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"),
        allow_dangerous_deserialization=True
    )
    results = db.similarity_search(query, k=k)
    return results

if __name__ == "__main__":
    query = "Quels sont les symptômes de la grippe ?"
    docs = retrieve_docs(query)
    for i, doc in enumerate(docs):
        print(f"--- Document {i+1} ---")
        print(doc.page_content)
