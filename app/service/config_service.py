import os
from dotenv import load_dotenv


class ConfigService:
    def __init__(self):
        load_dotenv(override=True)
        
        # Azure Speech Services
        self.speech_region = os.environ.get('SPEECH_REGION')
        self.speech_key = os.environ.get('SPEECH_KEY')
        
        # Azure OpenAI
        self.azure_openai_endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT')
        self.azure_openai_api_key = os.environ.get('AZURE_OPENAI_API_KEY')
        self.azure_openai_deployment_name = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME')
        
        # Azure Cognitive Search
        self.cognitive_search_endpoint = os.environ.get('COGNITIVE_SEARCH_ENDPOINT')
        self.cognitive_search_api_key = os.environ.get('COGNITIVE_SEARCH_API_KEY')
        self.cognitive_search_index_name = os.environ.get('COGNITIVE_SEARCH_INDEX_NAME')
        
        # ICE Server
        self.ice_server_url = os.environ.get('ICE_SERVER_URL')
        self.ice_server_url_remote = os.environ.get('ICE_SERVER_URL_REMOTE')
        self.ice_server_username = os.environ.get('ICE_SERVER_USERNAME')
        self.ice_server_password = os.environ.get('ICE_SERVER_PASSWORD')
        
        # Application Settings
        self.enable_websockets = True
        self.enable_vad = False
        self.enable_token_auth_for_speech = False
        self.default_tts_voice = 'en-US-JennyMultilingualV2Neural'
        self.repeat_speaking_sentence_after_reconnection = True
        
        # Validate required settings
        self._validate_config()
    
    def _validate_config(self):
        """설정 유효성 검사"""
        required_settings = [
            ('SPEECH_REGION', self.speech_region),
            ('SPEECH_KEY', self.speech_key),
            ('AZURE_OPENAI_ENDPOINT', self.azure_openai_endpoint),
            ('AZURE_OPENAI_API_KEY', self.azure_openai_api_key),
            ('AZURE_OPENAI_DEPLOYMENT_NAME', self.azure_openai_deployment_name)
        ]
        
        missing_settings = []
        for name, value in required_settings:
            if not value:
                missing_settings.append(name)
        
        if missing_settings:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_settings)}")
    
    def get_speech_config(self) -> dict:
        """Speech 관련 설정 반환"""
        return {
            'region': self.speech_region,
            'key': self.speech_key,
            'enable_token_auth': self.enable_token_auth_for_speech,
            'default_voice': self.default_tts_voice
        }
    
    def get_ice_config(self) -> dict:
        """ICE 서버 설정 반환"""
        return {
            'url': self.ice_server_url,
            'url_remote': self.ice_server_url_remote,
            'username': self.ice_server_username,
            'password': self.ice_server_password
        }
    
    def get_openai_config(self) -> dict:
        """OpenAI 설정 반환"""
        return {
            'endpoint': self.azure_openai_endpoint,
            'api_key': self.azure_openai_api_key,
            'deployment_name': self.azure_openai_deployment_name
        }
    
    def get_search_config(self) -> dict:
        """Cognitive Search 설정 반환"""
        return {
            'endpoint': self.cognitive_search_endpoint,
            'api_key': self.cognitive_search_api_key,
            'index_name': self.cognitive_search_index_name
        }
    
    def get_app_config(self) -> dict:
        """애플리케이션 설정 반환"""
        return {
            'enable_websockets': self.enable_websockets,
            'enable_vad': self.enable_vad,
            'repeat_speaking_after_reconnection': self.repeat_speaking_sentence_after_reconnection
        }
