import streamlit as st
import os
import json
import time
from datetime import datetime
from pp_agent import answer_question, export_to_pdf  # Assure-toi que cette fonction retourne le PDF en bytes

# === Supprimer une conversation ===
def delete_conversation(filename):
    filepath = os.path.join(CONV_DIR, filename)
    pdf_path = filepath.replace(".json", ".pdf")  # Optionnel : supprimer aussi le PDF
    try:
        os.remove(filepath)
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        # Si la conversation supprimée est active, on vide l'affichage
        if st.session_state.active_conv == filename:
            st.session_state.messages = []
            st.session_state.active_conv = None
        st.rerun()
    except Exception as e:
        st.error(f"Erreur lors de la suppression : {e}")

        

# === Configuration initiale ===
st.set_page_config(
    page_title="Agent Médical IA",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === Gestion du thème ===
THEME_FILE = "theme.json"

if os.path.exists(THEME_FILE):
    with open(THEME_FILE, "r", encoding="utf-8") as f:
        theme_data = json.load(f)
        st.session_state.dark_mode = theme_data.get("dark_mode", False)
else:
    st.session_state.dark_mode = False

def save_theme():
    with open(THEME_FILE, "w", encoding="utf-8") as f:
        json.dump({"dark_mode": st.session_state.dark_mode}, f)

def toggle_theme():
    st.session_state.dark_mode = not st.session_state.dark_mode
    save_theme()

# === Couleurs selon le thème ===
if st.session_state.dark_mode:
    bg_color = "#121212"
    main_text = "#e0e0e0"
    card_bg = "#1e1e1e"
    user_bg = "#0d6efd"
    agent_bg = "#0a5c47"
    accent_color = "#4db6ac"
    border_color = "#333"
    input_bg = "#2d2d2d"
    input_text = "white"
else:
    bg_color = "#f0f4f8"
    main_text = "#1e293b"
    card_bg = "white"
    user_bg = "#0d6efd"
    agent_bg = "#d1e7dd"
    accent_color = "#0d6efd"
    border_color = "#e0e0e0"
    input_bg = "white"
    input_text = "black"

# === CSS global avec animation fluide ===
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
    }}
    .stApp {{
        background-color: {bg_color};
        color: {main_text};
        transition: background-color 0.4s ease, color 0.4s ease;
    }}

    /* === Inputs et placeholders === */
    .stTextInput > div > div > input::placeholder {{
        color: {main_text}88 !important;
        opacity: 0.6;
    }}
    .stTextInput > div > div > input {{
        background-color: {input_bg} !important;
        color: {input_text} !important;
        border: 1px solid {border_color};
        transition: all 0.2s ease;
    }}

    /* === Boutons (envoyer, export, etc.) === */
    .stButton>button {{
        background-color: {accent_color} !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 500;
    }}
    .stButton>button:hover {{
        background-color: {accent_color}dd !important;
        color: white !important;
    }}

    /* === Sidebar (drawer) === */
    [data-testid="stSidebar"] {{
        background-color: {bg_color} !important;
        color: {main_text} !important;
    }}
    [data-testid="stSidebar"] .css-1offfwp {{
        color: {main_text} !important;
    }}
    [data-testid="stSidebar"] .css-1l02zno {{
        background-color: {card_bg} !important;
        border: 1px solid {border_color};
    }}
    

    /* === Animation douce === */
    * {{
        transition: all 0.3s ease !important;
    }}
    .main .block-container {{
        padding-top: 1rem;
        padding-bottom: 2rem;
    }}
    .header {{
        text-align: center;
        margin-bottom: 1.5rem;
    }}
    .header h1 {{
        color: {accent_color};
        margin: 0;
        font-size: 2.4rem;
        transition: color 0.3s ease;
    }}
    .header p {{
        color: {main_text}99;
        font-size: 1.1rem;
    }}
    .theme-toggle {{
        display: flex;
        justify-content: center;
        margin: 1rem 0;
    }}
    .theme-toggle button {{
        background: none;
        border: 1px solid {accent_color};
        color: {accent_color};
        border-radius: 24px;
        padding: 0.5rem 1.2rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }}
    .theme-toggle button:hover {{
        background: {accent_color};
        color: white;
        transform: scale(1.05);
    }}
    .avatar {{
        font-size: 1.5rem;
        margin-right: 0.8rem;
        display: flex;
        align-items: flex-start;
    }}
    .message-row {{
        display: flex;
        margin-bottom: 1.2rem;
        align-items: flex-start;
    }}
    .user-row {{
        flex-direction: row-reverse;
    }}
    .user-row .avatar {{
        margin-left: 0.8rem;
        margin-right: 0;
    }}
    .message {{
        max-width: 70%;
        padding: 0.9rem 1.2rem;
        border-radius: 14px;
        line-height: 1.6;
        font-size: 1rem;
        margin: 0;
    }}
    .user-msg {{
        background-color: {user_bg};
        color: white;
        border-bottom-right-radius: 4px;
    }}
    .agent-msg {{
        background-color: {agent_bg};
        color: {'white' if st.session_state.dark_mode else '#0f5132'};
        border-bottom-left-radius: 4px;
    }}
    .stTextInput > div > div > input {{
        background-color: {input_bg} !important;
        color: {input_text} !important;
    }}
    .new-chat-btn {{
        background-color: #dc3545;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 500;
        cursor: pointer;
        width: 100%;
        margin-bottom: 1rem;
        transition: background-color 0.2s ease;
    }}
    .new-chat-btn:hover {{
        background-color: #c82333;
    }}
    .conv-item {{
         display: flex;
        align-items: center;
        padding: 0.7rem 1rem;
        margin-bottom: 0.5rem;
        background: {card_bg};
        border: 1px solid {border_color};
        border-radius: 10px;
        transition: all 0.2s ease;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    .conv-item:hover {{
        transform: translateY(-1px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-color: {accent_color};
    }}
    .conv-item.active {{
        border: 2px solid {accent_color};
        background: {accent_color}10;
        font-weight: 500;
    }}
    .footer {{
        text-align: center;
        color: {main_text}88;
        font-size: 0.85rem;
        margin-top: 2rem;
        font-style: italic;
    }}
</style>
""", unsafe_allow_html=True)

# === Dossier conversations ===
CONV_DIR = "conversations"
os.makedirs(CONV_DIR, exist_ok=True)

# === Chargement des conversations ===
def load_conversations():
    convs = []
    for f in sorted(os.listdir(CONV_DIR), reverse=True):
        if f.endswith(".json"):
            with open(os.path.join(CONV_DIR, f), "r", encoding="utf-8") as cf:
                data = json.load(cf)
                convs.append({"file": f, "title": data.get("title", f), "timestamp": data.get("timestamp")})
    return convs

# === Charger une conversation ===
def load_chat(filename):
    with open(os.path.join(CONV_DIR, filename), "r", encoding="utf-8") as f:
        data = json.load(f)
        st.session_state.messages = data["messages"]
        st.session_state.active_conv = filename

# === Sauvegarder la conversation actuelle ===
def save_current_chat():
    if "messages" in st.session_state and st.session_state.messages:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conv_{timestamp}.json"
        filepath = os.path.join(CONV_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "title": f"Discussion du {timestamp[:8]}",
                "timestamp": timestamp,
                "messages": st.session_state.messages
            }, f, ensure_ascii=False, indent=2)
        st.session_state.active_conv = filename

# === Initialisation des sessions ===
if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_conv" not in st.session_state:
    st.session_state.active_conv = None

# === Sidebar : Historique des conversations ===

with st.sidebar:
    st.markdown("<h3 style='text-align: center;'> Historique</h3>", unsafe_allow_html=True)

    if st.button(" Nouvelle conversation", key="new_conv", help="Commencer une nouvelle discussion"):
        st.session_state.messages = []
        st.session_state.active_conv = None
        st.rerun()

    st.markdown("---")

     # === Liste des conversations avec bouton de suppression ===
    conversations = load_conversations()
    for conv in conversations:
        title = conv["title"]
        filename = conv["file"]
        is_active = st.session_state.active_conv == filename

        # Créer deux colonnes : nom de la conversation + bouton poubelle
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(title, key=f"conv_{filename}"):
                load_chat(filename)
                st.rerun()
        with col2:
            if st.button("🗑️", key=f"del_{filename}", help=f"Supprimer {title}"):
                delete_conversation(filename)

        # Optionnel : style visuel pour la conversation active
        if is_active:
            st.markdown(
                f"<div style='font-size: 0.85rem; color: {accent_color}; text-align: center; margin-top: -10px;'>En cours</div>",
                unsafe_allow_html=True
            )

    # === Espace flexible pour pousser le bouton vers le bas ===
    st.markdown("<div style='flex-grow: 1;'></div>", unsafe_allow_html=True)
    st.markdown("---")

    # === Bouton Mode Sombre/Clair en bas du drawer ===
    st.markdown('<div class="theme-toggle" style="margin-top: auto;">', unsafe_allow_html=True)
    st.button(
        "🌙 Mode Sombre" if not st.session_state.dark_mode else "☀️ Mode Clair",
        on_click=toggle_theme,
        key="btn_theme_toggle"
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # === Footer du drawer ===
    st.markdown("""
    <div style='text-align: center; color: #888; font-size: 0.8rem; margin-top: 1rem;'>
        v1.0 • Agent Médical IA
    </div>
    """, unsafe_allow_html=True)

# === En-tête principal ===
st.markdown("""
<div class="header">
    <h1>🩺 Agent Médical IA</h1>
   
</div>
""", unsafe_allow_html=True)

# === Zone de discussion ===
chat_container = st.container()

with chat_container:
    for role, content in st.session_state.messages:
        if role == "user":
            st.markdown(f"""
            <div class="message-row user-row">
                <div class="avatar">👤</div>
                <div class="message user-msg">{content}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="message-row">
                <div class="avatar">🩺</div>
                <div class="message agent-msg">{content}</div>
            </div>
            """, unsafe_allow_html=True)

# === Formulaire d'entrée ===
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input(
        "Votre question",
        placeholder="Ex : Quels sont les symptômes de syndrome de Sjögren ?",
        label_visibility="collapsed"
    )
    submitted = st.form_submit_button("Envoyer ➤")

    if submitted and user_input.strip():
        st.session_state.messages.append(("user", user_input))
        with st.spinner("🧠 L'agent médical réfléchit..."):
            time.sleep(0.8)
            response = answer_question(user_input)
            st.session_state.messages.append(("agent", response))
        st.rerun()

# === Bouton Export PDF (téléchargement direct) ===
if st.session_state.messages:
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📄 Exporter en PDF", use_container_width=True):
            pdf_bytes = export_to_pdf(st.session_state.messages)  # Doit retourner les bytes du PDF
            st.download_button(
                label="⬇️ Télécharger le PDF",
                data=pdf_bytes,
                file_name=f"conversation_medical_{datetime.now().strftime('%H%M')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

# === Sauvegarder automatiquement la conversation à chaque interaction ===
if st.session_state.messages and not st.session_state.active_conv:
    save_current_chat()

# === Footer ===
st.markdown("""
<div class="footer">
    ⚠️ À usage informatif uniquement. Ne remplace pas un avis médical.
</div>
""", unsafe_allow_html=True)