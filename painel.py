import streamlit as st
import requests
import pandas as pd

# =========================================================================
# 1. CONFIGURAÇÃO DA INTERFACE E AMBIENTE
# =========================================================================

# Define o layout em modo 'wide' (amplo) para melhor aproveitamento em monitores.
st.set_page_config(page_title="Painel de Controle - BusGuard", page_icon="🖥️", layout="wide")

# Variáveis seguras extraídas do secrets do Streamlit.
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# =========================================================================
# 2. GESTÃO DE ESTADO DO OPERADOR (SESSION STATE)
# =========================================================================
if "operador_logado" not in st.session_state:
    st.session_state.operador_logado = False
if "nome_operador" not in st.session_state:
    st.session_state.nome_operador = ""

# =========================================================================
# 3. MÓDULO DE AUTENTICAÇÃO (TELA DE LOGIN)
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
                    url_login = f"{SUPABASE_URL}/rest/v1/operadores?usuario=ilike.{usuario.strip()}&select=*"
                    headers_login = {
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                        "apikey": SUPABASE_KEY
                    }
                    response_login = requests.get(url_login, headers=headers_login)
                    
                    if response_login.status_code == 200:
                        resultado = response_login.json()
                        
                        if len(resultado) > 0:
                            dados_usuario = resultado[0]
                            senha_banco = str(dados_usuario.get("senha")).strip()
                            senha_digitada = str(senha).strip()
                            is_ativo = dados_usuario.get("ativo")
                            
                            if senha_digitada == senha_banco and (is_ativo is True or str(is_ativo).upper() == "TRUE"):
                                st.session_state.operador_logado = True
                                st.session_state.nome_operador = dados_usuario["nome"]
                                st.success("Acesso autorizado!")
                                st.rerun()
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
    st.stop()

# =========================================================================
# 4. PAINEL PRINCIPAL (CENTRAL DE MONITORAMENTO)
# =========================================================================

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

if st.button("🔄 Atualizar Dados Agora"):
    st.toast("Dados updated!")

# -------------------------------------------------------------------------
# LEITURA DOS DADOS TOTAIS NO SUPABASE
# -------------------------------------------------------------------------
try:
    # Continuamos buscando todas as ocorrências para calcular as métricas globais de forma centralizada
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
            
            # Garante compatibilidade: Se a coluna 'status' acabou de ser criada e o Pandas não mapeou, força sua existência local
            if "status" not in df.columns:
                df["status"] = "Aberto"

            # Mapeamento técnico de colunas para exibição em tabelas
            colunas_exibicao = {
                "prefixo_veiculo": "Ônibus",
                "tipo": "Tipo",
                "descricao": "Descrição",
                "registrador": "Quem Registrou",
                "foto_url": "Link da Foto",
                "anotacao_operador": "Tratamento / Resolução"
            }
            colunas_existentes = [col for col in colunas_exibicao.keys() if col in df.columns]
            
            # --- SEPARAÇÃO DOS DATA_FRAMES VIA PANDAS ---
            # Separamos as ocorrências baseadas no valor da coluna física 'status' do banco
            df_abertos = df[df["status"] == "Aberto"]
            df_tratados = df[df["status"] == "Tratado"]
            
            # --- ÁREA DE MÉTRICAS ANALÍTICAS (KPIs) ---
            m1, m2, m3 = st.columns(3)
            m1.metric("Total de Chamados em Aberto", len(df_abertos))
            m2.metric("Total de Chamados Tratados", len(df_tratados))
            m3.metric("Último Ônibus Afetado", str(df[df["status"] == "Aberto"]["prefixo_veiculo"].iloc[0] if not df_abertos.empty else "Nenhum"))
            
            # --- CRIAÇÃO DAS ABAS VISUAIS ---
            aba_abertos, aba_tratados = st.tabs(["📋 Chamados Abertos", "✅ Histórico de Tratados"])
            
            # =========================================================================
            # ABA 1: CHAMADOS EM ABERTO
            # =========================================================================
            with aba_abertos:
                if df_abertos.empty:
                    st.success("🎉 Excelente! Nenhum chamado em aberto no momento.")
                else:
                    df_abertos_filtrado = df_abertos[colunas_existentes].rename(columns=colunas_exibicao)
                    st.dataframe(df_abertos_filtrado, use_container_width=True, hide_index=True)
                    
                    # --- MÓDULO ATIVO DE TRATAMENTO INDIVIDUAL (APENAS PARA EM ABERTO) ---
                    st.markdown("---")
                    st.markdown("### 🔍 Tratamento de Ocorrência Individual")
                    
                    # Transforma em lista apenas as linhas que estão de fato com o status 'Aberto'
                    dados_abertos_json = df_abertos.to_dict(orient="records")
                    opcoes_ocorrencias = {
                        row["id"]: f"Veículo {row.get('prefixo_veiculo')} - {row.get('tipo')}" 
                        for row in dados_abertos_json
                    }
                    
                    id_selecionado = st.selectbox(
                        "Selecione a ocorrência para ver detalhes e tratar:", 
                        options=list(opcoes_ocorrencias.keys()),
                        format_func=lambda x: opcoes_ocorrencias[x],
                        key="sb_tratar_abertos"
                    )
                    
                    if id_selecionado:
                        linha_ocorrencia = df[df["id"] == id_selecionado].iloc[0]
                        col_dados, col_foto = st.columns([3, 2])
                        
                        with col_dados:
                            st.write(f"**🚌 Veículo:** {linha_ocorrencia.get('prefixo_veiculo')}")
                            st.write(f"**🚨 Tipo de Problema:** {linha_ocorrencia.get('tipo')}")
                            st.write(f"**👤 Registrado por:** {linha_ocorrencia.get('registrador')}")
                            st.write(f"**📝 Descrição:** {linha_ocorrencia.get('descricao')}")
                            
                            # Campo de texto para o operador detalhar o que foi feito para resolver
                            texto_nota = st.text_area("Anotações de Tratamento / Resolução", placeholder="Digite aqui as ações tomadas...", key=f"nota_{id_selecionado}")
                            
                            # MODIFICADO AQUI: Agora executa a persistência real via HTTP PATCH no Supabase
                            if st.button("✅ Marcar como Resolvido / Tratado", use_container_width=True):
                                with st.spinner("Atualizando dados no servidor do Supabase..."):
                                    try:
                                        # Aponta para a linha exata da ocorrência usando filtros PostgREST (?id=eq.X)
                                        url_patch = f"{SUPABASE_URL}/rest/v1/ocorrencias?id=eq.{id_selecionado}"
                                        
                                        headers_patch = {
                                            "Authorization": f"Bearer {SUPABASE_KEY}",
                                            "apikey": SUPABASE_KEY,
                                            "Content-Type": "application/json"
                                        }
                                        
                                        # Envia o novo status para 'Tratado' e anexa o texto explicativo
                                        dados_patch = {
                                            "status": "Tratado",
                                            "anotacao_operador": str(texto_nota)
                                        }
                                        
                                        response_patch = requests.patch(url_patch, headers=headers_patch, json=dados_patch)
                                        
                                        # Códigos HTTP 200 ou 204 indicam que a alteração de linha foi processada com sucesso
                                        if response_patch.status_code in [200, 204]:
                                            st.success(f"✅ Ocorrência do veículo {linha_ocorrencia.get('prefixo_veiculo')} tratada com sucesso!")
                                            st.rerun() # Força o recarregamento total. O item some de 'Abertos' e vai para 'Tratados'
                                        else:
                                            st.error(f"❌ Erro ao salvar alteração (Código HTTP {response_patch.status_code})")
                                    except Exception as ex_patch:
                                        st.error(f"❌ Falha crítica na comunicação com o banco: {ex_patch}")
                                
                        with col_foto:
                            st.write("**📸 Evidência Fotográfica:**")
                            url_foto = linha_ocorrencia.get('foto_url')
                            if url_foto:
                                st.image(url_foto, caption=f"Foto da Ocorrência", use_container_width=True)
                            else:
                                st.warning("Nenhuma foto anexada a este registro.")

            # =========================================================================
            # ABA 2: HISTÓRICO DE TRATADOS
            # =========================================================================
            with aba_tratados:
                if df_tratados.empty:
                    st.info("ℹ️ Nenhum chamado foi movido para o histórico de resolvidos até o momento.")
                else:
                    df_tratados_filtrado = df_tratados[colunas_existentes].rename(columns=colunas_exibicao)
                    # Renderiza a lista de chamados antigos para auditoria interna
                    st.dataframe(df_tratados_filtrado, use_container_width=True, hide_index=True)
                    
                    # Exibição simples e estática apenas para conferência visual das ocorrências antigas
                    st.markdown("---")
                    st.markdown("### 🔍 Histórico de Detalhes Remotos")
                    
                    dados_tratados_json = df_tratados.to_dict(orient="records")
                    opcoes_tratados = {
                        row["id"]: f"ID {row['id']} - Veículo {row.get('prefixo_veiculo')} (Tratado)" 
                        for row in dados_tratados_json
                    }
                    
                    id_tratado_sel = st.selectbox(
                        "Selecione uma ocorrência resolvida para auditar:",
                        options=list(opcoes_tratados.keys()),
                        format_func=lambda x: opcoes_tratados[x],
                        key="sb_ver_tratados"
                    )
                    
                    if id_tratado_sel:
                        linha_t = df[df["id"] == id_tratado_sel].iloc[0]
                        col_dt, col_ft = st.columns([3, 2])
                        with col_dt:
                            st.info(f"**✅ Chamado Encerrado / Arquivado**")
                            st.write(f"**🚌 Veículo:** {linha_t.get('prefixo_veiculo')}")
                            st.write(f"**🚨 Tipo:** {linha_t.get('tipo')}")
                            st.write(f"**👤 Registrado por:** {linha_t.get('registrador')}")
                            st.write(f"**📝 Descrição Inicial:** {linha_t.get('descricao')}")
                            st.write(f"**✏️ Nota de Solução do Operador:** {linha_t.get('anotacao_operador')}")
                        with col_ft:
                            url_foto_t = linha_t.get('foto_url')
                            if url_foto_t:
                                st.image(url_foto_t, caption="Foto arquivada", use_container_width=True)
                                
    else:
        st.error(f"Erro ao buscar dados do Supabase. Código: {response.status_code}")
except Exception as e:
    st.error(f"Erro crítico ao carregar painel: {e}")