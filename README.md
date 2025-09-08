# Azure Avatar Chatbot

Microsoft Azure TTS (Text-to-Speech) 기반의 대화형 아바타 챗봇 애플리케이션입니다. 사용자는 음성으로 아바타와 대화할 수 있으며, Azure OpenAI와 Cognitive Services를 활용한 지능형 응답을 받을 수 있습니다.

## 📋 주요 기능

- **음성 인식 (STT)**: Azure Speech Services를 통한 실시간 음성 텍스트 변환
- **텍스트 음성 변환 (TTS)**: Azure TTS를 활용한 자연스러운 음성 출력
- **대화형 아바타**: 웹브라우저에서 실시간으로 동작하는 3D 아바타
- **AI 챗봇**: Azure OpenAI GPT 모델을 통한 지능형 대화
- **음성 활동 감지 (VAD)**: 자동 음성 감지 및 처리
- **실시간 통신**: WebSocket을 통한 실시간 양방향 통신
- **한국어 지원**: 한국어 음성 인식 및 TTS 기본 지원

## 🏗️ 시스템 아키텍처

```
Frontend (HTML/JS)
    ↓ WebSocket
Flask-SocketIO Server
    ↓
┌─────────────────┬─────────────────┬─────────────────┐
│  Avatar Service │   Chat Service  │   STT Service   │
│  (Azure TTS)    │  (Azure OpenAI) │ (Azure Speech)  │
└─────────────────┴─────────────────┴─────────────────┘
```

## 🛠️ 기술 스택

### Backend
- **Python 3.12**: 백엔드 런타임
- **Flask**: 웹 프레임워크
- **Flask-SocketIO**: 실시간 WebSocket 통신
- **Azure Cognitive Services Speech**: 음성 인식/합성
- **Azure OpenAI**: GPT 기반 챗봇
- **PyTorch**: 머신러닝 (VAD)

### Frontend
- **HTML5/CSS3/JavaScript**: 웹 인터페이스
- **Socket.IO**: 실시간 클라이언트 통신
- **Azure Speech SDK**: 브라우저 음성 처리

### Infrastructure
- **Docker**: 컨테이너화
- **Azure Cloud Services**: 클라우드 인프라

## 🚀 빠른 시작

### 1. 필수 조건

- Python 3.12+
- Azure 구독 및 다음 서비스:
  - Azure Speech Services
  - Azure OpenAI
  - Azure Cognitive Search (선택사항)

### 2. 환경 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 환경 변수를 설정합니다:

```env
# Azure Speech Services
SPEECH_REGION=your-speech-region
SPEECH_KEY=your-speech-key

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-openai-instance.openai.azure.com/
AZURE_OPENAI_API_KEY=your-openai-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name

# Azure Cognitive Search (선택사항)
COGNITIVE_SEARCH_ENDPOINT=https://your-search-service.search.windows.net
COGNITIVE_SEARCH_API_KEY=your-search-api-key
COGNITIVE_SEARCH_INDEX_NAME=your-index-name

# 애플리케이션 설정
DEFAULT_TTS_VOICE=ko-KR-SunHiNeural
ENABLE_VAD=true
ENABLE_TOKEN_AUTH_FOR_SPEECH=false
```

### 3. 설치 및 실행

#### UV 패키지 매니저 사용 (권장)

```bash
# 의존성 설치
uv sync

# 애플리케이션 실행
cd app
uv run python app.py
```

### 5. 접속

웹브라우저에서 `http://localhost:5001`으로 접속합니다.

## 📁 프로젝트 구조

```
avatar-web/
├── app/
│   ├── app.py                      # 메인 애플리케이션
│   ├── Dockerfile                  # Docker 설정
│   ├── service/                    # 비즈니스 로직
│   │   ├── avatar_service.py       # 아바타 및 TTS 서비스
│   │   ├── chat_service.py         # OpenAI 챗봇 서비스
│   │   ├── stt_service.py          # 음성 인식 서비스
│   │   ├── client_manager.py       # 클라이언트 관리
│   │   ├── config_service.py       # 설정 관리
│   │   └── websocket_handler.py    # WebSocket 핸들러
│   ├── static/                     # 정적 파일
│   │   ├── chat.html               # 메인 UI
│   │   ├── css/styles.css          # 스타일시트
│   │   ├── js/chat.js              # 클라이언트 JavaScript
│   │   └── image/                  # 이미지 리소스
│   └── util/
│       └── vad_iterator.py         # 음성 활동 감지
├── pyproject.toml                  # 프로젝트 설정
├── uv.lock                         # 의존성 락 파일
└── README.md                       # 프로젝트 문서
```

## 🎮 사용법

1. **세션 시작**: "Start Session" 버튼을 클릭하여 아바타 세션을 시작합니다.
2. **음성 대화**: "Microphone" 버튼을 클릭하여 음성으로 대화를 시작합니다.
3. **텍스트 입력**: 채팅 입력창에 직접 텍스트를 입력할 수도 있습니다.
4. **아바타 응답**: AI가 응답을 생성하고 아바타가 음성으로 답변합니다.

## ⚙️ 설정 옵션

### 음성 설정
- **STT 언어**: 음성 인식 언어 (기본: ko-KR)
- **TTS 음성**: 텍스트 음성 변환 음성 (기본: ko-KR-SunHiNeural)
- **연속 대화**: 자동 음성 감지 활성화

### 아바타 설정
- **아바타 캐릭터**: 사용할 아바타 캐릭터 선택
- **아바타 스타일**: 아바타 스타일 및 포즈 설정
- **자동 재연결**: 연결 끊김 시 자동 재연결

### AI 설정
- **시스템 프롬프트**: AI 어시스턴트 성격 및 역할 정의
- **Azure OpenAI 모델**: 사용할 GPT 모델 선택
- **검색 기능**: Azure Cognitive Search 연동 (On Your Data)

## 🔧 개발

### 로컬 개발 환경

```bash
# 개발 의존성 설치
uv sync --dev

# 코드 포맷팅
black app/

# 린팅
flake8 app/

# 타입 체크
mypy app/
```

### API 엔드포인트

- `GET /`: 메인 챗봇 인터페이스
- `POST /chat`: 텍스트 기반 채팅 API
- `WebSocket /socket.io`: 실시간 통신

### WebSocket 이벤트

- `message`: 채팅 메시지 전송
- `speech_data`: 음성 데이터 전송
- `avatar_response`: 아바타 응답 수신
- `status_update`: 상태 업데이트

## 🐛 문제 해결

### 일반적인 문제

1. **음성이 들리지 않음**
   - 브라우저 마이크 권한 확인
   - Azure Speech 서비스 키 및 지역 확인

2. **아바타가 표시되지 않음**
   - 네트워크 연결 상태 확인
   - WebRTC 지원 브라우저 사용

3. **AI 응답이 없음**
   - Azure OpenAI 서비스 상태 확인
   - API 키 및 배포 이름 확인

### 로그 확인

```bash
# 애플리케이션 로그 확인
tail -f app.log

# Docker 로그 확인
docker logs avatar-chatbot
```