# === Import des bibliothèques nécessaires ===
from langchain_community.vectorstores import FAISS  
# FAISS permet de créer et interroger une base de vecteurs (vectorstore) de documents
# pour effectuer des recherches par similarité.

from langchain_huggingface import HuggingFaceEmbeddings  
# HuggingFaceEmbeddings transforme du texte en vecteurs numériques (embeddings)
# afin de les comparer dans FAISS.

# === Fonction pour récupérer les documents les plus pertinents ===
def retrieve_docs(query, k=3):
    """
    Recherche les k documents les plus similaires à la requête dans le vectorstore FAISS.
    
    Args:
        query (str): la question ou texte à rechercher.
        k (int): nombre de documents à retourner.
    
    Returns:
        list: liste d'objets Document trouvés.
    """
    
    # --- Charger le vectorstore FAISS ---
    db = FAISS.load_local(
        "vectorstore",  # Chemin local où se trouve le vectorstore sauvegardé
        HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"),  
        # Modèle HuggingFace qui transforme le texte en vecteurs pour la comparaison
        allow_dangerous_deserialization=True  
        # Permet de charger des objets FAISS même si ce n'est pas totalement sécurisé
    )
    # Ici, le vectorstore est chargé à chaque appel.
    # Pour un vrai projet, il serait plus efficace de le mettre en cache en mémoire.

    # --- Recherche des documents les plus similaires ---
    results = db.similarity_search(query, k=k)  
    # similarity_search fait la recherche par similarité :
    # - transforme la requête en vecteur
    # - compare ce vecteur aux vecteurs du vectorstore
    # - retourne les k documents les plus proches

    return results  
    # Retourne la liste des documents trouvés.
    # Chaque 'doc' contient :
    # - doc.page_content : le texte du document
    # - doc.metadata : dictionnaire avec des infos supplémentaires (ex: source)

# === Test de la fonction ===
if __name__ == "__main__":
    # --- Définir une requête utilisateur à rechercher ---
    query = "Quels sont les symptômes de la grippe ?"  

    # --- Appeler la fonction pour récupérer les documents pertinents ---
    docs = retrieve_docs(query)  

    # --- Affichage des résultats ---
    for i, doc in enumerate(docs):  
        # Parcours de tous les documents retournés
        print(f"--- Document {i+1} ---")  
        # Affiche un séparateur pour chaque document
        print(doc.page_content)  
        # Affiche le contenu textuel du document
