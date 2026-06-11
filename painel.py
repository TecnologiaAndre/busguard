import streamlit as st
import requests
import pandas as pd

# =========================================================================
# 1. CONFIGURAÇÃO DA INTERFACE E AMBIENTE
# =========================================================================

# Define o layout inicial da aplicação. Ao contrário do app mobile, aqui usamos 'wide'
# (modo amplo) para que as tabelas, gráficos e colunas aproveitem toda a largura de monitores de computadores.
st.set_page_config(page_title="Painel de Controle - BusGuard", page_icon="🖥️", layout="wide")

# Variáveis globais de ambiente carregadas de forma segura através do arquivo 'secrets.toml' do Streamlit.
# Centraliza os dados de autenticação da API Rest do Supabase sem expor as chaves publicamente.
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# =========================================================================
# 2. GESTÃO DE ESTADO DO OPERADOR (SESSION STATE)
# =========================================================================

# Inicializa e persiste as variáveis de controle de acesso do operador interno na memória da sessão.
if "operador_logado" not in st.session_state:
    st.session_state.operador_logado = False   # Define se o painel administrativo está bloqueado ou liberado
if "nome_operador" not in st.session_state:
    st.session_state.nome_operador = ""      # Armazena o nome do operador logado para auditoria e interface

# =========================================================================
# 3. MÓDULO DE AUTENTICAÇÃO (TELA DE LOGIN DO OPERADOR)
# =========================================================================
if not st.session_state.operador_logado:
    st.title("🖥️ Centro de Controle BusGuard")
    st.subheader("Área Restrita para Operadores e Tratamento de Dados")
    st.markdown("---")
    
    # Divide a tela ao meio (50% / 50%) para centralizar o formulário de login no lado esquerdo
    col1, col2 = st.columns([1, 1])
    with col1:
        with st.form("login_operador"):
            usuario = st.text_input("Usuário / Matrícula")
            senha = st.text_input("Senha de Acesso", type="password")
            botao_entrar = st.form_submit_button("Acessar Painel", use_container_width=True)
            
        if botao_entrar:
            if usuario and senha:
                try:
                    # 'ilike' realiza uma busca case-insensitive no PostgREST, ignorando maiúsculas e minúsculas.
                    # Remove também espaços vazios nas extremidades com o '.strip()'.
                    url_login = f"{SUPABASE_URL}/rest/v1/operadores?usuario=ilike.{usuario.strip()}&select=*"
                    headers_login = {
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                        "apikey": SUPABASE_KEY
                    }
                    response_login = requests.get(url_login, headers=headers_login)
                    
                    if response_login.status_code == 200:
                        resultado = response_login.json()
                        
                        # Se houver registro correspondente ao usuário buscado:
                        if len(resultado) > 0:
                            dados_usuario = resultado[0]
                            
                            # Limpeza e normalização das strings vinda do banco e digitadas pelo usuário
                            senha_banco = str(dados_usuario.get("senha")).strip()
                            senha_digitada = str(senha).strip()
                            is_ativo = dados_usuario.get("ativo")
                            
                            # Validação dupla: A senha precisa coincidir E a flag 'ativo' precisa ser True (no tipo boolean ou string)
                            if senha_digitada == senha_banco and (is_ativo is True or str(is_ativo).upper() == "TRUE"):
                                # Libera o painel e salva o nome nominal do operador na sessão do Streamlit
                                st.session_state.operador_logado = True
                                st.session_state.nome_operador = dados_usuario["nome"]
                                st.success("Acesso autorizado!")
                                st.rerun() # Reinicia o script do topo para carregar o Painel Principal imediatamente
                            else:
                                st.error("❌ Senha incorreta ou operador inativo.")
                        else:
                            st.error("❌ Usuário não encontrado.")
                    else:
                        st.error("Erro na comunicação com o banco de dados do Supabase.")
                except Exception as e:
                    st.error(f"Erro ao tentar fazer login: {e}")
            else:
                st.warning("Por favor, preencha o usuário e a senha.")
    st.stop() # Bloqueia a execução do código abaixo se o fluxo de autenticação não tiver sido satisfeito

# =========================================================================
# 4. PAINEL PRINCIPAL (CENTRAL DE MONITORAMENTO)
# =========================================================================

# Cria a barra superior do painel dividida em três colunas de tamanhos proporcionais (3:1:1)
col_tit, col_user, col_btn_sair = st.columns([3, 1, 1])
with col_tit:
    st.title("📊 Painel de Monitoramento em Tempo Real")
with col_user:
    # Exibe o nome do operador alinhado à direita de forma elegante via HTML inline permitido no markdown
    st.markdown(f"<p style='text-align:right; padding-top:15px;'>👤 <b>{st.session_state.nome_operador}</b></p>", unsafe_allow_html=True)
with col_btn_sair:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Sair do Sistema 🚪", use_container_width=True):
        # Reseta os estados de login para forçar o encerramento seguro da sessão
        st.session_state.operador_logado = False
        st.session_state.nome_operador = ""
        st.rerun()

st.markdown("---")

# Botão de re-renderização manual. Como qualquer clique no Streamlit recarrega o arquivo,
# esse botão funciona perfeitamente para disparar um novo ciclo de leitura e atualizar as ocorrências na tela.
if st.button("🔄 Atualizar Dados Agora"):
    st.toast("Dados atualizados!")

# -------------------------------------------------------------------------
# LEITURA E TRATAMENTO DA TABELA DE OCORRÊNCIAS
# -------------------------------------------------------------------------
try:
    # Busca todas as ocorrências cadastradas, ordenando de forma decrescente pelo ID (Mais novas primeiro)
    url_buscar = f"{SUPABASE_URL}/rest/v1/ocorrencias?select=*&order=id.desc"
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY
    }
    response = requests.get(url_buscar, headers=headers)
    
    if response.status_code == 200:
        dados_ocorrencias = response.json()
        
        if len(dados_ocorrencias) == 0:
            st.info("ℹ️ Nenhuma ocorrência registrada no momento.")
        else:
            # Converte a lista de dicionários JSON retornada pela API em um Dataframe estruturado do Pandas
            df = pd.DataFrame(dados_ocorrencias)
            
            # Dicionário de Tradução: Mapeia o nome técnico das colunas físicas do banco para termos amigáveis
            colunas_exibicao = {
                "prefixo_veiculo": "Ônibus",
                "tipo": "Tipo",
                "descricao": "Descrição",
                "registrador": "Quem Registrou",
                "foto_url": "Link da Foto"
            }
            
            # Garante que apenas as colunas que realmente existem no banco sejam selecionadas para evitar KeyError
            colunas_existentes = [col for col in colunas_exibicao.keys() if col in df.columns]
            df_filtrado = df[colunas_existentes].rename(columns=colunas_exibicao)
            
            # --- ÁREA DE MÉTRICAS ANALÍTICAS (KPIs) ---
            # Cria três blocos de visualização rápida no topo do dashboard
            m1, m2, m3 = st.columns(3)
            m1.metric("Total de Ocorrências", len(df))
            # Captura dinamicamente o valor da primeira linha da coluna "Ônibus" (por conta do order desc, é o mais recente)
            m2.metric("Último Ônibus Afetado", str(df_filtrado["Ônibus"].iloc[0] if not df_filtrado.empty else "Nenhum"))
            m3.metric("Status do Servidor", "Online 🟢")
            
            # Renderiza o Dataframe como uma planilha interativa de alta performance na tela
            st.markdown("### 📋 Lista de Chamados Abertos")
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
            
            # --- DETALHAMENTO E TRATAMENTO DA OCORRÊNCIA SELECIONADA ---
            st.markdown("---")
            st.markdown("### 🔍 Tratamento de Ocorrência Individual")
            
            # Estrutura um dicionário mapeando o ID (chave oculta) com um texto amigável Prefixo + Tipo (valor visível)
            # para que o operador possa selecionar o problema de forma intuitiva no selectbox.
            opcoes_ocorrencias = {
                row["id"]: f"Veículo {row.get('prefixo_veiculo')} - {row.get('tipo')}" 
                for row in dados_ocorrencias
            }
            
            # O selectbox exibe o texto amigável baseado na função lambda, mas o retorno prático é o ID da linha do banco
            id_selecionado = st.selectbox(
                "Selecione a ocorrência para ver detalhes e fotos:", 
                options=list(opcoes_ocorrencias.keys()),
                format_func=lambda x: opcoes_ocorrencias[x]
            )
            
            if id_selecionado:
                # Localiza a linha exata no dataframe correspondente ao ID selecionado no componente
                linha_ocorrencia = df[df["id"] == id_selecionado].iloc[0]
                
                # Divide o espaço inferior: 60% para os textos explicativos e 40% para a exibição da foto
                col_dados, col_foto = st.columns([3, 2])
                
                with col_dados:
                    st.write(f"**🚌 Veículo:** {linha_ocorrencia.get('prefixo_veiculo')}")
                    st.write(f"**🚨 Tipo de Problema:** {linha_ocorrencia.get('tipo')}")
                    st.write(f"**👤 Registrado por:** {linha_ocorrencia.get('registrador')}")
                    st.write(f"**📝 Descrição:** {linha_ocorrencia.get('descricao')}")
                    
                    # O 'key' dinâmico baseado no ID impede o Streamlit de misturar as anotações ao trocar de ocorrência
                    st.text_area("Anotações de Tratamento / Resolução", placeholder="Digite aqui as ações tomadas...", key=f"nota_{id_selecionado}")
                    if st.button("✅ Marcar como Resolvido / Tratado", use_container_width=True):
                        # Nota de Desenvolvimento futura: Implementar o endpoint HTTP PATCH aqui 
                        # para atualizar a flag de status ou texto de resolução direto na tabela do banco.
                        st.success(f"Ocorrência atualizada com sucesso no sistema!")
                        
                with col_foto:
                    st.write("**📸 Evidência Fotográfica:**")
                    url_foto = linha_ocorrencia.get('foto_url')
                    if url_foto:
                        # Exibe a foto puxando em tempo real da URL pública do bucket de storage do Supabase
                        st.image(url_foto, caption=f"Foto da Ocorrência", use_container_width=True)
                    else:
                        st.warning("Nenhuma foto anexada a este registro.")
                        
    else:
        st.error(f"Erro ao buscar dados do Supabase. Código: {response.status_code}")
except Exception as e:
    st.error(f"Erro crítico ao carregar painel: {e}")