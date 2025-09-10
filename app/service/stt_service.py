import azure.cognitiveservices.speech as speechsdk
import datetime
import logging
import numpy as np
import pytz
import torch
import uuid
from typing import Callable

# 로거 설정
logger = logging.getLogger(__name__)


class STTService:
    def __init__(self, speech_region: str, speech_key: str, language: str = 'ko-KR'):
        self.speech_region = speech_region
        self.speech_key = speech_key
        self.language = language
    
    def connect_stt(self, client_context: dict, system_prompt: str, 
                   chat_service, speak_with_queue_func: Callable,
                   client_id: uuid.UUID, socketio=None, vad_iterator=None,
                   stop_speaking_func: Callable = None):
        """STT 연결"""
        try:
            # STT 연결 해제 (기존 연결이 있다면)
            self.disconnect_stt(client_context)
            
            # Speech Config 설정
            speech_config = speechsdk.SpeechConfig(
                subscription=self.speech_key,
                endpoint=f'wss://{self.speech_region}.stt.speech.microsoft.com/speech/universal/v2',
                speech_recognition_language=self.language
            )
            
            # Audio Input Stream 설정
            audio_input_stream = speechsdk.audio.PushAudioInputStream()
            client_context['audio_input_stream'] = audio_input_stream
            
            # Audio Config 설정
            audio_config = speechsdk.audio.AudioConfig(stream=audio_input_stream)
            
            # Speech Recognizer 생성
            speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=speech_config, 
                audio_config=audio_config
            )
            client_context['speech_recognizer'] = speech_recognizer
            
            # 이벤트 핸들러 설정
            speech_recognizer.session_started.connect(
                lambda evt: logger.info(f'STT session started - session id: {evt.session_id}')
            )
            speech_recognizer.session_stopped.connect(
                lambda evt: logger.info('STT session stopped.')
            )
            
            speech_recognition_start_time = datetime.datetime.now(pytz.UTC)
            
            def stt_recognized_cb(evt):
                """STT 인식 완료 콜백"""
                if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                    try:
                        user_query = evt.result.text.strip()
                        if user_query == '':
                            return
                        
                        # WebSocket으로 사용자 쿼리 전송
                        if socketio:
                            socketio.emit("response", {
                                'path': 'api.chat', 
                                'chatResponse': '\n\n ' + user_query + '\n\n'
                            }, room=client_id)
                        
                        # STT 지연시간 계산
                        recognition_result_received_time = datetime.datetime.now(pytz.UTC)
                        speech_finished_offset = (evt.result.offset + evt.result.duration) / 10000
                        stt_latency = round(
                            (recognition_result_received_time - speech_recognition_start_time).total_seconds() * 1000 
                            - speech_finished_offset
                        )
                        logger.debug(f'STT latency: {stt_latency}ms')
                        
                        if socketio:
                            socketio.emit("response", {
                                'path': 'api.chat', 
                                'chatResponse': f"<STTL>{stt_latency}</STTL>"
                            }, room=client_id)
                        
                        # 채팅 처리
                        chat_initiated = client_context.get('chat_initiated', False)
                        if not chat_initiated:
                            chat_service.initialize_chat_context(system_prompt, client_id)
                            client_context['chat_initiated'] = True
                        
                        first_response_chunk = True
                        for chat_response in chat_service.handle_user_query(user_query, client_id, speak_with_queue_func):
                            if first_response_chunk and socketio:
                                socketio.emit("response", {
                                    'path': 'api.chat', 
                                    'chatResponse': 'Assistant: '
                                }, room=client_id)
                                first_response_chunk = False
                            
                            if socketio:
                                socketio.emit("response", {
                                    'path': 'api.chat', 
                                    'chatResponse': chat_response
                                }, room=client_id)
                    
                    except Exception as e:
                        logger.error(f"Error in handling user query: {e}")
            
            speech_recognizer.recognized.connect(stt_recognized_cb)
            
            def stt_recognizing_cb(evt):
                """STT 인식 중 콜백"""
                if not vad_iterator and stop_speaking_func:
                    stop_speaking_func(client_context, False)
            
            speech_recognizer.recognizing.connect(stt_recognizing_cb)
            
            def stt_canceled_cb(evt):
                """STT 취소 콜백"""
                cancellation_details = speechsdk.CancellationDetails(evt.result)
                logger.warning(f'STT connection canceled. Error message: {cancellation_details.error_details}')
            
            speech_recognizer.canceled.connect(stt_canceled_cb)
            
            # 연속 인식 시작
            speech_recognizer.start_continuous_recognition()
            
            return True
            
        except Exception as e:
            raise Exception(f"STT connection failed: {e}")
    
    def disconnect_stt(self, client_context: dict):
        """STT 연결 해제"""
        speech_recognizer = client_context.get('speech_recognizer')
        audio_input_stream = client_context.get('audio_input_stream')
        
        if speech_recognizer:
            speech_recognizer.stop_continuous_recognition()
            connection = speechsdk.Connection.from_recognizer(speech_recognizer)
            connection.close()
            client_context['speech_recognizer'] = None
        
        if audio_input_stream:
            audio_input_stream.close()
            client_context['audio_input_stream'] = None
    
    def handle_audio_chunk(self, client_context: dict, audio_chunk_binary: bytes, 
                          vad_iterator=None, client_id: uuid.UUID = None, 
                          stop_speaking_func: Callable = None):
        """오디오 청크 처리"""
        # 오디오 스트림에 데이터 추가
        audio_input_stream = client_context.get('audio_input_stream')
        if audio_input_stream:
            audio_input_stream.write(audio_chunk_binary)
        
        # VAD 처리 (Voice Activity Detection)
        if vad_iterator:
            audio_buffer = client_context.get('vad_audio_buffer', [])
            audio_buffer.extend(audio_chunk_binary)
            
            if len(audio_buffer) >= 1024:
                audio_chunk_int = np.frombuffer(bytes(audio_buffer[:1024]), dtype=np.int16)
                audio_buffer.clear()
                
                # int16을 float32로 변환
                audio_chunk_float = self._int2float(audio_chunk_int)
                
                # VAD 검사
                vad_detected = vad_iterator(torch.from_numpy(audio_chunk_float))
                if vad_detected:
                    logger.debug("Voice activity detected.")
                    if stop_speaking_func:
                        stop_speaking_func(client_id, False)
    
    def _int2float(self, sound):
        """int16을 float32로 변환"""
        abs_max = np.abs(sound).max()
        if abs_max > 0:
            sound = sound.astype('float32')
            if abs_max < 32768.0:
                sound = sound / 32768.0
            else:
                sound = sound / abs_max
        return sound
