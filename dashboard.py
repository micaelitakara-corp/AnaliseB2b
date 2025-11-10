import streamlit as st
import pandas as pd
import plotly.express as px
import warnings
# Importa o componente de calendário
from streamlit_calendar import calendar 

# Ignorar avisos que podem poluir o dashboard
warnings.filterwarnings('ignore')

# -----------------------------------------------------------------
# FUNÇÃO PARA CARREGAR E PREPARAR OS DADOS (NOSSA ANTIGA CÉLULA 1)
# -----------------------------------------------------------------
@st.cache_data
def carregar_dados():
    print("Iniciando: Carregamento e limpeza dos dados...")
    file_name = 'Pasta1.xlsx - Planilha1.csv'
    
    try:
        # Tenta ler com o separador e encoding (utf-8 para acentos)
        df = pd.read_csv(
            file_name, 
            sep=';', 
            encoding='utf-8', 
            # Manter a leitura de documentos como texto
            dtype={
                'Phone': 'str', 
                'Corporate Document': 'str',
                'Client Document': 'str'
            } 
        )
    except Exception as e:
        print(f"Erro ao ler CSV com UTF-8: {e}. Tentando 'latin1'...")
        try:
            df = pd.read_csv(
                file_name, 
                sep=';', 
                encoding='latin1',
                dtype={
                    'Phone': 'str', 
                    'Corporate Document': 'str',
                    'Client Document': 'str'
                }
            )
        except Exception as e2:
            print(f"Erro fatal ao ler CSV: {e2}")
            return None
            
    # --- LIMPEZA DE NÚMEROS (Total Value) ---
    if 'Total Value' in df.columns:
        df['Total Value'] = df['Total Value'].astype(str).str.replace(',', '.')
        df['Total Value'] = pd.to_numeric(df['Total Value'], errors='coerce')
        df['Total Value'] = df['Total Value'].fillna(0)
        print("Coluna 'Total Value' limpa e convertida para número.")
    else:
        print("AVISO: Coluna 'Total Value' não encontrada.")


    # --- ANÁLISE DE PEDIDOS (df_pedidos_unicos) ---
    
    colunas_relevantes = [
        'Order', 'Corporate Name', 'Creation Date', 'Total Value', 'UF',
        'Email', 'Phone', 'Status', 'Corporate Document', 
        'Client Document'
    ]
    
    colunas_existentes = [col for col in colunas_relevantes if col in df.columns]
    df_pedidos = df[colunas_existentes].copy()

    # Remover duplicadas para ter Pedidos Únicos
    if 'Order' in df_pedidos.columns:
        df_pedidos_unicos = df_pedidos.drop_duplicates(subset=['Order'])
    else:
        print("Erro: Coluna 'Order' não encontrada.")
        return None

    # Converter datas
    if 'Creation Date' in df_pedidos_unicos.columns:
        df_pedidos_unicos['Creation Date'] = pd.to_datetime(
            df_pedidos_unicos['Creation Date'], 
            format='mixed', 
            dayfirst=True
        )
        
        # --- CORREÇÃO DO BUG DE FUSO HORÁRIO ---
        if df_pedidos_unicos['Creation Date'].dt.tz is not None:
            df_pedidos_unicos['Creation Date'] = df_pedidos_unicos['Creation Date'].dt.tz_localize(None)
            print("Fuso horário (timezone) removido das datas.")
            
        # Criar colunas de Ano e Mês
        df_pedidos_unicos['Ano'] = df_pedidos_unicos['Creation Date'].dt.year
        df_pedidos_unicos['Mês'] = df_pedidos_unicos['Creation Date'].dt.month
        
        # --- NOVAS COLUNAS PARA PADRÃO TEMPORAL ---
        # Dia da Semana (0=Segunda, 6=Domingo)
        df_pedidos_unicos['Dia_Semana_Num'] = df_pedidos_unicos['Creation Date'].dt.dayofweek
        
        # ======= A CORREÇÃO ESTÁ AQUI =======
        # Mapeia os números (0-6) para os nomes em PT-BR manualmente
        # Isso evita o erro de 'locale' no servidor
        mapa_dias = {
            0: 'Segunda-feira',
            1: 'Terça-feira',
            2: 'Quarta-feira',
            3: 'Quinta-feira',
            4: 'Sexta-feira',
            5: 'Sábado',
            6: 'Domingo'
        }
        df_pedidos_unicos['Dia_Semana_Nome'] = df_pedidos_unicos['Dia_Semana_Num'].map(mapa_dias)
        # ======================================
        
        # Dia do Mês
        df_pedidos_unicos['Dia_do_Mes'] = df_pedidos_unicos['Creation Date'].dt.day
        
    
    print("Dados carregados e limpos com sucesso!")
    return df_pedidos_unicos

# -----------------------------------------------------------------
# INÍCIO DO APP (DASHBOARD)
# -----------------------------------------------------------------

# Configuração da Página
st.set_page_config(layout="wide")

# --- INICIALIZAÇÃO DO SESSION STATE ---
if 'top_n_clientes' not in st.session_state:
    st.session_state.top_n_clientes = 10 # Valor inicial

# Carregar os dados
df_pedidos = carregar_dados()

# --- SIDEBAR DE FILTROS ---
st.sidebar.header('Filtros Interativos')

if df_pedidos is not None:
    
    # Filtro de Data
    data_min = pd.to_datetime(df_pedidos['Creation Date'].min().date())
    data_max = pd.to_datetime(df_pedidos['Creation Date'].max().date())
    
    data_selecionada = st.sidebar.date_input(
        "Selecione o Período",
        value=(data_min, data_max),
        min_value=data_min,
        max_value=data_max,
        format="DD/MM/YYYY"
    )
    
    if len(data_selecionada) == 2:
        data_inicio = pd.to_datetime(data_selecionada[0])
        data_fim = pd.to_datetime(data_selecionada[1])
    else:
        data_inicio = data_min
        data_fim = data_max

    # Filtro de Estado (UF)
    opcoes_uf = sorted(df_pedidos['UF'].unique())
    uf_selecionados = st.sidebar.multiselect(
        "Selecione o Estado (UF)",
        options=opcoes_uf,
        default=[]
    )

    # Filtro de Status
    opcoes_status = sorted(df_pedidos['Status'].unique())
    status_selecionados = st.sidebar.multiselect(
        "Selecione o Status do Pedido",
        options=opcoes_status,
        default=[]
    )
    
    st.sidebar.markdown("---")
    
    # Botão de Resetar Filtros na Sidebar
    if st.sidebar.button("Limpar Todos os Filtros"):
        st.experimental_rerun()

    # -----------------------------------------------------------------
    # LÓGICA DE FILTRAGEM
    # -----------------------------------------------------------------
    
    df_filtrado = df_pedidos.copy()
    
    # 1. Aplica filtro de data
    df_filtrado = df_filtrado[
        (df_filtrado['Creation Date'] >= data_inicio) & 
        (df_filtrado['Creation Date'] <= data_fim)
    ]
    
    # 2. Aplica filtro de UF (se algum foi selecionado)
    if uf_selecionados:
        df_filtrado = df_filtrado[df_filtrado['UF'].isin(uf_selecionados)]
        
    # 3. Aplica filtro de Status (se algum foi selecionado)
    if status_selecionados:
        df_filtrado = df_filtrado[df_filtrado['Status'].isin(status_selecionados)]

# --- FIM DO SIDEBAR E FILTROS ---


# --- PÁGINA PRINCIPAL DO DASHBOARD ---

st.title('Dashboard de Compradores B2B 📈')
st.markdown("Análise de pedidos, clientes, produtos e localização.")

st.divider()

if df_pedidos is None:
     st.error("Erro fatal ao carregar os dados. Verifique o console ou o arquivo 'Pasta1.xlsx - Planilha1.csv'.")
elif df_filtrado.empty:
    st.warning("Nenhum dado encontrado para os filtros selecionados. Por favor, ajuste os filtros na barra lateral.")
else:

    # --- SEÇÃO 1: Métricas Principais (KPIs) ---
    st.header('Visão Geral do Período Filtrado')

    media_compra = df_filtrado['Total Value'].mean()
    total_pedidos = len(df_filtrado)
    total_clientes = df_filtrado['Corporate Name'].nunique()
    
    limite_alto_valor = 630
    ano_recente = df_filtrado['Ano'].max() 
    pedidos_alto_valor = df_filtrado[
        (df_filtrado['Total Value'] > limite_alto_valor) & 
        (df_filtrado['Ano'] == ano_recente)
    ]
    contagem_empresas_alto_valor = pedidos_alto_valor['Corporate Name'].nunique()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Pedidos", f"{total_pedidos}")
    col2.metric("Valor Médio do Pedido", f"R$ {media_compra:.2f}")
    col3.metric("Clientes Únicos", f"{total_clientes}")
    col4.metric(f"Empresas com Pedidos > R${limite_alto_valor} (em {ano_recente})", f"{contagem_empresas_alto_valor}")

    st.divider()

    # --- SEÇÃO 2: Análise Geográfica (Vendas por Estado/UF) ---
    st.header("Análise Geográfica")
    st.subheader("Vendas por Estado (UF)")
    
    vendas_uf = df_filtrado['UF'].value_counts().reset_index()
    vendas_uf.columns = ['UF', 'Total_de_Pedidos']
    
    fig_uf = px.bar(vendas_uf, 
                    x='UF', 
                    y='Total_de_Pedidos',
                    title='Distribuição de Pedidos por Estado')
    st.plotly_chart(fig_uf, use_container_width=True)

    st.divider()

    # --- SEÇÃO 3: Análise de Clientes ---
    st.header("Análise de Clientes")

    # --- PARTE 1: Tabela de Clientes Paginada ---
    st.subheader(f"Lista de Clientes por Frequência (Mostrando os {st.session_state.top_n_clientes} primeiros)")
    
    def ver_mais_10():
        st.session_state.top_n_clientes += 10
        
    def resetar_lista_clientes():
        st.session_state.top_n_clientes = 10
    
    # Agrupamos por CNPJ ('Corporate Document')
    analise_clientes = df_filtrado.groupby('Corporate Document').agg(
        Corporate_Name=('Corporate Name', 'first'), 
        Receita_Total=('Total Value', 'sum'),
        Total_de_Pedidos=('Order', 'count'),
        Meses_das_Compras=('Mês', lambda s: list(sorted(s.unique())))
    ).reset_index()
    
    analise_clientes = analise_clientes.rename(columns={'Corporate_Name': 'Nome da Empresa'})
    
    analise_clientes['Receita_Total'] = analise_clientes['Receita_Total'].round(2)
    
    analise_clientes_ordenado = analise_clientes.sort_values(
        by='Total_de_Pedidos', ascending=False
    )
    
    analise_clientes_ordenado = analise_clientes_ordenado[['Nome da Empresa', 'Corporate Document', 'Total_de_Pedidos', 'Receita_Total', 'Meses_das_Compras']]

    st.dataframe(
        analise_clientes_ordenado.head(st.session_state.top_n_clientes), 
        use_container_width=True
    )
    
    col_btn1, col_btn2, _ = st.columns([1, 1, 4])
    
    if st.session_state.top_n_clientes < len(analise_clientes_ordenado):
        col_btn1.button(
            "Ver mais 10", 
            on_click=ver_mais_10, 
            use_container_width=True
        )
    
    if st.session_state.top_n_clientes > 10:
        col_btn2.button(
            "Resetar lista", 
            on_click=resetar_lista_clientes, 
            use_container_width=True
        )
    
    st.divider() 

    # --- PARTE 2: FERRAMENTA DE BUSCA DE CLIENTE ---
    st.subheader("🔎 Dados do Comprador (Busca)")
    
    tipo_busca = st.radio(
        "Buscar cliente por:",
        options=["Nome da Empresa", "CNPJ", "Email"],
        horizontal=True
    )

    if tipo_busca == "Nome da Empresa":
        placeholder_text = "Digite ou selecione um Nome..."
        lista_opcoes = sorted(df_filtrado['Corporate Name'].dropna().unique())
        coluna_filtro = 'Corporate Name'
        
    elif tipo_busca == "CNPJ":
        placeholder_text = "Digite ou selecione um CNPJ..."
        lista_opcoes = sorted(df_filtrado['Corporate Document'].dropna().unique())
        coluna_filtro = 'Corporate Document'
        
    elif tipo_busca == "Email":
        placeholder_text = "Digite ou selecione um Email..."
        lista_opcoes = sorted(df_filtrado['Email'].dropna().unique())
        coluna_filtro = 'Email'

    valor_selecionado = st.selectbox(
        f"Selecione o {tipo_busca}:",
        options=lista_opcoes,
        index=None,
        placeholder=placeholder_text
    )

    if valor_selecionado:
        dados_cliente = df_filtrado[df_filtrado[coluna_filtro] == valor_selecionado].copy()
        
        cliente_selecionado = dados_cliente['Corporate Name'].iloc[0]
        email = dados_cliente['Email'].iloc[0]
        phone = dados_cliente['Phone'].iloc[0]
        doc_empresa = dados_cliente['Corporate Document'].iloc[0]
        
        if 'Client Document' in dados_cliente.columns:
            doc_cliente = dados_cliente['Client Document'].iloc[0]
        else:
            doc_cliente = pd.NA
        
        if pd.isna(email) or email == 'nan': email_display = "Não informado"
        else: email_display = str(email)

        if pd.isna(phone) or phone == 'nan': phone_display = "Não informado"
        else: phone_display = str(phone)
        
        if pd.isna(doc_empresa) or doc_empresa == 'nan': doc_empresa_display = "Não informado"
        else: doc_empresa_display = str(doc_empresa)
        
        if pd.isna(doc_cliente) or doc_cliente == 'nan': doc_cliente_display = "Não informado"
        else: doc_cliente_display = str(doc_cliente)
        
        st.markdown(f"**Empresa:** `{cliente_selecionado}`")
        st.markdown(f"**CNPJ:** `{doc_empresa_display}`")
        st.markdown(f"**CPF (Contato):** `{doc_cliente_display}`")
        st.markdown(f"**Email:** `{email_display}`")
        st.markdown(f"**Telefone:** `{phone_display}`")
        
        st.markdown("---")
        st.markdown("**Histórico de Pedidos (no período filtrado):**")
        st.dataframe(dados_cliente)

    st.divider()

    # --- SEÇÃO 4: Listas de Foco e Qualidade ---
    st.header("Listas de Foco e Qualidade de Dados")

    # PARTE 1: LISTA DE CLIENTES DE ALTO VALOR
    st.subheader(f"Lista de Empresas com Pedidos Acima de R${limite_alto_valor} (em {ano_recente})")
    st.markdown(f"Encontradas **{contagem_empresas_alto_valor}** empresas únicas nesta categoria (no período filtrado).")
    
    tabela_alto_valor = pedidos_alto_valor[['Corporate Name', 'Total Value', 'Creation Date']].sort_values(by='Total Value', ascending=False)
    tabela_alto_valor['Creation Date'] = tabela_alto_valor['Creation Date'].dt.strftime('%d/%m/%Y')
    st.dataframe(tabela_alto_valor, use_container_width=True)

    st.divider()

    # PARTE 2: TABELA DE DOCUMENTOS INVÁLIDOS
    st.subheader("Pedidos com 'Corporate Document' Inválido (com letras/caracteres)")
    
    if 'Corporate Document' in df_filtrado.columns:
        documentos_invalidos = df_filtrado[
            df_filtrado['Corporate Document'].str.contains(r'[^0-9]', na=False, regex=True)
        ]
        
        contagem_invalidos = len(documentos_invalidos)
        if contagem_invalidos == 0:
            st.success("✔️ Nenhum pedido com 'Corporate Document' inválido encontrado nos filtros atuais.")
        else:
            st.warning(f"Encontrados **{contagem_invalidos}** pedidos com 'Corporate Document' (CNPJ) inválido.")
            colunas_para_mostrar = ['Corporate Name', 'Corporate Document', 'Email', 'Phone', 'Creation Date']
            st.dataframe(documentos_invalidos[colunas_para_mostrar], use_container_width=True)
    else:
        st.info("Coluna 'Corporate Document' não foi encontrada para análise de invalidade.")


    st.divider()
    
    # --- SEÇÃO 5: Análise de Padrão Temporal ---
    st.header("Análise de Padrão Temporal")
    
    col_tempo1, col_tempo2 = st.columns(2)
    
    with col_tempo1:
        st.subheader("Pedidos por Dia da Semana")
        vendas_dia_semana = df_filtrado.groupby(['Dia_Semana_Num', 'Dia_Semana_Nome'])['Order'].count().reset_index()
        vendas_dia_semana.columns = ['Num', 'Dia', 'Total_de_Pedidos']
        vendas_dia_semana = vendas_dia_semana.sort_values(by='Num')
        
        fig_dia_sem = px.bar(vendas_dia_semana,
                             x='Dia',
                             y='Total_de_Pedidos',
                             title='Total de Pedidos por Dia da Semana')
        st.plotly_chart(fig_dia_sem, use_container_width=True)
        
    with col_tempo2:
        st.subheader("Pedidos por Dia do Mês")
        vendas_dia_mes = df_filtrado.groupby('Dia_do_Mes')['Order'].count().reset_index()
        vendas_dia_mes.columns = ['Dia_do_Mes', 'Total_de_Pedidos']
        
        fig_dia_mes = px.bar(vendas_dia_mes,
                             x='Dia_do_Mes',
                             y='Total_de_Pedidos',
                             title='Total de Pedidos por Dia do Mês')
        fig_dia_mes.update_xaxes(type='category')
        st.plotly_chart(fig_dia_mes, use_container_width=True)
    
    st.divider()

    # --- SEÇÃO 6: Segmentação de Clientes por Recência ---
    st.header("Segmentação de Clientes por Recência")
    st.markdown("Esta análise segmenta clientes pela sua última data de compra, com base nos filtros selecionados.")
    
    # 1. Preparar os dados para segmentação
    segment_df = analise_clientes.copy()
    
    # 2. Calcular Recência
    snapshot_date = df_filtrado['Creation Date'].max() + pd.Timedelta(days=1)
    
    df_recencia = df_filtrado.groupby('Corporate Document')['Creation Date'].max().reset_index()
    df_recencia['Recency'] = (snapshot_date - df_recencia['Creation Date']).dt.days
    
    segment_df = segment_df.merge(df_recencia[['Corporate Document', 'Recency']], on='Corporate Document')
    
    # 3. Definir a função de segmentação
    def define_segmento(recency_days):
        if recency_days <= 90: # 3 meses
            return "Ativos (Últimos 3 Meses)"
        elif 90 < recency_days <= 180: # 3 a 6 meses
            return "Em Risco (Últimos 6 Meses)"
        else: # Mais de 6 meses
            return "Inativos (Mais de 6 Meses)"

    # 4. Aplicar a segmentação
    segment_df['Segmento'] = segment_df['Recency'].apply(define_segmento)
    
    # 5. Mostrar os segmentos em 3 colunas
    col_seg1, col_seg2, col_seg3 = st.columns(3)
    
    # 'analise_clientes' já foi renomeada para 'Nome da Empresa'
    cols_to_show = ['Nome da Empresa', 'Corporate Document', 'Recency', 'Total_de_Pedidos', 'Receita_Total']
    
    with col_seg1:
        st.subheader("✅ Ativos (Últimos 3 Meses)")
        segmento_ativos = segment_df[segment_df['Segmento'] == "Ativos (Últimos 3 Meses)"].sort_values(by='Recency')
        st.metric(label="Total de Clientes", value=len(segmento_ativos))
        st.dataframe(segmento_ativos[cols_to_show], use_container_width=True)

    with col_seg2:
        st.subheader("⚠️ Em Risco (Últimos 6 Meses)")
        segmento_risco = segment_df[segment_df['Segmento'] == "Em Risco (Últimos 6 Meses)"].sort_values(by='Recency')
        st.metric(label="Total de Clientes", value=len(segmento_risco))
        st.dataframe(segmento_risco[cols_to_show], use_container_width=True)

    with col_seg3:
        st.subheader("🚫 Inativos (Mais de 6 Meses)")
        segmento_inativos = segment_df[segment_df['Segmento'] == "Inativos (Mais de 6 Meses)"].sort_values(by='Recency')
        st.metric(label="Total de Clientes", value=len(segmento_inativos))
        st.dataframe(segmento_inativos[cols_to_show], use_container_width=True)
    
    st.divider()

    # --- SEÇÃO 7: Calendário de Compras (com 'streamlit-calendar') ---
    st.header("Calendário de Compras")

    if 'Creation Date' in df_filtrado.columns:
        vendas_dia = df_filtrado.groupby(df_filtrado['Creation Date'].dt.date)['Order'].count().reset_index()
        vendas_dia.columns = ['Data', 'Total_de_Pedidos']
        
        eventos_calendario = []
        for index, row in vendas_dia.iterrows():
            eventos_calendario.append({
                'title': f"{row['Total_de_Pedidos']} Pedidos", # O que aparece no dia
                'start': str(row['Data']),                # A data do evento
                'allDay': True                            # Evento de dia inteiro
            })
            
        calendar_options = {
            "headerToolbar": {
                "left": "prev,next today",
                "center": "title",
                "right": "dayGridMonth" # Apenas visão mensal
            },
            "initialView": "dayGridMonth",
            "locale": "pt-br" # Tenta usar português do Brasil
        }
        
        calendario_componente = calendar(
            events=eventos_calendario,
            options=calendar_options,
            key="calendario_pedidos" # Chave única
        )
        
    else:
        st.warning("Coluna 'Creation Date' não pôde ser gerada.")