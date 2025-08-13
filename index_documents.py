import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredImageLoader,
)
from PIL import Image

import os
os.environ["PATH"] += os.pathsep + r"C:\Program Files\Tesseract-OCR"


# Dossier contenant tous les fichiers
docs_dir = "docs"
all_documents = []

# Parcourir tous les fichiers dans le dossier
for filename in os.listdir(docs_dir):
    file_path = os.path.join(docs_dir, filename)

    if filename.endswith(".txt"):
        loader = TextLoader(file_path, encoding="utf-8")
    elif filename.endswith(".pdf"):
        loader = PyPDFLoader(file_path)
    elif filename.endswith(".docx"):
        loader = UnstructuredWordDocumentLoader(file_path)
    elif filename.lower().endswith((".jpg", ".jpeg", ".png")):
        loader = UnstructuredImageLoader(file_path)
    else:
        print(f" Fichier non pris en charge : {filename}")
        continue

    try:
        docs = loader.load()
        all_documents.extend(docs)
        print(f" Chargé : {filename}")
    except Exception as e:
        print(f" Erreur lors du chargement de {filename} : {e}")

#  Embeddings
embedding = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

#  Indexation vectorielle
db = FAISS.from_documents(all_documents, embedding)
db.save_local("vectorstore")

print("\n Indexation terminée. Base vectorielle enregistrée dans 'vectorstore'")
