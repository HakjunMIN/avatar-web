// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license.

// Global objects
var clientId
var enableWebSockets
var socket
var audioContext
var isFirstResponseChunk
var speechRecognizer
var iceServerUrl
var iceServerUsername
var iceServerCredential
var peerConnectionQueue = []
var peerConnectionDataChannel
var speechSynthesizerConnected = false
var isSpeaking = false
var isReconnecting = false
var sessionActive = false
var userClosedSession = false
var recognitionStartedTime
var chatRequestSentTime
var chatResponseReceivedTime
var lastInteractionTime = new Date()
var lastSpeakTime
var isFirstRecognizingEvent = true
var sttLatencyRegex = new RegExp(/<STTL>(\d+)<\/STTL>/)
var firstTokenLatencyRegex = new RegExp(/<FTL>(\d+)<\/FTL>/)
var firstSentenceLatencyRegex = new RegExp(/<FSL>(\d+)<\/FSL>/)
var diagramRegex = new RegExp(/<DIAGRAM>(.*?)<\/DIAGRAM>/)
// Timestamp (ms) of last typed submission to suppress duplicate STT handling
var lastTypeSubmitTime = 0
// Global buffer for streaming chunks
var streamBuffer = ''
// Current assistant message element for streaming updates
var currentAssistantMessage = null
// WebSocket response completion timer
var wsResponseTimer = null
// Complete response text for markdown parsing
var completeWsResponse = ''

// Chat utility functions
function createChatMessage(sender, content = '', isMarkdown = false) {
    const messageDiv = document.createElement('div')
    messageDiv.className = `chat-message ${sender}`
    
    const messageHeader = document.createElement('div')
    messageHeader.className = 'message-header'
    
    const avatar = document.createElement('div')
    avatar.className = `avatar ${sender}`
    avatar.textContent = sender === 'user' ? 'U' : 'A'
    
    const senderLabel = document.createElement('span')
    senderLabel.textContent = sender === 'user' ? 'You' : 'Assistant'
    
    const timestamp = document.createElement('span')
    timestamp.className = 'message-timestamp'
    timestamp.textContent = new Date().toLocaleTimeString()
    
    messageHeader.appendChild(avatar)
    messageHeader.appendChild(senderLabel)
    messageHeader.appendChild(timestamp)
    
    const messageContent = document.createElement('div')
    messageContent.className = 'message-content'
    
    if (content) {
        if (isMarkdown && sender === 'assistant') {
            messageContent.innerHTML = marked.parse(content)
            // Apply syntax highlighting if Prism is available
            if (typeof Prism !== 'undefined') {
                Prism.highlightAllUnder(messageContent)
            }
        } else {
            messageContent.textContent = content
        }
    }
    
    messageDiv.appendChild(messageHeader)
    messageDiv.appendChild(messageContent)
    
    return messageDiv
}

function addUserMessage(content) {
    const chatHistory = document.getElementById('chatHistory')
    const userMessage = createChatMessage('user', content, false)
    chatHistory.appendChild(userMessage)
    chatHistory.scrollTop = chatHistory.scrollHeight
}

function addAssistantMessage(content = '', isComplete = false) {
    const chatHistory = document.getElementById('chatHistory')
    
    if (!currentAssistantMessage) {
        currentAssistantMessage = createChatMessage('assistant', '', false)
        chatHistory.appendChild(currentAssistantMessage)
    }
    
    const messageContent = currentAssistantMessage.querySelector('.message-content')
    
    if (content) {
        if (isComplete) {
            // Parse as markdown when message is complete
            messageContent.innerHTML = marked.parse(content)
            if (typeof Prism !== 'undefined') {
                Prism.highlightAllUnder(messageContent)
            }
        } else {
            // For streaming, just append text
            messageContent.textContent += content
        }
    }
    
    chatHistory.scrollTop = chatHistory.scrollHeight
    
    if (isComplete) {
        currentAssistantMessage = null
    }
}

function showTypingIndicator() {
    const chatHistory = document.getElementById('chatHistory')
    
    // Remove existing typing indicator
    const existingIndicator = chatHistory.querySelector('.typing-indicator')
    if (existingIndicator) {
        existingIndicator.remove()
    }
    
    const typingDiv = document.createElement('div')
    typingDiv.className = 'typing-indicator'
    typingDiv.innerHTML = `
        <span>Assistant is typing</span>
        <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `
    
    chatHistory.appendChild(typingDiv)
    chatHistory.scrollTop = chatHistory.scrollHeight
}

function hideTypingIndicator() {
    const chatHistory = document.getElementById('chatHistory')
    const typingIndicator = chatHistory.querySelector('.typing-indicator')
    if (typingIndicator) {
        typingIndicator.remove()
    }
}

// Configure marked for better rendering
if (typeof marked !== 'undefined') {
    marked.setOptions({
        breaks: true,
        gfm: true,
        sanitize: false,
        smartLists: true,
        smartypants: true
    })
}

// Function to process buffered content and extract complete tags
function processStreamBuffer(newChunk) {
    streamBuffer += newChunk
    let processedText = ''
    let remainingBuffer = streamBuffer
    
    // Process complete diagram tags
    let diagramMatch
    while ((diagramMatch = diagramRegex.exec(remainingBuffer)) !== null) {
        // Extract text before the diagram
        let beforeDiagram = remainingBuffer.substring(0, diagramMatch.index)
        processedText += beforeDiagram
        
        // Process the diagram
        let diagramPath = diagramMatch[1]
        console.log(`Architecture diagram received: ${diagramPath}`)
        displayArchitectureDiagram(diagramPath)
        
        // Update remaining buffer (text after the diagram tag)
        // 다이어그램 태그는 텍스트에서 완전히 제거
        remainingBuffer = remainingBuffer.substring(diagramMatch.index + diagramMatch[0].length)
        // Reset regex lastIndex for next iteration
        diagramRegex.lastIndex = 0
    }
    
    // Check if there might be an incomplete tag at the end
    let incompleteTagStart = remainingBuffer.lastIndexOf('<')
    if (incompleteTagStart !== -1) {
        let potentialTag = remainingBuffer.substring(incompleteTagStart)
        if (potentialTag.includes('DIAGRAM') || potentialTag.includes('FTL') || potentialTag.includes('FSL') || potentialTag.includes('STTL')) {
            // Keep potential incomplete tag in buffer
            processedText += remainingBuffer.substring(0, incompleteTagStart)
            streamBuffer = remainingBuffer.substring(incompleteTagStart)
        } else {
            // Not a tag we care about, process everything
            processedText += remainingBuffer
            streamBuffer = ''
        }
    } else {
        // No potential incomplete tag, process everything
        processedText += remainingBuffer
        streamBuffer = ''
    }
    
    return processedText
}

// Function to clear stream buffer (call when response is complete)
function clearStreamBuffer() {
    let finalText = streamBuffer
    streamBuffer = ''
    return finalText
}

// Function to display architecture diagram
function displayArchitectureDiagram(diagramPath) {
    console.log(`[displayArchitectureDiagram] Starting to display diagram: ${diagramPath}`)
    let chatHistoryDiv = document.getElementById('chatHistory')
    
    if (!chatHistoryDiv) {
        console.error('[displayArchitectureDiagram] chatHistory div not found!')
        return
    }
    
    // 이미 같은 다이어그램이 표시되어 있는지 확인
    const existingDiagrams = chatHistoryDiv.querySelectorAll('.diagram-message img')
    for (let img of existingDiagrams) {
        if (img.src.includes(encodeURIComponent(diagramPath))) {
            console.log('[displayArchitectureDiagram] Diagram already exists, skipping duplicate')
            return
        }
    }
    
    // Ensure chat history is visible
    if (chatHistoryDiv) {
        chatHistoryDiv.hidden = false
        chatHistoryDiv.style.display = 'flex'
        console.log('[displayArchitectureDiagram] chatHistory div made visible')
    }
    
    // Create a special message container for the diagram
    const diagramMessage = document.createElement('div')
    diagramMessage.className = 'chat-message assistant diagram-message'
    
    const messageHeader = document.createElement('div')
    messageHeader.className = 'message-header'
    
    const avatar = document.createElement('div')
    avatar.className = 'avatar assistant'
    avatar.textContent = 'A'
    
    const senderLabel = document.createElement('span')
    senderLabel.textContent = 'Assistant'
    
    const timestamp = document.createElement('span')
    timestamp.className = 'message-timestamp'
    timestamp.textContent = new Date().toLocaleTimeString()
    
    messageHeader.appendChild(avatar)
    messageHeader.appendChild(senderLabel)
    messageHeader.appendChild(timestamp)
    
    // Create message content with diagram
    const messageContent = document.createElement('div')
    messageContent.className = 'message-content'
    messageContent.style.maxWidth = '100%'
    messageContent.style.width = '100%'
    messageContent.style.padding = '1rem'
    
    // Create diagram container
    let diagramContainer = document.createElement('div')
    diagramContainer.className = 'diagram-container'
    diagramContainer.style.margin = '0'
    diagramContainer.style.width = '100%'
    diagramContainer.style.maxHeight = '600px'
    diagramContainer.style.overflowY = 'auto'
    diagramContainer.style.overflowX = 'auto'
    diagramContainer.style.textAlign = 'center'
    diagramContainer.style.border = '1px solid var(--border-color)'
    diagramContainer.style.borderRadius = 'var(--border-radius-sm)'
    diagramContainer.style.padding = '0.5rem'
    
    // Create diagram title
    let diagramTitle = document.createElement('h3')
    diagramTitle.innerHTML = '🔧 Azure Architecture Diagram'
    diagramTitle.style.margin = '0 0 1rem 0'
    diagramTitle.style.color = 'var(--primary-color)'
    diagramTitle.style.fontSize = '1.1rem'
    diagramTitle.style.fontWeight = '600'
    
    // Create image element
    let diagramImg = document.createElement('img')
    diagramImg.src = `/api/diagram/${encodeURIComponent(diagramPath)}`
    diagramImg.alt = 'Azure Architecture Diagram'
    diagramImg.style.width = '100%'
    diagramImg.style.maxWidth = '100%'
    diagramImg.style.height = 'auto'
    diagramImg.style.display = 'block'
    diagramImg.style.margin = '0 auto'
    diagramImg.style.border = '1px solid var(--border-color)'
    diagramImg.style.borderRadius = 'var(--border-radius-sm)'
    diagramImg.style.objectFit = 'contain'
    diagramImg.style.backgroundColor = '#ffffff'
    diagramImg.style.cursor = 'zoom-in'
    
    // Add loading message
    let loadingMsg = document.createElement('p')
    loadingMsg.textContent = '다이어그램 로딩 중...'
    loadingMsg.className = 'diagram-loading'
    loadingMsg.style.textAlign = 'center'
    loadingMsg.style.color = 'var(--text-secondary)'
    loadingMsg.style.margin = '1rem 0'
    diagramContainer.appendChild(loadingMsg)
    
    // Add error handling for image loading
    diagramImg.onerror = function() {
        this.style.display = 'none'
        loadingMsg.textContent = '❌ 다이어그램을 로드할 수 없습니다.'
        loadingMsg.className = 'diagram-error'
        loadingMsg.style.color = 'var(--danger-color)'
    }
    
    // Add success handling for image loading
    diagramImg.onload = function() {
        if (loadingMsg.parentNode) {
            loadingMsg.remove()
        }
    }
    
    // Add click to zoom functionality
    diagramImg.onclick = function() {
        if (this.style.width === '100%') {
            this.style.width = 'auto'
            this.style.maxWidth = 'none'
            this.style.cursor = 'zoom-out'
            diagramContainer.style.textAlign = 'left'
        } else {
            this.style.width = '100%'
            this.style.maxWidth = '100%'
            this.style.cursor = 'zoom-in'
            diagramContainer.style.textAlign = 'center'
        }
    }
    
    // Create download link
    let downloadLink = document.createElement('a')
    downloadLink.href = `/api/diagram/${encodeURIComponent(diagramPath)}`
    downloadLink.download = 'azure_architecture_diagram.png'
    downloadLink.textContent = '📥 다이어그램 다운로드'
    downloadLink.className = 'diagram-download-link'
    downloadLink.style.display = 'inline-block'
    downloadLink.style.marginTop = '1rem'
    downloadLink.style.padding = '0.5rem 1rem'
    downloadLink.style.backgroundColor = 'var(--primary-color)'
    downloadLink.style.color = 'white'
    downloadLink.style.textDecoration = 'none'
    downloadLink.style.borderRadius = 'var(--border-radius-sm)'
    downloadLink.style.fontSize = '0.875rem'
    downloadLink.style.transition = 'var(--transition)'
    
    downloadLink.onmouseover = function() {
        this.style.backgroundColor = 'var(--primary-hover)'
    }
    
    downloadLink.onmouseout = function() {
        this.style.backgroundColor = 'var(--primary-color)'
    }
    
    // Assemble the diagram container
    diagramContainer.appendChild(diagramTitle)
    diagramContainer.appendChild(diagramImg)
    diagramContainer.appendChild(downloadLink)
    
    // Add diagram to message content
    messageContent.appendChild(diagramContainer)
    
    // Assemble the complete message
    diagramMessage.appendChild(messageHeader)
    diagramMessage.appendChild(messageContent)
    
    // Insert diagram message into chat history
    chatHistoryDiv.appendChild(diagramMessage)
    chatHistoryDiv.scrollTop = chatHistoryDiv.scrollHeight
    
    console.log('[displayArchitectureDiagram] Diagram message added to chatHistory')
    console.log(`[displayArchitectureDiagram] chatHistory now has ${chatHistoryDiv.children.length} child elements`)
}

// Fetch ICE token from the server
function fetchIceToken() {
    fetch('/api/getIceToken', {
        method: 'GET',
    }).then(response => {
        if (response.ok) {
            response.json().then(data => {
                iceServerUrl = data.Urls[0]
                iceServerUsername = data.Username
                iceServerCredential = data.Password
                console.log(`[${new Date().toISOString()}] ICE token fetched.`)
                preparePeerConnection()
                // After first successful ICE token fetch, if no active session, show ready status
                if (!sessionActive) {
                    updateStatusIndicator('Ready to Start', 'initializing')
                }
            })
        } else {
            console.error(`Failed fetching ICE token: ${response.status} ${response.statusText}`)
        }
    })
}

// Connect to avatar service
function connectAvatar() {
    document.getElementById('startSession').disabled = true
    updateStatusIndicator('Connecting to Avatar...', 'connecting')
    waitForPeerConnectionAndStartSession()
    document.getElementById('configuration').hidden = true
}

// Create speech recognizer
function createSpeechRecognizer() {
    fetch('/api/getSpeechToken', {
        method: 'GET',
    })
    .then(response => {
        if (response.ok) {
            const speechRegion = response.headers.get('SpeechRegion')
            const speechPrivateEndpoint = response.headers.get('SpeechPrivateEndpoint')
            response.text().then(text => {
                const speechToken = text
                const speechRecognitionConfig = speechPrivateEndpoint ?
                    SpeechSDK.SpeechConfig.fromEndpoint(new URL(`wss://${speechPrivateEndpoint.replace('https://', '')}/stt/speech/universal/v2`)) :
                    SpeechSDK.SpeechConfig.fromEndpoint(new URL(`wss://${speechRegion}.stt.speech.microsoft.com/speech/universal/v2`))
                speechRecognitionConfig.authorizationToken = speechToken
                speechRecognitionConfig.setProperty(SpeechSDK.PropertyId.SpeechServiceConnection_LanguageIdMode, "Continuous")
                speechRecognitionConfig.setProperty("SpeechContext-PhraseDetection.TrailingSilenceTimeout", "3000")
                speechRecognitionConfig.setProperty("SpeechContext-PhraseDetection.InitialSilenceTimeout", "10000")
                speechRecognitionConfig.setProperty("SpeechContext-PhraseDetection.Dictation.Segmentation.Mode", "Custom")
                speechRecognitionConfig.setProperty("SpeechContext-PhraseDetection.Dictation.Segmentation.SegmentationSilenceTimeoutMs", "200")
                var sttLocales = document.getElementById('sttLocales').value.split(',')
                var autoDetectSourceLanguageConfig = SpeechSDK.AutoDetectSourceLanguageConfig.fromLanguages(sttLocales)
                speechRecognizer = SpeechSDK.SpeechRecognizer.FromConfig(speechRecognitionConfig, autoDetectSourceLanguageConfig, SpeechSDK.AudioConfig.fromDefaultMicrophoneInput())
            })
        } else {
            throw new Error(`Failed fetching speech token: ${response.status} ${response.statusText}`)
        }
    })
}

function waitForPeerConnectionAndStartSession() {
    if (peerConnectionQueue.length > 0) {
        let peerConnection = peerConnectionQueue.shift()
        connectToAvatarService(peerConnection)
        if (peerConnectionQueue.length === 0) {
            preparePeerConnection()
        }
    }
    else {
        console.log("Waiting for peer connection to be ready...")
        setTimeout(waitForPeerConnectionAndStartSession, 1000)
    }
}

// Disconnect from avatar service
function disconnectAvatar(closeSpeechRecognizer = false) {
    fetch('/api/disconnectAvatar', {
        method: 'POST',
        headers: {
            'ClientId': clientId
        },
        body: ''
    })

    if (speechRecognizer !== undefined) {
        speechRecognizer.stopContinuousRecognitionAsync()
        if (closeSpeechRecognizer) {
            speechRecognizer.close()
        }
    }

    sessionActive = false
}

function setupWebSocket() {
    socket = io.connect(`${window.location.origin}?clientId=${clientId}`)
    socket.on('connect', function() {
        console.log('WebSocket connected.')
    })

    socket.on('response', function(data) {
        let path = data.path
        if (path === 'api.chat') {
            lastInteractionTime = new Date()
            let chunkString = data.chatResponse
            if (sttLatencyRegex.test(chunkString)) {
                let sttLatency = parseInt(sttLatencyRegex.exec(chunkString)[0].replace('<STTL>', '').replace('</STTL>', ''))
                console.log(`STT latency: ${sttLatency} ms`)
                let latencyLogTextArea = document.getElementById('latencyLog')
                latencyLogTextArea.innerHTML += `STT latency: ${sttLatency} ms\n`
                chunkString = chunkString.replace(sttLatencyRegex, '')
            }

            if (firstTokenLatencyRegex.test(chunkString)) {
                let aoaiFirstTokenLatency = parseInt(firstTokenLatencyRegex.exec(chunkString)[0].replace('<FTL>', '').replace('</FTL>', ''))
                // console.log(`AOAI first token latency: ${aoaiFirstTokenLatency} ms`)
                chunkString = chunkString.replace(firstTokenLatencyRegex, '')
            }

            if (firstSentenceLatencyRegex.test(chunkString)) {
                let aoaiFirstSentenceLatency = parseInt(firstSentenceLatencyRegex.exec(chunkString)[0].replace('<FSL>', '').replace('</FSL>', ''))
                chatResponseReceivedTime = new Date()
                console.log(`AOAI latency: ${aoaiFirstSentenceLatency} ms`)
                let latencyLogTextArea = document.getElementById('latencyLog')
                latencyLogTextArea.innerHTML += `AOAI latency: ${aoaiFirstSentenceLatency} ms\n`
                latencyLogTextArea.scrollTop = latencyLogTextArea.scrollHeight
                chunkString = chunkString.replace(firstSentenceLatencyRegex, '')
            }

            // Use buffering for diagram processing
            let processedText = processStreamBuffer(chunkString)

            if (processedText.trim()) {
                // Handle first response chunk
                if (isFirstResponseChunk) {
                    hideTypingIndicator()
                    addAssistantMessage('', false)
                    isFirstResponseChunk = false
                    completeWsResponse = ''
                }
                
                // Add to complete response for final markdown parsing
                completeWsResponse += processedText
                
                if (currentAssistantMessage) {
                    const messageContent = currentAssistantMessage.querySelector('.message-content')
                    // 실시간 업데이트에서도 다이어그램 태그 제거
                    let currentText = messageContent.textContent
                    let newText = currentText + processedText
                    let cleanedText = newText.replace(/<DIAGRAM>.*?<\/DIAGRAM>/g, '')
                    messageContent.textContent = cleanedText
                    
                    // Scroll to bottom
                    const chatHistory = document.getElementById('chatHistory')
                    chatHistory.scrollTop = chatHistory.scrollHeight
                }
                
                // Reset completion timer
                if (wsResponseTimer) {
                    clearTimeout(wsResponseTimer)
                }
                
                // Set timer to detect completion (no new chunks for 1 second)
                wsResponseTimer = setTimeout(() => {
                    if (currentAssistantMessage) {
                        const messageContent = currentAssistantMessage.querySelector('.message-content')
                        // 다이어그램 태그를 완전히 제거한 후 마크다운 파싱
                        let cleanedResponse = completeWsResponse.replace(/<DIAGRAM>.*?<\/DIAGRAM>/g, '')
                        messageContent.innerHTML = marked.parse(cleanedResponse)
                        if (typeof Prism !== 'undefined') {
                            Prism.highlightAllUnder(messageContent)
                        }
                        currentAssistantMessage = null
                        completeWsResponse = ''
                        
                        // Scroll to bottom after markdown parsing
                        const chatHistory = document.getElementById('chatHistory')
                        chatHistory.scrollTop = chatHistory.scrollHeight
                    }
                }, 1000)
            }
        } else if (path === 'api.event') {
            console.log("[" + (new Date()).toISOString() + "] WebSocket event received: " + data.eventType)
            if (data.eventType === 'SPEECH_SYNTHESIZER_DISCONNECTED') {
                if (document.getElementById('autoReconnectAvatar').checked && !userClosedSession && !isReconnecting) {
                    // No longer reconnect when there is no interaction for a while
                    if (new Date() - lastInteractionTime < 300000) {
                        // Session disconnected unexpectedly, need reconnect
                        console.log(`[${(new Date()).toISOString()}] The speech synthesizer got disconnected unexpectedly, need reconnect.`)
                        isReconnecting = true
                        connectAvatar()
                        createSpeechRecognizer()
                    }
                }
            }
        }
    })
}

// Prepare peer connection for WebRTC
function preparePeerConnection() {
    // Create WebRTC peer connection
    let peerConnection = new RTCPeerConnection({
        iceServers: [{
            urls: [ iceServerUrl ],
            username: iceServerUsername,
            credential: iceServerCredential
        }],
        iceTransportPolicy: 'relay'
    })

    // Fetch WebRTC video stream and mount it to an HTML video element
    peerConnection.ontrack = function (event) {
        if (event.track.kind === 'audio') {
            let audioElement = document.createElement('audio')
            audioElement.id = 'audioPlayer'
            audioElement.srcObject = event.streams[0]
            audioElement.autoplay = true

            audioElement.onplaying = () => {
                console.log(`WebRTC ${event.track.kind} channel connected.`)
            }

            // Clean up existing audio element if there is any
            remoteVideoDiv = document.getElementById('remoteVideo')
            for (var i = 0; i < remoteVideoDiv.childNodes.length; i++) {
                if (remoteVideoDiv.childNodes[i].localName === event.track.kind) {
                    remoteVideoDiv.removeChild(remoteVideoDiv.childNodes[i])
                }
            }

            // Append the new audio element
            document.getElementById('remoteVideo').appendChild(audioElement)
        }

        if (event.track.kind === 'video') {
            let videoElement = document.createElement('video')
            videoElement.id = 'videoPlayer'
            videoElement.srcObject = event.streams[0]
            videoElement.autoplay = true
            videoElement.playsInline = true
            videoElement.style.width = '0.5px'
            document.getElementById('remoteVideo').appendChild(videoElement)

            // Continue speaking if there are unfinished sentences while reconnecting
            if (isReconnecting) {
                fetch('/api/chat/continueSpeaking', {
                    method: 'POST',
                    headers: {
                        'ClientId': clientId
                    },
                    body: ''
                })
            }

            videoElement.onplaying = () => {
                // Clean up existing video element if there is any
                remoteVideoDiv = document.getElementById('remoteVideo')
                for (var i = 0; i < remoteVideoDiv.childNodes.length; i++) {
                    if (remoteVideoDiv.childNodes[i].localName === event.track.kind) {
                        remoteVideoDiv.removeChild(remoteVideoDiv.childNodes[i])
                    }
                }

                // Append the new video element
                videoElement.style.width = '100%'
                document.getElementById('remoteVideo').appendChild(videoElement)

                console.log(`WebRTC ${event.track.kind} channel connected.`)
                updateStatusIndicator('Avatar Connected', 'connected')
                document.getElementById('microphone').disabled = false
                document.getElementById('stopSession').disabled = false
                document.getElementById('chatHistory').hidden = false
                document.getElementById('latencyLog').hidden = false
                document.getElementById('showTypeMessage').disabled = false

                if (document.getElementById('useLocalVideoForIdle').checked) {
                    document.getElementById('localVideo').hidden = true
                    if (lastSpeakTime === undefined) {
                        lastSpeakTime = new Date()
                    }
                }

                isReconnecting = false
                setTimeout(() => { sessionActive = true }, 5000) // Set session active after 5 seconds
            }
        }
    }

    // Listen to data channel, to get the event from the server
    peerConnection.addEventListener("datachannel", event => {
        peerConnectionDataChannel = event.channel
        peerConnectionDataChannel.onmessage = e => {
            console.log("[" + (new Date()).toISOString() + "] WebRTC event received: " + e.data)

            if (e.data.includes("EVENT_TYPE_SWITCH_TO_SPEAKING")) {
                if (chatResponseReceivedTime !== undefined) {
                    let speakStartTime = new Date()
                    let ttsLatency = speakStartTime - chatResponseReceivedTime
                    console.log(`TTS latency: ${ttsLatency} ms`)
                    let latencyLogTextArea = document.getElementById('latencyLog')
                    latencyLogTextArea.innerHTML += `TTS latency: ${ttsLatency} ms\n\n`
                    latencyLogTextArea.scrollTop = latencyLogTextArea.scrollHeight
                    chatResponseReceivedTime = undefined
                }

                isSpeaking = true
                updateStatusIndicator('Avatar Speaking', 'connected')
                document.getElementById('stopSpeaking').disabled = false
                // Show recording indicator
                const recordingIndicator = document.getElementById('recordingIndicator')
                if (recordingIndicator) recordingIndicator.style.display = 'flex'
            } else if (e.data.includes("EVENT_TYPE_SWITCH_TO_IDLE")) {
                isSpeaking = false
                lastSpeakTime = new Date()
                updateStatusIndicator('Avatar Ready', 'connected')
                document.getElementById('stopSpeaking').disabled = true
                // Hide recording indicator
                const recordingIndicator = document.getElementById('recordingIndicator')
                if (recordingIndicator) recordingIndicator.style.display = 'none'
            } else if (e.data.includes("EVENT_TYPE_SESSION_END")) {
                if (document.getElementById('autoReconnectAvatar').checked && !userClosedSession && !isReconnecting) {
                    // No longer reconnect when there is no interaction for a while
                    if (new Date() - lastInteractionTime < 300000) {
                        // Session disconnected unexpectedly, need reconnect
                        console.log(`[${(new Date()).toISOString()}] The session ended unexpectedly, need reconnect.`)
                        isReconnecting = true
                        // Remove data channel onmessage callback to avoid duplicatedly triggering reconnect
                        peerConnectionDataChannel.onmessage = null
                        connectAvatar()
                        createSpeechRecognizer()
                    }
                }
            }
        }
    })

    // This is a workaround to make sure the data channel listening is working by creating a data channel from the client side
    c = peerConnection.createDataChannel("eventChannel")

    // Make necessary update to the web page when the connection state changes
    peerConnection.oniceconnectionstatechange = e => {
        console.log("WebRTC status: " + peerConnection.iceConnectionState)
        if (peerConnection.iceConnectionState === 'disconnected') {
            if (document.getElementById('useLocalVideoForIdle').checked) {
                document.getElementById('localVideo').hidden = false
                document.getElementById('remoteVideo').style.width = '0.1px'
            }
        }
    }

    // Offer to receive 1 audio, and 1 video track
    peerConnection.addTransceiver('video', { direction: 'sendrecv' })
    peerConnection.addTransceiver('audio', { direction: 'sendrecv' })

    // Connect to avatar service when ICE candidates gathering is done
    iceGatheringDone = false

    peerConnection.onicecandidate = e => {
        if (!e.candidate && !iceGatheringDone) {
            iceGatheringDone = true
            peerConnectionQueue.push(peerConnection)
            console.log("[" + (new Date()).toISOString() + "] ICE gathering done, new peer connection prepared.")
            if (peerConnectionQueue.length > 1) {
                peerConnectionQueue.shift()
            }
        }
    }

    peerConnection.createOffer().then(sdp => {
        peerConnection.setLocalDescription(sdp).then(() => { setTimeout(() => {
            if (!iceGatheringDone) {
                iceGatheringDone = true
                peerConnectionQueue.push(peerConnection)
                console.log("[" + (new Date()).toISOString() + "] ICE gathering done, new peer connection prepared.")
                if (peerConnectionQueue.length > 1) {
                    peerConnectionQueue.shift()
                }
            }
        }, 10000) })
    })
}

// Connect to TTS Avatar Service
function connectToAvatarService(peerConnection) {
    let localSdp = btoa(JSON.stringify(peerConnection.localDescription))
    let headers = {
        'ClientId': clientId,
        'AvatarCharacter': document.getElementById('talkingAvatarCharacter').value,
        'AvatarStyle': document.getElementById('talkingAvatarStyle').value,
        'IsCustomAvatar': document.getElementById('customizedAvatar').checked
    }

    if (isReconnecting) {
        headers['Reconnect'] = true
    }

    if (document.getElementById('azureOpenAIDeploymentName').value !== '') {
        headers['AoaiDeploymentName'] = document.getElementById('azureOpenAIDeploymentName').value
    }

    if (document.getElementById('enableOyd').checked && document.getElementById('azureCogSearchIndexName').value !== '') {
        headers['CognitiveSearchIndexName'] = document.getElementById('azureCogSearchIndexName').value
    }

    if (document.getElementById('ttsVoice').value !== '') {
        headers['TtsVoice'] = document.getElementById('ttsVoice').value
    }

    if (document.getElementById('customVoiceEndpointId').value !== '') {
        headers['CustomVoiceEndpointId'] = document.getElementById('customVoiceEndpointId').value
    }

    if (document.getElementById('personalVoiceSpeakerProfileID').value !== '') {
        headers['PersonalVoiceSpeakerProfileId'] = document.getElementById('personalVoiceSpeakerProfileID').value
    }

    fetch('/api/connectAvatar', {
        method: 'POST',
        headers: headers,
        body: localSdp
    })
    .then(response => {
        if (response.ok) {
            response.text().then(text => {
                const remoteSdp = text
                peerConnection.setRemoteDescription(new RTCSessionDescription(JSON.parse(atob(remoteSdp))))
            })
        } else {
            document.getElementById('startSession').disabled = false;
            document.getElementById('configuration').hidden = false;
            throw new Error(`Failed connecting to the Avatar service: ${response.status} ${response.statusText}`)
        }
    })
}

// Handle user query. Send user query to the chat API and display the response.
function handleUserQuery(userQuery) {
    lastInteractionTime = new Date()
    chatRequestSentTime = new Date()
    
    // Add user message to chat
    addUserMessage(userQuery)
    
    // Show typing indicator
    showTypingIndicator()
    
    // Clear any existing assistant message
    currentAssistantMessage = null
    
    if (socket !== undefined) {
        socket.emit('message', { clientId: clientId, path: 'api.chat', systemPrompt: document.getElementById('prompt').value, userQuery: userQuery })
        isFirstResponseChunk = true
        return
    }

    fetch('/api/chat', {
        method: 'POST',
        headers: {
            'ClientId': clientId,
            'SystemPrompt': document.getElementById('prompt').value,
            'Content-Type': 'text/plain'
        },
        body: userQuery
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Chat API response status: ${response.status} ${response.statusText}`)
        }

        // Hide typing indicator when response starts
        hideTypingIndicator()
        
        // Create initial assistant message for streaming
        addAssistantMessage('', false)

        const reader = response.body.getReader()
        let completeResponse = ''

        // Function to recursively read chunks from the stream
        function read() {
            return reader.read().then(({ value, done }) => {
                // Check if there is still data to read
                if (done) {
                    // Stream complete - process any remaining buffer and finalize message
                    let finalText = clearStreamBuffer()
                    if (finalText.trim()) {
                        completeResponse += finalText
                    }
                    
                    // Update message content with complete markdown parsing
                    if (currentAssistantMessage) {
                        const messageContent = currentAssistantMessage.querySelector('.message-content')
                        messageContent.innerHTML = marked.parse(completeResponse)
                        if (typeof Prism !== 'undefined') {
                            Prism.highlightAllUnder(messageContent)
                        }
                        currentAssistantMessage = null
                    }
                    return
                }

                // Process the chunk of data (value)
                let chunkString = new TextDecoder().decode(value, { stream: true })

                if (firstTokenLatencyRegex.test(chunkString)) {
                    let aoaiFirstTokenLatency = parseInt(firstTokenLatencyRegex.exec(chunkString)[0].replace('<FTL>', '').replace('</FTL>', ''))
                    // console.log(`AOAI first token latency: ${aoaiFirstTokenLatency} ms`)
                    chunkString = chunkString.replace(firstTokenLatencyRegex, '')
                    if (chunkString === '') {
                        return read()
                    }
                }

                if (firstSentenceLatencyRegex.test(chunkString)) {
                    let aoaiFirstSentenceLatency = parseInt(firstSentenceLatencyRegex.exec(chunkString)[0].replace('<FSL>', '').replace('</FSL>', ''))
                    chatResponseReceivedTime = new Date()
                    let chatLatency = chatResponseReceivedTime - chatRequestSentTime
                    let appServiceLatency = chatLatency - aoaiFirstSentenceLatency
                    console.log(`App service latency: ${appServiceLatency} ms`)
                    console.log(`AOAI latency: ${aoaiFirstSentenceLatency} ms`)
                    let latencyLogTextArea = document.getElementById('latencyLog')
                    latencyLogTextArea.innerHTML += `App service latency: ${appServiceLatency} ms\n`
                    latencyLogTextArea.innerHTML += `AOAI latency: ${aoaiFirstSentenceLatency} ms\n`
                    latencyLogTextArea.scrollTop = latencyLogTextArea.scrollHeight
                    chunkString = chunkString.replace(firstSentenceLatencyRegex, '')
                    if (chunkString === '') {
                        return read()
                    }
                }

                // Use buffering for diagram processing
                let processedText = processStreamBuffer(chunkString)

                if (processedText.trim()) {
                    // Add to complete response for final markdown parsing
                    completeResponse += processedText
                    
                    // For streaming display, just append text content
                    if (currentAssistantMessage) {
                        const messageContent = currentAssistantMessage.querySelector('.message-content')
                        messageContent.textContent += processedText
                        
                        // Scroll to bottom
                        const chatHistory = document.getElementById('chatHistory')
                        chatHistory.scrollTop = chatHistory.scrollHeight
                    }
                }

                // Continue reading the next chunk
                return read()
            })
        }

        // Start reading the stream
        return read()
    })
}

// Handle local video. If the user is not speaking for 15 seconds, switch to local video.
function handleLocalVideo() {
    if (lastSpeakTime === undefined) {
        return
    }

    let currentTime = new Date()
    if (currentTime - lastSpeakTime > 15000) {
        if (document.getElementById('useLocalVideoForIdle').checked && sessionActive && !isSpeaking) {
            disconnectAvatar()
            userClosedSession = true // Indicating the session was closed on purpose, not due to network issue
            document.getElementById('localVideo').hidden = false
            document.getElementById('remoteVideo').style.width = '0.1px'
            sessionActive = false
        }
    }
}

// Check server status
function checkServerStatus() {
    fetch('/api/getStatus', {
        method: 'GET',
        headers: {
            'ClientId': clientId
        }
    })
    .then(response => {
        if (response.ok) {
            response.text().then(text => {
                responseJson = JSON.parse(text)
                synthesizerConnected = responseJson.speechSynthesizerConnected
                if (speechSynthesizerConnected === true && synthesizerConnected === false) {
                    console.log(`[${(new Date()).toISOString()}] The speech synthesizer connection is closed.`)
                    if (document.getElementById('autoReconnectAvatar').checked && !userClosedSession && !isReconnecting) {
                        // No longer reconnect when there is no interaction for a while
                        if (new Date() - lastInteractionTime < 300000) {
                            // Session disconnected unexpectedly, need reconnect
                            console.log(`[${(new Date()).toISOString()}] The speech synthesizer got disconnected unexpectedly, need reconnect.`)
                            isReconnecting = true
                            connectAvatar()
                            createSpeechRecognizer()
                        }
                    }
                }

                speechSynthesizerConnected = synthesizerConnected
            })
        }
    })
}

// Check whether the avatar video stream is hung
function checkHung() {
    // Check whether the avatar video stream is hung, by checking whether the video time is advancing
    let videoElement = document.getElementById('videoPlayer')
    if (videoElement !== null && videoElement !== undefined && sessionActive) {
        let videoTime = videoElement.currentTime
        setTimeout(() => {
            // Check whether the video time is advancing
            if (videoElement.currentTime === videoTime) {
                // Check whether the session is active to avoid duplicatedly triggering reconnect
                if (sessionActive) {
                    sessionActive = false
                    if (document.getElementById('autoReconnectAvatar').checked) {
                        // No longer reconnect when there is no interaction for a while
                        if (new Date() - lastInteractionTime < 300000) {
                            console.log(`[${(new Date()).toISOString()}] The video stream got disconnected, need reconnect.`)
                            isReconnecting = true
                            // Remove data channel onmessage callback to avoid duplicatedly triggering reconnect
                            peerConnectionDataChannel.onmessage = null
                            connectAvatar()
                            createSpeechRecognizer()
                        }
                    }
                }
            }
        }, 2000)
    }
}

window.onload = () => {
    clientId = document.getElementById('clientId').value

    fetchIceToken() // Fetch ICE token and prepare peer connection on page load
    setInterval(fetchIceToken, 60 * 1000) // Fetch ICE token and prepare peer connection every 1 minute

    enableWebSockets = document.getElementById('enableWebSockets').value === 'True'
    if (!enableWebSockets) {
        setInterval(() => {
            checkServerStatus()
        }, 2000) // Check server status every 2 seconds
    }

    setInterval(() => {
        checkHung()
    }, 2000) // Check session activity every 2 seconds

    // Update status indicator
    updateStatusIndicator('Initializing...', 'initializing')
}

// Update status indicator
function updateStatusIndicator(text, status) {
    const statusText = document.getElementById('statusText')
    const statusDot = document.getElementById('statusDot')
    
    if (statusText) statusText.textContent = text
    if (statusDot) {
        statusDot.className = 'status-dot'
        if (status === 'connected') statusDot.classList.add('connected')
    }
}

window.startSession = () => {
    lastInteractionTime = new Date()
    updateStatusIndicator('Connecting...', 'connecting')
    
    if (enableWebSockets) {
        setupWebSocket()
    }

    userClosedSession = false

    createSpeechRecognizer()
    if (document.getElementById('useLocalVideoForIdle').checked) {
        document.getElementById('startSession').disabled = true
        document.getElementById('configuration').hidden = true
        document.getElementById('microphone').disabled = false
        document.getElementById('stopSession').disabled = false
        document.getElementById('localVideo').hidden = false
        document.getElementById('remoteVideo').style.width = '0.1px'
        document.getElementById('chatHistory').hidden = false
        document.getElementById('latencyLog').hidden = false
        document.getElementById('showTypeMessage').disabled = false
        updateStatusIndicator('Session Active', 'connected')
        return
    }

    connectAvatar()
}

window.stopSpeaking = () => {
    lastInteractionTime = new Date()
    document.getElementById('stopSpeaking').disabled = true

    if (socket !== undefined) {
        socket.emit('message', { clientId: clientId, path: 'api.stopSpeaking' })
        return
    }

    fetch('/api/stopSpeaking', {
        method: 'POST',
        headers: {
            'ClientId': clientId
        },
        body: ''
    })
    .then(response => {
        if (response.ok) {
            console.log('Successfully stopped speaking.')
        } else {
            throw new Error(`Failed to stop speaking: ${response.status} ${response.statusText}`)
        }
    })
}

window.stopSession = () => {
    lastInteractionTime = new Date()
    updateStatusIndicator('Disconnecting...', 'initializing')
    document.getElementById('startSession').disabled = false
    document.getElementById('microphone').disabled = true
    document.getElementById('stopSession').disabled = true
    document.getElementById('configuration').hidden = false
    document.getElementById('chatHistory').hidden = true
    document.getElementById('latencyLog').hidden = true
    document.getElementById('showTypeMessage').checked = false
    document.getElementById('showTypeMessage').disabled = true
    document.getElementById('userMessageBox').hidden = true
    if (document.getElementById('useLocalVideoForIdle').checked) {
        document.getElementById('localVideo').hidden = true
    }

    userClosedSession = true // Indicating the session was closed by user on purpose, not due to network issue
    disconnectAvatar(true)
    
    setTimeout(() => {
        updateStatusIndicator('Session Ended', 'initializing')
    }, 1000)
}

window.clearChatHistory = () => {
    lastInteractionTime = new Date()
    // Clear stream buffer and response
    streamBuffer = ''
    completeWsResponse = ''
    // Reset current assistant message
    currentAssistantMessage = null
    // Clear any pending timers
    if (wsResponseTimer) {
        clearTimeout(wsResponseTimer)
        wsResponseTimer = null
    }
    
    fetch('/api/chat/clearHistory', {
        method: 'POST',
        headers: {
            'ClientId': clientId,
            'SystemPrompt': document.getElementById('prompt').value
        },
        body: ''
    })
    .then(response => {
        if (response.ok) {
            // Clear all child nodes from chatHistory to properly remove all messages
            let chatHistoryDiv = document.getElementById('chatHistory')
            while (chatHistoryDiv.firstChild) {
                chatHistoryDiv.removeChild(chatHistoryDiv.firstChild)
            }
            document.getElementById('latencyLog').innerHTML = ''
        } else {
            throw new Error(`Failed to clear chat history: ${response.status} ${response.statusText}`)
        }
    })
}

window.microphone = () => {
    lastInteractionTime = new Date()
    const micButton = document.getElementById('microphone')
    const micIcon = micButton.querySelector('i')
    const micText = micButton.querySelector('span')
    
    if (micText.textContent === 'Stop Microphone') {
        // Stop microphone for websocket mode
        if (socket !== undefined) {
            micButton.disabled = true
            fetch('/api/disconnectSTT', {
                method: 'POST',
                headers: {
                    'ClientId': clientId
                },
                body: ''
            })
            .then(() => {
                micText.textContent = 'Start Microphone'
                micIcon.className = 'fas fa-microphone'
                micButton.disabled = false
                updateStatusIndicator('Microphone Off', 'connected')
                if (audioContext !== undefined) {
                    audioContext.close()
                    audioContext = undefined
                }
            })
        }

        // Stop microphone
        micButton.disabled = true
        speechRecognizer.stopContinuousRecognitionAsync(
            () => {
                micText.textContent = 'Start Microphone'
                micIcon.className = 'fas fa-microphone'
                micButton.disabled = false
                updateStatusIndicator('Microphone Off', 'connected')
            }, (err) => {
                console.log("Failed to stop continuous recognition:", err)
                micButton.disabled = false
            })

        return
    }

    // Start microphone for websocket mode
    if (socket !== undefined) {
        document.getElementById('microphone').disabled = true
        // Audio worklet script (https://developer.chrome.com/blog/audio-worklet) for recording audio
        const audioWorkletScript = `class MicAudioWorkletProcessor extends AudioWorkletProcessor {
                constructor(options) {
                    super(options)
                }

                process(inputs, outputs, parameters) {
                    const input = inputs[0]
                    const output = []
                    for (let channel = 0; channel < input.length; channel += 1) {
                        output[channel] = input[channel]
                    }
                    this.port.postMessage(output[0])
                    return true
                }
            }

            registerProcessor('mic-audio-worklet-processor', MicAudioWorkletProcessor)`
        const audioWorkletScriptBlob = new Blob([audioWorkletScript], { type: 'application/javascript; charset=utf-8' })
        const audioWorkletScriptUrl = URL.createObjectURL(audioWorkletScriptBlob)

        fetch('/api/connectSTT', {
            method: 'POST',
            headers: {
                'ClientId': clientId,
                'SystemPrompt': document.getElementById('prompt').value
            },
            body: ''
        })
        .then(response => {
            micButton.disabled = false
            if (response.ok) {
                micText.textContent = 'Stop Microphone'
                micIcon.className = 'fas fa-microphone-slash'
                updateStatusIndicator('Listening...', 'connected')

                navigator.mediaDevices
                .getUserMedia({
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        sampleRate: 16000
                    }
                })
                .then((stream) => {
                    audioContext = new AudioContext({ sampleRate: 16000 })
                    const audioSource = audioContext.createMediaStreamSource(stream)
                    audioContext.audioWorklet
                        .addModule(audioWorkletScriptUrl)
                        .then(() => {
                            const audioWorkletNode = new AudioWorkletNode(audioContext, 'mic-audio-worklet-processor')
                            audioWorkletNode.port.onmessage = (e) => {
                                const audioDataFloat32 = e.data
                                const audioDataInt16 = new Int16Array(audioDataFloat32.length)
                                for (let i = 0; i < audioDataFloat32.length; i++) {
                                    audioDataInt16[i] = Math.max(-0x8000, Math.min(0x7FFF, audioDataFloat32[i] * 0x7FFF))
                                }
                                const audioDataBytes = new Uint8Array(audioDataInt16.buffer)
                                const audioDataBase64 = btoa(String.fromCharCode(...audioDataBytes))
                                socket.emit('message', { clientId: clientId, path: 'api.audio', audioChunk: audioDataBase64 })
                            }

                            audioSource.connect(audioWorkletNode)
                            audioWorkletNode.connect(audioContext.destination)
                        })
                        .catch((err) => {
                            console.log('Failed to add audio worklet module:', err)
                        })
                })
                .catch((err) => {
                    console.log('Failed to get user media:', err)
                })
            } else {
                throw new Error(`Failed to connect STT service: ${response.status} ${response.statusText}`)
            }
        })

        return
    }

    if (document.getElementById('useLocalVideoForIdle').checked) {
        if (!sessionActive) {
            connectAvatar()
        }

        setTimeout(() => {
            document.getElementById('audioPlayer').play()
        }, 5000)
    } else {
        document.getElementById('audioPlayer').play()
    }

    document.getElementById('microphone').disabled = true
    speechRecognizer.recognizing = async (s, e) => {
        if (isFirstRecognizingEvent && isSpeaking) {
            window.stopSpeaking()
            isFirstRecognizingEvent = false
        }
    }

    speechRecognizer.recognized = async (s, e) => {
        if (e.result.reason === SpeechSDK.ResultReason.RecognizedSpeech) {
            let userQuery = e.result.text.trim()
            if (userQuery === '') {
                return
            }

            // If a typed submission happened recently, skip STT handling to avoid duplicate User entry
            if (lastTypeSubmitTime !== 0 && (Date.now() - lastTypeSubmitTime) < 1500) {
                // clear the flag and ignore this STT event
                lastTypeSubmitTime = 0
                return
            }

            let recognitionResultReceivedTime = new Date()
            let speechFinishedOffset = (e.result.offset + e.result.duration) / 10000
            let sttLatency = recognitionResultReceivedTime - recognitionStartedTime - speechFinishedOffset
            console.log(`STT latency: ${sttLatency} ms`)
            let latencyLogTextArea = document.getElementById('latencyLog')
            latencyLogTextArea.innerHTML += `STT latency: ${sttLatency} ms\n`
            latencyLogTextArea.scrollTop = latencyLogTextArea.scrollHeight

            // Auto stop microphone when a phrase is recognized, when it's not continuous conversation mode
            if (!document.getElementById('continuousConversation').checked) {
                micButton.disabled = true
                speechRecognizer.stopContinuousRecognitionAsync(
                    () => {
                        micText.textContent = 'Start Microphone'
                        micIcon.className = 'fas fa-microphone'
                        micButton.disabled = false
                        updateStatusIndicator('Processing...', 'connected')
                    }, (err) => {
                        console.log("Failed to stop continuous recognition:", err)
                        micButton.disabled = false
                    })
            }

            let chatHistoryTextArea = document.getElementById('chatHistory')
            
            // Don't manually add user text here - handleUserQuery will handle it
            handleUserQuery(userQuery)

            isFirstRecognizingEvent = true
        }
    }

    recognitionStartedTime = new Date()
    speechRecognizer.startContinuousRecognitionAsync(
        () => {
            micText.textContent = 'Stop Microphone'
            micIcon.className = 'fas fa-microphone-slash'
            micButton.disabled = false
            updateStatusIndicator('Listening...', 'connected')
        }, (err) => {
            console.log("Failed to start continuous recognition:", err)
            micButton.disabled = false
        })
}

window.updataEnableOyd = () => {
    if (document.getElementById('enableOyd').checked) {
        document.getElementById('cogSearchConfig').hidden = false
    } else {
        document.getElementById('cogSearchConfig').hidden = true
    }
}

window.updateTypeMessageBox = () => {
    const userMessageBox = document.getElementById('userMessageBox')
    const submitHandler = (e) => {
        if (e.key !== 'Enter') return
        const raw = document.getElementById('userMessageBox').value
        const userQuery = raw.trim()
        if (userQuery === '') return

        if (isSpeaking) {
            window.stopSpeaking()
        }

        // Mark typed submission time to suppress immediate STT duplicate
        lastTypeSubmitTime = Date.now()

        handleUserQuery(userQuery)
        document.getElementById('userMessageBox').value = ''
    }

    if (document.getElementById('showTypeMessage').checked) {
        userMessageBox.hidden = false
        // prevent duplicate handlers
        userMessageBox.removeEventListener('keyup', submitHandler)
        userMessageBox.addEventListener('keyup', submitHandler)
    } else {
        userMessageBox.hidden = true
        userMessageBox.removeEventListener('keyup', submitHandler)
    }
}

window.updateLocalVideoForIdle = () => {
    if (document.getElementById('useLocalVideoForIdle').checked) {
        document.getElementById('showTypeMessageCheckbox').hidden = true
    } else {
        document.getElementById('showTypeMessageCheckbox').hidden = false
    }
}

window.onbeforeunload = () => {
    navigator.sendBeacon('/api/releaseClient', JSON.stringify({ clientId: clientId }))
}
