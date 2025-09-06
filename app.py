import azure.cognitiveservices.speech as speechsdk
import base64
import datetime
import html
import json
import numpy as np
import os
import pytz
import requests
import threading
import time
import torch
import traceback
import uuid
from flask import Flask, Response, render_template, request
from flask_socketio import SocketIO, join_room
from vad_iterator import VADIterator, int2float
from chat_service import chat_service
from dotenv import load_dotenv

load_dotenv(override=True)
app = Flask(__name__, template_folder='.')
socketio = SocketIO(app)

speech_region = os.environ.get('SPEECH_REGION') 
speech_key = os.environ.get('SPEECH_KEY')

azure_openai_endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT')
azure_openai_api_key = os.environ.get('AZURE_OPENAI_API_KEY')
azure_openai_deployment_name = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME')
cognitive_search_endpoint = os.environ.get('COGNITIVE_SEARCH_ENDPOINT')
cognitive_search_api_key = os.environ.get('COGNITIVE_SEARCH_API_KEY')
cognitive_search_index_name = os.environ.get('COGNITIVE_SEARCH_INDEX_NAME')
ice_server_url = os.environ.get('ICE_SERVER_URL')
ice_server_url_remote = os.environ.get('ICE_SERVER_URL_REMOTE')
ice_server_username = os.environ.get('ICE_SERVER_USERNAME')
ice_server_password = os.environ.get('ICE_SERVER_PASSWORD')

enable_websockets = True
enable_vad = False
enable_token_auth_for_speech = False
default_tts_voice = 'en-US-JennyMultilingualV2Neural'
repeat_speaking_sentence_after_reconnection = True

client_contexts = {}
speech_token = None
ice_token = None

vad_iterator = None
if enable_vad and enable_websockets:
    vad_model, _ = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad')
    vad_iterator = VADIterator(model=vad_model, threshold=0.5, sampling_rate=16000, min_silence_duration_ms=150, speech_pad_ms=100)


@app.route("/")
def index():
    return render_template("static/chat.html", methods=["GET"], client_id=initializeClient())

@app.route("/chat")
def chatView():
    return render_template("static/chat.html", methods=["GET"], client_id=initializeClient(), enable_websockets=enable_websockets)


@app.route("/api/getSpeechToken", methods=["GET"])
def getSpeechToken() -> Response:
    response = Response(speech_token, status=200)
    response.headers['SpeechRegion'] = speech_region
    return response


@app.route("/api/getIceToken", methods=["GET"])
def getIceToken() -> Response:
    if ice_server_url and ice_server_username and ice_server_password:
        custom_ice_token = json.dumps({
            'Urls': [ice_server_url],
            'Username': ice_server_username,
            'Password': ice_server_password
        })
        return Response(custom_ice_token, status=200)
    return Response(ice_token, status=200)


@app.route("/api/getStatus", methods=["GET"])
def getStatus() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    client_context = client_contexts[client_id]
    status = {
        'speechSynthesizerConnected': client_context['speech_synthesizer_connected']
    }
    return Response(json.dumps(status), status=200)


@app.route("/api/connectAvatar", methods=["POST"])
def connectAvatar() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    isReconnecting = request.headers.get('Reconnect') and request.headers.get('Reconnect').lower() == 'true'
    disconnectAvatarInternal(client_id, isReconnecting)
    client_context = client_contexts[client_id]

    client_context['azure_openai_deployment_name'] = (
        request.headers.get('AoaiDeploymentName') if request.headers.get('AoaiDeploymentName') else azure_openai_deployment_name)
    client_context['cognitive_search_index_name'] = (
        request.headers.get('CognitiveSearchIndexName') if request.headers.get('CognitiveSearchIndexName')
        else cognitive_search_index_name)
    client_context['tts_voice'] = request.headers.get('TtsVoice') if request.headers.get('TtsVoice') else default_tts_voice
    client_context['custom_voice_endpoint_id'] = request.headers.get('CustomVoiceEndpointId')
    client_context['personal_voice_speaker_profile_id'] = request.headers.get('PersonalVoiceSpeakerProfileId')

    custom_voice_endpoint_id = client_context['custom_voice_endpoint_id']

    try:
        if enable_token_auth_for_speech:
            while not speech_token:
                time.sleep(0.2)
            speech_config = speechsdk.SpeechConfig(
                endpoint=f'wss://{speech_region}.tts.speech.microsoft.com/cognitiveservices/websocket/v1?enableTalkingAvatar=true')
            speech_config.authorization_token = speech_token
        else:
            speech_config = speechsdk.SpeechConfig(
                subscription=speech_key,
                endpoint=f'wss://{speech_region}.tts.speech.microsoft.com/cognitiveservices/websocket/v1?enableTalkingAvatar=true')

        if custom_voice_endpoint_id:
            speech_config.endpoint_id = custom_voice_endpoint_id

        client_context['speech_synthesizer'] = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
        speech_synthesizer = client_context['speech_synthesizer']

        ice_token_obj = json.loads(ice_token)
        if ice_server_url and ice_server_username and ice_server_password:
            ice_token_obj = {
                'Urls': [ice_server_url_remote] if ice_server_url_remote else [ice_server_url],
                'Username': ice_server_username,
                'Password': ice_server_password
            }
        local_sdp = request.data.decode('utf-8')
        avatar_character = request.headers.get('AvatarCharacter')
        avatar_style = request.headers.get('AvatarStyle')
        background_color = '#FFFFFFFF' if request.headers.get('BackgroundColor') is None else request.headers.get('BackgroundColor')
        background_image_url = request.headers.get('BackgroundImageUrl')
        is_custom_avatar = request.headers.get('IsCustomAvatar')
        transparent_background = (
            'false' if request.headers.get('TransparentBackground') is None
            else request.headers.get('TransparentBackground'))
        video_crop = 'false' if request.headers.get('VideoCrop') is None else request.headers.get('VideoCrop')
        avatar_config = {
            'synthesis': {
                'video': {
                    'protocol': {
                        'name': "WebRTC",
                        'webrtcConfig': {
                            'clientDescription': local_sdp,
                            'iceServers': [{
                                'urls': [ice_token_obj['Urls'][0]],
                                'username': ice_token_obj['Username'],
                                'credential': ice_token_obj['Password']
                            }]
                        },
                    },
                    'format': {
                        'crop': {
                            'topLeft': {
                                'x': 600 if video_crop.lower() == 'true' else 0,
                                'y': 0
                            },
                            'bottomRight': {
                                'x': 1320 if video_crop.lower() == 'true' else 1920,
                                'y': 1080
                            }
                        },
                        'bitrate': 1000000
                    },
                    'talkingAvatar': {
                        'customized': is_custom_avatar.lower() == 'true',
                        'character': avatar_character,
                        'style': avatar_style,
                        'background': {
                            'color': '#00FF00FF' if transparent_background.lower() == 'true' else background_color,
                            'image': {
                                'url': background_image_url
                            }
                        }
                    }
                }
            }
        }

        connection = speechsdk.Connection.from_speech_synthesizer(speech_synthesizer)
        connection.connected.connect(lambda evt: print('TTS Avatar service connected.'))

        def tts_disconnected_cb(evt):
            print('TTS Avatar service disconnected.')
            client_context['speech_synthesizer_connection'] = None
            client_context['speech_synthesizer_connected'] = False
            if enable_websockets:
                socketio.emit("response", {'path': 'api.event', 'eventType': 'SPEECH_SYNTHESIZER_DISCONNECTED'}, room=client_id)

        connection.disconnected.connect(tts_disconnected_cb)
        connection.set_message_property('speech.config', 'context', json.dumps(avatar_config))
        client_context['speech_synthesizer_connection'] = connection
        client_context['speech_synthesizer_connected'] = True
        if enable_websockets:
            socketio.emit("response", {'path': 'api.event', 'eventType': 'SPEECH_SYNTHESIZER_CONNECTED'}, room=client_id)

        speech_sythesis_result = speech_synthesizer.speak_text_async('').get()
        print(f'Result id for avatar connection: {speech_sythesis_result.result_id}')
        if speech_sythesis_result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = speech_sythesis_result.cancellation_details
            print(f"Speech synthesis canceled: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print(f"Error details: {cancellation_details.error_details}")
                raise Exception(cancellation_details.error_details)
        turn_start_message = speech_synthesizer.properties.get_property_by_name('SpeechSDKInternal-ExtraTurnStartMessage')
        remoteSdp = json.loads(turn_start_message)['webrtc']['connectionString']

        return Response(remoteSdp, status=200)

    except Exception as e:
        return Response(f"Result ID: {speech_sythesis_result.result_id}. Error message: {e}", status=400)


@app.route("/api/connectSTT", methods=["POST"])
def connectSTT() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    disconnectSttInternal(client_id)
    system_prompt = request.headers.get('SystemPrompt')
    client_context = client_contexts[client_id]
    try:
        
        speech_config = speechsdk.SpeechConfig(
            subscription=speech_key, endpoint=f'wss://{speech_region}.stt.speech.microsoft.com/speech/universal/v2', speech_recognition_language='ko-KR') 

        audio_input_stream = speechsdk.audio.PushAudioInputStream()
        client_context['audio_input_stream'] = audio_input_stream

        audio_config = speechsdk.audio.AudioConfig(stream=audio_input_stream)
        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
        client_context['speech_recognizer'] = speech_recognizer

        speech_recognizer.session_started.connect(lambda evt: print(f'STT session started - session id: {evt.session_id}'))
        speech_recognizer.session_stopped.connect(lambda evt: print('STT session stopped.'))

        speech_recognition_start_time = datetime.datetime.now(pytz.UTC)

        def stt_recognized_cb(evt):
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                try:
                    user_query = evt.result.text.strip()
                    if user_query == '':
                        return

                    socketio.emit("response", {'path': 'api.chat', 'chatResponse': '\n\n ' + user_query + '\n\n'}, room=client_id)
                    recognition_result_received_time = datetime.datetime.now(pytz.UTC)
                    speech_finished_offset = (evt.result.offset + evt.result.duration) / 10000
                    stt_latency = round((recognition_result_received_time - speech_recognition_start_time).total_seconds() * 1000 - speech_finished_offset)
                    print(f'STT latency: {stt_latency}ms')
                    socketio.emit("response", {'path': 'api.chat', 'chatResponse': f"<STTL>{stt_latency}</STTL>"}, room=client_id)
                    chat_initiated = client_context['chat_initiated']
                    if not chat_initiated:
                        chat_service.initialize_chat_context(system_prompt, client_id)
                        client_context['chat_initiated'] = True
                    first_response_chunk = True
                    for chat_response in chat_service.handle_user_query(user_query, client_id, speakWithQueue):
                        if first_response_chunk:
                            socketio.emit("response", {'path': 'api.chat', 'chatResponse': 'Assistant: '}, room=client_id)
                            first_response_chunk = False
                        socketio.emit("response", {'path': 'api.chat', 'chatResponse': chat_response}, room=client_id)
                except Exception as e:
                    print(f"Error in handling user query: {e}")
        speech_recognizer.recognized.connect(stt_recognized_cb)

        def stt_recognizing_cb(evt):
            if not vad_iterator:
                stopSpeakingInternal(client_id, False)
        speech_recognizer.recognizing.connect(stt_recognizing_cb)

        def stt_canceled_cb(evt):
            cancellation_details = speechsdk.CancellationDetails(evt.result)
            print(f'STT connection canceled. Error message: {cancellation_details.error_details}')
        speech_recognizer.canceled.connect(stt_canceled_cb)

        speech_recognizer.start_continuous_recognition()
        return Response(status=200)

    except Exception as e:
        return Response(f"STT connection failed. Error message: {e}", status=400)


@app.route("/api/disconnectSTT", methods=["POST"])
def disconnectSTT() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    try:
        disconnectSttInternal(client_id)
        return Response('STT Disconnected.', status=200)
    except Exception as e:
        return Response(f"STT disconnection failed. Error message: {e}", status=400)


@app.route("/api/speak", methods=["POST"])
def speak() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    try:
        ssml = request.data.decode('utf-8')
        result_id = speakSsml(ssml, client_id, True)
        return Response(result_id, status=200)
    except Exception as e:
        return Response(f"Speak failed. Error message: {e}", status=400)


@app.route("/api/stopSpeaking", methods=["POST"])
def stopSpeaking() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    stopSpeakingInternal(client_id, False)
    return Response('Speaking stopped.', status=200)


@app.route("/api/chat", methods=["POST"])
def chat() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    client_context = client_contexts[client_id]
    chat_initiated = client_context['chat_initiated']
    if not chat_initiated:
        chat_service.initialize_chat_context(request.headers.get('SystemPrompt'), client_id)
        client_context['chat_initiated'] = True
    user_query = request.data.decode('utf-8')
    return Response(chat_service.handle_user_query(user_query, client_id, speakWithQueue), mimetype='text/plain', status=200)


@app.route("/api/chat/continueSpeaking", methods=["POST"])
def continueSpeaking() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    client_context = client_contexts[client_id]
    spoken_text_queue = client_context['spoken_text_queue']
    speaking_text = client_context['speaking_text']
    if speaking_text and repeat_speaking_sentence_after_reconnection:
        spoken_text_queue.insert(0, speaking_text)
    if len(spoken_text_queue) > 0:
        speakWithQueue(None, 0, client_id)
    return Response('Request sent.', status=200)


@app.route("/api/chat/clearHistory", methods=["POST"])
def clearChatHistory() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    client_context = client_contexts[client_id]
    chat_service.initialize_chat_context(request.headers.get('SystemPrompt'), client_id)
    client_context['chat_initiated'] = True
    return Response('Chat history cleared.', status=200)


@app.route("/api/disconnectAvatar", methods=["POST"])
def disconnectAvatar() -> Response:
    client_id = uuid.UUID(request.headers.get('ClientId'))
    try:
        disconnectAvatarInternal(client_id, False)
        return Response('Disconnected avatar', status=200)
    except Exception:
        return Response(traceback.format_exc(), status=400)


@app.route("/api/releaseClient", methods=["POST"])
def releaseClient() -> Response:
    client_id = uuid.UUID(json.loads(request.data)['clientId'])
    try:
        disconnectAvatarInternal(client_id, False)
        disconnectSttInternal(client_id)
        time.sleep(2)
        client_contexts.pop(client_id)
        print(f"Client context released for client {client_id}.")
        return Response('Client context released.', status=200)
    except Exception as e:
        print(f"Client context release failed. Error message: {e}")
        return Response(f"Client context release failed. Error message: {e}", status=400)


@socketio.on("connect")
def handleWsConnection():
    client_id = uuid.UUID(request.args.get('clientId'))
    join_room(client_id)
    print(f"WebSocket connected for client {client_id}.")


@socketio.on("message")
def handleWsMessage(message):
    client_id = uuid.UUID(message.get('clientId'))
    path = message.get('path')
    client_context = client_contexts[client_id]
    if path == 'api.audio':
        chat_initiated = client_context['chat_initiated']
        audio_chunk = message.get('audioChunk')
        audio_chunk_binary = base64.b64decode(audio_chunk)
        audio_input_stream = client_context['audio_input_stream']
        if audio_input_stream:
            audio_input_stream.write(audio_chunk_binary)
        if vad_iterator:
            audio_buffer = client_context['vad_audio_buffer']
            audio_buffer.extend(audio_chunk_binary)
            if len(audio_buffer) >= 1024:
                audio_chunk_int = np.frombuffer(bytes(audio_buffer[:1024]), dtype=np.int16)
                audio_buffer.clear()
                audio_chunk_float = int2float(audio_chunk_int)
                vad_detected = vad_iterator(torch.from_numpy(audio_chunk_float))
                if vad_detected:
                    print("Voice activity detected.")
                    stopSpeakingInternal(client_id, False)
    elif path == 'api.chat':
        chat_initiated = client_context['chat_initiated']
        if not chat_initiated:
            chat_service.initialize_chat_context(message.get('systemPrompt'), client_id)
            client_context['chat_initiated'] = True
        user_query = message.get('userQuery')
        first_response_chunk = True
        for chat_response in chat_service.handle_user_query(user_query, client_id, speakWithQueue):
            if first_response_chunk:
                socketio.emit("response", {'path': 'api.chat', 'chatResponse': 'Assistant: '}, room=client_id)
                first_response_chunk = False
            socketio.emit("response", {'path': 'api.chat', 'chatResponse': chat_response}, room=client_id)
    elif path == 'api.stopSpeaking':
        stopSpeakingInternal(client_id, False)


def initializeClient() -> uuid.UUID:
    client_id = uuid.uuid4()
    client_contexts[client_id] = {
        'audio_input_stream': None,
        'vad_audio_buffer': [],
        'speech_recognizer': None,
        'azure_openai_deployment_name': azure_openai_deployment_name,
        'cognitive_search_index_name': cognitive_search_index_name,
        'tts_voice': default_tts_voice,
        'custom_voice_endpoint_id': None,
        'personal_voice_speaker_profile_id': None,
        'speech_synthesizer': None,
        'speech_synthesizer_connection': None,
        'speech_synthesizer_connected': False,
        'speech_token': None,
        'ice_token': None,
        'chat_initiated': False,
        'messages': [],
        'data_sources': [],
        'is_speaking': False,
        'speaking_text': None,
        'spoken_text_queue': [],
        'speaking_thread': None,
        'last_speak_time': None
    }
    chat_service.set_client_contexts(client_contexts)
    return client_id


def refreshIceToken() -> None:
    global ice_token
    while True:
        if enable_token_auth_for_speech:
            while not speech_token:
                time.sleep(0.2)
            ice_token_response = requests.get(
                f'https://{speech_region}.tts.speech.microsoft.com/cognitiveservices/avatar/relay/token/v1',
                headers={'Authorization': f'Bearer {speech_token}'})
        else:
            ice_token_response = requests.get(
                f'https://{speech_region}.tts.speech.microsoft.com/cognitiveservices/avatar/relay/token/v1',
                headers={'Ocp-Apim-Subscription-Key': speech_key})
        if ice_token_response.status_code == 200:
            ice_token = ice_token_response.text
        else:
            raise Exception(f"Failed to get ICE token. Status code: {ice_token_response.status_code}")
        time.sleep(60 * 60 * 24)


def refreshSpeechToken() -> None:
    global speech_token
    while True:
        speech_token = requests.post(
            f'https://{speech_region}.api.cognitive.microsoft.com/sts/v1.0/issueToken',
            headers={'Ocp-Apim-Subscription-Key': speech_key}).text
        time.sleep(60 * 9)


def speakWithQueue(text: str, ending_silence_ms: int, client_id: uuid.UUID) -> None:
    client_context = client_contexts[client_id]
    spoken_text_queue = client_context['spoken_text_queue']
    is_speaking = client_context['is_speaking']
    if text:
        spoken_text_queue.append(text)
    if not is_speaking:
        def speakThread():
            spoken_text_queue = client_context['spoken_text_queue']
            tts_voice = client_context['tts_voice']
            personal_voice_speaker_profile_id = client_context['personal_voice_speaker_profile_id']
            client_context['is_speaking'] = True
            while len(spoken_text_queue) > 0:
                text = spoken_text_queue.pop(0)
                client_context['speaking_text'] = text
                try:
                    speakText(text, tts_voice, personal_voice_speaker_profile_id, ending_silence_ms, client_id)
                except Exception as e:
                    print(f"Error in speaking text: {e}")
                    break
                client_context['last_speak_time'] = datetime.datetime.now(pytz.UTC)
            client_context['is_speaking'] = False
            client_context['speaking_text'] = None
            print("Speaking thread stopped.")
        client_context['speaking_thread'] = threading.Thread(target=speakThread)
        client_context['speaking_thread'].start()


def speakText(text: str, voice: str, speaker_profile_id: str, ending_silence_ms: int, client_id: uuid.UUID) -> str:
    ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='en-US'>
                 <voice name='{voice}'>
                     <mstts:ttsembedding speakerProfileId='{speaker_profile_id}'>
                         <mstts:leadingsilence-exact value='0'/>
                         {html.escape(text)}
                     </mstts:ttsembedding>
                 </voice>
               </speak>"""
    if ending_silence_ms > 0:
        ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='en-US'>
                     <voice name='{voice}'>
                         <mstts:ttsembedding speakerProfileId='{speaker_profile_id}'>
                             <mstts:leadingsilence-exact value='0'/>
                             {html.escape(text)}
                             <break time='{ending_silence_ms}ms' />
                         </mstts:ttsembedding>
                     </voice>
                   </speak>"""
    return speakSsml(ssml, client_id, False)


def speakSsml(ssml: str, client_id: uuid.UUID, asynchronized: bool) -> str:
    speech_synthesizer = client_contexts[client_id]['speech_synthesizer']
    speech_sythesis_result = (
        speech_synthesizer.start_speaking_ssml_async(ssml).get() if asynchronized
        else speech_synthesizer.speak_ssml_async(ssml).get())
    if speech_sythesis_result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = speech_sythesis_result.cancellation_details
        print(f"Speech synthesis canceled: {cancellation_details.reason}")
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print(f"Result ID: {speech_sythesis_result.result_id}. Error details: {cancellation_details.error_details}")
            raise Exception(cancellation_details.error_details)
    return speech_sythesis_result.result_id


def stopSpeakingInternal(client_id: uuid.UUID, skipClearingSpokenTextQueue: bool) -> None:
    client_context = client_contexts[client_id]
    client_context['is_speaking'] = False
    if not skipClearingSpokenTextQueue:
        spoken_text_queue = client_context['spoken_text_queue']
        spoken_text_queue.clear()
    avatar_connection = client_context['speech_synthesizer_connection']
    if avatar_connection:
        avatar_connection.send_message_async('synthesis.control', '{"action":"stop"}').get()


def disconnectAvatarInternal(client_id: uuid.UUID, isReconnecting: bool) -> None:
    client_context = client_contexts[client_id]
    stopSpeakingInternal(client_id, isReconnecting)
    time.sleep(2)
    avatar_connection = client_context['speech_synthesizer_connection']
    if avatar_connection:
        avatar_connection.close()


def disconnectSttInternal(client_id: uuid.UUID) -> None:
    client_context = client_contexts[client_id]
    speech_recognizer = client_context['speech_recognizer']
    audio_input_stream = client_context['audio_input_stream']
    if speech_recognizer:
        speech_recognizer.stop_continuous_recognition()
        connection = speechsdk.Connection.from_recognizer(speech_recognizer)
        connection.close()
        client_context['speech_recognizer'] = None
    if audio_input_stream:
        audio_input_stream.close()
        client_context['audio_input_stream'] = None


speechTokenRefereshThread = threading.Thread(target=refreshSpeechToken)
speechTokenRefereshThread.daemon = True
speechTokenRefereshThread.start()

iceTokenRefreshThread = threading.Thread(target=refreshIceToken)
iceTokenRefreshThread.daemon = True
iceTokenRefreshThread.start()
