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
    const fileInput = document.getElementById('fileInput');
    const fileChosenSpan = document.getElementById('file-chosen');
    const fileQuestionInput = document.getElementById('fileQuestion');
    const fileSubmitBtn = document.getElementById('fileSubmitBtn');
    const clearBtn = document.getElementById('clearBtn');

    let currentFile = null;
    let currentSessionId; // Declare, but initialize below for first-time logic

    // Set file input accept attribute, removing .doc as per recommendation
    fileInput.setAttribute('accept', '.pdf, .docx, .txt, .jpg, .jpeg, .png, .webp, .bmp, .tiff, .gif');

    // Define a maximum file size for client-side validation (e.g., 200 MB)
    const MAX_FILE_SIZE_MB = 200;
    const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

    // --- Session Management ---
    function getSessionId() {
        let sid = localStorage.getItem('kaz_legal_session_id');
        if (!sid) {
            sid = 'sess_' + Math.random().toString(36).substr(2, 10);
            localStorage.setItem('kaz_legal_session_id', sid);
        }
        return sid;
    }

    function setCurrentSessionId(sid) {
        currentSessionId = sid;
        localStorage.setItem('kaz_legal_session_id', sid);
        highlightChatButton(sid); // Highlight the button when session changes
    }

    const welcomeMessageContent = '<p>Добро пожаловать в ИИ-юрист! Задайте свой вопрос по законодательству Казахстана или загрузите документ для анализа.</p>';

    function startNewSession() {
        setCurrentSessionId('sess_' + Math.random().toString(36).substr(2, 10)); // Generate new ID
        showInitialSections(); // Show initial sections for a fresh start
        chatMessagesDisplay.innerHTML = ''; // Clear current chat display
        userQuestionTextarea.value = '';
        fileQuestionInput.value = '';
        clearFileSelection();
        loadChatSessions(); // Reload sessions to show the new one
        addMessage(welcomeMessageContent, 'ai-response'); // Initial greeting for new chat
    }

    // --- Chat Message Rendering ---
    const addMessage = (content, type) => {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('chat-bubble', type);
        messageDiv.innerHTML = content;
        chatMessagesDisplay.appendChild(messageDiv);
        chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight;
    };

    // --- Fetch Chat History ---
    async function loadChatHistory(sessionId) {
        chatMessagesDisplay.innerHTML = ''; // Clear display before loading new history
        spinner.style.display = 'block'; // Show spinner while loading
        try {
            const res = await fetch(`/get-history?session_id=${encodeURIComponent(sessionId)}`);
            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.error || `Ошибка HTTP: ${res.status}`);
            }
            const data = await res.json();
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

    // --- Fetch Chat List (Sidebar) ---
    async function loadChatSessions() {
        chatList.innerHTML = '<p>Загрузка истории...</p>';
        try {
            const res = await fetch('/get-all-sessions-summary');
            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.error || `Ошибка HTTP: ${res.status}`);
            }
            const data = await res.json();
            chatList.innerHTML = ''; // Clear existing list

            if (data.sessions && data.sessions.length > 0) {
                data.sessions.sort((a, b) => b.id.localeCompare(a.id)); // Sort to show newer chats first (assuming 'sess_TIMESTAMP' format)
                data.sessions.forEach(session => {
                    const li = document.createElement('li');
                    const btn = document.createElement('button');
                    btn.textContent = session.title || 'Новый чат';
                    btn.classList.add('chat-session-btn');
                    btn.setAttribute('data-session-id', session.id); // Store session ID on button
                    btn.onclick = () => {
                        if (currentSessionId !== session.id) { // Only load if different session
                            setCurrentSessionId(session.id);
                            showChatArea();
                            loadChatHistory(session.id);
                        }
                    };
                    li.appendChild(btn);
                    chatList.appendChild(li);
                });
                highlightChatButton(currentSessionId); // Ensure the current session is highlighted
            } else {
                chatList.innerHTML = '<li><span>Нет чатов</span></li>';
            }
        } catch (error) {
            console.error('Ошибка загрузки списка чатов:', error);
            chatList.innerHTML = `<li><span>Ошибка загрузки: ${error.message || 'Неизвестная ошибка'}</span></li>`;
        }
    }

    function highlightChatButton(sessionId) {
        document.querySelectorAll('#chat-list button').forEach(b => {
            b.classList.remove('active');
            if (b.getAttribute('data-session-id') === sessionId) {
                b.classList.add('active');
            }
        });
    }

    // --- Chat Area State ---
    const showChatArea = () => {
        initialSections.style.display = 'none';
        currentChatContainer.style.display = 'flex';
        chatInput.focus();
    };
    const showInitialSections = () => {
        initialSections.style.display = 'flex';
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
        chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight;

        try {
            const res = await fetch('/ask', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    question: question,
                    session_id: currentSessionId
                })
            });
            const aiResponse = await res.json();
            spinner.style.display = 'none';

            if (aiResponse.error) {
                addMessage(`<p class="error-message">${aiResponse.error}</p>`, 'ai-response');
            } else if (aiResponse.articles && aiResponse.articles.length > 0) {
                addMessage(formatAiResponseWithArticles(aiResponse.response, aiResponse.articles), 'ai-response');
            } else {
                addMessage(`<p>${aiResponse.response}</p>`, 'ai-response');
            }
            // Reload sessions to update titles/order if necessary.
            // loadChatSessions() already calls highlightChatButton, so no need for a redundant call here.
            loadChatSessions();
        } catch (error) {
            spinner.style.display = 'none';
            console.error('Error sending text message:', error);
            addMessage(`<p class="error-message">Произошла ошибка при получении ответа: ${error.message || 'Неизвестная ошибка'}. Пожалуйста, попробуйте еще раз.</p>`, 'ai-response');
        }
    };

    // --- Format AI Response with Articles ---
    const formatAiResponseWithArticles = (responseText, articles) => {
        let html = `<div>${responseText}</div>`;
        if (articles && articles.length > 0) {
            html += `<div class="laws-container">
                        <h3 class="laws-header"><i class="fas fa-gavel"></i> Релевантные статьи законодательства РК <span class="article-count">(Только законы РК)</span></h3>
                        <div class="article-accordion">`;
            articles.forEach((article, index) => {
                html += `
                    <div class="accordion-item">
                        <div class="accordion-header" onclick="toggleAccordion(this)">
                            <span class="card-title">${index + 1}. ${article.title}</span>
                            <i class="fas fa-chevron-down accordion-icon"></i>
                        </div>
                        <div class="accordion-content">
                            <p class="card-body-text">${article.text}</p>
                            <div class="card-footer">
                                <span class="card-source">Источник: ${article.source}</span>
                                <a href="${article.link}" class="card-link" target="_blank">Читать полностью <i class="fas fa-external-link-alt"></i></a>
                            </div>
                        </div>
                    </div>`;
            });
            html += `</div></div>`;
        }
        return html;
    };

    // Accordion toggling
    window.toggleAccordion = (element) => {
        const item = element.closest('.accordion-item');
        const content = item.querySelector('.accordion-content');
        const icon = element.querySelector('.accordion-icon');
        item.classList.toggle('active');
        if (item.classList.contains('active')) {
            content.style.maxHeight = content.scrollHeight + "px";
            icon.classList.replace('fa-chevron-down', 'fa-chevron-up');
        } else {
            content.style.maxHeight = "0";
            icon.classList.replace('fa-chevron-up', 'fa-chevron-down');
        }
    };

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
        fileQuestionInput.value = '';
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
        chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight;

        try {
            const formData = new FormData();
            formData.append('file', currentFile);
            formData.append('question', fileQuestion);
            formData.append('session_id', currentSessionId);

            const res = await fetch('/upload-document', {
                method: 'POST',
                body: formData
            });
            const aiFileResponse = await res.json();
            fileSpinner.style.display = 'none';

            if (aiFileResponse.error) {
                addMessage(`<p class="error-message">${aiFileResponse.error}</p>`, 'ai-response');
            } else {
                addMessage(`<p>${aiFileResponse.response}</p>`, 'ai-response');
            }
            clearFileSelection();
            // Reload sessions to update titles/order if necessary.
            // loadChatSessions() already calls highlightChatButton, so no need for a redundant call here.
            loadChatSessions();
        } catch (error) {
            fileSpinner.style.display = 'none';
            console.error('Error uploading document:', error);
            addMessage(`<p class="error-message">Произошла ошибка при анализе документа: ${error.message || 'Неизвестная ошибка'}. Пожалуйста, попробуйте еще раз.</p>`, 'ai-response');
            clearFileSelection();
        }
    });

    // --- Event Listeners ---
    submitBtn.addEventListener('click', (e) => {
        e.preventDefault();
        sendTextMessage(userQuestionTextarea.value);
    });
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendTextMessage(chatInput.value);
        }
    });
    sendButton.addEventListener('click', () => {
        sendTextMessage(chatInput.value);
    });
    newChatSidebarButton.addEventListener('click', () => {
        startNewSession();
    });

    // --- Initialization ---
    // Initialize currentSessionId first
    currentSessionId = getSessionId();

    // Then load everything else
    showInitialSections(); // Start with initial sections visible
    loadChatSessions().then(() => {
        // After sessions are loaded, if there's a valid currentSessionId, load its history
        // And ensure a corresponding button for the session exists (meaning it was loaded successfully from backend)
        if (currentSessionId && currentSessionId !== 'default' && document.querySelector(`[data-session-id="${currentSessionId}"]`)) {
            loadChatHistory(currentSessionId);
            showChatArea(); // Show chat area if history is loaded
        } else {
            // If no existing session or it's 'default', treat as a new chat and show welcome message
            addMessage(welcomeMessageContent, 'ai-response');
        }
    });
});
