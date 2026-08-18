import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import re
import os
import pydeck as pdk
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
    div.stButton > button { min-height: 2.2rem !important; height: auto !important; padding: 4px 15px !important; text-align: left !important; display: flex !important; justify-content: flex-start !important; align-items: center !important; width: 100% !important; }
    div.stButton > button * { text-align: left !important; justify-content: flex-start !important; }
    div.stButton > button[kind="primary"] { justify-content: center !important; text-align: center !important; }
    div.stButton > button[kind="primary"] * { text-align: center !important; justify-content: center !important; }
    .card-mobile { background-color: #f8fafc; border-left: 4px solid #0066cc; padding: 12px; border-radius: 6px; margin-bottom: 10px; }
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
        df = pd.DataFrame(conectar_banco().worksheet("Funil_Vendas").get_all_records())
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
    return " ".join([p.lower() if p.lower() in excecoes else p.lower().capitalize() for p in palavras])

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

def obter_detalhes_split(row_data, df_produtos, df_valor_sensor, df_valor_ponto, unidade_selecionada):
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
        
        if ("obra" in cat or "instala" in cat) and not df_valor_ponto.empty:
            match_mo = df_valor_ponto[(df_valor_ponto['Unidade'].astype(str).str.strip() == unidade_selecionada) & (df_valor_ponto['Nome_Item'].astype(str).str.strip() == str(prod.get('Nome_Item', '')).strip())]
            if not match_mo.empty: v_u = converter_para_numero(match_mo.iloc[0]['Valor_MO'])
            
        if cod_item in ['254000000042', '254000000377', '25400000042', '25400000377']:
            if not df_valor_sensor.empty:
                match = df_valor_sensor[(df_valor_sensor['Codigo_Servico'].astype(str).str.strip().str.lstrip('0') == cod_item) & (pd.to_numeric(df_valor_sensor['Sensor_Abertura'], errors='coerce') == qtd_abertura) & (pd.to_numeric(df_valor_sensor['Sensor_IVP'], errors='coerce') == qtd_ivp)]
                if not match.empty: v_u = converter_para_numero(match.iloc[0]['Preco'])
                    
        if "obra" in cat or "instala" in cat: mao_obra += (v_u * qtd)
        elif "produto" in cat or "equipamento" in cat: bruto_prod += (v_u * qtd)
        else:
            if "imagem" in grupo: bruto_imagem += (v_u * qtd)
            else: bruto_alarme += (v_u * qtd)
            
    liq_prod = bruto_prod * (1 - desc_p)
    liq_mrr = (bruto_alarme * (1 - desc_a)) + (bruto_imagem * (1 - desc_i))

    mrr_fmt = f"R$ {liq_mrr:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    eqp_fmt = f"R$ {liq_prod:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    mo_fmt = f"R$ {mao_obra:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    
    return mrr_fmt, eqp_fmt, mo_fmt

# --- MOTOR DE E-MAILS DE APROVAÇÃO ---
def obter_emails_gestores(df_users, unidade_user, vertical_user):
    emails = []
    lideres = df_users[(df_users['Perfil'].astype(str).str.strip() == 'Lider') & (df_users['Unidade'].astype(str).str.strip().str.lower() == str(unidade_user).strip().lower())]
    emails.extend(lideres['Email_C'].tolist())
    
    if "varejo" in str(vertical_user).lower():
        gerentes = df_users[df_users['Perfil'].astype(str).str.strip() == 'Gerente_Varejo']
        emails.extend(gerentes['Email_C'].tolist())
    elif "condominio" in str(vertical_user).lower():
        gerentes = df_users[df_users['Perfil'].astype(str).str.strip() == 'Gerente_Condominio']
        emails.extend(gerentes['Email_C'].tolist())
        
    return list(set(emails))

def enviar_email_aprovacao(nome_consultor, unidade, vertical, valor_mrr, valor_equip, valor_mo, emails_destino):
    try:
        if "smtp" not in st.secrets:
            st.info("💡 E-mail de aprovação gerado! (Para envio real, configure as credenciais SMTP no Cloud).")
            return True
            
        remetente = st.secrets["smtp"]["email"]
        senha = st.secrets["smtp"]["password"]
        servidor = st.secrets["smtp"]["server"]
        porta = st.secrets["smtp"]["port"]

        msg = MIMEMultipart()
        msg['From'] = remetente
        msg['To'] = ", ".join(emails_destino)
        msg['Subject'] = "Contrato Aprovado pelo Cliente 🏆"

        html = f"""
        <div style="font-family: Arial, sans-serif; color: #1e293b;">
            <h2 style="color: #0066cc;">Nova Aprovação de Contrato!</h2>
            <p>Olá, Sinalizamos a aprovação do contrato abaixo:</p>
            <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%; max-width: 600px;">
                <tr style="background-color: #f8fafc;">
                    <td style="width: 40%;"><b>Nome Consultor:</b></td>
                    <td>{nome_consultor}</td>
                </tr>
                <tr>
                    <td><b>Unidade:</b></td>
                    <td>{unidade}</td>
                </tr>
                <tr style="background-color: #f8fafc;">
                    <td><b>Segmento:</b></td>
                    <td>{vertical}</td>
                </tr>
                <tr>
                    <td><b>Valor Mensalidade:</b></td>
                    <td><span style="color: #059669; font-weight: bold;">{valor_mrr}</span></td>
                </tr>
                <tr style="background-color: #f8fafc;">
                    <td><b>Valor Venda Equipamentos:</b></td>
                    <td>{valor_equip}</td>
                </tr>
                <tr>
                    <td><b>Valor Mão de Obra:</b></td>
                    <td>{valor_mo}</td>
                </tr>
            </table>
            <br>
            <p><i>Obs: Proposta Segue para Análise de Cadastro/Crédito.</i></p>
        </div>
        """
        msg.attach(MIMEText(html, 'html'))

        server = smtplib.SMTP(servidor, porta)
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, emails_destino, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Erro ao disparar email: {e}")
        return False

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
    st.session_state["temp_proposta_atual"] = str(dados_prop.get('Temperatura', 'Quente 🔥'))
    st.session_state["status_proposta_atual"] = str(dados_prop.get('Status_Proposta', 'Em Negociação'))
    
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
    num_cols = 4 
    if perfil == "Diretoria": num_cols = 6
    elif "Gerente" in perfil: num_cols = 5
    
    cols = st.columns(num_cols)
    idx = 0
    
    filtro_vert = "Todas"
    if perfil == "Diretoria":
        opcoes_vert = ["Todas"] + sorted(df_users['Vertical'].dropna().unique().tolist())
        filtro_vert = cols[idx].selectbox("Vertical", opcoes_vert)
        if filtro_vert != "Todas": df_users = df_users[df_users['Vertical'] == filtro_vert]
        idx += 1
            
    filtro_unid = "Todas"
    if perfil in ["Diretoria", "Gerente_Varejo", "Gerente_Condominio"]:
        opcoes_unid = ["Todas"] + sorted(df_users['Unidade'].dropna().unique().tolist())
        filtro_unid = cols[idx].selectbox("Unidade", opcoes_unid)
        if filtro_unid != "Todas": df_users = df_users[df_users['Unidade'] == filtro_unid]
        idx += 1
            
    opcoes_vend = ["Todos"] + sorted(df_users['Nome'].dropna().unique().tolist())
    filtro_vend = cols[idx].selectbox("Vendedor", opcoes_vend)
    if filtro_vend != "Todos": df_users = df_users[df_users['Nome'] == filtro_vend]
    idx += 1
    
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
    
    filtro_mes = cols[idx].selectbox("Mês", meses_d)
    if filtro_mes != "Todos":
        if not df_eq_l.empty: df_eq_l = df_eq_l[df_eq_l['Mes_Ano'] == filtro_mes]
        if not df_eq_p.empty: df_eq_p = df_eq_p[df_eq_p['Mes_Ano'] == filtro_mes]
    idx += 1
        
    dias_d = []
    if not df_eq_l.empty: dias_d.extend(df_eq_l['Dia_Str'].dropna().unique().tolist())
    if not df_eq_p.empty: dias_d.extend(df_eq_p['Dia_Str'].dropna().unique().tolist())
    dias_d = sorted(list(set(dias_d)))
    if 'Sem Data' in dias_d: dias_d.remove('Sem Data')
    dias_d = ["Todos"] + dias_d
    
    filtro_dia = cols[idx].selectbox("Dia", dias_d)
    if filtro_dia != "Todos":
        if not df_eq_l.empty: df_eq_l = df_eq_l[df_eq_l['Dia_Str'] == filtro_dia]
        if not df_eq_p.empty: df_eq_p = df_eq_p[df_eq_p['Dia_Str'] == filtro_dia]
    idx += 1
    
    temp_d = []
    if not df_eq_p.empty and 'Temperatura' in df_eq_p.columns:
        temp_d.extend([str(t).strip() for t in df_eq_p['Temperatura'].dropna().unique().tolist() if str(t).strip() != ''])
    temp_d = sorted(list(set(temp_d)))
    temp_d = ["Todas"] + temp_d
    
    if idx < num_cols:
        filtro_temp = cols[idx].selectbox("Temp. Proposta", temp_d)
        if filtro_temp != "Todas" and not df_eq_p.empty:
            df_eq_p = df_eq_p[df_eq_p['Temperatura'].astype(str).str.strip() == filtro_temp]

    mapa_v = dict(zip(df_users['Email_C'], df_users['Nome']))
    return df_eq_l, df_eq_p, mapa_v

# ==========================================
# 3. MEMÓRIA E ESTADOS
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
    cfg = carregar_configuracoes()
    vertical_user = str(st.session_state.get('vertical_usuario', '')).strip().lower()
    
    if "varejo" in vertical_user: limite_vencimento, limite_temp = int(cfg.get("Venc_Proposta_Varejo", 10)), int(cfg.get("Temp_Proposta_Varejo", 5))
    elif "condominio" in vertical_user: limite_vencimento, limite_temp = int(cfg.get("Venc_Proposta_Cond", 10)), int(cfg.get("Temp_Proposta_Cond", 5))
    elif "grandes_contas" in vertical_user or "gc" in vertical_user: limite_vencimento, limite_temp = int(cfg.get("Venc_Proposta_GC", 10)), int(cfg.get("Temp_Proposta_GC", 5))
    else: limite_vencimento, limite_temp = int(cfg.get("Venc_Proposta", 10)), int(cfg.get("Temp_Proposta", 5))

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
            # PROPOSTAS APROVADAS NÃO VENCEM!
            if status in ["Perdida", "Fechada", "Aprovada"]: continue
            
            data_ref_prop_str = str(row.get('Data_Proposta_Renovada', '')).strip() or str(row.get('Data_Proposta', '')).strip()
            data_ref_temp_str = str(row.get('Data_Temperatura_Renovada', '')).strip() or str(row.get('Data_Proposta', '')).strip()
            
            try:
                data_ref_prop = datetime.datetime.strptime(data_ref_prop_str, "%d/%m/%Y %H:%M:%S") if " " in data_ref_prop_str else datetime.datetime.strptime(data_ref_prop_str, "%d/%m/%Y")
                dias_passados_prop = (hoje - data_ref_prop).days
            except: dias_passados_prop = 0
            
            try:
                data_ref_temp = datetime.datetime.strptime(data_ref_temp_str, "%d/%m/%Y %H:%M:%S") if " " in data_ref_temp_str else datetime.datetime.strptime(data_ref_temp_str, "%d/%m/%Y")
                dias_passados_temp = (hoje - data_ref_temp).days
            except: dias_passados_temp = 0
            
            venc_prop = dias_passados_prop >= limite_vencimento
            venc_temp = dias_passados_temp >= limite_temp
            
            if venc_prop or venc_temp:
                propostas_vencidas.append({"idx_planilha": idx + 2, "dados": row, "vencida_prop": venc_prop, "vencida_temp": venc_temp, "dias_prop": dias_passados_prop, "dias_temp": dias_passados_temp})

    # --- TELA DE TRAVA VENCIDA (DUPLA CHECAGEM) ---
    if len(propostas_vencidas) > 0 and not st.session_state.get("proposta_idx_editando"):
        st.error("🚨 **AÇÃO EXIGIDA NO PIPELINE:** Você possui propostas ou temperaturas com o prazo de validade expirado!")
        st.warning("O sistema foi bloqueado temporariamente. Realize o follow-up abaixo para liberar o uso.")
        st.write("---")
        for p in propostas_vencidas:
            with st.container():
                st.markdown(f"### 💼 Cliente: {p['dados'].get('Nome_Cliente', '')} *(Ref: {p['dados'].get('Nome_Proposta', '')})*")
                
                if p['vencida_prop']: 
                    st.caption(f"🚨 **Proposta Vencida** há {p['dias_prop']} dias. (Limite: {limite_vencimento}d)")
                    opcoes_acao = ["Selecione...", f"Renovar Proposta e Temperatura", "Aprovação da Proposta", "Perda na negociação"]
                else: 
                    st.caption(f"⚠️ **Temperatura Vencida** há {p['dias_temp']} dias. (Limite: {limite_temp}d)")
                    opcoes_acao = ["Selecione...", "Atualizar Temperatura", "Aprovação da Proposta", "Perda na negociação"]
                
                c1, c2 = st.columns(2)
                acao = c1.selectbox("O que aconteceu com esta negociação?", opcoes_acao, key=f"acao_{p['idx_planilha']}")
                
                motivo, nova_temp = "", ""
                if acao == "Perda na negociação":
                    motivo = c2.selectbox("Motivo da Perda:", ["Selecione...", "Perdeu Interesse", "Valor Alto", "Fechou com Concorrente", "Tecnologia não atende", "Sem retorno do Cliente"], key=f"mot_{p['idx_planilha']}")
                elif acao in ["Atualizar Temperatura", "Renovar Proposta e Temperatura"]:
                    nova_temp = c2.selectbox("Nova Temperatura da Negociação:", ["Quente 🔥", "Morno 🌤️", "Frio ❄️"], key=f"temp_{p['idx_planilha']}")
                
                if acao != "Selecione...":
                    if acao == "Perda na negociação":
                        if motivo == "Selecione...": st.info("⚠️ Selecione o motivo da perda para confirmar.")
                        elif st.button("Confirmar Perda", type="primary", key=f"btn_{p['idx_planilha']}"):
                            if efetivar_perda(p['idx_planilha'], motivo): st.toast(f"Proposta atualizada para Perdida."); st.cache_data.clear(); st.rerun()
                    
                    elif acao == "Aprovação da Proposta":
                        if st.button("🏆 Confirmar Aprovação", type="primary", key=f"btn_aprov_{p['idx_planilha']}"):
                            if efetivar_aprovacao(p['idx_planilha']):
                                mrr_fmt, eqp_fmt, mo_fmt = obter_detalhes_split(p['dados'], df_produtos, df_valor_sensor, df_valor_ponto, st.session_state['unidade_usuario'])
                                df_us = carregar_usuarios()
                                df_us['Email_C'] = df_us['Email'].astype(str).str.strip().str.lower()
                                emails_destino = obter_emails_gestores(df_us, st.session_state['unidade_usuario'], st.session_state['vertical_usuario'])
                                if emails_destino:
                                    enviar_email_aprovacao(st.session_state['nome_usuario'], st.session_state['unidade_usuario'], st.session_state['vertical_usuario'], mrr_fmt, eqp_fmt, mo_fmt, emails_destino)

                                st.toast("Proposta Aprovada com sucesso! 🏆"); st.cache_data.clear(); st.rerun()

                    elif acao == "Atualizar Temperatura":
                        if st.button("Confirmar Nova Temperatura", type="primary", key=f"btn_temp_{p['idx_planilha']}"):
                            if efetivar_atualizacao_temperatura(p['idx_planilha'], nova_temp):
                                st.toast("Temperatura renovada com sucesso!"); st.cache_data.clear(); st.rerun()
                                
                    elif acao == "Renovar Proposta e Temperatura":
                        mrr_n, setup_n = calcular_novos_valores_proposta(p['dados'], df_produtos, df_valor_sensor)
                        mrr_a, setup_a = p['dados'].get('Total_MRR', ''), p['dados'].get('Total_Setup', '')
                        pode_salvar = True
                        if mrr_n != mrr_a or setup_n != setup_a:
                            st.warning(f"⚠️ **ATENÇÃO:** Os preços da tabela base foram atualizados!\n\n**Total Serviços:** de {mrr_a} ➡️ **{mrr_n}**\n**Setup:** de {setup_a} ➡️ **{setup_n}**")
                            if not st.checkbox("Estou ciente e avisarei o cliente.", key=f"chk_{p['idx_planilha']}"): pode_salvar = False
                        
                        c_b1, c_b2 = st.columns([3, 7])
                        if c_b1.button("Confirmar Renovação Completa", type="primary", disabled=not pode_salvar, key=f"btn_ren_{p['idx_planilha']}"):
                            if efetivar_renovacao(p['idx_planilha'], mrr_n, setup_n, nova_temp): st.toast("Renovada com sucesso!"); st.cache_data.clear(); st.rerun()
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

    # --- TELA: LOCALIZAÇÃO DA EQUIPE (MAPA AVANÇADO) ---
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
                df_mapa['Nome_Exibicao'] = df_mapa['Nome_Razao'].astype(str).fillna('Cliente Desconhecido')
                df_agrupado = df_mapa.groupby(['lat', 'lon']).agg(
                    Qtd=('Nome_Exibicao', 'count'),
                    Nomes=('Nome_Exibicao', lambda x: ' | '.join(list(x)))
                ).reset_index()
                
                df_agrupado['cor_rgba'] = df_agrupado['Qtd'].apply(lambda x: [0, 102, 204, 200] if x == 1 else [227, 6, 19, 200])
                df_agrupado['raio_tamanho'] = df_agrupado['Qtd'].apply(lambda x: 150 if x == 1 else 250 + (x * 50))
                
                camada_deck = pdk.Layer("ScatterplotLayer", data=df_agrupado, get_position='[lon, lat]', get_color='cor_rgba', get_radius='raio_tamanho', pickable=True)
                visao_inicial = pdk.ViewState(latitude=df_agrupado['lat'].mean(), longitude=df_agrupado['lon'].mean(), zoom=10, pitch=0)
                st.pydeck_chart(pdk.Deck(map_style=None, initial_view_state=visao_inicial, layers=[camada_deck], tooltip={"html": "<b>{Qtd} Lead(s) neste local:</b><br/>{Nomes}", "style": {"backgroundColor": "#1e293b", "color": "white"}}))
                st.caption(f"📍 Mostrando a localização exata de **{len(df_mapa)} lead(s)**. 🔴 Pontos vermelhos maiores indicam múltiplos clientes na mesma coordenada. Passe o mouse em cima para ver os nomes.")
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
                            status_str = str(prop_cliente.iloc[-1].get('Status_Proposta', '')).strip()
                            status_lead = "🏆 Aprovada" if status_str == "Aprovada" else ("🔴 Perdida" if status_str == "Perdida" else "🟢 Proposta")
                    
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
                h1, h_v, h2, h_np, h3, h_temp, h4, h5, h6 = st.columns([2, 2, 3, 2.5, 2, 2, 2.5, 2, 2])
                with h1: st.markdown("**Data**")
                with h_v: st.markdown("**Vendedor**")
                with h2: st.markdown("**👤 Cliente (Ver CRM)**")
                with h_np: st.markdown("**Ref. Proposta**")
                with h3: st.markdown("**Status**")
                with h_temp: st.markdown("**Temp.**")
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
                    temperatura = str(row.get('Temperatura', 'Morno 🌤️')).split(" ")[0]
                    mrr, setup = str(row.get('Total_MRR', '')), str(row.get('Total_Setup', ''))
                    
                    data_ref_prop_str = str(row.get('Data_Proposta_Renovada', '')).strip() or str(row.get('Data_Proposta', '')).strip()
                    data_ref_temp_str = str(row.get('Data_Temperatura_Renovada', '')).strip() or str(row.get('Data_Proposta', '')).strip()
                    
                    tempo_faltante = "-"
                    if status == "Em Negociação":
                        try:
                            d_ref_p = datetime.datetime.strptime(data_ref_prop_str, "%d/%m/%Y %H:%M:%S") if " " in data_ref_prop_str else datetime.datetime.strptime(data_ref_prop_str, "%d/%m/%Y")
                            faltam_p = limite_vencimento - (hoje - d_ref_p).days
                            txt_p = f"{faltam_p}d" if faltam_p >= 0 else "Venc"
                        except: txt_p = "-"
                        try:
                            d_ref_t = datetime.datetime.strptime(data_ref_temp_str, "%d/%m/%Y %H:%M:%S") if " " in data_ref_temp_str else datetime.datetime.strptime(data_ref_temp_str, "%d/%m/%Y")
                            faltam_t = limite_temp - (hoje - d_ref_t).days
                            txt_t = f"{faltam_t}d" if faltam_t >= 0 else "Venc"
                        except: txt_t = "-"
                        tempo_faltante = f"P:{txt_p} | T:{txt_t}"
                    
                    cor_status = "🏆" if status == "Aprovada" else ("🟢" if status == "Em Negociação" else ("🔴" if status == "Perdida" else "⚫"))
                    
                    c1, c_v, c2, c_np, c3, c_temp, c4, c5, c6 = st.columns([2, 2, 3, 2.5, 2, 2, 2.5, 2, 2])
                    with c1: st.write(data_p)
                    with c_v: st.write(vendedor[:12] + ("..." if len(vendedor) > 12 else ""))
                    with c2: 
                        with st.expander(f"👤 {cliente[:18]}{'...' if len(cliente) > 18 else ''}"):
                            itens_crm = extrair_tabela_crm_itens(row.get('Itens_Orcamento', ''))
                            if itens_crm: st.dataframe(itens_crm, use_container_width=True, hide_index=True)
                            else: st.info("Sem detalhes avançados.")
                    with c_np: st.write(nome_prop[:15] + ("..." if len(nome_prop) > 15 else ""))
                    with c3: st.write(f"{cor_status} {status}")
                    with c_temp: st.write(temperatura)
                    with c4: st.write(tempo_faltante)
                    with c5: st.write(mrr)
                    with c6: st.write(setup)

    # --- TELA: MINHAS PROPOSTAS ---
    elif st.session_state["etapa_atual"] == "minhas_propostas":
        st.header("💼 Minhas Propostas Enviadas")
        
        c_tit, c_modo = st.columns([7, 3])
        with c_modo: modo_prop = st.radio("Modo de Exibição:", ["📱 Cartões (Celular)", "🖥️ Tabela Analítica"], key="modo_visao_propostas", horizontal=True)

        if st.session_state.get("renovar_proposta_idx"):
            idx_planilha = st.session_state["renovar_proposta_idx"]
            dados_prop = st.session_state["renovar_proposta_dados"]
            
            st.info(f"🎯 **Gerenciar Proposta:** {dados_prop.get('Nome_Cliente')} *(Ref: {dados_prop.get('Nome_Proposta', '')})*")
            
            c1, c2 = st.columns(2)
            acao = c1.selectbox("O que aconteceu com esta negociação?", 
                                ["Selecione...", "Atualizar Temperatura", "Renovar Proposta e Temperatura", "Aprovação da Proposta", "Perda na negociação", "Modificar Proposta (Simulador)"], 
                                key="acao_prop_manual")
            
            motivo, nova_temp = "", ""
            if acao == "Perda na negociação":
                motivo = c2.selectbox("Motivo da Perda:", ["Selecione...", "Perdeu Interesse", "Valor Alto", "Fechou com Concorrente", "Tecnologia não atende", "Sem retorno do Cliente"], key="mot_manual")
            elif acao in ["Atualizar Temperatura", "Renovar Proposta e Temperatura"]:
                nova_temp = c2.selectbox("Nova Temperatura da Negociação:", ["Quente 🔥", "Morno 🌤️", "Frio ❄️"], key="temp_manual")
            
            if acao != "Selecione...":
                if acao == "Perda na negociação":
                    if motivo == "Selecione...": st.info("⚠️ Selecione o motivo da perda para confirmar.")
                    elif st.button("Confirmar Perda", type="primary"):
                        if efetivar_perda(idx_planilha, motivo):
                            st.session_state["msg_sucesso"] = "Proposta atualizada para Perdida!"
                            st.session_state["renovar_proposta_idx"] = None
                            st.cache_data.clear(); st.rerun()
                            
                elif acao == "Aprovação da Proposta":
                    if st.button("🏆 Confirmar Aprovação", type="primary"):
                        if efetivar_aprovacao(idx_planilha):
                            mrr_fmt, eqp_fmt, mo_fmt = obter_detalhes_split(dados_prop, df_produtos, df_valor_sensor, df_valor_ponto, st.session_state['unidade_usuario'])
                            df_us = carregar_usuarios()
                            df_us['Email_C'] = df_us['Email'].astype(str).str.strip().str.lower()
                            emails_destino = obter_emails_gestores(df_us, st.session_state['unidade_usuario'], st.session_state['vertical_usuario'])
                            if emails_destino:
                                enviar_email_aprovacao(st.session_state['nome_usuario'], st.session_state['unidade_usuario'], st.session_state['vertical_usuario'], mrr_fmt, eqp_fmt, mo_fmt, emails_destino)
                            
                            st.session_state["msg_sucesso"] = "Proposta Aprovada com sucesso! 🏆"
                            st.session_state["renovar_proposta_idx"] = None
                            st.cache_data.clear(); st.rerun()
                            
                elif acao == "Atualizar Temperatura":
                    if st.button("Confirmar Nova Temperatura", type="primary"):
                        if efetivar_atualizacao_temperatura(idx_planilha, nova_temp):
                            st.session_state["msg_sucesso"] = "Temperatura renovada com sucesso!"
                            st.session_state["renovar_proposta_idx"] = None
                            st.cache_data.clear(); st.rerun()
                            
                elif acao == "Renovar Proposta e Temperatura":
                    mrr_n, setup_n = calcular_novos_valores_proposta(dados_prop, df_produtos, df_valor_sensor)
                    mrr_a, setup_a = dados_prop.get('Total_MRR', ''), dados_prop.get('Total_Setup', '')
                    pode_renovar = True
                    
                    if mrr_n != mrr_a or setup_n != setup_a:
                        st.warning(f"⚠️ **ATENÇÃO:** Os preços sofrerão reajuste de acordo com a tabela atual!\n\n**Total Serviços:** de {mrr_a} ➡️ **{mrr_n}**\n**Setup:** de {setup_a} ➡️ **{setup_n}**")
                        if not st.checkbox("Estou ciente e avisarei o cliente da alteração.", key="chk_manual"): pode_renovar = False
                    else:
                        st.success("✅ Os valores da proposta continuam os mesmos da tabela atual.")
                        
                    if st.button("Confirmar Renovação Completa", type="primary", disabled=not pode_renovar):
                        if efetivar_renovacao(idx_planilha, mrr_n, setup_n, nova_temp):
                            st.session_state["msg_sucesso"] = "Renovada com sucesso!"
                            st.session_state["renovar_proposta_idx"] = None
                            st.cache_data.clear(); st.rerun()
                            
                elif acao == "Modificar Proposta (Simulador)":
                    if st.button("✏️ Ir para o Simulador", type="primary"):
                        carregar_proposta_para_simulador(idx_planilha, dados_prop, df_produtos, df_leads)
                        st.rerun()
                        
            if st.button("❌ Cancelar Operação"):
                st.session_state["renovar_proposta_idx"] = None
                st.rerun()
                
            st.divider()

        df_prop = df_prop.iloc[::-1] if not df_prop.empty else pd.DataFrame()
        hoje = datetime.datetime.now()
        cfg = carregar_configuracoes()
        vertical_user = str(st.session_state.get('vertical_usuario', '')).strip().lower()
        if "varejo" in vertical_user: limite_vencimento, limite_temp = int(cfg.get("Venc_Proposta_Varejo", 10)), int(cfg.get("Temp_Proposta_Varejo", 5))
        elif "condominio" in vertical_user: limite_vencimento, limite_temp = int(cfg.get("Venc_Proposta_Cond", 10)), int(cfg.get("Temp_Proposta_Cond", 5))
        elif "grandes_contas" in vertical_user or "gc" in vertical_user: limite_vencimento, limite_temp = int(cfg.get("Venc_Proposta_GC", 10)), int(cfg.get("Temp_Proposta_GC", 5))
        else: limite_vencimento, limite_temp = int(cfg.get("Venc_Proposta", 10)), int(cfg.get("Temp_Proposta", 5))

        if df_prop.empty: st.info("Nenhuma proposta registrada.")
        else:
            if "Tabela" in modo_prop:
                st.write("---")
                h1, h_ult, h2, h_np, h3, h_temp, h4, h5, h6, h7 = st.columns([2, 2, 3, 2.5, 2, 2, 2.5, 2, 2, 2])
                with h1: st.markdown("**Data**")
                with h_ult: st.markdown("**Últ. Prop**")
                with h2: st.markdown("**👤 Cliente (Ver CRM)**")
                with h_np: st.markdown("**Ref. Proposta**")
                with h3: st.markdown("**Status**")
                with h_temp: st.markdown("**Temp.**")
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
                    temperatura = str(row.get('Temperatura', 'Morno 🌤️')).split(" ")[0]
                    data_ref_prop_str = str(row.get('Data_Proposta_Renovada', '')).strip() or str(row.get('Data_Proposta', '')).strip()
                    data_ref_temp_str = str(row.get('Data_Temperatura_Renovada', '')).strip() or str(row.get('Data_Proposta', '')).strip()
                    
                    tempo_faltante = "-"
                    if status == "Em Negociação":
                        try:
                            d_ref_p = datetime.datetime.strptime(data_ref_prop_str, "%d/%m/%Y %H:%M:%S") if " " in data_ref_prop_str else datetime.datetime.strptime(data_ref_prop_str, "%d/%m/%Y")
                            faltam_p = limite_vencimento - (hoje - d_ref_p).days
                            txt_p = f"{faltam_p}d" if faltam_p >= 0 else "Venc"
                        except: txt_p = "-"
                        try:
                            d_ref_t = datetime.datetime.strptime(data_ref_temp_str, "%d/%m/%Y %H:%M:%S") if " " in data_ref_temp_str else datetime.datetime.strptime(data_ref_temp_str, "%d/%m/%Y")
                            faltam_t = limite_temp - (hoje - d_ref_t).days
                            txt_t = f"{faltam_t}d" if faltam_t >= 0 else "Venc"
                        except: txt_t = "-"
                        tempo_faltante = f"P:{txt_p} | T:{txt_t}"
                    
                    cor_status = "🏆" if status == "Aprovada" else ("🟢" if status == "Em Negociação" else ("🔴" if status == "Perdida" else "⚫"))
                    
                    c1, c_ult, c2, c_np, c3, c_temp, c4, c5, c6, c7 = st.columns([2, 2, 3, 2.5, 2, 2, 2.5, 2, 2, 2])
                    with c1: st.write(data_p)
                    with c_ult: st.write(data_ult_str if data_ult_str else "-")
                    with c2: 
                        with st.expander(f"👤 {cliente[:18]}{'...' if len(cliente)>18 else ''}"):
                            itens_crm = extrair_tabela_crm_itens(row.get('Itens_Orcamento', ''))
                            if itens_crm: st.dataframe(itens_crm, use_container_width=True, hide_index=True)
                    with c_np: st.write(nome_prop[:15] + ("..." if len(nome_prop)>15 else ""))
                    with c3: st.write(f"{cor_status} {status}")
                    with c_temp: st.write(temperatura)
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
                    temperatura = str(row.get('Temperatura', 'Morno 🌤️')).split(" ")[0]
                    data_ref_prop_str = str(row.get('Data_Proposta_Renovada', '')).strip() or str(row.get('Data_Proposta', '')).strip()
                    data_ref_temp_str = str(row.get('Data_Temperatura_Renovada', '')).strip() or str(row.get('Data_Proposta', '')).strip()
                    
                    tempo_faltante = "-"
                    if status == "Em Negociação":
                        try:
                            d_ref_p = datetime.datetime.strptime(data_ref_prop_str, "%d/%m/%Y %H:%M:%S") if " " in data_ref_prop_str else datetime.datetime.strptime(data_ref_prop_str, "%d/%m/%Y")
                            faltam_p = limite_vencimento - (hoje - d_ref_p).days
                            txt_p = f"{faltam_p}d" if faltam_p >= 0 else "Venc"
                        except: txt_p = "-"
                        try:
                            d_ref_t = datetime.datetime.strptime(data_ref_temp_str, "%d/%m/%Y %H:%M:%S") if " " in data_ref_temp_str else datetime.datetime.strptime(data_ref_temp_str, "%d/%m/%Y")
                            faltam_t = limite_temp - (hoje - d_ref_t).days
                            txt_t = f"{faltam_t}d" if faltam_t >= 0 else "Venc"
                        except: txt_t = "-"
                        tempo_faltante = f"Prop: {txt_p} | Temp: {txt_t}"
                    
                    cor_status = "🏆" if status == "Aprovada" else ("🟢" if status == "Em Negociação" else ("🔴" if status == "Perdida" else "⚫"))
                    
                    with st.expander(f"{cor_status} {cliente} — {nome_prop} ({data_p})"):
                        st.markdown(f"**Status:** {status} | **Temp:** {temperatura} | **Restante:** {tempo_faltante}<br>**Serviços:** {mrr} | **Setup:** {setup}", unsafe_allow_html=True)
                        itens_crm = extrair_tabela_crm_itens(row.get('Itens_Orcamento', ''))
                        if itens_crm: st.write("---"); st.markdown("📋 **Itens do Projeto para CRM:**"); st.dataframe(itens_crm, use_container_width=True, hide_index=True)
                        st.write("")
                        if status == "Em Negociação":
                            if st.button("🔄 Renovar / Editar Proposta", key=f"ren_tab_{linha_real_planilha}", type="primary", use_container_width=True): st.session_state["renovar_proposta_idx"] = linha_real_planilha; st.session_state["renovar_proposta_dados"] = row.to_dict(); st.rerun()

# ==========================================
# 6. INICIALIZAÇÃO E FLUXO DE TELAS
# ==========================================
if not st.session_state.get("autenticado", False): 
    tela_login()
elif st.session_state.get("precisa_trocar_senha", False):
    tela_trocar_senha()
else: 
    tela_principal()
