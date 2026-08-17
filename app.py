import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import re
import os
from streamlit_geolocation import streamlit_geolocation
from geopy.geocoders import Nominatim

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA E CSS
# ==========================================
st.set_page_config(page_title="Khronos Sales", page_icon="🛡️", layout="wide")

SENHA_PADRAO_SISTEMA = "Khronos@2026"

st.markdown("""
    <style>
    div[data-testid="stVerticalBlock"] { gap: 0.3rem !important; }
    div[data-testid="stMarkdownContainer"] p { margin-bottom: 0.5rem !important; padding-top: 2px !important; }
    
    div.stButton > button {
        min-height: 2.2rem !important;
        height: auto !important;
        padding: 4px 15px !important;
        text-align: left !important;
        display: flex !important;
        justify-content: flex-start !important;
        align-items: center !important;
        width: 100% !important;
    }
    
    div.stButton > button * {
        text-align: left !important;
        justify-content: flex-start !important;
    }
    
    div.stButton > button[kind="primary"] {
        justify-content: center !important;
        text-align: center !important;
    }
    div.stButton > button[kind="primary"] * {
        text-align: center !important;
        justify-content: center !important;
    }
    
    .card-mobile {
        background-color: #f8fafc;
        border-left: 4px solid #0066cc;
        padding: 12px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

def exibir_topo_com_logo(titulo="Khronos Sales", subtitulo="Acesso ao Portal Comercial de Vendas"):
    c_logo, c_txt = st.columns([1, 8])
    with c_logo:
        if os.path.exists("logo.jpg"): st.image("logo.jpg", width=65)
        else: st.write("🛡️")
    with c_txt:
        st.markdown(f"<h1 style='margin:0; padding:0; line-height: 1.1;'>{titulo}</h1>", unsafe_allow_html=True)
        st.caption(subtitulo)

# ==========================================
# 2. CONEXÃO E LEITURA DO GOOGLE SHEETS
# ==========================================
@st.cache_resource
def conectar_banco():
    escopos = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    if "gcp_service_account" in st.secrets:
        credenciais = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=escopos)
    else:
        credenciais = Credentials.from_service_account_file("credenciais.json", scopes=escopos)
    cliente = gspread.authorize(credenciais)
    return cliente.open("BD_Aplicativo_Vendas")

@st.cache_data(ttl=300)
def carregar_produtos():
    aba = conectar_banco().worksheet("Base_Produtos")
    dados = aba.get_all_values()
    if len(dados) > 1: return pd.DataFrame(dados[1:], columns=dados[0])
    return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_valores_sensores():
    try:
        dados = conectar_banco().worksheet("Valor_Sensor").get_all_values()
        if len(dados) > 1: return pd.DataFrame(dados[1:], columns=dados[0])
        return pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_valores_ponto_mo():
    try:
        dados = conectar_banco().worksheet("Valor_Ponto").get_all_values()
        if len(dados) > 1: return pd.DataFrame(dados[1:], columns=dados[0])
        return pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_regras_validacao():
    try:
        dados = conectar_banco().worksheet("Regras_Validacao").get_all_values()
        if len(dados) > 1: return pd.DataFrame(dados[1:], columns=dados[0])
        return pd.DataFrame()
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_configuracoes():
    try:
        dados = conectar_banco().worksheet("Configuracoes").get_all_values()
        if len(dados) > 1:
            df_config = pd.DataFrame(dados[1:], columns=dados[0])
            config_dict = {}
            for _, linha in df_config.iterrows():
                param = str(linha.get('Parametro', '')).strip()
                valor = str(linha.get('Valor', '')).replace("%", "").replace("R$", "").strip()
                if valor == "": val_num = 0.0
                else:
                    if "." in valor and "," in valor: valor = valor.replace(".", "").replace(",", ".")
                    elif "," in valor: valor = valor.replace(",", ".")
                    try: val_num = float(valor)
                    except: val_num = 0.0
                config_dict[param] = val_num
            return config_dict
    except: pass
    return {"Taxa_Juros_Mensal": 0.022, "Max_Parcelas_Sem_Juros": 3, "Max_Parcelas_Boleto": 18, "Max_Parcelas_Cartao": 24, "Desc_Max_Produtos": 15.0, "Desc_Max_Alarme": 15.0, "Desc_Max_Imagem": 30.0}

@st.cache_data(ttl=300)
def carregar_usuarios():
    try: return pd.DataFrame(conectar_banco().worksheet("Usuarios").get_all_records())
    except Exception as e: 
        st.error(f"⚠️ Erro de conexão com o Google Sheets: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_todos_leads():
    try:
        df = pd.DataFrame(conectar_banco().worksheet("Funil_Vendas").get_all_records())
        if not df.empty:
            df.columns = df.columns.astype(str).str.strip()
            if 'Email_Vendedor' in df.columns:
                df['Email_Vendedor'] = df['Email_Vendedor'].astype(str).str.strip().str.lower()
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_todas_propostas():
    try:
        df = pd.DataFrame(conectar_banco().worksheet("Propostas").get_all_records())
        if not df.empty:
            df.columns = df.columns.astype(str).str.strip()
            if 'Email_Vendedor' in df.columns:
                df['Email_Vendedor'] = df['Email_Vendedor'].astype(str).str.strip().str.lower()
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_meus_leads(email):
    df = carregar_todos_leads()
    if not df.empty and 'Email_Vendedor' in df.columns:
        return df[df['Email_Vendedor'] == str(email).strip().lower()]
    return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_minhas_propostas(email):
    df = carregar_todas_propostas()
    if not df.empty and 'Email_Vendedor' in df.columns:
        return df[df['Email_Vendedor'] == str(email).strip().lower()]
    return pd.DataFrame()

# --- FUNÇÕES DE PADRONIZAÇÃO E LIMPEZA ---
def converter_para_numero(valor):
    if isinstance(valor, (int, float)): return float(valor)
    texto = str(valor).replace("R$", "").replace("%", "").strip()
    if texto == "": return 0.0
    if "," in texto:
        if "." in texto: texto = texto.replace(".", "")
        texto = texto.replace(",", ".")
    try: return float(texto)
    except: return 0.0

def padronizar_nome(texto):
    if not texto: return ""
    excecoes = ['de', 'da', 'do', 'das', 'dos', 'e']
    palavras = str(texto).strip().split()
    resultado = []
    for p in palavras:
        p_lower = p.lower()
        if p_lower in excecoes: resultado.append(p_lower)
        else: resultado.append(p_lower.capitalize())
    return " ".join(resultado)

def padronizar_telefone(tel):
    if not tel: return ""
    num = re.sub(r'\D', '', str(tel))
    if len(num) == 11: return f"({num[:2]}) {num[2]} {num[3:7]}-{num[7:]}"
    elif len(num) == 10: return f"({num[:2]}) {num[2:6]}-{num[6:]}"
    return tel 

def extrair_tabela_crm_itens(itens_str):
    dados_tabela = []
    if not itens_str or itens_str == 'nan': return dados_tabela
    for elem in str(itens_str).split(";"):
        elem = elem.strip()
        if not elem: continue
        cod, qtd, nome, v_u = "-", 1, elem, 0.0
        if "[Cód:" in elem:
            try:
                parte_qtd_nome, rest = elem.split("[Cód:", 1)
                cod, rest2 = rest.split("]", 1)[0].strip(), rest.split("]", 1)[1]
                if "x " in parte_qtd_nome:
                    qtd = int(parte_qtd_nome.split("x ", 1)[0].strip())
                    nome = parte_qtd_nome.split("x ", 1)[1].strip()
                else: nome = parte_qtd_nome.strip()
                if "(R$" in rest2: v_u = converter_para_numero(rest2.split("(R$", 1)[1].replace(")", "").strip())
            except: pass
        elif "x " in elem:
            try:
                qtd = int(elem.split("x ", 1)[0].strip())
                nome = elem.split("x ", 1)[1].strip()
            except: pass
        subtotal = v_u * qtd
        dados_tabela.append({"Código KME": cod, "Produto / Serviço": nome, "Qtd": qtd, "Valor Unit.": f"R$ {v_u:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") if v_u > 0 else "-", "Subtotal": f"R$ {subtotal:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") if subtotal > 0 else "-"})
    return dados_tabela

def validar_inconsistencias_carrinho(carrinho, df_regras):
    avisos = []
    if df_regras.empty or not carrinho: return avisos
    codigos_no_carrinho = [str(item.get('codigo', '')).strip().lstrip('0') for item in carrinho]
    for _, regra in df_regras.iterrows():
        gatilho = str(regra.get('Item_Gatilho', '')).strip().lstrip('0')
        exigidos_str = str(regra.get('Itens_Exigidos', '')).strip()
        msg = str(regra.get('Mensagem_Aviso', 'Inconsistência detectada.'))
        tipo_regra = str(regra.get('Tipo_Regra', 'Exigencia')).strip().lower()
        if gatilho in codigos_no_carrinho:
            itens_relacionados = [c.strip().lstrip('0') for c in exigidos_str.split(';') if c.strip()]
            if 'exig' in tipo_regra:
                if not any(codigo in codigos_no_carrinho for codigo in itens_relacionados): avisos.append(msg)
            elif 'incompat' in tipo_regra or 'proib' in tipo_regra:
                if any(codigo in codigos_no_carrinho for codigo in itens_relacionados): avisos.append(msg)
    return avisos

# --- FUNÇÕES DE GRAVAÇÃO E ATUALIZAÇÃO ---
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
        aba = conectar_banco().worksheet("Funil_Vendas")
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        aba.append_row([agora, ld.get("nome", ""), ld.get("cpf_cnpj", ""), ld.get("endereco", ""), ld.get("numero", ""), ld.get("cidade", ""), ld.get("estado", ""), ld.get("telefone", ""), ld.get("contato", ""), ld.get("email_cliente", ""), ld.get("gps", ""), vendedor, email, ""])
        return len(aba.col_values(1))
    except Exception as err:
        st.error(f"❌ Erro ao registrar Lead: {err}")
        return None

def atualizar_lead(row_index, ld):
    try:
        aba = conectar_banco().worksheet("Funil_Vendas")
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        valores = [[ld.get("nome", ""), ld.get("cpf_cnpj", ""), ld.get("endereco", ""), ld.get("numero", ""), ld.get("cidade", ""), ld.get("estado", ""), ld.get("telefone", ""), ld.get("contato", ""), ld.get("email_cliente", ""), ld.get("gps", "")]]
        aba.update(f"B{row_index}:K{row_index}", valores)
        aba.update_cell(row_index, 14, agora) 
        return True
    except: return False

def salvar_proposta(nome_cliente, nome_proposta, vendedor, email, total_mrr, total_setup, forma_pag, parcelas, val_parcela, itens, desc_p, desc_a, desc_i):
    try:
        aba = conectar_banco().worksheet("Propostas")
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        resumo_itens = "; ".join([f"{item['quantidade']}x {item['nome']} [Cód: {item.get('codigo', '-')}] (R$ {item.get('preco_calculado', item.get('preco_venda', 0)):,.2f})" for item in itens])
        nova_linha = [agora, nome_cliente, vendedor, email, f"R$ {total_mrr:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."), f"R$ {total_setup:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."), forma_pag, f"{parcelas}x", val_parcela, resumo_itens, f"{desc_p:.1f}%", f"{desc_a:.1f}%", f"{desc_i:.1f}%", "Em Negociação", "", "", nome_proposta]
        aba.append_row(nova_linha)
        return True
    except: return False

def atualizar_proposta_modificada(row_index, nome_proposta, total_mrr, total_setup, forma_pag, parcelas, val_parcela, itens, desc_p, desc_a, desc_i):
    try:
        aba = conectar_banco().worksheet("Propostas")
        agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        resumo_itens = "; ".join([f"{item['quantidade']}x {item['nome']} [Cód: {item.get('codigo', '-')}] (R$ {item.get('preco_calculado', item.get('preco_venda', 0)):,.2f})" for item in itens])
        valores = [[f"R$ {total_mrr:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."), f"R$ {total_setup:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."), forma_pag, f"{parcelas}x", val_parcela, resumo_itens, f"{desc_p:.1f}%", f"{desc_a:.1f}%", f"{desc_i:.1f}%", "Em Negociação", agora]]
        aba.update(f"E{row_index}:O{row_index}", valores)
        aba.update_cell(row_index, 17, nome_proposta) 
        return True
    except: return False

def calcular_novos_valores_proposta(row_data, df_produtos, df_valor_sensor):
    itens_str = str(row_data.get('Itens_Orcamento', ''))
    desc_p, desc_a, desc_i = converter_para_numero(row_data.get('Desc_Prod', '0')) / 100, converter_para_numero(row_data.get('Desc_Alarme', '0')) / 100, converter_para_numero(row_data.get('Desc_Imagem', '0')) / 100
    bruto_prod, bruto_alarme, bruto_imagem, mao_obra = 0.0, 0.0, 0.0, 0.0
    itens_parsed, qtd_abertura, qtd_ivp = [], 0, 0
    
    for item in itens_str.split(";"):
        if "x " in item:
            try:
                qtd = int(item.strip().split("x ", 1)[0])
                nome_item = item.strip().split("x ", 1)[1].split("[Cód:")[0].strip() if "[Cód:" in item else item.strip().split("x ", 1)[1].strip()
            except: qtd, nome_item = 0, ""
            prod_info = df_produtos[df_produtos['Nome_Item'].astype(str).str.strip() == nome_item]
            if not prod_info.empty:
                prod = prod_info.iloc[0]
                ts = str(prod.get('Tipo_Sensor', '')).strip().upper()
                if ts == 'ABERTURA': qtd_abertura += qtd
                elif ts == 'IVP': qtd_ivp += qtd
                itens_parsed.append({'qtd': qtd, 'prod': prod})
                
    for it in itens_parsed:
        qtd, prod = it['qtd'], it['prod']
        cat, grupo, cod_item = str(prod.get('Categoria_Receita', '')).strip().lower(), str(prod.get('Grupo_Itens', '')).strip().lower(), str(prod.get('Codigo_KME', '')).strip().lstrip('0')
        v_u = converter_para_numero(prod.get('Preco_Venda', 0)) if converter_para_numero(prod.get('Preco_Venda', 0)) > 0 else converter_para_numero(prod.get('Preco_LOC_36', 0))
        
        if cod_item in ['254000000042', '254000000377', '25400000042', '25400000377']:
            if not df_valor_sensor.empty:
                match = df_valor_sensor[(df_valor_sensor['Codigo_Servico'].astype(str).str.strip().str.lstrip('0') == cod_item) & (pd.to_numeric(df_valor_sensor['Sensor_Abertura'], errors='coerce') == qtd_abertura) & (pd.to_numeric(df_valor_sensor['Sensor_IVP'], errors='coerce') == qtd_ivp)]
                if not match.empty: v_u = converter_para_numero(match.iloc[0]['Preco'])
                    
        if "obra" in cat or "instala" in cat: mao_obra += (v_u * qtd)
        elif "produto" in cat or "equipamento" in cat: bruto_prod += (v_u * qtd)
        else:
            if "imagem" in grupo: bruto_imagem += (v_u * qtd)
            else: bruto_alarme += (v_u * qtd)
            
    novo_total_mrr, novo_total_setup = (bruto_alarme * (1 - desc_a)) + (bruto_imagem * (1 - desc_i)), (bruto_prod * (1 - desc_p)) + mao_obra
    return f"R$ {novo_total_mrr:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."), f"R$ {novo_total_setup:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

def efetivar_renovacao(row_index_planilha, novo_mrr, novo_setup):
    try:
        aba = conectar_banco().worksheet("Propostas")
        aba.update(f"E{row_index_planilha}:F{row_index_planilha}", [[novo_mrr, novo_setup]])
        aba.update(f"N{row_index_planilha}:O{row_index_planilha}", [["Em Negociação", datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")]])
        return True
    except: return False

def efetivar_perda(row_index_planilha, motivo):
    try:
        conectar_banco().worksheet("Propostas").update(f"N{row_index_planilha}:P{row_index_planilha}", [["Perdida", "", motivo]])
        return True
    except: return False

def carregar_proposta_para_simulador(idx_planilha, dados_prop, df_produtos, df_leads):
    novo_carrinho = []
    for item in str(dados_prop.get('Itens_Orcamento', '')).split(";"):
        if "x " in item:
            try:
                qtd = int(item.strip().split("x ", 1)[0])
                nome_item = item.strip().split("x ", 1)[1].split("[Cód:")[0].strip() if "[Cód:" in item else item.strip().split("x ", 1)[1].strip()
            except: qtd, nome_item = 0, ""
            prod_info = df_produtos[df_produtos['Nome_Item'].astype(str).str.strip() == nome_item]
            if not prod_info.empty:
                prod = prod_info.iloc[0]
                novo_carrinho.append({"nome": str(prod['Nome_Item']), "codigo": str(prod.get('Codigo_KME', '')), "tipo_sensor": str(prod.get('Tipo_Sensor', '')), "categoria": str(prod.get('Categoria_Receita', '')), "grupo": str(prod.get('Grupo_Itens', '')), "quantidade": qtd, "preco_venda": converter_para_numero(prod.get('Preco_Venda', 0)), "preco_mrr": converter_para_numero(prod.get('Preco_LOC_36', 0))})
                
    st.session_state["desc_prod"] = converter_para_numero(dados_prop.get('Desc_Prod', '0'))
    st.session_state["desc_alarme"] = converter_para_numero(dados_prop.get('Desc_Alarme', '0'))
    st.session_state["desc_imagem"] = converter_para_numero(dados_prop.get('Desc_Imagem', '0'))
    st.session_state["nome_proposta_atual"] = str(dados_prop.get('Nome_Proposta', ''))
    
    nome_cliente = str(dados_prop.get('Nome_Cliente', '')).strip()
    lead_row = df_leads[df_leads['Nome_Razao'].astype(str).str.strip() == nome_cliente]
    if not lead_row.empty:
        lr = lead_row.iloc[0]
        st.session_state["lead_dados"] = {"data_cadastro": str(lr.get("Data_Cadastro", "")), "nome": str(lr.get("Nome_Razao", "")), "cpf_cnpj": str(lr.get("CPF_CNPJ", "")).replace('nan', ''), "endereco": str(lr.get("Endereco", "")).replace('nan', ''), "numero": str(lr.get("Numero", "")).replace('nan', ''), "cidade": str(lr.get("Cidade", "")).replace('nan', ''), "estado": str(lr.get("Estado", "")).replace('nan', ''), "telefone": str(lr.get("Telefone", "")).replace('nan', ''), "contato": str(lr.get("Contato", "")).replace('nan', ''), "email_cliente": str(lr.get("Email_Cliente", "")).replace('nan', ''), "gps": str(lr.get("Coordenadas_GPS", "")).replace('nan', '')}
        st.session_state["editando_lead_idx"] = lead_row.index[0] + 2 
    else:
        st.session_state["lead_dados"] = {"nome": nome_cliente}
        st.session_state["editando_lead_idx"] = None
        
    st.session_state.update({"carrinho": novo_carrinho, "lead_salvo": True, "renovar_proposta_idx": None, "proposta_idx_editando": idx_planilha, "etapa_atual": "simulador"})

# MOTOR DE FILTROS GERENCIAIS
def aplicar_filtros_gerenciais(df_users, df_all_leads, df_all_prop, perfil, minha_unidade):
    if perfil == "Lider": df_users = df_users[df_users['Unidade'].astype(str).str.strip().str.lower() == minha_unidade]
    elif perfil == "Gerente_Varejo": df_users = df_users[df_users['Vertical'].astype(str).str.strip().str.lower().str.contains('varejo')]
    elif perfil == "Gerente_Condominio": df_users = df_users[df_users['Vertical'].astype(str).str.strip().str.lower().str.contains('condominio')]
    
    st.write("---")
    c1, c2, c3, c4, c5 = st.columns(5)
    
    filtro_vert = "Todas"
    if perfil == "Diretoria":
        opcoes_vert = ["Todas"] + sorted(df_users['Vertical'].dropna().unique().tolist())
        filtro_vert = c1.selectbox("Vertical", opcoes_vert)
        if filtro_vert != "Todas": df_users = df_users[df_users['Vertical'] == filtro_vert]
            
    filtro_unid = "Todas"
    if perfil in ["Diretoria", "Gerente_Varejo", "Gerente_Condominio"]:
        opcoes_unid = ["Todas"] + sorted(df_users['Unidade'].dropna().unique().tolist())
        col_t = c2 if perfil == "Diretoria" else c1
        filtro_unid = col_t.selectbox("Unidade", opcoes_unid)
        if filtro_unid != "Todas": df_users = df_users[df_users['Unidade'] == filtro_unid]
            
    opcoes_vend = ["Todos"] + sorted(df_users['Nome'].dropna().unique().tolist())
    col_t_v = c3 if perfil == "Diretoria" else (c2 if perfil in ["Gerente_Varejo", "Gerente_Condominio"] else c1)
    filtro_vend = col_t_v.selectbox("Vendedor", opcoes_vend)
    if filtro_vend != "Todos": df_users = df_users[df_users['Nome'] == filtro_vend]
    
    valid_em = df_users['Email_C'].tolist()
    df_eq_l = df_all_leads[df_all_leads['Email_Vendedor'].isin(valid_em)] if not df_all_leads.empty else pd.DataFrame()
    df_eq_p = df_all_prop[df_all_prop['Email_Vendedor'].isin(valid_em)] if not df_all_prop.empty else pd.DataFrame()
    
    if not df_eq_l.empty:
        df_eq_l['Data_Fmt'] = pd.to_datetime(df_eq_l['Data_Cadastro'].astype(str).str.split(" ").str[0], format='%d/%m/%Y', errors='coerce')
        df_eq_l['Mes_Ano'] = df_eq_l['Data_Fmt'].dt.strftime('%m/%Y').fillna('Sem Data')
        df_eq_l['Dia_Str'] = df_eq_l['Data_Fmt'].dt.strftime('%d/%m/%Y').fillna('Sem Data')
    if not df_eq_p.empty:
        df_eq_p['Data_Fmt'] = pd.to_datetime(df_eq_p['Data_Proposta'].astype(str).str.split(" ").str[0], format='%d/%m/%Y', errors='coerce')
        df_eq_p['Mes_Ano'] = df_eq_p['Data_Fmt'].dt.strftime('%m/%Y').fillna('Sem Data')
        df_eq_p['Dia_Str'] = df_eq_p['Data_Fmt'].dt.strftime('%d/%m/%Y').fillna('Sem Data')
        
    meses_d = []
    if not df_eq_l.empty: meses_d.extend(df_eq_l['Mes_Ano'].dropna().unique().tolist())
    if not df_eq_p.empty: meses_d.extend(df_eq_p['Mes_Ano'].dropna().unique().tolist())
    meses_d = sorted(list(set(meses_d)))
    if 'Sem Data' in meses_d: meses_d.remove('Sem Data')
    meses_d = ["Todos"] + meses_d
    
    col_t_m = c4 if perfil == "Diretoria" else (c3 if perfil in ["Gerente_Varejo", "Gerente_Condominio"] else c2)
    filtro_mes = col_t_m.selectbox("Mês", meses_d)
    if filtro_mes != "Todos":
        if not df_eq_l.empty: df_eq_l = df_eq_l[df_eq_l['Mes_Ano'] == filtro_mes]
        if not df_eq_p.empty: df_eq_p = df_eq_p[df_eq_p['Mes_Ano'] == filtro_mes]
        
    dias_d = []
    if not df_eq_l.empty: dias_d.extend(df_eq_l['Dia_Str'].dropna().unique().tolist())
    if not df_eq_p.empty: dias_d.extend(df_eq_p['Dia_Str'].dropna().unique().tolist())
    dias_d = sorted(list(set(dias_d)))
    if 'Sem Data' in dias_d: dias_d.remove('Sem Data')
    dias_d = ["Todos"] + dias_d
    
    col_t_d = c5 if perfil == "Diretoria" else (c4 if perfil in ["Gerente_Varejo", "Gerente_Condominio"] else c3)
    filtro_dia = col_t_d.selectbox("Dia", dias_d)
    if filtro_dia != "Todos":
        if not df_eq_l.empty: df_eq_l = df_eq_l[df_eq_l['Dia_Str'] == filtro_dia]
        if not df_eq_p.empty: df_eq_p = df_eq_p[df_eq_p['Dia_Str'] == filtro_dia]
        
    mapa_v = dict(zip(df_users['Email_C'], df_users['Nome']))
    return df_eq_l, df_eq_p, mapa_v

# ==========================================
# 3. MEMÓRIA
# ==========================================
if "autenticado" not in st.session_state:
    st.session_state.update({"autenticado": False, "nome_usuario": "", "email_usuario": "", "perfil_usuario": "Consultor", "unidade_usuario": "", "vertical_usuario": "", "carrinho": [], "desc_prod": 0.0, "desc_alarme": 0.0, "desc_imagem": 0.0, "etapa_atual": "lead", "lead_dados": {}, "lead_salvo": False, "msg_sucesso": "", "renovar_proposta_idx": None, "renovar_proposta_dados": {}, "proposta_idx_editando": None, "editando_lead_idx": None, "nome_proposta_atual": "", "ultimo_gps_capturado": "", "item_aberto": None, "unidade_mo_selecionada": None, "modo_visao_leads": "📱 Cartões (Celular)", "modo_visao_propostas": "📱 Cartões (Celular)", "precisa_trocar_senha": False})

# ==========================================
# 4. TELA DE LOGIN, TROCA DE SENHA E MAESTRO
# ==========================================
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

def tela_principal():
    df_produtos = carregar_produtos()
    df_valor_sensor = carregar_valores_sensores()
    df_valor_ponto = carregar_valores_ponto_mo()
    df_regras = carregar_regras_validacao()
    df_leads = carregar_meus_leads(st.session_state["email_usuario"])
    df_prop = carregar_minhas_propostas(st.session_state["email_usuario"])
    propostas_vencidas = []
    
    if not df_prop.empty:
        hoje = datetime.datetime.now()
        for idx, row in df_prop.iterrows():
            status = str(row.get('Status_Proposta', '')).strip()
            if status in ["Perdida", "Fechada"]: continue
            data_ref_str = str(row.get('Data_Proposta_Renovada', '')).strip() or str(row.get('Data_Proposta', '')).strip()
            try:
                data_ref = datetime.datetime.strptime(data_ref_str, "%d/%m/%Y %H:%M:%S") if " " in data_ref_str else datetime.datetime.strptime(data_ref_str, "%d/%m/%Y")
                dias_passados = (hoje - data_ref).days
                if dias_passados >= 10: propostas_vencidas.append({"idx_planilha": idx + 2, "dados": row, "dias": dias_passados})
            except: pass

    if len(propostas_vencidas) > 0 and not st.session_state.get("proposta_idx_editando"):
        st.error(f"🚨 **AÇÃO EXIGIDA:** Você possui {len(propostas_vencidas)} proposta(s) parada(s) há 10 dias ou mais!")
        st.warning("O sistema foi bloqueado temporariamente. Informe o andamento da negociação abaixo para liberar o uso.")
        st.write("---")
        for p in propostas_vencidas:
            with st.container():
                st.markdown(f"### 💼 Cliente: {p['dados'].get('Nome_Cliente', '')} *(Ref: {p['dados'].get('Nome_Proposta', '')})*")
                st.caption(f"Vencida há {p['dias']} dias.")
                c1, c2 = st.columns(2)
                acao = c1.selectbox("O que aconteceu com esta negociação?", ["Selecione...", "Renovar por mais 10 dias", "Perda na negociação"], key=f"acao_{p['idx_planilha']}")
                motivo = c2.selectbox("Motivo da Perda:", ["Selecione...", "Perdeu Interesse", "Valor Alto", "Fechou com Concorrente", "Tecnologia não atende", "Sem retorno do Cliente"], key=f"mot_{p['idx_planilha']}") if acao == "Perda na negociação" else ""
                
                if acao != "Selecione...":
                    if acao == "Perda na negociação":
                        if motivo == "Selecione...": st.info("⚠️ Selecione o motivo da perda para confirmar.")
                        elif st.button("Confirmar Perda", type="primary", key=f"btn_{p['idx_planilha']}"):
                            if efetivar_perda(p['idx_planilha'], motivo): st.toast(f"Proposta atualizada para Perdida."); st.cache_data.clear(); st.rerun()
                    elif acao == "Renovar por mais 10 dias":
                        mrr_n, setup_n = calcular_novos_valores_proposta(p['dados'], df_produtos, df_valor_sensor)
                        mrr_a, setup_a = p['dados'].get('Total_MRR', ''), p['dados'].get('Total_Setup', '')
                        pode_salvar = True
                        if mrr_n != mrr_a or setup_n != setup_a:
                            st.warning(f"⚠️ **ATENÇÃO:** Os preços da tabela base foram atualizados!\n\n**Total Serviços:** de {mrr_a} ➡️ **{mrr_n}**\n**Setup:** de {setup_a} ➡️ **{setup_n}**")
                            if not st.checkbox("Estou ciente e avisarei o cliente.", key=f"chk_{p['idx_planilha']}"): pode_salvar = False
                        
                        c_b1, c_b2 = st.columns([3, 7])
                        if c_b1.button("Confirmar Renovação", type="primary", disabled=not pode_salvar, key=f"btn_ren_{p['idx_planilha']}"):
                            if efetivar_renovacao(p['idx_planilha'], mrr_n, setup_n): st.toast("Renovada com sucesso!"); st.cache_data.clear(); st.rerun()
                        if c_b2.button("✏️ Modificar Proposta", key=f"btn_mod_{p['idx_planilha']}"):
                            carregar_proposta_para_simulador(p['idx_planilha'], p['dados'], df_produtos, df_leads); st.rerun()
                st.divider()
        st.stop() 

    # ==========================================
    # MENU LATERAL E FLUXO NORMAL
    # ==========================================
    with st.sidebar:
        if os.path.exists("logo.jpg"): st.image("logo.jpg", width=120)
        st.markdown("### **Khronos Sales**")
        st.write(f"👤 **{st.session_state['nome_usuario']}**")
        st.divider()
        if st.button("➕ Novo Lead", use_container_width=True): st.session_state.update({"gatilho_limpar_tudo": True, "etapa_atual": "lead"}); st.rerun()
        if st.button("📋 Meus Leads", use_container_width=True): st.session_state.update({"etapa_atual": "meus_leads", "proposta_idx_editando": None}); st.rerun()
        if st.button("💼 Minhas Propostas", use_container_width=True): st.session_state.update({"etapa_atual": "minhas_propostas", "proposta_idx_editando": None}); st.rerun()
            
        perfil_acesso = str(st.session_state.get('perfil_usuario', '')).strip()
        if perfil_acesso in ["Lider", "Gerente_Varejo", "Gerente_Condominio", "Diretoria"]:
            st.divider()
            st.caption("🔒 **Área Gerencial**")
            if st.button("📊 Funil da Equipe", use_container_width=True): st.session_state.update({"etapa_atual": "funil_equipe", "proposta_idx_editando": None}); st.rerun()
            if st.button("🗺️ Localização da Equipe", use_container_width=True): st.session_state.update({"etapa_atual": "mapa_equipe", "proposta_idx_editando": None}); st.rerun()
                
        st.divider()
        if st.session_state["lead_dados"].get("nome"):
            st.success(f"🛒 Simulador Ativo:\n{st.session_state['lead_dados']['nome']}")
            if st.button("Ir para o Simulador", use_container_width=True): st.session_state["etapa_atual"] = "simulador"; st.rerun()
        st.divider()
        if st.button("🚪 Sair", use_container_width=True): st.session_state.clear(); st.rerun()

    if st.session_state.get("gatilho_limpar_tudo", False):
        st.session_state.update({"carrinho": [], "desc_prod": 0.0, "desc_alarme": 0.0, "desc_imagem": 0.0, "lead_dados": {}, "lead_salvo": False, "renovar_proposta_idx": None, "proposta_idx_editando": None, "editando_lead_idx": None, "nome_proposta_atual": "", "ultimo_gps_capturado": "", "item_aberto": None, "unidade_mo_selecionada": None, "gatilho_limpar_tudo": False})
    if st.session_state.get("gatilho_limpar_carrinho", False):
        st.session_state.update({"carrinho": [], "desc_prod": 0.0, "desc_alarme": 0.0, "desc_imagem": 0.0, "item_aberto": None, "gatilho_limpar_carrinho": False})
    if st.session_state["msg_sucesso"] != "": st.success(st.session_state["msg_sucesso"]); st.session_state["msg_sucesso"] = ""

    # --- TELA: LOCALIZAÇÃO DA EQUIPE (MAPA) ---
    if st.session_state["etapa_atual"] == "mapa_equipe":
        st.header("🗺️ Localização da Equipe")
        df_users = carregar_usuarios()
        df_users['Email_C'] = df_users['Email'].astype(str).str.strip().str.lower()
        perfil, minha_unidade = st.session_state['perfil_usuario'], st.session_state['unidade_usuario'].lower()
        
        df_eq_l, _, _ = aplicar_filtros_gerenciais(df_users, carregar_todos_leads(), carregar_todas_propostas(), perfil, minha_unidade)
        
        st.write("---")
        df_mapa = df_eq_l.copy()
        if not df_mapa.empty and 'Coordenadas_GPS' in df_mapa.columns:
            df_mapa['lat'] = pd.to_numeric(df_mapa['Coordenadas_GPS'].astype(str).str.split(',').str[0], errors='coerce')
            df_mapa['lon'] = pd.to_numeric(df_mapa['Coordenadas_GPS'].astype(str).str.split(',').str[1], errors='coerce')
            df_mapa = df_mapa.dropna(subset=['lat', 'lon'])
            
            if not df_mapa.empty:
                st.map(df_mapa[['lat', 'lon']], zoom=10)
                st.caption(f"📍 Mostrando a localização exata de **{len(df_mapa)} lead(s)** com base nos filtros aplicados acima.")
            else: st.info("Nenhuma localização de GPS válida encontrada com os filtros selecionados.")
        else: st.info("Nenhum lead com localização registrada encontrado para esta seleção.")

    # --- TELA: FUNIL DA EQUIPE (VISÃO GERENCIAL) ---
    elif st.session_state["etapa_atual"] == "funil_equipe":
        st.header("📊 Funil da Equipe")
        df_users = carregar_usuarios()
        df_users['Email_C'] = df_users['Email'].astype(str).str.strip().str.lower()
        perfil, minha_unidade = st.session_state['perfil_usuario'], st.session_state['unidade_usuario'].lower()
        
        df_eq_leads, df_eq_prop, mapa_vendedores = aplicar_filtros_gerenciais(df_users, carregar_todos_leads(), carregar_todas_propostas(), perfil, minha_unidade)
        
        st.write("---")
        aba_leads, aba_prop = st.tabs(["📋 Leads da Equipe", "💼 Propostas da Equipe"])
        
        with aba_leads:
            if df_eq_leads.empty: st.info("Nenhum lead encontrado para esta seleção.")
            else:
                df_eq_leads = df_eq_leads.iloc[::-1]
                h1, h2, h3, h4, h5 = st.columns([2, 4, 2, 2, 2])
                with h1: st.markdown("**Vendedor**")
                with h2: st.markdown("**👤 Cliente**")
                with h3: st.markdown("**📞 Telefone**")
                with h4: st.markdown("**📅 Cadastro**")
                with h5: st.markdown("**📊 Status**")
                st.write("---")
                
                for idx, row in df_eq_leads.iterrows():
                    nome = str(row.get('Nome_Razao', 'Não Informado')).strip()
                    telefone, data_cad = str(row.get('Telefone', '-')).strip(), str(row.get('Data_Cadastro', '-')).split(" ")[0]
                    vendedor = str(mapa_vendedores.get(str(row.get('Email_Vendedor', '')), "Desconhecido"))
                    
                    status_lead = "🔵 Lead"
                    if not df_eq_prop.empty and 'Nome_Cliente' in df_eq_prop.columns:
                        prop_cliente = df_eq_prop[df_eq_prop['Nome_Cliente'].astype(str).str.strip() == nome]
                        if not prop_cliente.empty:
                            status_lead = "🔴 Perdida" if str(prop_cliente.iloc[-1].get('Status_Proposta', '')).strip() == "Perdida" else "🟢 Proposta"
                    
                    c1, c2, c3, c4, c5 = st.columns([2, 4, 2, 2, 2])
                    with c1: st.write(vendedor[:18] + ("..." if len(vendedor) > 18 else ""))
                    with c2: 
                        with st.expander(f"👤 {nome[:25]}{'...' if len(nome) > 25 else ''}"):
                            st.markdown(f"**Endereço:** {row.get('Endereco', '')}, {row.get('Numero', '')} - {row.get('Cidade', '')}<br>**Contato:** {row.get('Contato', '')} | **E-mail:** {row.get('Email_Cliente', '')}", unsafe_allow_html=True)
                    with c3: st.write(telefone)
                    with c4: st.write(data_cad)
                    with c5: st.write(status_lead)

        with aba_prop:
            if df_eq_prop.empty: st.info("Nenhuma proposta encontrada para esta seleção.")
            else:
                df_eq_prop = df_eq_prop.iloc[::-1]
                hoje = datetime.datetime.now()
                h1, h_v, h2, h_np, h3, h4, h5, h6 = st.columns([2, 2, 4, 3, 2, 2, 2, 2])
                with h1: st.markdown("**Data**")
                with h_v: st.markdown("**Vendedor**")
                with h2: st.markdown("**👤 Cliente (Ver CRM)**")
                with h_np: st.markdown("**Ref. Proposta**")
                with h3: st.markdown("**Status**")
                with h4: st.markdown("**Restante**")
                with h5: st.markdown("**Serviços**")
                with h6: st.markdown("**Setup**")
                st.write("---")
                
                for idx, row in df_eq_prop.iterrows():
                    data_p = str(row.get('Data_Proposta', '')).split(" ")[0]
                    vendedor = str(mapa_vendedores.get(str(row.get('Email_Vendedor', '')), "Desconhecido"))
                    cliente = str(row.get('Nome_Cliente', ''))
                    nome_prop = str(row.get('Nome_Proposta', 'Principal'))
                    status = str(row.get('Status_Proposta', 'Em Negociação')).strip() or "Em Negociação"
                    mrr, setup = str(row.get('Total_MRR', '')), str(row.get('Total_Setup', ''))
                    
                    data_ref_str = str(row.get('Data_Proposta_Renovada', '')).strip() or str(row.get('Data_Proposta', '')).strip()
                    tempo_faltante = "-"
                    if status == "Em Negociação" and data_ref_str:
                        try:
                            d_ref = datetime.datetime.strptime(data_ref_str, "%d/%m/%Y %H:%M:%S") if " " in data_ref_str else datetime.datetime.strptime(data_ref_str, "%d/%m/%Y")
                            faltam = 10 - (hoje - d_ref).days
                            if faltam > 0: tempo_faltante = f"{faltam} dia(s)"
                            elif faltam == 0: tempo_faltante = "Vence hoje"
                            else: tempo_faltante = "Vencida"
                        except: pass
                    
                    cor_status = "🟢" if status == "Em Negociação" else ("🔴" if status == "Perdida" else "⚫")
                    
                    c1, c_v, c2, c_np, c3, c4, c5, c6 = st.columns([2, 2, 4, 3, 2, 2, 2, 2])
                    with c1: st.write(data_p)
                    with c_v: st.write(vendedor[:15] + ("..." if len(vendedor) > 15 else ""))
                    with c2: 
                        with st.expander(f"👤 {cliente[:25]}{'...' if len(cliente) > 25 else ''}"):
                            itens_crm = extrair_tabela_crm_itens(row.get('Itens_Orcamento', ''))
                            if itens_crm: st.dataframe(itens_crm, use_container_width=True, hide_index=True)
                            else: st.info("Sem detalhes avançados.")
                    with c_np: st.write(nome_prop[:20] + ("..." if len(nome_prop) > 20 else ""))
                    with c3: st.write(f"{cor_status} {status}")
                    with c4: st.write(tempo_faltante)
                    with c5: st.write(mrr)
                    with c6: st.write(setup)

    # --- TELA: MINHAS PROPOSTAS ---
    elif st.session_state["etapa_atual"] == "minhas_propostas":
        st.header("💼 Minhas Propostas Enviadas")
        
        c_tit, c_modo = st.columns([7, 3])
        with c_modo: modo_prop = st.radio("Modo de Exibição:", ["📱 Cartões (Celular)", "🖥️ Tabela Analítica"], key="modo_visao_propostas", horizontal=True)

        if st.session_state.get("renovar_proposta_idx"):
            idx_planilha, dados_prop = st.session_state["renovar_proposta_idx"], st.session_state["renovar_proposta_dados"]
            st.info(f"🔄 **Renovando proposta de:** {dados_prop.get('Nome_Cliente')} (por mais 10 dias)")
            mrr_n, setup_n = calcular_novos_valores_proposta(dados_prop, df_produtos, df_valor_sensor)
            mrr_a, setup_a = dados_prop.get('Total_MRR', ''), dados_prop.get('Total_Setup', '')
            
            pode_renovar = True
            if mrr_n != mrr_a or setup_n != setup_a:
                st.warning(f"⚠️ **ATENÇÃO:** Os preços sofrerão reajuste de acordo com a tabela atual!\n\n**Total Serviços:** de {mrr_a} ➡️ **{mrr_n}**\n**Setup:** de {setup_a} ➡️ **{setup_n}**")
                if not st.checkbox("Estou ciente e avisarei o cliente da alteração."): pode_renovar = False
            else: st.success("✅ Os valores da proposta continuam os mesmos da tabela atual.")
            
            c_btn1, c_btn2, c_btn3 = st.columns([3, 3, 4])
            if c_btn1.button("Confirmar Renovação", disabled=not pode_renovar, type="primary"):
                if efetivar_renovacao(idx_planilha, mrr_n, setup_n): st.session_state["msg_sucesso"] = "Proposta renovada com sucesso!"; st.session_state["renovar_proposta_idx"] = None; st.cache_data.clear(); st.rerun()
            if c_btn2.button("✏️ Modificar Proposta"): carregar_proposta_para_simulador(idx_planilha, dados_prop, df_produtos, df_leads); st.rerun()
            if c_btn3.button("Cancelar Operação"): st.session_state["renovar_proposta_idx"] = None; st.rerun()
            st.divider()

        if df_prop.empty: st.info("Nenhuma proposta registrada.")
        else:
            df_prop = df_prop.iloc[::-1] 
            hoje = datetime.datetime.now()
            
            if "Tabela" in modo_prop:
                st.write("---")
                h1, h_ult, h2, h_np, h3, h4, h5, h6, h7 = st.columns([2, 2, 4, 3, 2, 2, 2, 2, 2])
                with h1: st.markdown("**Data**")
                with h_ult: st.markdown("**Últ. Prop**")
                with h2: st.markdown("**👤 Cliente (Ver CRM)**")
                with h_np: st.markdown("**Ref. Proposta**")
                with h3: st.markdown("**Status**")
                with h4: st.markdown("**Restante**")
                with h5: st.markdown("**Serviços**")
                with h6: st.markdown("**Setup**")
                with h7: st.markdown("**Ação**")
                st.write("---")
                
                for idx, row in df_prop.iterrows():
                    linha_real_planilha = row.name + 2 
                    data_p, data_ult_str = str(row.get('Data_Proposta', '')).split(" ")[0], str(row.get('Data_Proposta_Renovada', '')).split(" ")[0]
                    cliente, nome_prop = str(row.get('Nome_Cliente', '')), str(row.get('Nome_Proposta', 'Principal'))
                    status, mrr, setup = str(row.get('Status_Proposta', 'Em Negociação')).strip() or "Em Negociação", str(row.get('Total_MRR', '')), str(row.get('Total_Setup', ''))
                    data_ref_str = str(row.get('Data_Proposta_Renovada', '')).strip() or str(row.get('Data_Proposta', '')).strip()
                    
                    tempo_faltante = "-"
                    if status == "Em Negociação" and data_ref_str:
                        try:
                            d_ref = datetime.datetime.strptime(data_ref_str, "%d/%m/%Y %H:%M:%S") if " " in data_ref_str else datetime.datetime.strptime(data_ref_str, "%d/%m/%Y")
                            faltam = 10 - (hoje - d_ref).days
                            if faltam > 0: tempo_faltante = f"{faltam} dia(s)"
                            elif faltam == 0: tempo_faltante = "Vence hoje"
                            else: tempo_faltante = "Vencida"
                        except: pass
                    
                    c1, c_ult, c2, c_np, c3, c4, c5, c6, c7 = st.columns([2, 2, 4, 3, 2, 2, 2, 2, 2])
                    with c1: st.write(data_p)
                    with c_ult: st.write(data_ult_str if data_ult_str else "-")
                    with c2: 
                        with st.expander(f"👤 {cliente[:25]}{'...' if len(cliente)>25 else ''}"):
                            itens_crm = extrair_tabela_crm_itens(row.get('Itens_Orcamento', ''))
                            if itens_crm: st.dataframe(itens_crm, use_container_width=True, hide_index=True)
                    with c_np: st.write(nome_prop[:20] + ("..." if len(nome_prop)>20 else ""))
                    with c3: st.write(f"{'🟢 ' if status == 'Em Negociação' else ('🔴 ' if status == 'Perdida' else '⚫ ')}{status}")
                    with c4: st.write(tempo_faltante)
                    with c5: st.write(mrr)
                    with c6: st.write(setup)
                    with c7:
                        if status == "Em Negociação":
                            if st.button("🔄 Renovar", key=f"ren_tab_{linha_real_planilha}", use_container_width=True): st.session_state["renovar_proposta_idx"] = linha_real_planilha; st.session_state["renovar_proposta_dados"] = row.to_dict(); st.rerun()
            else:
                for idx, row in df_prop.iterrows():
                    linha_real_planilha = row.name + 2 
                    data_p, cliente, nome_prop = str(row.get('Data_Proposta', '')).split(" ")[0], str(row.get('Nome_Cliente', '')), str(row.get('Nome_Proposta', 'Principal'))
                    status, mrr, setup = str(row.get('Status_Proposta', 'Em Negociação')).strip() or "Em Negociação", str(row.get('Total_MRR', '')), str(row.get('Total_Setup', ''))
                    data_ref_str = str(row.get('Data_Proposta_Renovada', '')).strip() or str(row.get('Data_Proposta', '')).strip()
                    
                    tempo_faltante = "-"
                    if status == "Em Negociação" and data_ref_str:
                        try:
                            d_ref = datetime.datetime.strptime(data_ref_str, "%d/%m/%Y %H:%M:%S") if " " in data_ref_str else datetime.datetime.strptime(data_ref_str, "%d/%m/%Y")
                            faltam = 10 - (hoje - d_ref).days
                            if faltam > 0: tempo_faltante = f"{faltam} dia(s)"
                            elif faltam == 0: tempo_faltante = "Vence hoje"
                            else: tempo_faltante = "Vencida"
                        except: pass
                    
                    with st.expander(f"{'🟢' if status == 'Em Negociação' else ('🔴' if status == 'Perdida' else '⚫')} {cliente} — {nome_prop} ({data_p})"):
                        st.markdown(f"**Status:** {status} | **Validade:** {tempo_faltante}<br>**Serviços:** {mrr} | **Setup:** {setup}", unsafe_allow_html=True)
                        itens_crm = extrair_tabela_crm_itens(row.get('Itens_Orcamento', ''))
                        if itens_crm: st.write("---"); st.markdown("📋 **Itens do Projeto para CRM:**"); st.dataframe(itens_crm, use_container_width=True, hide_index=True)
                        st.write("")
                        if status == "Em Negociação":
                            if st.button("🔄 Renovar / Editar Proposta", key=f"ren_tab_{linha_real_planilha}", type="primary", use_container_width=True): st.session_state["renovar_proposta_idx"] = linha_real_planilha; st.session_state["renovar_proposta_dados"] = row.to_dict(); st.rerun()

    # --- TELA: MEUS LEADS ---
    elif st.session_state["etapa_atual"] == "meus_leads":
        st.header("📋 Meus Leads")
        df_leads = carregar_meus_leads(st.session_state["email_usuario"])
        
        c_busc, c_modo = st.columns([7, 3])
        with c_modo: modo_lead = st.radio("Modo de Exibição:", ["📱 Cartões (Celular)", "🖥️ Tabela Analítica"], key="modo_visao_leads", horizontal=True)

        if df_leads.empty: st.info("Nenhum lead encontrado no seu funil.")
        else:
            with c_busc: busca = st.text_input("🔍 Buscar Lead por Nome ou Telefone:")
            if busca: df_leads = df_leads[df_leads.astype(str).apply(lambda x: x.str.contains(busca, case=False)).any(axis=1)]
            df_leads = df_leads.iloc[::-1]

            if "Tabela" in modo_lead:
                st.write("---")
                h1, h2, h3, h4, h5, h6, h7 = st.columns([4, 3, 4, 2, 2, 2, 3])
                with h1: st.markdown("**👤 Nome**"); 
                with h2: st.markdown("**📞 Telefone**")
                with h3: st.markdown("**📍 Endereço**"); 
                with h4: st.markdown("**📅 Cadastro**")
                with h5: st.markdown("**📊 Status**"); 
                with h6: st.markdown("**📅 Últ. Prop**")
                st.write("---")
                    
                for idx, row in df_leads.iterrows():
                    linha_real_planilha = row.name + 2
                    nome, telefone, data_cad = str(row.get('Nome_Razao', 'Não Informado')).strip(), str(row.get('Telefone', '-')).strip(), str(row.get('Data_Cadastro', '-')).split(" ")[0]
                    end_curto = f"{str(row.get('Endereco', '')).strip()}, {str(row.get('Numero', '')).strip()} - {str(row.get('Cidade', '')).strip()}".replace("nan", "").strip(" ,-") or "-"
                    
                    status_lead, data_ult_prop = "🔵 Lead", "-"
                    if not df_prop.empty and 'Nome_Cliente' in df_prop.columns:
                        prop_cliente = df_prop[df_prop['Nome_Cliente'].astype(str).str.strip() == nome]
                        if not prop_cliente.empty:
                            status_lead, data_ult_prop = "🔴 Perdida" if str(prop_cliente.iloc[-1].get('Status_Proposta', '')).strip() == "Perdida" else "🟢 Proposta", str(prop_cliente.iloc[-1].get('Data_Proposta', '-')).split(" ")[0]

                    c1, c2, c3, c4, c5, c6, c7 = st.columns([4, 3, 4, 2, 2, 2, 3])
                    with c1: 
                        with st.expander(f"👤 {nome[:25]}{'...' if len(nome)>25 else ''}"):
                            st.markdown(f"<span style='font-size: 0.85rem; color: #475569;'><b>CPF/CNPJ:</b> {str(row.get('CPF_CNPJ', '')).replace('nan', '')}<br><b>E-mail:</b> {str(row.get('Email_Cliente', '')).replace('nan', '')}<br><b>Contato:</b> {str(row.get('Contato', '')).replace('nan', '')}</span>", unsafe_allow_html=True)
                    with c2: st.markdown(f"<div style='margin-top: 0.4rem;'>{telefone}</div>", unsafe_allow_html=True)
                    with c3: st.markdown(f"<div style='margin-top: 0.4rem;'>{end_curto[:30]}{'...' if len(end_curto)>30 else ''}</div>", unsafe_allow_html=True)
                    with c4: st.markdown(f"<div style='margin-top: 0.4rem;'>{data_cad}</div>", unsafe_allow_html=True)
                    with c5: st.markdown(f"<div style='margin-top: 0.4rem;'>{status_lead}</div>", unsafe_allow_html=True)
                    with c6: st.markdown(f"<div style='margin-top: 0.4rem;'>{data_ult_prop}</div>", unsafe_allow_html=True)
                    with c7:
                        btn1, btn2 = st.columns([7, 3])
                        with btn1:
                            if st.button("Proposta", key=f"btn_lead_{idx}", use_container_width=True): st.session_state.update({"lead_dados": {"data_cadastro": data_cad, "nome": nome, "cpf_cnpj": str(row.get('CPF_CNPJ', '')).replace('nan', ''), "endereco": str(row.get('Endereco', '')).replace('nan', ''), "numero": str(row.get('Numero', '')).replace('nan', ''), "cidade": str(row.get('Cidade', '')).replace('nan', ''), "estado": str(row.get("Estado", "")).replace('nan', ''), "telefone": telefone, "email_cliente": str(row.get('Email_Cliente', '')).replace('nan', ''), "contato": str(row.get('Contato', '')).replace('nan', ''), "gps": str(row.get("Coordenadas_GPS", "")).replace('nan', '')}, "lead_salvo": True, "gatilho_limpar_carrinho": True, "etapa_atual": "simulador", "editando_lead_idx": linha_real_planilha}); st.rerun()
                        with btn2:
                            if st.button("✏️", help="Editar", key=f"btn_edit_lead_{idx}", use_container_width=True): st.session_state.update({"lead_dados": {"data_cadastro": data_cad, "nome": nome, "cpf_cnpj": str(row.get('CPF_CNPJ', '')).replace('nan', ''), "endereco": str(row.get('Endereco', '')).replace('nan', ''), "numero": str(row.get('Numero', '')).replace('nan', ''), "cidade": str(row.get('Cidade', '')).replace('nan', ''), "estado": str(row.get("Estado", "")).replace('nan', ''), "telefone": telefone, "email_cliente": str(row.get('Email_Cliente', '')).replace('nan', ''), "contato": str(row.get('Contato', '')).replace('nan', ''), "gps": str(row.get("Coordenadas_GPS", "")).replace('nan', '')}, "lead_salvo": True, "etapa_atual": "lead", "editando_lead_idx": linha_real_planilha}); st.rerun()

            else:
                for idx, row in df_leads.iterrows():
                    linha_real_planilha = row.name + 2
                    nome, telefone, data_cad = str(row.get('Nome_Razao', 'Não Informado')).strip(), str(row.get('Telefone', '-')).strip(), str(row.get('Data_Cadastro', '-')).split(" ")[0]
                    end_curto = f"{str(row.get('Endereco', '')).strip()}, {str(row.get('Numero', '')).strip()} - {str(row.get('Cidade', '')).strip()}".replace("nan", "").strip(" ,-") or "-"
                    
                    status_lead = "🔵 Lead"
                    if not df_prop.empty and 'Nome_Cliente' in df_prop.columns:
                        prop_cliente = df_prop[df_prop['Nome_Cliente'].astype(str).str.strip() == nome]
                        if not prop_cliente.empty: status_lead = "🔴 Perdida" if str(prop_cliente.iloc[-1].get('Status_Proposta', '')).strip() == "Perdida" else "🟢 Proposta"

                    with st.expander(f"👤 {nome} ({status_lead})"):
                        st.markdown(f"📞 <b>Telefone:</b> {telefone}<br>📍 <b>Endereço:</b> {end_curto}<br>📄 <b>CPF/CNPJ:</b> {str(row.get('CPF_CNPJ', '')).replace('nan', '')} | ✉️ <b>E-mail:</b> {str(row.get('Email_Cliente', '')).replace('nan', '')}<br>👤 <b>Contato:</b> {str(row.get('Contato', '')).replace('nan', '')} | 📅 <b>Cadastro:</b> {data_cad}", unsafe_allow_html=True)
                        st.write("")
                        c_b1, c_b2 = st.columns([7, 3])
                        with c_b1:
                            if st.button("➕ Criar Proposta", key=f"btn_lead_{idx}", type="primary", use_container_width=True): st.session_state.update({"lead_dados": {"data_cadastro": data_cad, "nome": nome, "cpf_cnpj": str(row.get('CPF_CNPJ', '')).replace('nan', ''), "endereco": str(row.get('Endereco', '')).replace('nan', ''), "numero": str(row.get('Numero', '')).replace('nan', ''), "cidade": str(row.get('Cidade', '')).replace('nan', ''), "estado": str(row.get("Estado", "")).replace('nan', ''), "telefone": telefone, "email_cliente": str(row.get('Email_Cliente', '')).replace('nan', ''), "contato": str(row.get('Contato', '')).replace('nan', ''), "gps": str(row.get("Coordenadas_GPS", "")).replace('nan', '')}, "lead_salvo": True, "gatilho_limpar_carrinho": True, "etapa_atual": "simulador", "editando_lead_idx": linha_real_planilha}); st.rerun()
                        with c_b2:
                            if st.button("✏️ Editar", key=f"btn_edit_lead_{idx}", use_container_width=True): st.session_state.update({"lead_dados": {"data_cadastro": data_cad, "nome": nome, "cpf_cnpj": str(row.get('CPF_CNPJ', '')).replace('nan', ''), "endereco": str(row.get('Endereco', '')).replace('nan', ''), "numero": str(row.get('Numero', '')).replace('nan', ''), "cidade": str(row.get('Cidade', '')).replace('nan', ''), "estado": str(row.get("Estado", "")).replace('nan', ''), "telefone": telefone, "email_cliente": str(row.get('Email_Cliente', '')).replace('nan', ''), "contato": str(row.get('Contato', '')).replace('nan', ''), "gps": str(row.get("Coordenadas_GPS", "")).replace('nan', '')}, "lead_salvo": True, "etapa_atual": "lead", "editando_lead_idx": linha_real_planilha}); st.rerun()

    # --- TELA: LEAD ---
    elif st.session_state["etapa_atual"] == "lead":
        idx_editando_lead = st.session_state.get("editando_lead_idx")
        st.title("👤 Atualizar Dados do Lead" if idx_editando_lead else "👤 1. Cadastro de Novo Lead")
        
        st.write("📍 **Preencher Localização**")
        st.caption("Clique no botão abaixo para registrar sua coordenada atual.")
        
        loc = streamlit_geolocation()
        gps_audit = ""
        if loc and loc.get('latitude'):
            gps_audit = f"{loc['latitude']}, {loc['longitude']}"
            if st.session_state.get("ultimo_gps_capturado") != gps_audit:
                st.session_state["ultimo_gps_capturado"] = gps_audit
                try:
                    location = Nominatim(user_agent="kme_vendas_app_v1").reverse(f"{loc['latitude']}, {loc['longitude']}")
                    if location and location.raw.get('address'):
                        addr = location.raw['address']
                        mapa_estados = {"Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM", "Bahia": "BA", "Ceará": "CE", "Distrito Federal": "DF", "Espírito Santo": "ES", "Goiás": "GO", "Maranhão": "MA", "Mato Grosso": "MT", "Mato Grosso do Sul": "MS", "Minas Gerais": "MG", "Pará": "PA", "Paraíba": "PB", "Paraná": "PR", "Pernambuco": "PE", "Piauí": "PI", "Rio de Janeiro": "RJ", "Rio Grande do Norte": "RN", "Rio Grande do Sul": "RS", "Rondônia": "RO", "Roraima": "RR", "Santa Catarina": "SC", "São Paulo": "SP", "Sergipe": "SE", "Tocantins": "TO"}
                        if addr.get('road', ''): st.session_state["lead_dados"]["endereco"] = addr.get('road', '')
                        if addr.get('house_number', ''): st.session_state["lead_dados"]["numero"] = addr.get('house_number', '')
                        if addr.get('city', addr.get('town', addr.get('village', addr.get('municipality', '')))): st.session_state["lead_dados"]["cidade"] = addr.get('city', addr.get('town', addr.get('village', addr.get('municipality', ''))))
                        st.session_state["lead_dados"]["estado"] = mapa_estados.get(addr.get('state', ''), "SC")
                except: pass 
            st.success("✅ Localização capturada!")

        ld = st.session_state["lead_dados"]
        with st.form("form_lead"):
            c1, c2 = st.columns(2)
            nome, cpf_cnpj = c1.text_input("Nome / Razão Social *", value=ld.get("nome", "")), c2.text_input("CPF / CNPJ", value=ld.get("cpf_cnpj", ""))
            c3, c4, c5 = st.columns([4, 2, 3])
            endereco, numero, telefone = c3.text_input("Endereço *", value=ld.get("endereco", "")), c4.text_input("Número *", value=ld.get("numero", "")), c5.text_input("Telefone *", value=ld.get("telefone", ""), max_chars=15)
            c6, c7, c8 = st.columns([3, 1, 4])
            cidade = c6.text_input("Cidade", value=ld.get("cidade", ""))
            estados_br = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]
            estado = c7.selectbox("Estado", estados_br, index=estados_br.index(ld.get("estado", "SC").upper()) if ld.get("estado", "SC").upper() in estados_br else estados_br.index("SC"))
            contato, email_cliente = c8.text_input("Nome do Contato", value=ld.get("contato", "")), st.text_input("✉️ E-mail do Cliente", value=ld.get("email_cliente", ""))
            gps_final = gps_audit if gps_audit else ld.get("gps", "")
            
            if st.form_submit_button("Atualizar Dados do Lead ➡️" if idx_editando_lead else "Salvar Lead e Iniciar Proposta ➡️", type="primary", use_container_width=True):
                tel_numeros, email_valido = re.sub(r'\D', '', telefone), False if email_cliente and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email_cliente) else True
                if not nome or not endereco or not numero or not telefone: st.error("⚠️ Atenção: Preencha todos os campos marcados com (*).")
                elif len(tel_numeros) < 10 or len(tel_numeros) > 11: st.error("⚠️ Atenção: O Telefone deve conter o DDD + Número válido (10 ou 11 dígitos).")
                elif not email_valido: st.error("⚠️ Atenção: O E-mail digitado é inválido.")
                elif not (gps_audit if gps_audit else ld.get("gps", "")) and not idx_editando_lead: st.error("⚠️ Atenção: Valide sua localização clicando no ícone de GPS.")
                else:
                    st.session_state["lead_dados"].update({"nome": padronizar_nome(nome), "cpf_cnpj": cpf_cnpj, "endereco": padronizar_nome(endereco), "numero": numero, "cidade": padronizar_nome(cidade), "estado": estado, "telefone": padronizar_telefone(telefone), "contato": padronizar_nome(contato), "email_cliente": email_cliente, "gps": gps_audit if gps_audit else ld.get("gps", "")})
                    if idx_editando_lead:
                        if atualizar_lead(idx_editando_lead, st.session_state["lead_dados"]): st.toast("Lead atualizado!"); st.cache_data.clear(); st.session_state["etapa_atual"] = "meus_leads"; st.rerun()
                    else:
                        novo_idx = salvar_lead(st.session_state["lead_dados"], st.session_state["nome_usuario"], st.session_state["email_usuario"])
                        if novo_idx: st.session_state.update({"lead_salvo": True, "etapa_atual": "simulador", "editando_lead_idx": novo_idx}); st.toast("Lead salvo!"); st.cache_data.clear(); st.rerun()

    # --- TELA: SIMULADOR ---
    elif st.session_state["etapa_atual"] == "simulador":
        st.title("🛒 2. Simulador de Vendas")
        if st.session_state.get("proposta_idx_editando"): st.warning("✏️ **Modo de Edição Ativo:** Você está modificando uma proposta já enviada.")
        col_lead_info, col_lead_btn = st.columns([8, 2])
        with col_lead_info: st.info(f"👤 **Cliente Ativo:** {st.session_state['lead_dados'].get('nome', '')} | 📞 {st.session_state['lead_dados'].get('telefone', '')}")
        with col_lead_btn:
            if st.button("✏️ Editar Lead", use_container_width=True): st.session_state["etapa_atual"] = "lead"; st.rerun()
        nome_proposta = st.text_input("📝 Nome/Referência da Proposta (Ex: Matriz, Filial Centro)", value=st.session_state.get("nome_proposta_atual", ""))
        st.divider()

        try:
            df_produtos, df_valor_sensor, df_valor_ponto, df_regras, cfg = carregar_produtos(), carregar_valores_sensores(), carregar_valores_ponto_mo(), carregar_regras_validacao(), carregar_configuracoes()
            taxa_bruta = cfg.get("Taxa_Juros_Mensal", 0.022)
            taxa_juros = taxa_bruta / 100 if (taxa_bruta >= 10 and taxa_bruta/10 < 1) else (taxa_bruta/100 if taxa_bruta > 1 else taxa_bruta)
            max_sj, max_bol, max_cc = int(cfg.get("Max_Parcelas_Sem_Juros", 3)), int(cfg.get("Max_Parcelas_Boleto", 18)), int(cfg.get("Max_Parcelas_Cartao", 24))
            lim_p, lim_a, lim_i = cfg.get("Desc_Max_Produtos", 15.0), cfg.get("Desc_Max_Alarme", 15.0), cfg.get("Desc_Max_Imagem", 30.0)
            unidades_disponiveis = sorted(list(set(df_valor_ponto['Unidade'].dropna().astype(str).str.strip()))) if not df_valor_ponto.empty and 'Unidade' in df_valor_ponto.columns else ["Padrão"]

            col_produtos, col_resumo = st.columns([5, 5])
            with col_resumo:
                st.write("### 📊 Resumo Financeiro")
                if st.session_state["desc_prod"] > float(lim_p): st.session_state["desc_prod"] = float(lim_p)
                if st.session_state["desc_alarme"] > float(lim_a): st.session_state["desc_alarme"] = float(lim_a)
                if st.session_state["desc_imagem"] > float(lim_i): st.session_state["desc_imagem"] = float(lim_i)
                with st.expander("🏷️ Aplicar Descontos por Categoria"):
                    c_d1, c_d2, c_d3 = st.columns(3)
                    with c_d1: st.number_input(f"Prod (%) [Máx: {lim_p:.0f}%]", min_value=0.0, max_value=float(lim_p), step=0.5, key="desc_prod")
                    with c_d2: st.number_input(f"Alarme (%) [Máx: {lim_a:.0f}%]", min_value=0.0, max_value=float(lim_a), step=0.5, key="desc_alarme")
                    with c_d3: st.number_input(f"Imagem (%) [Máx: {lim_i:.0f}%]", min_value=0.0, max_value=float(lim_i), step=0.5, key="desc_imagem")
                unidade_selecionada = st.selectbox("🏢 Unidade de Mão de Obra", unidades_disponiveis, key="unidade_mo_selecionada")

            with col_produtos:
                st.write("### ➕ Catálogo")
                aba_servicos, aba_produtos, aba_mao_obra = st.tabs(["🔄 Serviços", "📦 Produtos", "🛠️ Mão de Obra"])
                
                def desenhar_card_produto(index, linha):
                    is_aberto, nome_item_limpo, cat_limpa_card, cod_kme = st.session_state.get("item_aberto") == index, str(linha.get('Nome_Item', '')).strip(), str(linha.get('Categoria_Receita', '')).strip().lower(), str(linha.get('Codigo_KME', '')).strip()
                    pv_card = converter_para_numero(linha.get('Preco_Venda', 0))
                    if ("obra" in cat_limpa_card or "instala" in cat_limpa_card) and not df_valor_ponto.empty:
                        match_mo_card = df_valor_ponto[(df_valor_ponto['Unidade'].astype(str).str.strip() == unidade_selecionada) & (df_valor_ponto['Nome_Item'].astype(str).str.strip() == nome_item_limpo)]
                        if not match_mo_card.empty:
                            pv_card = converter_para_numero(match_mo_card.iloc[0]['Valor_MO'])
                            if str(match_mo_card.iloc[0].get('Codigo', '')).strip() and str(match_mo_card.iloc[0].get('Codigo', '')).strip() != 'nan': cod_kme = str(match_mo_card.iloc[0].get('Codigo', '')).strip()
                    if st.button(f"{'🔽' if is_aberto else '▶️'} {nome_item_limpo}{f' (Cód: {cod_kme})' if cod_kme else ''}", key=f"btn_acc_{index}", use_container_width=True): st.session_state["item_aberto"] = None if is_aberto else index; st.rerun()
                    if is_aberto:
                        with st.container():
                            st.caption(f"**Grupo:** {linha.get('Grupo_Itens', 'N/A')} | **Categoria:** {linha.get('Categoria_Receita', '')}")
                            c_qtd, c_add = st.columns([3, 7])
                            qtd = c_qtd.number_input("Qtd", min_value=1, step=1, key=f"qtd_{index}")
                            c_add.write(""); c_add.write("")
                            if c_add.button("Adicionar ao Orçamento", key=f"btn_add_{index}", type="primary", use_container_width=True):
                                st.session_state["carrinho"].append({"nome": nome_item_limpo, "codigo": cod_kme, "tipo_sensor": str(linha.get('Tipo_Sensor', '')), "categoria": str(linha.get('Categoria_Receita', '')), "grupo": str(linha.get('Grupo_Itens', '')), "quantidade": qtd, "preco_venda": pv_card, "preco_mrr": converter_para_numero(linha.get('Preco_LOC_36', 0))})
                                st.session_state["item_aberto"] = None; st.rerun()
                        st.divider()

                def preencher_aba_grupo(df, nome_grupo):
                    itens = df[df['Grupo_Itens'].fillna("").astype(str).str.strip().str.lower() == nome_grupo.lower()]
                    with st.container(height=500):
                        if itens.empty: st.info(f"Nenhum item em '{nome_grupo}'.")
                        else:
                            for index, linha in itens.iterrows(): desenhar_card_produto(index, linha)

                with aba_servicos:
                    grupos_serv = ["Servico Alarme", "Servico Imagem"]
                    sub_abas_serv = st.tabs(grupos_serv + ["Outros"])
                    for i, nome in enumerate(grupos_serv):
                        with sub_abas_serv[i]: preencher_aba_grupo(df_produtos, nome)
                    with sub_abas_serv[-1]:
                        outros_serv = df_produtos[df_produtos['Categoria_Receita'].fillna("").astype(str).str.lower().str.contains("mensal|loca|servi|seguro") & ~df_produtos['Grupo_Itens'].fillna("").astype(str).str.strip().str.lower().isin([g.lower() for g in grupos_serv])]
                        with st.container(height=500):
                            if not outros_serv.empty:
                                for index, linha in outros_serv.iterrows(): desenhar_card_produto(index, linha)

                with aba_produtos:
                    grupos_prod = ["Smart Alarme", "JFL 8W", "AXPRO", "Detect IA", "CFTV"]
                    sub_abas_prod = st.tabs(grupos_prod + ["Outros"])
                    for i, nome in enumerate(grupos_prod):
                        with sub_abas_prod[i]: preencher_aba_grupo(df_produtos, nome)
                    with sub_abas_prod[-1]:
                        outros_prod = df_produtos[~df_produtos['Categoria_Receita'].fillna("").astype(str).str.lower().str.contains("mensal|loca|servi|seguro|obra|instala") & ~df_produtos['Grupo_Itens'].fillna("").astype(str).str.strip().str.lower().isin([g.lower() for g in grupos_prod])]
                        with st.container(height=500):
                            if not outros_prod.empty:
                                for index, linha in outros_prod.iterrows(): desenhar_card_produto(index, linha)

                with aba_mao_obra:
                    st.write("#### 🔹 Instalação e Configuração")
                    itens_mo = df_produtos[df_produtos['Categoria_Receita'].fillna("").astype(str).str.lower().str.contains("obra|instala")]
                    with st.container(height=500):
                        if not itens_mo.empty:
                            for index, linha in itens_mo.iterrows(): desenhar_card_produto(index, linha)

            with col_resumo:
                bruto_alarme, bruto_imagem, bruto_produtos, total_mao_obra = 0.0, 0.0, 0.0, 0.0
                qtd_abertura = sum(it['quantidade'] for it in st.session_state["carrinho"] if str(it.get('tipo_sensor', '')).strip().upper() == 'ABERTURA')
                qtd_ivp = sum(it['quantidade'] for it in st.session_state["carrinho"] if str(it.get('tipo_sensor', '')).strip().upper() == 'IVP')
                
                for item in st.session_state["carrinho"]:
                    cat_limpa, grp_limpo, cod_item, nome_item_limpo = str(item['categoria']).strip().lower(), str(item.get('grupo', '')).strip().lower(), str(item.get('codigo', '')).strip().lstrip('0'), str(item.get('nome', '')).strip()
                    v_u = item['preco_venda'] if item['preco_venda'] > 0 else item['preco_mrr']
                    if ("obra" in cat_limpa or "instala" in cat_limpa) and not df_valor_ponto.empty:
                        match_mo = df_valor_ponto[(df_valor_ponto['Unidade'].astype(str).str.strip() == unidade_selecionada) & (df_valor_ponto['Nome_Item'].astype(str).str.strip() == nome_item_limpo)]
                        if not match_mo.empty:
                            v_u = converter_para_numero(match_mo.iloc[0]['Valor_MO'])
                            if str(match_mo.iloc[0].get('Codigo', '')).strip() and str(match_mo.iloc[0].get('Codigo', '')).strip() != 'nan': item['codigo'] = str(match_mo.iloc[0].get('Codigo', '')).strip()
                    if cod_item in ['254000000042', '254000000377', '25400000042', '25400000377'] and not df_valor_sensor.empty:
                        match = df_valor_sensor[(df_valor_sensor['Codigo_Servico'].astype(str).str.strip().str.lstrip('0') == cod_item) & (pd.to_numeric(df_valor_sensor['Sensor_Abertura'], errors='coerce') == qtd_abertura) & (pd.to_numeric(df_valor_sensor['Sensor_IVP'], errors='coerce') == qtd_ivp)]
                        if not match.empty: v_u = converter_para_numero(match.iloc[0]['Preco'])
                    item['preco_calculado'] = v_u 
                    if "obra" in cat_limpa or "instala" in cat_limpa: total_mao_obra += (v_u * item['quantidade'])
                    elif "produto" in cat_limpa or "equipamento" in cat_limpa: bruto_produtos += (v_u * item['quantidade'])
                    else:
                        if "imagem" in grp_limpo: bruto_imagem += (v_u * item['quantidade'])
                        else: bruto_alarme += (v_u * item['quantidade'])

                liq_produtos = bruto_produtos * (1 - (st.session_state["desc_prod"] / 100))
                liq_alarme = bruto_alarme * (1 - (st.session_state["desc_alarme"] / 100))
                liq_imagem = bruto_imagem * (1 - (st.session_state["desc_imagem"] / 100))
                total_mensal = liq_alarme + liq_imagem

                st.metric("🔄 Total Serviços", f"R$ {total_mensal:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."))
                st.metric("📦 Equipamentos (Setup)", f"R$ {liq_produtos:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."))
                st.metric("🛠️ Mão de Obra", f"R$ {total_mao_obra:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."))
                st.divider()
                st.write("#### 🛒 Seu Orçamento")
                with st.container(height=350):
                    if len(st.session_state["carrinho"]) == 0: st.info("O carrinho está vazio.")
                    else:
                        for i, item in enumerate(st.session_state["carrinho"]):
                            v_u = item.get('preco_calculado', item['preco_venda'] if item['preco_venda'] > 0 else item['preco_mrr'])
                            c_txt, c_btn = st.columns([8, 2])
                            with c_txt: st.write(f"- {item['quantidade']}x {item['nome']} **(R$ {v_u:,.2f})**")
                            with c_btn:
                                if st.button("❌", key=f"del_{i}"): st.session_state["carrinho"].pop(i); st.rerun()
                if len(st.session_state["carrinho"]) > 0:
                    if st.button("🗑️ Limpar Carrinho", use_container_width=True): st.session_state["gatilho_limpar_carrinho"] = True; st.rerun()

            st.divider()
            st.header("💳 Tabela de Parcelamento (Setup Inicial)")
            total_setup = liq_produtos + total_mao_obra
            
            if total_setup > 0:
                col_pag1, col_pag2 = st.columns([4, 6])
                with col_pag1: forma_pagamento = st.radio("Selecione a Forma de Pagamento:", [f"Boleto Bancário (Até {max_bol}x)", f"Cartão de Crédito (Até {max_cc}x)"])
                limite_parcelas = max_bol if "Boleto" in forma_pagamento else max_cc
                with col_pag2: st.write(f"#### 📊 Simulação para **R$ {total_setup:,.2f}** no {forma_pagamento.split(' ')[0]}")
                
                dados_tabela = []
                for n in range(1, limite_parcelas + 1):
                    val_parcela = total_setup / n if n <= max_sj else (total_setup * ((1 + taxa_juros) ** n)) / n
                    total_pago = total_setup if n <= max_sj else (total_setup * ((1 + taxa_juros) ** n))
                    dados_tabela.append({"Plano": f"{n}x", "Valor Parcela": f"R$ {val_parcela:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."), "Total Final": f"R$ {total_pago:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")})
                with st.container(height=300): st.dataframe(dados_tabela, use_container_width=True, hide_index=True)
                
                st.write("---")
                st.subheader("📝 Apresentação Final para o Cliente")
                col_sel1, col_sel2 = st.columns([4, 6])
                with col_sel1: parcela_escolhida = st.selectbox("Selecione a condição fechada com o cliente:", range(1, limite_parcelas + 1), format_func=lambda x: f"{x}x parcela(s)")
                txt_parcela, forma_limpa, mrr_formatado = dados_tabela[parcela_escolhida - 1]["Valor Parcela"], forma_pagamento.split(' ')[0], f"R$ {total_mensal:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
                
                st.markdown(f"""
                    <div style="background-color: #f0f7ff; border-left: 5px solid #0066cc; padding: 18px; border-radius: 8px; margin-bottom: 15px;">
                        <p style="font-size: 1.25rem; font-weight: 600; color: #1e293b; margin-bottom: 10px;">💳 <b>Setup Inicial:</b> <span style="color: #0066cc; font-size: 1.35rem;">{parcela_escolhida}x de {txt_parcela}</span> <span style="font-size: 0.95rem; color: #64748b;">(no {forma_limpa})</span></p>
                        <p style="font-size: 1.25rem; font-weight: 600; color: #1e293b; margin: 0;">🔄 <b>Total Serviços:</b> <span style="color: #059669; font-size: 1.35rem;">{mrr_formatado} / mês</span> <span style="font-size: 0.95rem; color: #64748b;">(no Boleto)</span></p>
                    </div>
                """, unsafe_allow_html=True) 
                
                avisos_projeto = validar_inconsistencias_carrinho(st.session_state["carrinho"], df_regras)
                pode_gravar = True
                if avisos_projeto:
                    st.warning("⚠️ **AVISOS DE INCONSISTÊNCIA TÉCNICA NO PROJETO:**")
                    for a in avisos_projeto: st.write(f"- {a}")
                    if not st.checkbox("Estou ciente das inconsistências técnicas acima e confirmo o salvamento da proposta assim mesmo.", key="chk_override_regras"): pode_gravar = False
                
                _, col_btn_fechar = st.columns([6, 4])
                with col_btn_fechar:
                    if st.button("✅ Fechar Proposta Comercial", type="primary", disabled=not pode_gravar, use_container_width=True):
                        if not nome_proposta.strip(): st.error("⚠️ Por favor, suba a tela e digite um Nome/Referência para a proposta antes de salvar.")
                        else:
                            idx_editando = st.session_state.get("proposta_idx_editando")
                            if idx_editando: sucesso = atualizar_proposta_modificada(idx_editando, nome_proposta, total_mensal, total_setup, forma_limpa, parcela_escolhida, txt_parcela, st.session_state["carrinho"], st.session_state["desc_prod"], st.session_state["desc_alarme"], st.session_state["desc_imagem"])
                            else: sucesso = salvar_proposta(st.session_state["lead_dados"].get("nome", ""), nome_proposta, st.session_state["nome_usuario"], st.session_state["email_usuario"], total_mensal, total_setup, forma_limpa, parcela_escolhida, txt_parcela, st.session_state["carrinho"], st.session_state["desc_prod"], st.session_state["desc_alarme"], st.session_state["desc_imagem"])
                            if sucesso:
                                st.session_state["msg_sucesso"] = f"🎉 Proposta '{nome_proposta}' {'modificada' if idx_editando else 'registrada'} com sucesso!"
                                st.session_state["gatilho_limpar_tudo"] = True; st.cache_data.clear(); st.rerun()
            else: st.info("Adicione itens no carrinho para gerar o parcelamento.")

        except Exception as e: st.error(f"❌ Erro na conexão: {e}")

# ==========================================
# 6. INICIALIZAÇÃO E FLUXO DE TELAS
# ==========================================
if not st.session_state.get("autenticado", False): 
    tela_login()
elif st.session_state.get("precisa_trocar_senha", False):
    tela_trocar_senha()
else: 
    tela_principal()
