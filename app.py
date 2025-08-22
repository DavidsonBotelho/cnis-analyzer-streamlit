import streamlit as st
import pandas as pd
import re
from datetime import datetime
import io

# ----------------------------------------------------------------------
# TABELAS INSS - Alíquotas e Tetos por período (do seu código original)
# ----------------------------------------------------------------------
INSS_TABLES = {
    "2025-01": {
        "ranges": [
            {"min": 0.00, "max": 1518.00, "aliquot": 0.075},
            {"min": 1518.01, "max": 2793.88, "aliquot": 0.09},
            {"min": 2793.89, "max": 4190.83, "aliquot": 0.12},
            {"min": 4190.84, "max": 8157.41, "aliquot": 0.14}
        ],
        "ceiling": 8157.41
    },
    "2024-01": {
        "ranges": [
            {"min": 0.00, "max": 1412.00, "aliquot": 0.075},
            {"min": 1412.01, "max": 2666.68, "aliquot": 0.09},
            {"min": 2666.69, "max": 4000.03, "aliquot": 0.12},
            {"min": 4000.04, "max": 7786.02, "aliquot": 0.14}
        ],
        "ceiling": 7786.02
    },
    "2023-05": {
        "ranges": [
            {"min": 0.00, "max": 1320.00, "aliquot": 0.075},
            {"min": 1320.01, "max": 2571.29, "aliquot": 0.09},
            {"min": 2571.30, "max": 3856.94, "aliquot": 0.12},
            {"min": 3856.95, "max": 7507.49, "aliquot": 0.14}
        ],
        "ceiling": 7507.49
    },
    "2023-01": {
        "ranges": [
            {"min": 0.00, "max": 1302.00, "aliquot": 0.075},
            {"min": 1302.01, "max": 2571.29, "aliquot": 0.09},
            {"min": 2571.30, "max": 3856.94, "aliquot": 0.12},
            {"min": 3856.95, "max": 7507.49, "aliquot": 0.14}
        ],
        "ceiling": 7507.49
    },
    "2022-01": {
        "ranges": [
            {"min": 0.00, "max": 1212.00, "aliquot": 0.075},
            {"min": 1212.01, "max": 2427.35, "aliquot": 0.09},
            {"min": 2427.36, "max": 3641.03, "aliquot": 0.12},
            {"min": 3641.04, "max": 7087.22, "aliquot": 0.14}
        ],
        "ceiling": 7087.22
    },
    "2021-01": {
        "ranges": [
            {"min": 0.00, "max": 1100.00, "aliquot": 0.075},
            {"min": 1100.01, "max": 2203.48, "aliquot": 0.09},
            {"min": 2203.49, "max": 3305.22, "aliquot": 0.12},
            {"min": 3305.23, "max": 6433.57, "aliquot": 0.14}
        ],
        "ceiling": 6433.57
    },
    "2020-03": {
        "ranges": [
            {"min": 0.00, "max": 1045.00, "aliquot": 0.075},
            {"min": 1045.01, "max": 2089.60, "aliquot": 0.09},
            {"min": 2089.61, "max": 3134.40, "aliquot": 0.12},
            {"min": 3134.41, "max": 6101.06, "aliquot": 0.14}
        ],
        "ceiling": 6101.06
    },
    "2020-01": {
        "ranges": [
            {"min": 0.00, "max": 1830.29, "aliquot": 0.08},
            {"min": 1830.30, "max": 3050.52, "aliquot": 0.09},
            {"min": 3050.53, "max": 6101.06, "aliquot": 0.11}
        ],
        "ceiling": 6101.06
    },
    "2019-01": {
        "ranges": [
            {"min": 0.00, "max": 1751.81, "aliquot": 0.08},
            {"min": 1751.82, "max": 2919.72, "aliquot": 0.09},
            {"min": 2919.73, "max": 5839.45, "aliquot": 0.11}
        ],
        "ceiling": 5839.45
    }
}

def calculate_inss(salary, competence_dt):
    comp_year = competence_dt.year
    comp_month = competence_dt.month

    table_key = None
    for key in sorted(INSS_TABLES.keys(), reverse=True):
        table_year = int(key.split("-")[0])
        table_month = int(key.split("-")[1])
        if comp_year > table_year or (comp_year == table_year and comp_month >= table_month):
            table_key = key
            break
    
    if not table_key:
        return 0.0

    table = INSS_TABLES[table_key]
    contribution = 0.0
    
    remaining_salary = salary
    for r in table["ranges"]:
        if remaining_salary <= 0:
            break
        
        portion = min(remaining_salary, r["max"] - r["min"] + (1 if r["min"] == 0 else 0))
        if salary > r["max"] and r["max"] != table["ceiling"]:
            portion = r["max"] - r["min"] + (1 if r["min"] == 0 else 0)
        elif salary <= r["max"]:
            portion = salary - r["min"] + (1 if r["min"] == 0 else 0)
            if portion < 0: portion = 0

        contribution += portion * r["aliquot"]
        remaining_salary -= portion

    max_contribution = 0.0
    for r in table["ranges"]:
        if table["ceiling"] >= r["min"]:
            portion = min(table["ceiling"], r["max"]) - r["min"] + (1 if r["min"] == 0 else 0)
            if portion < 0: portion = 0
            max_contribution += portion * r["aliquot"]
    
    return min(contribution, max_contribution)

def get_inss_ceiling(competence_dt):
    comp_year = competence_dt.year
    comp_month = competence_dt.month

    table_key = None
    for key in sorted(INSS_TABLES.keys(), reverse=True):
        table_year = int(key.split("-")[0])
        table_month = int(key.split("-")[1])
        if comp_year > table_year or (comp_year == table_year and comp_month >= table_month):
            table_key = key
            break
    
    if not table_key:
        return 0.0
    
    return INSS_TABLES[table_key]["ceiling"]

# ----------------------------------------------------------------------
# FUNÇÃO PRINCIPAL DE ANÁLISE DO CNIS (adaptada para Streamlit)
# ----------------------------------------------------------------------
def analyze_cnis_pdf(pdf_file):
    try:
        # Usar PyMuPDF para extrair texto do PDF
        import fitz
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        texto = "".join(page.get_text() for page in doc)
        doc.close()
    except Exception as e:
        st.error(f"Erro ao extrair texto do PDF. Certifique-se de que é um PDF válido e não está protegido. Erro: {e}")
        return None

    CNPJ_RE        = r"\d{2}\.\d{3}\.\d{3}(?:/\d{4}-\d{2})?"
    re_cnpj_bloco  = re.compile(CNPJ_RE)
    re_simples     = re.compile(r"^(\d{2}/\d{4})\s+([\d.,]+)$", re.MULTILINE)
    re_agrup       = re.compile(
        rf"""
          ^(\d{{2}}/\d{{4}})            # 1 - Competência
          \s+({CNPJ_RE})                # 2 - CNPJ 1 (coluna Contrat.)
          (?:\s+({CNPJ_RE}))?           # 3 - CNPJ 2 (opcional)
          \s+.*?                        # lixo
          \s+([\d.,]+)$                 # 4 - Valor
        """,
        re.MULTILINE | re.VERBOSE,
    )

    dados = []
    for bloco in re.split(r"Código Emp\.", texto):
        bloco = bloco.strip()

        if "AGRUPAMENTO DE CONTRATANTES/COOPERATIVAS" in bloco:
            for comp, cnpj1, cnpj2, val in re_agrup.findall(bloco):
                cnpj = cnpj1
                dados.append(
                    {"Competência": comp,
                     "CNPJ": cnpj,
                     "Salário": float(val.replace(".", "").replace(",", "."))})
        else:
            m = re_cnpj_bloco.search(bloco)
            if not m:
                continue
            cnpj_bloco = m.group(0)
            for comp, val in re_simples.findall(bloco):
                dados.append(
                    {"Competência": comp,
                     "CNPJ": cnpj_bloco,
                     "Salário": float(val.replace(".", "").replace(",", "."."))}
                )

    if not dados:
        st.warning("Nenhuma remuneração encontrada no extrato CNIS.")
        return None

    df = pd.DataFrame(dados)
    
    # Calcula a contribuição INSS para cada registro
    for index, row in df.iterrows():
        salary = row["Salário"]
        competence_str = row["Competência"]
        competence_dt = pd.to_datetime("01/" + competence_str, format="%d/%m/%Y")
        df.loc[index, "Contribuição"] = calculate_inss(salary, competence_dt)

    contribuicoes_a_maior_por_competencia = {}

    for competencia, grupo in df.groupby("Competência"):
        total_contribuicao_competencia = grupo["Contribuição"].sum()
        
        competencia_dt = pd.to_datetime("01/" + competencia, format="%d/%m/%Y")
        
        contribuicao_maxima_teto = calculate_inss(get_inss_ceiling(competencia_dt), competencia_dt)
        
        contribuicao_a_maior = max(0, total_contribuicao_competencia - contribuicao_maxima_teto)
        
        contribuicoes_a_maior_por_competencia[competencia] = contribuicao_a_maior
        
    today         = pd.Timestamp.today().normalize()
    start_cutoff  = pd.Timestamp(year=today.year - 5, month=today.month, day=1)

    df["Comp_dt"] = pd.to_datetime("01/" + df["Competência"], format="%d/%m/%Y")
    df            = df[df["Comp_dt"] >= start_cutoff]

    total_registros = len(dados) # Mantém o total de registros do arquivo original
    total_competencias = df["Competência"].nunique()
    competencia_min = df["Competência"].min() if not df.empty else "N/A"
    competencia_max = df["Competência"].max() if not df.empty else "N/A"

    df["Contribuição a maior"] = df["Competência"].map(contribuicoes_a_maior_por_competencia)

    total_contribuicoes_a_maior_final = df["Contribuição a maior"].sum()

    return {
        "success": True,
        "total_contribuicoes_a_maior": total_contribuicoes_a_maior_final,
        "total_registros": total_registros,
        "total_competencias": total_competencias,
        "periodo_analisado": {
            "inicio": competencia_min,
            "fim": competencia_max
        }
    }

# ----------------------------------------------------------------------
# INTERFACE STREAMLIT
# ----------------------------------------------------------------------
st.set_page_config(layout="centered", page_title="Análise CNIS - Recuperação de INSS")

# Custom CSS para um design mais limpo e moderno
st.markdown("""
<style>
    .stApp { 
        background-color: #f0f2f6; 
        color: #333333;
    }
    .stButton>button {
        background-color: #4CAF50; /* Green */
        color: white;
        padding: 10px 24px;
        border-radius: 8px;
        border: none;
        cursor: pointer;
        font-size: 16px;
        transition: background-color 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .stTextInput>div>div>input {
        border-radius: 8px;
        border: 1px solid #cccccc;
        padding: 10px;
    }
    .stFileUploader>div>div>button {
        background-color: #007bff; /* Blue */
        color: white;
        padding: 10px 24px;
        border-radius: 8px;
        border: none;
        cursor: pointer;
        font-size: 16px;
        transition: background-color 0.3s ease;
    }
    .stFileUploader>div>div>button:hover {
        background-color: #0056b3;
    }
    .header-title {
        font-size: 3em;
        color: #2c3e50;
        text-align: center;
        margin-bottom: 0.5em;
    }
    .subheader-text {
        font-size: 1.2em;
        color: #555555;
        text-align: center;
        margin-bottom: 2em;
    }
    .result-box {
        background-color: #ffffff;
        padding: 30px;
        border-radius: 15px;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        margin-top: 30px;
        text-align: center;
    }
    .result-value {
        font-size: 2.5em;
        color: #28a745; /* Green for positive value */
        font-weight: bold;
        margin-bottom: 10px;
    }
    .contact-form-container {
        background-color: #ffffff;
        padding: 30px;
        border-radius: 15px;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        margin-top: 40px;
    }
    .stAlert {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Título e Subtítulo
st.markdown("<h1 class='header-title'>Descubra se você tem direito à recuperação de INSS</h1>", unsafe_allow_html=True)
st.markdown("<p class='subheader-text'>Analise seu extrato CNIS gratuitamente e descubra valores pagos a maior que podem ser recuperados. Nossa análise preliminar é rápida e segura.</p>", unsafe_allow_html=True)

# Seção de Upload
st.header("Análise do Seu Extrato CNIS")
st.write("Faça o upload do seu extrato e descubra em segundos se você tem valores a recuperar.")

uploaded_file = st.file_uploader("Arraste seu extrato CNIS aqui ou clique para selecionar o arquivo", type=["pdf"])

if uploaded_file is not None:
    st.info("Analisando seu extrato... Isso pode levar alguns segundos.")
    
    # Chamar a função de análise
    analysis_result = analyze_cnis_pdf(uploaded_file)
    
    if analysis_result and analysis_result["success"]:
        st.session_state["analysis_result"] = analysis_result
        st.session_state["uploaded_pdf_name"] = uploaded_file.name
        st.session_state["uploaded_pdf_content"] = uploaded_file.getvalue() # Armazena o conteúdo binário
        
        st.markdown("<div class='result-box'>", unsafe_allow_html=True)
        st.markdown("<h3>✅ Análise Concluída!</h3>", unsafe_allow_html=True)
        st.markdown(f"<p>Valor estimado de recuperação:</p><p class='result-value'>R$ {analysis_result['total_contribuicoes_a_maior']:.2f}</p>", unsafe_allow_html=True)
        st.write(f"Registros analisados: {analysis_result['total_registros']}")
        st.write(f"Competências: {analysis_result['total_competencias']}")
        st.write(f"Período: {analysis_result['periodo_analisado']['inicio']} a {analysis_result['periodo_analisado']['fim']}")
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.success("Sua análise foi concluída! Para continuar e obter uma apuração precisa, preencha seus dados abaixo.")
        
        # Formulário de Contato
        st.markdown("<div class='contact-form-container'>", unsafe_allow_html=True)
        st.subheader("Preencha seus dados para contato")
        
        with st.form("contact_form"):
            nome = st.text_input("Nome Completo", key="nome_completo")
            email = st.text_input("E-mail", key="email_contato")
            telefone = st.text_input("Telefone (com DDD)", key="telefone_contato")
            cpf = st.text_input("CPF (opcional)", key="cpf_contato")
            
            submitted = st.form_submit_button("Continuar Processo")
            
            if submitted:
                if not nome or not email or not telefone:
                    st.error("Por favor, preencha Nome, E-mail e Telefone.")
                else:
                    # Armazenar dados do lead na session_state
                    st.session_state["lead_data"] = {
                        "nome": nome,
                        "email": email,
                        "telefone": telefone,
                        "cpf": cpf,
                        "analysis_result": st.session_state["analysis_result"],
                        "uploaded_pdf_name": st.session_state["uploaded_pdf_name"]
                    }
                    st.success("Dados enviados com sucesso! Entraremos em contato em breve.")
                    st.write("**Recuperação garantida:** Só cobramos após a conclusão da análise completa e realização do pedido junto à Receita.")
                    
                    # TODO: Aqui você integraria o envio de e-mail real com o PDF anexado
                    # Por exemplo, usando um serviço de e-mail ou webhook
                    # st.write("Simulando envio de e-mail com dados do lead e PDF...")
                    # print(st.session_state["lead_data"])
                    # print("PDF Content Size:", len(st.session_state["uploaded_pdf_content"])) # Conteúdo binário do PDF

        st.markdown("</div>", unsafe_allow_html=True)

    else:
        st.error("Não foi possível processar o extrato CNIS. Por favor, tente novamente com um arquivo válido.")

# Seção 

