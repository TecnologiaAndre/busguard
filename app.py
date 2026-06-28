import streamlit as st
import datetime
import base64
import requests
import json
import os

# =========================================================================
# 1. CONFIGURAÇÃO DA INTERFACE, AMBIENTE E ARQUIVO LOCAL (OFFLINE)
# =========================================================================

st.set_page_config(page_title="Ocorrências Em Trânsito", page_icon="🚌", layout="centered")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# Caminho do arquivo de texto que guardará os registros offline no celular
ARQUIVO_OFFLINE = "/data/fila_ocorrencias.json"

def ler_ocorrencias_offline():
    if not os.path.exists(ARQUIVO_OFFLINE):
        return []
    try:
        with open(ARQUIVO_OFFLINE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def salvar_ocorrencia_offline(dados):
    lista = ler_ocorrencias_offline()
    lista.append(dados)
    try:
        with open(ARQUIVO_OFFLINE, "w", encoding="utf-8") as f:
            json.dump(lista, f, ensure_ascii=False, indent=4)
    except Exception as e:
        st.error(f"Erro ao salvar arquivo local: {e}")

def atualizar_ocorrencias_offline(nova_lista):
    try:
        with open(ARQUIVO_OFFLINE, "w", encoding="utf-8") as f:
            json.dump(nova_lista, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

def upload_foto_supabase(nome_arquivo, bytes_foto):
    url = f"{SUPABASE_URL}/storage/v1/object/fotos-ocorrencias/{nome_arquivo}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "image/jpeg"
    }
    response = requests.post(url, headers=headers, data=bytes_foto)
    if response.status_code not in [200, 201]:
        raise Exception(f"Erro no upload da foto: {response.text}")
    return f"{SUPABASE_URL}/storage/v1/object/public/fotos-ocorrencias/{nome_arquivo}"

def sincronizar_dados_pendentes():
    registros_pendentes = ler_ocorrencias_offline()
    
    if registros_pendentes:
        status_placeholder = st.empty()
        status_placeholder.info(f"🔄 Conexão detectada! Sincronizando {len(registros_pendentes)} ocorrência(s) salvas offline...")
        
        registros_restantes = []
        sucesso_total = True
        
        for item in registros_pendentes:
            prefixo = item["prefixo_veiculo"]
            tipo = item["tipo"]
            descricao = item["descricao"]
            registrador = item["registrador"]
            foto_b64 = item["foto_bytes_base64"]
            timestamp = item["data_registro"]
            
            nome_do_arquivo = f"{prefixo}_{timestamp}_offline.jpg"
            
            if sucesso_total:
                try:
                    bytes_da_foto = base64.b64decode(foto_b64)
                    url_da_foto = upload_foto_supabase(nome_do_arquivo, bytes_da_foto)
                    
                    url_tabela = f"{SUPABASE_URL}/rest/v1/ocorrencias"
                    dados_ocorrencia = {
                        "prefixo_veiculo": str(prefixo), 
                        "tipo": tipo,
                        "descricao": f"[REGISTRO OFFLINE EM {timestamp}] {descricao}",
                        "foto_url": url_da_foto,
                        "registrador": str(registrador)
                    }
                    res = requests.post(url_tabela, headers=SUPABASE_HEADERS, json=dados_ocorrencia)
                    if res.status_code not in [200, 201]:
                        raise Exception()
                except Exception:
                    sucesso_total = False
                    # Se falhar este item, guarda ele e os próximos de volta no arquivo
                    registros_restantes.append(item)
            else:
                registros_restantes.append(item)
        
        # Atualiza o arquivo local apenas com o que sobrou (ou limpa se enviou tudo)
        atualizar_ocorrencias_offline(registros_restantes)
        
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
# 3. MÓDULO DE AUTENTICAÇÃO (TELA DE LOGIN VIA HTTP REST)
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
                    url_login = f"{SUPABASE_URL}/rest/v1/cadastro_login?matricula=eq.{input_matricula}&cpf=eq.{input_cpf}"
                    resposta_login = requests.get(url_login, headers=SUPABASE_HEADERS)
                    resultado = resposta_login.json()
                    
                    if resultado and len(resultado) > 0:
                        nome_encontrado = f"Matrícula {input_matricula}" 
                        
                        url_mot = f"{SUPABASE_URL}/rest/v1/motoristas?matricula=eq.{input_matricula}&select=nome"
                        resposta_mot = requests.get(url_mot, headers=SUPABASE_HEADERS)
                        resultado_mot = resposta_mot.json()
                        
                        if resultado_mot and len(resultado_mot) > 0:
                            username = resultado_mot[0]["nome"]
                        else:
                            username = f"Matrícula {input_matricula}"
                        
                        st.session_state.logado = True
                        st.session_state.matricula_usuario = input_matricula
                        st.session_state.nome_motorista = username
                        
                        st.success("✅ Login efetuado com sucesso!")
                        st.rerun() 
                    else:
                        st.error("❌ Matrícula ou CPF incorretos. Tente novamente.")
                except Exception:
                    st.error(f"❌ Erro de conexão ou credenciais. Verifique sua internet.")
                    
    st.stop() 

# =========================================================================
# 4. MÓDULO PRINCIPAL (FORMULÁRIO DE REGISTRO DE OCORRÊNCIAS)
# =========================================================================

sincronizar_dados_pendentes()

@st.cache_data(ttl=3600)
def carregar_veiculos():
    try:
        url = f"{SUPABASE_URL}/rest/v1/veiculos?select=prefixo"
        resposta = requests.get(url, headers=SUPABASE_HEADERS)
        return [row["prefixo"] for row in resposta.json()] if resposta.status_code == 200 else []
    except Exception:
        return []

@st.cache_data(ttl=3600)
def carregar_tipos_ocorrencia():
    try:
        url = f"{SUPABASE_URL}/rest/v1/tipo_ocorrencia?select=nome"
        resposta = requests.get(url, headers=SUPABASE_HEADERS)
        return [row["nome"] for row in resposta.json()] if resposta.status_code == 200 else []
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
# 5. PROCESSAMENTO E ENVIO DOS DADOS (SALVAMENTO LOCAL EM JSON SE OFFLINE)
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
                url_da_foto = upload_foto_supabase(nome_do_arquivo, bytes_da_foto)
                
                url_tabela = f"{SUPABASE_URL}/rest/v1/ocorrencias"
                dados_ocorrencia = {
                    "prefixo_veiculo": str(prefixo), 
                    "tipo": tipo,
                    "descricao": descricao,
                    "foto_url": url_da_foto,
                    "registrador": str(nome_registrador)
                }
                res = requests.post(url_tabela, headers=SUPABASE_HEADERS, json=dados_ocorrencia)
                if res.status_code not in [200, 201]:
                    raise Exception()
                
                st.success(f"✅ Ocorrência registrada ONLINE com sucesso por {nome_registrador}!")
                st.balloons()
                
            except Exception:
                # SE DER ERRO DE CONEXÃO: Salva em formato JSON no sistema de arquivos local persistido pelo stlite
                foto_base64 = base64.b64encode(bytes_da_foto).decode("utf-8")
                
                dados_offline = {
                    "prefixo_veiculo": str(prefixo),
                    "tipo": tipo,
                    "descricao": descricao,
                    "registrador": str(nome_registrador),
                    "foto_bytes_base64": foto_base64,
                    "data_registro": timestamp
                }
                
                salvar_ocorrencia_offline(dados_offline)
                st.warning("⚠️ Você está sem sinal de internet! A ocorrência foi salva localmente no seu celular e será enviada automaticamente assim que a conexão retornar.")