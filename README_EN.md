# Azure Avatar Chatbot

This project is a conversational avatar chatbot application based on **Microsoft Azure TTS (Text-to-Speech)**. Users can talk to an avatar using voice, and the system provides intelligent responses powered by **Azure OpenAI** and **Azure Cognitive Services**.

## 📋 Main Features

- **Speech Recognition (STT)**: Real-time speech-to-text using Azure Speech Services
- **Text-to-Speech (TTS)**: Natural speech generation using Azure TTS
- **Interactive Avatar**: Real-time 3D avatar operating in the web browser
- **AI Chatbot**: Intelligent responses with Azure OpenAI GPT models
- **Voice Activity Detection (VAD)**: Automatically detects and handles speech
- **Real-time Communication**: Two-way communication via WebSocket
- **Korean Language Support**: Built-in support for Korean speech recognition and TTS

## 🏗️ System Architecture

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

## 🛠️ Tech Stack

### Backend
- **Python 3.12**: Backend runtime
- **Flask**: Web framework
- **Flask-SocketIO**: Real-time WebSocket communication
- **Azure Cognitive Services Speech**: Speech recognition and synthesis
- **Azure OpenAI**: GPT-powered chatbot
- **PyTorch**: Machine learning for VAD

### Frontend
- **HTML5/CSS3/JavaScript**: Web interface
- **Socket.IO**: Real-time client communication
- **Azure Speech SDK**: Speech processing in the browser

### Infrastructure
- **Docker**: Containerization
- **Azure Cloud Services**: Cloud infrastructure

## 🚀 Quick Start

### 1. Requirements

- Python 3.12+
- Azure subscription with the following services:
  - Azure Speech Services
  - Azure OpenAI
  - Azure Cognitive Search (optional)

### 2. Environment Setup

Create an `.env` file in the project root and set the following variables:

```env
# Azure Speech Services
SPEECH_REGION=your-speech-region
SPEECH_KEY=your-speech-key

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_API_KEY=your-openai-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name

# Azure Cognitive Search (optional)
COGNITIVE_SEARCH_ENDPOINT=https://your-search-service.search.windows.net
COGNITIVE_SEARCH_API_KEY=your-search-api-key
COGNITIVE_SEARCH_INDEX_NAME=your-index-name

# Application Settings
DEFAULT_TTS_VOICE=ko-KR-SunHiNeural
ENABLE_VAD=true
ENABLE_TOKEN_AUTH_FOR_SPEECH=false
```

### 3. Installation and Run

#### Using UV Package Manager (Recommended)

```bash
# Install dependencies
uv sync

# Run the application
cd app
uv run python app.py
```

### 5. Access

Open your browser and go to `http://localhost:5001`

## 📁 Project Structure

```
avatar-web/
├── app/
│   ├── app.py                      # Main application
│   ├── Dockerfile                  # Docker configuration
│   ├── service/                    # Business logic
│   │   ├── avatar_service.py       # Avatar and TTS service
│   │   ├── chat_service.py         # OpenAI chatbot service
│   │   ├── stt_service.py          # Speech recognition service
│   │   ├── client_manager.py       # Client management
│   │   ├── config_service.py       # Configuration management
│   │   └── websocket_handler.py    # WebSocket handler
│   ├── static/                     # Static files
│   │   ├── chat.html               # Main UI
│   │   ├── css/styles.css          # Stylesheet
│   │   ├── js/chat.js              # Client JavaScript
│   │   └── image/                  # Image resources
│   └── util/
│       └── vad_iterator.py         # Voice activity detection
├── pyproject.toml                  # Project configuration
├── uv.lock                         # Dependency lock file
└── README.md                       # Korean documentation
```

## 🎮 Usage

1. **Start Session**: Click the "Start Session" button to begin the avatar chat.
2. **Voice Chat**: Click the "Microphone" button to start talking.
3. **Text Chat**: You can also type messages manually in the chat input.
4. **Avatar Response**: The AI generates a response and the avatar speaks it aloud.

## ⚙️ Configuration Options

### Speech Settings
- **STT Language**: Speech recognition language (default: `ko-KR`)
- **TTS Voice**: Voice used for text-to-speech (default: `ko-KR-SunHiNeural`)
- **Continuous Conversation**: Enable automatic voice detection

### Avatar Settings
- **Avatar Character**: Select avatar character
- **Avatar Style**: Configure avatar style and pose
- **Auto Reconnect**: Automatically reconnect on disconnects

### AI Settings
- **System Prompt**: Define AI assistant personality and role
- **Azure OpenAI Model**: Choose GPT model to use
- **Search Integration**: Integrate with Azure Cognitive Search (On Your Data)

## 🔧 Development

### Local Development Environment

```bash
# Install development dependencies
uv sync --dev

# Code formatting
black app/

# Linting
flake8 app/

# Type checking
mypy app/
```

### API Endpoints

- `GET /`: Main chatbot interface
- `POST /chat`: Text-based chat API
- `WebSocket /socket.io`: Real-time communication

### WebSocket Events

- `message`: Send chat messages
- `speech_data`: Send speech data
- `avatar_response`: Receive avatar responses
- `status_update`: Receive system status updates

## 🐛 Troubleshooting

### Common Issues

1. **No audio output**
   - Check browser microphone permissions
   - Verify Azure Speech Service credentials

2. **Avatar not displayed**
   - Check network connection
   - Use a browser that supports WebRTC

3. **No AI response**
   - Verify Azure OpenAI status
   - Check API key and deployment name

### Check Logs

```bash
# Application logs
tail -f app.log

# Docker logs
docker logs avatar-chatbot
```