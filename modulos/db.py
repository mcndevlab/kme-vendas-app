import streamlit as st
import pandas as pd
from supabase import create_client, Client
import datetime

@st.cache_resource
def conectar_banco() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

@st.cache_data(ttl=300)
def carregar_produtos():
    try:
        # Removido o .order("id") para evitar erros se a coluna não existir
        res = conectar_banco().table("Base_Produtos").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_valores_sensores():
    try:
        res = conectar_banco().table("Valor_Sensor").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_valores_ponto_mo():
    try:
        res = conectar_banco().table("Valor_Ponto").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_regras_validacao():
    try:
        res = conectar_banco().table("Regras_Validacao").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
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
        res = conectar_banco().table("Configuracoes").select("*").execute()
        if res.data:
            df_config = pd.DataFrame(res.data)
            for _, linha in df_config.iterrows():
                param = str(linha.get('Parametro', '')).strip()
                valor = str(linha.get('Valor', '')).replace("%", "").replace("R$", "").strip()
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
        res = conectar_banco().table("Usuarios").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e: 
        st.error(f"⚠️ Erro de conexão com o Supabase: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_todos_leads():
    try:
        res = conectar_banco().table("Cadastro_Clientes").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df.columns = df.columns.astype(str).str.strip()
            if 'Email_Vendedor' in df.columns: df['Email_Vendedor'] = df['Email_Vendedor'].astype(str).str.strip().str.lower()
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_todas_propostas():
    try:
        res = conectar_banco().table("Propostas").select("*").execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df.columns = df.columns.astype(str).str.strip()
            if 'Email_Vendedor' in df.columns: df['Email_Vendedor'] = df['Email_Vendedor'].astype(str).str.strip().str.lower()
            return df
        return pd.DataFrame()
    except Exception as e: 
        return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_meus_leads(email):
    df = carregar_todos_leads()
    return df[df['Email_Vendedor'] == str(email).strip().lower()] if not df.empty and 'Email_Vendedor' in df.columns else pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_minhas_propostas(email):
    df = carregar_todas_propostas()
    return df[df['Email_Vendedor'] == str(email).strip().lower()] if not df.empty and 'Email_Vendedor' in df.columns else pd.DataFrame()

def atualizar_senha_banco(email_usuario, nova_senha):
    try:
        conectar_banco().table("Usuarios").update({"Senha": nova_senha}).eq("Email", email_usuario).execute()
        return True
    except: return False


# --- TRADUTOR DE "LINHA DO EXCEL" PARA "ID DO BANCO" ---
def obter_id_por_index(tabela, row_index_planilha):
    pandas_index = row_index_planilha - 2
    df = carregar_todos_leads() if tabela == "Cadastro_Clientes" else carregar_todas_propostas()
    if pandas_index in df.index and 'id' in df.columns:
        return int(df.loc[pandas_index, 'id'])
    return None


def salvar_lead(ld, vendedor, email):
    try:
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        dados = {
            "Data_Cadastro": agora,
            "Nome_Razao": ld.get("nome", ""),
            "CPF_CNPJ": ld.get("cpf_cnpj", ""),
            "Data_Nascimento": ld.get("data_nascimento", ""),
            "Endereco": ld.get("endereco", ""),
            "Numero": ld.get("numero", ""),
            "Cidade": ld.get("cidade", ""),
            "Estado": ld.get("estado", ""),
            "Telefone": ld.get("telefone", ""),
            "Contato": ld.get("contato", ""),
            "Email_Cliente": ld.get("email_cliente", ""),
            "Coordenadas_GPS": ld.get("gps", ""),
            "Nome_Usuario": vendedor,
            "Email_Vendedor": email,
            "Data_Atualizacao": ""
        }
        conectar_banco().table("Cadastro_Clientes").insert(dados).execute()
        
        df = carregar_todos_leads()
        return len(df) + 1 
    except Exception as err:
        st.error(f"❌ Erro ao registrar Lead: {err}")
        return None

def atualizar_lead(row_index, ld):
    try:
        db_id = obter_id_por_index("Cadastro_Clientes", row_index)
        if not db_id: return False
        
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        dados = {
            "Nome_Razao": ld.get("nome", ""),
            "CPF_CNPJ": ld.get("cpf_cnpj", ""),
            "Data_Nascimento": ld.get("data_nascimento", ""),
            "Endereco": ld.get("endereco", ""),
            "Numero": ld.get("numero", ""),
            "Cidade": ld.get("cidade", ""),
            "Estado": ld.get("estado", ""),
            "Telefone": ld.get("telefone", ""),
            "Contato": ld.get("contato", ""),
            "Email_Cliente": ld.get("email_cliente", ""),
            "Coordenadas_GPS": ld.get("gps", ""),
            "Data_Atualizacao": agora
        }
        conectar_banco().table("Cadastro_Clientes").update(dados).eq("id", db_id).execute()
        return True
    except: return False

def salvar_proposta(nome_cliente, nome_proposta, vendedor, email, total_mrr, total_setup, forma_pag, parcelas, val_parcela, itens, desc_p, desc_a, desc_i, temperatura, status_prop):
    try:
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        resumo_itens = "; ".join([f"{item['quantidade']}x {item['nome']} [Cód: {item.get('codigo', '-')}] (R$ {item.get('preco_calculado', item.get('preco_venda', 0)):,.2f})" for item in itens])
        dados = {
            "Data_Proposta": agora,
            "Nome_Cliente": nome_cliente,
            "Nome_Usuario": vendedor,
            "Email_Vendedor": email,
            "Total_MRR": f"R$ {total_mrr:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."),
            "Total_Setup": f"R$ {total_setup:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."),
            "Forma_Pagamento": forma_pag,
            "Parcelas": f"{parcelas}x",
            "Valor_Parcela": val_parcela,
            "Itens_Orcamento": resumo_itens,
            "Desc_Prod": f"{desc_p:.1f}%",
            "Desc_Alarme": f"{desc_a:.1f}%",
            "Desc_Imagem": f"{desc_i:.1f}%",
            "Status_Proposta": status_prop,
            "Data_Proposta_Renovada": "",
            "Motivo_Perda": "",
            "Nome_Proposta": nome_proposta,
            "Temperatura": temperatura,
            "Data_Temperatura_Renovada": agora
        }
        conectar_banco().table("Propostas").insert(dados).execute()
        return True
    except: return False

def atualizar_proposta_modificada(row_index, nome_proposta, total_mrr, total_setup, forma_pag, parcelas, val_parcela, itens, desc_p, desc_a, desc_i, temperatura, status_prop):
    try:
        db_id = obter_id_por_index("Propostas", row_index)
        if not db_id: return False

        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        resumo_itens = "; ".join([f"{item['quantidade']}x {item['nome']} [Cód: {item.get('codigo', '-')}] (R$ {item.get('preco_calculado', item.get('preco_venda', 0)):,.2f})" for item in itens])
        dados = {
            "Total_MRR": f"R$ {total_mrr:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."),
            "Total_Setup": f"R$ {total_setup:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."),
            "Forma_Pagamento": forma_pag,
            "Parcelas": f"{parcelas}x",
            "Valor_Parcela": val_parcela,
            "Itens_Orcamento": resumo_itens,
            "Desc_Prod": f"{desc_p:.1f}%",
            "Desc_Alarme": f"{desc_a:.1f}%",
            "Desc_Imagem": f"{desc_i:.1f}%",
            "Status_Proposta": status_prop,
            "Data_Proposta_Renovada": agora,
            "Nome_Proposta": nome_proposta,
            "Temperatura": temperatura,
            "Data_Temperatura_Renovada": agora
        }
        conectar_banco().table("Propostas").update(dados).eq("id", db_id).execute()
        return True
    except: return False

def efetivar_renovacao(row_index_planilha, novo_mrr, novo_setup, nova_temp):
    try:
        db_id = obter_id_por_index("Propostas", row_index_planilha)
        if not db_id: return False

        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        dados = {
            "Total_MRR": novo_mrr,
            "Total_Setup": novo_setup,
            "Status_Proposta": "Em Negociação",
            "Data_Proposta_Renovada": agora,
            "Temperatura": nova_temp,
            "Data_Temperatura_Renovada": agora
        }
        conectar_banco().table("Propostas").update(dados).eq("id", db_id).execute()
        return True
    except: return False

def efetivar_atualizacao_temperatura(row_index_planilha, nova_temp):
    try:
        db_id = obter_id_por_index("Propostas", row_index_planilha)
        if not db_id: return False

        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        conectar_banco().table("Propostas").update({"Temperatura": nova_temp, "Data_Temperatura_Renovada": agora}).eq("id", db_id).execute()
        return True
    except: return False

def efetivar_perda(row_index_planilha, motivo):
    try:
        db_id = obter_id_por_index("Propostas", row_index_planilha)
        if not db_id: return False

        conectar_banco().table("Propostas").update({"Status_Proposta": "Perdida", "Motivo_Perda": motivo}).eq("id", db_id).execute()
        return True
    except: return False

def efetivar_aprovacao(row_index_planilha):
    try:
        db_id = obter_id_por_index("Propostas", row_index_planilha)
        if not db_id: return False

        conectar_banco().table("Propostas").update({"Status_Proposta": "Aprovada", "Motivo_Perda": ""}).eq("id", db_id).execute()
        return True
    except: return False
