import azure.cognitiveservices.speech as speechsdk
import datetime
import html
import json
import pytz
import requests
import threading
import time
import uuid


class AvatarService:
    def __init__(self, speech_region: str, speech_key: str, ice_server_url: str = None, 
                 ice_server_url_remote: str = None, ice_server_username: str = None, 
                 ice_server_password: str = None, enable_token_auth: bool = False,
                 default_tts_voice: str = 'en-US-JennyMultilingualV2Neural'):
        self.speech_region = speech_region
        self.speech_key = speech_key
        self.ice_server_url = ice_server_url
        self.ice_server_url_remote = ice_server_url_remote
        self.ice_server_username = ice_server_username
        self.ice_server_password = ice_server_password
        self.enable_token_auth = enable_token_auth
        self.default_tts_voice = default_tts_voice
        
        self.speech_token = None
        self.ice_token = None
        
        # 토큰 갱신 스레드 시작
        self._start_token_refresh_threads()
    
    def _start_token_refresh_threads(self):
        """토큰 갱신 스레드 시작"""
        speech_token_thread = threading.Thread(target=self._refresh_speech_token)
        speech_token_thread.daemon = True
        speech_token_thread.start()
        
        ice_token_thread = threading.Thread(target=self._refresh_ice_token)
        ice_token_thread.daemon = True
        ice_token_thread.start()
    
    def _refresh_speech_token(self):
        """Speech 토큰 갱신"""
        while True:
            try:
                self.speech_token = requests.post(
                    f'https://{self.speech_region}.api.cognitive.microsoft.com/sts/v1.0/issueToken',
                    headers={'Ocp-Apim-Subscription-Key': self.speech_key}
                ).text
            except Exception as e:
                print(f"Failed to refresh speech token: {e}")
            time.sleep(60 * 9)  # 9분마다 갱신
    
    def _refresh_ice_token(self):
        """ICE 토큰 갱신"""
        while True:
            try:
                if self.enable_token_auth:
                    while not self.speech_token:
                        time.sleep(0.2)
                    ice_token_response = requests.get(
                        f'https://{self.speech_region}.tts.speech.microsoft.com/cognitiveservices/avatar/relay/token/v1',
                        headers={'Authorization': f'Bearer {self.speech_token}'}
                    )
                else:
                    ice_token_response = requests.get(
                        f'https://{self.speech_region}.tts.speech.microsoft.com/cognitiveservices/avatar/relay/token/v1',
                        headers={'Ocp-Apim-Subscription-Key': self.speech_key}
                    )
                
                if ice_token_response.status_code == 200:
                    self.ice_token = ice_token_response.text
                else:
                    raise Exception(f"Failed to get ICE token. Status code: {ice_token_response.status_code}")
            except Exception as e:
                print(f"Failed to refresh ICE token: {e}")
            time.sleep(60 * 60 * 24)  # 24시간마다 갱신
    
    def get_speech_token(self) -> str:
        """Speech 토큰 반환"""
        return self.speech_token
    
    def get_ice_token(self) -> str:
        """ICE 토큰 반환"""
        if self.ice_server_url and self.ice_server_username and self.ice_server_password:
            custom_ice_token = json.dumps({
                'Urls': [self.ice_server_url],
                'Username': self.ice_server_username,
                'Password': self.ice_server_password
            })
            return custom_ice_token
        return self.ice_token
    
    def connect_avatar(self, client_context: dict, local_sdp: str, avatar_character: str,
                      avatar_style: str, background_color: str = '#FFFFFFFF',
                      background_image_url: str = None, is_custom_avatar: bool = False,
                      transparent_background: bool = False, video_crop: bool = False,
                      tts_voice: str = None, custom_voice_endpoint_id: str = None,
                      personal_voice_speaker_profile_id: str = None) -> str:
        """Avatar 연결"""
        try:
            # Speech Config 설정
            if self.enable_token_auth:
                while not self.speech_token:
                    time.sleep(0.2)
                speech_config = speechsdk.SpeechConfig(
                    endpoint=f'wss://{self.speech_region}.tts.speech.microsoft.com/cognitiveservices/websocket/v1?enableTalkingAvatar=true'
                )
                speech_config.authorization_token = self.speech_token
            else:
                speech_config = speechsdk.SpeechConfig(
                    subscription=self.speech_key,
                    endpoint=f'wss://{self.speech_region}.tts.speech.microsoft.com/cognitiveservices/websocket/v1?enableTalkingAvatar=true'
                )
            
            if custom_voice_endpoint_id:
                speech_config.endpoint_id = custom_voice_endpoint_id
            
            # Speech Synthesizer 생성
            speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
            client_context['speech_synthesizer'] = speech_synthesizer
            
            # ICE 토큰 설정
            ice_token_obj = json.loads(self.ice_token) if self.ice_token else {}
            if self.ice_server_url and self.ice_server_username and self.ice_server_password:
                ice_token_obj = {
                    'Urls': [self.ice_server_url_remote] if self.ice_server_url_remote else [self.ice_server_url],
                    'Username': self.ice_server_username,
                    'Password': self.ice_server_password
                }
            
            # Avatar 설정
            avatar_config = self._create_avatar_config(
                local_sdp, ice_token_obj, avatar_character, avatar_style,
                background_color, background_image_url, is_custom_avatar,
                transparent_background, video_crop
            )
            
            # 연결 설정
            connection = speechsdk.Connection.from_speech_synthesizer(speech_synthesizer)
            connection.connected.connect(lambda evt: print('TTS Avatar service connected.'))
            
            def tts_disconnected_cb(evt):
                print('TTS Avatar service disconnected.')
                client_context['speech_synthesizer_connection'] = None
                client_context['speech_synthesizer_connected'] = False
            
            connection.disconnected.connect(tts_disconnected_cb)
            connection.set_message_property('speech.config', 'context', json.dumps(avatar_config))
            
            client_context['speech_synthesizer_connection'] = connection
            client_context['speech_synthesizer_connected'] = True
            client_context['tts_voice'] = tts_voice or self.default_tts_voice
            client_context['custom_voice_endpoint_id'] = custom_voice_endpoint_id
            client_context['personal_voice_speaker_profile_id'] = personal_voice_speaker_profile_id
            
            # Avatar 연결 시작
            speech_synthesis_result = speech_synthesizer.speak_text_async('').get()
            print(f'Result id for avatar connection: {speech_synthesis_result.result_id}')
            
            if speech_synthesis_result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = speech_synthesis_result.cancellation_details
                print(f"Speech synthesis canceled: {cancellation_details.reason}")
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    print(f"Error details: {cancellation_details.error_details}")
                    raise Exception(cancellation_details.error_details)
            
            turn_start_message = speech_synthesizer.properties.get_property_by_name('SpeechSDKInternal-ExtraTurnStartMessage')
            remote_sdp = json.loads(turn_start_message)['webrtc']['connectionString']
            
            return remote_sdp
            
        except Exception as e:
            raise Exception(f"Avatar connection failed: {e}")
    
    def _create_avatar_config(self, local_sdp: str, ice_token_obj: dict, avatar_character: str,
                             avatar_style: str, background_color: str, background_image_url: str,
                             is_custom_avatar: bool, transparent_background: bool, video_crop: bool) -> dict:
        """Avatar 설정 생성"""
        return {
            'synthesis': {
                'video': {
                    'protocol': {
                        'name': "WebRTC",
                        'webrtcConfig': {
                            'clientDescription': local_sdp,
                            'iceServers': [{
                                'urls': [ice_token_obj['Urls'][0]] if ice_token_obj.get('Urls') else [],
                                'username': ice_token_obj.get('Username', ''),
                                'credential': ice_token_obj.get('Password', '')
                            }]
                        },
                    },
                    'format': {
                        'crop': {
                            'topLeft': {
                                'x': 600 if video_crop else 0,
                                'y': 0
                            },
                            'bottomRight': {
                                'x': 1320 if video_crop else 1920,
                                'y': 1080
                            }
                        },
                        'bitrate': 1000000
                    },
                    'talkingAvatar': {
                        'customized': is_custom_avatar,
                        'character': avatar_character,
                        'style': avatar_style,
                        'background': {
                            'color': '#00FF00FF' if transparent_background else background_color,
                            'image': {
                                'url': background_image_url
                            }
                        }
                    }
                }
            }
        }
    
    def disconnect_avatar(self, client_context: dict, is_reconnecting: bool = False):
        """Avatar 연결 해제"""
        self.stop_speaking(client_context, is_reconnecting)
        time.sleep(2)
        avatar_connection = client_context.get('speech_synthesizer_connection')
        if avatar_connection:
            avatar_connection.close()
    
    def speak_with_queue(self, text: str, ending_silence_ms: int, client_context: dict, client_id: uuid.UUID):
        """큐를 사용한 음성 출력"""
        spoken_text_queue = client_context.get('spoken_text_queue', [])
        is_speaking = client_context.get('is_speaking', False)
        
        if text:
            spoken_text_queue.append(text)
        
        if not is_speaking:
            def speak_thread():
                tts_voice = client_context.get('tts_voice', self.default_tts_voice)
                personal_voice_speaker_profile_id = client_context.get('personal_voice_speaker_profile_id')
                client_context['is_speaking'] = True
                
                while len(spoken_text_queue) > 0:
                    text_to_speak = spoken_text_queue.pop(0)
                    client_context['speaking_text'] = text_to_speak
                    try:
                        self.speak_text(text_to_speak, tts_voice, personal_voice_speaker_profile_id, 
                                      ending_silence_ms, client_context)
                    except Exception as e:
                        print(f"Error in speaking text: {e}")
                        break
                    client_context['last_speak_time'] = datetime.datetime.now(pytz.UTC)
                
                client_context['is_speaking'] = False
                client_context['speaking_text'] = None
                print("Speaking thread stopped.")
            
            client_context['speaking_thread'] = threading.Thread(target=speak_thread)
            client_context['speaking_thread'].start()
    
    def speak_text(self, text: str, voice: str, speaker_profile_id: str, 
                   ending_silence_ms: int, client_context: dict) -> str:
        """텍스트 음성 출력"""
        ssml = self._create_ssml(text, voice, speaker_profile_id, ending_silence_ms)
        return self.speak_ssml(ssml, client_context, False)
    
    def _create_ssml(self, text: str, voice: str, speaker_profile_id: str, ending_silence_ms: int) -> str:
        """SSML 생성"""
        base_ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='en-US'>
                         <voice name='{voice}'>
                             <mstts:ttsembedding speakerProfileId='{speaker_profile_id}'>
                                 <mstts:leadingsilence-exact value='0'/>
                                 {html.escape(text)}
                             </mstts:ttsembedding>
                         </voice>
                       </speak>"""
        
        if ending_silence_ms > 0:
            base_ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='en-US'>
                             <voice name='{voice}'>
                                 <mstts:ttsembedding speakerProfileId='{speaker_profile_id}'>
                                     <mstts:leadingsilence-exact value='0'/>
                                     {html.escape(text)}
                                     <break time='{ending_silence_ms}ms' />
                                 </mstts:ttsembedding>
                             </voice>
                           </speak>"""
        return base_ssml
    
    def speak_ssml(self, ssml: str, client_context: dict, asynchronized: bool) -> str:
        """SSML 음성 출력"""
        speech_synthesizer = client_context.get('speech_synthesizer')
        if not speech_synthesizer:
            raise Exception("Speech synthesizer not initialized")
        
        speech_synthesis_result = (
            speech_synthesizer.start_speaking_ssml_async(ssml).get() if asynchronized
            else speech_synthesizer.speak_ssml_async(ssml).get()
        )
        
        if speech_synthesis_result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = speech_synthesis_result.cancellation_details
            print(f"Speech synthesis canceled: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print(f"Result ID: {speech_synthesis_result.result_id}. Error details: {cancellation_details.error_details}")
                raise Exception(cancellation_details.error_details)
        
        return speech_synthesis_result.result_id
    
    def stop_speaking(self, client_context: dict, skip_clearing_spoken_text_queue: bool = False):
        """음성 출력 중지"""
        client_context['is_speaking'] = False
        
        if not skip_clearing_spoken_text_queue:
            spoken_text_queue = client_context.get('spoken_text_queue', [])
            spoken_text_queue.clear()
        
        avatar_connection = client_context.get('speech_synthesizer_connection')
        if avatar_connection:
            avatar_connection.send_message_async('synthesis.control', '{"action":"stop"}').get()
