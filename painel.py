import hashlib
import hmac
import pandas as pd
import requests
import streamlit as st

# =========================================================================
# 1. CONFIGURAÇÃO DA INTERFACE E SESSÃO HTTP
# =========================================================================
st.set_page_config(
    page_title="Painel de Controle - BusGuard", page_icon="🖥️", layout="wide"
)

# Inicializa as credenciais do banco de dados (Supabase)
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]


# Gerencia conexões persistentes com o servidor para melhorar a performance das requisições HTTP
@st.cache_resource
def obter_sessao_http():
    """Retorna uma sessão HTTP persistente com os headers do Supabase pré-configurados.

    Evita a criação e fechamento de conexões a cada requisição (Connection
    Pooling).
    """
    sessao = requests.Session()
    sessao.headers.update(
        {"Authorization": f"Bearer {SUPABASE_KEY}", "apikey": SUPABASE_KEY}
    )
    return sessao


http_client = obter_sessao_http()

# =========================================================================
# 2. FUNÇÕES AUXILIARES E CRIPTOGRAFIA
# =========================================================================


def gerar_hash_senha(senha_pura: str) -> str:
    """Gera uma assinatura segura SHA-256 usando PBKDF2 com 100.000 iterações.

    Utiliza os primeiros 16 caracteres da SUPABASE_KEY como Salt para proteção
    contra Rainbow Tables.
    """
    salt = SUPABASE_KEY[:16].encode("utf-8")
    hash_calculado = hashlib.pbkdf2_hmac(
        "sha256", senha_pura.encode("utf-8"), salt, 100000
    )
    return hash_calculado.hex()


# TTL de 120 segundos evita sobrecarga no Supabase a cada interação do operador no painel
@st.cache_data(ttl=120)
def buscar_ocorrencias_banco():
    """Busca a lista completa de ocorrências ordenadas por ID decrescente.

    Utiliza cache de dados para acelerar a renderização da interface do
    Streamlit.
    """
    url_buscar = f"{SUPABASE_URL}/rest/v1/ocorrencias?select=*&order=id.desc"
    response = http_client.get(url_buscar)

    if response.status_code == 200:
        return response.json()
    else:
        st.error(
            f"Erro ao buscar dados do Supabase. Código: {response.status_code}"
        )
        return None


# =========================================================================
# 3. GESTÃO DE ESTADO DO OPERADOR (SESSION STATE)
# =========================================================================
if "operador_logado" not in st.session_state:
    st.session_state.operador_logado = False
if "nome_operador" not in st.session_state:
    st.session_state.nome_operador = ""

# =========================================================================
# 4. MÓDULO DE AUTENTICAÇÃO (LOGIN)
# =========================================================================
if not st.session_state.operador_logado:
    st.title("🖥️ Centro de Controle BusGuard")
    st.subheader("Área Restrita para Operadores e Tratamento de Dados")
    st.markdown("---")

    col1, col2 = st.columns([1, 1])
    with col1:
        with st.form("login_operador"):
            usuario = st.text_input("Usuário / Matrícula")
            senha = st.text_input(
                "Senha de Acesso", type="password", placeholder="Digite sua senha"
            )
            botao_entrar = st.form_submit_button(
                "Acessar Painel", use_container_width=True
            )

        if botao_entrar:
            if usuario and senha:
                try:
                    url_login = f"{SUPABASE_URL}/rest/v1/operadores?usuario=ilike.{usuario.strip()}&select=*"
                    response_login = http_client.get(url_login)

                    if response_login.status_code == 200:
                        resultado = response_login.json()

                        if len(resultado) > 0:
                            dados_usuario = resultado[0]
                            id_operador = dados_usuario.get("id")
                            senha_banco = str(dados_usuario.get("senha")).strip()
                            senha_digitada = str(senha).strip()
                            is_ativo = dados_usuario.get("ativo")

                            # Validação preventiva de status do operador
                            if not (
                                is_ativo is True
                                or str(is_ativo).upper() == "TRUE"
                            ):
                                st.error("❌ Operador inativo no sistema.")
                                st.stop()

                            # Verificação de segurança da senha
                            hash_da_digitada = gerar_hash_senha(senha_digitada)
                            login_valido = False
                            precisa_converter_para_hash = False

                            # CENÁRIO A: Senha já migrada para Hash seguro
                            if len(senha_banco) == 64 and hmac.compare_digest(
                                senha_banco, hash_da_digitada
                            ):
                                login_valido = True

                            # CENÁRIO B: Primeiro acesso (senha ainda em texto puro)
                            elif senha_digitada == senha_banco:
                                login_valido = True
                                precisa_converter_para_hash = True

                            if login_valido:
                                # Processo automático de migração para Hash (Segurança Progressiva)
                                if precisa_converter_para_hash:
                                    with st.spinner(
                                        "🔒 Protegendo sua conta: Gerando chave Hash..."
                                    ):
                                        url_patch_senha = f"{SUPABASE_URL}/rest/v1/operadores?id=eq.{id_operador}"
                                        payload_senha = {
                                            "senha": hash_da_digitada
                                        }
                                        http_client.patch(
                                            url_patch_senha, json=payload_senha
                                        )

                                # Armazena credenciais na sessão da aplicação
                                st.session_state.operador_logado = True
                                st.session_state.nome_operador = dados_usuario[
                                    "nome"
                                ]
                                st.success("Acesso autorizado com sucesso!")
                                st.rerun()
                            else:
                                st.error("❌ Senha incorreta.")
                        else:
                            st.error("❌ Usuário não encontrado.")
                    else:
                        st.error(
                            "Erro na comunicação com o banco de dados do Supabase."
                        )
                except Exception as e:
                    st.error(f"Erro ao tentar fazer login: {e}")
            else:
                st.warning("Por favor, preencha o usuário e a senha.")
    st.stop()

# =========================================================================
# 5. PAINEL PRINCIPAL (APÓS LOGIN BEM-SUCEDIDO)
# =========================================================================
col_tit, col_user, col_btn_sair = st.columns([3, 1, 1])
with col_tit:
    st.title("📊 Painel de Monitoramento em Tempo Real")
with col_user:
    st.markdown(
        f"<p style='text-align:right; padding-top:15px;'>👤 <b>{st.session_state.nome_operador}</b></p>",
        unsafe_allow_html=True,
    )
with col_btn_sair:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Sair do Sistema 🚪", use_container_width=True):
        st.session_state.operador_logado = False
        st.session_state.nome_operador = ""
        st.rerun()

st.markdown("---")

# Botão para limpar o cache explicitamente e forçar nova requisição ao Supabase
if st.button("🔄 Atualizar Dados Agora"):
    st.cache_data.clear()
    st.toast("Dados atualizados direto do servidor!")

try:
    # Executa a busca cacheada
    dados_ocorrencias = buscar_ocorrencias_banco()

    if dados_ocorrencias is not None:
        if len(dados_ocorrencias) == 0:
            st.info("ℹ️ Nenhuma ocorrência registrada no momento.")
        else:
            # Engenharia de Recursos / Criação do DataFrame
            df = pd.DataFrame(dados_ocorrencias)

            if "status" not in df.columns:
                df["status"] = "Aberto"

            # Dicionário de mapeamento para exibição visual limpa
            colunas_exibicao = {
                "prefixo_veiculo": "Ônibus",
                "tipo": "Tipo",
                "descricao": "Descrição",
                "registrador": "Quem Registrou",
                "foto_url": "Link da Foto",
                "anotacao_operador": "Tratamento / Resolução",
            }
            colunas_existentes = [
                col for col in colunas_exibicao.keys() if col in df.columns
            ]

            # Separação eficiente usando filtros de vetores do Pandas
            df_abertos = df[df["status"] == "Aberto"]
            df_tratados = df[df["status"] == "Tratado"]

            # Bloco de Métricas Resumo
            m1, m2, m3 = st.columns(3)
            m1.metric("Total de Chamados em Aberto", len(df_abertos))
            m2.metric("Total de Chamados Tratados", len(df_tratados))

            ultimo_onibus = (
                str(df_abertos["prefixo_veiculo"].iloc[0])
                if not df_abertos.empty
                else "Nenhum"
            )
            m3.metric("Último Ônibus Afetado", ultimo_onibus)

            # Renderização de Abas Operacionais
            aba_abertos, aba_tratados = st.tabs(
                ["📋 Chamados Abertos", "✅ Histórico de Tratados"]
            )

            # -----------------------------------------------------------------
            # ABA 1: CHAMADOS EM ABERTO
            # -----------------------------------------------------------------
            with aba_abertos:
                if df_abertos.empty:
                    st.success(
                        "🎉 Excelente! Nenhum chamado em aberto no momento."
                    )
                else:
                    df_abertos_filtrado = df_abertos[colunas_existentes].rename(
                        columns=colunas_exibicao
                    )
                    st.dataframe(
                        df_abertos_filtrado,
                        use_container_width=True,
                        hide_index=True,
                    )

                    st.markdown("---")
                    st.markdown("### 🔍 Tratamento de Ocorrência Individual")

                    # Otimização: Geração de dicionário reduzido usando list comprehension
                    dados_abertos_json = df_abertos[["id", "prefixo_veiculo", "tipo"]].to_dict(orient="records")
                    opcoes_ocorrencias = {
                        row["id"]: f"Veículo {row.get('prefixo_veiculo')} - {row.get('tipo')}"
                        for row in dados_abertos_json
                    }

                    id_selecionado = st.selectbox(
                        "Selecione a ocorrência para ver detalhes e tratar:",
                        options=list(opcoes_ocorrencias.keys()),
                        format_func=lambda x: opcoes_ocorrencias[x],
                        key="sb_tratar_abertos",
                    )

                    if id_selecionado:
                        linha_ocorrencia = df[df["id"] == id_selecionado].iloc[
                            0
                        ]
                        col_dados, col_foto = st.columns([3, 2])

                        with col_dados:
                            st.write(
                                f"**🚌 Veículo:** {linha_ocorrencia.get('prefixo_veiculo')}"
                            )
                            st.write(
                                f"**🚨 Tipo de Problema:** {linha_ocorrencia.get('tipo')}"
                            )
                            st.write(
                                f"**👤 Registrado por:** {linha_ocorrencia.get('registrador')}"
                            )
                            st.write(
                                f"**📝 Descrição:** {linha_ocorrencia.get('descricao')}"
                            )

                            texto_nota = st.text_area(
                                "Anotações de Tratamento / Resolução",
                                placeholder="Digite aqui as ações tomadas...",
                                key=f"nota_{id_selecionado}",
                            )

                            if st.button(
                                "✅ Marcar como Resolvido / Tratado",
                                use_container_width=True,
                            ):
                                with st.spinner("Atualizando dados..."):
                                    try:
                                        url_patch = f"{SUPABASE_URL}/rest/v1/ocorrencias?id=eq.{id_selecionado}"
                                        dados_patch = {
                                            "status": "Tratado",
                                            "anotacao_operador": str(
                                                texto_nota
                                            ),
                                        }

                                        response_patch = http_client.patch(
                                            url_patch, json=dados_patch
                                        )

                                        if response_patch.status_code in [
                                            200,
                                            204,
                                        ]:
                                            st.success("Ocorrência resolvida!")
                                            st.cache_data.clear()  # Limpa cache para forçar recarregamento na próxima linha
                                            st.rerun()
                                        else:
                                            st.error(
                                                f"❌ Erro ao salvar alteração (HTTP {response_patch.status_code})"
                                            )
                                    except Exception as ex_patch:
                                        st.error(
                                            f"❌ Falha na comunicação: {ex_patch}"
                                        )

                        with col_foto:
                            st.write("**📸 Evidência Fotográfica:**")
                            url_foto = linha_ocorrencia.get("foto_url")
                            if url_foto:
                                st.image(
                                    url_foto,
                                    caption="Foto da Ocorrência",
                                    use_container_width=True,
                                )
                            else:
                                st.warning(
                                    "Nenhuma foto anexada a este registro."
                                )

            # -----------------------------------------------------------------
            # ABA 2: HISTÓRICO DE TRATADOS
            # -----------------------------------------------------------------
            with aba_tratados:
                if df_tratados.empty:
                    st.info(
                        "ℹ️ Nenhum chamado foi movido para o histórico de resolvidos até o momento."
                    )
                else:
                    df_tratados_filtrado = df_tratados[
                        colunas_existentes
                    ].rename(columns=colunas_exibicao)
                    st.dataframe(
                        df_tratados_filtrado,
                        use_container_width=True,
                        hide_index=True,
                    )

                    st.markdown("---")
                    st.markdown("### 🔍 Histórico de Detalhes Remotos")

                    dados_tratados_json = df_tratados[["id", "prefixo_veiculo"]].to_dict(orient="records")
                    opcoes_tratados = {
                        row["id"]: f"ID {row['id']} - Veículo {row.get('prefixo_veiculo')} (Tratado)"
                        for row in dados_tratados_json
                    }

                    id_tratado_sel = st.selectbox(
                        "Selecione uma ocorrência resolvida para auditar:",
                        options=list(opcoes_tratados.keys()),
                        format_func=lambda x: opcoes_tratados[x],
                        key="sb_ver_tratados",
                    )

                    if id_tratado_sel:
                        linha_t = df[df["id"] == id_tratado_sel].iloc[0]
                        col_dt, col_ft = st.columns([3, 2])
                        with col_dt:
                            st.info("**✅ Chamado Encerrado / Arquivado**")
                            st.write(
                                f"**🚌 Veículo:** {linha_t.get('prefixo_veiculo')}"
                            )
                            st.write(f"**🚨 Tipo:** {linha_t.get('tipo')}")
                            st.write(
                                f"**👤 Registrado por:** {linha_t.get('registrador')}"
                            )
                            st.write(
                                f"**📝 Descrição Inicial:** {linha_t.get('descricao')}"
                            )
                            st.write(
                                f"**✏️ Nota de Solução do Operador:** {linha_t.get('anotacao_operador')}"
                            )
                        with col_ft:
                            url_foto_t = linha_t.get("foto_url")
                            if url_foto_t:
                                st.image(
                                    url_foto_t,
                                    caption="Foto arquivada",
                                    use_container_width=True,
                                )
except Exception as e:
    st.error(f"Erro crítico ao carregar painel: {e}")