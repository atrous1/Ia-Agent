from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import TextLoader
import os

# 🔍 Chemin vers le fichier texte
doc_path = os.path.join("docs", "syndorme.txt")

# 📥 Charger les documents
loader = TextLoader(doc_path, encoding="utf-8")
documents = loader.load()

# 🔠 Modèle de vecteurs
embedding = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# 🧠 Création de la base vectorielle
db = FAISS.from_documents(documents, embedding)

# 💾 Sauvegarde de la base vectorielle dans un dossier
db.save_local("vectorstore")

print("✅ Indexation terminée. Base vectorielle enregistrée dans 'vectorstore'")
