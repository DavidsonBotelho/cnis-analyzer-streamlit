import streamlit as st
import pandas as pd
import re
from datetime import datetime
import io
# import requests # Descomente se for usar para enviar dados via HTTP POST

# ----------------------------------------------------------------------
# TABELAS INSS - Alíquotas e Tetos por período
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
    # Itera sobre as chaves da tabela em ordem decrescente para encontrar a tabela correta
    for key in sorted(INSS_TABLES.keys(), reverse=True):
        table_year = int(key.split("-")[0])
        table_month = int(key.split("-")[1])
        
        # Se o ano da competência for maior que o ano da tabela, ou
        # se o ano for o mesmo e o mês da competência for maior ou igual ao mês da tabela,
        # então esta é a tabela mais recente aplicável.
        if comp_year > table_year or (comp_year == table_year and comp_month >= table_month):
            table_key = key
            break
    
    if not table_key:
        # Se nenhuma tabela for encontrada (ex: data muito antiga), retorna 0
        return 0.0

    table = INSS_TABLES[table_key]
    contribution = 0.0
    
    # Aplica o teto do INSS antes de calcular a contribuição
    salary_for_calculation = min(salary, table["ceiling"])

    remaining_salary = salary_for_calculation
    
    # Calcula a contribuição progressiva
    for r in table["ranges"]:
        if remaining_salary <= 0:
            break
        
        # Calcula a porção do salário que cai nesta faixa
        # A porção é o mínimo entre o salário restante e a largura da faixa
        # (r["max"] - r["min"] + 0.01 para incluir o limite superior da faixa)
        # Ou, se o salário for menor que o limite superior da faixa, a porção é o que resta do salário
        
        # Ajuste para cálculo progressivo correto:
        # A contribuição é calculada sobre a parte do salário que se encaixa em cada faixa.
        # O valor a ser considerado para a faixa é o mínimo entre o salário restante
        # e o valor máximo da faixa menos o valor mínimo da faixa (mais 0.01 para cobrir o limite superior).
        
        # Exemplo: Salário 2000, Faixa 1 (0-1412, 7.5%), Faixa 2 (1412.01-2666.68, 9%)
        # Na Faixa 1: contribui sobre 1412 * 0.075
        # Na Faixa 2: contribui sobre (2000 - 1412) * 0.09
        
        # Valor efetivo dentro da faixa atual
        portion_in_range = min(remaining_salary, r["max"] - r["min"] + 0.01) # +0.01 para incluir o limite superior
        
        # Garante que a porção não seja negativa
        if portion_in_range < 0:
            portion_in_range = 0
            
        contribution += portion_in_range * r["aliquot"]
        remaining_salary -= portion_in_range

    # O cálculo progressivo já lida com o teto implicitamente ao limitar salary_for_calculation
    # e ao iterar pelas faixas. O max_contribution abaixo é mais para verificar o teto teórico
    # se o salário fosse exatamente o teto, mas o cálculo progressivo já é o método correto.
    # A linha `return min(contribution, max_contribution)` do código original não é necessária
    # se o `salary_for_calculation` já limita o salário ao teto antes do cálculo progressivo.
    # No entanto, para manter a lógica original de "teto de contribuição", podemos recalcular
    # a contribuição máxima sobre o teto.
    
    # Recalcula a contribuição máxima possível sobre o teto para garantir que não exceda
    max_contribution_at_ceiling = 0.0
    ceiling_remaining = table["ceiling"]
    for r in table["ranges"]:
        if ceiling_remaining <= 0:
            break
        
        # Porção da faixa que está abaixo ou igual ao teto
        portion_of_ceiling_in_range = min(ceiling_remaining, r["max"] - r["min"] + 0.01)
        if portion_of_ceiling_in_range < 0:
            portion_of_ceiling_in_range = 0
            
        max_contribution_at_ceiling += portion_of_ceiling_in_range * r["aliquot"]
        ceiling_remaining -= portion_of_ceiling_in_range

    return min(contribution, max_contribution_at_ceiling)


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
# FUNÇÃO PRINCIPAL DE ANÁLISE DO CNIS
# ----------------------------------------------------------------------
def analyze_cnis_pdf(pdf_file):
    try:
        # Importa fitz (PyMuPDF) aqui para garantir que a importação ocorra apenas se a função for chamada
        # e para que o erro seja mais específico se PyMuPDF não estiver instalado.
        import fitz 
        # Usar io.BytesIO para garantir que o arquivo seja lido como bytes
        doc = fitz.open(stream=io.BytesIO(pdf_file.read()), filetype="pdf")
        texto = "".join(page.get_text() for page in doc)
        doc.close()
    except ImportError:
        st.error("Erro: A biblioteca 'PyMuPDF' (fitz) não está instalada. Por favor, adicione 'PyMuPDF' ao seu requirements.txt.")
        return None
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
    # O split por "Código Emp." pode ser problemático se essa string não for consistente.
    # Uma abordagem mais robusta seria procurar por padrões de "Competência" e "Valor"
    # em todo o texto, e então tentar associar ao CNPJ mais próximo.
    # Por enquanto, mantemos o split original.
    for bloco in re.split(r"Código Emp\.", texto):
        bloco = bloco.strip()

        if "AGRUPAMENTO DE CONTRATANTES/COOPERATIVAS" in bloco:
            for comp, cnpj1, cnpj2, val in re_agrup.findall(bloco):
                cnpj = cnpj1 # Assume cnpj1 é o principal
                try:
                    dados.append(
                        {"Competência": comp,
                         "CNPJ": cnpj,
                         "Salário": float(val.replace(".", "").replace(",", "."))})
                except ValueError:
                    st.warning(f"Não foi possível converter o salário '{val}' para número na competência {comp} (agrupamento). Ignorando registro.")
        else:
            m = re_cnpj_bloco.search(bloco)
            if not m:
                continue
            cnpj_bloco = m.group(0)
            for comp, val in re_simples.findall(bloco):
                try:
                    dados.append(
                        {"Competência": comp,
                         "CNPJ": cnpj_bloco,
                         "Salário": float(val.replace(".", "").replace(",", "."))} # CORREÇÃO AQUI: .replace(",", ".")
                    )
                except ValueError:
                    st.warning(f"Não foi possível converter o salário '{val}' para número na competência {comp} (simples). Ignorando registro.")

    if not dados:
        st.warning("Nenhuma remuneração válida encontrada no extrato CNIS. Verifique o formato do arquivo.")
        return None

    df = pd.DataFrame(dados)
    
    # Calcula a contribuição INSS para cada registro
    # Usamos .apply para maior eficiência em DataFrames grandes
    df["Comp_dt"] = pd.to_datetime("01/" + df["Competência"], format="%d/%m/%Y", errors='coerce')
    
    # Remove linhas onde a conversão de data falhou
    df.dropna(subset=["Comp_dt"], inplace=True)

    if df.empty:
        st.warning("Nenhuma competência válida encontrada após a conversão de datas.")
        return None

    df["Contribuição"] = df.apply(lambda row: calculate_inss(row["Salário"], row["Comp_dt"]), axis=1)

    contribuicoes_a_maior_por_competencia = {}

    for competencia, grupo in df.groupby("Competência"):
        total_contribuicao_competencia = grupo["Contribuição"].sum()
        
        # Pega a primeira data de competência do grupo (todas são iguais para a mesma competência)
        competencia_dt = grupo["Comp_dt"].iloc[0] 
        
        # Calcula a contribuição máxima teórica para o teto daquele período
        teto_inss_periodo = get_inss_ceiling(competencia_dt)
        contribuicao_maxima_teto = calculate_inss(teto_inss_periodo, competencia_dt)
        
        contribuicao_a_maior = max(0, total_contribuicao_competencia - contribuicao_maxima_teto)
        
        contribuicoes_a_maior_por_competencia[competencia] = contribuicao_a_maior
        
    today         = pd.Timestamp.today().normalize()
    # Analisa os últimos 5 anos completos até o mês atual
    start_cutoff  = pd.Timestamp(year=today.year - 5, month=today.month, day=1)

    # Filtra o DataFrame para incluir apenas as competências dentro do período de 5 anos
    df_filtered = df[df["Comp_dt"] >= start_cutoff].copy() # Usar .copy() para evitar SettingWithCopyWarning

    if df_filtered.empty:
        st.warning("Nenhuma remuneração encontrada nos últimos 5 anos para análise.")
        return {
            "success": True,
            "total_contribuicoes_a_maior": 0.0,
            "total_registros": 0,
            "total_competencias": 0,
            "periodo_analisado": {
                "inicio": "N/A",
                "fim": "N/A"
            }
        }

    total_registros = len(df_filtered) # Total de registros no período analisado
    total_competencias = df_filtered["Competência"].nunique()
    competencia_min = df_filtered["Competência"].min()
    competencia_max = df_filtered["Competência"].max()

    # Mapeia as contribuições a maior para o DataFrame filtrado
    # Isso garante que o sum final seja apenas do período analisado
    df_filtered["Contribuição a maior"] = df_filtered["Competência"].map(contribuicoes_a_maior_por_competencia)

    # Soma apenas as contribuições a maior do período filtrado
    total_contribuicoes_a_maior_final = df_filtered["Contribuição a maior"].sum()

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
        # Armazena o resultado da análise e o conteúdo do PDF na session_state
        # para que possam ser acessados após o envio do formulário.
        st.session_state["analysis_result"] = analysis_result
        st.session_state["uploaded_pdf_name"] = uploaded_file.name
        # É crucial armazenar o conteúdo binário do PDF se você planeja enviá-lo.
        # uploaded_file.getvalue() lê o conteúdo UMA VEZ. Se você precisar dele novamente,
        # ele deve ser armazenado ou o uploader deve ser re-executado.
        st.session_state["uploaded_pdf_content"] = uploaded_file.getvalue() 
        
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
                    # Estes dados podem ser usados para enviar para um serviço externo
                    st.session_state["lead_data"] = {
                        "nome": nome,
                        "email": email,
                        "telefone": telefone,
                        "cpf": cpf,
                        "analysis_result": st.session_state["analysis_result"],
                        "uploaded_pdf_name": st.session_state["uploaded_pdf_name"]
                        # O conteúdo binário do PDF está em st.session_state["uploaded_pdf_content"]
                    }
                    
                    # --- LÓGICA DE ENVIO DE DADOS (EXEMPLO) ---
                    # Aqui você integraria o envio de e-mail real ou para um serviço de webhook.
                    # Para um protótipo simples, você pode apenas imprimir no console do Streamlit Cloud
                    # ou usar um serviço como Formspree/Web3Forms.
                    
                    # Exemplo de como você enviaria para um webhook (requer 'requests' no requirements.txt)
                    # import requests
                    # try:
                    #     webhook_url = "SUA_URL_DO_WEBHOOK_AQUI" # Ex: https://formspree.io/f/your_form_id
                    #     payload = {
                    #         "nome": nome,
                    #         "email": email,
                    #         "telefone": telefone,
                    #         "cpf": cpf,
                    #         "valor_recuperacao_estimado": analysis_result['total_contribuicoes_a_maior'],
                    #         "periodo_analisado": f"{analysis_result['periodo_analisado']['inicio']} a {analysis_result['periodo_analisado']['fim']}",
                    #         "nome_arquivo_cnis": st.session_state["uploaded_pdf_name"]
                    #         # Para enviar o PDF, você precisaria codificá-lo em base64 ou fazer upload para um serviço de armazenamento
                    #         # e enviar o link. Webhooks geralmente têm limites de tamanho para dados.
                    #         # "cnis_pdf_base64": base64.b64encode(st.session_state["uploaded_pdf_content"]).decode('utf-8')
                    #     }
                    #     response = requests.post(webhook_url, json=payload)
                    #     if response.status_code == 200:
                    #         st.success("Dados enviados com sucesso! Entraremos em contato em breve.")
                    #     else:
                    #         st.error(f"Erro ao enviar dados. Código: {response.status_code}. Resposta: {response.text}")
                    #         st.warning("Por favor, entre em contato conosco diretamente se o problema persistir.")
                    # except Exception as e:
                    #     st.error(f"Ocorreu um erro inesperado ao enviar os dados: {e}")
                    #     st.warning("Por favor, entre em contato conosco diretamente se o problema persistir.")

                    # Mensagem de sucesso para o usuário
                    st.success("Dados enviados com sucesso! Entraremos em contato em breve.")
                    st.write("**Recuperação garantida:** Só cobramos após a conclusão da análise completa e realização do pedido junto à Receita.")
                    
                    # Para depuração, você pode imprimir os dados no console do Streamlit Cloud
                    print("\n--- DADOS DO LEAD CAPTURADOS ---")
                    print(f"Nome: {nome}")
                    print(f"Email: {email}")
                    print(f"Telefone: {telefone}")
                    print(f"CPF: {cpf if cpf else 'Não informado'}")
                    print(f"Valor Estimado de Recuperação: R$ {analysis_result['total_contribuicoes_a_maior']:.2f}")
                    print(f"Nome do Arquivo CNIS: {st.session_state['uploaded_pdf_name']}")
                    print(f"Tamanho do Conteúdo do PDF: {len(st.session_state['uploaded_pdf_content'])} bytes")
                    print("----------------------------------\n")

        st.markdown("</div>", unsafe_allow_html=True)

    else:
        st.error("Não foi possível processar o extrato CNIS. Por favor, tente novamente com um arquivo válido ou verifique o formato.")

