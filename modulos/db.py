import streamlit as st
import pandas as pd
from supabase import create_client, Client
import datetime

# --- RELÓGIO OFICIAL DO BRASIL ---
def obter_data_hora_brasil():
    fuso_br = datetime.timezone(datetime.timedelta(hours=-3))
    return datetime.datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M:%S")

@st.cache_resource
def conectar_banco() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

@st.cache_data(ttl=300)
def carregar_produtos():
    try:
        res = conectar_banco().table("base_produtos").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df.columns = df.columns.astype(str).str.strip()
            for col in df.columns:
                df[col] = df[col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_valores_sensores():
    try:
        res = conectar_banco().table("valor_sensor").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_valores_ponto_mo():
    try:
        res = conectar_banco().table("valor_ponto").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_regras_validacao():
    try:
        res = conectar_banco().table("regras_validacao").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df.columns = df.columns.astype(str).str.strip()
            for col in df.columns:
                df[col] = df[col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_configuracoes():
    config_dict = {
        "Taxa_Juros_Mensal": 0.022, "Max_Parcelas_Sem_Juros": 3, "Max_Parcelas_Boleto": 18, "Max_Parcelas_Cartao": 24, 
        "Desc_Max_Produtos": 15.0, "Desc_Max_Alarme": 15.0, "Desc_Max_Imagem": 30.0,
        "Venc_Proposta": 10.0, "Venc_Proposta_Varejo": 10.0, "Venc_Proposta_Cond": 10.0, "Venc_Proposta_GC": 10.0,
        "Temp_Proposta": 5.0, "Temp_Proposta_Varejo": 5.0, "Temp_Proposta_Cond": 5.0, "Temp_Proposta_GC": 5.0
    }
    try:
        res = conectar_banco().table("configuracoes").select("*").execute()
        if res.data:
            df_config = pd.DataFrame(res.data)
            for _, linha in df_config.iterrows():
                param = str(linha.get('parametro', '')).strip()
                valor = str(linha.get('valor', '')).replace("%", "").replace("R$", "").strip()
                if valor != "":
                    if "." in valor and "," in valor: valor = valor.replace(".", "").replace(",", ".")
                    elif "," in valor: valor = valor.replace(",", ".")
                    try: config_dict[param] = float(valor)
                    except: pass
    except: pass
    return config_dict

@st.cache_data(ttl=300)
def carregar_usuarios():
    try: 
        res = conectar_banco().table("usuarios").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e: 
        st.error(f"⚠️ Erro de conexão com o Supabase: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_todos_leads():
    try:
        res = conectar_banco().table("cadastro_clientes").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df.columns = df.columns.astype(str).str.strip()
            if 'email_vendedor' in df.columns: df['email_vendedor'] = df['email_vendedor'].astype(str).str.strip().str.lower()
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_todas_propostas():
    try:
        res = conectar_banco().table("propostas").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df.columns = df.columns.astype(str).str.strip()
            if 'email_vendedor' in df.columns: df['email_vendedor'] = df['email_vendedor'].astype(str).str.strip().str.lower()
            return df
        return pd.DataFrame()
    except Exception as e: 
        return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_meus_leads(email):
    df = carregar_todos_leads()
    return df[df['email_vendedor'] == str(email).strip().lower()] if not df.empty and 'email_vendedor' in df.columns else pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_minhas_propostas(email):
    df = carregar_todas_propostas()
    return df[df['email_vendedor'] == str(email).strip().lower()] if not df.empty and 'email_vendedor' in df.columns else pd.DataFrame()

def atualizar_senha_banco(email_usuario, nova_senha):
    try:
        conectar_banco().table("usuarios").update({"senha": nova_senha}).eq("email", email_usuario).execute()
        return True
    except: return False

def obter_id_por_index(tabela, row_index_planilha):
    pandas_index = row_index_planilha - 2
    df = carregar_todos_leads() if tabela == "cadastro_clientes" else carregar_todas_propostas()
    
    col_id = None
    if 'id' in df.columns: col_id = 'id'
    
    if not col_id:
        st.error(f"❌ **ERRO CRÍTICO:** A tabela `{tabela}` não possui a coluna 'id'.")
        return None
        
    if pandas_index in df.index:
        return int(df.loc[pandas_index, col_id])
        
    st.error(f"❌ Não foi possível encontrar a linha no banco de dados.")
    return None

def salvar_lead(ld, vendedor, email):
    try:
        agora = obter_data_hora_brasil()
        dados = {
            "data_cadastro": agora,
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
        df = carregar_todos_leads()
        return len(df) + 1 
    except Exception as err:
        st.error(f"❌ Erro ao registrar Lead no banco: {err}")
        return None

def atualizar_lead(row_index, ld):
    try:
        db_id = obter_id_por_index("cadastro_clientes", row_index)
        if not db_id: return False
        
        agora = obter_data_hora_brasil()
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
            "data_atualizacao": agora
        }
        conectar_banco().table("cadastro_clientes").update(dados).eq("id", db_id).execute()
        return True
    except Exception as err:
        st.error(f"❌ Erro ao atualizar Lead no banco: {err}")
        return False

def salvar_proposta(nome_cliente, nome_proposta, vendedor, email, total_mrr, total_setup, forma_pag, parcelas, val_parcela, itens, desc_p, desc_a, desc_i, temperatura, status_prop):
    try:
        agora = obter_data_hora_brasil()
        resumo_itens = "; ".join([f"{item['quantidade']}x {item['nome']} [Cód: {item.get('codigo', '-')}] (R$ {item.get('preco_calculado', item.get('preco_venda', 0)):,.2f})" for item in itens])
        dados = {
            "data_proposta": agora,
            "nome_cliente": nome_cliente,
            "nome_usuario": vendedor,
            "email_vendedor": email,
            "total_mrr": f"R$ {total_mrr:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."),
            "total_setup": f"R$ {total_setup:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."),
            "forma_pagamento": forma_pag,
            "parcelas": f"{parcelas}x",
            "valor_parcela": val_parcela,
            "itens_orcamento": resumo_itens,
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

def atualizar_proposta_modificada(row_index, nome_proposta, total_mrr, total_setup, forma_pag, parcelas, val_parcela, itens, desc_p, desc_a, desc_i, temperatura, status_prop):
    try:
        db_id = obter_id_por_index("propostas", row_index)
        if not db_id: return False

        agora = obter_data_hora_brasil()
        resumo_itens = "; ".join([f"{item['quantidade']}x {item['nome']} [Cód: {item.get('codigo', '-')}] (R$ {item.get('preco_calculado', item.get('preco_venda', 0)):,.2f})" for item in itens])
        dados = {
            "total_mrr": f"R$ {total_mrr:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."),
            "total_setup": f"R$ {total_setup:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."),
            "forma_pagamento": forma_pag,
            "parcelas": f"{parcelas}x",
            "valor_parcela": val_parcela,
            "itens_orcamento": resumo_itens,
            "desc_prod": f"{desc_p:.1f}%",
            "desc_alarme": f"{desc_a:.1f}%",
            "desc_imagem": f"{desc_i:.1f}%",
            "status_proposta": status_prop,
            "data_proposta_renovada": agora,
            "nome_proposta": nome_proposta,
            "temperatura": temperatura,
            "data_temperatura_renovada": agora
        }
        conectar_banco().table("propostas").update(dados).eq("id", db_id).execute()
        return True
    except Exception as err:
        st.error(f"❌ Erro Supabase ao atualizar proposta: {err}")
        return False

def efetivar_renovacao(row_index_planilha, novo_mrr, novo_setup, nova_temp):
    try:
        db_id = obter_id_por_index("propostas", row_index_planilha)
        if not db_id: return False

        agora = obter_data_hora_brasil()
        dados = {
            "total_mrr": novo_mrr,
            "total_setup": novo_setup,
            "status_proposta": "Em Negociação",
            "data_proposta_renovada": agora,
            "temperatura": nova_temp,
            "data_temperatura_renovada": agora
        }
        conectar_banco().table("propostas").update(dados).eq("id", db_id).execute()
        return True
    except Exception as err:
        st.error(f"❌ Erro Supabase ao renovar proposta: {err}")
        return False

def efetivar_atualizacao_temperatura(row_index_planilha, nova_temp):
    try:
        db_id = obter_id_por_index("propostas", row_index_planilha)
        if not db_id: return False

        agora = obter_data_hora_brasil()
        conectar_banco().table("propostas").update({"temperatura": nova_temp, "data_temperatura_renovada": agora}).eq("id", db_id).execute()
        return True
    except Exception as err:
        st.error(f"❌ Erro Supabase ao atualizar temperatura: {err}")
        return False

def efetivar_perda(row_index_planilha, motivo):
    try:
        db_id = obter_id_por_index("propostas", row_index_planilha)
        if not db_id: return False

        conectar_banco().table("propostas").update({"status_proposta": "Perdida", "motivo_perda": motivo}).eq("id", db_id).execute()
        return True
    except Exception as err:
        st.error(f"❌ Erro Supabase ao efetivar perda: {err}")
        return False

def efetivar_aprovacao(row_index_planilha):
    try:
        db_id = obter_id_por_index("propostas", row_index_planilha)
        if not db_id: return False

        conectar_banco().table("propostas").update({"status_proposta": "Aprovada", "motivo_perda": ""}).eq("id", db_id).execute()
        return True
    except Exception as err:
        st.error(f"❌ Erro Supabase ao aprovar proposta: {err}")
        return False

def registrar_atividade(email_usuario):
    try:
        fuso_br = datetime.timezone(datetime.timedelta(hours=-3))
        agora_dt = datetime.datetime.now(fuso_br)
        
        # Formatamos a hora atual
        agora_str = agora_dt.strftime("%d/%m/%Y %H:%M:%S")
        
        # Removemos a trava de horário para gravar a qualquer momento
        conectar_banco().table("usuarios").update({"ultimo_acesso": agora_str}).eq("email", email_usuario).execute()
        return True
    except Exception as e:
        return False

@st.cache_data(ttl=60)
def carregar_tabela_configuracoes():
    try:
        res = conectar_banco().table("configuracoes").select("*").execute()
        if res.data: return pd.DataFrame(res.data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"🚨 Erro ao buscar tabela no Supabase: {e}")
        return pd.DataFrame()

def atualizar_valor_configuracao(parametro, novo_valor):
    try:
        conectar_banco().table("configuracoes").update({"valor": str(novo_valor)}).eq("parametro", parametro).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar {parametro}: {e}")
        return False

# --- NOVAS FUNÇÕES DE GESTÃO DE USUÁRIOS ---
def adicionar_usuario_banco(dados):
    try:
        conectar_banco().table("usuarios").insert(dados).execute()
        return True, "Usuário adicionado com sucesso!"
    except Exception as e:
        return False, f"Erro Supabase: {e}"

def atualizar_usuario_banco(id_usuario, email_original, dados):
    try:
        if id_usuario and str(id_usuario).lower() != 'nan':
            conectar_banco().table("usuarios").update(dados).eq("id", int(id_usuario)).execute()
        else:
            conectar_banco().table("usuarios").update(dados).eq("email", email_original).execute()
        return True, "Usuário atualizado com sucesso!"
    except Exception as e:
        return False, f"Erro Supabase: {e}"
