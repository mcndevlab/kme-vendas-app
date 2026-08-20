import streamlit as st
import os
from modulos.db import carregar_usuarios
from modulos.utils import enviar_email_recuperacao_senha

def tela_login():
    # Cria a variável de memória para saber qual tela mostrar (Login ou Esqueci Senha)
    if "modo_esqueci_senha" not in st.session_state:
        st.session_state["modo_esqueci_senha"] = False

    c1, c2, c3 = st.columns([3, 4, 3])
    with c2:
        st.write("")
        st.write("")
        c_logo, c_tit = st.columns([2, 8])
        with c_logo:
            if os.path.exists("logo.jpg"): st.image("logo.jpg", width=80)
        with c_tit:
            st.markdown("<h1 style='margin-bottom:0; padding-bottom:0;'>Khronos Sales</h1><p style='color:gray; margin-top:0;'>Acesso ao Portal Comercial de Vendas</p>", unsafe_allow_html=True)
        st.divider()

        # --- TELA: FAZER LOGIN PADRÃO ---
        if not st.session_state["modo_esqueci_senha"]:
            with st.container(border=True):
                email = st.text_input("E-mail corporativo", placeholder="seu.email@grupokhronos.com.br")
                senha = st.text_input("Senha", type="password")
                
                st.write("")
                col_btn_entrar, col_btn_esqueci = st.columns([3, 7])
                
                with col_btn_entrar:
                    if st.button("Entrar", type="primary", use_container_width=True):
                        if email and senha:
                            df_users = carregar_usuarios()
                            df_users['Email_C'] = df_users['Email'].astype(str).str.strip().str.lower()
                            match = df_users[(df_users['Email_C'] == email.strip().lower()) & (df_users['Senha'].astype(str) == str(senha))]
                            
                            if not match.empty:
                                user = match.iloc[0]
                                st.session_state.update({
                                    "autenticado": True,
                                    "nome_usuario": user['Nome'],
                                    "email_usuario": user['Email_C'],
                                    "perfil_usuario": str(user['Perfil']).strip(),
                                    "unidade_usuario": str(user['Unidade']).strip(),
                                    "vertical_usuario": str(user.get('Vertical', '')).strip(),
                                    "precisa_trocar_senha": str(user.get('Trocar_Senha', 'Nao')).strip().upper() == 'SIM'
                                })
                                st.rerun()
                            else:
                                st.error("⚠️ E-mail ou senha incorretos.")
                        else:
                            st.warning("Preencha e-mail e senha.")
                            
                with col_btn_esqueci:
                    if st.button("Esqueci minha senha", use_container_width=False):
                        st.session_state["modo_esqueci_senha"] = True
                        st.rerun()
                        
        # --- TELA: RECUPERAÇÃO DE SENHA ---
        else:
            with st.container(border=True):
                st.markdown("### 🔒 Recuperação de Senha")
                st.write("Digite seu e-mail cadastrado no portal para receber sua senha atual.")
                
                email_rec = st.text_input("E-mail corporativo", key="email_recuperacao")
                
                st.write("")
                c_env, c_voltar = st.columns([5, 5])
                
                with c_env:
                    if st.button("Enviar Senha", type="primary", use_container_width=True):
                        if email_rec:
                            df_users = carregar_usuarios()
                            df_users['Email_C'] = df_users['Email'].astype(str).str.strip().str.lower()
                            match = df_users[df_users['Email_C'] == email_rec.strip().lower()]
                            
                            if not match.empty:
                                senha_atual = match.iloc[0]['Senha']
                                # Aciona o motor do utils.py para disparar o email
                                if enviar_email_recuperacao_senha(email_rec.strip().lower(), senha_atual):
                                    st.success("✅ Senha enviada! Verifique seu e-mail.")
                            else:
                                st.error("⚠️ E-mail não encontrado no sistema.")
                        else:
                            st.warning("Preencha o e-mail.")
                            
                with c_voltar:
                    if st.button("Voltar ao Login", use_container_width=True):
                        st.session_state["modo_esqueci_senha"] = False
                        st.rerun()

def tela_trocar_senha():
    c1, c2, c3 = st.columns([3, 4, 3])
    with c2:
        st.write("")
        st.write("")
        st.title("🔒 Troca de Senha")
        st.write("Sua conta requer a definição de uma nova senha segura.")
        with st.form("form_senha"):
            nova_senha = st.text_input("Nova Senha", type="password")
            confirma = st.text_input("Confirme a Nova Senha", type="password")
            if st.form_submit_button("Salvar Nova Senha", type="primary", use_container_width=True):
                if nova_senha and nova_senha == confirma:
                    st.warning("⚠️ Função de salvar no banco de dados temporariamente desativada.")
                else:
                    st.error("⚠️ As senhas não coincidem ou estão vazias.")
