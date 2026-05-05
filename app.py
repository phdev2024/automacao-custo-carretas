import streamlit as st
import pandas as pd
from datetime import datetime
from processador import extrair_dados_xml, calcular_custos
from banco import salvar_no_banco, consultar_historico, consultar_entregas
import io  # Biblioteca para lidar com arquivos na memória

def formato_brasil(valor):
    # Transforma o número em string no formato 1,234.56
    v = f"{valor:,.2f}"
    # Inverte: vira 1.234,56
    return v.replace(",", "X").replace(".", ",").replace("X", ".")

def converter_para_excel(df):
    output = io.BytesIO()
    # Cria o arquivo Excel usando o motor xlsxwriter
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio_Logistica')
    return output.getvalue()

st.set_page_config(page_title="Gestor Logístico Ortobom", layout="wide", page_icon="🚚")

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

def resetar_formulario():
    st.session_state["uploader_key"] += 1

data_hoje = datetime.now().strftime("%d/%m/%Y")

st.title("🚚 Gestão de Entregas - Ortobom ")

aba_novo, aba_historico = st.tabs(["🆕 Novo Lote", "📊 Dashboard e Status"])

with aba_novo:
    with st.sidebar:
        st.header("⚙️ Configurações")
        p_base = st.number_input("Taxa Base (%)", value=8.0) / 100
        p_logcare = st.number_input("Taxa Logcare (%)", value=7.0) / 100
        st.button("🧹 Limpar Tudo", on_click=resetar_formulario)

    id_lote = st.text_input("Identificação do Lote:", value=data_hoje, key=f"lote_{st.session_state['uploader_key']}")
    arquivos = st.file_uploader("Upload XMLs", type=["xml"], accept_multiple_files=True, key=f"xml_{st.session_state['uploader_key']}")

    if st.button("🚀 Processar e Sincronizar"):
        if id_lote and arquivos:
            with st.status("Sincronizando...", expanded=True) as status:
                lista = []
                data_proc = datetime.now().strftime("%d/%m/%Y %H:%M")
                for arq in arquivos:
                    d = extrair_dados_xml(arq)
                    # ... dentro do loop for arq in arquivos:
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
                            "Endereco": d["Endereco_Destino"], 
                            "KM": d["KM_Estimado"],             
                            "Lat": d["Latitude"],               
                            "Long": d["Longitude"]              
                        })
                if lista:
                    salvar_no_banco(pd.DataFrame(lista))
                    status.update(label="✅ Sincronizado!", state="complete")
                    st.success("Lote enviado com sucesso.")
                    st.button("🔄 Próxima Importação", on_click=resetar_formulario)

with aba_historico:
    df_h = consultar_historico()
    df_entregas = consultar_entregas()
    
    if not df_h.empty:
        st.markdown("### 🔍 Filtros de Visualização")
        col_f1, col_f2 = st.columns(2)
        
        with col_f1:
            lotes_disponiveis = ["Todos"] + list(df_h['Lote'].unique())
            escolha_lote = st.selectbox("Filtrar por Lote:", lotes_disponiveis)
        
        with col_f2:
            status_disponiveis = ["Todos", "✅ Entregue", "⏳ Pendente"]
            escolha_status = st.selectbox("Filtrar por Status:", status_disponiveis)

        # 1. Lógica de Status
        def tratar(v): return str(v).strip().split('.')[0]
        notas_ok = df_entregas['Nota Fiscal'].apply(tratar).tolist() if not df_entregas.empty else []
        df_h['Status'] = df_h['Nota'].apply(lambda x: "✅ Entregue" if tratar(x) in notas_ok else "⏳ Pendente")

        # 2. Aplicando os Filtros
        df_filtrado = df_h.copy()
        if escolha_lote != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Lote'] == escolha_lote]
        if escolha_status != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Status'] == escolha_status]

        # 3. Limpeza e Cálculos (Baseado no que foi filtrado)
        def limpar_moeda(v):
            if isinstance(v, str): v = v.replace('R$', '').replace('.', '').replace(',', '.').strip()
            try: return float(v)
            except: return 0.0

        v_total_f = df_filtrado['Valor_Total'].apply(limpar_moeda).sum()
        c_total_f = df_filtrado['Custo_Total_Nota'].apply(limpar_moeda).sum()
        n_entregues_f = len(df_filtrado[df_filtrado['Status'] == "✅ Entregue"])
        eficiencia_f = (n_entregues_f / len(df_filtrado)) * 100 if len(df_filtrado) > 0 else 0

        # 4. Botão de Exportar (Linkado ao resultado do filtro)
        dados_excel = converter_para_excel(df_filtrado)
        st.download_button(
            label="📥 Exportar Relatório para Excel",
            data=dados_excel,
            file_name=f"Relatorio_Ortobom_{datetime.now().strftime('%d_%m_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # 5. Visualização das Métricas
        # --- Lógica de Cores para Eficiência ---
        cor_eficiencia = "normal" if eficiencia_f >= 90 else "inverse" if eficiencia_f < 75 else "off"
        msg_eficiencia = "Excelente" if eficiencia_f >= 90 else "Abaixo da Meta" if eficiencia_f < 75 else "Na Média"

        st.markdown("#### 💰 Resumo Financeiro")
        m1, m2, m3 = st.columns(3)

        # Aplicando o formato brasileiro nos valores financeiros
        m1.metric("Faturamento", f"R$ {formato_brasil(v_total_f)}")
        m2.metric("Custo Total", f"R$ {formato_brasil(c_total_f)}")
        m3.metric("Notas Total", len(df_filtrado))

        st.markdown("#### 📦 Operacional")
        s1, s2, s3 = st.columns(3)

        # O Delta traz a cor e o contexto visual
        s1.metric("Entregues", n_entregues_f, delta="Concluído", delta_color="normal")
        s2.metric("Pendentes", len(df_filtrado) - n_entregues_f, delta="Aguardando", delta_color="inverse")
        s3.metric("Eficiência", f"{eficiencia_f:.1f}%", delta=msg_eficiencia, delta_color=cor_eficiencia)

        # Mostra a tabela final organizada
        # Mostra a tabela final organizada
        cols_ordenadas = ['Status'] + [c for c in df_filtrado.columns if c != 'Status']
        
        # Cria uma visualização renomeando os cabeçalhos para incluir as unidades
        df_visual = df_filtrado[cols_ordenadas].rename(columns={
            "KM": "Distância (KM)",
            "Valor_Total": "Valor Total (R$)",
            "Custo_Base": "Custo Base (R$)",
            "Custo_Logcare": "Custo Logcare (R$)",
            "Custo_Total_Nota": "Custo Total (R$)"
        })
        
        st.dataframe(df_visual, use_container_width=True)