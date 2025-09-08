import uuid
from typing import Dict, Any


class ClientManager:
    def __init__(self, azure_openai_deployment_name: str, cognitive_search_index_name: str, default_tts_voice: str):
        self.client_contexts: Dict[uuid.UUID, Dict[str, Any]] = {}
        self.azure_openai_deployment_name = azure_openai_deployment_name
        self.cognitive_search_index_name = cognitive_search_index_name
        self.default_tts_voice = default_tts_voice
    
    def initialize_client(self) -> uuid.UUID:
        """새 클라이언트 초기화"""
        client_id = uuid.uuid4()
        self.client_contexts[client_id] = {
            'audio_input_stream': None,
            'vad_audio_buffer': [],
            'speech_recognizer': None,
            'azure_openai_deployment_name': self.azure_openai_deployment_name,
            'cognitive_search_index_name': self.cognitive_search_index_name,
            'tts_voice': self.default_tts_voice,
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
        return client_id
    
    def get_client_context(self, client_id: uuid.UUID) -> Dict[str, Any]:
        """클라이언트 컨텍스트 반환"""
        return self.client_contexts.get(client_id, {})
    
    def release_client(self, client_id: uuid.UUID):
        """클라이언트 컨텍스트 해제"""
        if client_id in self.client_contexts:
            self.client_contexts.pop(client_id)
            print(f"Client context released for client {client_id}.")
    
    def get_client_status(self, client_id: uuid.UUID) -> Dict[str, Any]:
        """클라이언트 상태 반환"""
        client_context = self.get_client_context(client_id)
        return {
            'speechSynthesizerConnected': client_context.get('speech_synthesizer_connected', False)
        }
    
    def get_all_contexts(self) -> Dict[uuid.UUID, Dict[str, Any]]:
        """모든 클라이언트 컨텍스트 반환"""
        return self.client_contexts
