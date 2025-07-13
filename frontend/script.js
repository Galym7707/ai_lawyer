// ===== Backend API helpers =====
const API_BASE = window.location.hostname.includes('vercel.app')
      ? 'https://ai-lawyer.up.railway.app'  // production backend on Railway
      : 'http://localhost:5000';            // local backend during dev

const apiFetch = (path, options = {}) => fetch(`${API_BASE}${path}`, options);

// Gracefully parse JSON or throw detailed error when server returns HTML/CORS error page
async function safeJson(res) {
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return res.json();
  }
  const text = await res.text();
  throw new Error(text.slice(0, 300) || `HTTP ${res.status}`);
}

document.addEventListener('DOMContentLoaded', () => {
    // DOM elements
    const initialSections = document.getElementById('initial-sections');
    const currentChatContainer = document.getElementById('current-chat-container');
    const chatMessagesDisplay = document.getElementById('chat-messages-display');
    const userQuestionTextarea = document.getElementById('userQuestion'); // For initial section
    const submitBtn = document.getElementById('submitBtn'); // For initial section
    const chatInput = document.getElementById('chat-input'); // For current chat section
    const sendButton = document.getElementById('send-button'); // For current chat section
    const newChatSidebarButton = document.getElementById('start-new-conversation-sidebar');
    const spinner = document.getElementById('spinner');
    const fileSpinner = document.getElementById('fileSpinner');
    const chatList = document.getElementById('chat-list'); // Ensure this element exists in your HTML

    // File Upload Elements
    const dragAndDropArea = document.getElementById('drag-and-drop-area');
    const fileInput = document.getElementById('file-input');
    const fileQuestionInput = document.getElementById('file-question-input');
    const fileSubmitBtn = document.getElementById('file-submit-btn');
    const fileChosenSpan = document.getElementById('file-chosen');
    const clearBtn = document.getElementById('clear-btn');

    // Constants
    const MAX_FILE_SIZE_MB = 1024; // 1 GB limit
    const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

    // State
    let currentSessionId = localStorage.getItem('currentSessionId') || 'default';
    let currentFile = null;

    // Helper to scroll chat to bottom
    const scrollChatToBottom = () => {
        chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight;
    };

    // --- UI Show/Hide helpers ---
    const showChatArea = () => {
        initialSections.style.display = 'none';
        currentChatContainer.style.display = 'block';
    };

    const showInitialSections = () => {
        initialSections.style.display = 'block';
        currentChatContainer.style.display = 'none';
    };

    // --- Message rendering ---
    const welcomeMessageContent = `<p>👋 Привет! Я ваш ИИ-юрист. Задайте вопрос или загрузите документ.</p>`;
    const addMessage = (content, type = 'ai-response') => {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('chat-bubble', type);
        messageDiv.innerHTML = content;
        chatMessagesDisplay.appendChild(messageDiv);
        scrollChatToBottom();
    };

    // --- Fetch Chat History ---
    async function loadChatHistory(sessionId) {
        chatMessagesDisplay.innerHTML = ''; // Clear display before loading new history
        spinner.style.display = 'block'; // Show spinner while loading
        try {
            const res = await apiFetch(`/get-history?session_id=${encodeURIComponent(sessionId)}`);
            if (!res.ok) {
                const errorData = await safeJson(res);
                throw new Error(errorData.error || `Ошибка HTTP: ${res.status}`);
            }
            const data = await safeJson(res);
            spinner.style.display = 'none';

            if (data.history && data.history.length > 0) {
                data.history.forEach(msg => {
                    addMessage(`<p>${msg.content}</p>`, msg.role === 'user' ? 'user-query' : 'ai-response');
                });
            } else {
                addMessage(welcomeMessageContent, 'ai-response'); // Consistent welcome for empty history
            }
        } catch (error) {
            spinner.style.display = 'none';
            console.error('Ошибка загрузки истории:', error);
            addMessage(`<p class="error-message">Ошибка загрузки истории: ${error.message || 'Неизвестная ошибка'}</p>`, 'ai-response');
        }
    }

    // --- Load chat sessions for sidebar ---
    async function loadChatSessions() {
        chatList.innerHTML = '<p>Загрузка истории...</p>';
        try {
            const res = await apiFetch('/get-all-sessions-summary');
            if (!res.ok) {
                const errorData = await safeJson(res);
                throw new Error(errorData.error || `Ошибка HTTP: ${res.status}`);
            }
            const data = await safeJson(res);
            chatList.innerHTML = ''; // Clear existing list

            if (data.sessions && data.sessions.length > 0) {
                // Newest first (id looks like sess_TIMESTAMP)
                data.sessions.sort((a, b) => b.id.localeCompare(a.id));
                data.sessions.forEach(session => {
                    const li = document.createElement('li');
                    li.textContent = session.title || 'Без названия';
                    li.dataset.sessionId = session.id;
                    li.addEventListener('click', () => {
                        currentSessionId = session.id;
                        localStorage.setItem('currentSessionId', currentSessionId);
                        highlightChatButton(session.id);
                        loadChatHistory(session.id);
                        showChatArea();
                    });
                    chatList.appendChild(li);
                });
            } else {
                chatList.innerHTML = '<p>Пока нет сохранённых чатов</p>';
            }
        } catch (error) {
            chatList.innerHTML = '<p class="error-message">Ошибка загрузки списка чатов</p>';
            console.error('Ошибка загрузки списка чатов:', error);
        }
    }

    const highlightChatButton = (sessionId) => {
        document.querySelectorAll('#chat-list li').forEach(li => {
            li.classList.toggle('active', li.dataset.sessionId === sessionId);
        });
    };

    // --- New Chat logic ---
    const startNewChat = () => {
        currentSessionId = 'default';
        localStorage.setItem('currentSessionId', currentSessionId);
        highlightChatButton(null);
        showInitialSections(); // Back to initial sections
        currentChatContainer.style.display = 'none';
        chatMessagesDisplay.innerHTML = ''; // Clear chat history display
        userQuestionTextarea.value = '';
        chatInput.value = ''; // Clear persistent chat input
        fileQuestionInput.value = '';
        clearFileSelection();
    };

    // --- Sending Text Messages ---
    const sendTextMessage = async (question) => {
        if (!question.trim()) return;
        showChatArea();
        addMessage(`<p>${question}</p>`, 'user-query');
        userQuestionTextarea.value = ''; // Clear initial section input
        chatInput.value = ''; // Clear current chat section input
        spinner.style.display = 'block';
        scrollChatToBottom();

        try {
            const res = await apiFetch('/ask', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    question: question,
                    session_id: currentSessionId
                })
            });
            const aiResponse = await safeJson(res);
            spinner.style.display = 'none';

            if (aiResponse.error) {
                addMessage(`<p class="error-message">${aiResponse.error}</p>`, 'ai-response');
            } else {
                addMessage(`<p>${aiResponse.answer}</p>`, 'ai-response');
                currentSessionId = aiResponse.session_id; // Ensure we keep latest
                localStorage.setItem('currentSessionId', currentSessionId);
                loadChatSessions(); // Refresh sidebar
            }
        } catch (error) {
            spinner.style.display = 'none';
            console.error('Ошибка отправки вопроса:', error);
            addMessage(`<p class="error-message">Ошибка: ${error.message || 'Неизвестная ошибка'}</p>`, 'ai-response');
        }
    };

    // --- Accordion behaviour in initial sections ---
    document.querySelectorAll('.accordion').forEach(acc => {
        acc.addEventListener('click', function() {
            this.classList.toggle('active');
            const content = this.nextElementSibling;
            const icon = this.querySelector('i');
            if (content.style.maxHeight) {
                content.style.maxHeight = null;
                icon.classList.replace('fa-chevron-up', 'fa-chevron-down');
            } else {
                content.style.maxHeight = content.scrollHeight + "px";
                icon.classList.replace('fa-chevron-down', 'fa-chevron-up');
            }
        });
    });

    // --- File Upload Logic ---
    dragAndDropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        dragAndDropArea.classList.add('highlight');
    });
    dragAndDropArea.addEventListener('dragleave', () => {
        dragAndDropArea.classList.remove('highlight');
    });
    dragAndDropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dragAndDropArea.classList.remove('highlight');
        if (e.dataTransfer.files.length > 0) {
            handleFileSelection(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelection(e.target.files[0]);
        }
    });

    const handleFileSelection = (file) => {
        if (file.size > MAX_FILE_SIZE_BYTES) {
            alert(`Ошибка: Размер файла превышает ${MAX_FILE_SIZE_MB} МБ. Пожалуйста, выберите файл поменьше.`);
            clearFileSelection();
            return;
        }

        currentFile = file;
        fileChosenSpan.textContent = file.name;
        fileSubmitBtn.disabled = false;
        clearBtn.disabled = false;
        fileQuestionInput.focus();
    };

    const clearFileSelection = () => {
        currentFile = null;
        fileInput.value = '';
        fileChosenSpan.textContent = 'Файл не выбран';
        fileSubmitBtn.disabled = true;
        clearBtn.disabled = true;
    };

    clearBtn.addEventListener('click', clearFileSelection);

    fileSubmitBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        if (!currentFile) return;
        showChatArea();
        const fileQuestion = fileQuestionInput.value.trim();
        const userFileMessage = `<p><strong>Документ загружен:</strong> ${currentFile.name}</p>` +
                                 (fileQuestion ? `<p><strong>Мой вопрос:</strong> ${fileQuestion}</p>` : '');
        addMessage(userFileMessage, 'user-query');
        fileSpinner.style.display = 'block';
        scrollChatToBottom();

        try {
            const formData = new FormData();
            formData.append('file', currentFile);
            formData.append('question', fileQuestion);
            formData.append('session_id', currentSessionId);

            const res = await apiFetch('/upload-document', {
                method: 'POST',
                body: formData
            });
            const aiFileResponse = await safeJson(res);
            fileSpinner.style.display = 'none';

            if (aiFileResponse.error) {
                addMessage(`<p class="error-message">${aiFileResponse.error}</p>`, 'ai-response');
            } else {
                addMessage(`<p>${aiFileResponse.answer}</p>`, 'ai-response');
                currentSessionId = aiFileResponse.session_id;
                localStorage.setItem('currentSessionId', currentSessionId);
                loadChatSessions();
            }
            clearFileSelection();
        } catch (error) {
            fileSpinner.style.display = 'none';
            console.error('Error uploading document:', error);
            addMessage(`<p class="error-message">Произошла ошибка: ${error.message || 'Неизвестная ошибка'}. Пожалуйста, попробуйте еще раз.</p>`, 'ai-response');
            clearFileSelection();
        }
    });

    // --- Event Listeners ---
    submitBtn.addEventListener('click', (e) => {
        e.preventDefault();
        sendTextMessage(userQuestionTextarea.value);
    });

    sendButton.addEventListener('click', (e) => {
        e.preventDefault();
        sendTextMessage(chatInput.value);
    });

    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendTextMessage(chatInput.value);
        }
    });

    userQuestionTextarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendTextMessage(userQuestionTextarea.value);
        }
    });

    newChatSidebarButton.addEventListener('click', startNewChat);

    // Initial load
    showInitialSections(); // Start with initial sections visible
    loadChatSessions().then(() => {
        if (currentSessionId && currentSessionId !== 'default' &&
            document.querySelector(`[data-session-id="${currentSessionId}"]`)) {
            loadChatHistory(currentSessionId);
            showChatArea(); // Show chat area if history is loaded
        } else {
            addMessage(welcomeMessageContent, 'ai-response');
        }
    });
});
