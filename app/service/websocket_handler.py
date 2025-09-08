import base64
import uuid
from flask import request
from flask_socketio import join_room


class WebSocketHandler:
    def __init__(self, client_manager, avatar_service, stt_service, chat_service, vad_service):
        self.client_manager = client_manager
        self.avatar_service = avatar_service
        self.stt_service = stt_service
        self.chat_service = chat_service
        self.vad_service = vad_service
    
    def handle_connection(self, socketio):
        """WebSocket 연결 처리"""
        client_id = uuid.UUID(request.args.get('clientId'))
        join_room(client_id)
        print(f"WebSocket connected for client {client_id}.")
    
    def handle_message(self, message, socketio):
        """WebSocket 메시지 처리"""
        client_id = uuid.UUID(message.get('clientId'))
        path = message.get('path')
        client_context = self.client_manager.get_client_context(client_id)
        
        if path == 'api.audio':
            self._handle_audio_message(message, client_context, client_id, socketio)
        elif path == 'api.chat':
            self._handle_chat_message(message, client_context, client_id, socketio)
        elif path == 'api.stopSpeaking':
            self._handle_stop_speaking(client_context, client_id)
    
    def _handle_audio_message(self, message, client_context, client_id, socketio):
        """오디오 메시지 처리"""
        audio_chunk = message.get('audioChunk')
        audio_chunk_binary = base64.b64decode(audio_chunk)
        
        # STT 서비스로 오디오 처리
        self.stt_service.handle_audio_chunk(
            client_context, 
            audio_chunk_binary,
            vad_iterator=self.vad_service.get_vad_iterator(),
            client_id=client_id,
            stop_speaking_func=self.avatar_service.stop_speaking
        )
    
    def _handle_chat_message(self, message, client_context, client_id, socketio):
        """채팅 메시지 처리"""
        chat_initiated = client_context.get('chat_initiated', False)
        if not chat_initiated:
            self.chat_service.initialize_chat_context(message.get('systemPrompt'), client_id)
            client_context['chat_initiated'] = True
        
        user_query = message.get('userQuery')
        first_response_chunk = True
        
        for chat_response in self.chat_service.handle_user_query(
            user_query, client_id, self.avatar_service.speak_with_queue
        ):
            if first_response_chunk:
                socketio.emit("response", {
                    'path': 'api.chat', 
                    'chatResponse': 'Assistant: '
                }, room=client_id)
                first_response_chunk = False
            
            socketio.emit("response", {
                'path': 'api.chat', 
                'chatResponse': chat_response
            }, room=client_id)
    
    def _handle_stop_speaking(self, client_context, client_id):
        """음성 출력 중지 처리"""
        self.avatar_service.stop_speaking(client_context, False)
