import streamlit as st
import pdfplumber
import pandas as pd
import io
import re  # <--- Nova biblioteca adicionada para encontrar os 6 dígitos
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gerador de Etiquetas - Borrachas", page_icon="📦")
st.title("📦 Gerador Automático de Etiquetas")
st.write("Faça o upload do Pedido de Venda em PDF para gerar as etiquetas das caixas.")

# --- FUNÇÃO 1: EXTRAIR DADOS DO PDF ---
def extrair_pedidos(ficheiro_pdf):
    linhas_tabela = []
    
    with pdfplumber.open(ficheiro_pdf) as pdf:
        for page in pdf.pages:
            tabela = page.extract_table()
            if tabela:
                for linha in tabela:
                    # Filtra linhas vazias
                    if linha and len(linha) > 5: 
                        linhas_tabela.append(linha)
    
    if not linhas_tabela:
        return None
        
    df = pd.DataFrame(linhas_tabela[1:], columns=linhas_tabela[0])
    return df

# --- FUNÇÃO 2: APLICAR REGRAS DE QUANTIDADE E LIMPAR SKU ---
def calcular_etiquetas(df):
    etiquetas_para_imprimir = []
    
    # Procura as colunas corretas
    col_referencia = next((col for col in df.columns if 'Referência' in str(col) or 'Item' in str(col)), None)
    col_qtd = next((col for col in df.columns if 'Qtd' in str(col)), None)
    
    if not col_referencia or not col_qtd:
        st.error("Não foi possível encontrar as colunas no PDF.")
        return []

    for index, row in df.iterrows():
        # Transforma o texto da célula em string
        celula_ref = str(row[col_referencia]).replace('\n', ' ').strip()
        
        # MAGIA AQUI: Procura especificamente por um número de 6 dígitos (o SKU)
        match_sku = re.search(r'\b\d{6}\b', celula_ref)
        
        if match_sku:
            sku = match_sku.group(0) # Pega o SKU de 6 dígitos encontrado
        else:
            # Fallback caso não encontre 6 dígitos exatos (pega o maior número)
            partes = celula_ref.split()
            sku = partes[0] if partes else ""
            for p in partes:
                if len(p) > 3: 
                    sku = p
                    break
        
        qtd_str = str(row[col_qtd]).replace(',', '.')
        
        try:
            qtd = float(qtd_str)
            # Aplica a sua regra de negócio
            if qtd == 5.0:
                qtd_etiquetas = 1
            elif qtd >= 10.0:
                qtd_etiquetas = int(qtd // 10)
            else:
                qtd_etiquetas = 0 # Ignora compras avulsas
                
            for _ in range(qtd_etiquetas):
                etiquetas_para_imprimir.append(sku)
        except ValueError:
            pass 
            
    return etiquetas_para_imprimir

# --- FUNÇÃO 3: GERAR O PDF FINAL COM REPORTLAB ---
def gerar_pdf_etiquetas(lista_skus):
    buffer = io.BytesIO()
    
    # Tamanho da etiqueta térmica (100mm largura x 50mm altura)
    largura = 100 * mm
    altura = 50 * mm
    c = canvas.Canvas(buffer, pagesize=(largura, altura))
    
    data_hoje = datetime.today().strftime("%d/%m/%Y")
    
    for sku in lista_skus:
        # Desenha o SKU no centro
        c.setFont("Helvetica-Bold", 36)
        c.drawCentredString(largura / 2.0, (altura / 2.0) + 5 * mm, sku)
        
        # Desenha a data logo abaixo
        c.setFont("Helvetica", 16)
        c.drawCentredString(largura / 2.0, (altura / 2.0) - 12 * mm, f"Data: {data_hoje}")
        
        c.showPage() 
        
    c.save()
    buffer.seek(0)
    return buffer

# --- INTERFACE DO STREAMLIT ---
arquivo_upload = st.file_uploader("Arraste o PDF do mERP aqui", type=["pdf"])

if arquivo_upload is not None:
    st.info("A ler o documento...")
    
    df_extraido = extrair_pedidos(arquivo_upload)
    
    if df_extraido is not None:
        lista_final = calcular_etiquetas(df_extraido)
        
        if lista_final:
            st.success(f"Sucesso! {len(lista_final)} etiquetas calculadas.")
            
            st.write("Prévia das etiquetas geradas:")
            st.dataframe(pd.DataFrame({"SKUs a Imprimir": lista_final}))
            
            pdf_pronto = gerar_pdf_etiquetas(lista_final)
            st.download_button(
                label="📥 Baixar Etiquetas em PDF",
                data=pdf_pronto,
                file_name=f"etiquetas_{datetime.today().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )
        else:
            st.warning("Nenhuma etiqueta necessária de acordo com as regras.")
    else:
        st.error("Erro ao ler as tabelas do PDF.")
