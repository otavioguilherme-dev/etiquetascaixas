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

# --- FUNÇÃO 1: EXTRAIR DADOS DO PDF ---
def extrair_pedidos(ficheiro_pdf):
    linhas_tabela = []
    num_pedido = ""
    
    with pdfplumber.open(ficheiro_pdf) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            if texto:
                match_dao = re.search(r'\b(DAO-\d+/\d+)\b', texto)
                if match_dao:
                    num_pedido = match_dao.group(1)
                else:
                    match_alt = re.search(r'Pedido de Venda N°\.\s*\n?([^\n]+)', texto, re.IGNORECASE)
                    if match_alt:
                        num_pedido = match_alt.group(1).strip()

            tabela = page.extract_table()
            if tabela:
                for linha in tabela:
                    if linha and len(linha) > 5: 
                        linhas_tabela.append(linha)
    
    if not linhas_tabela:
        return None, num_pedido
        
    cabecalho_seguro = [str(col).replace('\n', ' ').strip() if col else f"Coluna_{i}" for i, col in enumerate(linhas_tabela[0])]
    df = pd.DataFrame(linhas_tabela[1:], columns=cabecalho_seguro)
    return df, num_pedido

# --- FUNÇÃO 2: APLICAR REGRAS E ENCONTRAR SKU ---
def calcular_etiquetas(df):
    etiquetas_para_imprimir = []
    
    col_qtd = next((col for col in df.columns if 'Qtd' in str(col)), None)
    
    if not col_qtd:
        st.error("Não foi possível encontrar a coluna 'Qtd'.")
        return []

    for index, row in df.iterrows():
        sku = None
        
        for col in df.columns:
            celula = str(row[col]).replace('\n', ' ').strip()
            match = re.search(r'\b\d{6,10}\b', celula)
            if match:
                sku = match.group(0) 
                break 
        
        if not sku:
            continue 
            
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

# --- FUNÇÃO 3: GERAR O PDF FINAL 15x10 cm (HORIZONTAL) ---
def gerar_pdf_etiquetas(lista_skus, num_pedido=""):
    buffer = io.BytesIO()
    
    largura = 150 * mm
    altura = 100 * mm
    c = canvas.Canvas(buffer, pagesize=(largura, altura))
    data_hoje = datetime.today().strftime("%d/%m/%Y")
    
    for sku in lista_skus:
        c.setFont("Helvetica-Bold", 100)
        c.drawCentredString(largura / 2.0, 55 * mm, str(sku))
        
        c.setFont("Helvetica", 36)
        c.drawCentredString(largura / 2.0, 25 * mm, data_hoje)
        
        if num_pedido:
            c.setFont("Helvetica", 24)
            c.drawCentredString(largura / 2.0, 10 * mm, num_pedido)
        
        c.showPage() 
        
    c.save()
    buffer.seek(0)
    return buffer

# --- INTERFACE DO STREAMLIT COM ABAS ---
aba1, aba2 = st.tabs(["📄 Automático (PDF mERP)", "✍️ Manual (Lote Avulso)"])

# ====== ABA 1: AUTOMÁTICO ======
with aba1:
    st.write("Faça o upload do Pedido de Venda em PDF para gerar as etiquetas em lote.")
    arquivo_upload = st.file_uploader("Arraste o PDF aqui", type=["pdf"])

    if arquivo_upload is not None:
        try:
            df_extraido, num_pedido = extrair_pedidos(arquivo_upload)
            
            if df_extraido is not None:
                lista_final = calcular_etiquetas(df_extraido)
                
                if lista_final:
                    st.success(f"Sucesso! {len(lista_final)} etiquetas calculadas.")
                    if num_pedido:
                        st.info(f"📄 Número Identificado: {num_pedido}")
                    
                    st.dataframe(pd.DataFrame({"SKUs a Imprimir": lista_final}))
                    
                    pdf_pronto = gerar_pdf_etiquetas(lista_final, num_pedido)
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
            st.code(traceback.format_exc())

# ====== ABA 2: MANUAL (TABELA INTERATIVA) ======
with aba2:
    st.write("Digite os SKUs na tabela abaixo. Para adicionar novas linhas, preencha a última linha vazia ou clique nela. Você também pode colar dados direto do Excel!")
    
    # Cria uma tabela inicial com algumas linhas em branco
    df_inicial = pd.DataFrame([{"SKU": "", "Quantidade": 1} for _ in range(3)])
    
    # O st.data_editor permite que o usuário edite a tabela livremente na tela
    df_editado = st.data_editor(
        df_inicial,
        column_config={
            "SKU": st.column_config.TextColumn("Código / SKU", width="large"),
            "Quantidade": st.column_config.NumberColumn("Quantidade de Etiquetas", min_value=1, step=1)
        },
        num_rows="dynamic", # Permite adicionar ou excluir linhas
        hide_index=True,
        use_container_width=True
    )

    # Processa os dados preenchidos na tabela
    lista_manual = []
    for index, row in df_editado.iterrows():
        sku_preenchido = str(row["SKU"]).strip()
        # Ignora linhas que o usuário não preencheu
        if sku_preenchido and sku_preenchido.lower() not in ["none", "nan", ""]:
            try:
                qtd_preenchida = int(row["Quantidade"])
            except:
                qtd_preenchida = 1
            
            # Adiciona o SKU à lista final multiplicando pela quantidade
            lista_manual.extend([sku_preenchido] * qtd_preenchida)

    # Se tiver alguma etiqueta válida na lista, mostra o botão de download
    if len(lista_manual) > 0:
        pdf_manual_pronto = gerar_pdf_etiquetas(lista_manual, "")
        
        st.success(f"Tabela lida com sucesso! {len(lista_manual)} etiqueta(s) pronta(s) para impressão.")
        st.download_button(
            label=f"📥 Baixar {len(lista_manual)} Etiqueta(s) Avulsa(s) (15x10)",
            data=pdf_manual_pronto,
            file_name=f"etiquetas_avulsas_{datetime.today().strftime('%Y%m%d')}.pdf",
            mime="application/pdf"
        )
