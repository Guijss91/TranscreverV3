import streamlit as st
import requests
from typing import List, Dict, Any

st.set_page_config(page_title="Transcritor de Audiências", layout="wide")

# Endpoints n8n
N8N_ENDPOINT_PROCESSO = "https://laboratorio-n8n.nu7ixt.easypanel.host/webhook/numero-processo"
N8N_ENDPOINT_TRANSCRICAO = "https://laboratorio-n8n.nu7ixt.easypanel.host/webhook/transcrever-link"
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
    Recebe do endpoint:
    - Uma lista: [{"nome": ..., "documento": ...}, ...]
    - Um único objeto: {"nome": ..., "documento": ...}
    """
    try:
        resp = requests.post(N8N_ENDPOINT_PROCESSO, json={"numero_processo": numero_processo}, timeout=60)
        resp.raise_for_status()
        dados = resp.json()
        
        if isinstance(dados, list):
            # Já é uma lista
            videos = [
                {"nome": v.get("nome", "Sem nome"), "documento": v.get("documento")}
                for v in dados if v.get("documento")
            ]
        elif isinstance(dados, dict) and dados.get("documento"):
            # É um único objeto, transformar em lista
            videos = [{
                "nome": dados.get("nome", "Sem nome"),
                "documento": dados.get("documento")
            }]
        else:
            st.warning(f"JSON recebido não está no formato esperado. Dados: {dados}")
            return []
        
        return videos
    except Exception as e:
        st.error(f"Erro ao consultar processo: {e}")
        return []

def montar_link_video(numero_processo: str, documento: str) -> str:
    return f"https://novosolar.defensoria.df.gov.br/procapi/processo/{numero_processo}/documento/{documento}/"

def transcrever_video(link_video: str, nome: str, documento: str, numero_processo: str):
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
    try:
        resp = requests.post(N8N_ENDPOINT_SOLAR, json={"transcricao": transcricao_texto}, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Erro ao enviar ao SOLAR: {e}")
        return None

def formatar_apenas_interlocutores_falas(transcricao_payload: Any) -> str:
    try:
        data = None
        if isinstance(transcricao_payload, list) and transcricao_payload:
            data = transcricao_payload[0]
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
                linhas.append(f"{speaker}:\n{text}\n")
            return "\n".join(linhas).strip()

        texto = (data.get("text") or "").strip()
        return texto
    except Exception:
        return ""

st.title("📑 Transcrição de Audiências")

# Entrada do número do processo
numero_processo = st.text_input("Digite o número do processo:", value=st.session_state.numero_processo)

# Consultar processo -> popula lista
if st.button("Consultar Processo"):
    if numero_processo.strip():
        st.session_state.numero_processo = numero_processo.strip()
        st.session_state.videos = consultar_processo(st.session_state.numero_processo)
        st.session_state.video_selecionado = None
        st.session_state.transcricao = None
    else:
        st.warning("Digite um número de processo válido.")

# Lista de vídeos como botões/opções
if st.session_state.videos:
    st.subheader("📹 Vídeos encontrados:")
    for i, video in enumerate(st.session_state.videos):
        col1, col2, col3 = st.columns([3, 2, 2])
        
        with col1:
            st.write(f"**{video['nome']}**")
        
        with col2:
            link = montar_link_video(st.session_state.numero_processo, video["documento"])
            st.markdown(f'<a href="{link}" target="_blank" rel="noopener noreferrer">🔗 Ver vídeo</a>', unsafe_allow_html=True)
        
        with col3:
            if st.button("Selecionar", key=f"btn_{i}"):
                st.session_state.video_selecionado = video
                st.success(f"Vídeo selecionado: {video['nome']}")
        
        st.divider()
else:
    st.info("Nenhum vídeo retornado para este número de processo.")

# Transcrição do vídeo selecionado
if st.session_state.video_selecionado:
    st.subheader("📝 Vídeo selecionado para transcrição:")
    st.write(f"**{st.session_state.video_selecionado['nome']}**")
    
    if st.button("🎤 Transcrever"):
        link = montar_link_video(
            st.session_state.numero_processo,
            st.session_state.video_selecionado["documento"]
        )
        transcricao_payload = transcrever_video(
            link,
            st.session_state.video_selecionado["nome"],
            st.session_state.video_selecionado["documento"],
            st.session_state.numero_processo
        )
        if transcricao_payload:
            st.session_state.transcricao = transcricao_payload
            st.success("Transcrição recebida!")

# Exibição da transcrição
if st.session_state.transcricao:
    st.subheader("📝 Interlocutores e falas")
    texto_formatado = formatar_apenas_interlocutores_falas(st.session_state.transcricao)
    st.text_area("Transcrição (apenas nome e fala)", texto_formatado, height=480)
    
    if st.button("📤 Enviar ao SOLAR"):
        resp = enviar_solar(texto_formatado)
        if resp is not None:
            st.success("Transcrição enviada ao SOLAR com sucesso!")
