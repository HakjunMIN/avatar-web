import json
import time
import traceback
import uuid
import os
import urllib.parse
import logging
from flask import Flask, Response, render_template, request, send_file
from flask_socketio import SocketIO

from service.config_service import ConfigService
from service.client_manager import ClientManager
from service.avatar_service import AvatarService
from service.stt_service import STTService
from service.chat_service import chat_service
from util.vad_iterator import VADService
from service.websocket_handler import WebSocketHandler

# 로거 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

config = ConfigService()

app = Flask(__name__, template_folder='.')
socketio = SocketIO(app)

client_manager = ClientManager(
    config.azure_openai_deployment_name,
    config.cognitive_search_index_name,
    config.default_tts_voice
)

avatar_service = AvatarService(
    speech_region=config.speech_region,
    speech_key=config.speech_key,
    ice_server_url=config.ice_server_url,
    ice_server_url_remote=config.ice_server_url_remote,
    ice_server_username=config.ice_server_username,
    ice_server_password=config.ice_server_password,
    enable_token_auth=config.enable_token_auth_for_speech,
    default_tts_voice=config.default_tts_voice
)

stt_service = STTService(
    speech_region=config.speech_region,
    speech_key=config.speech_key,
    language='ko-KR'
)

vad_service = VADService(
    enable_vad=config.enable_vad,
    threshold=0.5,
    sampling_rate=16000,
    min_silence_duration_ms=150,
    speech_pad_ms=100
)

websocket_handler = WebSocketHandler(
    client_manager, avatar_service, stt_service, chat_service, vad_service
)

chat_service.set_client_contexts(client_manager.get_all_contexts())


@app.route("/")
def index():
    return render_template("static/chat.html", methods=["GET"], client_id=client_manager.initialize_client())


@app.route("/chat")
def chatView():
    return render_template("static/chat.html", methods=["GET"], 
                         client_id=client_manager.initialize_client(), 
                         enable_websockets=config.enable_websockets)


@app.route("/api/getSpeechToken", methods=["GET"])
def getSpeechToken() -> Response:
    speech_token = avatar_service.get_speech_token()
    response = Response(speech_token, status=200)
    response.headers['SpeechRegion'] = config.speech_region
    return response


@app.route("/api/getIceToken", methods=["GET"])
def getIceToken() -> Response:
    ice_token = avatar_service.get_ice_token()
    return Response(ice_token, status=200)


@app.route("/api/getStatus", methods=["GET"])
def getStatus() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    status = client_manager.get_client_status(client_id)
    return Response(json.dumps(status), status=200)


@app.route("/api/connectAvatar", methods=["POST"])
def connectAvatar() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    is_reconnecting = request.headers.get('Reconnect') and request.headers.get('Reconnect').lower() == 'true'
    client_context = client_manager.get_client_context(client_id)
    avatar_service.disconnect_avatar(client_context, is_reconnecting)
    try:
        local_sdp = request.data.decode('utf-8')
        avatar_character = request.headers.get('AvatarCharacter')
        avatar_style = request.headers.get('AvatarStyle')
        background_color = '#FFFFFFFF' if request.headers.get('BackgroundColor') is None else request.headers.get('BackgroundColor')
        background_image_url = request.headers.get('BackgroundImageUrl')
        is_custom_avatar = request.headers.get('IsCustomAvatar', 'false').lower() == 'true'
        transparent_background = request.headers.get('TransparentBackground', 'false').lower() == 'true'
        video_crop = request.headers.get('VideoCrop', 'false').lower() == 'true'
        tts_voice = request.headers.get('TtsVoice')
        custom_voice_endpoint_id = request.headers.get('CustomVoiceEndpointId')
        personal_voice_speaker_profile_id = request.headers.get('PersonalVoiceSpeakerProfileId')
        remote_sdp = avatar_service.connect_avatar(
            client_context=client_context,
            local_sdp=local_sdp,
            avatar_character=avatar_character,
            avatar_style=avatar_style,
            background_color=background_color,
            background_image_url=background_image_url,
            is_custom_avatar=is_custom_avatar,
            transparent_background=transparent_background,
            video_crop=video_crop,
            tts_voice=tts_voice,
            custom_voice_endpoint_id=custom_voice_endpoint_id,
            personal_voice_speaker_profile_id=personal_voice_speaker_profile_id
        )
        if config.enable_websockets:
            socketio.emit("response", {
                'path': 'api.event', 
                'eventType': 'SPEECH_SYNTHESIZER_CONNECTED'
            }, room=client_id)
        return Response(remote_sdp, status=200)
    except Exception as e:
        return Response(f"Avatar connection failed. Error message: {e}", status=400)


@app.route("/api/connectSTT", methods=["POST"])
def connectSTT() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    system_prompt = request.headers.get('SystemPrompt')
    client_context = client_manager.get_client_context(client_id)
    try:
        def speak_with_queue_wrapper(text, ending_silence_ms, target_client_id):
            target_context = client_manager.get_client_context(target_client_id)
            avatar_service.speak_with_queue(text, ending_silence_ms, target_context, target_client_id)
        stt_service.connect_stt(
            client_context=client_context,
            system_prompt=system_prompt,
            chat_service=chat_service,
            speak_with_queue_func=speak_with_queue_wrapper,
            client_id=client_id,
            socketio=socketio if config.enable_websockets else None,
            vad_iterator=vad_service.get_vad_iterator(),
            stop_speaking_func=avatar_service.stop_speaking
        )
        return Response(status=200)
    except Exception as e:
        return Response(f"STT connection failed. Error message: {e}", status=400)


@app.route("/api/disconnectSTT", methods=["POST"])
def disconnectSTT() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    try:
        client_context = client_manager.get_client_context(client_id)
        stt_service.disconnect_stt(client_context)
        return Response('STT Disconnected.', status=200)
    except Exception as e:
        return Response(f"STT disconnection failed. Error message: {e}", status=400)


@app.route("/api/speak", methods=["POST"])
def speak() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    try:
        ssml = request.data.decode('utf-8')
        client_context = client_manager.get_client_context(client_id)
        result_id = avatar_service.speak_ssml(ssml, client_context, True)
        return Response(result_id, status=200)
    except Exception as e:
        return Response(f"Speak failed. Error message: {e}", status=400)


@app.route("/api/stopSpeaking", methods=["POST"])
def stopSpeaking() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    client_context = client_manager.get_client_context(client_id)
    avatar_service.stop_speaking(client_context, False)
    return Response('Speaking stopped.', status=200)


@app.route("/api/chat", methods=["POST"])
def chat() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    client_context = client_manager.get_client_context(client_id)
    chat_initiated = client_context.get('chat_initiated', False)
    if not chat_initiated:
        chat_service.initialize_chat_context(request.headers.get('SystemPrompt'), client_id)
        client_context['chat_initiated'] = True
    user_query = request.data.decode('utf-8')
    def speak_with_queue_wrapper(text, ending_silence_ms, target_client_id):
        target_context = client_manager.get_client_context(target_client_id)
        avatar_service.speak_with_queue(text, ending_silence_ms, target_context, target_client_id)
    return Response(
        chat_service.handle_user_query(user_query, client_id, speak_with_queue_wrapper), 
        mimetype='text/plain', 
        status=200
    )


@app.route("/api/chat/continueSpeaking", methods=["POST"])
def continueSpeaking() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    client_context = client_manager.get_client_context(client_id)
    spoken_text_queue = client_context.get('spoken_text_queue', [])
    speaking_text = client_context.get('speaking_text')
    if speaking_text and config.repeat_speaking_sentence_after_reconnection:
        spoken_text_queue.insert(0, speaking_text)
    if len(spoken_text_queue) > 0:
        avatar_service.speak_with_queue(None, 0, client_context, client_id)
    return Response('Request sent.', status=200)


@app.route("/api/chat/clearHistory", methods=["POST"])
def clearChatHistory() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    client_context = client_manager.get_client_context(client_id)
    chat_service.initialize_chat_context(request.headers.get('SystemPrompt'), client_id)
    client_context['chat_initiated'] = True
    return Response('Chat history cleared.', status=200)


@app.route("/api/disconnectAvatar", methods=["POST"])
def disconnectAvatar() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    try:
        client_context = client_manager.get_client_context(client_id)
        avatar_service.disconnect_avatar(client_context, False)
        return Response('Disconnected avatar', status=200)
    except Exception:
        return Response(traceback.format_exc(), status=400)


@app.route("/api/releaseClient", methods=["POST"])
def releaseClient() -> Response:
    client_id = uuid.UUID(json.loads(request.data)['clientId'])
    try:
        client_context = client_manager.get_client_context(client_id)
        avatar_service.disconnect_avatar(client_context, False)
        stt_service.disconnect_stt(client_context)
        time.sleep(2)
        client_manager.release_client(client_id)
        return Response('Client context released.', status=200)
    except Exception as e:
        logger.error(f"Client context release failed. Error message: {e}")
        return Response(f"Client context release failed. Error message: {e}", status=400)

@app.route("/api/diagram/<path:diagram_path>", methods=["GET"])
def serveDiagram(diagram_path):
    """다이어그램 파일을 서빙하는 엔드포인트"""
    try:
        # URL 디코딩
        decoded_path = urllib.parse.unquote(diagram_path)
        
        # 파일 존재 여부 확인
        if not os.path.exists(decoded_path):
            return Response('Diagram file not found.', status=404)
        
        # 파일 전송
        return send_file(decoded_path, mimetype='image/png')
    except Exception as e:
        logger.error(f"Error serving diagram: {e}")
        return Response(f"Error serving diagram: {e}", status=500)


@socketio.on("connect")
def handleWsConnection():
    websocket_handler.handle_connection(socketio)


@socketio.on("message")
def handleWsMessage(message):
    websocket_handler.handle_message(message, socketio)


if __name__ == '__main__':
    socketio.run(app, debug=True, port=5001)
