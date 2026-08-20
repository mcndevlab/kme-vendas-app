import streamlit as st
import pandas as pd
import datetime
import re
import os
import urllib.parse
import pydeck as pdk
from streamlit_geolocation import streamlit_geolocation
from geopy.geocoders import Nominatim

from modulos.db import (carregar_produtos, carregar_valores_sensores, carregar_valores_ponto_mo,
                        carregar_regras_validacao, carregar_configuracoes, carregar_usuarios,
                        carregar_todos_leads, carregar_todas_propostas, carregar_meus_leads,
                        carregar_minhas_propostas, salvar_lead, atualizar_lead, salvar_proposta,
                        atualizar_proposta_modificada, efetivar_renovacao, efetivar_atualizacao_temperatura,
                        efetivar_perda, efetivar_aprovacao)

from modulos.utils import (padronizar_nome, padronizar_telefone, extrair_tabela_crm_itens,
                           validar_inconsistencias_carrinho, calcular_novos_valores_proposta,
                           obter_detalhes_split, obter_emails_gestores, enviar_email_aprovacao, 
                           converter_para_numero, gerar_html_proposta, enviar_email_proposta_cliente)

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
    
    # Ao editar, recupera o status original
    st.session_state["temp_proposta_atual"] = str(dados_prop.get('Temperatura', 'Selecione...'))
    st.session_state["status_proposta_atual"] = str(dados_prop.get('Status_Proposta', 'Selecione...'))
    
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

    with st.sidebar:
        if os.path.exists("logo.jpg"): st.image("logo.jpg", width=120)
        st.markdown("### **Khronos Sales**")
        st.write(f"👤 **{st.session_state['nome_usuario']}**")
        st.divider()
        if st.button("➕ Novo Cliente", use_container_width=True): st.session_state.update({"gatilho_limpar_tudo": True, "etapa_atual": "lead"}); st.rerun()
        if st.button("📋 Meus Clientes", use_container_width=True): st.session_state.update({"etapa_atual": "meus_leads", "proposta_idx_editando": None}); st.rerun()
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
        st.session_state.update({
            "carrinho": [], "desc_prod": 0.0, "desc_alarme": 0.0, "desc_imagem": 0.0, 
            "lead_dados": {}, "lead_salvo": False, "renovar_proposta_idx": None, 
            "proposta_idx_editando": None, "editando_lead_idx": None, "nome_proposta_atual": "", 
            "temp_proposta_atual": "Selecione...", "status_proposta_atual": "Selecione...", 
            "ultimo_gps_capturado": "", "item_aberto": None, "unidade_mo_selecionada": None, 
            "gatilho_limpar_tudo": False
        })
    if st.session_state.get("gatilho_limpar_carrinho", False):
        st.session_state.update({"carrinho": [], "desc_prod": 0.0, "desc_alarme": 0.0, "desc_imagem": 0.0, "item_aberto": None, "gatilho_limpar_carrinho": False})
    if st.session_state["msg_sucesso"] != "": st.success(st.session_state["msg_sucesso"]); st.session_state["msg_sucesso"] = ""

    # --- TELAS INTERNAS ---
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
                st.pydeck_chart(pdk.Deck(map_style=None, initial_view_state=visao_inicial, layers=[camada_deck], tooltip={"html": "<b>{Qtd} Cliente(s) neste local:</b><br/>{Nomes}", "style": {"backgroundColor": "#1e293b", "color": "white"}}))
                st.caption(f"📍 Mostrando a localização exata de **{len(df_mapa)} cliente(s)**.")
            else: st.info("Nenhuma localização válida com os filtros selecionados.")
        else: st.info("Nenhum cliente com localização registrada.")

    elif st.session_state["etapa_atual"] == "funil_equipe":
        st.header("📊 Funil da Equipe")
        df_users = carregar_usuarios()
        df_users['Email_C'] = df_users['Email'].astype(str).str.strip().str.lower()
        perfil, minha_unidade = st.session_state['perfil_usuario'], st.session_state['unidade_usuario'].lower()
        
        df_eq_leads, df_eq_prop, mapa_vendedores = aplicar_filtros_gerenciais(df_users, carregar_todos_leads(), carregar_todas_propostas(), perfil, minha_unidade)
        
        st.write("---")
        aba_leads, aba_prop = st.tabs(["📋 Clientes da Equipe", "💼 Propostas da Equipe"])
        
        with aba_leads:
            if df_eq_leads.empty: st.info("Nenhum cliente encontrado para esta seleção.")
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

    elif st.session_state["etapa_atual"] == "minhas_propostas":
        st.header("💼 Minhas Propostas Enviadas")
        
        c_tit, c_modo = st.columns([7, 3])
        with c_modo: modo_prop = st.radio("Modo de Exibição:", ["📱 Cartões (Celular)", "🖥️ Tabela Analítica"], key="modo_visao_propostas", horizontal=True)

        if st.session_state.get("renovar_proposta_idx"):
            idx_planilha = st.session_state["renovar_proposta_idx"]
            dados_prop = st.session_state["renovar_proposta_dados"]
            
            st.info(f"🎯 **Gerenciar Proposta:** {dados_prop.get('Nome_Cliente')} *(Ref: {dados_prop.get('Nome_Proposta', '')})*")
            
            c1, c2 = st.columns(2)
            acao = c1.selectbox("O que aconteceu com esta negociação?", ["Selecione...", "Atualizar Temperatura", "Renovar Proposta e Temperatura", "Aprovação da Proposta", "Perda na negociação", "Modificar Proposta (Simulador)"], key="acao_prop_manual")
            
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
                            st.session_state["renovar_proposta_idx"] = None; st.cache_data.clear(); st.rerun()
                            
                elif acao == "Aprovação da Proposta":
                    if st.button("🏆 Confirmar Aprovação", type="primary"):
                        if efetivar_aprovacao(idx_planilha):
                            mrr_fmt, eqp_fmt, mo_fmt = obter_detalhes_split(dados_prop, df_produtos, df_valor_sensor, df_valor_ponto, st.session_state['unidade_usuario'])
                            df_us = carregar_usuarios()
                            df_us['Email_C'] = df_us['Email'].astype(str).str.strip().str.lower()
                            emails_destino = obter_emails_gestores(df_us, st.session_state['unidade_usuario'], st.session_state['vertical_usuario'])
                            if emails_destino: enviar_email_aprovacao(st.session_state['nome_usuario'], st.session_state['unidade_usuario'], st.session_state['vertical_usuario'], mrr_fmt, eqp_fmt, mo_fmt, emails_destino)
                            st.session_state["msg_sucesso"] = "Proposta Aprovada com sucesso! 🏆"
                            st.session_state["renovar_proposta_idx"] = None; st.cache_data.clear(); st.rerun()
                            
                elif acao == "Atualizar Temperatura":
                    if st.button("Confirmar Nova Temperatura", type="primary"):
                        if efetivar_atualizacao_temperatura(idx_planilha, nova_temp):
                            st.session_state["msg_sucesso"] = "Temperatura renovada com sucesso!"
                            st.session_state["renovar_proposta_idx"] = None; st.cache_data.clear(); st.rerun()
                            
                elif acao == "Renovar Proposta e Temperatura":
                    mrr_n, setup_n = calcular_novos_valores_proposta(dados_prop, df_produtos, df_valor_sensor)
                    mrr_a, setup_a = dados_prop.get('Total_MRR', ''), dados_prop.get('Total_Setup', '')
                    pode_renovar = True
                    
                    if mrr_n != mrr_a or setup_n != setup_a:
                        st.warning(f"⚠️ **ATENÇÃO:** Os preços sofrerão reajuste!\n\n**Total Serviços:** de {mrr_a} ➡️ **{mrr_n}**\n**Setup:** de {setup_a} ➡️ **{setup_n}**")
                        if not st.checkbox("Estou ciente e avisarei o cliente.", key="chk_manual"): pode_renovar = False
                    else: st.success("✅ Os valores continuam os mesmos da tabela atual.")
                        
                    if st.button("Confirmar Renovação Completa", type="primary", disabled=not pode_renovar):
                        if efetivar_renovacao(idx_planilha, mrr_n, setup_n, nova_temp):
                            st.session_state["msg_sucesso"] = "Renovada com sucesso!"
                            st.session_state["renovar_proposta_idx"] = None; st.cache_data.clear(); st.rerun()
                            
                elif acao == "Modificar Proposta (Simulador)":
                    if st.button("✏️ Ir para o Simulador", type="primary"):
                        carregar_proposta_para_simulador(idx_planilha, dados_prop, df_produtos, df_leads); st.rerun()
                        
            if st.button("❌ Cancelar Operação"):
                st.session_state["renovar_proposta_idx"] = None; st.rerun()
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
                    vendedor = str(row.get('Nome_Usuario', ''))
                    
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
                        itens_para_html = [{"quantidade": it["Qtd"], "nome": it["Produto / Serviço"]} for it in extrair_tabela_crm_itens(row.get('Itens_Orcamento', ''))]
                        condicao_txt = f"{str(row.get('Parcelas', '1x'))} de {str(row.get('Valor_Parcela', 'R$ 0,00'))} ({str(row.get('Forma_Pagamento', 'Boleto'))})"
                        html_prop = gerar_html_proposta(cliente, nome_prop, vendedor, itens_para_html, mrr, setup, condicao_txt)
                        st.download_button("📄 Gerar", data=html_prop, file_name=f"Proposta_{cliente}.html", mime="text/html", use_container_width=True, key=f"dl_tab_{linha_real_planilha}")
                        
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
                    vendedor = str(row.get('Nome_Usuario', ''))
                    
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
                        
                        itens_para_html = [{"quantidade": it["Qtd"], "nome": it["Produto / Serviço"]} for it in extrair_tabela_crm_itens(row.get('Itens_Orcamento', ''))]
                        condicao_txt = f"{str(row.get('Parcelas', '1x'))} de {str(row.get('Valor_Parcela', 'R$ 0,00'))} ({str(row.get('Forma_Pagamento', 'Boleto'))})"
                        html_prop = gerar_html_proposta(cliente, nome_prop, vendedor, itens_para_html, mrr, setup, condicao_txt)
                        
                        c_b1, c_b2 = st.columns(2)
                        with c_b1:
                            st.download_button("📄 Gerar PDF/HTML", data=html_prop, file_name=f"Proposta_{cliente}.html", mime="text/html", use_container_width=True, key=f"dl_card_{linha_real_planilha}")
                        with c_b2:
                            if status == "Em Negociação":
                                if st.button("🔄 Renovar / Editar", key=f"ren_tab_{linha_real_planilha}", type="primary", use_container_width=True): st.session_state["renovar_proposta_idx"] = linha_real_planilha; st.session_state["renovar_proposta_dados"] = row.to_dict(); st.rerun()

    elif st.session_state["etapa_atual"] == "meus_leads":
        st.header("📋 Meus Clientes")
        df_leads = carregar_meus_leads(st.session_state["email_usuario"])
        
        c_busc, c_modo = st.columns([7, 3])
        with c_modo: modo_lead = st.radio("Modo de Exibição:", ["📱 Cartões (Celular)", "🖥️ Tabela Analítica"], key="modo_visao_leads", horizontal=True)

        if df_leads.empty: st.info("Nenhum cliente encontrado no seu funil.")
        else:
            with c_busc: busca = st.text_input("🔍 Buscar Cliente por Nome ou Telefone:")
            if busca: df_leads = df_leads[df_leads.astype(str).apply(lambda x: x.str.contains(busca, case=False)).any(axis=1)]
            df_leads = df_leads.iloc[::-1]

            if "Tabela" in modo_lead:
                st.write("---")
                h1, h2, h3, h4, h5, h6, h7 = st.columns([4, 3, 4, 2, 2, 2, 3])
                with h1: st.markdown("**👤 Nome**")
                with h2: st.markdown("**📞 Telefone**")
                with h3: st.markdown("**📍 Endereço**")
                with h4: st.markdown("**📅 Cadastro**")
                with h5: st.markdown("**📊 Status**")
                with h6: st.markdown("**📅 Últ. Prop**")
                st.write("---")
                    
                for idx, row in df_leads.iterrows():
                    linha_real_planilha = row.name + 2
                    nome = str(row.get('Nome_Razao', 'Não Informado')).strip()
                    telefone = str(row.get('Telefone', '-')).strip()
                    data_cad = str(row.get('Data_Cadastro', '-')).split(" ")[0]
                    end_curto = f"{str(row.get('Endereco', '')).strip()}, {str(row.get('Numero', '')).strip()} - {str(row.get('Cidade', '')).strip()}".replace("nan", "").strip(" ,-") or "-"
                    
                    status_lead, data_ult_prop = "🔵 Lead", "-"
                    df_prop_total = carregar_minhas_propostas(st.session_state["email_usuario"])
                    if not df_prop_total.empty and 'Nome_Cliente' in df_prop_total.columns:
                        prop_cliente = df_prop_total[df_prop_total['Nome_Cliente'].astype(str).str.strip() == nome]
                        if not prop_cliente.empty:
                            status_str = str(prop_cliente.iloc[-1].get('Status_Proposta', '')).strip()
                            status_lead = "🏆 Aprovada" if status_str == "Aprovada" else ("🔴 Perdida" if status_str == "Perdida" else "🟢 Proposta")
                            data_ult_prop = str(prop_cliente.iloc[-1].get('Data_Proposta', '-')).split(" ")[0]

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
                            if st.button("Proposta", key=f"btn_lead_{idx}", use_container_width=True): 
                                st.session_state.update({"lead_dados": {"data_cadastro": data_cad, "nome": nome, "cpf_cnpj": str(row.get('CPF_CNPJ', '')).replace('nan', ''), "endereco": str(row.get('Endereco', '')).replace('nan', ''), "numero": str(row.get('Numero', '')).replace('nan', ''), "cidade": str(row.get('Cidade', '')).replace('nan', ''), "estado": str(row.get("Estado", "")).replace('nan', ''), "telefone": telefone, "email_cliente": str(row.get('Email_Cliente', '')).replace('nan', ''), "contato": str(row.get('Contato', '')).replace('nan', ''), "gps": str(row.get("Coordenadas_GPS", "")).replace('nan', '')}, "lead_salvo": True, "gatilho_limpar_carrinho": True, "etapa_atual": "simulador", "editando_lead_idx": linha_real_planilha, "nome_proposta_atual": "", "temp_proposta_atual": "Selecione...", "status_proposta_atual": "Selecione..."}); st.rerun()
                        with btn2:
                            if st.button("✏️", help="Editar", key=f"btn_edit_lead_{idx}", use_container_width=True): 
                                st.session_state.update({"lead_dados": {"data_cadastro": data_cad, "nome": nome, "cpf_cnpj": str(row.get('CPF_CNPJ', '')).replace('nan', ''), "endereco": str(row.get('Endereco', '')).replace('nan', ''), "numero": str(row.get('Numero', '')).replace('nan', ''), "cidade": str(row.get('Cidade', '')).replace('nan', ''), "estado": str(row.get("Estado", "")).replace('nan', ''), "telefone": telefone, "email_cliente": str(row.get('Email_Cliente', '')).replace('nan', ''), "contato": str(row.get('Contato', '')).replace('nan', ''), "gps": str(row.get("Coordenadas_GPS", "")).replace('nan', '')}, "lead_salvo": True, "etapa_atual": "lead", "editando_lead_idx": linha_real_planilha}); st.rerun()

            else:
                for idx, row in df_leads.iterrows():
                    linha_real_planilha = row.name + 2
                    nome = str(row.get('Nome_Razao', 'Não Informado')).strip()
                    telefone = str(row.get('Telefone', '-')).strip()
                    data_cad = str(row.get('Data_Cadastro', '-')).split(" ")[0]
                    end_curto = f"{str(row.get('Endereco', '')).strip()}, {str(row.get('Numero', '')).strip()} - {str(row.get('Cidade', '')).strip()}".replace("nan", "").strip(" ,-") or "-"
                    
                    status_lead = "🔵 Lead"
                    df_prop_total = carregar_minhas_propostas(st.session_state["email_usuario"])
                    if not df_prop_total.empty and 'Nome_Cliente' in df_prop_total.columns:
                        prop_cliente = df_prop_total[df_prop_total['Nome_Cliente'].astype(str).str.strip() == nome]
                        if not prop_cliente.empty: 
                            status_str = str(prop_cliente.iloc[-1].get('Status_Proposta', '')).strip()
                            status_lead = "🏆 Aprovada" if status_str == "Aprovada" else ("🔴 Perdida" if status_str == "Perdida" else "🟢 Proposta")

                    with st.expander(f"👤 {nome} ({status_lead})"):
                        st.markdown(f"📞 <b>Telefone:</b> {telefone}<br>📍 <b>Endereço:</b> {end_curto}<br>📄 <b>CPF/CNPJ:</b> {str(row.get('CPF_CNPJ', '')).replace('nan', '')} | ✉️ <b>E-mail:</b> {str(row.get('Email_Cliente', '')).replace('nan', '')}<br>👤 <b>Contato:</b> {str(row.get('Contato', '')).replace('nan', '')} | 📅 <b>Cadastro:</b> {data_cad}", unsafe_allow_html=True)
                        st.write("")
                        c_b1, c_b2 = st.columns([7, 3])
                        with c_b1:
                            if st.button("➕ Criar Proposta", key=f"btn_lead_{idx}", type="primary", use_container_width=True): 
                                st.session_state.update({"lead_dados": {"data_cadastro": data_cad, "nome": nome, "cpf_cnpj": str(row.get('CPF_CNPJ', '')).replace('nan', ''), "endereco": str(row.get('Endereco', '')).replace('nan', ''), "numero": str(row.get('Numero', '')).replace('nan', ''), "cidade": str(row.get('Cidade', '')).replace('nan', ''), "estado": str(row.get("Estado", "")).replace('nan', ''), "telefone": telefone, "email_cliente": str(row.get('Email_Cliente', '')).replace('nan', ''), "contato": str(row.get('Contato', '')).replace('nan', ''), "gps": str(row.get("Coordenadas_GPS", "")).replace('nan', '')}, "lead_salvo": True, "gatilho_limpar_carrinho": True, "etapa_atual": "simulador", "editando_lead_idx": linha_real_planilha, "nome_proposta_atual": "", "temp_proposta_atual": "Selecione...", "status_proposta_atual": "Selecione..."}); st.rerun()
                        with c_b2:
                            if st.button("✏️ Editar", key=f"btn_edit_lead_{idx}", use_container_width=True): 
                                st.session_state.update({"lead_dados": {"data_cadastro": data_cad, "nome": nome, "cpf_cnpj": str(row.get('CPF_CNPJ', '')).replace('nan', ''), "endereco": str(row.get('Endereco', '')).replace('nan', ''), "numero": str(row.get('Numero', '')).replace('nan', ''), "cidade": str(row.get('Cidade', '')).replace('nan', ''), "estado": str(row.get("Estado", "")).replace('nan', ''), "telefone": telefone, "email_cliente": str(row.get('Email_Cliente', '')).replace('nan', ''), "contato": str(row.get('Contato', '')).replace('nan', ''), "gps": str(row.get("Coordenadas_GPS", "")).replace('nan', '')}, "lead_salvo": True, "etapa_atual": "lead", "editando_lead_idx": linha_real_planilha}); st.rerun()

    elif st.session_state["etapa_atual"] == "lead":
        idx_editando_lead = st.session_state.get("editando_lead_idx")
        st.title("👤 Atualizar Dados do Cliente" if idx_editando_lead else "👤 1. Cadastro de Novo Cliente")
        
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
            
            if st.form_submit_button("Atualizar Dados do Cliente ➡️" if idx_editando_lead else "Salvar Cliente e Iniciar Proposta ➡️", type="primary", use_container_width=True):
                tel_numeros, email_valido = re.sub(r'\D', '', telefone), False if email_cliente and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email_cliente) else True
                if not nome or not endereco or not numero or not telefone: st.error("⚠️ Atenção: Preencha todos os campos marcados com (*).")
                elif len(tel_numeros) < 10 or len(tel_numeros) > 11: st.error("⚠️ Atenção: O Telefone deve conter o DDD + Número válido (10 ou 11 dígitos).")
                elif not email_valido: st.error("⚠️ Atenção: O E-mail digitado é inválido.")
                elif not (gps_audit if gps_audit else ld.get("gps", "")) and not idx_editando_lead: st.error("⚠️ Atenção: Valide sua localização clicando no ícone de GPS.")
                else:
                    st.session_state["lead_dados"].update({"nome": padronizar_nome(nome), "cpf_cnpj": cpf_cnpj, "endereco": padronizar_nome(endereco), "numero": numero, "cidade": padronizar_nome(cidade), "estado": estado, "telefone": padronizar_telefone(telefone), "contato": padronizar_nome(contato), "email_cliente": email_cliente, "gps": gps_audit if gps_audit else ld.get("gps", "")})
                    if idx_editando_lead:
                        if atualizar_lead(idx_editando_lead, st.session_state["lead_dados"]): st.toast("Cliente atualizado!"); st.cache_data.clear(); st.session_state["etapa_atual"] = "meus_leads"; st.rerun()
                    else:
                        novo_idx = salvar_lead(st.session_state["lead_dados"], st.session_state["nome_usuario"], st.session_state["email_usuario"])
                        if novo_idx: st.session_state.update({"lead_salvo": True, "etapa_atual": "simulador", "editando_lead_idx": novo_idx, "nome_proposta_atual": "", "temp_proposta_atual": "Selecione...", "status_proposta_atual": "Selecione..."}); st.toast("Cliente salvo!"); st.cache_data.clear(); st.rerun()

    elif st.session_state["etapa_atual"] == "simulador":
        st.title("🛒 2. Simulador de Vendas")
        if st.session_state.get("proposta_idx_editando"): st.warning("✏️ **Modo de Edição Ativo:** Você está modificando uma proposta já enviada.")
        col_lead_info, col_lead_btn = st.columns([8, 2])
        with col_lead_info: st.info(f"👤 **Cliente Ativo:** {st.session_state['lead_dados'].get('nome', '')} | 📞 {st.session_state['lead_dados'].get('telefone', '')}")
        with col_lead_btn:
            if st.button("✏️ Editar Cliente", use_container_width=True): st.session_state["etapa_atual"] = "lead"; st.rerun()
        
        c_nome, c_temp, c_status = st.columns([4, 3, 3])
        with c_nome:
            nome_proposta = st.text_input("📝 Nome/Referência da Proposta (Ex: Matriz, Filial)", value=st.session_state.get("nome_proposta_atual", ""))
            if not nome_proposta.strip():
                st.markdown('<p style="color:#d90429; font-size:0.85rem; margin-top:-10px; font-weight:600;">⚠️ Preenchimento obrigatório</p>', unsafe_allow_html=True)
        with c_temp:
            temp_opcoes = ["Selecione...", "Quente 🔥", "Morno 🌤️", "Frio ❄️"]
            temp_salva = st.session_state.get("temp_proposta_atual", "Selecione...")
            if temp_salva not in temp_opcoes: temp_salva = "Selecione..."
            temperatura_escolhida = st.selectbox("🌡️ Temperatura Atual:", temp_opcoes, index=temp_opcoes.index(temp_salva))
            if temperatura_escolhida == "Selecione...":
                st.markdown('<p style="color:#d90429; font-size:0.85rem; margin-top:-10px; font-weight:600;">⚠️ Preenchimento obrigatório</p>', unsafe_allow_html=True)
        with c_status:
            status_opcoes = ["Selecione...", "Em Negociação", "Aprovada"]
            status_salvo = st.session_state.get("status_proposta_atual", "Selecione...")
            if status_salvo not in status_opcoes: status_salvo = "Selecione..."
            status_escolhido = st.selectbox("📊 Status da Proposta:", status_opcoes, index=status_opcoes.index(status_salvo))
            if status_escolhido == "Selecione...":
                st.markdown('<p style="color:#d90429; font-size:0.85rem; margin-top:-10px; font-weight:600;">⚠️ Preenchimento obrigatório</p>', unsafe_allow_html=True)
        
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
                
                opcoes_unidade = ["Selecione..."] + unidades_disponiveis
                unidade_selecionada_op = st.selectbox("🏢 Unidade de Mão de Obra", opcoes_unidade, index=0)
                unidade_selecionada = None if unidade_selecionada_op == "Selecione..." else unidade_selecionada_op
                
                if not unidade_selecionada:
                    st.markdown('<p style="color:#d90429; font-size:0.85rem; margin-top:-10px; font-weight:600;">⚠️ Selecione a unidade de MO.</p>', unsafe_allow_html=True)

            with col_produtos:
                st.write("### ➕ Catálogo")
                aba_servicos, aba_produtos, aba_mao_obra = st.tabs(["🔄 Serviços", "📦 Produtos", "🛠️ Mão de Obra"])
                
                def desenhar_card_produto(index, linha):
                    is_aberto, nome_item_limpo, cat_limpa_card, cod_kme = st.session_state.get("item_aberto") == index, str(linha.get('Nome_Item', '')).strip(), str(linha.get('Categoria_Receita', '')).strip().lower(), str(linha.get('Codigo_KME', '')).strip()
                    pv_card = converter_para_numero(linha.get('Preco_Venda', 0))
                    
                    if unidade_selecionada and ("obra" in cat_limpa_card or "instala" in cat_limpa_card) and not df_valor_ponto.empty:
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
                            if c_add.button("Adicionar ao Orçamento", key=f"btn_add_{index}", type="primary", use_container_width=True, disabled=(not unidade_selecionada)):
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
                    
                    if unidade_selecionada and ("obra" in cat_limpa or "instala" in cat_limpa) and not df_valor_ponto.empty:
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
                
                if not unidade_selecionada or not nome_proposta.strip() or temperatura_escolhida == "Selecione..." or status_escolhido == "Selecione...":
                    pode_gravar = False
                
                st.write("")
                if st.button("💾 Salvar Orçamento", type="primary", disabled=not pode_gravar, use_container_width=True, help="Preencha o Nome da Proposta, Temperatura, Status e Unidade de Mão de Obra para habilitar"):
                    idx_editando = st.session_state.get("proposta_idx_editando")
                    if idx_editando: sucesso = atualizar_proposta_modificada(idx_editando, nome_proposta, total_mensal, total_setup, forma_limpa, parcela_escolhida, txt_parcela, st.session_state["carrinho"], st.session_state["desc_prod"], st.session_state["desc_alarme"], st.session_state["desc_imagem"], temperatura_escolhida, status_escolhido)
                    else: sucesso = salvar_proposta(st.session_state["lead_dados"].get("nome", ""), nome_proposta, st.session_state["nome_usuario"], st.session_state["email_usuario"], total_mensal, total_setup, forma_limpa, parcela_escolhida, txt_parcela, st.session_state["carrinho"], st.session_state["desc_prod"], st.session_state["desc_alarme"], st.session_state["desc_imagem"], temperatura_escolhida, status_escolhido)
                    if sucesso:
                        if status_escolhido == "Aprovada":
                            df_us = carregar_usuarios()
                            df_us['Email_C'] = df_us['Email'].astype(str).str.strip().str.lower()
                            emails_destino = obter_emails_gestores(df_us, st.session_state['unidade_usuario'], st.session_state['vertical_usuario'])
                            if emails_destino:
                                eqp_fmt = f"R$ {(bruto_produtos * (1 - (st.session_state['desc_prod']/100))):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
                                mo_fmt = f"R$ {total_mao_obra:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
                                enviar_email_aprovacao(st.session_state['nome_usuario'], st.session_state['unidade_usuario'], st.session_state['vertical_usuario'], mrr_formatado, eqp_fmt, mo_fmt, emails_destino)
                            
                        st.session_state["msg_sucesso"] = f"🎉 Orçamento '{nome_proposta}' salvo com sucesso!"
                        st.session_state["gatilho_limpar_tudo"] = True; st.cache_data.clear(); st.rerun()

                condicao_txt = f"{parcela_escolhida}x de {txt_parcela} (no {forma_limpa})"
                setup_txt = f"R$ {total_setup:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
                html_prop = gerar_html_proposta(st.session_state["lead_dados"].get("nome", ""), nome_proposta, st.session_state["nome_usuario"], st.session_state["carrinho"], mrr_formatado, setup_txt, condicao_txt)
                
                email_cliente = st.session_state["lead_dados"].get("email_cliente", "").strip()
                telefone_cliente = st.session_state["lead_dados"].get("telefone", "").strip()
                tel_numeros = re.sub(r'\D', '', telefone_cliente)
                
                tem_email = bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email_cliente)) if email_cliente else False
                tem_telefone = len(tel_numeros) >= 10
                
                msg_wa = f"Olá {st.session_state['lead_dados'].get('nome', '')}, tudo bem?\nSegue o resumo da nossa proposta pela Khronos:\n\n*Setup Inicial:* {condicao_txt}\n*Total Serviços:* {mrr_formatado} / mês\n\nQualquer dúvida, estou à disposição!"
                wa_url = f"https://api.whatsapp.com/send?phone=55{tel_numeros}&text={urllib.parse.quote(msg_wa)}"
                
                st.write("---")
                st.markdown("#### 📤 Ações da Proposta")
                c_gerar, c_email, c_wa, c_contrato = st.columns([2.5, 2.5, 2.5, 3.5])
                
                with c_gerar:
                    st.download_button(
                        label="📄 Gerar Proposta",
                        data=html_prop,
                        file_name=f"Proposta_{st.session_state['lead_dados'].get('nome', '')}.html",
                        mime="text/html",
                        use_container_width=True
                    )
                
                with c_email:
                    if st.button("✉️ Enviar p/ E-mail", disabled=not tem_email, help="Falta E-mail no cadastro do cliente." if not tem_email else f"Enviar para {email_cliente}", use_container_width=True):
                        if enviar_email_proposta_cliente(st.session_state["lead_dados"].get("nome", ""), email_cliente, html_prop):
                            st.toast(f"E-mail enviado com sucesso para {email_cliente}! ✉️")
                            
                with c_wa:
                    if tem_telefone:
                        st.link_button("💬 Enviar p/ WhatsApp", wa_url, use_container_width=True)
                    else:
                        st.button("💬 Enviar p/ WhatsApp", disabled=True, help="Falta Telefone no cadastro do cliente.", use_container_width=True)
                
                with c_contrato:
                    if st.button("📝 Gerar Contrato", type="primary", use_container_width=True):
                        st.info("🚀 Módulo de Contratos em desenvolvimento! (Aguardando o arquivo base)")

            else: st.info("Adicione itens no carrinho para gerar o parcelamento.")
        except Exception as e: st.error(f"❌ Erro na conexão: {e}")
