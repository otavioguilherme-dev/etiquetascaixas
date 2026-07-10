import streamlit as st
import pdfplumber
import pandas as pd
import io
import re
import traceback
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerador de Etiquetas - Borrachas", page_icon="📦")
st.title("📦 Gerador Automático de Etiquetas")
st.write("Faça o upload do Pedido de Venda em PDF para gerar as etiquetas das caixas.")

# --- FUNÇÃO 1: EXTRAIR DADOS DO PDF (COM PROTEÇÃO) ---
def extrair_pedidos(ficheiro_pdf):
    linhas_tabela = []
    
    with pdfplumber.open(ficheiro_pdf) as pdf:
        for page in pdf.pages:
            tabela = page.extract_table()
            if tabela:
                for linha in tabela:
                    if linha and len(linha) > 5: 
                        linhas_tabela.append(linha)
    
    if not linhas_tabela:
        return None
        
    # PROTEÇÃO: Garante que o nome das colunas não sejam nulos ou repetidos, o que quebra o Pandas
    cabecalho_seguro = [str(col).replace('\n', ' ').strip() if col else f"Coluna_Vazia_{i}" for i, col in enumerate(linhas_tabela[0])]
    df = pd.DataFrame(linhas_tabela[1:], columns=cabecalho_seguro)
    return df

# --- FUNÇÃO 2: APLICAR REGRAS DE QUANTIDADE E LIMPAR SKU ---
def calcular_etiquetas(df):
    etiquetas_para_imprimir = []
    
    col_referencia = next((col for col in df.columns if 'Referência' in str(col) or 'Item' in str(col)), None)
    col_qtd = next((col for col in df.columns if 'Qtd' in str(col)), None)
    
    if not col_referencia or not col_qtd:
        st.error(f"Colunas não encontradas. Colunas que o sistema leu: {list(df.columns)}")
        return []

    for index, row in df.iterrows():
        celula_ref = str(row[col_referencia]).replace('\n', ' ').strip()
        match_sku = re.search(r'\b\d{6}\b', celula_ref)
        
        if match_sku:
            sku = match_sku.group(0) 
        else:
            partes = celula_ref.split()
            sku = partes[0] if partes else ""
            for p in partes:
                if len(p) > 3: 
                    sku = p
                    break
        
        qtd_str = str(row[col_qtd]).replace(',', '.')
        
        try:
            qtd = float(qtd_str)
            if qtd == 5.0:
                qtd_etiquetas = 1
            elif qtd >= 10.0:
                qtd_etiquetas = int(qtd // 10)
            else:
                qtd_etiquetas = 0 
                
            for _ in range(qtd_etiquetas):
                etiquetas_para_imprimir.append(sku)
        except ValueError:
            pass 
            
    return etiquetas_para_imprimir

# --- FUNÇÃO 3: GERAR O PDF FINAL COM REPORTLAB ---
def gerar_pdf_etiquetas(lista_skus):
    buffer = io.BytesIO()
    largura = 100 * mm
    altura = 50 * mm
    c = canvas.Canvas(buffer, pagesize=(largura, altura))
    data_hoje = datetime.today().strftime("%d/%m/%Y")
    
    for sku in lista_skus:
        c.setFont("Helvetica-Bold", 36)
        c.drawCentredString(largura / 2.0, (altura / 2.0) + 5 * mm, sku)
        c.setFont("Helvetica", 16)
        c.drawCentredString(largura / 2.0, (altura / 2.0) - 12 * mm, f"Data: {data_hoje}")
        c.showPage() 
        
    c.save()
    buffer.seek(0)
    return buffer

# --- INTERFACE DO STREAMLIT COM CAPTURA DE ERRO ---
arquivo_upload = st.file_uploader("Arraste o PDF do mERP aqui", type=["pdf"])

if arquivo_upload is not None:
    try:
        st.info("A ler o documento...")
        df_extraido = extrair_pedidos(arquivo_upload)
        
        if df_extraido is not None:
            lista_final = calcular_etiquetas(df_extraido)
            
            if lista_final:
                st.success(f"Sucesso! {len(lista_final)} etiquetas calculadas.")
                st.dataframe(pd.DataFrame({"SKUs a Imprimir": lista_final}))
                pdf_pronto = gerar_pdf_etiquetas(lista_final)
                st.download_button(
                    label="📥 Baixar Etiquetas em PDF",
                    data=pdf_pronto,
                    file_name=f"etiquetas_{datetime.today().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf"
                )
            else:
                st.warning("Nenhuma etiqueta gerada. Verifique as quantidades.")
        else:
            st.error("Erro ao extrair a tabela do PDF.")
            
    except Exception as e:
        st.error("🚨 Ocorreu um erro interno durante o processamento do PDF.")
        st.code(traceback.format_exc()) # Isso vai imprimir o erro técnico exato na tela
