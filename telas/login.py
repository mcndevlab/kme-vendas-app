import streamlit as st
import os
from modulos.db import buscar_usuario_para_login, atualizar_senha_banco
from modulos.utils import enviar_email_recuperacao_senha

# ============================================================
# KHRONOS SALES - telas/login.py  (versao multiempresa)
#
# Mudancas:
#  1. A busca do usuario passou a ser cross-tenant e explicita
#     (buscar_usuario_para_login), porque no momento do login ainda
#     nao sabemos a empresa. Todo o resto do sistema ja e filtrado.
#  2. empresa_id entra na sessao. Sem ele, nenhuma consulta do db.py
#     funciona: e essa a trava.
#  3. Bloqueio de usuario inativo e de empresa sem vinculo.
#
# Ainda pendente (frente 2 - seguranca):
#  - senha em texto puro no banco
#  - recuperacao que envia a senha atual por e-mail
# ============================================================


def tela_login():
    if "modo_esqueci_senha" not in st.session_state:
        st.session_state["modo_esqueci_senha"] = False

    c1, c2, c3 = st.columns([3, 4, 3])
    with c2:
        st.write("")
        st.write("")
        c_logo, c_tit = st.columns([2, 8])
        with c_logo:
            if os.path.exists("logo.jpg"):
                st.image("logo.jpg", width=80)
        with c_tit:
            st.markdown(
                "<h1 style='margin-bottom:0; padding-bottom:0;'>Khronos Sales</h1>"
                "<p style='color:gray; margin-top:0;'>Acesso ao Portal Comercial de Vendas</p>",
                unsafe_allow_html=True)
        st.divider()

        # --- TELA: FAZER LOGIN PADRÃO ---
        if not st.session_state["modo_esqueci_senha"]:
            with st.container(border=True):
                email = st.text_input("E-mail corporativo", placeholder="seu.email@suaempresa.com.br")
                senha = st.text_input("Senha", type="password")

                st.write("")
                col_btn_entrar, col_btn_esqueci = st.columns([3, 7])

                with col_btn_entrar:
                    if st.button("Entrar", type="primary", use_container_width=True):
                        if not (email and senha):
                            st.warning("Preencha e-mail e senha.")
                            st.stop()

                        user = buscar_usuario_para_login(email)

                        if not user or str(user.get("senha", "")) != str(senha):
                            st.error("⚠️ E-mail ou senha incorretos.")
                            st.stop()

                        if str(user.get("status", "Ativo")).strip().lower() != "ativo":
                            st.error("⚠️ Usuário inativo. Procure o administrador.")
                            st.stop()

                        if not user.get("empresa_id"):
                            st.error("⚠️ Usuário sem empresa vinculada. Procure o administrador.")
                            st.stop()

                        # limpa cache herdado de outra sessão/empresa
                        st.cache_data.clear()

                        st.session_state.update({
                            "autenticado": True,
                            "empresa_id": str(user["empresa_id"]),
                            "nome_usuario": user.get("nome", ""),
                            "email_usuario": str(user.get("email", "")).strip().lower(),
                            "perfil_usuario": str(user.get("perfil", "")).strip(),
                            "unidade_usuario": str(user.get("unidade", "")).strip(),
                            "vertical_usuario": str(user.get("vertical", "")).strip(),
                            "precisa_trocar_senha": str(user.get("trocar_senha", "Nao")).strip().upper() == "SIM"
                        })

                        from modulos.db import registrar_atividade
                        registrar_atividade(st.session_state["email_usuario"])
                        st.rerun()

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
                            user = buscar_usuario_para_login(email_rec)
                            if user:
                                if enviar_email_recuperacao_senha(
                                        str(user.get("email", "")).strip().lower(),
                                        user.get("senha", "")):
                                    st.success("✅ Senha enviada! Verifique seu e-mail.")
                            else:
                                # mensagem neutra evita descobrir quem tem conta
                                st.success("✅ Se o e-mail estiver cadastrado, você receberá a senha.")
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
                if not nova_senha or nova_senha != confirma:
                    st.error("⚠️ As senhas não coincidem ou estão vazias.")
                elif len(nova_senha) < 8:
                    st.error("⚠️ A senha precisa ter ao menos 8 caracteres.")
                elif atualizar_senha_banco(st.session_state.get("email_usuario", ""), nova_senha):
                    st.session_state["precisa_trocar_senha"] = False
                    st.cache_data.clear()
                    st.success("✅ Senha alterada!")
                    st.rerun()
                else:
                    st.error("⚠️ Não foi possível salvar a nova senha.")
