import streamlit as st
from telas.login import tela_login, tela_trocar_senha
from telas.dashboard import tela_principal

# 1. Configuração da página (Ícone com a Logo e Menu Lateral forçado para iniciar aberto)
st.set_page_config(
    page_title="Khronos Sales", 
    page_icon="logo.jpg",   
    layout="wide",
    initial_sidebar_state="expanded" # <-- Este é o comando que força o menu a abrir
)

# 2. Estilização CSS Padrão
st.markdown("""
    <style>
    div[data-testid="stVerticalBlock"] { gap: 0.3rem !important; }
    div[data-testid="stMarkdownContainer"] p { margin-bottom: 0.5rem !important; padding-top: 2px !important; }
    div.stButton > button { min-height: 2.2rem !important; height: auto !important; padding: 4px 15px !important; text-align: left !important; display: flex !important; justify-content: flex-start !important; align-items: center !important; width: 100% !important; }
    div.stButton > button * { text-align: left !important; justify-content: flex-start !important; }
    div.stButton > button[kind="primary"] { justify-content: center !important; text-align: center !important; }
    div.stButton > button[kind="primary"] * { text-align: center !important; justify-content: center !important; }
    .card-mobile { background-color: #f8fafc; border-left: 4px solid #0066cc; padding: 12px; border-radius: 6px; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# 3. Criação da Memória Inicial
if "autenticado" not in st.session_state:
    st.session_state.update({
        "autenticado": False, 
        "nome_usuario": "", 
        "email_usuario": "", 
        "perfil_usuario": "Consultor", 
        "unidade_usuario": "", 
        "vertical_usuario": "", 
        "carrinho": [], 
        "desc_prod": 0.0, 
        "desc_alarme": 0.0, 
        "desc_imagem": 0.0, 
        "etapa_atual": "lead",  # <-- Voltou para abrir direto no Cadastro do Cliente
        "lead_dados": {}, 
        "lead_salvo": False, 
        "msg_sucesso": "", 
        "renovar_proposta_idx": None, 
        "renovar_proposta_dados": {}, 
        "proposta_idx_editando": None, 
        "editando_lead_idx": None, 
        "nome_proposta_atual": "", 
        "temp_proposta_atual": "Selecione...", 
        "status_proposta_atual": "Selecione...", 
        "status_credito_deps": None,
        "ultimo_gps_capturado": "", 
        "item_aberto": None, 
        "unidade_mo_selecionada": None, 
        "modo_visao_leads": "📱 Cartões (Celular)", 
        "modo_visao_propostas": "📱 Cartões (Celular)", 
        "precisa_trocar_senha": False
    })

# 4. Roteamento de Telas
if not st.session_state.get("autenticado", False): 
    tela_login()
elif st.session_state.get("precisa_trocar_senha", False):
    tela_trocar_senha()
else: 
    tela_principal()
