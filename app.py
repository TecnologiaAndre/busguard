import streamlit as st
from supabase import create_client, Client
import datetime
import sqlite3  # <- Controla o banco offline
import base64   # <- Transforma a foto em texto e vice-versa

# =========================================================================
# 1. CONFIGURAÇÃO DA INTERFACE, AMBIENTE E BANCO LOCAL (OFFLINE)
# =========================================================================

st.set_page_config(page_title="Ocorrências Em Trânsito", page_icon="🚌", layout="centered")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# Inicialização do Banco de Dados SQLite Local Persistente no Celular
def init_local_db():
    conn = sqlite3.connect("/data/ocorrencias_offline.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fila_ocorrencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prefixo_veiculo TEXT,
            tipo TEXT,
            descricao TEXT,
            registrador TEXT,
            foto_bytes_base64 TEXT,
            data_registro TEXT
        )
    """)
    conn.commit()
    return conn

conn_local = init_local_db()

# NOVO: Função que descarrega os dados do celular para o Supabase quando há internet
def sincronizar_dados_pendentes():
    cursor_local = conn_local.cursor()
    # Puxa tudo o que estiver guardado na fila offline
    cursor_local.execute("SELECT id, prefixo_veiculo, tipo, descricao, registrador, foto_bytes_base64, data_registro FROM fila_ocorrencias")
    registros_pendentes = cursor_local.fetchall()
    
    if registros_pendentes:
        status_placeholder = st.empty()
        status_placeholder.info(f"🔄 Conexão detectada! Sincronizando {len(registros_pendentes)} ocorrência(s) salvas offline...")
        
        sucesso_total = True
        
        for item in registros_pendentes:
            id_local, prefixo, tipo, descricao, registrador, foto_b64, timestamp = item
            nome_do_arquivo = f"{prefixo}_{timestamp}_offline.jpg"
            
            try:
                # Decodifica o texto base64 de volta para os bytes da foto original
                bytes_da_foto = base64.b64decode(foto_b64)
                
                # Envia a foto para o Storage do Supabase
                supabase.storage.from_("fotos-ocorrencias").upload(
                    path=nome_do_arquivo,
                    file=bytes_da_foto,
                    file_options={"content-type": "image/jpeg"}
                )
                
                url_da_foto = supabase.storage.from_("fotos-ocorrencias").get_public_url(nome_do_arquivo)
                
                # Prepara e envia os dados textuais da ocorrência
                dados_ocorrencia = {
                    "prefixo_veiculo": str(prefixo), 
                    "tipo": tipo,
                    "descricao": f"[REGISTRO OFFLINE EM {timestamp}] {descricao}",
                    "foto_url": url_da_foto,
                    "registrador": str(registrador)
                }
                supabase.table("ocorrencias").insert(dados_ocorrencia).execute()
                
                # Se deu certo, deleta essa ocorrência específica da fila do celular
                cursor_local.execute("DELETE FROM fila_ocorrencias WHERE id = ?", (id_local,))
                conn_local.commit()
                
            except Exception:
                # Se falhar no meio do caminho (ex: internet oscilou de novo), para e tenta o resto depois
                sucesso_total = False
                break
        
        if sucesso_total:
            status_placeholder.success("✅ Todas as ocorrências offline foram sincronizadas com sucesso!")
            st.balloons()
        else:
            status_placeholder.warning("⚠️ Algumas ocorrências não puderam ser sincronizadas ainda. Tentaremos na próxima recarga.")

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
                    st.error(f"❌ Erro de conexão ou credenciais. Verifique sua internet: {e}")
                    
    st.stop() 

# =========================================================================
# 4. MÓDULO PRINCIPAL (FORMULÁRIO DE REGISTRO DE OCORRÊNCIAS)
# =========================================================================

# Tenta sincronizar registros que ficaram guardados no celular antes de desenhar a tela
sincronizar_dados_pendentes()

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
# 5. PROCESSAMENTO E ENVIO DOS DADOS (MODIFICADO PARA SUPORTAR OFFLINE)
# =========================================================================
if botao_enviar:
    if not prefixo or not descricao or not foto_arquivo:
        st.error("❌ Por favor, preencha todos os campos e tire a foto antes de enviar!")
    else:
        with st.spinner("Processando dados... Por favor, aguarde."):
            nome_registrador = st.session_state.nome_motorista
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_do_arquivo = f"{prefixo}_{timestamp}.jpg"
            bytes_da_foto = foto_arquivo.getvalue()
            
            try:
                # TENTATIVA ONLINE: Envia foto para o Storage
                supabase.storage.from_("fotos-ocorrencias").upload(
                    path=nome_do_arquivo,
                    file=bytes_da_foto,
                    file_options={"content-type": "image/jpeg"}
                )
                
                url_da_foto = supabase.storage.from_("fotos-ocorrencias").get_public_url(nome_do_arquivo)
                
                # Envia dados para a Tabela
                dados_ocorrencia = {
                    "prefixo_veiculo": str(prefixo), 
                    "tipo": tipo,
                    "descricao": descricao,
                    "foto_url": url_da_foto,
                    "registrador": str(nome_registrador)
                }
                supabase.table("ocorrencias").insert(dados_ocorrencia).execute()
                
                st.success(f"✅ Ocorrência registrada ONLINE com sucesso por {nome_registrador}!")
                st.balloons()
                
            except Exception as erro_rede:
                # SE FALHAR (OFFLINE): Salva localmente no banco SQLite do celular
                cursor_local = conn_local.cursor()
                
                # Transforma os bytes da foto em texto base64 para armazenar no SQLite de forma segura
                foto_base64 = base64.b64encode(bytes_da_foto).decode("utf-8")
                
                cursor_local.execute("""
                    INSERT INTO fila_ocorrencias 
                    (prefixo_veiculo, tipo, descricao, registrador, foto_bytes_base64, data_registro)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (str(prefixo), tipo, descricao, str(nome_registrador), foto_base64, timestamp))
                
                conn_local.commit()
                
                st.warning("⚠️ Você está sem sinal de internet! A ocorrência foi salva localmente no seu celular e será enviada automaticamente assim que a conexão retornar.")