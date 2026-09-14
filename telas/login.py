import streamlit as st
import os

from modulos.auth import (autenticar, encerrar_sessao, trocar_propria_senha,
                          resetar_senha_por_email)
from modulos.db import carregar_perfil_logado, marcar_senha_trocada, registrar_atividade

# ============================================================
# KHRONOS SALES - telas/login.py  (Supabase Auth)
#
# Antes: o app baixava a tabela usuarios e comparava a senha em Python.
# Agora: o Supabase Auth valida o hash, devolve um JWT, e esse JWT e o
# que da acesso ao banco. Se o token nao corresponder a um usuario ativo,
# a RLS simplesmente nao entrega linha nenhuma, mesmo que o codigo erre.
#
# A coluna 'senha' da tabela usuarios nao e mais lida em lugar nenhum.
# ============================================================


def _cabecalho():
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


def _entrar(email, senha):
    ok, erro = autenticar(email, senha)
    if not ok:
        st.error(f"⚠️ {erro}")
        return

    perfil = carregar_perfil_logado(email)

    if not perfil:
        # Autenticou no Auth mas nao tem cadastro ativo vinculado a uma empresa.
        encerrar_sessao()
        st.error("⚠️ Usuário sem cadastro ativo no portal. Procure o administrador.")
        return

    if str(perfil.get("status", "Ativo")).strip().lower() != "ativo":
        encerrar_sessao()
        st.error("⚠️ Usuário inativo. Procure o administrador.")
        return

    st.cache_data.clear()
    st.session_state.update({
        "autenticado": True,
        "empresa_id": str(perfil["empresa_id"]),
        "nome_usuario": perfil.get("nome", ""),
        "email_usuario": str(perfil.get("email", "")).strip().lower(),
        "perfil_usuario": str(perfil.get("perfil", "")).strip(),
        "unidade_usuario": str(perfil.get("unidade", "")).strip(),
        "vertical_usuario": str(perfil.get("vertical", "")).strip(),
        "precisa_trocar_senha": str(perfil.get("trocar_senha", "Nao")).strip().upper() == "SIM"
    })
    registrar_atividade(st.session_state["email_usuario"])
    st.rerun()


def tela_login():
    if "modo_esqueci_senha" not in st.session_state:
        st.session_state["modo_esqueci_senha"] = False

    c1, c2, c3 = st.columns([3, 4, 3])
    with c2:
        st.write("")
        st.write("")
        _cabecalho()

        # --- LOGIN ---
        if not st.session_state["modo_esqueci_senha"]:
            with st.container(border=True):
                email = st.text_input("E-mail corporativo", placeholder="seu.email@suaempresa.com.br")
                senha = st.text_input("Senha", type="password")

                st.write("")
                col_entrar, col_esqueci = st.columns([3, 7])

                with col_entrar:
                    if st.button("Entrar", type="primary", use_container_width=True):
                        if email and senha:
                            with st.spinner("Entrando..."):
                                _entrar(email, senha)
                        else:
                            st.warning("Preencha e-mail e senha.")

                with col_esqueci:
                    if st.button("Esqueci minha senha", use_container_width=False):
                        st.session_state["modo_esqueci_senha"] = True
                        st.rerun()

        # --- RECUPERAÇÃO ---
        else:
            with st.container(border=True):
                st.markdown("### 🔒 Recuperação de Senha")
                st.write("Informe seu e-mail cadastrado. Enviaremos uma senha temporária "
                         "válida para um único acesso.")

                email_rec = st.text_input("E-mail corporativo", key="email_recuperacao")

                st.write("")
                c_env, c_voltar = st.columns([5, 5])

                with c_env:
                    if st.button("Enviar", type="primary", use_container_width=True):
                        if email_rec:
                            with st.spinner("Processando..."):
                                resetar_senha_por_email(email_rec)
                            # mensagem neutra de proposito: nao revela quem tem conta
                            st.success("✅ Se o e-mail estiver cadastrado, você receberá "
                                       "uma senha temporária em instantes.")
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
        st.title("🔒 Defina sua senha")
        st.caption(f"Conta: {st.session_state.get('email_usuario', '')}")
        st.write("Sua conta requer a definição de uma nova senha antes de continuar.")

        with st.form("form_senha"):
            nova = st.text_input("Nova senha", type="password")
            confirma = st.text_input("Confirme a nova senha", type="password")
            enviar = st.form_submit_button("Salvar nova senha", type="primary",
                                           use_container_width=True)

        if enviar:
            if not nova or nova != confirma:
                st.error("⚠️ As senhas não coincidem ou estão vazias.")
            elif len(nova) < 8:
                st.error("⚠️ Use ao menos 8 caracteres.")
            else:
                ok, erro = trocar_propria_senha(nova)
                if ok:
                    marcar_senha_trocada(st.session_state.get("email_usuario", ""))
                    st.session_state["precisa_trocar_senha"] = False
                    st.success("✅ Senha alterada.")
                    st.rerun()
                else:
                    st.error(f"⚠️ {erro}")

        st.write("")
        if st.button("Sair"):
            encerrar_sessao()
            st.rerun()
