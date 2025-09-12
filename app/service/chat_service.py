import json
import logging
import os
import random
import re
import uuid
from openai import AzureOpenAI
from typing import Generator, Dict
from .architecture_diagram_service import ArchitectureDiagramService

azure_openai_endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT')
azure_openai_api_key = os.environ.get('AZURE_OPENAI_API_KEY')
azure_openai_deployment_name = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME')
cognitive_search_endpoint = os.environ.get('COGNITIVE_SEARCH_ENDPOINT')
cognitive_search_api_key = os.environ.get('COGNITIVE_SEARCH_API_KEY')
cognitive_search_index_name = os.environ.get('COGNITIVE_SEARCH_INDEX_NAME')

sentence_level_punctuations = ['.', '?', '!', ':', ';', '。', '？', '！', '：', '；']
enable_quick_reply = False
quick_replies = ['Let me take a look.', 'Let me check.', 'One moment, please.']
oyd_doc_regex = re.compile(r'\[doc(\d+)\]')

# Logger 설정
logger = logging.getLogger(__name__)

azure_openai = None
if azure_openai_endpoint and azure_openai_api_key:
    azure_openai = AzureOpenAI(
        azure_endpoint=azure_openai_endpoint,
        api_version='2024-06-01',
        api_key=azure_openai_api_key)


class ChatService:
    
    def __init__(self):
        self.client_contexts = {}
        self.architecture_service = ArchitectureDiagramService()
    
    def set_client_contexts(self, client_contexts: Dict):
        self.client_contexts = client_contexts
    
    def get_system_prompt(self):
        """시스템 프롬프트 반환 - LLM이 JSON 형태로 응답하도록 지시"""
        return """
당신은 Azure 아키텍처 전문가입니다. 사용자의 질문을 분석하여 적절한 응답과 액션을 결정해주세요.

응답 형식은 반드시 다음 JSON 형태여야 합니다:
{
  "response": "사용자에게 보여줄 응답 메시지",
  "action": "수행할 액션 (아래 중 하나 또는 빈 문자열)"
}

가능한 action 종류:
1. "generate_architecture_diagram" - 새로운 아키텍처 다이어그램을 생성해야 하는 경우
2. "modify_architecture_diagram" - 기존 아키텍처를 수정해야 하는 경우  
3. "generate_bicep_infrastructure" - Bicep 인프라 코드를 생성해야 하는 경우
4. "" (빈 문자열) - 일반적인 질문으로 특별한 액션이 필요 없는 경우

판단 기준:
- 아키텍처 생성/설계 관련 키워드: "아키텍처", "다이어그램", "설계", "구조" 등이 포함되고 새로 만들어달라는 요청
- 아키텍처 수정 관련 키워드: "수정", "변경", "업데이트", "추가", "제거" 등이 아키텍처와 함께 언급
- 인프라/배포 관련 키워드: "배포", "인프라", "Bicep", "bicep", "IaC" 등이 포함

예시:
사용자: "웹 애플리케이션을 위한 Azure 아키텍처를 만들어주세요"
응답: {"response": "웹 애플리케이션을 위한 Azure 아키텍처 다이어그램을 생성하겠습니다.", "action": "generate_architecture_diagram"}

사용자: "기존 아키텍처에 Redis 캐시를 추가해주세요"  
응답: {"response": "기존 아키텍처에 Redis 캐시를 추가하여 수정하겠습니다.", "action": "modify_architecture_diagram"}

사용자: "이 아키텍처를 배포할 Bicep 코드를 만들어주세요"
응답: {"response": "아키텍처를 바탕으로 Bicep 인프라 코드를 생성하겠습니다.", "action": "generate_bicep_infrastructure"}

사용자: "Azure가 뭐야?"
응답: {"response": "Azure는 Microsoft에서 제공하는 클라우드 컴퓨팅 플랫폼입니다...", "action": ""}

반드시 유효한 JSON 형태로만 응답해주세요.
"""
    
    def initialize_chat_context(self, system_prompt: str, client_id: uuid.UUID) -> None:
        client_context = self.client_contexts[client_id]
        messages = client_context['messages']
        data_sources = client_context['data_sources']

        data_sources.clear()
        if (cognitive_search_endpoint and cognitive_search_api_key):
            data_source = {
                'type': 'azure_search',
                'parameters': {
                    'endpoint': cognitive_search_endpoint,
                    'index_name': cognitive_search_index_name,
                    'authentication': {
                        'type': 'api_key',
                        'key': cognitive_search_api_key
                    },
                    'semantic_configuration': '',
                    'query_type': 'simple',
                    'fields_mapping': {
                        'content_fields_separator': '\n',
                        'content_fields': ['content'],
                        'filepath_field': None,
                        'title_field': 'title',
                        'url_field': None
                    },
                    'in_scope': True,
                    'role_information': self.get_system_prompt()
                }
            }
            data_sources.append(data_source)

        messages.clear()
        if len(data_sources) == 0:
            system_message = {
                'role': 'system',
                'content': self.get_system_prompt()
            }
            messages.append(system_message)

    def handle_user_query(self, user_query: str, client_id: uuid.UUID, 
                         speak_callback=None) -> Generator[str, None, None]:
        client_context = self.client_contexts[client_id]
        messages = client_context['messages']
        data_sources = client_context['data_sources']

        chat_message = {
            'role': 'user',
            'content': user_query
        }

        messages.append(chat_message)

        if len(data_sources) > 0 and enable_quick_reply and speak_callback:
            speak_callback(random.choice(quick_replies), 2000, client_id)
        
        # 현재 아키텍처 구조가 있는 경우 컨텍스트에 추가
        current_structure = client_context.get('current_structure', '')
        if current_structure:
            architecture_context = f"""

현재 아키텍처 구조가 있습니다: {current_structure}

사용자가 아키텍처 수정이나 Bicep 코드 생성을 요청하면 위 구조를 활용해주세요."""
            
            chat_message['content'] += architecture_context
            logger.info(f"Added current structure context for client {client_id}")
        
        # LLM에서 JSON 응답 받기
        response = azure_openai.chat.completions.create(
            model=azure_openai_deployment_name,
            messages=messages,
            extra_body={'data_sources': data_sources} if len(data_sources) > 0 else None
        )
        
        response_content = response.choices[0].message.content
        logger.info(f"LLM Response: {response_content}")
        
        try:
            # JSON 응답 파싱
            llm_response = json.loads(response_content)
            response_text = llm_response.get("response", "")
            action = llm_response.get("action", "")
            
            logger.info(f"Parsed response - action: {action}, response length: {len(response_text)}")
            
            # 응답 메시지를 스트리밍으로 출력
            yield response_text + "\n\n"
            
            if speak_callback:
                speak_callback(response_text, 0, client_id)
            
            # action에 따른 분기 처리
            if action == "generate_architecture_diagram":
                logger.info("Executing generate_architecture_diagram")
                yield "🔍 아키텍처 요구사항을 분석하고 있습니다...\n\n"
                yield f"📋 요구사항: {user_query}\n\n"
                yield "🎨 Azure 아키텍처 다이어그램을 생성 중입니다...\n\n"
                
                if speak_callback:
                    speak_callback("아키텍처 다이어그램을 생성하고 있습니다.", 0, client_id)
                
                result = self.architecture_service.generate_architecture_diagram(user_query)
                yield from self._handle_architecture_result(result, "generate", client_id, speak_callback)
                
            elif action == "modify_architecture_diagram":
                logger.info("Executing modify_architecture_diagram")
                yield "🔄 기존 아키텍처를 분석하고 있습니다...\n\n"
                yield f"📝 수정 요청: {user_query}\n\n"
                yield "🎨 아키텍처 다이어그램을 수정 중입니다...\n\n"
                
                if speak_callback:
                    speak_callback("아키텍처 다이어그램을 수정하고 있습니다.", 0, client_id)
                
                if current_structure:
                    result = self.architecture_service.modify_architecture_diagram(current_structure, user_query)
                    yield from self._handle_architecture_result(result, "modify", client_id, speak_callback)
                else:
                    error_msg = "수정할 기존 아키텍처가 없습니다. 먼저 아키텍처를 생성해주세요."
                    yield error_msg
                    if speak_callback:
                        speak_callback(error_msg, 0, client_id)
                        
            elif action == "generate_bicep_infrastructure":
                logger.info("Executing generate_bicep_infrastructure")
                yield "🔄 아키텍처 구조를 분석하고 있습니다...\n\n"
                yield "☁️ Azure Bicep 인프라 코드를 생성 중입니다...\n\n"
                yield "📝 배포 가이드를 작성하고 있습니다...\n\n"
                
                if speak_callback:
                    speak_callback("비셉 인프라 코드를 생성하고 있습니다.", 0, client_id)
                
                if current_structure:
                    result = self.architecture_service.generate_bicep_infrastructure(current_structure)
                    yield from self._handle_bicep_result(result, client_id, speak_callback)
                else:
                    error_msg = "Bicep 코드를 생성할 아키텍처가 없습니다. 먼저 아키텍처를 생성해주세요."
                    yield error_msg
                    if speak_callback:
                        speak_callback(error_msg, 0, client_id)
                        
            # action이 빈 문자열인 경우 일반적인 응답만 처리 (이미 위에서 응답 출력됨)
            
            # 대화 히스토리에 추가
            assistant_message = {
                'role': 'assistant',
                'content': response_text
            }
            messages.append(assistant_message)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response content: {response_content}")
            
            # JSON 파싱 실패 시 일반적인 스트리밍 응답으로 폴백
            yield "죄송합니다. 응답을 처리하는 중 오류가 발생했습니다. 다시 시도해주세요.\n\n"
            
            if speak_callback:
                speak_callback("응답을 처리하는 중 오류가 발생했습니다.", 0, client_id)
    
    def _handle_architecture_result(self, result: dict, operation_type: str, client_id: uuid.UUID, speak_callback=None) -> Generator[str, None, None]:
        """아키텍처 생성/수정 결과 처리"""
        client_context = self.client_contexts[client_id]
        
        if result.get('success'):
            diagram_path = result['diagram_path']
            description = result['description']
            structure = result['structure']
            
            logger.info(f"Architecture {operation_type} successful: {diagram_path}")
            
            # 클라이언트 컨텍스트에 현재 구조 저장
            client_context['current_structure'] = structure
            logger.info(f"Updated current_structure for client {client_id}")
            
            # 완료 메시지
            if operation_type == "generate":
                yield "✅ 다이어그램 생성이 완료되었습니다!\n\n"
                if speak_callback:
                    speak_callback("다이어그램 생성이 완료되었습니다.", 0, client_id)
            elif operation_type == "modify":
                yield "✅ 다이어그램 수정이 완료되었습니다!\n\n"
                if speak_callback:
                    speak_callback("다이어그램 수정이 완료되었습니다.", 0, client_id)
            
            # 다이어그램 경로와 구조를 클라이언트에게 전송
            yield f"<DIAGRAM>{diagram_path}</DIAGRAM>"
            yield f"<STRUCTURE>{structure}</STRUCTURE>"
            
            # 설명을 스트리밍으로 전송
            if description:
                spoken_sentence = ''
                for char in description:
                    yield char
                    if speak_callback and char in sentence_level_punctuations:
                        if spoken_sentence.strip():
                            speak_callback(spoken_sentence.strip(), 0, client_id)
                            spoken_sentence = ''
                    else:
                        spoken_sentence += char
                
                # 마지막 문장 처리
                if spoken_sentence.strip() and speak_callback:
                    speak_callback(spoken_sentence.strip(), 0, client_id)
        else:
            # 오류 발생 시
            error_message = f"다이어그램 {operation_type} 중 오류가 발생했습니다: {result.get('error', 'Unknown error')}"
            logger.error(f"Architecture {operation_type} error: {result.get('error', 'Unknown error')}")
            yield error_message
            
            if speak_callback:
                speak_callback("다이어그램 작업 중 오류가 발생했습니다.", 0, client_id)
    
    def _handle_bicep_result(self, result: dict, client_id: uuid.UUID, speak_callback=None) -> Generator[str, None, None]:
        """Bicep 코드 생성 결과 처리"""
        if result.get('success'):
            bicep_code = result.get('bicep_code', '')
            parameters_file = result.get('parameters_file', '')
            deployment_guide = result.get('deployment_guide', '')
            
            logger.info(f"Bicep code generated successfully: {len(bicep_code)} characters")
            
            # 완료 메시지
            yield "✅ Bicep 인프라 코드 생성이 완료되었습니다!\n\n"
            
            if speak_callback:
                speak_callback("비셉 인프라 코드 생성이 완료되었습니다.", 0, client_id)
            
            # Bicep 코드 출력
            if bicep_code:
                yield "## 📄 main.bicep\n\n"
                yield "```bicep\n"
                yield bicep_code
                yield "\n```\n\n"
            
            # 파라미터 파일 출력
            if parameters_file:
                yield "## ⚙️ main.bicepparam\n\n"
                yield "```bicepparam\n"
                yield parameters_file
                yield "\n```\n\n"
            
            # 배포 가이드 출력
            if deployment_guide:
                yield deployment_guide
                
        else:
            # 오류 발생 시
            error_message = f"Bicep 코드 생성 중 오류가 발생했습니다: {result.get('error', 'Unknown error')}"
            logger.error(f"Bicep generation error: {result.get('error', 'Unknown error')}")
            yield error_message
            
            if speak_callback:
                speak_callback("비셉 코드 생성 중 오류가 발생했습니다.", 0, client_id)


chat_service = ChatService()
