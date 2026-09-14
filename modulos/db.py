import streamlit as st
import pandas as pd
import datetime

from modulos.auth import cliente_sessao, conectar_admin, criar_usuario_auth

# ============================================================
# KHRONOS SALES - modulos/db.py  (versao multiempresa)
#
# O que mudou em relacao a versao anterior:
#  1. Toda leitura e escrita filtra por empresa_id.
#  2. O cache do Streamlit agora tem empresa_id na chave. Antes,
#     carregar_todos_leads() nao recebia argumento nenhum, e o cache
#     e por processo (nao por sessao): a empresa B recebia o
#     DataFrame ja carregado pela empresa A.
#  3. Paginacao no select. O PostgREST corta em 1000 linhas por padrao,
#     e valor_sensor tem ~20.400 linhas, ou seja, ja vinha truncada.
#  4. Ordenacao explicita por id. O esquema row.name + 2 do dashboard
#     depende da ordem das linhas, e o PostgREST nao garante ordem
#     sem ORDER BY.
#  5. Os updates filtram por id E empresa_id, entao um indice errado
#     nunca consegue gravar em outra empresa.
#
# As assinaturas publicas continuam identicas: o dashboard.py nao
# precisa de nenhuma alteracao.
#
# FRENTE 2 (Auth + RLS Fase B):
#  6. conectar_banco() deixou de ser um cliente global em cache_resource
#     e passou a ser o cliente da sessao, com o JWT do usuario. A RLS do
#     banco agora filtra por empresa sozinha, independente do codigo.
#  7. Escrita na tabela usuarios passou para o cliente service_role
#     (conectar_admin), que ignora RLS. O filtro por empresa_id continua
#     explicito nessas chamadas.
#  8. Senha saiu do banco. Quem guarda e valida e o Supabase Auth.
# ============================================================


# --- RELÓGIO OFICIAL DO BRASIL ---
def obter_data_hora_brasil():
    fuso_br = datetime.timezone(datetime.timedelta(hours=-3))
    return datetime.datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M:%S")


def conectar_banco():
    """Cliente da sessao atual, autenticado como o usuario logado."""
    return cliente_sessao()


# ============================================================
# CONTEXTO DA EMPRESA (TENANT)
# ============================================================
def empresa_atual():
    """Retorna o empresa_id da sessao, ou None se ainda nao logado."""
    eid = st.session_state.get("empresa_id")
    return str(eid) if eid else None


def _exigir_empresa():
    """Usado por tudo que so pode rodar com usuario logado."""
    eid = empresa_atual()
    if not eid:
        st.error("⚠️ Sessão sem empresa vinculada. Faça login novamente.")
        st.stop()
    return eid


def _buscar_tudo(tabela, empresa_id, order_col="id", page_size=1000):
    """Select paginado e ordenado, sempre restrito a uma empresa."""
    sb = conectar_banco()
    linhas, inicio = [], 0
    while True:
        q = sb.table(tabela).select("*").eq("empresa_id", empresa_id)
        if order_col:
            q = q.order(order_col)
        lote = q.range(inicio, inicio + page_size - 1).execute().data or []
        linhas.extend(lote)
        if len(lote) < page_size:
            break
        inicio += page_size
    return linhas


def _limpar_texto(df):
    df.columns = df.columns.astype(str).str.strip()
    for col in df.columns:
        df[col] = df[col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    return df


# ============================================================
# CATALOGOS
# ============================================================
@st.cache_data(ttl=300)
def _carregar_produtos(empresa_id):
    try:
        dados = _buscar_tudo("base_produtos", empresa_id)
        return _limpar_texto(pd.DataFrame(dados)) if dados else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def carregar_produtos():
    return _carregar_produtos(_exigir_empresa())


@st.cache_data(ttl=300)
def _carregar_valores_sensores(empresa_id):
    try:
        dados = _buscar_tudo("valor_sensor", empresa_id)
        return pd.DataFrame(dados) if dados else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def carregar_valores_sensores():
    return _carregar_valores_sensores(_exigir_empresa())


@st.cache_data(ttl=300)
def _carregar_valores_ponto_mo(empresa_id):
    try:
        dados = _buscar_tudo("valor_ponto", empresa_id)
        return pd.DataFrame(dados) if dados else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def carregar_valores_ponto_mo():
    return _carregar_valores_ponto_mo(_exigir_empresa())


@st.cache_data(ttl=300)
def _carregar_regras_validacao(empresa_id):
    try:
        dados = _buscar_tudo("regras_validacao", empresa_id, order_col="id_regra")
        return _limpar_texto(pd.DataFrame(dados)) if dados else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def carregar_regras_validacao():
    return _carregar_regras_validacao(_exigir_empresa())


@st.cache_data(ttl=300)
def _carregar_configuracoes(empresa_id):
    config_dict = {
        "Taxa_Juros_Mensal": 0.022, "Max_Parcelas_Sem_Juros": 3, "Max_Parcelas_Boleto": 18, "Max_Parcelas_Cartao": 24,
        "Desc_Max_Produtos": 15.0, "Desc_Max_Alarme": 15.0, "Desc_Max_Imagem": 30.0,
        "Venc_Proposta": 10.0, "Venc_Proposta_Varejo": 10.0, "Venc_Proposta_Cond": 10.0, "Venc_Proposta_GC": 10.0,
        "Temp_Proposta": 5.0, "Temp_Proposta_Varejo": 5.0, "Temp_Proposta_Cond": 5.0, "Temp_Proposta_GC": 5.0
    }
    try:
        dados = _buscar_tudo("configuracoes", empresa_id)
        for linha in dados:
            param = str(linha.get('parametro', '')).strip()
            valor = str(linha.get('valor', '')).replace("%", "").replace("R$", "").strip()
            if valor != "":
                if "." in valor and "," in valor:
                    valor = valor.replace(".", "").replace(",", ".")
                elif "," in valor:
                    valor = valor.replace(",", ".")
                try:
                    config_dict[param] = float(valor)
                except Exception:
                    pass
    except Exception:
        pass
    return config_dict

def carregar_configuracoes():
    return _carregar_configuracoes(_exigir_empresa())


@st.cache_data(ttl=60)
def _carregar_tabela_configuracoes(empresa_id):
    try:
        dados = _buscar_tudo("configuracoes", empresa_id)
        return pd.DataFrame(dados) if dados else pd.DataFrame()
    except Exception as e:
        st.error(f"🚨 Erro ao buscar tabela no Supabase: {e}")
        return pd.DataFrame()

def carregar_tabela_configuracoes():
    return _carregar_tabela_configuracoes(_exigir_empresa())


def atualizar_valor_configuracao(parametro, novo_valor):
    try:
        eid = _exigir_empresa()
        conectar_banco().table("configuracoes") \
            .update({"valor": str(novo_valor)}) \
            .eq("parametro", parametro).eq("empresa_id", eid).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar {parametro}: {e}")
        return False


# ============================================================
# USUARIOS
# ============================================================
def carregar_perfil_logado(email):
    """
    Chamada logo APOS o login no Supabase Auth, para descobrir empresa,
    perfil e unidade. Usa o cliente da sessao: o proprio JWT ja garante
    que so a linha dele (e a dos colegas de empresa) esta visivel.
    Nao existe mais busca cross-tenant por senha.
    """
    try:
        alvo = str(email).strip().lower()
        res = conectar_banco().table("usuarios").select("*").eq("email", alvo).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        st.error(f"⚠️ Erro ao carregar perfil: {e}")
        return None


@st.cache_data(ttl=300)
def _carregar_usuarios(empresa_id):
    try:
        dados = _buscar_tudo("usuarios", empresa_id)
        return pd.DataFrame(dados) if dados else pd.DataFrame()
    except Exception as e:
        st.error(f"⚠️ Erro de conexão com o Supabase: {e}")
        return pd.DataFrame()

def carregar_usuarios():
    return _carregar_usuarios(_exigir_empresa())


def adicionar_usuario_banco(dados):
    """
    Cria o usuario no Supabase Auth e na tabela usuarios, na mesma operacao.
    'dados' pode trazer 'senha': ela vai apenas para o Auth, nunca para a tabela.
    """
    try:
        eid = _exigir_empresa()
        dados = dict(dados)
        email = str(dados.get("email", "")).strip().lower()
        senha_inicial = str(dados.pop("senha", "")).strip()

        if not email or "@" not in email:
            return False, "Informe um e-mail válido."
        if len(senha_inicial) < 8:
            return False, "A senha inicial precisa ter ao menos 8 caracteres."

        auth_id, erro = criar_usuario_auth(email, senha_inicial, dados.get("nome", ""))
        if erro:
            return False, erro

        dados.update({
            "email": email,
            "empresa_id": eid,
            "auth_user_id": auth_id,
            "trocar_senha": "Sim"
        })
        conectar_admin().table("usuarios").insert(dados).execute()
        st.cache_data.clear()
        return True, "Usuário adicionado. Ele definirá a senha no primeiro acesso."
    except Exception as e:
        return False, f"Erro Supabase: {e}"


def atualizar_usuario_banco(id_usuario, email_original, dados):
    try:
        eid = _exigir_empresa()
        dados = dict(dados)
        # nada disso pode ser alterado pela tela de gestao
        for campo in ("empresa_id", "auth_user_id", "senha", "email"):
            dados.pop(campo, None)

        tab = conectar_admin().table("usuarios")
        if id_usuario and str(id_usuario).lower() != 'nan':
            tab.update(dados).eq("id", int(id_usuario)).eq("empresa_id", eid).execute()
        else:
            tab.update(dados).eq("email", email_original).eq("empresa_id", eid).execute()
        st.cache_data.clear()
        return True, "Usuário atualizado com sucesso!"
    except Exception as e:
        return False, f"Erro Supabase: {e}"


def marcar_senha_trocada(email_usuario):
    """Chamada depois que o proprio usuario define a senha nova no Auth."""
    try:
        eid = empresa_atual()
        q = conectar_admin().table("usuarios").update({"trocar_senha": "Nao"}) \
            .eq("email", str(email_usuario).strip().lower())
        if eid:
            q = q.eq("empresa_id", eid)
        q.execute()
        return True
    except Exception:
        return False


def registrar_atividade(email_usuario):
    try:
        fuso_br = datetime.timezone(datetime.timedelta(hours=-3))
        agora_str = datetime.datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M:%S")
        eid = empresa_atual()
        q = conectar_admin().table("usuarios").update({"ultimo_acesso": agora_str}) \
            .eq("email", str(email_usuario).strip().lower())
        if eid:
            q = q.eq("empresa_id", eid)
        q.execute()
        return True
    except Exception:
        return False


# ============================================================
# LEADS
# ============================================================
@st.cache_data(ttl=300)
def _carregar_todos_leads(empresa_id):
    try:
        dados = _buscar_tudo("cadastro_clientes", empresa_id)
        if not dados:
            return pd.DataFrame()
        df = pd.DataFrame(dados)
        df.columns = df.columns.astype(str).str.strip()
        if 'email_vendedor' in df.columns:
            df['email_vendedor'] = df['email_vendedor'].astype(str).str.strip().str.lower()
        return df
    except Exception:
        return pd.DataFrame()

def carregar_todos_leads():
    return _carregar_todos_leads(_exigir_empresa())


@st.cache_data(ttl=300)
def _carregar_meus_leads(empresa_id, email):
    df = _carregar_todos_leads(empresa_id)
    if df.empty or 'email_vendedor' not in df.columns:
        return pd.DataFrame()
    return df[df['email_vendedor'] == str(email).strip().lower()]

def carregar_meus_leads(email):
    return _carregar_meus_leads(_exigir_empresa(), email)


def salvar_lead(ld, vendedor, email):
    try:
        eid = _exigir_empresa()
        dados = {
            "empresa_id": eid,
            "data_cadastro": obter_data_hora_brasil(),
            "nome_razao": ld.get("nome", ""),
            "cpf_cnpj": ld.get("cpf_cnpj", ""),
            "data_nascimento": ld.get("data_nascimento", ""),
            "endereco": ld.get("endereco", ""),
            "numero": ld.get("numero", ""),
            "cidade": ld.get("cidade", ""),
            "estado": ld.get("estado", ""),
            "telefone": ld.get("telefone", ""),
            "contato": ld.get("contato", ""),
            "email_cliente": ld.get("email_cliente", ""),
            "coordenadas_gps": ld.get("gps", ""),
            "nome_usuario": vendedor,
            "email_vendedor": email,
            "data_atualizacao": ""
        }
        conectar_banco().table("cadastro_clientes").insert(dados).execute()
        st.cache_data.clear()
        df = carregar_todos_leads()
        return len(df) + 1
    except Exception as err:
        st.error(f"❌ Erro ao registrar Lead no banco: {err}")
        return None


def atualizar_lead(row_index, ld):
    try:
        eid = _exigir_empresa()
        db_id = obter_id_por_index("cadastro_clientes", row_index)
        if not db_id:
            return False
        dados = {
            "nome_razao": ld.get("nome", ""),
            "cpf_cnpj": ld.get("cpf_cnpj", ""),
            "data_nascimento": ld.get("data_nascimento", ""),
            "endereco": ld.get("endereco", ""),
            "numero": ld.get("numero", ""),
            "cidade": ld.get("cidade", ""),
            "estado": ld.get("estado", ""),
            "telefone": ld.get("telefone", ""),
            "contato": ld.get("contato", ""),
            "email_cliente": ld.get("email_cliente", ""),
            "coordenadas_gps": ld.get("gps", ""),
            "data_atualizacao": obter_data_hora_brasil()
        }
        conectar_banco().table("cadastro_clientes").update(dados) \
            .eq("id", db_id).eq("empresa_id", eid).execute()
        return True
    except Exception as err:
        st.error(f"❌ Erro ao atualizar Lead no banco: {err}")
        return False


# ============================================================
# PROPOSTAS
# ============================================================
@st.cache_data(ttl=300)
def _carregar_todas_propostas(empresa_id):
    try:
        dados = _buscar_tudo("propostas", empresa_id)
        if not dados:
            return pd.DataFrame()
        df = pd.DataFrame(dados)
        df.columns = df.columns.astype(str).str.strip()
        if 'email_vendedor' in df.columns:
            df['email_vendedor'] = df['email_vendedor'].astype(str).str.strip().str.lower()
        return df
    except Exception:
        return pd.DataFrame()

def carregar_todas_propostas():
    return _carregar_todas_propostas(_exigir_empresa())


@st.cache_data(ttl=300)
def _carregar_minhas_propostas(empresa_id, email):
    df = _carregar_todas_propostas(empresa_id)
    if df.empty or 'email_vendedor' not in df.columns:
        return pd.DataFrame()
    return df[df['email_vendedor'] == str(email).strip().lower()]

def carregar_minhas_propostas(email):
    return _carregar_minhas_propostas(_exigir_empresa(), email)


def _resumo_itens(itens):
    return "; ".join([
        f"{item['quantidade']}x {item['nome']} [Cód: {item.get('codigo', '-')}] "
        f"(R$ {item.get('preco_calculado', item.get('preco_venda', 0)):,.2f})"
        for item in itens
    ])


def _moeda(v):
    return f"R$ {v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def salvar_proposta(nome_cliente, nome_proposta, vendedor, email, total_mrr, total_setup,
                    forma_pag, parcelas, val_parcela, itens, desc_p, desc_a, desc_i,
                    temperatura, status_prop):
    try:
        eid = _exigir_empresa()
        agora = obter_data_hora_brasil()
        dados = {
            "empresa_id": eid,
            "data_proposta": agora,
            "nome_cliente": nome_cliente,
            "nome_usuario": vendedor,
            "email_vendedor": email,
            "total_mrr": _moeda(total_mrr),
            "total_setup": _moeda(total_setup),
            "forma_pagamento": forma_pag,
            "parcelas": f"{parcelas}x",
            "valor_parcela": val_parcela,
            "itens_orcamento": _resumo_itens(itens),
            "desc_prod": f"{desc_p:.1f}%",
            "desc_alarme": f"{desc_a:.1f}%",
            "desc_imagem": f"{desc_i:.1f}%",
            "status_proposta": status_prop,
            "data_proposta_renovada": "",
            "motivo_perda": "",
            "nome_proposta": nome_proposta,
            "temperatura": temperatura,
            "data_temperatura_renovada": agora
        }
        conectar_banco().table("propostas").insert(dados).execute()
        return True
    except Exception as err:
        st.error(f"❌ Erro Supabase ao salvar proposta: {err}")
        return False


def atualizar_proposta_modificada(row_index, nome_proposta, total_mrr, total_setup, forma_pag,
                                  parcelas, val_parcela, itens, desc_p, desc_a, desc_i,
                                  temperatura, status_prop):
    try:
        eid = _exigir_empresa()
        db_id = obter_id_por_index("propostas", row_index)
        if not db_id:
            return False
        agora = obter_data_hora_brasil()
        dados = {
            "total_mrr": _moeda(total_mrr),
            "total_setup": _moeda(total_setup),
            "forma_pagamento": forma_pag,
            "parcelas": f"{parcelas}x",
            "valor_parcela": val_parcela,
            "itens_orcamento": _resumo_itens(itens),
            "desc_prod": f"{desc_p:.1f}%",
            "desc_alarme": f"{desc_a:.1f}%",
            "desc_imagem": f"{desc_i:.1f}%",
            "status_proposta": status_prop,
            "data_proposta_renovada": agora,
            "nome_proposta": nome_proposta,
            "temperatura": temperatura,
            "data_temperatura_renovada": agora
        }
        conectar_banco().table("propostas").update(dados) \
            .eq("id", db_id).eq("empresa_id", eid).execute()
        return True
    except Exception as err:
        st.error(f"❌ Erro Supabase ao atualizar proposta: {err}")
        return False


def efetivar_renovacao(row_index_planilha, novo_mrr, novo_setup, nova_temp):
    try:
        eid = _exigir_empresa()
        db_id = obter_id_por_index("propostas", row_index_planilha)
        if not db_id:
            return False
        agora = obter_data_hora_brasil()
        dados = {
            "total_mrr": novo_mrr,
            "total_setup": novo_setup,
            "status_proposta": "Em Negociação",
            "data_proposta_renovada": agora,
            "temperatura": nova_temp,
            "data_temperatura_renovada": agora
        }
        conectar_banco().table("propostas").update(dados) \
            .eq("id", db_id).eq("empresa_id", eid).execute()
        return True
    except Exception as err:
        st.error(f"❌ Erro Supabase ao renovar proposta: {err}")
        return False


def efetivar_atualizacao_temperatura(row_index_planilha, nova_temp):
    try:
        eid = _exigir_empresa()
        db_id = obter_id_por_index("propostas", row_index_planilha)
        if not db_id:
            return False
        conectar_banco().table("propostas").update({
            "temperatura": nova_temp,
            "data_temperatura_renovada": obter_data_hora_brasil()
        }).eq("id", db_id).eq("empresa_id", eid).execute()
        return True
    except Exception as err:
        st.error(f"❌ Erro Supabase ao atualizar temperatura: {err}")
        return False


def efetivar_perda(row_index_planilha, motivo):
    try:
        eid = _exigir_empresa()
        db_id = obter_id_por_index("propostas", row_index_planilha)
        if not db_id:
            return False
        conectar_banco().table("propostas") \
            .update({"status_proposta": "Perdida", "motivo_perda": motivo}) \
            .eq("id", db_id).eq("empresa_id", eid).execute()
        return True
    except Exception as err:
        st.error(f"❌ Erro Supabase ao efetivar perda: {err}")
        return False


def efetivar_aprovacao(row_index_planilha):
    try:
        eid = _exigir_empresa()
        db_id = obter_id_por_index("propostas", row_index_planilha)
        if not db_id:
            return False
        conectar_banco().table("propostas") \
            .update({"status_proposta": "Aprovada", "motivo_perda": ""}) \
            .eq("id", db_id).eq("empresa_id", eid).execute()
        return True
    except Exception as err:
        st.error(f"❌ Erro Supabase ao aprovar proposta: {err}")
        return False


# ============================================================
# PONTE COM O ESQUEMA DE INDICE DO DASHBOARD
# O dashboard ainda usa row.name + 2 (heranca da planilha).
# Mantido por compatibilidade, mas agora resolvendo dentro da
# empresa e com a lista ordenada por id.
# TODO: passar o 'id' real do registro e aposentar esta funcao.
# ============================================================
def obter_id_por_index(tabela, row_index_planilha):
    pandas_index = row_index_planilha - 2
    df = carregar_todos_leads() if tabela == "cadastro_clientes" else carregar_todas_propostas()

    if 'id' not in df.columns:
        st.error(f"❌ **ERRO CRÍTICO:** A tabela `{tabela}` não possui a coluna 'id'.")
        return None

    if pandas_index in df.index:
        return int(df.loc[pandas_index, 'id'])

    st.error("❌ Não foi possível encontrar a linha no banco de dados.")
    return None
