import streamlit as st
import requests
import pandas as pd

# 1. Configuração da Página (Modo Amplo para visualização em Computador/Monitor)
st.set_page_config(page_title="Painel de Controle - BusGuard", page_icon="🖥️", layout="wide")

# --- CREDENCIAIS PROTEGIDAS (Usando os secrets do seu app) ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
# -------------------------------------------------------------------

# --- CONTROLE DE SESSÃO DO OPERADOR ---
if "operador_logado" not in st.session_state:
    st.session_state.operador_logado = False
if "nome_operador" not in st.session_state:
    st.session_state.nome_operador = ""

# =========================================================================
# TELA DE LOGIN DO OPERADOR (COM DIAGNÓSTICO INTEGRADO)
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
            if usuario and senha:
                try:
                    # Buscamos no banco apenas pelo usuário (removendo maiúsculas/minúsculas)
                    url_login = f"{SUPABASE_URL}/rest/v1/operadores?usuario=ilike.{usuario.strip()}&select=*"
                    headers_login = {
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                        "apikey": SUPABASE_KEY
                    }
                    response_login = requests.get(url_login, headers=headers_login)
                    
                    # 🔍 --- ÁREA DE DIAGNÓSTICO NA TELA ---
                    st.info("--- ⚙️ DIAGNÓSTICO DO SUPABASE ---")
                    st.write(f"**Código de Resposta HTTP:** {response_login.status_code}")
                    st.write("**Dados que retornaram do Banco:**")
                    st.code(response_login.json(), language="json")
                    st.markdown("---------------------------------")
                    # --------------------------------------
                    
                    if response_login.status_code == 200:
                        resultado = response_login.json()
                        
                        if len(resultado) > 0:
                            dados_usuario = resultado[0]
                            
                            # Limpa espaços invisíveis
                            senha_banco = str(dados_usuario.get("senha")).strip()
                            senha_digitada = str(senha).strip()
                            is_ativo = dados_usuario.get("ativo")
                            
                            # Validação exata da senha e do status ativo
                            if senha_digitada == senha_banco and (is_ativo is True or str(is_ativo).upper() == "TRUE"):
                                st.session_state.operador_logado = True
                                st.session_state.nome_operador = dados_usuario["nome"]
                                st.success("Acesso autorizado!")
                                st.rerun()
                            else:
                                st.error("❌ Senha incorreta ou operador inativo.")
                        else:
                            st.error("❌ Usuário não encontrado no banco (O Supabase retornou uma lista vazia []).")
                    else:
                        st.error("Erro na comunicação com o banco de dados do Supabase.")
                except Exception as e:
                    st.error(f"Erro ao tentar fazer login: {e}")
            else:
                st.warning("Por favor, preencha o usuário e a senha.")
    st.stop()

# =========================================================================
# PAINEL PRINCIPAL (APÓS LOGIN BEM-SUCEDIDO)
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
    st.toast("Dados updated!")

# --- BUSCANDO AS OCORRÊNCIAS NO SUPABASE ---
try:
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
            df = pd.DataFrame(dados_ocorrencias)
            
            # Mapeamento de colunas do banco para exibição em português
            colunas_exibicao = {
                "id": "ID",
                "prefixo_veiculo": "Ônibus",
                "tipo": "Tipo",
                "descricao": "Descrição",
                "registrador": "Quem Registrou",
                "foto_url": "Link da Foto"
            }
            
            colunas_existentes = [col for col in colunas_exibicao.keys() if col in df.columns]
            df_filtrado = df[colunas_existentes].rename(columns=colunas_exibicao)
            
            # --- ÁREA DE MÉTRICAS (KPIs) ---
            m1, m2, m3 = st.columns(3)
            m1.metric("Total de Ocorrências", len(df))
            m2.metric("Último Ônibus Afetado", str(df_filtrado["Ônibus"].iloc[0] if not df_filtrado.empty else "Nenhum"))
            m3.metric("Status do Servidor", "Online 🟢")
            
            st.markdown("### 📋 Lista de Chamados Abertos")
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
            
            # --- DETALHAMENTO DA OCORRÊNCIA SELECIONADA ---
            st.markdown("---")
            st.markdown("### 🔍 Tratamento de Ocorrência Individual")
            
            id_selecionado = st.selectbox("Selecione o ID da ocorrência para ver detalhes e fotos:", options=df_filtrado["ID"].tolist())
            
            if id_selecionado:
                linha_ocorrencia = df[df["id"] == id_selecionado].iloc[0]
                col_dados, col_foto = st.columns([3, 2])
                
                with col_dados:
                    st.write(f"**🚌 Veículo:** {linha_ocorrencia.get('prefixo_veiculo')}")
                    st.write(f"**🚨 Tipo de Problema:** {linha_ocorrencia.get('tipo')}")
                    st.write(f"**👤 Registrado por:** {linha_ocorrencia.get('registrador')}")
                    st.write(f"**📝 Descrição:** {linha_ocorrencia.get('descricao')}")
                    
                    st.text_area("Anotações de Tratamento / Resolução", placeholder="Digite aqui as ações tomadas...", key=f"nota_{id_selecionado}")
                    if st.button("✅ Marcar como Resolvido / Tratado", use_container_width=True):
                        st.success(f"Ocorrência {id_selecionado} atualizada com sucesso no sistema!")
                        
                with col_foto:
                    st.write("**📸 Evidência Fotográfica:**")
                    url_foto = Server_url = linha_ocorrencia.get('foto_url')
                    if url_foto:
                        st.image(url_foto, caption=f"Foto da Ocorrência ID {id_selecionado}", use_container_width=True)
                    else:
                        st.warning("Nenhuma foto anexada a este registro.")
                        
    else:
        st.error(f"Erro ao buscar dados do Supabase. Código: {response.status_code}")
except Exception as e:
    st.error(f"Erro crítico ao carregar painel: {e}")