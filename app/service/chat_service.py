import datetime
import json
import logging
import os
import pytz
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
    
    def get_architecture_diagram_tools(self):
        """Function Calling을 위한 아키텍처 다이어그램 도구 정의"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "generate_architecture_diagram",
                    "description": "Azure 아키텍처 요구사항을 받아서 Architecture Diagram을 생성합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "requirements": {
                                "type": "string",
                                "description": "자연어로 작성된 아키텍처 요구사항"
                            }
                        },
                        "required": ["requirements"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "modify_architecture_diagram",
                    "description": "기존 Architecture Diagram을 수정합니다. 기존 구조를 바탕으로 변경 요청을 적용합니다.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "requirements": {
                                "type": "string",
                                "description": "아키텍처 수정 요청사항 (자연어)"
                            },
                            "previous_structure": {
                                "type": "string",
                                "description": "기존 아키텍처 구조의 JSON 문자열"
                            }
                        },
                        "required": ["requirements", "previous_structure"]
                    }
                }
            }
        ]
    
    def handle_function_call(self, function_name: str, arguments: dict):
        """Function Call 처리"""
        logger.info(f"Starting function call: {function_name}")
        logger.debug(f"Arguments received: {arguments}")
        
        if function_name == "generate_architecture_diagram":
            requirements = arguments.get("requirements", "")
            logger.info("Processing architecture diagram request")
            logger.debug(f"Requirements: {requirements}")
            
            try:
                result = self.architecture_service.generate_architecture_diagram(requirements)
                logger.info(f"Architecture service completed with success: {result.get('success', False)}")
                if result.get('success'):
                    logger.info(f"Generated diagram path: {result.get('diagram_path', 'N/A')}")
                else:
                    logger.error(f"Architecture service error: {result.get('error', 'Unknown error')}")
                return result
            except Exception as e:
                logger.exception(f"Exception occurred during architecture diagram generation: {str(e)}")
                return {"success": False, "error": f"Exception in architecture service: {str(e)}"}
        
        elif function_name == "modify_architecture_diagram":
            requirements = arguments.get("requirements", "")
            previous_structure = arguments.get("previous_structure", "")
            logger.info("Processing architecture diagram modification request")
            logger.debug(f"Modification request: {requirements}")
            logger.debug(f"Previous structure length: {len(previous_structure)} characters")
            
            try:
                result = self.architecture_service.modify_architecture_diagram(previous_structure, requirements)
                logger.info(f"Architecture modification completed with success: {result.get('success', False)}")
                if result.get('success'):
                    logger.info(f"Modified diagram path: {result.get('diagram_path', 'N/A')}")
                else:
                    logger.error(f"Architecture modification error: {result.get('error', 'Unknown error')}")
                return result
            except Exception as e:
                logger.exception(f"Exception occurred during architecture diagram modification: {str(e)}")
                return {"success": False, "error": f"Exception in architecture modification: {str(e)}"}
        else:
            logger.warning(f"Unknown function: {function_name}")
            return {"success": False, "error": f"Unknown function: {function_name}"}
    
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
                    'role_information': system_prompt
                }
            }
            data_sources.append(data_source)

        messages.clear()
        if len(data_sources) == 0:
            system_message = {
                'role': 'system',
                'content': system_prompt
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

        assistant_reply = ''
        tool_content = ''
        spoken_sentence = ''

        # Function Calling을 위한 tools 설정
        tools = self.get_architecture_diagram_tools()

        aoai_start_time = datetime.datetime.now(pytz.UTC)
        
        # 아키텍처 수정 요청인지 확인하고 현재 구조를 메시지에 추가
        current_structure = client_context.get('current_structure', '')
        if current_structure and self._is_architecture_modification_request(user_query):
            # 아키텍처 수정 요청인 경우 시스템 메시지에 현재 구조 정보 추가
            modification_context = f"""

현재 아키텍처 구조가 있습니다. 사용자가 아키텍처 수정을 요청하면, modify_architecture_diagram 함수를 호출할 때 반드시 previous_structure 파라미터에 아래 JSON 구조를 정확히 전달해주세요:

{current_structure}

사용자 요청을 바탕으로 이 구조를 수정하는 modify_architecture_diagram 함수를 호출해주세요."""
            
            chat_message['content'] += modification_context
            logger.info(f"Added current structure to modification request for client {client_id}")
        
        # 먼저 Function Calling이 필요한지 확인
        response = azure_openai.chat.completions.create(
            model=azure_openai_deployment_name,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            extra_body={'data_sources': data_sources} if len(data_sources) > 0 else None
        )
        
        response_message = response.choices[0].message
        
        # Function Call이 요청된 경우
        if response_message.tool_calls:
            logger.info(f"{len(response_message.tool_calls)} tool call(s) detected for client {client_id}")
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"Executing function: {function_name}")
                logger.debug(f"Function arguments: {function_args}")
                
                # 진행 상황 알림 메시지들
                if function_name == "generate_architecture_diagram":
                    requirements = function_args.get("requirements", "")
                    
                    logger.info("Architecture diagram generation started")
                    logger.debug(f"Requirements: {requirements}")
                    
                    # 단계별 진행 상황 메시지
                    yield "🔍 아키텍처 요구사항을 분석하고 있습니다...\n\n"
                    yield f"📋 요구사항: {requirements}\n\n"
                    yield "🎨 Azure 아키텍처 다이어그램을 생성 중입니다...\n\n"
                    
                    if speak_callback:
                        speak_callback("아키텍처 다이어그램을 생성하고 있습니다.", 0, client_id)
                
                elif function_name == "modify_architecture_diagram":
                    requirements = function_args.get("requirements", "")
                    previous_structure = function_args.get("previous_structure", "")
                    
                    logger.info("Architecture diagram modification started")
                    logger.debug(f"Modification request: {requirements}")
                    
                    # 단계별 진행 상황 메시지
                    yield "🔄 기존 아키텍처를 분석하고 있습니다...\n\n"
                    yield f"📝 수정 요청: {requirements}\n\n"
                    yield "🎨 아키텍처 다이어그램을 수정 중입니다...\n\n"
                    
                    if speak_callback:
                        speak_callback("아키텍처 다이어그램을 수정하고 있습니다.", 0, client_id)
                
                # 아키텍처 다이어그램 생성 함수 호출
                logger.debug(f"Calling function handler for {function_name}")
                result = self.handle_function_call(function_name, function_args)
                logger.debug(f"Function result: {result}")
                
                if result['success']:
                    # 다이어그램이 성공적으로 생성된 경우
                    diagram_path = result['diagram_path']
                    description = result['description']
                    structure = result['structure']
                    
                    logger.info(f"Diagram processed successfully: {diagram_path}")
                    logger.debug(f"Description length: {len(description) if description else 0} characters")
                    
                    # 완료 메시지
                    if function_name == "generate_architecture_diagram":
                        yield "✅ 다이어그램 생성이 완료되었습니다!\n\n"
                        if speak_callback:
                            speak_callback("다이어그램 생성이 완료되었습니다.", 0, client_id)
                    elif function_name == "modify_architecture_diagram":
                        yield "✅ 다이어그램 수정이 완료되었습니다!\n\n"
                        if speak_callback:
                            speak_callback("다이어그램 수정이 완료되었습니다.", 0, client_id)
                    
                    # 다이어그램 경로와 설명을 클라이언트에게 전송
                    yield f"<DIAGRAM>{diagram_path}</DIAGRAM>"

                     # 다이어그램 스트럭쳐를 클라이언트에게 전송
                    yield f"<STRUCTURE>{structure}</STRUCTURE>"
                    
                    # 설명을 스트리밍으로 전송
                    if description:
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
                    
                    assistant_reply = description
                else:
                    # 오류 발생 시
                    if function_name == "generate_architecture_diagram":
                        error_message = f"다이어그램 생성 중 오류가 발생했습니다: {result.get('error', 'Unknown error')}"
                    elif function_name == "modify_architecture_diagram":
                        error_message = f"다이어그램 수정 중 오류가 발생했습니다: {result.get('error', 'Unknown error')}"
                    else:
                        error_message = f"작업 중 오류가 발생했습니다: {result.get('error', 'Unknown error')}"
                    
                    logger.error(f"Function call error: {result.get('error', 'Unknown error')}")
                    yield error_message
                    assistant_reply = error_message
            
            logger.info(f"All function calls completed for client {client_id}")
        else:
            # 일반적인 스트리밍 응답 처리
            stream_response = azure_openai.chat.completions.create(
                model=azure_openai_deployment_name,
                messages=messages,
                extra_body={'data_sources': data_sources} if len(data_sources) > 0 else None,
                stream=True
            )

            is_first_chunk = True
            is_first_sentence = True
            for chunk in stream_response:
                if len(chunk.choices) > 0:
                    response_token = chunk.choices[0].delta.content
                    if response_token is not None:
                        if is_first_chunk:
                            first_token_latency_ms = round(
                                (datetime.datetime.now(pytz.UTC) - aoai_start_time).total_seconds() * 1000)
                            logger.info(f"AOAI first token latency: {first_token_latency_ms}ms")
                            yield f"<FTL>{first_token_latency_ms}</FTL>"
                            is_first_chunk = False
                        if oyd_doc_regex.search(response_token):
                            response_token = oyd_doc_regex.sub('', response_token).strip()
                        yield response_token
                        assistant_reply += response_token
                        if response_token == '\n' or response_token == '\n\n':
                            if is_first_sentence:
                                first_sentence_latency_ms = round(
                                    (datetime.datetime.now(pytz.UTC) - aoai_start_time).total_seconds() * 1000)
                                logger.info(f"AOAI first sentence latency: {first_sentence_latency_ms}ms")
                                yield f"<FSL>{first_sentence_latency_ms}</FSL>"
                                is_first_sentence = False
                            if speak_callback:
                                speak_callback(spoken_sentence.strip(), 0, client_id)
                            spoken_sentence = ''
                        else:
                            response_token = response_token.replace('\n', '')
                            spoken_sentence += response_token
                            if len(response_token) == 1 or len(response_token) == 2:
                                for punctuation in sentence_level_punctuations:
                                    if response_token.startswith(punctuation):
                                        if is_first_sentence:
                                            first_sentence_latency_ms = round(
                                                (datetime.datetime.now(pytz.UTC) - aoai_start_time).total_seconds() * 1000)
                                            logger.info(f"AOAI first sentence latency: {first_sentence_latency_ms}ms")
                                            yield f"<FSL>{first_sentence_latency_ms}</FSL>"
                                            is_first_sentence = False
                                        if speak_callback:
                                            speak_callback(spoken_sentence.strip(), 0, client_id)
                                        spoken_sentence = ''
                                        break

            if spoken_sentence != '' and speak_callback:
                speak_callback(spoken_sentence.strip(), 0, client_id)
                spoken_sentence = ''

        if len(data_sources) > 0:
            tool_message = {
                'role': 'tool',
                'content': tool_content
            }
            messages.append(tool_message)

        assistant_message = {
            'role': 'assistant',
            'content': assistant_reply
        }
        messages.append(assistant_message)

    def _is_architecture_modification_request(self, user_query: str) -> bool:
        """사용자 쿼리가 아키텍처 수정 요청인지 확인합니다."""
        modification_keywords = [
            '수정', '변경', '업데이트', '개선', '추가', '제거', '삭제', 
            'modify', 'change', 'update', 'improve', 'add', 'remove', 'delete',
            '바꿔', '고쳐', '수정해', '변경해', '업데이트해', '개선해', '추가해', '제거해', '삭제해'
        ]
        architecture_keywords = [
            '아키텍처', '구조', '다이어그램', '설계', 
            'architecture', 'diagram', 'structure', 'design'
        ]
        
        query_lower = user_query.lower()
        has_modification = any(keyword in query_lower for keyword in modification_keywords)
        has_architecture = any(keyword in query_lower for keyword in architecture_keywords)
        
        return has_modification and has_architecture


chat_service = ChatService()
