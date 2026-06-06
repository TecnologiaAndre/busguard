import streamlit as st
from supabase import create_client, Client
import datetime
import requests

# 1. Configurações da Página (Visual Mobile)
st.set_page_config(page_title="BusGuard - Ocorrências", page_icon="🚌", layout="centered")

# --- CREDENCIAIS DO SEU PROJETO ---
SUPABASE_URL = "https://arzogujddgulqdepqxbi.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFyem9ndWpkZGd1bHFkZXBxeGJpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA3Mjg5ODYsImV4cCI6MjA5NjMwNDk4Nn0.yEbFFFZ7M_AytZTwXmGQkU--sHe8Wr7szLtYH5irFnM"
# ----------------------------------

# Conectando ao banco de dados (Necessário para manter a estrutura do cliente ativa)
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

# 2. Buscando os veículos cadastrados DIRETO via API HTTP (Evita bugs da biblioteca)
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

# 3. Interface Visual
st.title("🚌 BusGuard")
st.subheader("Registro de Ocorrências da Frota")
st.markdown("---")

# Formulário
with st.form("form_ocorrencia", clear_on_submit=True):
    
    if lista_onibus:
        prefixo = st.selectbox("Selecione o Ônibus (Prefixo)", options=lista_onibus)
    else:
        prefixo = st.text_input("Digite o Ônibus (Prefixo)", placeholder="Ex: 40012")
        
    tipo = st.selectbox(
        "Tipo de Ocorrência", 
        options=["Mecânica", "Batida/Sinistro", "Limpeza/Conservação", "Vandalismo", "Outros"]
    )
    
    descricao = st.text_area("Descrição Detalhada do Problema", placeholder="Descreva o que aconteceu...")
    foto_arquivo = st.camera_input("📸 Tire a foto da ocorrência")
    botao_enviar = st.form_submit_button("💾 Registrar Ocorrência", use_container_width=True)

# 4. Lógica de Envio Manual via API (Blindado contra erros de sintaxe e rotas)
if botao_enviar:
    if not prefixo or not descricao or not foto_arquivo:
        st.error("❌ Por favor, preencha todos os campos e tire a foto antes de enviar!")
    else:
        with st.spinner("Enviando dados e imagem... Por favor, aguarde."):
            try:
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

                # C. Gera a URL pública da foto
                url_da_foto = f"{SUPABASE_URL}/storage/v1/object/public/fotos-ocorrencias/{nome_do_arquivo}"
                
                # D. Salva os dados na Tabela 'ocorrencias' via HTTP POST direto
                url_tabela = f"{SUPABASE_URL}/rest/v1/ocorrencias"
                headers_tabela = {
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "apikey": SUPABASE_KEY,
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                }
                
                dados_ocorrencia = {
                    "prefixo_veiculo": str(prefixo), 
                    "tipo": tipo,
                    "descricao": descricao,
                    "foto_url": url_da_foto
                }
                
                response_tabela = requests.post(url_tabela, headers=headers_tabela, json=dados_ocorrencia)
                
                if response_tabela.status_code not in [200, 201]:
                    st.error(f"❌ Erro ao inserir dados na tabela (Código {response_tabela.status_code})")
                    st.json(response_tabela.json() if response_tabela.text else {"detalhe": response_tabela.text})
                    st.stop()
                
                st.success("✅ Ocorrência registrada com sucesso no sistema!")
                st.balloons()
                
            except Exception as e:
                st.error(f"❌ Erro crítico no envio: {e}")