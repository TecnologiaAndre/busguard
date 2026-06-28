import streamlit as st
import datetime
import base64
import requests
import json
import os

st.set_page_config(page_title="Ocorrências Em Trânsito", page_icon="🚌", layout="centered")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

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
    except Exception:
        pass

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
        raise Exception()
    return f"{SUPABASE_URL}/storage/v1/object/public/fotos-ocorrencias/{nome_arquivo}"

def sincronizar_dados_pendentes():
    registros_pendentes = ler_ocorrencias_offline()
    if registros_pendentes:
        status_placeholder = st.empty()
        status_placeholder.info(f"🔄 Conexão detectada! Sincronizando {len(registros_pendentes)} ocorrência(s)...")
        registros_restantes = []
        sucesso_total = True
        for item in registros_pendentes:
            if sucesso_total:
                try:
                    bytes_da_foto = base64.b64decode(item["foto_bytes_base64"])
                    url_da_foto = upload_foto_supabase(f"{item['prefixo_veiculo']}_{item['data_registro']}_offline.jpg", bytes_da_foto)
                    url_tabela = f"{SUPABASE_URL}/rest/v1/ocorrencias"
                    dados_ocorrencia = {
                        "prefixo_veiculo": str(item["prefixo_veiculo"]), 
                        "tipo": item["tipo"],
                        "descricao": f"[REGISTRO OFFLINE] {item['descricao']}",
                        "foto_url": url_da_foto,
                        "registrador": str(item["registrador"])
                    }
                    res = requests.post(url_tabela, headers=SUPABASE_HEADERS, json=dados_ocorrencia)
                    if res.status_code not in [200, 201]: raise Exception()
                except Exception:
                    sucesso_total = False
                    registros_restantes.append(item)
            else:
                registros_restantes.append(item)
        atualizar_ocorrencias_offline(registros_restantes)
        if sucesso_total:
            status_placeholder.success("✅ Todas as ocorrências offline foram sincronizadas!")
            st.balloons()

if "logado" not in st.session_state: st.session_state.logado = False            
if "matricula_usuario" not in st.session_state: st.session_state.matricula_usuario = ""    
if "nome_motorista" not in st.session_state: st.session_state.nome_motorista = ""       

if not st.session_state.logado:
    st.title("🔐 Ocorrências Em Trânsito - Acesso")
    st.subheader("Identifique-se para acessar o sistema")
    st.markdown("---")
    with st.form("form_login"):
        input_matricula = st.text_input("Matrícula")
        input_cpf = st.text_input("CPF (Apenas números)", type="password")
        botao_login = st.form_submit_button("Entrar", use_container_width=True)
    if botao_login:
        if not input_matricula or not input_cpf:
            st.error("❌ Por favor, preencha todos os campos!")
        else:
            with st.spinner("Autenticando..."):
                try:
                    url_login = f"{SUPABASE_URL}/rest/v1/cadastro_login?matricula=eq.{input_matricula}&cpf=eq.{input_cpf}"
                    resposta_login = requests.get(url_login, headers=SUPABASE_HEADERS)
                    resultado = resposta_login.json()
                    if resultado and len(resultado) > 0:
                        url_mot = f"{SUPABASE_URL}/rest/v1/motoristas?matricula=eq.{input_matricula}&select=nome"
                        resposta_mot = requests.get(url_mot, headers=SUPABASE_HEADERS)
                        resultado_mot = resposta_mot.json()
                        username = resultado_mot[0]["nome"] if resultado_mot else f"Matrícula {input_matricula}"
                        st.session_state.logado = True
                        st.session_state.matricula_usuario = input_matricula
                        st.session_state.nome_motorista = username
                        st.success("✅ Login efetuado com sucesso!")
                        st.rerun() 
                    else:
                        st.error("❌ Matrícula ou CPF incorretos.")
                except Exception:
                    st.error("❌ Erro de conexão.")
    st.stop() 

sincronizar_dados_pendentes()

@st.cache_data(ttl=3600)
def carregar_veiculos():
    try:
        resposta = requests.get(f"{SUPABASE_URL}/rest/v1/veiculos?select=prefixo", headers=SUPABASE_HEADERS)
        return [row["prefixo"] for row in resposta.json()] if resposta.status_code == 200 else []
    except Exception: return []

@st.cache_data(ttl=3600)
def carregar_tipos_ocorrencia():
    try:
        resposta = requests.get(f"{SUPABASE_URL}/rest/v1/tipo_ocorrencia?select=nome", headers=SUPABASE_HEADERS)
        return [row["nome"] for row in resposta.json()] if resposta.status_code == 200 else []
    except Exception: return []

col_titulo, col_sair = st.columns([4, 1])
with col_titulo: st.title("🚌 Ocorrências Em Trânsito")
with col_sair:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Sair 🚪"):
        st.session_state.logado = False
        st.rerun()

st.subheader("Registro de Ocorrências da Frota")
st.markdown(f"👤 **Motorista Logado:** {st.session_state.nome_motorista}")
st.markdown("---")

lista_onibus = carregar_veiculos()
lista_tipos = carregar_tipos_ocorrencia()
if not lista_tipos: lista_tipos = ["Mecânica", "Batida/Sinistro", "Limpeza/Conservação", "Vandalismo", "Outros"]

with st.form("form_ocorrencia", clear_on_submit=True):
    prefixo = st.selectbox("Selecione o Ônibus (Prefixo)", options=lista_onibus) if lista_onibus else st.text_input("Digite o Ônibus (Prefixo)")
    tipo = st.selectbox("Tipo de Ocorrência", options=lista_tipos)
    descricao = st.text_area("Descrição Detalhada do Problema")
    foto_arquivo = st.camera_input("📸 Tire a foto da ocorrência")
    botao_enviar = st.form_submit_button("💾 Registrar Ocorrência", use_container_width=True)

if botao_enviar:
    if not prefixo or not descricao or not foto_arquivo:
        st.error("❌ Por favor, preencha todos os campos e tire a foto!")
    else:
        with st.spinner("Processando..."):
            nome_registrador = st.session_state.nome_motorista
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            bytes_da_foto = foto_arquivo.getvalue()
            try:
                url_da_foto = upload_foto_supabase(f"{prefixo}_{timestamp}.jpg", bytes_da_foto)
                url_tabela = f"{SUPABASE_URL}/rest/v1/ocorrencias"
                dados_ocorrencia = {"prefixo_veiculo": str(prefixo), "tipo": tipo, "descricao": descricao, "foto_url": url_da_foto, "registrador": str(nome_registrador)}
                res = requests.post(url_tabela, headers=SUPABASE_HEADERS, json=dados_ocorrencia)
                if res.status_code not in [200, 201]: raise Exception()
                st.success("✅ Ocorrência registrada ONLINE com sucesso!")
                st.balloons()
            except Exception:
                foto_base64 = base64.b64encode(bytes_da_foto).decode("utf-8")
                salvar_ocorrencia_offline({"prefixo_veiculo": str(prefixo), "tipo": tipo, "descricao": descricao, "registrador": str(nome_registrador), "foto_bytes_base64": foto_base64, "data_registro": timestamp})
                st.warning("⚠️ Você está sem internet! Ocorrência salva localmente.")
