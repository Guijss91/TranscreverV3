from flask import Flask, request, jsonify, render_template, session
import requests
from typing import List, Dict, Any
import uuid

app = Flask(__name__)
app.secret_key = 'UAhsuHAUSHUHSUHAUhsUAHusHA'

# Endpoints n8n
N8N_ENDPOINT_PROCESSO = "https://laboratorio-n8n.nu7ixt.easypanel.host/webhook/numero-processo"
N8N_ENDPOINT_TRANSCRICAO = "https://laboratorio-n8n.nu7ixt.easypanel.host/webhook/transcrever-link"
N8N_ENDPOINT_SOLAR = "https://laboratorio-n8n.nu7ixt.easypanel.host/webhook-test/trancricao"

def consultar_processo(numero_processo: str) -> List[Dict[str, str]]:

    try:
        resp = requests.post(N8N_ENDPOINT_PROCESSO, json={"numero_processo": numero_processo}, timeout=60)
        resp.raise_for_status()
        dados = resp.json()
        
        if isinstance(dados, list):
            videos = [
                {"nome": v.get("nome", "Sem nome"), "documento": v.get("documento")}
                for v in dados if v.get("documento")
            ]
        elif isinstance(dados, dict) and dados.get("documento"):
            videos = [{
                "nome": dados.get("nome", "Sem nome"),
                "documento": dados.get("documento")
            }]
        else:
            return []
        
        return videos
    except Exception as e:
        print(f"Erro ao consultar processo: {e}")
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
        print(f"Erro ao transcrever vídeo: {e}")
        return None

def enviar_solar(transcricao_texto: str):
    try:
        resp = requests.post(N8N_ENDPOINT_SOLAR, json={"transcricao": transcricao_texto}, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Erro ao enviar ao SOLAR: {e}")
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/consultar-processo', methods=['POST'])
def consultar_processo_route():
    data = request.get_json()
    numero_processo = data.get('numero_processo', '').strip()
    
    if not numero_processo:
        return jsonify({'success': False, 'message': 'Número do processo é obrigatório'}), 400
    
    videos = consultar_processo(numero_processo)
    session['numero_processo'] = numero_processo
    session['videos'] = videos
    
    # Adicionar links aos vídeos
    for video in videos:
        video['link'] = montar_link_video(numero_processo, video['documento'])
    
    return jsonify({
        'success': True, 
        'videos': videos,
        'total': len(videos)
    })

@app.route('/transcrever', methods=['POST'])
def transcrever_route():
    data = request.get_json()
    documento = data.get('documento')
    
    if not documento:
        return jsonify({'success': False, 'message': 'Documento é obrigatório'}), 400
    
    videos = session.get('videos', [])
    numero_processo = session.get('numero_processo', '')
    
    # Encontrar o vídeo selecionado
    video_selecionado = next((v for v in videos if v['documento'] == documento), None)
    
    if not video_selecionado:
        return jsonify({'success': False, 'message': 'Vídeo não encontrado'}), 404
    
    # Transcrever
    link = montar_link_video(numero_processo, documento)
    transcricao_payload = transcrever_video(
        link,
        video_selecionado['nome'],
        documento,
        numero_processo
    )
    
    if transcricao_payload:
        transcricao_texto = formatar_apenas_interlocutores_falas(transcricao_payload)
        session['transcricao'] = transcricao_texto
        session['video_selecionado'] = video_selecionado
        
        return jsonify({
            'success': True,
            'transcricao': transcricao_texto,
            'video': video_selecionado
        })
    else:
        return jsonify({'success': False, 'message': 'Erro ao transcrever vídeo'}), 500

@app.route('/enviar-solar', methods=['POST'])
def enviar_solar_route():
    transcricao = session.get('transcricao', '')
    
    if not transcricao:
        return jsonify({'success': False, 'message': 'Nenhuma transcrição encontrada'}), 400
    
    resultado = enviar_solar(transcricao)
    
    if resultado is not None:
        return jsonify({'success': True, 'message': 'Transcrição enviada ao SOLAR com sucesso!'})
    else:
        return jsonify({'success': False, 'message': 'Erro ao enviar ao SOLAR'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
