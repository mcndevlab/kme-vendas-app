import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

@st.cache_resource
def conectar_banco():
    escopos = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        credenciais = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=escopos)
    else:
        credenciais = Credentials.from_service_account_file("credenciais.json", scopes=escopos)
    return gspread.authorize(credenciais).open("BD_Aplicativo_Vendas")

@st.cache_data(ttl=300)
def carregar_produtos():
    dados = conectar_banco().worksheet("Base_Produtos").get_all_values()
    return pd.DataFrame(dados[1:], columns=dados[0]) if len(dados) > 1 else pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_valores_sensores():
    try:
        dados = conectar_banco().worksheet("Valor_Sensor").get_all_values()
        return pd.DataFrame(dados[1:], columns=dados[0]) if len(dados) > 1 else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_valores_ponto_mo():
    try:
        dados = conectar_banco().worksheet("Valor_Ponto").get_all_values()
        return pd.DataFrame(dados[1:], columns=dados[0]) if len(dados) > 1 else pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_regras_validacao():
    try:
        dados = conectar_banco().worksheet("Regras_Validacao").get_all_values()
        return pd.DataFrame(dados[1:], columns=dados[0]) if len(dados) > 1 else pd.DataFrame()
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
        dados = conectar_banco().worksheet("Configuracoes").get_all_values()
        if len(dados) > 1:
            df_config = pd.DataFrame(dados[1:], columns=dados[0])
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
    try: return pd.DataFrame(conectar_banco().worksheet("Usuarios").get_all_records())
    except Exception as e: 
        st.error(f"⚠️ Erro de conexão com o Google Sheets: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_todos_leads():
    try:
        df = pd.DataFrame(conectar_banco().worksheet("Cadastro_Clientes").get_all_records())
        if not df.empty:
            df.columns = df.columns.astype(str).str.strip()
            if 'Email_Vendedor' in df.columns: df['Email_Vendedor'] = df['Email_Vendedor'].astype(str).str.strip().str.lower()
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_todas_propostas():
    try:
        dados = conectar_banco().worksheet("Propostas").get_all_values()
        if len(dados) > 1:
            cabecalho = dados[0]
            while len(cabecalho) < 19: cabecalho.append(f"Coluna_{len(cabecalho)+1}")
            cabecalho[17], cabecalho[18] = "Temperatura", "Data_Temperatura_Renovada"
            df = pd.DataFrame(dados[1:], columns=cabecalho)
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
        aba = conectar_banco().worksheet("Usuarios")
        cabecalho = aba.row_values(1)
        if "Email" not in cabecalho or "Senha" not in cabecalho: return False
        col_email, col_senha = cabecalho.index("Email") + 1, cabecalho.index("Senha") + 1
        for i, email_planilha in enumerate(aba.col_values(col_email)):
            if email_planilha.strip().lower() == email_usuario.strip().lower():
                aba.update_cell(i + 1, col_senha, nova_senha)
                return True
        return False
    except: return False

def salvar_lead(ld, vendedor, email):
    try:
        aba = conectar_banco().worksheet("Cadastro_Clientes")
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        aba.append_row([agora, ld.get("nome", ""), ld.get("cpf_cnpj", ""), ld.get("endereco", ""), ld.get("numero", ""), ld.get("cidade", ""), ld.get("estado", ""), ld.get("telefone", ""), ld.get("contato", ""), ld.get("email_cliente", ""), ld.get("gps", ""), vendedor, email, ""])
        return len(aba.col_values(1))
    except Exception as err:
        st.error(f"❌ Erro ao registrar Lead: {err}")
        return None

def atualizar_lead(row_index, ld):
    try:
        aba = conectar_banco().worksheet("Cadastro_Clientes")
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        valores = [[ld.get("nome", ""), ld.get("cpf_cnpj", ""), ld.get("endereco", ""), ld.get("numero", ""), ld.get("cidade", ""), ld.get("estado", ""), ld.get("telefone", ""), ld.get("contato", ""), ld.get("email_cliente", ""), ld.get("gps", "")]]
        aba.update(f"B{row_index}:K{row_index}", valores)
        aba.update_cell(row_index, 14, agora) 
        return True
    except: return False

def salvar_proposta(nome_cliente, nome_proposta, vendedor, email, total_mrr, total_setup, forma_pag, parcelas, val_parcela, itens, desc_p, desc_a, desc_i, temperatura, status_prop):
    try:
        aba = conectar_banco().worksheet("Propostas")
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        resumo_itens = "; ".join([f"{item['quantidade']}x {item['nome']} [Cód: {item.get('codigo', '-')}] (R$ {item.get('preco_calculado', item.get('preco_venda', 0)):,.2f})" for item in itens])
        nova_linha = [agora, nome_cliente, vendedor, email, f"R$ {total_mrr:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."), f"R$ {total_setup:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."), forma_pag, f"{parcelas}x", val_parcela, resumo_itens, f"{desc_p:.1f}%", f"{desc_a:.1f}%", f"{desc_i:.1f}%", status_prop, "", "", nome_proposta, temperatura, agora]
        aba.append_row(nova_linha)
        return True
    except: return False

def atualizar_proposta_modificada(row_index, nome_proposta, total_mrr, total_setup, forma_pag, parcelas, val_parcela, itens, desc_p, desc_a, desc_i, temperatura, status_prop):
    try:
        aba = conectar_banco().worksheet("Propostas")
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        resumo_itens = "; ".join([f"{item['quantidade']}x {item['nome']} [Cód: {item.get('codigo', '-')}] (R$ {item.get('preco_calculado', item.get('preco_venda', 0)):,.2f})" for item in itens])
        valores = [[f"R$ {total_mrr:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."), f"R$ {total_setup:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."), forma_pag, f"{parcelas}x", val_parcela, resumo_itens, f"{desc_p:.1f}%", f"{desc_a:.1f}%", f"{desc_i:.1f}%", status_prop, agora, "", nome_proposta, temperatura, agora]]
        aba.update(f"E{row_index}:S{row_index}", valores)
        return True
    except: return False

def efetivar_renovacao(row_index_planilha, novo_mrr, novo_setup, nova_temp):
    try:
        aba = conectar_banco().worksheet("Propostas")
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        aba.update(f"E{row_index_planilha}:F{row_index_planilha}", [[novo_mrr, novo_setup]])
        aba.update(f"N{row_index_planilha}:O{row_index_planilha}", [["Em Negociação", agora]])
        aba.update(f"R{row_index_planilha}:S{row_index_planilha}", [[nova_temp, agora]])
        return True
    except: return False

def efetivar_atualizacao_temperatura(row_index_planilha, nova_temp):
    try:
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        conectar_banco().worksheet("Propostas").update(f"R{row_index_planilha}:S{row_index_planilha}", [[nova_temp, agora]])
        return True
    except: return False

def efetivar_perda(row_index_planilha, motivo):
    try:
        conectar_banco().worksheet("Propostas").update(f"N{row_index_planilha}:P{row_index_planilha}", [["Perdida", "", motivo]])
        return True
    except: return False

def efetivar_aprovacao(row_index_planilha):
    try:
        conectar_banco().worksheet("Propostas").update(f"N{row_index_planilha}:P{row_index_planilha}", [["Aprovada", "", ""]])
        return True
    except: return False
