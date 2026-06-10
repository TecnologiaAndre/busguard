import streamlit as st
import requests
import pandas as pd
import datetime

# 1. Configuração da Página (Modo Amplo para visualização em Computador/Monitor)
st.set_page_config(page_title="Painel de Controle - BusGuard", page_icon="🖥️", layout="wide")

# --- CREDENCIAIS PROTEGIDAS (Usando os mesmos secrets do seu app principal) ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
# -------------------------------------------------------------------

# --- CONTROLE DE SESSÃO DO OPERADOR ---
if "operador_logado" not in st.session_state:
    st.session_state.operador_logado = False
if "nome_operador" not in st.session_state:
    st.session_state.nome_operador = ""

# =========================================================================
# TELA DE LOGIN DO OPERADOR
# =========================================================================
if not st.session_state.operador_logado:
    st.title("🖥️ Centro de Controle BusGuard")
    st.subheader("Área Restrita para Operadores e Tratamento de Dados")
    st.markdown("---")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        with st.form("login_operador"):
            usuario = st.text_input("Usuário / Matrícula")
            senha = st.text_input("Senha de Acesso", type="password")
            botao_entrar = st.form_submit_button("Acessar Painel", use_container_width=True)
            
        if botao_entrar:
            # Aqui você pode validar contra uma tabela 'operadores' no Supabase.
            # Para testar rápido, fixei um usuário padrão:
            if usuario == "admin" and senha == "1234":
                st.session_state.operador_logado = True
                st.session_state.nome_operador = "Operador Central"
                st.success("Acesso autorizado!")
                st.rerun()
            else:
                st.error("❌ Usuário ou senha inválidos para o Painel.")
    st.stop()

# =========================================================================
# PAINEL PRINCIPAL (APÓS LOGIN DO OPERADOR)
# =========================================================================

# Cabeçalho do Painel
col_tit, col_user, col_btn_sair = st.columns([3, 1, 1])
with col_tit:
    st.title("📊 Painel de Monitoramento em Tempo Real")
with col_user:
    st.markdown(f"<p style='text-align:right; padding-top:15px;'>👤 <b>{st.session_state.nome_operador}</b></p>", unsafe_allow_html=True)
with col_btn_sair:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Sair do Sistema 🚪", use_container_width=True):
        st.session_state.operador_logado = False
        st.session_state.nome_operador = ""
        st.rerun()

st.markdown("---")

# Botão manual para atualizar os dados na hora
if st.button("🔄 Atualizar Dados Agora"):
    st.toast("Dados atualizados!")

# --- BUSCANDO AS OCORRÊNCIAS NO SUPABASE ---
try:
    # Ordena para trazer as ocorrências mais recentes primeiro (baseado no ID ou created_at)
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
            # Convertendo os dados para um DataFrame do Pandas para facilitar a manipulação
            df = pd.DataFrame(dados_ocorrencias)
            
            # Reorganizando ou renomeando as colunas para o operador ver bonito
            # Certifique-se de que esses nomes de colunas batem com o seu banco
            colunas_exibicao = {
                "id": "ID",
                "prefixo_veiculo": "Ônibus",
                "tipo": "Tipo",
                "descricao": "Descrição",
                "registrador": "Quem Registrou",
                "foto_url": "Link da Foto"
            }
            
            # Filtra apenas as colunas que existem no banco para evitar erros
            colunas_existentes = [col for col in colunas_exibicao.keys() if col in df.columns]
            df_filtrado = df[colunas_existentes].rename(columns=colunas_exibicao)
            
            # --- ÁREA DE METRICAS ---
            m1, m2, m3 = st.columns(3)
            m1.metric("Total de Ocorrências", len(df))
            m2.metric("Último Ônibus Afetado", str(df_filtrado["Ônibus"].iloc[0] if not df_filtrado.empty else "Nenhum"))
            m3.metric("Status do Servidor", "Online 🟢")
            
            st.markdown("### 📋 Lista de Chamados Abertos")
            
            # Exibindo os dados em formato de tabela rica interativa
            # O st.dataframe permite que o operador ordene, filtre e pesquise na tabela
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
            
            # --- DETALHAMENTO DA OCORRÊNCIA SELECIONADA ---
            st.markdown("---")
            st.markdown("### 🔍 Tratamento de Ocorrência Individual")
            
            # Caixa de seleção para o operador escolher qual ID ele quer tratar e ver a foto
            id_selecionado = st.selectbox("Selecione o ID da ocorrência para ver detalhes e fotos:", options=df_filtrado["ID"].tolist())
            
            if id_selecionado:
                # Filtrando a linha correspondente ao ID escolhido
                linha_ocorrencia = df[df["id"] == id_selecionado].iloc[0]
                
                col_dados, col_foto = st.columns([3, 2])
                
                with col_dados:
                    st.write(f"**🚌 Veículo:** {linha_ocorrencia.get('prefixo_veiculo')}")
                    st.write(f"**🚨 Tipo de Problema:** {linha_ocorrencia.get('tipo')}")
                    st.write(f"**👤 Registrado por:** {linha_ocorrencia.get('registrador')}")
                    st.write(f"**📝 Descrição:** {linha_ocorrencia.get('descricao')}")
                    
                    # Campo simulado para o operador interagir/tratar
                    st.text_area("Anotações de Tratamento / Resolução", placeholder="Digite aqui as ações tomadas...")
                    if st.button("✅ Marcar como Resolvido / Tratado", use_container_width=True):
                        st.success(f"Ocorrência {id_selecionado} atualizada com sucesso no sistema!")
                        
                with col_foto:
                    st.write("**📸 Evidência Fotográfica:**")
                    url_foto = linha_ocorrencia.get('foto_url')
                    if url_foto:
                        st.image(url_foto, caption=f"Foto da Ocorrência ID {id_selecionado}", use_container_width=True)
                    else:
                        st.warning("Nenhuma foto anexada a este registro.")
                        
    else:
        st.error(f"Erro ao buscar dados do Supabase. Código: {response.status_code}")
except Exception as e:
    st.error(f"Erro crítico ao carregar painel: {e}")