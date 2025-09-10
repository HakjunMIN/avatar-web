import base64
import uuid
import logging
from flask import request
from flask_socketio import join_room

# 로거 설정
logger = logging.getLogger(__name__)


class WebSocketHandler:
    def __init__(self, client_manager, avatar_service, stt_service, chat_service, vad_service, architecture_service=None):
        self.client_manager = client_manager
        self.avatar_service = avatar_service
        self.stt_service = stt_service
        self.chat_service = chat_service
        self.vad_service = vad_service
        self.architecture_service = architecture_service
    
    def handle_connection(self, socketio):
        """WebSocket 연결 처리"""
        client_id = uuid.UUID(request.args.get('clientId'))
        join_room(client_id)
        logger.info(f"WebSocket connected for client {client_id}.")
    
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
        elif path == 'api.bicep':
            self._handle_bicep_generation(message, client_context, client_id, socketio)
    
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
        
        # JSON 구조로 받은 메시지 데이터 처리
        message_data = message.get('messageData', {})
        user_query = message_data.get('query', message.get('userQuery', ''))  # fallback for compatibility
        current_structure = message_data.get('structureJson', '')
        
        # 클라이언트 컨텍스트에 현재 구조 저장
        if current_structure:
            client_context['current_structure'] = current_structure
            logger.info(f"Received structure from WebSocket client {client_id}: {len(current_structure)} characters")
        
        logger.info(f"Processing WebSocket JSON message for {client_id}: query={user_query[:50]}...")
        
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
    
    def _handle_bicep_generation(self, message, client_context, client_id, socketio):
        """Bicep 인프라 코드 생성 처리"""
        logger.info(f"Handling Bicep generation for client {client_id}")
        
        if not self.architecture_service:
            error_message = "Architecture service is not available"
            logger.error(error_message)
            socketio.emit("response", {
                'path': 'api.bicep',
                'error': error_message
            }, room=client_id)
            return
        
        try:
            # 클라이언트로부터 structureJson 받기
            structure_json = message.get('structureJson')
            if not structure_json:
                error_message = "구조 정보가 제공되지 않았습니다. 먼저 아키텍처 다이어그램을 생성해주세요."
                logger.warning(f"No structure JSON provided for client {client_id}")
                socketio.emit("response", {
                    'path': 'api.bicep',
                    'error': error_message
                }, room=client_id)
                return
            
            # 진행 상황 알림
            socketio.emit("response", {
                'path': 'api.bicep',
                'status': 'processing',
                'message': '🔄 Bicep 인프라 코드를 생성하고 있습니다...'
            }, room=client_id)
            
            # Bicep 코드 생성
            bicep_result = self.architecture_service.generate_bicep_infrastructure(structure_json)
            
            if bicep_result['success']:
                # 성공적으로 생성된 경우
                logger.info(f"Bicep code generated successfully for client {client_id}")
                
                response_message = "✅ **Bicep 인프라 코드가 성공적으로 생성되었습니다!**\n\n"
                
                # Bicep 메인 파일
                if bicep_result.get('bicep_code'):
                    response_message += "## 📄 main.bicep\n\n"
                    response_message += "```bicep\n"
                    response_message += bicep_result['bicep_code']
                    response_message += "\n```\n\n"
                
                # 파라미터 파일
                if bicep_result.get('parameters_file'):
                    response_message += "## ⚙️ main.bicepparam\n\n"
                    response_message += "```bicepparam\n"
                    response_message += bicep_result['parameters_file']
                    response_message += "\n```\n\n"
                
                # 배포 가이드
                if bicep_result.get('deployment_guide'):
                    response_message += bicep_result['deployment_guide']
                
                socketio.emit("response", {
                    'path': 'api.bicep',
                    'status': 'completed',
                    'message': response_message,
                    'bicep_code': bicep_result.get('bicep_code'),
                    'parameters_file': bicep_result.get('parameters_file'),
                    'deployment_guide': bicep_result.get('deployment_guide'),
                    'resource_count': bicep_result.get('resource_count', 0)
                }, room=client_id)
                
            else:
                # 생성 실패한 경우
                error_message = f"❌ Bicep 코드 생성에 실패했습니다: {bicep_result.get('error', '알 수 없는 오류')}"
                logger.error(f"Bicep generation failed for client {client_id}: {bicep_result.get('error')}")
                
                socketio.emit("response", {
                    'path': 'api.bicep',
                    'status': 'error',
                    'error': error_message
                }, room=client_id)
                
        except Exception as e:
            error_message = f"❌ Bicep 코드 생성 중 오류가 발생했습니다: {str(e)}"
            logger.exception(f"Exception during Bicep generation for client {client_id}: {str(e)}")
            
            socketio.emit("response", {
                'path': 'api.bicep',
                'status': 'error', 
                'error': error_message
            }, room=client_id)
