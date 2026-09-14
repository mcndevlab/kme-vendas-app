import streamlit as st
import pandas as pd
import datetime
import re
import os
import urllib.parse
import requests
import pydeck as pdk
from streamlit_geolocation import streamlit_geolocation
from geopy.geocoders import Nominatim

from modulos.db import (carregar_produtos, carregar_valores_sensores, carregar_valores_ponto_mo,
                        carregar_regras_validacao, carregar_configuracoes, carregar_usuarios,
                        carregar_todos_leads, carregar_todas_propostas, carregar_meus_leads,
                        carregar_minhas_propostas, salvar_lead, atualizar_lead, salvar_proposta,
                        atualizar_proposta_modificada, efetivar_renovacao, efetivar_atualizacao_temperatura,
                        efetivar_perda, efetivar_aprovacao, 
                        carregar_tabela_configuracoes, atualizar_valor_configuracao,
                        adicionar_usuario_banco, atualizar_usuario_banco)

from modulos.utils import (padronizar_nome, padronizar_telefone, extrair_tabela_crm_itens,
                           validar_inconsistencias_carrinho, calcular_novos_valores_proposta,
                           obter_detalhes_split, obter_emails_gestores, enviar_email_aprovacao, 
                           converter_para_numero, gerar_html_proposta, enviar_email_proposta_cliente,
                           gerar_documento_contrato, enviar_para_zapsign, validar_cpf, validar_cnpj, formatar_documento,
                           converter_para_pdf_na_nuvem)

def carregar_proposta_para_simulador(idx_planilha, dados_prop, df_produtos, df_leads):
    novo_carrinho = []
    for item in str(dados_prop.get('itens_orcamento', '')).split(";"):
        if "x " in item:
            try:
                qtd = int(item.strip().split("x ", 1)[0])
                nome_item = item.strip().split("x ", 1)[1].split("[Cód:")[0].strip() if "[Cód:" in item else item.strip().split("x ", 1)[1].strip()
            except: qtd, nome_item = 0, ""
            prod_info = df_produtos[df_produtos['nome_item'].astype(str).str.strip() == nome_item]
            if not prod_info.empty:
                prod = prod_info.iloc[0]
                novo_carrinho.append({"nome": str(prod['nome_item']), "codigo": str(prod.get('codigo_kme', '')), "tipo_sensor": str(prod.get('tipo_sensor', '')), "categoria": str(prod.get('categoria_receita', '')), "grupo": str(prod.get('grupo_itens', '')), "quantidade": qtd, "preco_venda": converter_para_numero(prod.get('preco_venda', 0)), "preco_mrr": converter_para_numero(prod.get('preco_loc_36', 0))})
                
    st.session_state["desc_prod"] = converter_para_numero(dados_prop.get('desc_prod', '0')) or None
    st.session_state["desc_alarme"] = converter_para_numero(dados_prop.get('desc_alarme', '0')) or None
    st.session_state["desc_imagem"] = converter_para_numero(dados_prop.get('desc_imagem', '0')) or None
    st.session_state["nome_proposta_atual"] = str(dados_prop.get('nome_proposta', ''))
    
    st.session_state["temp_proposta_atual"] = str(dados_prop.get('temperatura', 'Selecione...'))
    st.session_state["status_proposta_atual"] = str(dados_prop.get('status_proposta', 'Selecione...'))
    st.session_state["segmento_proposta_atual"] = "Selecione..." 
    st.session_state["status_credito_deps"] = None
    st.session_state["tempo_empresa_credito"] = None
    st.session_state["situacao_cnpj"] = None
    
    nome_cliente = str(dados_prop.get('nome_cliente', '')).strip()
    lead_row = df_leads[df_leads['nome_razao'].astype(str).str.strip() == nome_cliente]
    if not lead_row.empty:
        lr = lead_row.iloc[0]
        st.session_state["lead_dados"] = {"data_cadastro": str(lr.get("data_cadastro", "")), "nome": str(lr.get("nome_razao", "")), "cpf_cnpj": str(lr.get("cpf_cnpj", "")).replace('nan', ''), "data_nascimento": str(lr.get("data_nascimento", "")).replace('nan', ''), "endereco": str(lr.get("endereco", "")).replace('nan', ''), "numero": str(lr.get("numero", "")).replace('nan', ''), "cidade": str(lr.get("cidade", "")).replace('nan', ''), "estado": str(lr.get("estado", "")).replace('nan', ''), "telefone": str(lr.get("telefone", "")).replace('nan', ''), "contato": str(lr.get("contato", "")).replace('nan', ''), "email_cliente": str(lr.get("email_cliente", "")).replace('nan', ''), "gps": str(lr.get("coordenadas_gps", "")).replace('nan', '')}
        st.session_state["editando_lead_idx"] = lead_row.index[0] + 2 
    else:
        st.session_state["lead_dados"] = {"nome": nome_cliente}
        st.session_state["editando_lead_idx"] = None
        
    st.session_state.update({"carrinho": novo_carrinho, "lead_salvo": True, "renovar_proposta_idx": None, "proposta_idx_editando": idx_planilha, "etapa_atual": "simulador"})

def aplicar_filtros_gerenciais(df_users, df_all_leads, df_all_prop, perfil, minha_unidade):
    if perfil == "Lider": df_users = df_users[df_users['unidade'].astype(str).str.strip().str.lower() == minha_unidade]
    elif perfil == "Gerente_Varejo": df_users = df_users[df_users['vertical'].astype(str).str.strip().str.lower().str.contains('varejo')]
    elif perfil == "Gerente_Condominio": df_users = df_users[df_users['vertical'].astype(str).str.strip().str.lower().str.contains('condominio')]
    
    st.write("---")
    num_cols = 4 
    if perfil == "Diretoria": num_cols = 6
    elif "Gerente" in perfil: num_cols = 5
    
    cols = st.columns(num_cols)
    idx = 0
    
    filtro_vert = "Todas"
    if perfil == "Diretoria":
        opcoes_vert = ["Todas"] + sorted(df_users['vertical'].dropna().unique().tolist())
        filtro_vert = cols[idx].selectbox("Vertical", opcoes_vert)
        if filtro_vert != "Todas": df_users = df_users[df_users['vertical'] == filtro_vert]
        idx += 1
            
    filtro_unid = "Todas"
    if perfil in ["Diretoria", "Gerente_Varejo", "Gerente_Condominio"]:
        opcoes_unid = ["Todas"] + sorted(df_users['unidade'].dropna().unique().tolist())
        filtro_unid = cols[idx].selectbox("Unidade", opcoes_unid)
        if filtro_unid != "Todas": df_users = df_users[df_users['unidade'] == filtro_unid]
        idx += 1
            
    opcoes_vend = ["Todos"] + sorted(df_users['nome'].dropna().unique().tolist())
    filtro_vend = cols[idx].selectbox("Vendedor", opcoes_vend)
    if filtro_vend != "Todos": df_users = df_users[df_users['nome'] == filtro_vend]
    idx += 1
    
    valid_em = df_users['email_c'].tolist()
    df_eq_l = df_all_leads[df_all_leads['email_vendedor'].isin(valid_em)] if not df_all_leads.empty else pd.DataFrame()
    df_eq_p = df_all_prop[df_all_prop['email_vendedor'].isin(valid_em)] if not df_all_prop.empty else pd.DataFrame()
    
    if not df_eq_l.empty:
        df_eq_l['data_fmt'] = pd.to_datetime(df_eq_l['data_cadastro'].astype(str).str.split(" ").str[0], format='%d/%m/%Y', errors='coerce')
        df_eq_l['mes_ano'] = df_eq_l['data_fmt'].dt.strftime('%m/%Y').fillna('Sem Data')
        df_eq_l['dia_str'] = df_eq_l['data_fmt'].dt.strftime('%d/%m/%Y').fillna('Sem Data')
    if not df_eq_p.empty:
        df_eq_p['data_fmt'] = pd.to_datetime(df_eq_p['data_proposta'].astype(str).str.split(" ").str[0], format='%d/%m/%Y', errors='coerce')
        df_eq_p['mes_ano'] = df_eq_p['data_fmt'].dt.strftime('%m/%Y').fillna('Sem Data')
        df_eq_p['dia_str'] = df_eq_p['data_fmt'].dt.strftime('%d/%m/%Y').fillna('Sem Data')
        
    meses_d = []
    if not df_eq_l.empty: meses_d.extend(df_eq_l['mes_ano'].dropna().unique().tolist())
    if not df_eq_p.empty: meses_d.extend(df_eq_p['mes_ano'].dropna().unique().tolist())
    meses_d = sorted(list(set(meses_d)))
    if 'Sem Data' in meses_d: meses_d.remove('Sem Data')
    meses_d = ["Todos"] + meses_d
    
    filtro_mes = cols[idx].selectbox("Mês", meses_d)
    if filtro_mes != "Todos":
        if not df_eq_l.empty: df_eq_l = df_eq_l[df_eq_l['mes_ano'] == filtro_mes]
        if not df_eq_p.empty: df_eq_p = df_eq_p[df_eq_p['mes_ano'] == filtro_mes]
    idx += 1
        
    dias_d = []
    if not df_eq_l.empty: dias_d.extend(df_eq_l['dia_str'].dropna().unique().tolist())
    if not df_eq_p.empty: dias_d.extend(df_eq_p['dia_str'].dropna().unique().tolist())
    dias_d = sorted(list(set(dias_d)))
    if 'Sem Data' in dias_d: dias_d.remove('Sem Data')
    dias_d = ["Todos"] + dias_d
    
    filtro_dia = cols[idx].selectbox("Dia", dias_d)
    if filtro_dia != "Todos":
        if not df_eq_l.empty: df_eq_l = df_eq_l[df_eq_l['dia_str'] == filtro_dia]
        if not df_eq_p.empty: df_eq_p = df_eq_p[df_eq_p['dia_str'] == filtro_dia]
    idx += 1
    
    temp_d = []
    if not df_eq_p.empty and 'temperatura' in df_eq_p.columns:
        temp_d.extend([str(t).strip() for t in df_eq_p['temperatura'].dropna().unique().tolist() if str(t).strip() != ''])
    temp_d = sorted(list(set(temp_d)))
    temp_d = ["Todas"] + temp_d
    
    if idx < num_cols:
        filtro_temp = cols[idx].selectbox("Temp. Proposta", temp_d)
        if filtro_temp != "Todas" and not df_eq_p.empty:
            df_eq_p = df_eq_p[df_eq_p['temperatura'].astype(str).str.strip() == filtro_temp]

    mapa_v = dict(zip(df_users['email_c'], df_users['nome']))
    dicionario_filtros = {"vertical": filtro_vert, "mes": filtro_mes, "dia": filtro_dia}
    return df_eq_l, df_eq_p, mapa_v, dicionario_filtros

def tela_principal():
    cfg = carregar_configuracoes()
    vertical_user = str(st.session_state.get('vertical_usuario', '')).strip().lower()
    
    if "varejo" in vertical_user: limite_vencimento, limite_temp = int(cfg.get("venc_proposta_varejo", 10)), int(cfg.get("temp_proposta_varejo", 5))
    elif "condominio" in vertical_user: limite_vencimento, limite_temp = int(cfg.get("venc_proposta_cond", 10)), int(cfg.get("temp_proposta_cond", 5))
    elif "grandes_contas" in vertical_user or "gc" in vertical_user: limite_vencimento, limite_temp = int(cfg.get("venc_proposta_gc", 10)), int(cfg.get("temp_proposta_gc", 5))
    else: limite_vencimento, limite_temp = int(cfg.get("venc_proposta", 10)), int(cfg.get("temp_proposta", 5))

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
            status = str(row.get('status_proposta', '')).strip()
            if status in ["Perdida", "Fechada", "Aprovada"]: continue
            
            prop_renovada = str(row.get('data_proposta_renovada', '')).replace('nan', '').replace('None', '').strip()
            data_ref_prop_str = prop_renovada if prop_renovada else str(row.get('data_proposta', '')).replace('nan', '').replace('None', '').strip()
            
            temp_renovada = str(row.get('data_temperatura_renovada', '')).replace('nan', '').replace('None', '').strip()
            data_ref_temp_str = temp_renovada if temp_renovada else str(row.get('data_proposta', '')).replace('nan', '').replace('None', '').strip()
            
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
                st.markdown(f"### 💼 Cliente: {p['dados'].get('nome_cliente', '')} *(Ref: {p['dados'].get('nome_proposta', '')})*")
                
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
                                df_us['email_c'] = df_us['email'].astype(str).str.strip().str.lower()
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
                        mrr_a, setup_a = p['dados'].get('total_mrr', ''), p['dados'].get('total_setup', '')
                        pode_salvar = True
                        if mrr_n != mrr_a or setup_n != setup_a:
                            st.markdown(f"""
                            <div style="background-color: #fffbeb; border-left: 5px solid #f59e0b; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
                                <p style="margin: 0 0 8px 0; font-size: 1.05rem; color: #92400e;"><b>⚠️ ATENÇÃO: Os preços da tabela base foram atualizados!</b></p>
                                <p style="margin: 0; font-size: 0.95rem; color: #92400e;">
                                    <b>Total Serviços:</b> de <s>{str(mrr_a).strip()}</s> ➡️ <b>{str(mrr_n).strip()}</b><br>
                                    <b>Setup:</b> de <s>{str(setup_a).strip()}</s> ➡️ <b>{str(setup_n).strip()}</b>
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            if not st.checkbox("Estou ciente e avisarei o cliente.", key=f"chk_{p['idx_planilha']}"): pode_salvar = False
                        
                        c_b1, c_b2 = st.columns([3, 7])
                        if c_b1.button("Confirmar Renovação Completa", type="primary", disabled=not pode_salvar, key=f"btn_ren_{p['idx_planilha']}"):
                            if efetivar_renovacao(p['idx_planilha'], mrr_n, setup_n, nova_temp): st.toast("Renovada com sucesso!"); st.cache_data.clear(); st.rerun()
                        if c_b2.button("✏️ Modificar Proposta", key=f"btn_mod_{p['idx_planilha']}"):
                            carregar_proposta_para_simulador(p['idx_planilha'], p['dados'], df_produtos, df_leads); st.rerun()
                st.divider()
        st.stop() 

    # --- VERIFICAÇÃO SE O USUÁRIO É ADMINISTRADOR ---
    df_users_chk = carregar_usuarios()
    is_admin = False
    if not df_users_chk.empty and 'perfil_acesso' in df_users_chk.columns:
        user_info = df_users_chk[df_users_chk['email'].astype(str).str.lower().str.strip() == st.session_state['email_usuario'].lower().strip()]
        if not user_info.empty:
            perfil_acc = str(user_info.iloc[0].get('perfil_acesso', '')).strip().lower()
            if perfil_acc == 'administrador':
                is_admin = True

    with st.sidebar:
        if os.path.exists("logo.jpg"): st.image("logo.jpg", width=120)
        st.markdown("### **Khronos Sales**")
        st.write(f"👤 **{st.session_state['nome_usuario']}**")
        st.divider()
        if st.button("➕ Novo Cliente", use_container_width=True): st.session_state.update({"gatilho_limpar_tudo": True, "etapa_atual": "lead"}); st.rerun()
        if st.button("📋 Meus Clientes", use_container_width=True): st.session_state.update({"etapa_atual": "meus_leads", "proposta_idx_editando": None}); st.rerun()
        if st.button("💼 Minhas Propostas", use_container_width=True): st.session_state.update({"etapa_atual": "minhas_propostas", "proposta_idx_editando": None}); st.rerun()
            
        perfil_acesso = str(st.session_state.get('perfil_usuario', '')).strip()
        if perfil_acesso in ["Lider", "Gerente_Varejo", "Gerente_Condominio", "Diretoria", "Gerente_Unidade"]:
            st.divider()
            st.caption("🔒 **Área Gerencial**")
            if st.button("📈 Dashboard", use_container_width=True): st.session_state.update({"etapa_atual": "dashboard", "proposta_idx_editando": None}); st.rerun()
            if st.button("📊 Funil da Equipe", use_container_width=True): st.session_state.update({"etapa_atual": "funil_equipe", "proposta_idx_editando": None}); st.rerun()
            if st.button("🗺️ Localização da Equipe", use_container_width=True): st.session_state.update({"etapa_atual": "mapa_equipe", "proposta_idx_editando": None}); st.rerun()
        
        # --- MENU EXCLUSIVO PARA ADMINISTRADOR ---
        if is_admin:
            st.divider()
            st.caption("🛠️ **Administração**")
            if st.button("⚙️ Painel de Controle", use_container_width=True): 
                st.session_state.update({"etapa_atual": "painel_controle", "proposta_idx_editando": None})
                st.rerun()
                
        st.divider()
        if st.session_state["lead_dados"].get("nome"):
            st.success(f"🛒 Simulador Ativo:\n{st.session_state['lead_dados']['nome']}")
            if st.button("Ir para o Simulador", use_container_width=True): st.session_state["etapa_atual"] = "simulador"; st.rerun()
        st.divider()
        if st.button("🚪 Sair", use_container_width=True): st.session_state.clear(); st.rerun()

    if st.session_state.get("gatilho_limpar_tudo", False):
        st.session_state.update({
            "carrinho": [], "desc_prod": None, "desc_alarme": None, "desc_imagem": None, 
            "lead_dados": {}, "lead_salvo": False, "renovar_proposta_idx": None, 
            "proposta_idx_editando": None, "editando_lead_idx": None, "nome_proposta_atual": "", 
            "temp_proposta_atual": "Selecione...", "status_proposta_atual": "Selecione...", 
            "segmento_proposta_atual": "Selecione...",
            "status_credito_deps": None, "tempo_empresa_credito": None, "situacao_cnpj": None,
            "ultimo_gps_capturado": "", "item_aberto": None, "unidade_mo_selecionada": None, 
            "gatilho_limpar_tudo": False
        })
    if st.session_state.get("gatilho_limpar_carrinho", False):
        st.session_state.update({"carrinho": [], "desc_prod": None, "desc_alarme": None, "desc_imagem": None, "item_aberto": None, "gatilho_limpar_carrinho": False, "status_credito_deps": None, "tempo_empresa_credito": None, "situacao_cnpj": None})
    if st.session_state["msg_sucesso"] != "": st.success(st.session_state["msg_sucesso"]); st.session_state["msg_sucesso"] = ""

    # --- TELAS INTERNAS ---
    
    # --- NOVA TELA: PAINEL DE CONTROLE ---
    if st.session_state["etapa_atual"] == "painel_controle":
        st.header("⚙️ Painel de Controle")
        st.caption("Área exclusiva para Gestão Técnica e Configurações do Sistema.")
        
        aba_config, aba_usuarios = st.tabs(["🛠️ Configurações Gerais", "👥 Gestão de Usuários"])
        
        with aba_config:
            st.markdown("#### Tabela de Configurações")
            st.write("Altere os valores dos parâmetros abaixo e clique no botão verde no fim da página para atualizar o banco de dados em tempo real.")
            
            df_configs = carregar_tabela_configuracoes()
            
            if df_configs.empty:
                st.info("Nenhuma configuração encontrada na tabela 'configuracoes'.")
            else:
                col_desc = 'descricao' if 'descricao' in df_configs.columns else ('descrição' if 'descrição' in df_configs.columns else None)
                
                with st.form("form_configs"):
                    novos_valores = {}
                    
                    for idx, row in df_configs.iterrows():
                        param = str(row.get('parametro', ''))
                        val = str(row.get('valor', ''))
                        desc = str(row[col_desc]) if col_desc and not pd.isna(row.get(col_desc)) else ""
                        
                        st.markdown(f"**{param}**")
                        if desc and desc.lower() != 'nan':
                            st.caption(desc)
                        
                        novos_valores[param] = st.text_input("Valor", value=val, key=f"conf_{param}", label_visibility="collapsed")
                        st.write("---")
                        
                    col_submit, _ = st.columns([3, 7])
                    if col_submit.form_submit_button("💾 Salvar Alterações", type="primary", use_container_width=True):
                        sucesso_geral = True
                        
                        for p, v in novos_valores.items():
                            val_antigo = str(df_configs[df_configs['parametro'] == p]['valor'].values[0])
                            if v != val_antigo:
                                if not atualizar_valor_configuracao(p, v):
                                    sucesso_geral = False
                        
                        if sucesso_geral:
                            st.success("✅ Configurações atualizadas no Supabase com sucesso!")
                            st.cache_data.clear() 
                            st.rerun()
                        else:
                            st.error("⚠️ Ocorreu um erro ao atualizar algumas configurações.")

        with aba_usuarios:
            st.markdown("#### Gerenciamento da Equipe")
            df_all_users = carregar_usuarios()
            
            acao_user = st.radio("Selecione a ação desejada:", ["Adicionar Novo Usuário", "Editar Usuário Existente"], horizontal=True)
            st.write("---")
            
            if acao_user == "Adicionar Novo Usuário":
                with st.form("form_novo_user"):
                    c1, c2 = st.columns(2)
                    novo_nome = c1.text_input("Nome Completo *")
                    novo_email = c2.text_input("E-mail (Login) *")
                    
                    c3, c4 = st.columns(2)
                    nova_senha = c3.text_input("Senha *")
                    novo_status = c4.selectbox("Status no Sistema", ["Ativo", "Inativo"])
                    
                    c5, c6, c7 = st.columns(3)
                    novo_perfil = c5.selectbox("Cargo/Perfil", ["Vendedor", "Lider", "Gerente_Unidade", "Gerente_Varejo", "Gerente_Condominio", "Diretoria"])
                    nova_unidade = c6.text_input("Unidade Base (Ex: Matriz)")
                    nova_vertical = c7.text_input("Vertical (Ex: Varejo, Condominio)")
                    
                    c8, c9 = st.columns(2)
                    novo_login_crm = c8.text_input("Login do CRM")
                    novo_perfil_acesso = c9.selectbox("Perfil de Acesso (App)", ["padrao", "administrador"])
                    
                    if st.form_submit_button("➕ Salvar Novo Usuário", type="primary"):
                        if not novo_nome or not novo_email or not nova_senha:
                            st.error("⚠️ Nome, E-mail e Senha são campos obrigatórios!")
                        else:
                            dados_novo = {
                                "nome": novo_nome, 
                                "email": str(novo_email).lower().strip(), 
                                "senha": nova_senha, 
                                "perfil": novo_perfil, 
                                "unidade": nova_unidade,
                                "vertical": nova_vertical, 
                                "status": novo_status, 
                                "login_crm": novo_login_crm,
                                "perfil_acesso": novo_perfil_acesso
                            }
                            suc, msg = adicionar_usuario_banco(dados_novo)
                            if suc:
                                st.success(msg)
                                st.cache_data.clear()
                                st.rerun()
                            else:
                                st.error(msg)
                                
            else: 
                if df_all_users.empty:
                    st.info("Nenhum usuário localizado no banco de dados.")
                else:
                    opcoes_exibicao = []
                    mapa_usuarios = {}
                    
                    for idx, u in df_all_users.iterrows():
                        nome_exib = str(u.get('nome', 'Sem Nome')).strip()
                        email_exib = str(u.get('email', '')).strip()
                        
                        if email_exib.lower() == 'nan' or not email_exib:
                            email_exib = "Sem Email cadastrado"
                            
                        txt_opcao = f"{nome_exib} ({email_exib}) - ID: {u.get('id', idx)}"
                        opcoes_exibicao.append(txt_opcao)
                        mapa_usuarios[txt_opcao] = idx
                            
                    opcoes_exibicao = sorted(opcoes_exibicao)
                    
                    user_selecionado_txt = st.selectbox("Selecione o usuário para editar:", ["Selecione..."] + opcoes_exibicao)
                    
                    if user_selecionado_txt != "Selecione...":
                        idx_real = mapa_usuarios[user_selecionado_txt]
                        user_data = df_all_users.loc[idx_real]
                        
                        id_usuario = user_data.get('id')
                        email_original = str(user_data.get('email', '')).strip()
                        if email_original.lower() == 'nan': email_original = ""
                        
                        with st.form("form_edit_user"):
                            c1, c2 = st.columns(2)
                            ed_nome = c1.text_input("Nome Completo *", value=str(user_data.get('nome', '')).replace('nan',''))
                            ed_email = c2.text_input("E-mail (Login) *", value=email_original, disabled=True, help="Para trocar o e-mail de login, inative este usuário e cadastre um novo.")
                            
                            c3, c4 = st.columns(2)
                            c3.text_input("Senha", value="••••••••", disabled=True,help="Gerenciada pelo Supabase Auth. Use o botão de reset abaixo.")
                            
                            opcoes_status = ["Ativo", "Inativo"]
                            idx_status = opcoes_status.index(user_data.get('status', 'Ativo')) if user_data.get('status', 'Ativo') in opcoes_status else 0
                            ed_status = c4.selectbox("Status no Sistema", opcoes_status, index=idx_status)
                            
                            c5, c6, c7 = st.columns(3)
                            opcoes_perfil = ["Vendedor", "Lider", "Gerente_Unidade", "Gerente_Varejo", "Gerente_Condominio", "Diretoria"]
                            idx_perfil = opcoes_perfil.index(user_data.get('perfil', 'Vendedor')) if user_data.get('perfil', 'Vendedor') in opcoes_perfil else 0
                            ed_perfil = c5.selectbox("Cargo/Perfil", opcoes_perfil, index=idx_perfil)
                            
                            ed_unidade = c6.text_input("Unidade Base", value=str(user_data.get('unidade', '')).replace('nan',''))
                            ed_vertical = c7.text_input("Vertical", value=str(user_data.get('vertical', '')).replace('nan','')) 
                            
                            c8, c9 = st.columns(2)
                            ed_login_crm = c8.text_input("Login do CRM", value=str(user_data.get('login_crm', '')).replace('nan',''))
                            
                            opcoes_acc = ["padrao", "administrador"]
                            curr_acc = str(user_data.get('perfil_acesso', 'padrao')).lower().strip()
                            idx_acc = opcoes_acc.index(curr_acc) if curr_acc in opcoes_acc else 0
                            ed_perfil_acesso = c9.selectbox("Perfil de Acesso (App)", opcoes_acc, index=idx_acc)
                            
                            if st.form_submit_button("💾 Salvar Alterações", type="primary"):
                                if not ed_nome or not ed_email:
                                    st.error("⚠️ Nome, E-mail e Senha são campos obrigatórios!")
                                else:
                                    dados_update = {
                                        "nome": ed_nome, 
                                        "email": str(ed_email).lower().strip(), 
                                        "perfil": ed_perfil, 
                                        "unidade": ed_unidade,
                                        "vertical": ed_vertical, 
                                        "status": ed_status, 
                                        "login_crm": ed_login_crm,
                                        "perfil_acesso": ed_perfil_acesso
                                    }
                                    suc, msg = atualizar_usuario_banco(id_usuario, email_original, dados_update)
                                    if suc:
                                        st.success(msg)
                                        st.cache_data.clear()
                                        st.rerun()
                                    else:
                                        st.error(msg)
                        st.write("")
                        if st.button("🔑 Enviar senha temporária", key=f"reset_{id_usuario}"):
                          from modulos.auth import resetar_senha_como_admin
                          ok, msg = resetar_senha_como_admin(email_original)
                          (st.success if ok else st.error)(msg)


    elif st.session_state["etapa_atual"] == "dashboard":
        st.header("📈 Dashboard Gerencial")
        df_users = carregar_usuarios()
        df_users['email_c'] = df_users['email'].astype(str).str.strip().str.lower()
        perfil, minha_unidade = st.session_state['perfil_usuario'], st.session_state['unidade_usuario'].lower()
        
        df_eq_leads, df_eq_prop, mapa_vendedores, sel_filtros = aplicar_filtros_gerenciais(df_users, carregar_todos_leads(), carregar_todas_propostas(), perfil, minha_unidade)
        
        total_leads = len(df_eq_leads)
        total_propostas = len(df_eq_prop)
        df_aprovadas = df_eq_prop[df_eq_prop['status_proposta'].astype(str).str.strip() == 'Aprovada'].copy() if not df_eq_prop.empty else pd.DataFrame()
        total_aprovadas = len(df_aprovadas)
        
        conv_lead = (total_aprovadas / total_leads * 100) if total_leads > 0 else 0.0
        conv_prop = (total_aprovadas / total_propostas * 100) if total_propostas > 0 else 0.0
        
        tm_mrr, tm_setup, realizado_mrr, realizado_setup = 0.0, 0.0, 0.0, 0.0
        if not df_aprovadas.empty:
            df_aprovadas['val_mrr'] = df_aprovadas['total_mrr'].apply(converter_para_numero)
            df_aprovadas['val_setup'] = df_aprovadas['total_setup'].apply(converter_para_numero)
            
            tm_mrr = df_aprovadas['val_mrr'].mean()
            tm_setup = df_aprovadas['val_setup'].mean()
            realizado_mrr = df_aprovadas['val_mrr'].sum()
            realizado_setup = df_aprovadas['val_setup'].sum()

        st.markdown("#### 🎯 Conversão e Ticket Médio")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Conversão (Lead ➡️ Venda)", f"{conv_lead:.1f}%", f"{total_aprovadas} de {total_leads} leads")
        c2.metric("Conversão (Proposta ➡️ Venda)", f"{conv_prop:.1f}%", f"{total_aprovadas} de {total_propostas} props")
        c3.metric("Ticket Médio (Mensalidade)", f"R$ {tm_mrr:,.2f}".replace(',','_').replace('.',',').replace('_','.'))
        c4.metric("Ticket Médio (Setup)", f"R$ {tm_setup:,.2f}".replace(',','_').replace('.',',').replace('_','.'))

        st.divider()

        dia_ref = datetime.datetime.now().day
        if sel_filtros["dia"] != "Todos":
            try: dia_ref = int(sel_filtros["dia"].split("/")[0])
            except: pass
        elif sel_filtros["mes"] != "Todos":
            try:
                mes_sel, ano_sel = sel_filtros["mes"].split("/")
                hoje = datetime.datetime.now()
                if int(mes_sel) != hoje.month or int(ano_sel) != hoje.year:
                    dia_ref = 30 
            except: pass

        meta_total_mrr, meta_total_setup = 0.0, 0.0
        if mapa_vendedores:
            df_vendedores_filtrados = df_users[df_users['email_c'].isin(mapa_vendedores.keys())]
            for _, u in df_vendedores_filtrados.iterrows():
                vert = str(u.get('vertical', '')).lower()
                if 'varejo' in vert:
                    meta_total_mrr += float(cfg.get("Meta_Varejo_Receita_Vendedor", 1250))
                    meta_total_setup += float(cfg.get("Meta_Varejo_Produtos_Vendedor", 5000))
                elif 'condominio' in vert:
                    meta_total_mrr += float(cfg.get("Meta_Condominio_Receita_Vendedor", 2500))
                    meta_total_setup += float(cfg.get("Meta_Condominio_Produtos_Vendedor", 10000))
                else: 
                    meta_total_mrr += float(cfg.get("Meta_Varejo_Receita_Vendedor", 1250))
                    meta_total_setup += float(cfg.get("Meta_Varejo_Produtos_Vendedor", 5000))
        
        meta_prop_mrr = (meta_total_mrr / 30) * dia_ref
        meta_prop_setup = (meta_total_setup / 30) * dia_ref

        st.markdown("#### 🚀 Desempenho Diário - Meta Acumulada x Realizado")
        c_m1, c_m2 = st.columns(2)
        
        with c_m1:
            perc_mrr = (realizado_mrr / meta_prop_mrr * 100) if meta_prop_mrr > 0 else 0.0
            st.markdown(f"**Receita Recorrente (Mensalidade) - Dia {dia_ref}/30**")
            
            meta_mrr_fmt = f"R$ {meta_prop_mrr:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
            realizado_mrr_fmt = f"R$ {realizado_mrr:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
            
            st.markdown(f"<p style='margin-bottom: 5px; font-size: 0.95rem; color: #475569;'>Meta Alvo Diária: {meta_mrr_fmt} | Realizado: <b style='color: #0f172a;'>{realizado_mrr_fmt}</b></p>", unsafe_allow_html=True)
            st.progress(min(perc_mrr / 100, 1.0))
            st.markdown(f"<p style='text-align:right; margin-top:-10px; font-size:0.85rem; color:{'#10b981' if perc_mrr>=100 else '#f59e0b'};'><b>{perc_mrr:.1f}% Atingido</b></p>", unsafe_allow_html=True)
            
        with c_m2:
            perc_setup = (realizado_setup / meta_prop_setup * 100) if meta_prop_setup > 0 else 0.0
            st.markdown(f"**Receita Imediata (Equip. + MO) - Dia {dia_ref}/30**")
            
            meta_setup_fmt = f"R$ {meta_prop_setup:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
            realizado_setup_fmt = f"R$ {realizado_setup:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
            
            st.markdown(f"<p style='margin-bottom: 5px; font-size: 0.95rem; color: #475569;'>Meta Alvo Diária: {meta_setup_fmt} | Realizado: <b style='color: #0f172a;'>{realizado_setup_fmt}</b></p>", unsafe_allow_html=True)
            st.progress(min(perc_setup / 100, 1.0))
            st.markdown(f"<p style='text-align:right; margin-top:-10px; font-size:0.85rem; color:{'#10b981' if perc_setup>=100 else '#f59e0b'};'><b>{perc_setup:.1f}% Atingido</b></p>", unsafe_allow_html=True)
            
        st.divider()
        cg1, cg2, cg3 = st.columns(3)
        with cg1:
            st.markdown("**Status das Negociações**")
            if not df_eq_prop.empty: st.bar_chart(df_eq_prop['status_proposta'].value_counts())
            else: st.info("Sem dados")
        with cg2:
            st.markdown("**Volume do Pipeline**")
            dados_funil = pd.DataFrame({"Etapa": ["1. Adicionados", "2. Propostas", "3. Fechadas"], "Quantidade": [total_leads, total_propostas, total_aprovadas]}).set_index("Etapa")
            st.bar_chart(dados_funil)
        with cg3:
            st.markdown("**Motivos de Perdas**")
            col_motivo = None
            if not df_eq_prop.empty:
                for c in df_eq_prop.columns:
                    if 'motivo' in c.lower():
                        col_motivo = c
                        break
                if col_motivo:
                    df_perdidas = df_eq_prop[df_eq_prop['status_proposta'].astype(str).str.strip() == 'Perdida']
                    if not df_perdidas.empty:
                        m_counts = df_perdidas[col_motivo].replace('', pd.NA).dropna().value_counts()
                        if not m_counts.empty:
                            st.bar_chart(m_counts)
                        else:
                            st.info("Sem motivos detalhados.")
                    else:
                        st.info("Nenhuma perda registrada.")
                else:
                    st.info("Coluna de motivo ausente.")
            else:
                st.info("Sem dados.")
            
        # --- RANKING DE VENDAS ---
        st.divider()
        st.markdown("#### 🏆 Ranking de Vendas da Equipe (Aprovadas)")
        
        if not df_aprovadas.empty:
            df_ranking = df_aprovadas.groupby('email_vendedor').agg(
                Vendedor=('nome_usuario', 'first'),
                Receita_Mensalidade=('val_mrr', 'sum'),
                Receita_Setup=('val_setup', 'sum')
            ).reset_index()

            mapa_unidades = dict(zip(df_users['email_c'], df_users['unidade']))
            df_ranking['Unidade'] = df_ranking['email_vendedor'].apply(lambda e: str(mapa_unidades.get(e, '-')))
            
            mapa_meta_ind = {}
            for _, u in df_users.iterrows():
                email = str(u.get('email_c', '')).strip()
                vert = str(u.get('vertical', '')).lower()
                if 'varejo' in vert: m = float(cfg.get("Meta_Varejo_Receita_Vendedor", 1250))
                elif 'condominio' in vert: m = float(cfg.get("Meta_Condominio_Receita_Vendedor", 2500))
                else: m = float(cfg.get("Meta_Varejo_Receita_Vendedor", 1250))
                mapa_meta_ind[email] = (m / 30) * dia_ref

            df_ranking['Meta_Prop'] = df_ranking['email_vendedor'].map(mapa_meta_ind).fillna(1.0)
            df_ranking['Perc_Ating'] = (df_ranking['Receita_Mensalidade'] / df_ranking['Meta_Prop']) * 100

            c_vazio_rank, c_sort_rank = st.columns([6, 4])
            with c_sort_rank:
                sort_rank_opt = st.selectbox("Ordenar Ranking por:", [
                    "Mensalidade (Maior Valor)", "Mensalidade (Menor Valor)",
                    "Setup (Maior Valor)", "Setup (Menor Valor)",
                    "% Atingimento Mensalidade (Maior p/ Menor)",
                    "% Atingimento Mensalidade (Menor p/ Maior)"
                ], label_visibility="collapsed")
                
            if sort_rank_opt == "Mensalidade (Maior Valor)": df_ranking = df_ranking.sort_values(by='Receita_Mensalidade', ascending=False)
            elif sort_rank_opt == "Mensalidade (Menor Valor)": df_ranking = df_ranking.sort_values(by='Receita_Mensalidade', ascending=True)
            elif sort_rank_opt == "Setup (Maior Valor)": df_ranking = df_ranking.sort_values(by='Receita_Setup', ascending=False)
            elif sort_rank_opt == "Setup (Menor Valor)": df_ranking = df_ranking.sort_values(by='Receita_Setup', ascending=True)
            elif sort_rank_opt == "% Atingimento Mensalidade (Maior p/ Menor)": df_ranking = df_ranking.sort_values(by='Perc_Ating', ascending=False)
            elif sort_rank_opt == "% Atingimento Mensalidade (Menor p/ Maior)": df_ranking = df_ranking.sort_values(by='Perc_Ating', ascending=True)

            df_ranking['Receita Mensalidade'] = df_ranking['Receita_Mensalidade'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."))
            df_ranking['Receita Setup'] = df_ranking['Receita_Setup'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."))
            df_ranking['% Atingimento (Mensalidade x Meta)'] = df_ranking['Perc_Ating'].apply(lambda x: f"{x:.1f}%")
            
            df_exibicao = df_ranking[['Vendedor', 'Unidade', 'Receita Mensalidade', 'Receita Setup', '% Atingimento (Mensalidade x Meta)']].reset_index(drop=True)
            df_exibicao.index = df_exibicao.index + 1 
            
            st.dataframe(df_exibicao, use_container_width=True)
        else:
            st.info("Nenhuma venda fechada no período selecionado para gerar o ranking.")

        # --- SINAL DE VIDA DA EQUIPE (INATIVIDADE) ---
        st.divider()
        st.markdown("#### 📡 Monitor de Atividade da Equipe")
        st.caption("Visão em tempo real baseada no último clique de cada consultor da sua base filtrada (Horário Comercial).")
        
        df_equipe_vida = df_users[df_users['email_c'].isin(mapa_vendedores.keys())].copy()
        
        if not df_equipe_vida.empty:
            dados_vida = []
            fuso_br = datetime.timezone(datetime.timedelta(hours=-3))
            agora_dt = datetime.datetime.now(fuso_br)
            
            for _, u in df_equipe_vida.iterrows():
                nome_u = str(u.get('nome', 'Desconhecido'))
                unidade_u = str(u.get('unidade', '-'))
                ultimo_acesso_str = str(u.get('ultimo_acesso', '')).strip()
                
                status_vida = "⚪ Nunca acessou"
                
                if ultimo_acesso_str and ultimo_acesso_str.lower() != 'nan':
                    try:
                        dt_acesso = datetime.datetime.strptime(ultimo_acesso_str, "%d/%m/%Y %H:%M:%S")
                        dt_acesso = dt_acesso.replace(tzinfo=fuso_br)
                        
                        diff_horas = (agora_dt - dt_acesso).total_seconds() / 3600
                        
                        if diff_horas > 4:
                            status_vida = f"🔴 Inativo há {int(diff_horas)}h"
                        else:
                            if diff_horas < 1:
                                status_vida = "🟢 Ativo agora"
                            else:
                                status_vida = f"🟡 Inativo há {int(diff_horas)}h"
                    except:
                        status_vida = "⚪ Data inválida"
                        
                dados_vida.append({
                    "Consultor": nome_u,
                    "Unidade": unidade_u,
                    "Último Acesso Registrado": ultimo_acesso_str if ultimo_acesso_str and ultimo_acesso_str.lower() != 'nan' else "-",
                    "Status em Tempo Real": status_vida
                })
                
            df_vida = pd.DataFrame(dados_vida)
            st.dataframe(df_vida, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum consultor encontrado para os filtros atuais.")


    elif st.session_state["etapa_atual"] == "mapa_equipe":
        st.header("🗺️ Localização da Equipe")
        df_users = carregar_usuarios()
        df_users['email_c'] = df_users['email'].astype(str).str.strip().str.lower()
        perfil, minha_unidade = st.session_state['perfil_usuario'], st.session_state['unidade_usuario'].lower()
        
        df_eq_l, _, _, _ = aplicar_filtros_gerenciais(df_users, carregar_todos_leads(), carregar_todas_propostas(), perfil, minha_unidade)
        
        st.write("---")
        df_mapa = df_eq_l.copy()
        if not df_mapa.empty and 'coordenadas_gps' in df_mapa.columns:
            df_mapa['lat'] = pd.to_numeric(df_mapa['coordenadas_gps'].astype(str).str.split(',').str[0], errors='coerce')
            df_mapa['lon'] = pd.to_numeric(df_mapa['coordenadas_gps'].astype(str).str.split(',').str[1], errors='coerce')
            df_mapa = df_mapa.dropna(subset=['lat', 'lon'])
            
            if not df_mapa.empty:
                df_mapa['nome_exibicao'] = df_mapa['nome_razao'].astype(str).fillna('Cliente Desconhecido')
                df_agrupado = df_mapa.groupby(['lat', 'lon']).agg(
                    Qtd=('nome_exibicao', 'count'),
                    Nomes=('nome_exibicao', lambda x: ' | '.join(list(x)))
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
        df_users['email_c'] = df_users['email'].astype(str).str.strip().str.lower()
        perfil, minha_unidade = st.session_state['perfil_usuario'], st.session_state['unidade_usuario'].lower()
        
        df_eq_leads, df_eq_prop, mapa_vendedores, _ = aplicar_filtros_gerenciais(df_users, carregar_todos_leads(), carregar_todas_propostas(), perfil, minha_unidade)
        
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
                    nome = str(row.get('nome_razao', 'Não Informado')).strip()
                    telefone, data_cad = str(row.get('telefone', '-')).strip(), str(row.get('data_cadastro', '-')).split(" ")[0]
                    vendedor = str(mapa_vendedores.get(str(row.get('email_vendedor', '')), "Desconhecido"))
                    
                    status_lead = "🔵 Lead"
                    if not df_eq_prop.empty and 'nome_cliente' in df_eq_prop.columns:
                        prop_cliente = df_eq_prop[df_eq_prop['nome_cliente'].astype(str).str.strip() == nome]
                        if not prop_cliente.empty:
                            status_str = str(prop_cliente.iloc[-1].get('status_proposta', '')).strip()
                            status_lead = "🏆 Aprovada" if status_str == "Aprovada" else ("🔴 Perdida" if status_str == "Perdida" else "🟢 Proposta")
                    
                    c1, c2, c3, c4, c5 = st.columns([2, 4, 2, 2, 2])
                    with c1: st.write(vendedor[:18] + ("..." if len(vendedor) > 18 else ""))
                    with c2: 
                        with st.expander(f"👤 {nome[:25]}{'...' if len(nome) > 25 else ''}"):
                            st.markdown(f"**Endereço:** {row.get('endereco', '')}, {row.get('numero', '')} - {row.get('cidade', '')}<br>**Contato:** {row.get('contato', '')} | **E-mail:** {row.get('email_cliente', '')}", unsafe_allow_html=True)
                    with c3: st.write(telefone)
                    with c4: st.write(data_cad)
                    with c5: st.write(status_lead)

        with aba_prop:
            if df_eq_prop.empty: st.info("Nenhuma proposta encontrada para esta seleção.")
            else:
                df_eq_prop = df_eq_prop.copy()
                
                df_eq_prop['Data_Sort'] = pd.to_datetime(df_eq_prop['data_proposta'].astype(str).str.split(" ").str[0], format='%d/%m/%Y', errors='coerce')
                
                def converter_moeda_para_sort(valor):
                    try:
                        v = str(valor).replace('R$', '').strip()
                        v = v.replace('.', '').replace(',', '.')
                        return float(v)
                    except: return 0.0
                df_eq_prop['Servicos_Sort'] = df_eq_prop['total_mrr'].apply(converter_moeda_para_sort)
                
                temp_map = {"Quente": 3, "Morno": 2, "Frio": 1}
                df_eq_prop['Temp_Sort'] = df_eq_prop['temperatura'].astype(str).apply(lambda x: temp_map.get(x.split(" ")[0], 0))

                c_vazio, c_sort = st.columns([6, 4])
                with c_sort:
                    sort_option = st.selectbox("Ordenar por:", [
                        "Data (Mais recentes)", "Data (Mais antigas)",
                        "Temperatura (Quente > Frio)", "Temperatura (Frio > Quente)",
                        "Serviços (Maior Valor)", "Serviços (Menor Valor)"
                    ], label_visibility="collapsed")
                
                if sort_option == "Data (Mais recentes)":
                    df_eq_prop = df_eq_prop.sort_values(by='Data_Sort', ascending=False)
                elif sort_option == "Data (Mais antigas)":
                    df_eq_prop = df_eq_prop.sort_values(by='Data_Sort', ascending=True)
                elif sort_option == "Temperatura (Quente > Frio)":
                    df_eq_prop = df_eq_prop.sort_values(by=['Temp_Sort', 'Data_Sort'], ascending=[False, False])
                elif sort_option == "Temperatura (Frio > Quente)":
                    df_eq_prop = df_eq_prop.sort_values(by=['Temp_Sort', 'Data_Sort'], ascending=[True, False])
                elif sort_option == "Serviços (Maior Valor)":
                    df_eq_prop = df_eq_prop.sort_values(by='Servicos_Sort', ascending=False)
                elif sort_option == "Serviços (Menor Valor)":
                    df_eq_prop = df_eq_prop.sort_values(by='Servicos_Sort', ascending=True)

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
                    data_p = str(row.get('data_proposta', '')).split(" ")[0]
                    vendedor = str(mapa_vendedores.get(str(row.get('email_vendedor', '')), "Desconhecido"))
                    cliente = str(row.get('nome_cliente', ''))
                    nome_prop = str(row.get('nome_proposta', 'Principal'))
                    status = str(row.get('status_proposta', 'Em Negociação')).strip() or "Em Negociação"
                    temperatura = str(row.get('temperatura', 'Morno 🌤️')).split(" ")[0]
                    mrr, setup = str(row.get('total_mrr', '')), str(row.get('total_setup', ''))
                    
                    prop_renovada = str(row.get('data_proposta_renovada', '')).replace('nan', '').replace('None', '').strip()
                    data_ref_prop_str = prop_renovada if prop_renovada else str(row.get('data_proposta', '')).replace('nan', '').replace('None', '').strip()
                    
                    temp_renovada = str(row.get('data_temperatura_renovada', '')).replace('nan', '').replace('None', '').strip()
                    data_ref_temp_str = temp_renovada if temp_renovada else str(row.get('data_proposta', '')).replace('nan', '').replace('None', '').strip()
                    
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
                            itens_crm = extrair_tabela_crm_itens(row.get('itens_orcamento', ''))
                            if itens_crm: st.dataframe(itens_crm, use_container_width=True, hide_index=True)
                            else: st.info("Sem detalhes avançados.")
                    with c_np: st.write(nome_prop[:15] + ("..." if len(nome_prop) > 15 else ""))
                    with c3: st.write(f"{cor_status} {status}")
                    with c_temp: st.write(temperatura)
                    with c4: st.write(tempo_faltante)
                    with c5: st.write(mrr)
                    with c6: st.write(setup)

    elif st.session_state["etapa_atual"] == "minhas_propostas":
        st.header("💼 Minhas Propostas")
        
        c_tit, c_modo = st.columns([7, 3])
        with c_modo: modo_prop = st.radio("Modo de Exibição:", ["📱 Cartões (Celular)", "🖥️ Tabela Analítica"], key="modo_visao_propostas", horizontal=True)

        if st.session_state.get("renovar_proposta_idx"):
            idx_planilha = st.session_state["renovar_proposta_idx"]
            dados_prop = st.session_state["renovar_proposta_dados"]
            
            st.info(f"🎯 **Gerenciar Proposta:** {dados_prop.get('nome_cliente')} *(Ref: {dados_prop.get('nome_proposta', '')})*")
            
            c1, c2 = st.columns(2)
            acao = c1.selectbox("O que aconteceu com esta negociação?", ["Selecione...", "Atualizar Temperatura", "Renovar Proposta e Temperatura", "Aprovação da Proposta", "Perda na negociação"], key="acao_prop_manual")
            
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
                            df_us['email_c'] = df_us['email'].astype(str).str.strip().str.lower()
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
                    mrr_a, setup_a = dados_prop.get('total_mrr', ''), dados_prop.get('total_setup', '')
                    pode_renovar = True
                    
                    if mrr_n != mrr_a or setup_n != setup_a:
                        st.markdown(f"""
                        <div style="background-color: #fffbeb; border-left: 5px solid #f59e0b; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
                            <p style="margin: 0 0 8px 0; font-size: 1.05rem; color: #92400e;"><b>⚠️ ATENÇÃO: Os preços da tabela base foram atualizados!</b></p>
                            <p style="margin: 0; font-size: 0.95rem; color: #92400e;">
                                <b>Total Serviços:</b> de <s>{str(mrr_a).strip()}</s> ➡️ <b>{str(mrr_n).strip()}</b><br>
                                <b>Setup:</b> de <s>{str(setup_a).strip()}</s> ➡️ <b>{str(setup_n).strip()}</b>
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if not st.checkbox("Estou ciente e avisarei o cliente.", key="chk_manual"): pode_renovar = False
                    else: st.success("✅ Os valores continuam os mesmos da tabela atual.")
                        
                    if st.button("Confirmar Renovação Completa", type="primary", disabled=not pode_renovar):
                        if efetivar_renovacao(idx_planilha, mrr_n, setup_n, nova_temp):
                            st.session_state["msg_sucesso"] = "Renovada com sucesso!"
                            st.session_state["renovar_proposta_idx"] = None; st.cache_data.clear(); st.rerun()
                        
            if st.button("❌ Cancelar Operação"):
                st.session_state["renovar_proposta_idx"] = None; st.rerun()
            st.divider()

        df_prop = df_prop.iloc[::-1] if not df_prop.empty else pd.DataFrame()
        hoje = datetime.datetime.now()
        cfg = carregar_configuracoes()
        vertical_user = str(st.session_state.get('vertical_usuario', '')).strip().lower()
        if "varejo" in vertical_user: limite_vencimento, limite_temp = int(cfg.get("venc_proposta_varejo", 10)), int(cfg.get("temp_proposta_varejo", 5))
        elif "condominio" in vertical_user: limite_vencimento, limite_temp = int(cfg.get("venc_proposta_cond", 10)), int(cfg.get("temp_proposta_cond", 5))
        elif "grandes_contas" in vertical_user or "gc" in vertical_user: limite_vencimento, limite_temp = int(cfg.get("venc_proposta_gc", 10)), int(cfg.get("temp_proposta_gc", 5))
        else: limite_vencimento, limite_temp = int(cfg.get("venc_proposta", 10)), int(cfg.get("temp_proposta", 5))

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
                    data_p, data_ult_str = str(row.get('data_proposta', '')).split(" ")[0], str(row.get('data_proposta_renovada', '')).split(" ")[0]
                    cliente, nome_prop = str(row.get('nome_cliente', '')), str(row.get('nome_proposta', 'Principal'))
                    status, mrr, setup = str(row.get('status_proposta', 'Em Negociação')).strip() or "Em Negociação", str(row.get('total_mrr', '')), str(row.get('total_setup', ''))
                    temperatura = str(row.get('temperatura', 'Morno 🌤️')).split(" ")[0]
                    data_ref_prop_str = str(row.get('data_proposta_renovada', '')).strip() or str(row.get('data_proposta', '')).strip()
                    data_ref_temp_str = str(row.get('data_temperatura_renovada', '')).strip() or str(row.get('data_proposta', '')).strip()
                    vendedor = str(row.get('nome_usuario', ''))
                    
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
                            itens_crm = extrair_tabela_crm_itens(row.get('itens_orcamento', ''))
                            if itens_crm: st.dataframe(itens_crm, use_container_width=True, hide_index=True)
                    with c_np: st.write(nome_prop[:15] + ("..." if len(nome_prop)>15 else ""))
                    with c3: st.write(f"{cor_status} {status}")
                    with c_temp: st.write(temperatura)
                    with c4: st.write(tempo_faltante)
                    with c5: st.write(mrr)
                    with c6: st.write(setup)
                    with c7:
                        lead_para_contrato = {"nome": cliente}
                        match_lead = df_leads[df_leads['nome_razao'].astype(str).str.strip() == cliente.strip()]
                        if not match_lead.empty:
                            lr = match_lead.iloc[0]
                            lead_para_contrato = {"nome": str(lr.get("nome_razao", "")), "cpf_cnpj": str(lr.get("cpf_cnpj", "")).replace('nan', ''), "endereco": str(lr.get("endereco", "")).replace('nan', ''), "numero": str(lr.get("numero", "")).replace('nan', ''), "cidade": str(lr.get("cidade", "")).replace('nan', ''), "estado": str(lr.get("estado", "")).replace('nan', ''), "telefone": str(lr.get("telefone", "")).replace('nan', ''), "email_cliente": str(lr.get("email_cliente", "")).replace('nan', '')}
                            
                        itens_para_html = [{"quantidade": it["Qtd"], "nome": it["Produto / Serviço"]} for it in extrair_tabela_crm_itens(row.get('itens_orcamento', ''))]
                        condicao_txt = f"{str(row.get('parcelas', '1x'))} de {str(row.get('valor_parcela', 'R$ 0,00'))} ({str(row.get('forma_pagamento', 'Boleto'))})"
                        
                        html_prop = gerar_html_proposta(cliente, nome_prop, vendedor, itens_para_html, mrr, setup, condicao_txt)
                        
                        docx_bytes, erro_docx = gerar_documento_contrato(lead_para_contrato, mrr, setup, condicao_txt, row.get('itens_orcamento', ''))
                        
                        opcoes_acao = ["Selecione...", "📄 PDF Proposta", "📄 PDF Contrato", "✍️ Assinar Zapsign"]
                        if status == "Em Negociação":
                            opcoes_acao.extend(["✏️ Editar no Simulador", "🔄 Alterar Status"])
                            
                        acao_escolhida = st.selectbox("Ações", opcoes_acao, key=f"sel_acao_tab_{linha_real_planilha}", label_visibility="collapsed")
                        
                        if acao_escolhida == "📄 PDF Proposta":
                            st.download_button("📥 Baixar Proposta", data=html_prop, file_name=f"Proposta_{cliente}.html", mime="text/html", use_container_width=True, type="primary", key=f"dl_tab_{linha_real_planilha}")
                        elif acao_escolhida == "📄 PDF Contrato":
                            if docx_bytes:
                                with st.spinner("Gerando PDF (ConvertAPI)..."):
                                    pdf_bytes, erro_pdf = converter_para_pdf_na_nuvem(docx_bytes)
                                    if pdf_bytes:
                                        st.download_button("📥 Baixar Contrato (PDF)", data=pdf_bytes, file_name=f"Contrato_{cliente}.pdf", mime="application/pdf", use_container_width=True, type="primary", key=f"dl_cx_{linha_real_planilha}")
                                    else:
                                        st.error(f"Erro ao converter: {erro_pdf}")
                            else:
                                st.error("Erro ao gerar o documento DOCX base.")
                        elif acao_escolhida == "✍️ Assinar Zapsign":
                            if docx_bytes:
                                if st.button("✔️ Enviar ZapSign", type="primary", use_container_width=True, key=f"zap_tab_{linha_real_planilha}"):
                                    sucesso, retorno = enviar_para_zapsign(docx_bytes, cliente, lead_para_contrato.get('email_cliente', ''), lead_para_contrato.get('telefone', ''))
                                    if sucesso: st.success(retorno)
                                    else: st.error(retorno)
                        elif acao_escolhida == "✏️ Editar no Simulador":
                            if st.button("✔️ Abrir Simulador", type="primary", use_container_width=True, key=f"edit_tab_{linha_real_planilha}"):
                                st.session_state["status_credito_deps"] = None
                                carregar_proposta_para_simulador(linha_real_planilha, row.to_dict(), df_produtos, df_leads)
                                st.rerun()
                        elif acao_escolhida == "🔄 Alterar Status":
                            if st.button("✔️ Alterar Status", type="primary", use_container_width=True, key=f"ren_tab_{linha_real_planilha}"):
                                st.session_state["renovar_proposta_idx"] = linha_real_planilha
                                st.session_state["renovar_proposta_dados"] = row.to_dict()
                                st.rerun()
            else:
                for idx, row in df_prop.iterrows():
                    linha_real_planilha = row.name + 2 
                    data_p, cliente, nome_prop = str(row.get('data_proposta', '')).split(" ")[0], str(row.get('nome_cliente', '')), str(row.get('nome_proposta', 'Principal'))
                    status, mrr, setup = str(row.get('status_proposta', 'Em Negociação')).strip() or "Em Negociação", str(row.get('total_mrr', '')), str(row.get('total_setup', ''))
                    temperatura = str(row.get('temperatura', 'Morno 🌤️')).split(" ")[0]
                    
                    prop_renovada = str(row.get('data_proposta_renovada', '')).replace('nan', '').replace('None', '').strip()
                    data_ref_prop_str = prop_renovada if prop_renovada else str(row.get('data_proposta', '')).replace('nan', '').replace('None', '').strip()
                    
                    temp_renovada = str(row.get('data_temperatura_renovada', '')).replace('nan', '').replace('None', '').strip()
                    data_ref_temp_str = temp_renovada if temp_renovada else str(row.get('data_proposta', '')).replace('nan', '').replace('None', '').strip()
                    vendedor = str(row.get('nome_usuario', ''))
                    
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
                        itens_crm = extrair_tabela_crm_itens(row.get('itens_orcamento', ''))
                        if itens_crm: st.write("---"); st.markdown("📋 **Itens do Projeto para CRM:**"); st.dataframe(itens_crm, use_container_width=True, hide_index=True)
                        st.write("")
                        
                        lead_para_contrato = {"nome": cliente}
                        match_lead = df_leads[df_leads['nome_razao'].astype(str).str.strip() == cliente.strip()]
                        if not match_lead.empty:
                            lr = match_lead.iloc[0]
                            lead_para_contrato = {"nome": str(lr.get("nome_razao", "")), "cpf_cnpj": str(lr.get("cpf_cnpj", "")).replace('nan', ''), "endereco": str(lr.get("endereco", "")).replace('nan', ''), "numero": str(lr.get("numero", "")).replace('nan', ''), "cidade": str(lr.get("cidade", "")).replace('nan', ''), "estado": str(lr.get("estado", "")).replace('nan', ''), "telefone": str(lr.get("telefone", "")).replace('nan', ''), "email_cliente": str(lr.get("email_cliente", "")).replace('nan', '')}
                            
                        itens_para_html = [{"quantidade": it["Qtd"], "nome": it["Produto / Serviço"]} for it in extrair_tabela_crm_itens(row.get('itens_orcamento', ''))]
                        condicao_txt = f"{str(row.get('parcelas', '1x'))} de {str(row.get('valor_parcela', 'R$ 0,00'))} ({str(row.get('forma_pagamento', 'Boleto'))})"
                        html_prop = gerar_html_proposta(cliente, nome_prop, vendedor, itens_para_html, mrr, setup, condicao_txt)
                        docx_bytes, erro_docx = gerar_documento_contrato(lead_para_contrato, mrr, setup, condicao_txt, row.get('itens_orcamento', ''))
                        
                        st.markdown("**⚙️ Gerenciar Proposta e Negociação:**")
                        opcoes_acao = ["Selecione...", "📄 PDF Proposta", "📄 PDF Contrato", "✍️ Assinar Zapsign"]
                        if status == "Em Negociação":
                            opcoes_acao.extend(["✏️ Editar no Simulador", "🔄 Alterar Status"])
                            
                        acao_escolhida = st.selectbox("Selecione a ação:", opcoes_acao, key=f"sel_acao_card_{linha_real_planilha}", label_visibility="collapsed")
                        
                        if acao_escolhida == "📄 PDF Proposta":
                            st.download_button("📥 Baixar PDF Proposta", data=html_prop, file_name=f"Proposta_{cliente}.html", mime="text/html", use_container_width=True, type="primary", key=f"dl_card_{linha_real_planilha}")
                        elif acao_escolhida == "📄 PDF Contrato":
                            if docx_bytes:
                                with st.spinner("Convertendo na nuvem..."):
                                    pdf_bytes, erro_pdf = converter_para_pdf_na_nuvem(docx_bytes)
                                    if pdf_bytes:
                                        st.download_button("📥 Concluído! Baixar PDF", data=pdf_bytes, file_name=f"Contrato_{cliente}.pdf", mime="application/pdf", use_container_width=True, type="primary", key=f"dl_cx_card_{linha_real_planilha}")
                                    else:
                                        st.error(f"Erro: {erro_pdf}")
                            else:
                                st.error("Erro ao gerar o contrato docx base.")
                        elif acao_escolhida == "✍️ Assinar Zapsign":
                            if docx_bytes:
                                if st.button("✔️ Confirmar Envio (ZapSign)", type="primary", use_container_width=True, key=f"zap_card_{linha_real_planilha}"):
                                    sucesso, retorno = enviar_para_zapsign(docx_bytes, cliente, lead_para_contrato.get('email_cliente', ''), lead_para_contrato.get('telefone', ''))
                                    if sucesso: st.success(retorno)
                                    else: st.error(retorno)
                        elif acao_escolhida == "✏️ Editar no Simulador":
                            if st.button("✔️ Abrir no Simulador", type="primary", use_container_width=True, key=f"edit_card_{linha_real_planilha}"):
                                st.session_state["status_credito_deps"] = None
                                carregar_proposta_para_simulador(linha_real_planilha, row.to_dict(), df_produtos, df_leads)
                                st.rerun()
                        elif acao_escolhida == "🔄 Alterar Status":
                            if st.button("✔️ Alterar Status", type="primary", use_container_width=True, key=f"ren_card_{linha_real_planilha}"):
                                st.session_state["renovar_proposta_idx"] = linha_real_planilha
                                st.session_state["renovar_proposta_dados"] = row.to_dict()
                                st.rerun()

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
                    nome = str(row.get('nome_razao', 'Não Informado')).strip()
                    telefone = str(row.get('telefone', '-')).strip()
                    data_cad = str(row.get('data_cadastro', '-')).split(" ")[0]
                    end_curto = f"{str(row.get('endereco', '')).strip()}, {str(row.get('numero', '')).strip()} - {str(row.get('cidade', '')).strip()}".replace("nan", "").strip(" ,-") or "-"
                    
                    status_lead, data_ult_prop = "🔵 Lead", "-"
                    df_prop_total = carregar_minhas_propostas(st.session_state["email_usuario"])
                    if not df_prop_total.empty and 'nome_cliente' in df_prop_total.columns:
                        prop_cliente = df_prop_total[df_prop_total['nome_cliente'].astype(str).str.strip() == nome]
                        if not prop_cliente.empty:
                            status_str = str(prop_cliente.iloc[-1].get('status_proposta', '')).strip()
                            status_lead = "🏆 Aprovada" if status_str == "Aprovada" else ("🔴 Perdida" if status_str == "Perdida" else "🟢 Proposta")
                            data_ult_prop = str(prop_cliente.iloc[-1].get('data_proposta', '-')).split(" ")[0]

                    c1, c2, c3, c4, c5, c6, c7 = st.columns([4, 3, 4, 2, 2, 2, 3])
                    with c1: 
                        with st.expander(f"👤 {nome[:25]}{'...' if len(nome)>25 else ''}"):
                            st.markdown(f"<span style='font-size: 0.85rem; color: #475569;'><b>CPF/CNPJ:</b> {str(row.get('cpf_cnpj', '')).replace('nan', '')}<br><b>E-mail:</b> {str(row.get('email_cliente', '')).replace('nan', '')}<br><b>Contato:</b> {str(row.get('contato', '')).replace('nan', '')}</span>", unsafe_allow_html=True)
                    with c2: st.markdown(f"<div style='margin-top: 0.4rem;'>{telefone}</div>", unsafe_allow_html=True)
                    with c3: st.markdown(f"<div style='margin-top: 0.4rem;'>{end_curto[:30]}{'...' if len(end_curto)>30 else ''}</div>", unsafe_allow_html=True)
                    with c4: st.markdown(f"<div style='margin-top: 0.4rem;'>{data_cad}</div>", unsafe_allow_html=True)
                    with c5: st.markdown(f"<div style='margin-top: 0.4rem;'>{status_lead}</div>", unsafe_allow_html=True)
                    with c6: st.markdown(f"<div style='margin-top: 0.4rem;'>{data_ult_prop}</div>", unsafe_allow_html=True)
                    with c7:
                        btn1, btn2 = st.columns([7, 3])
                        with btn1:
                            if st.button("Proposta", key=f"btn_lead_{idx}", use_container_width=True): 
                                st.session_state.update({"lead_dados": {"data_cadastro": data_cad, "nome": nome, "cpf_cnpj": str(row.get('cpf_cnpj', '')).replace('nan', ''), "data_nascimento": str(row.get("data_nascimento", "")).replace('nan', ''), "endereco": str(row.get('endereco', '')).replace('nan', ''), "numero": str(row.get('numero', '')).replace('nan', ''), "cidade": str(row.get('cidade', '')).replace('nan', ''), "estado": str(row.get("estado", "")).replace('nan', ''), "telefone": telefone, "email_cliente": str(row.get('email_cliente', '')).replace('nan', ''), "contato": str(row.get('contato', '')).replace('nan', ''), "gps": str(row.get("coordenadas_gps", "")).replace('nan', '')}, "lead_salvo": True, "gatilho_limpar_carrinho": True, "etapa_atual": "simulador", "editando_lead_idx": linha_real_planilha, "nome_proposta_atual": "", "temp_proposta_atual": "Selecione...", "status_proposta_atual": "Selecione...", "segmento_proposta_atual": "Selecione...", "status_credito_deps": None}); st.rerun()
                        with btn2:
                            if st.button("✏️", help="Editar", key=f"btn_edit_lead_{idx}", use_container_width=True): 
                                st.session_state.update({"lead_dados": {"data_cadastro": data_cad, "nome": nome, "cpf_cnpj": str(row.get('cpf_cnpj', '')).replace('nan', ''), "data_nascimento": str(row.get("data_nascimento", "")).replace('nan', ''), "endereco": str(row.get('endereco', '')).replace('nan', ''), "numero": str(row.get('numero', '')).replace('nan', ''), "cidade": str(row.get('cidade', '')).replace('nan', ''), "estado": str(row.get("estado", "")).replace('nan', ''), "telefone": telefone, "email_cliente": str(row.get('email_cliente', '')).replace('nan', ''), "contato": str(row.get('contato', '')).replace('nan', ''), "gps": str(row.get("coordenadas_gps", "")).replace('nan', '')}, "lead_salvo": True, "etapa_atual": "lead", "editando_lead_idx": linha_real_planilha}); st.rerun()

            else:
                for idx, row in df_leads.iterrows():
                    linha_real_planilha = row.name + 2
                    nome = str(row.get('nome_razao', 'Não Informado')).strip()
                    telefone = str(row.get('telefone', '-')).strip()
                    data_cad = str(row.get('data_cadastro', '-')).split(" ")[0]
                    end_curto = f"{str(row.get('endereco', '')).strip()}, {str(row.get('numero', '')).strip()} - {str(row.get('cidade', '')).strip()}".replace("nan", "").strip(" ,-") or "-"
                    
                    status_lead = "🔵 Lead"
                    df_prop_total = carregar_minhas_propostas(st.session_state["email_usuario"])
                    if not df_prop_total.empty and 'nome_cliente' in df_prop_total.columns:
                        prop_cliente = df_prop_total[df_prop_total['nome_cliente'].astype(str).str.strip() == nome]
                        if not prop_cliente.empty: 
                            status_str = str(prop_cliente.iloc[-1].get('status_proposta', '')).strip()
                            status_lead = "🏆 Aprovada" if status_str == "Aprovada" else ("🔴 Perdida" if status_str == "Perdida" else "🟢 Proposta")

                    with st.expander(f"👤 {nome} ({status_lead})"):
                        st.markdown(f"📞 <b>Telefone:</b> {telefone}<br>📍 <b>Endereço:</b> {end_curto}<br>📄 <b>CPF/CNPJ:</b> {str(row.get('cpf_cnpj', '')).replace('nan', '')} | ✉️ <b>E-mail:</b> {str(row.get('email_cliente', '')).replace('nan', '')}<br>👤 <b>Contato:</b> {str(row.get('contato', '')).replace('nan', '')} | 📅 <b>Cadastro:</b> {data_cad}", unsafe_allow_html=True)
                        st.write("")
                        c_b1, c_b2 = st.columns([7, 3])
                        with c_b1:
                            if st.button("➕ Criar Proposta", key=f"btn_lead_{idx}", type="primary", use_container_width=True): 
                                st.session_state.update({"lead_dados": {"data_cadastro": data_cad, "nome": nome, "cpf_cnpj": str(row.get('cpf_cnpj', '')).replace('nan', ''), "data_nascimento": str(row.get("data_nascimento", "")).replace('nan', ''), "endereco": str(row.get('endereco', '')).replace('nan', ''), "numero": str(row.get('numero', '')).replace('nan', ''), "cidade": str(row.get('cidade', '')).replace('nan', ''), "estado": str(row.get("estado", "")).replace('nan', ''), "telefone": telefone, "email_cliente": str(row.get('email_cliente', '')).replace('nan', ''), "contato": str(row.get('contato', '')).replace('nan', ''), "gps": str(row.get("coordenadas_gps", "")).replace('nan', '')}, "lead_salvo": True, "gatilho_limpar_carrinho": True, "etapa_atual": "simulador", "editando_lead_idx": linha_real_planilha, "nome_proposta_atual": "", "temp_proposta_atual": "Selecione...", "status_proposta_atual": "Selecione...", "segmento_proposta_atual": "Selecione...", "status_credito_deps": None}); st.rerun()
                        with c_b2:
                            if st.button("✏️ Editar", key=f"btn_edit_lead_{idx}", use_container_width=True): 
                                st.session_state.update({"lead_dados": {"data_cadastro": data_cad, "nome": nome, "cpf_cnpj": str(row.get('cpf_cnpj', '')).replace('nan', ''), "data_nascimento": str(row.get("data_nascimento", "")).replace('nan', ''), "endereco": str(row.get('endereco', '')).replace('nan', ''), "numero": str(row.get('numero', '')).replace('nan', ''), "cidade": str(row.get('cidade', '')).replace('nan', ''), "estado": str(row.get("estado", "")).replace('nan', ''), "telefone": telefone, "email_cliente": str(row.get('email_cliente', '')).replace('nan', ''), "contato": str(row.get('contato', '')).replace('nan', ''), "gps": str(row.get("coordenadas_gps", "")).replace('nan', '')}, "lead_salvo": True, "etapa_atual": "lead", "editando_lead_idx": linha_real_planilha}); st.rerun()

    elif st.session_state["etapa_atual"] == "lead":
        idx_editando_lead = st.session_state.get("editando_lead_idx")
        st.write(f"### 👤 Atualizar Dados do Cliente" if idx_editando_lead else "### 👤 1. Cadastro de Novo Cliente")
        
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
        
        doc_atual = re.sub(r'\D', '', str(ld.get("cpf_cnpj", "")))
        idx_tipo = 1 if len(doc_atual) > 11 else 0
        tipo_pessoa = st.radio("Tipo de Cliente:", ["Pessoa Física (CPF)", "Pessoa Jurídica (CNPJ)"], index=idx_tipo, horizontal=True)

        with st.container(border=True):
            if "CPF" in tipo_pessoa:
                c1, c2, c3 = st.columns([4, 3, 3])
                nome = c1.text_input("Nome Completo *", value=ld.get("nome", ""))
                cpf_cnpj = c2.text_input("CPF *", value=ld.get("cpf_cnpj", ""), max_chars=14, placeholder="Somente números")
                data_nasc = c3.text_input("Data de Nascimento *", value=ld.get("data_nascimento", ""), max_chars=10, placeholder="Ex: 02121978")
            else:
                c1, c2 = st.columns([6, 4])
                nome = c1.text_input("Razão Social *", value=ld.get("nome", ""))
                cpf_cnpj = c2.text_input("CNPJ *", value=ld.get("cpf_cnpj", ""), max_chars=18, placeholder="Somente números")
                data_nasc = ""

            c3_b, c4, c5 = st.columns([4, 2, 3])
            endereco = c3_b.text_input("Endereço *", value=ld.get("endereco", ""))
            numero = c4.text_input("Número *", value=ld.get("numero", ""))
            telefone = c5.text_input("Telefone *", value=ld.get("telefone", ""), max_chars=15)
            
            c6, c7, c8 = st.columns([3, 1, 4])
            cidade = c6.text_input("Cidade", value=ld.get("cidade", ""))
            estados_br = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]
            estado = c7.selectbox("Estado", estados_br, index=estados_br.index(ld.get("estado", "SC").upper()) if ld.get("estado", "SC").upper() in estados_br else estados_br.index("SC"))
            contato = c8.text_input("Nome do Contato", value=ld.get("contato", ""))
            email_cliente = st.text_input("✉️ E-mail do Cliente", value=ld.get("email_cliente", ""))
            gps_final = gps_audit if gps_audit else ld.get("gps", "")
            
            st.write("")
            if st.button("Atualizar Dados do Cliente ➡️" if idx_editando_lead else "Salvar Cliente e Iniciar Proposta ➡️", type="primary", use_container_width=True):
                tel_numeros = re.sub(r'\D', '', telefone)
                email_valido = False if email_cliente and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email_cliente) else True
                
                doc_limpo = re.sub(r'\D', '', cpf_cnpj)
                is_cpf = "CPF" in tipo_pessoa
                doc_valido = validar_cpf(doc_limpo) if is_cpf else validar_cnpj(doc_limpo)
                
                if is_cpf:
                    msg_doc = "CPF inválido. Certifique-se de digitar os 11 números."
                else:
                    msg_doc = "CNPJ inválido. Certifique-se de digitar os 14 números."
                
                nasc_valido = True
                data_nasc_formatada = data_nasc.strip()
                if is_cpf and data_nasc_formatada:
                    nasc_limpo = re.sub(r'\D', '', data_nasc_formatada)
                    if len(nasc_limpo) == 8:
                        data_nasc_formatada = f"{nasc_limpo[:2]}/{nasc_limpo[2:4]}/{nasc_limpo[4:]}"
                    
                    if not re.match(r'^(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[012])/\d{4}$', data_nasc_formatada):
                        nasc_valido = False
                
                if not nome or not endereco or not numero or not telefone or not cpf_cnpj: 
                    st.error("⚠️ Atenção: Preencha todos os campos obrigatórios marcados com (*).")
                elif is_cpf and not data_nasc_formatada:
                    st.error("⚠️ Atenção: Preencha a Data de Nascimento para pessoa física.")
                elif len(tel_numeros) < 10 or len(tel_numeros) > 11: 
                    st.error("⚠️ Atenção: O Telefone deve conter o DDD + Número válido (10 ou 11 dígitos).")
                elif not email_valido: 
                    st.error("⚠️ Atenção: O E-mail digitado é inválido.")
                elif not doc_valido:
                    st.error(f"⚠️ Atenção: {msg_doc}")
                elif is_cpf and not nasc_valido:
                    st.error("⚠️ Atenção: A Data de Nascimento deve ter 8 números (ex: 02121978) ou estar no formato DD/MM/AAAA.")
                elif not (gps_audit if gps_audit else ld.get("gps", "")) and not idx_editando_lead: 
                    st.error("⚠️ Atenção: Valide sua localização clicando no ícone de GPS.")
                else:
                    doc_formatado = formatar_documento(doc_limpo, "CPF" if is_cpf else "CNPJ")
                    st.session_state["lead_dados"].update({
                        "nome": padronizar_nome(nome), 
                        "cpf_cnpj": doc_formatado, 
                        "data_nascimento": data_nasc_formatada if is_cpf else "",
                        "endereco": padronizar_nome(endereco), 
                        "numero": numero, 
                        "cidade": padronizar_nome(cidade), 
                        "estado": estado, 
                        "telefone": padronizar_telefone(telefone), 
                        "contato": padronizar_nome(contato), 
                        "email_cliente": email_cliente, 
                        "gps": gps_audit if gps_audit else ld.get("gps", "")
                    })
                    
                    if idx_editando_lead:
                        if atualizar_lead(idx_editando_lead, st.session_state["lead_dados"]): st.toast("Cliente atualizado!"); st.cache_data.clear(); st.session_state["etapa_atual"] = "meus_leads"; st.rerun()
                    else:
                        novo_idx = salvar_lead(st.session_state["lead_dados"], st.session_state["nome_usuario"], st.session_state["email_usuario"])
                        if novo_idx: st.session_state.update({"lead_salvo": True, "etapa_atual": "simulador", "editando_lead_idx": novo_idx, "nome_proposta_atual": "", "temp_proposta_atual": "Selecione...", "status_proposta_atual": "Selecione...", "segmento_proposta_atual": "Selecione...", "status_credito_deps": None}); st.toast("Cliente salvo!"); st.cache_data.clear(); st.rerun()

    elif st.session_state["etapa_atual"] == "simulador":
        st.write("### 🛒 2. Simulador de Vendas")
        if st.session_state.get("proposta_idx_editando"): st.warning("✏️ **Modo de Edição Ativo:** Você está modificando uma proposta já enviada.")
        col_lead_info, col_lead_btn = st.columns([8, 2])
        with col_lead_info: st.info(f"👤 **Cliente Ativo:** {st.session_state['lead_dados'].get('nome', '')} | 📞 {st.session_state['lead_dados'].get('telefone', '')}")
        with col_lead_btn:
            if st.button("✏️ Editar Cliente", use_container_width=True): st.session_state["etapa_atual"] = "lead"; st.rerun()
        
        try:
            df_produtos, df_valor_sensor, df_valor_ponto, df_regras, cfg = carregar_produtos(), carregar_valores_sensores(), carregar_valores_ponto_mo(), carregar_regras_validacao(), carregar_configuracoes()
            taxa_bruta = cfg.get("taxa_juros_mensal", 0.022)
            taxa_juros = taxa_bruta / 100 if (taxa_bruta >= 10 and taxa_bruta/10 < 1) else (taxa_bruta/100 if taxa_bruta > 1 else taxa_bruta)
            max_sj, max_bol, max_cc = int(cfg.get("max_parcelas_sem_juros", 3)), int(cfg.get("max_parcelas_boleto", 18)), int(cfg.get("max_parcelas_cartao", 24))
            lim_p, lim_a, lim_i = cfg.get("desc_max_produtos", 15.0), cfg.get("desc_max_alarme", 15.0), cfg.get("desc_max_imagem", 30.0)
            unidades_disponiveis = sorted(list(set(df_valor_ponto['unidade'].dropna().astype(str).str.strip()))) if not df_valor_ponto.empty and 'unidade' in df_valor_ponto.columns else ["Padrão"]

            c_nome, c_temp, c_status, c_unid, c_seg, c_copiar = st.columns([2.5, 1.5, 1.5, 2.0, 1.5, 2.0])
            
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
            with c_unid:
                opcoes_unidade = ["Selecione..."] + unidades_disponiveis
                idx_unid = 0
                val_unid = st.session_state.get("unidade_mo_selecionada")
                if val_unid in opcoes_unidade:
                    idx_unid = opcoes_unidade.index(val_unid)
                unidade_selecionada_op = st.selectbox("🏢 Unidade de Mão de Obra", opcoes_unidade, index=idx_unid)
                st.session_state["unidade_mo_selecionada"] = unidade_selecionada_op
                unidade_selecionada = None if unidade_selecionada_op == "Selecione..." else unidade_selecionada_op
                
                if not unidade_selecionada:
                    st.markdown('<p style="color:#d90429; font-size:0.85rem; margin-top:-10px; font-weight:600;">⚠️ Selecione a unidade de MO.</p>', unsafe_allow_html=True)
            
            with c_seg:
                opcoes_segmento = ["Selecione...", "KMA", "KRV", "KAV", "KPV", "IOT"]
                seg_salvo = st.session_state.get("segmento_proposta_atual", "Selecione...")
                if seg_salvo not in opcoes_segmento: seg_salvo = "Selecione..."
                segmento_escolhido = st.selectbox("🏷️ Segmento de Produto", opcoes_segmento, index=opcoes_segmento.index(seg_salvo))
                st.session_state["segmento_proposta_atual"] = segmento_escolhido
                
                if segmento_escolhido == "Selecione...":
                    st.markdown('<p style="color:#d90429; font-size:0.85rem; margin-top:-10px; font-weight:600;">⚠️ Selecione o Segmento</p>', unsafe_allow_html=True)

            with c_copiar:
                df_prop_user = df_prop
                if not df_prop_user.empty:
                    opcoes_copia = []
                    idx_map = {}
                    for i, r in df_prop_user.iterrows():
                        texto_exibicao = f"{str(r.get('nome_cliente',''))[:15]} | {str(r.get('nome_proposta',''))[:15]} ({str(r.get('data_proposta','')).split(' ')[0]})"
                        opcoes_copia.append(texto_exibicao)
                        idx_map[texto_exibicao] = r
                    
                    prop_sel = st.selectbox("📋 Copiar Orçamento Anterior", ["Selecione..."] + opcoes_copia, key="sel_copia_orc_top")
                    
                    if prop_sel != "Selecione...":
                        def efetivar_copia():
                            row_sel = idx_map[st.session_state["sel_copia_orc_top"]]
                            novo_carrinho = []
                            for item in str(row_sel.get('itens_orcamento', '')).split(";"):
                                if "x " in item:
                                    try:
                                        qtd = int(item.strip().split("x ", 1)[0])
                                        nome_item = item.strip().split("x ", 1)[1].split("[Cód:")[0].strip() if "[Cód:" in item else item.strip().split("x ", 1)[1].strip()
                                    except: qtd, nome_item = 0, ""
                                    prod_info = df_produtos[df_produtos['nome_item'].astype(str).str.strip() == nome_item]
                                    if not prod_info.empty:
                                        prod = prod_info.iloc[0]
                                        novo_carrinho.append({"nome": str(prod['nome_item']), "codigo": str(prod.get('codigo_kme', '')), "tipo_sensor": str(prod.get('tipo_sensor', '')), "categoria": str(prod.get('categoria_receita', '')), "grupo": str(prod.get('grupo_itens', '')), "quantidade": qtd, "preco_venda": converter_para_numero(prod.get('preco_venda', 0)), "preco_mrr": converter_para_numero(prod.get('preco_loc_36', 0))})
                            
                            st.session_state["carrinho"] = novo_carrinho
                            st.session_state["desc_prod"] = converter_para_numero(row_sel.get('desc_prod', '0')) or None
                            st.session_state["desc_alarme"] = converter_para_numero(row_sel.get('desc_alarme', '0')) or None
                            st.session_state["desc_imagem"] = converter_para_numero(row_sel.get('desc_imagem', '0')) or None
                            
                            st.session_state["sel_copia_orc_top"] = "Selecione..."
                        
                        st.button("✔️ Confirmar Cópia", use_container_width=True, type="primary", on_click=efetivar_copia)
                else:
                    st.selectbox("📋 Copiar Orçamento Anterior", ["Sem histórico..."], disabled=True)

            st.divider()

            col_produtos, col_resumo = st.columns([5, 5])
            with col_resumo:
                st.write("### 📊 Resumo Financeiro")
                
                val_desc_p = st.session_state.get("desc_prod") or 0.0
                val_desc_a = st.session_state.get("desc_alarme") or 0.0
                val_desc_i = st.session_state.get("desc_imagem") or 0.0
                
                if val_desc_p > float(lim_p): st.session_state["desc_prod"] = float(lim_p); val_desc_p = float(lim_p)
                if val_desc_a > float(lim_a): st.session_state["desc_alarme"] = float(lim_a); val_desc_a = float(lim_a)
                if val_desc_i > float(lim_i): st.session_state["desc_imagem"] = float(lim_i); val_desc_i = float(lim_i)
                
                with st.expander("🏷️ Aplicar Descontos por Categoria"):
                    c_d1, c_d2, c_d3 = st.columns(3)
                    with c_d1: st.number_input(f"Prod (%) [Máx: {lim_p:.0f}%]", min_value=0.0, max_value=float(lim_p), step=0.5, key="desc_prod")
                    with c_d2: st.number_input(f"Alarme (%) [Máx: {lim_a:.0f}%]", min_value=0.0, max_value=float(lim_a), step=0.5, key="desc_alarme")
                    with c_d3: st.number_input(f"Imagem (%) [Máx: {lim_i:.0f}%]", min_value=0.0, max_value=float(lim_i), step=0.5, key="desc_imagem")
                
            with col_produtos:
                st.write("### ➕ Catálogo")
                
                if segmento_escolhido == "Selecione...":
                    st.info("👆 Selecione um **Segmento de Produto** no cabeçalho acima para carregar as opções do catálogo.")
                else:
                    if 'segmento' in df_produtos.columns:
                        df_catalogo = df_produtos[df_produtos['segmento'].fillna("").astype(str).str.strip().str.upper() == segmento_escolhido.upper()]
                    else:
                        df_catalogo = pd.DataFrame()
                        st.error("A coluna 'segmento' não foi encontrada na tabela base_produtos.")
                    
                    if df_catalogo.empty and 'segmento' in df_produtos.columns:
                        st.warning(f"Nenhum produto encontrado para o segmento **{segmento_escolhido}** no banco de dados.")
                        
                    aba_servicos, aba_produtos, aba_mao_obra = st.tabs(["🔄 Serviços", "📦 Produtos", "🛠️ Mão de Obra"])
                    
                    def desenhar_card_produto(index, linha):
                        is_aberto, nome_item_limpo, cat_limpa_card, cod_kme = st.session_state.get("item_aberto") == index, str(linha.get('nome_item', '')).strip(), str(linha.get('categoria_receita', '')).strip().lower(), str(linha.get('codigo_kme', '')).strip()
                        pv_card = converter_para_numero(linha.get('preco_venda', 0))
                        
                        if unidade_selecionada and ("obra" in cat_limpa_card or "instala" in cat_limpa_card) and not df_valor_ponto.empty:
                            match_mo_card = df_valor_ponto[(df_valor_ponto['unidade'].astype(str).str.strip() == unidade_selecionada) & (df_valor_ponto['nome_item'].astype(str).str.strip() == nome_item_limpo)]
                            if not match_mo_card.empty:
                                pv_card = converter_para_numero(match_mo_card.iloc[0]['valor_mo'])
                                if str(match_mo_card.iloc[0].get('codigo', '')).strip() and str(match_mo_card.iloc[0].get('codigo', '')).strip() != 'nan': cod_kme = str(match_mo_card.iloc[0].get('codigo', '')).strip()
                        
                        if st.button(f"{'🔽' if is_aberto else '▶️'} {nome_item_limpo}{f' (Cód: {cod_kme})' if cod_kme else ''}", key=f"btn_acc_{index}", use_container_width=True): st.session_state["item_aberto"] = None if is_aberto else index; st.rerun()
                        
                        if is_aberto:
                            with st.container():
                                st.caption(f"**Grupo:** {linha.get('grupo_itens', 'N/A')} | **Categoria:** {linha.get('categoria_receita', '')}")
                                c_qtd, c_add = st.columns([3, 7])
                                qtd = c_qtd.number_input("Qtd", min_value=1, step=1, key=f"qtd_{index}")
                                c_add.write(""); c_add.write("")
                                if c_add.button("Adicionar ao Orçamento", key=f"btn_add_{index}", type="primary", use_container_width=True, disabled=(not unidade_selecionada)):
                                    st.session_state["carrinho"].append({"nome": nome_item_limpo, "codigo": cod_kme, "tipo_sensor": str(linha.get('tipo_sensor', '')), "categoria": str(linha.get('categoria_receita', '')), "grupo": str(linha.get('grupo_itens', '')), "quantidade": qtd, "preco_venda": pv_card, "preco_mrr": converter_para_numero(linha.get('preco_loc_36', 0))})
                                    st.session_state["item_aberto"] = None; st.rerun()
                            st.divider()

                    def preencher_aba_grupo(df, nome_grupo):
                        itens = df[df['grupo_itens'].fillna("").astype(str).str.strip().str.lower() == nome_grupo.lower()]
                        with st.container(height=500):
                            if itens.empty: st.info(f"Nenhum item em '{nome_grupo}'.")
                            else:
                                for index, linha in itens.iterrows(): desenhar_card_produto(index, linha)

                    with aba_servicos:
                        grupos_serv = ["Servico Alarme", "Servico Imagem"]
                        sub_abas_serv = st.tabs(grupos_serv + ["Outros"])
                        for i, nome in enumerate(grupos_serv):
                            with sub_abas_serv[i]: preencher_aba_grupo(df_catalogo, nome)
                        with sub_abas_serv[-1]:
                            outros_serv = df_catalogo[df_catalogo['categoria_receita'].fillna("").astype(str).str.lower().str.contains("mensal|loca|servi|seguro") & ~df_catalogo['grupo_itens'].fillna("").astype(str).str.strip().str.lower().isin([g.lower() for g in grupos_serv])]
                            with st.container(height=500):
                                if not outros_serv.empty:
                                    for index, linha in outros_serv.iterrows(): desenhar_card_produto(index, linha)

                    with aba_produtos:
                        grupos_prod = ["Smart Alarme", "JFL 8W", "AXPRO", "Detect IA", "CFTV"]
                        sub_abas_prod = st.tabs(grupos_prod + ["Outros"])
                        for i, nome in enumerate(grupos_prod):
                            with sub_abas_prod[i]: preencher_aba_grupo(df_catalogo, nome)
                        with sub_abas_prod[-1]:
                            outros_prod = df_catalogo[~df_catalogo['categoria_receita'].fillna("").astype(str).str.lower().str.contains("mensal|loca|servi|seguro|obra|instala") & ~df_catalogo['grupo_itens'].fillna("").astype(str).str.strip().str.lower().isin([g.lower() for g in grupos_prod])]
                            with st.container(height=500):
                                if not outros_prod.empty:
                                    for index, linha in outros_prod.iterrows(): desenhar_card_produto(index, linha)

                    with aba_mao_obra:
                        st.write("#### 🔹 Instalação e Configuração")
                        itens_mo = df_catalogo[df_catalogo['categoria_receita'].fillna("").astype(str).str.lower().str.contains("obra|instala")]
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
                        match_mo_card = df_valor_ponto[(df_valor_ponto['unidade'].astype(str).str.strip() == unidade_selecionada) & (df_valor_ponto['nome_item'].astype(str).str.strip() == nome_item_limpo)]
                        if not match_mo_card.empty:
                            v_u = converter_para_numero(match_mo_card.iloc[0]['valor_mo'])
                            if str(match_mo_card.iloc[0].get('codigo', '')).strip() and str(match_mo_card.iloc[0].get('codigo', '')).strip() != 'nan': item['codigo'] = str(match_mo_card.iloc[0].get('codigo', '')).strip()
                            
                    if cod_item in ['254000000042', '254000000377', '25400000042', '25400000377'] and not df_valor_sensor.empty:
                        match = df_valor_sensor[(df_valor_sensor['codigo_servico'].astype(str).str.strip().str.lstrip('0') == cod_item) & (pd.to_numeric(df_valor_sensor['sensor_abertura'], errors='coerce') == qtd_abertura) & (pd.to_numeric(df_valor_sensor['sensor_ivp'], errors='coerce') == qtd_ivp)]
                        if not match.empty: v_u = converter_para_numero(match.iloc[0]['preco'])
                    
                    item['preco_calculado'] = v_u 
                    if "obra" in cat_limpa or "instala" in cat_limpa: total_mao_obra += (v_u * item['quantidade'])
                    elif "produto" in cat_limpa or "equipamento" in cat_limpa: bruto_produtos += (v_u * item['quantidade'])
                    else:
                        if "imagem" in grp_limpo: bruto_imagem += (v_u * item['quantidade'])
                        else: bruto_alarme += (v_u * item['quantidade'])

                liq_produtos = bruto_produtos * (1 - (val_desc_p / 100))
                liq_alarme = bruto_alarme * (1 - (val_desc_a / 100))
                liq_imagem = bruto_imagem * (1 - (val_desc_i / 100))
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
                
                st.write("")
                if len(st.session_state["carrinho"]) > 0:
                    c_vazio_carrinho, c_btn_limpar = st.columns([7, 3])
                    with c_btn_limpar:
                        if st.button("🗑️ Limpar Carrinho", use_container_width=True): 
                            st.session_state["gatilho_limpar_carrinho"] = True
                            st.rerun()

            st.divider()
            
            # ---> INÍCIO DA ANÁLISE DE CRÉDITO <---
            st.write("### 🔍 Análise de Crédito (Deps)")
            cpf_cnpj_lead = st.session_state["lead_dados"].get("cpf_cnpj", "").strip()
            
            if not cpf_cnpj_lead:
                st.warning("⚠️ CPF/CNPJ não informado no cadastro do cliente. Edite o cliente para adicionar o documento.")
            else:
                c_cred1, c_cred2 = st.columns([3, 7])
                with c_cred1:
                    if st.button("⚙️ Consultar Crédito", use_container_width=True):
                        st.session_state["status_credito_deps"] = "Aprovado"
                        
                        doc_limpo = re.sub(r'\D', '', cpf_cnpj_lead)
                        tempo_str = "Não identificado"
                        situacao_str = "Não identificada"
                        
                        try:
                            if len(doc_limpo) == 14:
                                resp = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{doc_limpo}", timeout=5)
                                if resp.status_code == 200:
                                    dados_cnpj = resp.json()
                                    data_inicio = dados_cnpj.get('data_inicio_atividade')
                                    situacao_str = str(dados_cnpj.get('descricao_situacao_cadastral', 'Não identificada')).title()
                                    if data_inicio:
                                        d_inicio = datetime.datetime.strptime(data_inicio, '%Y-%m-%d')
                                        dias = (datetime.datetime.now() - d_inicio).days
                                        anos = dias // 365
                                        meses = (dias % 365) // 30
                                        tempo_str = f"{anos} anos e {meses} meses"
                            elif len(doc_limpo) == 11:
                                situacao_str = "N/A (Pessoa Física)"
                                data_nasc = st.session_state["lead_dados"].get("data_nascimento", "")
                                if data_nasc:
                                    d_nasc = datetime.datetime.strptime(data_nasc, '%d/%m/%Y')
                                    anos = (datetime.datetime.now() - d_nasc).days // 365
                                    tempo_str = f"{anos} anos"
                        except Exception as e:
                            pass
                            
                        st.session_state["tempo_empresa_credito"] = tempo_str
                        st.session_state["situacao_cnpj"] = situacao_str
                        st.rerun()
                        
                with c_cred2:
                    if st.session_state.get("status_credito_deps") == "Aprovado":
                        tempo_exibicao = st.session_state.get("tempo_empresa_credito", "Não identificado")
                        situacao_exibicao = st.session_state.get("situacao_cnpj", "Não identificada")
                        
                        st.markdown(f"""
                            <div style="background-color: #ecfdf5; border-left: 5px solid #10b981; padding: 15px; border-radius: 8px;">
                                <p style="margin:0; font-size: 1.1rem; color: #065f46;"><b>✅ Análise Concluída</b></p>
                                <p style="margin:0; font-size: 0.95rem; color: #065f46;">
                                <b>Situação do CNPJ:</b> {situacao_exibicao}<br>
                                <b>Score:</b> 1.000 | <b>Prob. Inadimplência:</b> 0% | <b>Pendências:</b> 0<br>
                                <b>Tempo de Empresa/Idade:</b> {tempo_exibicao}<br>
                                <b>Resultado Final:</b> Sem restrições. (Liberação total de parcelamento em Boleto)
                                </p>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.info("Aguardando consulta do documento para liberação de política de pagamento.")
            # ---> FIM DA ANÁLISE DE CRÉDITO <---

            st.divider()
            st.write("### 💳 Tabela de Parcelamento (Setup Inicial)")
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
                st.write("### 📝 Apresentação Final para o Cliente")
                col_sel1, col_sel2 = st.columns([4, 6])
                with col_sel1: parcela_escolhida = st.selectbox("Selecione a condition fechada com o cliente:", range(1, limite_parcelas + 1), format_func=lambda x: f"{x}x parcela(s)")
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
                
                if not unidade_selecionada or not nome_proposta.strip() or temperatura_escolhida == "Selecione..." or status_escolhido == "Selecione..." or segmento_escolhido == "Selecione...":
                    pode_gravar = False
                
                st.markdown('<p id="btn-salvar-orcamento"></p>', unsafe_allow_html=True)
                st.markdown('''
                    <style>
                    div:has(> p#btn-salvar-orcamento) + div button:not(:disabled) {
                        background-color: #10b981 !important;
                        color: white !important;
                        border-color: #10b981 !important;
                    }
                    div:has(> p#btn-salvar-orcamento) + div button:not(:disabled):hover {
                        background-color: #059669 !important;
                        border-color: #059669 !important;
                    }
                    </style>
                ''', unsafe_allow_html=True)
                
                st.write("")
                if st.button("💾 Salvar Orçamento", type="primary", disabled=not pode_gravar, use_container_width=True, help="Preencha o Nome da Proposta, Temperatura, Status, Segmento e Unidade de MO para habilitar"):
                    idx_editando = st.session_state.get("proposta_idx_editando")
                    if idx_editando: sucesso = atualizar_proposta_modificada(idx_editando, nome_proposta, total_mensal, total_setup, forma_limpa, parcela_escolhida, txt_parcela, st.session_state["carrinho"], val_desc_p, val_desc_a, val_desc_i, temperatura_escolhida, status_escolhido)
                    else: sucesso = salvar_proposta(st.session_state["lead_dados"].get("nome", ""), nome_proposta, st.session_state["nome_usuario"], st.session_state["email_usuario"], total_mensal, total_setup, forma_limpa, parcela_escolhida, txt_parcela, st.session_state["carrinho"], val_desc_p, val_desc_a, val_desc_i, temperatura_escolhida, status_escolhido)
                    if sucesso:
                        if status_escolhido == "Aprovada":
                            df_us = carregar_usuarios()
                            df_us['email_c'] = df_us['email'].astype(str).str.strip().str.lower()
                            emails_destino = obter_emails_gestores(df_us, st.session_state['unidade_usuario'], st.session_state['vertical_usuario'])
                            if emails_destino:
                                eqp_fmt = f"R$ {(bruto_produtos * (1 - (val_desc_p/100))):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
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
                st.write("#### 📤 Ações da Proposta")
                
                c_gerar, c_email, c_wa, c_contrato, c_zapsign = st.columns(5)
                
                with c_gerar:
                    st.download_button(
                        label="📄 Download Proposta",
                        data=html_prop,
                        file_name=f"Proposta_{st.session_state['lead_dados'].get('nome', '')}.html",
                        mime="text/html",
                        use_container_width=True,
                        type="primary"
                    )
                
                with c_email:
                    if st.button("✉️ Enviar p/ E-mail", disabled=not tem_email, help="Falta E-mail no cadastro do cliente." if not tem_email else f"Enviar para {email_cliente}", use_container_width=True, type="primary"):
                        if enviar_email_proposta_cliente(st.session_state["lead_dados"].get("nome", ""), email_cliente, html_prop):
                            st.toast(f"E-mail enviado com sucesso para {email_cliente}! ✉️")
                            
                with c_wa:
                    if tem_telefone:
                        st.link_button("💬 Enviar p/ WhatsApp", wa_url, use_container_width=True, type="primary")
                    else:
                        st.button("💬 Enviar p/ WhatsApp", disabled=True, help="Falta Telefone no cadastro do cliente.", use_container_width=True, type="primary")
                
                with c_contrato:
                    docx_bytes, erro_docx = gerar_documento_contrato(st.session_state["lead_dados"], mrr_formatado, setup_txt, condicao_txt, st.session_state["carrinho"])
                    if docx_bytes:
                        if hasattr(st, "popover"):
                            caixa_pdf = st.popover("📄 PDF Contrato", use_container_width=True)
                            with caixa_pdf:
                                if st.button("🔄 Iniciar Conversão para PDF", use_container_width=True):
                                    with st.spinner("Convertendo na nuvem..."):
                                        pdf_bytes, err = converter_para_pdf_na_nuvem(docx_bytes)
                                        if pdf_bytes:
                                            st.download_button("📥 Baixar PDF Agora", data=pdf_bytes, file_name=f"Contrato_{st.session_state['lead_dados'].get('nome', '')}.pdf", mime="application/pdf", use_container_width=True, type="primary")
                                        else:
                                            st.error(err)
                        else:
                            st.download_button("📝 Download Contrato (DOCX)", data=docx_bytes, file_name=f"Contrato_{st.session_state['lead_dados'].get('nome', '')}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, type="primary")
                    else:
                        st.button("📝 Erro no Contrato", disabled=True, help=str(erro_docx), use_container_width=True, type="primary")

                with c_zapsign:
                    if docx_bytes:
                        if st.button("✍️ Assinar Contrato", type="primary", use_container_width=True, help="Disparar via ZapSign"):
                            sucesso, retorno = enviar_para_zapsign(docx_bytes, st.session_state["lead_dados"].get("nome", ""), email_cliente, telefone_cliente)
                            if sucesso:
                                st.success("Enviado para ZapSign!")
                            else:
                                st.error(retorno)
                    else:
                        st.button("✍️ Assinar Contrato", type="primary", disabled=True, use_container_width=True)

            else: st.info("Adicione itens no carrinho para gerar o parcelamento.")
        except Exception as e: st.error(f"❌ Erro na conexão: {e}")
