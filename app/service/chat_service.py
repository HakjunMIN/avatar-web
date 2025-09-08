import datetime
import os
import pytz
import random
import re
import uuid
from openai import AzureOpenAI
from typing import Generator, Dict

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

azure_openai = None
if azure_openai_endpoint and azure_openai_api_key:
    azure_openai = AzureOpenAI(
        azure_endpoint=azure_openai_endpoint,
        api_version='2024-06-01',
        api_key=azure_openai_api_key)


class ChatService:
    
    def __init__(self):
        self.client_contexts = {}
    
    def set_client_contexts(self, client_contexts: Dict):
        self.client_contexts = client_contexts
    
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

        aoai_start_time = datetime.datetime.now(pytz.UTC)
        response = azure_openai.chat.completions.create(
            model=azure_openai_deployment_name,
            messages=messages,
            extra_body={'data_sources': data_sources} if len(data_sources) > 0 else None,
            stream=True)

        is_first_chunk = True
        is_first_sentence = True
        for chunk in response:
            if len(chunk.choices) > 0:
                response_token = chunk.choices[0].delta.content
                if response_token is not None:
                    if is_first_chunk:
                        first_token_latency_ms = round(
                            (datetime.datetime.now(pytz.UTC) - aoai_start_time).total_seconds() * 1000)
                        print(f"AOAI first token latency: {first_token_latency_ms}ms")
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
                            print(f"AOAI first sentence latency: {first_sentence_latency_ms}ms")
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
                                        print(f"AOAI first sentence latency: {first_sentence_latency_ms}ms")
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


chat_service = ChatService()
