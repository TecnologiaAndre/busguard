import streamlit as st
from supabase import create_client, Client
import datetime
import requests

# 1. Configurações da Página (Visual Mobile)
st.set_page_config(page_title="BusGuard - Ocorrências", page_icon="🚌", layout="centered")

# --- CREDENCIAIS PROTEGIDAS (Lendo do cofre seguro do Streamlit) ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
# -------------------------------------------------------------------

# Conectando ao banco de dados (Necessário para manter a estrutura do cliente ativa)
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

# --- CONTROLE DE SESSÃO (LOGIN) ---
if "logado" not in st.session_state:
    st.session_state.logado = False
if "matricula_usuario" not in st.session_state:
    st.session_state.matricula_usuario = ""

# =========================================================================
# TELA DE LOGIN
# =========================================================================
if not st.session_state.logado:
    st.title("🔐 BusGuard - Acesso")
    st.subheader("Identifique-se para acessar o sistema")
    st.markdown("---")
    
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
                    url_login = f"{SUPABASE_URL}/rest/v1/cadastro_login?matricula=eq.{input_matricula}&cpf=eq.{input_cpf}&select=*"
                    headers_login = {
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                        "apikey": SUPABASE_KEY
                    }
                    response_login = requests.get(url_login, headers=headers_login)
                    
                    if response_login.status_code == 200:
                        resultado = response_login.json()
                        
                        if len(resultado) > 0:
                            st.session_state.logado = True
                            st.session_state.matricula_usuario = input_matricula
                            st.success("✅ Login efetuado com sucesso!")
                            st.rerun()
                        else:
                            st.error("❌ Matrícula ou CPF incorretos. Tente novamente.")
                    else:
                        st.error(f"❌ Erro de comunicação com o banco (Código {response_login.status_code})")
                except Exception as e:
                    st.error(f"❌ Erro crítico no login: {e}")
                    
    st.stop()

# =========================================================================
# TELA PRINCIPAL (APLICATIVO LIBERADO APÓS LOGIN)
# =========================================================================

col_titulo, col_sair = st.columns([4, 1])
with col_titulo:
    st.title("🚌 BusGuard")
with col_sair:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Sair 🚪"):
        st.session_state.logado = False
        st.session_state.matricula_usuario = ""
        st.rerun()

st.subheader(f"Registro de Ocorrências da Frota")
st.caption(f"Operador logado: Matrícula {st.session_state.matricula_usuario}")
st.markdown("---")

# 2. Buscando os veículos cadastrados DIRETO via API HTTP
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
        lista_onibus = [row["prefixo"] for row in dados_dados]
except Exception:
    lista_onibus = []

# --- Buscando os Tipos de Ocorrência DIRETO da tabela do Supabase ---
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

if not lista_tipos:
    lista_tipos = ["Mecânica", "Batida/Sinistro", "Limpeza/Conservação", "Vandalismo", "Outros"]

# Formulário de Ocorrências
with st.form("form_ocorrencia", clear_on_submit=True):
    
    if lista_onibus:
        prefixo = st.selectbox("Selecione o Ônibus (Prefixo)", options=lista_onibus)
    else:
        prefixo = st.text_input("Digite o Ônibus (Prefixo)", placeholder="Ex: 40012")
        
    tipo = st.selectbox(
        "Tipo de Ocorrência", 
        options=lista_tipos
    )
    
    descricao = st.text_area("Descrição Detalhada do Problema", placeholder="Descreva o que aconteceu...")
    foto_arquivo = st.camera_input("📸 Tire a foto da ocorrência")
    botao_enviar = st.form_submit_button("💾 Registrar Ocorrência", use_container_width=True)

# 4. Lógica de Envio Manual via API
if botao_enviar:
    if not prefixo or not descricao or not foto_arquivo:
        st.error("❌ Por favor, preencha todos os campos e tire a foto antes de enviar!")
    else:
        with st.spinner("Processando e enviando dados... Por favor, aguarde."):
            try:
                # ---------------------------------------------------------------------------------
                # --- NOVO NO FLUXO: Cruzando a matrícula com a tabela 'motoristas' ---
                # ---------------------------------------------------------------------------------
                nome_registrador = f"Matrícula {st.session_state.matricula_usuario}" # Valor padrão caso a tabela falhe
                
                url_motorista = f"{SUPABASE_URL}/rest/v1/motoristas?matricula=eq.{st.session_state.matricula_usuario}&select=nome"
                headers_motorista = {
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "apikey": SUPABASE_KEY
                }
                response_motorista = requests.get(url_motorista, headers=headers_motorista)
                
                if response_motorista.status_code == 200:
                    dados_motorista = response_motorista.json()
                    if len(dados_motorista) > 0:
                        # Achou o motorista! Armazena o nome dele para salvar na ocorrência
                        nome_registrador = dados_motorista[0]["nome"]
                # ---------------------------------------------------------------------------------

                # A. Preparando nome único do arquivo para a foto
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_do_arquivo = f"{prefixo}_{timestamp}.jpg"
                bytes_da_foto = foto_arquivo.getvalue()
                
                # B. Upload da Foto via HTTP POST (Storage)
                url_upload = f"{SUPABASE_URL}/storage/v1/object/fotos-ocorrencias/{nome_do_arquivo}"
                headers_upload = {
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "apikey": SUPABASE_KEY,
                    "Content-Type": "image/jpeg"
                }
                
                response_api = requests.post(url_upload, headers=headers_upload, data=bytes_da_foto)
                
                if response_api.status_code != 200:
                    st.error(f"❌ O Supabase recusou o arquivo com o código {response_api.status_code}")
                    st.json(response_api.json())
                    st.stop()

                url_da_foto = f"{SUPABASE_URL}/storage/v1/object/public/fotos-ocorrencias/{nome_do_arquivo}"
                
                # C. Salva os dados na Tabela 'ocorrencias'
                url_tabela = f"{SUPABASE_URL}/rest/v1/ocorrencias"
                headers_tabela = {
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "apikey": SUPABASE_KEY,
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                }
                
                # Monta o JSON enviando o NOME do motorista capturado no cruzamento
                dados_ocorrencia = {
                    "prefixo_veiculo": str(prefixo), 
                    "tipo": tipo,
                    "descricao": descricao,
                    "foto_url": url_da_foto,
                    "registrador": str(nome_registrador) # Agora grava o NOME em vez da matrícula pura
                }
                
                response_tabela = requests.post(url_tabela, headers=headers_tabela, json=dados_ocorrencia)
                
                if response_tabela.status_code not in [200, 201]:
                    st.error(f"❌ Erro ao inserir dados na tabela (Código {response_tabela.status_code})")
                    st.json(response_tabela.json() if response_tabela.text else {"detalhe": response_tabela.text})
                    st.stop()
                
                st.success(f"✅ Ocorrência registrada com sucesso por {nome_registrador}!")
                st.balloons()
                
            except Exception as e:
                st.error(f"❌ Erro crítico no envio: {e}")