import streamlit as st
from supabase import create_client, Client
import datetime

# =========================================================================
# 1. CONFIGURAÇÃO DA INTERFACE E AMBIENTE
# =========================================================================

st.set_page_config(page_title="Ocorrências Em Trânsito", page_icon="🚌", layout="centered")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# =========================================================================
# 2. GESTÃO DE ESTADO DO OPERADOR (SESSION STATE)
# =========================================================================

if "logado" not in st.session_state:
    st.session_state.logado = False            
if "matricula_usuario" not in st.session_state:
    st.session_state.matricula_usuario = ""    
if "nome_motorista" not in st.session_state:
    st.session_state.nome_motorista = ""       

# =========================================================================
# 3. MÓDULO DE AUTENTICAÇÃO (TELA DE LOGIN)
# =========================================================================

if not st.session_state.logado:
    st.title("🔐 Ocorrências Em Trânsito - Acesso")
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
                    resposta_login = supabase.table("cadastro_login") \
                        .select("*") \
                        .eq("matricula", input_matricula) \
                        .eq("cpf", input_cpf) \
                        .execute()
                    
                    resultado = resposta_login.data
                    
                    if resultado and len(resultado) > 0:
                        nome_encontrado = f"Matrícula {input_matricula}" 
                        
                        resposta_mot = supabase.table("motoristas") \
                            .select("nome") \
                            .eq("matricula", input_matricula) \
                            .execute()
                        
                        if resposta_mot.data and len(resposta_mot.data) > 0:
                            nome_encontrado = resposta_mot.data[0]["nome"]
                        
                        st.session_state.logado = True
                        st.session_state.matricula_usuario = input_matricula
                        st.session_state.nome_motorista = nome_encontrado
                        
                        st.success("✅ Login efetuado com sucesso!")
                        st.rerun() 
                    else:
                        st.error("❌ Matrícula ou CPF incorretos. Tente novamente.")
                except Exception as e:
                    st.error(f"❌ Erro crítico no login: {e}")
                    
    st.stop() 

# =========================================================================
# 4. MÓDULO PRINCIPAL (FORMULÁRIO DE REGISTRO DE OCORRÊNCIAS)
# =========================================================================

@st.cache_data(ttl=3600)
def carregar_veiculos():
    try:
        resposta = supabase.table("veiculos").select("prefixo").execute()
        return [row["prefixo"] for row in resposta.data] if resposta.data else []
    except Exception:
        return []

@st.cache_data(ttl=3600)
def carregar_tipos_ocorrencia():
    try:
        resposta = supabase.table("tipo_ocorrencia").select("nome").execute()
        return [row["nome"] for row in resposta.data] if resposta.data else []
    except Exception:
        return []

col_titulo, col_sair = st.columns([4, 1])
with col_titulo:
    st.title("🚌 Ocorrências Em Trânsito")
with col_sair:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Sair 🚪"):
        st.session_state.logado = False
        st.session_state.matricula_usuario = ""
        st.session_state.nome_motorista = ""
        st.rerun()

st.subheader("Registro de Ocorrências da Frota")
st.markdown(f"👤 **Motorista Logado:** {st.session_state.nome_motorista}")
st.markdown("---")

lista_onibus = carregar_veiculos()
lista_tipos = carregar_tipos_ocorrencia()

if not lista_tipos:
    lista_tipos = ["Mecânica", "Batida/Sinistro", "Limpeza/Conservação", "Vandalismo", "Outros"]

# -------------------------------------------------------------------------
# CONSTRUÇÃO DO FORMULÁRIO VISUAL
# -------------------------------------------------------------------------
with st.form("form_ocorrencia", clear_on_submit=True):
    if lista_onibus:
        prefixo = st.selectbox("Selecione o Ônibus (Prefixo)", options=lista_onibus)
    else:
        prefixo = st.text_input("Digite o Ônibus (Prefixo)", placeholder="Ex: 40012")
        
    tipo = st.selectbox("Tipo de Ocorrência", options=lista_tipos)
    descricao = st.text_area("Descrição Detalhada do Problema", placeholder="Descreva o que aconteceu...")
    foto_arquivo = st.camera_input("📸 Tire a foto da ocorrência")
    
    botao_enviar = st.form_submit_button("💾 Registrar Ocorrência", use_container_width=True)

# =========================================================================
# 5. PROCESSAMENTO E ENVIO DOS DADOS (SUBMIT DO FORMULÁRIO)
# =========================================================================
if botao_enviar:
    if not prefixo or not descricao or not foto_arquivo:
        st.error("❌ Por favor, preencha todos os campos e tire a foto antes de enviar!")
    else:
        with st.spinner("Processando e enviando dados... Por favor, aguarde."):
            try:
                nome_registrador = st.session_state.nome_motorista

                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_do_arquivo = f"{prefixo}_{timestamp}.jpg"
                bytes_da_foto = foto_arquivo.getvalue()
                
                # ALTERAÇÃO AQUI: Passando os bytes puros diretamente (sem BytesIO)
                supabase.storage.from_("fotos-ocorrencias").upload(
                    path=nome_do_arquivo,
                    file=bytes_da_foto,
                    file_options={"content-type": "image/jpeg"}
                )
                
                url_da_foto = supabase.storage.from_("fotos-ocorrencias").get_public_url(nome_do_arquivo)
                
                dados_ocorrencia = {
                    "prefixo_veiculo": str(prefixo), 
                    "tipo": tipo,
                    "descricao": descricao,
                    "foto_url": url_da_foto,
                    "registrador": str(nome_registrador)
                }
                
                supabase.table("ocorrencias").insert(dados_ocorrencia).execute()
                
                st.success(f"✅ Ocorrência registrada com sucesso por {nome_registrador}!")
                st.balloons()
                
            except Exception as e:
                st.error(f"❌ Erro crítico no envio: {e}")