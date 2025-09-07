Agent Médical IA – Spécialisation Syndrome de Sjögren

Agent Médical IA est une application web interactive spécialisée dans le syndrome de Sjögren, permettant aux utilisateurs (patients, étudiants ou professionnels de santé) de poser des questions et d’obtenir des réponses basées sur une base de connaissances internes et des recherches web fiables.

L’agent utilise la recherche augmentée par récupération (RAG) pour fournir des réponses contextualisées et documentées, avec un historique complet et la possibilité d’exporter les conversations en PDF.

FONCTIONNALITES PRINCIPALES

💬 Chat interactif spécialisé : Posez vos questions sur le syndrome de Sjögren et recevez des réponses détaillées.

📚 RAG sur documents internes : Recherche dans un vectorstore FAISS contenant articles scientifiques, protocoles médicaux et guides cliniques.

🌐 Recherche web fiable : Complément d’information via Google Serper.dev lorsque les documents internes ne suffisent pas.

📝 Historique des conversations : Chaque échange est sauvegardé automatiquement en JSON pour consultation ou export.

📄 Export PDF : Génération d’un PDF reprenant l’intégralité de la conversation.

🗂️ Sidebar de gestion des conversations : Créez, ouvrez, supprimez et renommez vos conversations facilement.

⚙️ Multi-environnements : Compatible avec Mistral Cloud ou Ollama local.

🔬 Focus scientifique : L’agent cite toujours la source du document utilisé pour éviter les informations non vérifiées.

STRUCTURE DU PROJET

Agent-Medical-IA/
│
├─ img/
│  └─ logo.jfif               # Logo de l’application
│
├─ vectorstore/               # Base de connaissances RAG spécialisée Sjögren (FAISS)
│
├─ conversations/             # Historique JSON des conversations
│
├─ pp_agent.py                # Backend de l’agent IA (RAG, LLM, PDF)
├─ interface_agent.py         # Interface web Streamlit
├─ mcp_client.py              # Module MCP pour logs JSONL
├─ requirements.txt           # Dépendances Python
└─ README.md                  # Ce fichier

INSTALLATION

1 Cloner le dépôt

git clone https://github.com/atrous1/Ia-Agent
cd Ia-Agent

2 Créer un environnement Python et installer les dépendances

python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows

pip install -r requirements.txt

3 Configurer les clés API (optionnel pour Mistral Cloud ou Serper.dev)

export MISTRAL_API_KEY="votre_cle_api"
export SERPER_API_KEY="votre_cle_api"

4 Préparer la base de documents FAISS spécialisée Sjögren

Collecter des documents fiables (articles scientifiques, recommandations cliniques, protocoles de soins).

Générer les embeddings avec sentence-transformers/all-MiniLM-L6-v2.

Sauvegarder le vectorstore dans vectorstore/.

UTILISATION

Lancer l’interface Streamlit : streamlit run interface_agent.py

Accéder à l’URL locale indiquée par Streamlit (ex: http://localhost:8501).

Créer une nouvelle conversation ou charger une conversation existante.

Poser vos questions sur le syndrome de Sjögren.

Télécharger la conversation complète en PDF pour consultation ou archivage.

FONCTIONNEMENT INTERNE 

RAG : Recherche d’informations dans la base FAISS sur le syndrome de Sjögren.

Fallback Web : Recherche web via Serper.dev si aucun document interne pertinent n’est trouvé.

Agents Autogen : AssistantAgent et UserProxyAgent gèrent la génération de réponses et l’appel des fonctions RAG/Web.

MCP Logging : Chaque interaction est horodatée et enregistrée dans mcp_logs.jsonl.

DEPENDANCES PRINCIPALES

streamlit : Interface web interactive

fpdf : Génération de PDF

autogen : Agents IA

langchain_community : FAISS vectorstore et embeddings

requests : Requêtes HTTP pour recherche web

sentence-transformers : Modèle d’embeddings pour documents internes

mcp_client.py : Logging des événements MCP

BONNES PRATIQUES POUR LA SPECIALISATION SJOGEN

Mettre à jour régulièrement la base de documents internes avec les dernières recommandations cliniques.

Citer toujours les sources des documents utilisés.

Limiter l’usage à informations éducatives ou support aux professionnels, pas pour diagnostic médical direct.

AVERTISSEMENTS 

⚠️ Usage informatif uniquement : Ce projet ne remplace pas un avis médical professionnel.

Les réponses proviennent de documents internes et du web ; elles peuvent contenir des imprécisions.

Pour des diagnostics ou traitements, consulter un professionnel de santé.

LICENCE

Ce projet est sous licence MIT — voir le fichier LICENSE pour plus de détails.
