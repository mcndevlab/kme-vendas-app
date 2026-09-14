import time
import secrets
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import streamlit as st
from supabase import create_client, Client

# ============================================================
# KHRONOS SALES - modulos/auth.py
#
# Por que este arquivo existe:
#
# Ate aqui o app falava com o banco usando uma chave fixa e um cliente
# guardado em @st.cache_resource. Cache_resource e por PROCESSO, nao por
# sessao: um cliente carregando o token do usuario A seria reaproveitado
# pelo usuario B. E o mesmo problema do cache de dados, na camada de conexao.
#
# Agora existem dois clientes, com papeis bem separados:
#
#   cliente_sessao()  -> chave anon + JWT do usuario logado.
#                        Toda operacao normal do app passa por aqui.
#                        A RLS do banco filtra por empresa automaticamente.
#
#   conectar_admin()  -> chave service_role. Ignora RLS.
#                        So para o que o proprio usuario nao pode fazer:
#                        criar usuario, resetar senha de terceiro,
#                        gravar ultimo_acesso.
#
# A service_role roda apenas no servidor do Streamlit e nunca chega ao
# navegador. Ainda assim, use o minimo possivel.
#
# secrets.toml esperado:
#   [supabase]
#   url = "https://xxxx.supabase.co"
#   anon_key = "eyJ..."
#   service_key = "eyJ..."
# ============================================================


def _url():
    return st.secrets["supabase"]["url"]


def _anon_key():
    s = st.secrets["supabase"]
    return s.get("anon_key") or s.get("key")


def _service_key():
    s = st.secrets["supabase"]
    return s.get("service_key") or s.get("key")


@st.cache_resource
def conectar_admin() -> Client:
    """Cliente service_role. Nao carrega token de usuario, pode ser global."""
    return create_client(_url(), _service_key())


def _guardar_tokens(sessao):
    st.session_state["_sb_tokens"] = {
        "access_token": sessao.access_token,
        "refresh_token": sessao.refresh_token,
        "expires_at": int(getattr(sessao, "expires_at", 0) or (time.time() + 3600)),
    }


def cliente_sessao() -> Client:
    """
    Cliente da sessao atual, sempre com o token do usuario logado aplicado.
    Antes de expirar, renova sozinho.
    """
    cli = st.session_state.get("_sb_client")
    if cli is None:
        cli = create_client(_url(), _anon_key())
        st.session_state["_sb_client"] = cli

    tokens = st.session_state.get("_sb_tokens")
    if not tokens:
        return cli  # ainda na tela de login, sem identidade

    if time.time() > tokens["expires_at"] - 60:
        try:
            resp = cli.auth.refresh_session(tokens["refresh_token"])
            _guardar_tokens(resp.session)
            tokens = st.session_state["_sb_tokens"]
        except Exception:
            encerrar_sessao()
            st.warning("Sua sessão expirou. Faça login novamente.")
            st.stop()

    cli.postgrest.auth(tokens["access_token"])
    return cli


def autenticar(email, senha):
    """
    Faz login no Supabase Auth. Retorna (ok, erro).
    A senha nunca e comparada em Python: quem valida o hash e o Auth.
    """
    try:
        cli = create_client(_url(), _anon_key())
        resp = cli.auth.sign_in_with_password({
            "email": str(email).strip().lower(),
            "password": senha
        })
        if not resp or not resp.session:
            return False, "E-mail ou senha incorretos."
        st.session_state["_sb_client"] = cli
        _guardar_tokens(resp.session)
        return True, None
    except Exception as e:
        msg = str(e).lower()
        if "invalid login" in msg or "credentials" in msg:
            return False, "E-mail ou senha incorretos."
        if "email not confirmed" in msg:
            return False, "E-mail ainda não confirmado. Procure o administrador."
        return False, f"Não foi possível entrar: {e}"


def encerrar_sessao():
    cli = st.session_state.get("_sb_client")
    if cli is not None:
        try:
            cli.auth.sign_out()
        except Exception:
            pass
    for chave in ("_sb_client", "_sb_tokens", "_sb_sessao_ativa"):
        st.session_state.pop(chave, None)
    st.session_state["autenticado"] = False
    st.session_state["empresa_id"] = None
    st.cache_data.clear()


def trocar_propria_senha(nova_senha):
    """O proprio usuario define a senha. Vai direto para o Auth, em hash."""
    try:
        cliente_sessao().auth.update_user({"password": nova_senha})
        return True, None
    except Exception as e:
        msg = str(e).lower()
        if "should be at least" in msg or "weak" in msg:
            return False, "Senha muito fraca. Use ao menos 8 caracteres."
        if "different from the old" in msg:
            return False, "A nova senha precisa ser diferente da atual."
        return False, f"Não foi possível alterar a senha: {e}"


def _senha_temporaria(tamanho=12):
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho)) + "!9"


def _enviar_email(destino, assunto, html):
    if "smtp" not in st.secrets:
        st.info("💡 E-mail gerado. (Configure SMTP no Cloud para envio real.)")
        return True
    try:
        remetente = st.secrets["smtp"]["email"]
        msg = MIMEMultipart()
        msg["From"] = remetente
        msg["To"] = destino
        msg["Subject"] = assunto
        msg.attach(MIMEText(html, "html"))
        server = smtplib.SMTP(st.secrets["smtp"]["server"], st.secrets["smtp"]["port"])
        server.starttls()
        server.login(remetente, st.secrets["smtp"]["password"])
        server.send_message(msg)
        server.quit()
        return True
    except Exception:
        return False


def resetar_senha_por_email(email):
    """
    Recuperacao de senha. Gera uma senha temporaria, grava no Auth e envia.
    Marca trocar_senha = 'Sim', entao ela serve para um acesso so.

    Substitui o fluxo antigo, que enviava a senha real do usuario por e-mail.

    Sempre retorna True: a tela nao deve revelar se o e-mail existe ou nao.
    """
    email = str(email).strip().lower()
    admin = conectar_admin()
    try:
        res = admin.table("usuarios").select("id, nome, auth_user_id, empresa_id") \
            .eq("email", email).limit(1).execute()
        if not res.data:
            return True

        u = res.data[0]
        if not u.get("auth_user_id"):
            return True  # ainda nao migrado para o Auth

        temp = _senha_temporaria()
        admin.auth.admin.update_user_by_id(u["auth_user_id"], {"password": temp})
        admin.table("usuarios").update({"trocar_senha": "Sim"}).eq("id", u["id"]).execute()

        html = f"""
        <div style="font-family: Arial, sans-serif; color: #1e293b;">
            <h2 style="color:#e20613;">Recuperação de Senha</h2>
            <p>Olá, {u.get('nome', '')}.</p>
            <p>Sua senha temporária de acesso ao Khronos Sales é:</p>
            <p style="font-size:20px;"><strong>{temp}</strong></p>
            <p>Ela vale para um único acesso. Ao entrar, o sistema pedirá que você
               defina uma senha nova.</p>
            <p style="color:#64748b;font-size:13px;">Se você não pediu esta troca,
               avise o administrador do portal.</p>
        </div>
        """
        _enviar_email(email, "Khronos Sales - Senha Temporária", html)
        return True
    except Exception:
        return True


def resetar_senha_como_admin(email):
    """
    Versao da recuperacao para a tela de gestao de usuarios: aqui o
    administrador precisa de retorno de verdade, entao devolve (ok, msg).
    """
    email = str(email).strip().lower()
    admin = conectar_admin()
    try:
        res = admin.table("usuarios").select("id, nome, auth_user_id, empresa_id") \
            .eq("email", email).eq("empresa_id", st.session_state.get("empresa_id")) \
            .limit(1).execute()
        if not res.data:
            return False, "Usuário não encontrado nesta empresa."
        if not res.data[0].get("auth_user_id"):
            return False, "Usuário ainda não migrado para o Auth."
        resetar_senha_por_email(email)
        return True, "Senha temporária enviada por e-mail."
    except Exception as e:
        return False, f"Erro ao resetar senha: {e}"


def criar_usuario_auth(email, senha_inicial, nome=""):
    """Usada pela tela de gestao ao cadastrar gente nova. Retorna (auth_id, erro)."""
    try:
        resp = conectar_admin().auth.admin.create_user({
            "email": str(email).strip().lower(),
            "password": senha_inicial,
            "email_confirm": True,
            "user_metadata": {"nome": nome}
        })
        return resp.user.id, None
    except Exception as e:
        if "already" in str(e).lower():
            return None, "Já existe um usuário com este e-mail."
        return None, f"Erro ao criar usuário no Auth: {e}"


def remover_usuario_auth(auth_user_id):
    try:
        conectar_admin().auth.admin.delete_user(auth_user_id)
        return True
    except Exception:
        return False
