# === interface_agent.py - VERSION FIXED POUR DEPLOIEMENT ===
# Interface web pour un agent médical IA avec Streamlit.
# Inclut :
# - Historique de conversation
# - Streaming de réponses
# - Export PDF
# - Sidebar pour gérer les conversations

# === IMPORTS ===
import streamlit as st        # Framework pour créer des interfaces web interactives
import os                     # Gestion des fichiers et des dossiers
import json                   # Lecture / écriture de fichiers JSON
from datetime import datetime # Pour horodatage des conversations et fichiers
from pp_agent import answer_question, export_to_pdf  # Fonctions backend du chatbot
import base64                 # Pour encoder des images en base64 (affichage logo)

# === LOGO ET CONFIGURATION DE LA PAGE ===
# Utilise un chemin relatif (valide en local + cloud)
logo_path = os.path.join("img", "logo.jfif")

# Toujours mettre un emoji pour l’onglet navigateur (plus fiable que les images)
st.set_page_config(
    page_title="Agent Médical IA",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# === RÉPERTOIRE POUR LES CONVERSATIONS ===
CONV_DIR = "conversations"
os.makedirs(CONV_DIR, exist_ok=True)  # Crée le dossier si non existant

# === FONCTIONS UTILITAIRES ===
def load_conversations():
    convs = []
    for f in sorted(os.listdir(CONV_DIR), reverse=True):
        if f.endswith(".json"):
            try:
                with open(os.path.join(CONV_DIR, f), "r", encoding="utf-8") as cf:
                    data = json.load(cf)
                    convs.append({
                        "file": f,
                        "title": data.get("title", f),
                        "timestamp": data.get("timestamp")
                    })
            except:
                continue
    return convs

def save_chat(filename, messages, title=None):
    formatted = [{"role": "user" if r=="user" else "assistant", "content": c} for r,c in messages]
    data = {
        "title": title or f"Discussion du {datetime.now().strftime('%Y-%m-%d')}",
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "messages": formatted
    }
    with open(os.path.join(CONV_DIR, filename), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_chat(filename):
    try:
        with open(os.path.join(CONV_DIR, filename), "r", encoding="utf-8") as f:
            data = json.load(f)
            messages = [(m["role"] if m["role"]=="user" else "agent", m["content"]) for m in data["messages"]]
            return messages, data.get("title", filename)
    except:
        return [], filename

# === INITIALISATION DE LA SESSION STREAMLIT ===
if "messages" not in st.session_state: st.session_state.messages = []
if "active_conv" not in st.session_state: st.session_state.active_conv = None
if "conv_title" not in st.session_state: st.session_state.conv_title = "Nouvelle conversation"
if "waiting" not in st.session_state: st.session_state.waiting = False

# === SIDEBAR ===
with st.sidebar:
    st.markdown("### 💬 Conversations")

    if st.button("➕ Nouvelle conversation"):
        st.session_state.messages = []
        st.session_state.active_conv = None
        st.session_state.conv_title = "Nouvelle conversation"
        st.rerun()

    convs = load_conversations()
    for conv in convs:
        col1, col2 = st.columns([4,1])
        with col1:
            if st.button(conv["title"], key=f"open_{conv['file']}"):
                msgs, title = load_chat(conv["file"])
                st.session_state.messages = msgs
                st.session_state.active_conv = conv["file"]
                st.session_state.conv_title = title
                st.rerun()
        with col2:
            if st.button("🗑️", key=f"del_{conv['file']}"):
                os.remove(os.path.join(CONV_DIR, conv["file"]))
                st.rerun()

    st.markdown("---")
    if st.session_state.active_conv:
        new_title = st.text_input("✏️ Renommer", st.session_state.conv_title)
        if new_title != st.session_state.conv_title:
            st.session_state.conv_title = new_title
            save_chat(st.session_state.active_conv, st.session_state.messages, title=new_title)

    st.markdown("<br><center>⚕️ Medical Agent v1.3</center>", unsafe_allow_html=True)

# === HEADER AVEC LOGO ===
if os.path.exists(logo_path):
    with open(logo_path, "rb") as f:
        data = f.read()
    encoded = base64.b64encode(data).decode()
    st.markdown(
        f"""
        <h1 style='text-align:center; margin-top:10px;'>
            <img src="data:image/jpg;base64,{encoded}" width="100">
            Agent Médical IA
        </h1>
        """,
        unsafe_allow_html=True
    )
else:
    st.markdown("<h1 style='text-align:center;'>Agent Médical IA</h1>", unsafe_allow_html=True)

# === CHAT CONTAINER ===
chat_box = st.container()

# === FORMULAIRE DE SAISIE UTILISATEUR ===
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_area(
        "Votre question :",
        placeholder="Décrivez vos symptômes ou posez une question...",
        height=80
    )
    submitted = st.form_submit_button("Envoyer ➤")

# === AJOUTER LE MESSAGE UTILISATEUR ===
if submitted and user_input.strip():
    st.session_state.messages.append(("user", user_input))
    if not st.session_state.active_conv:
        filename = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        st.session_state.active_conv = filename
    save_chat(st.session_state.active_conv, st.session_state.messages, st.session_state.conv_title)

# === AFFICHAGE DES MESSAGES ===
for role, content in st.session_state.messages:
    if role == "user":
        chat_box.markdown(f"""
        <div style="display:flex;justify-content:flex-end;margin:6px 0;">
            <div style="background:#0d6efd;color:white;padding:10px 14px;border-radius:12px;max-width:70%">{content}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        chat_box.markdown(f"""
        <div style="display:flex;justify-content:flex-start;margin:6px 0;">
            <div style="background:#e9f7ef;color:#0f5132;padding:10px 14px;border-radius:12px;max-width:70%">{content}</div>
        </div>
        """, unsafe_allow_html=True)

# === STREAMING DE LA RÉPONSE ===
if submitted and user_input.strip():
    response_placeholder = chat_box.empty()
    response_text = ""
    response_placeholder.markdown("<i>Agent est en train d'écrire...</i>", unsafe_allow_html=True)

    # Ici on ne peut pas faire for chunk in answer_question si answer_question renvoie une str
    # On le remplace par réponse complète d'un coup
    response_text = answer_question(user_input)

    response_placeholder.markdown(f"""
        <div style="display:flex;justify-content:flex-start;margin:6px 0;">
            <div style="background:#e9f7ef;color:#0f5132;padding:10px 14px;border-radius:12px;max-width:70%;">
                {response_text}
            </div>
        </div>
    """, unsafe_allow_html=True)

    st.session_state.messages.append(("agent", response_text))
    save_chat(st.session_state.active_conv, st.session_state.messages, st.session_state.conv_title)
    st.stop()


# === EXPORT PDF ===
if st.session_state.messages:
    if st.button("📄 Exporter en PDF"):
        pdf_path = export_to_pdf([(u, a) for u, a in st.session_state.messages])
        with open(pdf_path, "rb") as f:
            st.download_button(
                label="⬇️ Télécharger le PDF",
                data=f,
                file_name=f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf"
            )

# === FOOTER ===
st.markdown("<p style='text-align:center;color:gray;'>⚠️ À usage informatif uniquement. Ne remplace pas un avis médical.</p>", unsafe_allow_html=True)
