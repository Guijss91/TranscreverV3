import streamlit as st
import requests
from typing import List, Dict, Any

st.set_page_config(page_title="Transcritor de Audiências", layout="wide")

# Endpoints n8n
N8N_ENDPOINT_PROCESSO = "https://laboratorio-n8n.nu7ixt.easypanel.host/webhook-test/numero-processo"
N8N_ENDPOINT_TRANSCRICAO = "https://laboratorio-n8n.nu7ixt.easypanel.host/webhook-test/transcrever-link"
N8N_ENDPOINT_SOLAR = "https://laboratorio-n8n.nu7ixt.easypanel.host/webhook-test/trancricao"

# Estado
if "videos" not in st.session_state:
    st.session_state.videos = []
if "video_selecionado" not in st.session_state:
    st.session_state.video_selecionado = None
if "transcricao" not in st.session_state:
    st.session_state.transcricao = None
if "numero_processo" not in st.session_state:
    st.session_state.numero_processo = ""

def consultar_processo(numero_processo: str) -> List[Dict[str, str]]:
    """
    Consome o primeiro endpoint e retorna [{nome, documento}] para montar o dropdown.
    Aceita resposta como dict {"videos": [...]} ou como lista [{"videos": [...]}].
    """
    try:
        resp = requests.post(N8N_ENDPOINT_PROCESSO, json={"numero_processo": numero_processo}, timeout=60)
        resp.raise_for_status()
        dados = resp.json()

        if isinstance(dados, dict) and "videos" in dados:
            videos_raw = dados["videos"]
        elif isinstance(dados, list) and len(dados) > 0 and isinstance(dados, dict) and "videos" in dados:
            videos_raw = dados["videos"]
        else:
            st.warning(f"JSON recebido não está no formato esperado. Dados: {dados}")
            return []

        videos = []
        for v in videos_raw:
            nome = v.get("nome", "Sem nome")
            documento = v.get("documento")
            if documento:
                videos.append({"nome": nome, "documento": documento})
        return videos
    except Exception as e:
        st.error(f"Erro ao consultar processo: {e}")
        return []

def montar_link_video(numero_processo: str, documento: str) -> str:
    return f"https://novosolar.defensoria.df.gov.br/procapi/processo/{numero_processo}/documento/{documento}/"

def transcrever_video(link_video: str, nome: str, documento: str, numero_processo: str):
    """
    Envia ao segundo endpoint: link do vídeo + metadados (nome, id_documento, numero_processo).
    Espera receber JSON no formato de lista com 1 objeto contendo 'utterances'.
    """
    try:
        payload = {
            "link_video": link_video,
            "nome_video": nome,
            "id_documento": documento,
            "numero_processo": numero_processo
        }
        resp = requests.post(N8N_ENDPOINT_TRANSCRICAO, json=payload, timeout=600)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Erro ao transcrever vídeo: {e}")
        return None

def enviar_solar(transcricao_texto: str):
    """
    Envia a transcrição final (texto) ao terceiro endpoint.
    """
    try:
        resp = requests.post(N8N_ENDPOINT_SOLAR, json={"transcricao": transcricao_texto}, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Erro ao enviar ao SOLAR: {e}")
        return None

def formatar_apenas_interlocutores_falas(transcricao_payload: Any) -> str:
    """
    Formata somente 'nome do interlocutor' e 'fala' (utterances[].speaker e utterances[].text).
    - O payload esperado pode ser:
      - lista com um item contendo chave 'utterances'
      - objeto único contendo 'utterances'
    - Fallback: se não houver utterances, usa campo 'text' como uma única fala sem identificação de interlocutor.
    """
    try:
        # Normaliza payload
        data = None
        if isinstance(transcricao_payload, list) and transcricao_payload:
            data = transcricao_payload
        elif isinstance(transcricao_payload, dict):
            data = transcricao_payload
        else:
            return ""

        utterances = data.get("utterances", [])
        linhas = []

        if isinstance(utterances, list) and utterances:
            for utt in utterances:
                speaker = (utt.get("speaker") or "Interlocutor").strip()
                text = (utt.get("text") or "").strip()
                if not text:
                    continue
                # Apenas nome e fala
                linhas.append(f"{speaker}:\n{text}\n")
            return "\n".join(linhas).strip()

        # Fallback para 'text' caso não haja utterances
        texto = (data.get("text") or "").strip()
        return texto
    except Exception:
        return ""

st.title("📑 Transcrição de Audiências")

# Entrada do número do processo
numero_processo = st.text_input("Digite o número do processo:", value=st.session_state.numero_processo)

# Consultar processo -> popula dropdown
if st.button("Consultar Processo"):
    if numero_processo.strip():
        st.session_state.numero_processo = numero_processo.strip()
        st.session_state.videos = consultar_processo(st.session_state.numero_processo)
        st.session_state.video_selecionado = None
        st.session_state.transcricao = None
    else:
        st.warning("Digite um número de processo válido.")

# Dropdown de vídeos (sempre que houver opções)
if st.session_state.videos:
    opcoes_fmt = [v["nome"] for v in st.session_state.videos]
    escolha = st.selectbox("Escolha um vídeo:", options=opcoes_fmt)

    if escolha:
        selecionado = next((v for v in st.session_state.videos if v["nome"] == escolha), None)
        st.session_state.video_selecionado = selecionado
else:
    st.info("Nenhum vídeo retornado para este número de processo.")

# Exibição do link (sem player) e Transcrever
if st.session_state.video_selecionado:
    link = montar_link_video(
        st.session_state.numero_processo,
        st.session_state.video_selecionado.get("documento", "")
    )
    st.markdown(f'<a href="{link}" target="_blank" rel="noopener noreferrer">▶️ Link para o vídeo</a>', unsafe_allow_html=True)

    if st.button("Transcrever"):
        transcricao_payload = transcrever_video(
            link,
            st.session_state.video_selecionado["nome"],
            st.session_state.video_selecionado["documento"],
            st.session_state.numero_processo
        )
        if transcricao_payload:
            st.session_state.transcricao = transcricao_payload
            st.success("Transcrição recebida!")

# Apenas nome e fala por interlocutor
if st.session_state.transcricao:
    st.subheader("📝 Interlocutores e falas")
    texto_formatado = formatar_apenas_interlocutores_falas(st.session_state.transcricao)
    st.text_area("Transcrição (apenas nome e fala)", texto_formatado, height=480)

    # Enviar ao SOLAR a versão já formatada (somente nome + fala)
    if st.button("Enviar ao SOLAR"):
        resp = enviar_solar(texto_formatado)
        if resp is not None:
            st.success("Transcrição enviada ao SOLAR com sucesso!")
