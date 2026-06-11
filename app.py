import streamlit as st
from supabase import create_client, Client
import datetime
import requests

# =========================================================================
# 1. CONFIGURAÇÃO DA INTERFACE E AMBIENTE
# =========================================================================

# Define o layout inicial da aplicação. 'centered' garante que os elementos fiquem 
# compactos e agrupados no centro, simulando a usabilidade de um app mobile (foco em celulares).
st.set_page_config(page_title="Ocorrências Em Trânsito", page_icon="🚌", layout="centered")

# Variáveis globais de ambiente carregadas de forma segura através do arquivo 'secrets.toml' do Streamlit.
# Evita a exposição de tokens e chaves de segurança diretamente no repositório do Git.
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# Inicialização do Cliente Supabase oficial nativo do Python.
# O decorator '@st.cache_resource' faz o cache do objeto de conexão. Isso é crucial no Streamlit, 
# pois o script roda do topo ao fim a cada clique na tela. O cache impede o app de recriar a 
# conexão com o banco a cada interação do usuário, economizando memória e processamento.
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

# =========================================================================
# 2. GESTÃO DE ESTADO DO OPERADOR (SESSION STATE)
# =========================================================================

# O Streamlit perde todas as variáveis locais quando a página renderiza de novo.
# Usamos o 'st.session_state' como uma memória global persistente por aba aberta no navegador.
if "logado" not in st.session_state:
    st.session_state.logado = False            # Controla se a tela visível será o login ou o formulário
if "matricula_usuario" not in st.session_state:
    st.session_state.matricula_usuario = ""    # Armazena a matrícula usada no input de login
if "nome_motorista" not in st.session_state:
    st.session_state.nome_motorista = ""       # Armazena o nome real do motorista trazido do banco

# =========================================================================
# 3. MÓDULO DE AUTENTICAÇÃO (TELA DE LOGIN)
# =========================================================================
if not st.session_state.logado:
    st.title("🔐 Ocorrências Em Trânsito - Acesso")
    st.subheader("Identifique-se para acessar o sistema")
    st.markdown("---")
    
    # O bloco 'st.form' agrupa os inputs para que o script só processe as validações 
    # de uma única vez quando o 'st.form_submit_button' for acionado pelo usuário.
    with st.form("form_login"):
        input_matricula = st.text_input("Matrícula", placeholder="Digite sua matrícula")
        input_cpf = st.text_input("CPF (Apenas números)", type="password", placeholder="Digite seu CPF")
        botao_login = st.form_submit_button("Entrar", use_container_width=True)
        
    if botao_login:
        if not input_matricula or not input_cpf:
            st.error("❌ Por favor, preencha a matrícula e o CPF!")
        else:
            with st.spinner("Autenticando..."):
                try:
                    # ETAPA A: Validação das credenciais na tabela de credenciais rápidas (cadastro_login).
                    # A consulta é feita usando sintaxe PostgREST via URL (eq = equals).
                    url_login = f"{SUPABASE_URL}/rest/v1/cadastro_login?matricula=eq.{input_matricula}&cpf=eq.{input_cpf}&select=*"
                    headers_login = {
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                        "apikey": SUPABASE_KEY
                    }
                    response_login = requests.get(url_login, headers=headers_login)
                    
                    if response_login.status_code == 200:
                        resultado = response_login.json()
                        
                        # Se o retorno trouxer elementos, significa que matrícula e CPF casam perfeitamente.
                        if len(resultado) > 0:
                            
                            # ETAPA B: Cruzamento de tabelas para resgate do Nome Completo do colaborador.
                            # Valor padrão de contingência caso o motorista não possua registro nominal associado.
                            nome_encontrado = f"Matrícula {input_matricula}" 
                            
                            # Consulta a tabela principal de 'motoristas' usando a matrícula validada
                            url_motorista_login = f"{SUPABASE_URL}/rest/v1/motoristas?matricula=eq.{input_matricula}&select=nome"
                            response_mot = requests.get(url_motorista_login, headers=headers_login)
                            
                            if response_mot.status_code == 200:
                                dados_mot = response_mot.json()
                                if len(dados_mot) > 0:
                                    # Substitui o valor padrão pelo nome cadastrado no banco de dados
                                    nome_encontrado = dados_mot[0]["nome"]
                            
                            # ETAPA C: Salvamento do estado de login bem-sucedido na sessão global.
                            st.session_state.logado = True
                            st.session_state.matricula_usuario = input_matricula
                            st.session_state.nome_motorista = nome_encontrado
                            
                            st.success("✅ Login efetuado com sucesso!")
                            st.rerun() # Força a reinicialização imediata do script para pular para a tela principal
                        else:
                            st.error("❌ Matrícula ou CPF incorretos. Tente novamente.")
                    else:
                        st.error(f"❌ Erro de comunicação com o banco (Código {response_login.status_code})")
                except Exception as e:
                    st.error(f"❌ Erro crítico no login: {e}")
                    
    st.stop() # Interrompe a execução aqui caso o usuário não esteja logado, impedindo a exibição do app

# =========================================================================
# 4. MÓDULO PRINCIPAL (FORMULÁRIO DE REGISTRO DE OCORRÊNCIAS)
# =========================================================================

# Cabeçalho da aplicação e controle de Logout do sistema
col_titulo, col_sair = st.columns([4, 1])
with col_titulo:
    st.title("🚌 Ocorrências Em Trânsito")
with col_sair:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Sair 🚪"):
        # Limpa todos os estados de sessão para deslogar o usuário com segurança
        st.session_state.logado = False
        st.session_state.matricula_usuario = ""
        st.session_state.nome_motorista = ""
        st.rerun()

st.subheader(f"Registro de Ocorrências da Frota")
# Exibe de forma limpa apenas o Nome do Motorista autenticado no cabeçalho
st.markdown(f"👤 **Motorista Logado:** {st.session_state.nome_motorista}")
st.markdown("---")

# -------------------------------------------------------------------------
# CARREGAMENTO DINÂMICO DOS COMPONENTES (ÔNIBUS E TIPOS VIA API REST)
# -------------------------------------------------------------------------

# Puxa dinamicamente a listagem de prefixos de ônibus ativos no banco para alimentar o selectbox
lista_onibus = []
try:
    url_veiculos = f"{SUPABASE_URL}/rest/v1/veiculos?select=prefixo"
    headers_veiculos = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY
    }
    response_veiculos = requests.get(url_veiculos, headers=headers_veiculos)
    
    if response_veiculos.status_code == 200:
        dados_dados = response_veiculos.json()
        # Cria uma lista linear contendo apenas os valores textuais dos prefixos
        lista_onibus = [row["prefixo"] for row in dados_dados]
except Exception:
    lista_onibus = [] # Em caso de falha de conexão, mantém a lista vazia para o tratamento fallback

# Puxa os tipos de incidentes cadastrados no banco para evitar hardcode no código Python
lista_tipos = []
try:
    url_tipos = f"{SUPABASE_URL}/rest/v1/tipo_ocorrencia?select=nome"
    headers_tipos = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY
    }
    response_tipos = requests.get(url_tipos, headers=headers_tipos)
    
    if response_tipos.status_code == 200:
        dados_tipos = response_tipos.json()
        lista_tipos = [row["nome"] for row in dados_tipos]
except Exception:
    lista_tipos = []

# Fallback estratégico: Se o banco de tipos estiver offline ou vazio, o sistema injeta
# opções padrão para que o motorista na rua não fique impossibilitado de enviar o registro.
if not lista_tipos:
    lista_tipos = ["Mecânica", "Batida/Sinistro", "Limpeza/Conservação", "Vandalismo", "Outros"]

# -------------------------------------------------------------------------
# CONSTRUÇÃO DO FORMULÁRIO VISUAL
# -------------------------------------------------------------------------
with st.form("form_ocorrencia", clear_on_submit=True):
    
    # Tratamento Inteligente de Interface: Se a API trouxe os ônibus, mostra um dropdown (evita digitação errada).
    # Se a API falhou, libera um campo de texto aberto para preenchimento manual para manter a resiliência do app.
    if lista_onibus:
        prefixo = st.selectbox("Selecione o Ônibus (Prefixo)", options=lista_onibus)
    else:
        prefixo = st.text_input("Digite o Ônibus (Prefixo)", placeholder="Ex: 40012")
        
    tipo = st.selectbox("Tipo de Ocorrência", options=lista_tipos)
    descricao = st.text_area("Descrição Detalhada do Problema", placeholder="Descreva o que aconteceu...")
    
    # Aciona a câmera nativa do dispositivo móvel do motorista em tempo real
    foto_arquivo = st.camera_input("📸 Tire a foto da ocorrência")
    
    botao_enviar = st.form_submit_button("💾 Registrar Ocorrência", use_container_width=True)

# =========================================================================
# 5. PROCESSAMENTO E ENVIO DOS DADOS (SUBMIT DO FORMULÁRIO)
# =========================================================================
if botao_enviar:
    # Validação rigorosa no front-end: impede o envio de formulários incompletos ou sem evidência fotográfica.
    if not prefixo or not descricao or not foto_arquivo:
        st.error("❌ Por favor, preencha todos os campos e tire a foto antes de enviar!")
    else:
        with st.spinner("Processando e enviando dados... Por favor, aguarde."):
            try:
                # Resgata o nome mapeado durante a autenticação inicial para vincular a autoria do chamado
                nome_registrador = st.session_state.nome_motorista

                # -----------------------------------------------------------------
                # PROCESSO A: Preparação do payload de mídia (Upload para o Storage)
                # -----------------------------------------------------------------
                # Monta uma hash/nome baseado no prefixo e timestamp atual para garantir que
                # um arquivo nunca sobrescreva outro dentro do bucket do Supabase.
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_do_arquivo = f"{prefixo}_{timestamp}.jpg"
                bytes_da_foto = foto_arquivo.getvalue() # Extrai a matriz binária bruta da imagem capturada
                
                # Endereço de destino dentro do Bucket 'fotos-ocorrencias' do Supabase Storage
                url_upload = f"{SUPABASE_URL}/storage/v1/object/fotos-ocorrencias/{nome_do_arquivo}"
                headers_upload = {
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "apikey": SUPABASE_KEY,
                    "Content-Type": "image/jpeg"
                }
                
                # Executa o upload enviando os bytes da foto diretamente no corpo do método POST
                response_api = requests.post(url_upload, headers=headers_upload, data=bytes_da_foto)
                
                if response_api.status_code != 200:
                    st.error(f"❌ O Supabase recusou o arquivo com o código {response_api.status_code}")
                    st.json(response_api.json())
                    st.stop()

                # Se o upload deu certo, constrói a URL pública definitiva onde a foto ficará hospedada na nuvem
                url_da_foto = f"{SUPABASE_URL}/storage/v1/object/public/fotos-ocorrencias/{nome_do_arquivo}"
                
                # -----------------------------------------------------------------
                # PROCESSO B: Inserção do registro textual na tabela 'ocorrencias'
                # -----------------------------------------------------------------
                url_tabela = f"{SUPABASE_URL}/rest/v1/ocorrencias"
                headers_tabela = {
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "apikey": SUPABASE_KEY,
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal" # Otimiza a rede: diz ao banco para não retornar o objeto completo gravado
                }
                
                # Estruturação exata do dicionário JSON mapeado com as colunas da tabela do Supabase
                dados_ocorrencia = {
                    "prefixo_veiculo": str(prefixo), 
                    "tipo": tipo,
                    "descricao": descricao,
                    "foto_url": url_da_foto,
                    "registrador": str(nome_registrador) # Salva o nome amigável do motorista autor
                }
                
                # Envia os dados estruturados para persistência final no banco
                response_tabela = requests.post(url_tabela, headers=headers_tabela, json=dados_ocorrencia)
                
                # Códigos HTTP 200 ou 201 confirmam sucesso de criação no banco PostgREST
                if response_tabela.status_code not in [200, 201]:
                    st.error(f"❌ Erro ao inserir dados na tabela (Código {response_tabela.status_code})")
                    st.json(response_tabela.json() if response_tabela.text else {"detalhe": response_tabela.text})
                    st.stop()
                
                # Feedback de Sucesso Completo na Interface do Usuário
                st.success(f"✅ Ocorrência registrada com sucesso por {nome_registrador}!")
                st.balloons() # Efeito visual comemorativo do Streamlit na tela
                
            except Exception as e:
                st.error(f"❌ Erro crítico no envio: {e}")