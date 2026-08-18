import streamlit as st
import os
from modulos.db import carregar_usuarios, atualizar_senha_banco

SENHA_PADRAO_SISTEMA = "Khronos@2026"

def exibir_topo_com_logo(titulo="Khronos Sales", subtitulo="Acesso ao Portal Comercial de Vendas"):
    c_logo, c_txt = st.columns([1, 8])
    with c_logo:
        if os.path.exists("logo.jpg"): st.image("logo.jpg", width=65)
        else: st.write("🛡️")
    with c_txt:
        st.markdown(f"<h1 style='margin:0; padding:0; line-height: 1.1;'>{titulo}</h1>", unsafe_allow_html=True)
        st.caption(subtitulo)

def tela_login():
    exibir_topo_com_logo("Khronos Sales", "Acesso ao Portal Comercial de Vendas")
    st.write("---")
    with st.form("form_login"):
        email_input = st.text_input("E-mail corporativo").strip().lower()
        senha_input = st.text_input("Senha", type="password").strip()
        if st.form_submit_button("Entrar", type="primary"):
            st.cache_data.clear() 
            df_us = carregar_usuarios()
            if df_us.empty: st.error("❌ A base de usuários retornou vazia. Aguarde 1 minuto se for limite de cota do Google.")
            else:
                df_us['Email_C'] = df_us['Email'].astype(str).str.strip().str.lower()
                df_us['Senha_C'] = df_us['Senha'].astype(str).str.strip()
                match = df_us[(df_us['Email_C'] == email_input) & (df_us['Senha_C'] == senha_input)]
                if not match.empty:
                    st.session_state.update({
                        "autenticado": True, "nome_usuario": str(match.iloc[0].get('Nome', '')), "email_usuario": email_input,
                        "perfil_usuario": str(match.iloc[0].get('Perfil', 'Consultor')).strip(), "unidade_usuario": str(match.iloc[0].get('Unidade', '')).strip(),
                        "vertical_usuario": str(match.iloc[0].get('Vertical', '')).strip(), "precisa_trocar_senha": (str(match.iloc[0].get('Senha', '')).strip() == SENHA_PADRAO_SISTEMA)
                    }); st.rerun()
                else: st.error("❌ E-mail ou senha incorretos.")

def tela_trocar_senha():
    exibir_topo_com_logo("Khronos Sales", "Atualização Obrigatória de Senha")
    st.write("---")
    st.warning("🔒 **Ação Necessária:** Detectamos que você está usando a senha provisória de acesso. Para garantir a segurança da sua conta, defina uma nova senha.")
    with st.form("form_trocar_senha"):
        nova_senha, confirma_senha = st.text_input("Nova Senha", type="password"), st.text_input("Confirme a Nova Senha", type="password")
        if st.form_submit_button("Salvar Nova Senha e Continuar", type="primary"):
            if len(nova_senha) < 6: st.error("A sua nova senha deve ter pelo menos 6 caracteres.")
            elif nova_senha != confirma_senha: st.error("As senhas digitadas não coincidem. Tente novamente.")
            elif nova_senha == SENHA_PADRAO_SISTEMA: st.error("Você não pode utilizar a mesma senha padrão.")
            else:
                if atualizar_senha_banco(st.session_state["email_usuario"], nova_senha):
                    st.success("✅ Senha atualizada com sucesso! Acessando o sistema...")
                    st.session_state["precisa_trocar_senha"] = False; st.cache_data.clear(); st.rerun()
                else: st.error("Erro ao salvar a nova senha. Tente novamente.")
