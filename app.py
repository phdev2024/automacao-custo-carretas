import streamlit as st
import pandas as pd
from datetime import datetime
from processador import extrair_dados_xml, calcular_custos
from banco import salvar_no_banco, consultar_historico, consultar_entregas
import io

def formato_brasil(valor):
    # Transforma o número em string no formato 1,234.56
    v = f"{valor:,.2f}"
    # Inverte: vira 1.234,56
    return v.replace(",", "X").replace(".", ",").replace("X", ".")

def converter_para_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio_Logistica')
    return output.getvalue()

st.set_page_config(page_title="Gestor Logístico Ortobom", layout="wide", page_icon="🚚")

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

def resetar_formulario():
    st.session_state["uploader_key"] += 1

data_hoje = datetime.now().strftime("%d/%m/%Y")

st.title("🚚 Gestão de Entregas - Ortobom")

# =====================================================================
# ⚙️ BARRA LATERAL: ENTRADA DE DADOS E PROCESSAMENTO
# =====================================================================
with st.sidebar:
    st.header("📥 Upload de Lote")
    
    id_lote = st.text_input("Identificação do Lote:", value=data_hoje, key=f"lote_{st.session_state['uploader_key']}")
    arquivos = st.file_uploader("Upload XMLs", type=["xml"], accept_multiple_files=True, key=f"xml_{st.session_state['uploader_key']}")
    
    st.markdown("---")
    st.header("⚙️ Configurações de Taxas")
    p_base = st.number_input("Taxa Base (%)", value=8.0) / 100
    p_logcare = st.number_input("Taxa Logcare (%)", value=7.0) / 100
    
    st.markdown("<br>", unsafe_allow_html=True)
    bt_processar = st.button("🚀 Processar e Sincronizar", use_container_width=True)
    st.button("🧹 Limpar Painel de Upload", on_click=resetar_formulario, use_container_width=True)

    if bt_processar:
        if id_lote and arquivos:
            with st.status("Sincronizando...", expanded=True) as status:
                lista = []
                data_proc = datetime.now().strftime("%d/%m/%Y %H:%M")
                for arq in arquivos:
                    d = extrair_dados_xml(arq)
                    if d:
                        d = calcular_custos(d, p_base, p_logcare)
                        lista.append({
                            "Lote": id_lote, 
                            "Data_Processamento": data_proc,
                            "Nota": str(d["Nota"]), 
                            "Emissao": d["Emissao"],
                            "Emitente": d["Emitente"], 
                            "Valor_Total": round(float(d["Valor_Total"]), 2),
                            "Custo_Base": round(float(d["Custo_Base"]), 2), 
                            "Custo_Logcare": round(float(d["Custo_Logcare"]), 2),
                            "Custo_Total_Nota": round(float(d["Custo_Total_Nota"]), 2),
                            "Endereco": d.get("Endereco_Destino", ""),
                            "KM": round(float(d.get("KM_Estimado", 0)), 2),             
                            "Lat": float(d.get("Latitude", 0)),               
                            "Long": float(d.get("Longitude", 0))              
                        })
                if lista:
                    salvar_no_banco(pd.DataFrame(lista))
                    status.update(label="✅ Sincronizado!", state="complete")
                    st.success("Lote enviado com sucesso.")
                    st.rerun()

# =====================================================================
# 📊 PÁGINA PRINCIPAL: DASHBOARD E STATUS (SEMPRE VISÍVEL)
# =====================================================================
df_h = consultar_historico()
df_entregas = consultar_entregas()

if not df_h.empty:
    st.markdown("### 🔍 Filtros de Visualização")
    col_f1, col_f2 = st.columns(2)
    
    with col_f1:
        lotes_disponiveis = ["Todos"] + list(df_h['Lote'].unique())
        escolha_lote = st.selectbox("Filtrar por Lote:", lotes_disponiveis)
    
    with col_f2:
        # 1. Adicionamos "🚫 Cancelado" na lista de filtros da tela
        status_disponiveis = ["Todos", "✅ Entregue", "⏳ Pendente", "🚨 Devolução Fábrica", "❌ Recusado", "🚫 Cancelado"]
        escolha_status = st.selectbox("Filtrar por Status:", status_disponiveis)

    # Lógica Avançada para capturar Devoluções, Recusas e Cancelamentos
    def definir_status(linha_nota, df_entregas):
        nota_tratada = str(linha_nota).strip().split('.')[0]
        if df_entregas.empty:
            return "⏳ Pendente"
            
        col_nf = 'Nota Fiscal' if 'Nota Fiscal' in df_entregas.columns else df_entregas.columns[0]
        match_entrega = df_entregas[df_entregas[col_nf].astype(str).str.strip().str.split('.').str[0] == nota_tratada]
        
        if not match_entrega.empty:
            conteudo_linha = str(match_entrega.values).lower()
            
            # Checagem 1: Procura por "devolu"
            if "devolu" in conteudo_linha:
                return "🚨 Devolução Fábrica"
                
            # Checagem 2: Procura por "recusa"
            if "recusa" in conteudo_linha:
                return "❌ Recusado"
                
            # Checagem 3: NOVA REGRA - Procura por "cancela"
            if "cancela" in conteudo_linha:
                return "🚫 Cancelado"
                
            return "✅ Entregue"
        
        return "⏳ Pendente"

    df_h['Status'] = df_h['Nota'].apply(lambda x: definir_status(x, df_entregas))

    df_filtrado = df_h.copy()
    if escolha_lote != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Lote'] == escolha_lote]
    if escolha_status != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Status'] == escolha_status]

    def limpar_moeda(v):
        if isinstance(v, str): v = v.replace('R$', '').replace('.', '').replace(',', '.').strip()
        try: return float(v)
        except: return 0.0

    v_total_f = df_filtrado['Valor_Total'].apply(limpar_moeda).sum()
    c_total_f = df_filtrado['Custo_Total_Nota'].apply(limpar_moeda).sum()
    
    # Contadores do painel operacional
    n_entregues_f = len(df_filtrado[df_filtrado['Status'] == "✅ Entregue"])
    n_devolucoes_f = len(df_filtrado[df_filtrado['Status'] == "🚨 Devolução Fábrica"])
    n_recusados_f = len(df_filtrado[df_filtrado['Status'] == "❌ Recusado"])
    n_cancelados_f = len(df_filtrado[df_filtrado['Status'] == "🚫 Cancelado"]) # Novo contador
    
    eficiencia_f = (n_entregues_f / len(df_filtrado)) * 100 if len(df_filtrado) > 0 else 0

    dados_excel = converter_para_excel(df_filtrado)
    st.download_button(
        label="📥 Exportar Relatório Filtrado para Excel",
        data=dados_excel,
        file_name=f"Relatorio_Ortobom_{datetime.now().strftime('%d_%m_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    cor_eficiencia = "normal" if eficiencia_f >= 90 else "inverse" if eficiencia_f < 75 else "off"
    msg_eficiencia = "Excelente" if eficiencia_f >= 90 else "Abaixo da Meta" if eficiencia_f < 75 else "Na Média"

    st.markdown("#### 💰 Resumo Financeiro")
    m1, m2, m3 = st.columns(3)
    m1.metric("Faturamento", f"R$ {formato_brasil(v_total_f)}")
    m2.metric("Custo Total", f"R$ {formato_brasil(c_total_f)}")
    m3.metric("Notas Total", len(df_filtrado))

    st.markdown("#### 📦 Operacional")
    # Ajustamos para 6 colunas para acomodar o painel perfeitamente na horizontal
    s1, s2, s3, s4, s5, s6 = st.columns(6)
    s1.metric("Entregues", n_entregues_f, delta="Concluído", delta_color="normal")
    s2.metric("Devoluções", n_devolucoes_f, delta="Retorno Fábrica", delta_color="off")
    s3.metric("Recusados", n_recusados_f, delta="Cliente Recusou", delta_color="off")
    s4.metric("Cancelados", n_cancelados_f, delta="NF Cancelada", delta_color="off") # Nova Métrica
    s5.metric("Pendentes", len(df_filtrado) - n_entregues_f - n_devolucoes_f - n_recusados_f - n_cancelados_f, delta="Aguardando", delta_color="inverse")
    s6.metric("Eficiência", f"{eficiencia_f:.1f}%", delta=msg_eficiencia, delta_color=cor_eficiencia)

    # ---------------------------------------------------------------------
    # FRONTEND: MAQUIAGEM VISUAL (Exibição sem quebras no Arrow)
    # ---------------------------------------------------------------------
    cols_ordenadas = ['Status'] + [c for c in df_filtrado.columns if c != 'Status']
    df_visual = df_filtrado[cols_ordenadas].copy()

    # Força a conversão rápida para string para evitar conflitos no Streamlit
    for col in df_visual.columns:
        df_visual[col] = df_visual[col].astype(str)

    df_visual = df_visual.rename(columns={
        "KM": "Distância (KM)",
        "Valor_Total": "Valor Total (R$)",
        "Custo_Base": "Custo Base (R$)",
        "Custo_Logcare": "Custo Logcare (R$)",
        "Custo_Total_Nota": "Custo Total (R$)"
    })
    
    def formatar_para_tela(v, prefixo=""):
        try:
            if v is None or v == "" or v == "nan": return f"{prefixo} 0,00".strip()
            if "R$" in str(v): return v
            num = float(str(v).replace(',', '.'))
            return f"{prefixo} {formato_brasil(num)}".strip()
        except:
            return str(v)

    cols_fin = ["Valor Total (R$)", "Custo Base (R$)", "Custo Logcare (R$)", "Custo Total (R$)"]
    for col in cols_fin:
        if col in df_visual.columns:
            df_visual[col] = df_visual[col].apply(lambda x: formatar_para_tela(x, "R$"))

    if "Distância (KM)" in df_visual.columns:
        df_visual["Distância (KM)"] = df_visual["Distância (KM)"].apply(lambda x: formatar_para_tela(x))

    st.dataframe(df_visual, use_container_width=True)
else:
    st.info("Nenhum dado encontrado no histórico. Use a barra lateral para processar um novo lote de XMLs.")