import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st

def conectar_google_sheets():
    # Escopos para acessar o Google Drive e Planilhas
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # Tenta ler das 'Secrets' do Streamlit (Modo Nuvem/Seguro)
        google_creds = st.secrets["google_sales_creds"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(google_creds), scope)
    except:
        # Se não achar nas Secrets, tenta o arquivo local (Para seus testes no VS Code)
        creds = ServiceAccountCredentials.from_json_keyfile_name('credenciais.json', scope)
    
    client = gspread.authorize(creds)
    # Use o nome correto da sua planilha
    return client.open("Banco_Dados_Ortobom")

def salvar_no_banco(df):
    try:
        planilha = conectar_google_sheets()
        aba = planilha.get_worksheet(0)
        aba.append_rows(df.values.tolist())
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def consultar_historico():
    try:
        planilha = conectar_google_sheets()
        aba = planilha.get_worksheet(0)
        dados = aba.get_all_records()
        return pd.DataFrame(dados) if dados else pd.DataFrame()
    except Exception as e:
        st.error(f"Erro no histórico: {e}")
        return pd.DataFrame()

def consultar_entregas():
    try:
        planilha = conectar_google_sheets()
        aba = planilha.worksheet("Entregas")
        dados = aba.get_all_records()
        return pd.DataFrame(dados)
    except:
        return pd.DataFrame()