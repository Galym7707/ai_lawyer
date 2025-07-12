document.addEventListener('DOMContentLoaded', () => {
    // DOM elements
    const initialSections = document.getElementById('initial-sections');
    const currentChatContainer = document.getElementById('current-chat-container');
    const chatMessagesDisplay = document.getElementById('chat-messages-display');
    const userQuestionTextarea = document.getElementById('userQuestion');
    const submitBtn = document.getElementById('submitBtn');
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');
    const newChatSidebarButton = document.getElementById('start-new-conversation-sidebar');
    const spinner = document.getElementById('spinner');
    const fileSpinner = document.getElementById('fileSpinner');
    const chatList = document.getElementById('chat-list');

    // File Upload Elements
    const dragAndDropArea = document.getElementById('drag-and-drop-area');
    const fileInput = document.getElementById('fileInput');
    const fileChosenSpan = document.getElementById('file-chosen');
    const fileQuestionInput = document.getElementById('fileQuestion');
    const fileSubmitBtn = document.getElementById('fileSubmitBtn');
    const clearBtn = document.getElementById('clearBtn');

    let currentFile = null;
    let currentSessionId = getSessionId();

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
    }
    function startNewSession() {
        setCurrentSessionId('sess_' + Math.random().toString(36).substr(2, 10));
        showInitialSections();
        loadChatSessions();
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
        chatMessagesDisplay.innerHTML = '';
        spinner.style.display = 'block';
        try {
            const res = await fetch(`/get-history?session_id=${encodeURIComponent(sessionId)}`);
            const data = await res.json();
            spinner.style.display = 'none';
            if (data.history && data.history.length) {
                data.history.forEach(msg => {
                    addMessage(`<p>${msg.content}</p>`, msg.role === 'user' ? 'user-query' : 'ai-response');
                });
            } else {
                addMessage('<p>Начните диалог с ИИ-юристом!</p>', 'ai-response');
            }
        } catch {
            spinner.style.display = 'none';
            addMessage('<p class="error-message">Ошибка загрузки истории.</p>', 'ai-response');
        }
    }

    // --- Fetch Chat List (Sidebar) ---
    async function loadChatSessions() {
        chatList.innerHTML = '<p>Загрузка истории...</p>';
        try {
            const res = await fetch('/get-all-sessions-summary');
            const data = await res.json();
            chatList.innerHTML = '';
            if (data.sessions && data.sessions.length) {
                data.sessions.forEach(session => {
                    const li = document.createElement('li');
                    const btn = document.createElement('button');
                    btn.textContent = session.title || 'Новый чат';
                    btn.onclick = () => {
                        setCurrentSessionId(session.id);
                        showChatArea();
                        loadChatHistory(session.id);
                        highlightChatButton(session.id);
                    };
                    li.appendChild(btn);
                    if (session.id === currentSessionId) btn.classList.add('active');
                    chatList.appendChild(li);
                });
            } else {
                chatList.innerHTML = '<li><span>Нет чатов</span></li>';
            }
        } catch {
            chatList.innerHTML = '<li><span>Ошибка загрузки</span></li>';
        }
    }
    function highlightChatButton(sessionId) {
        document.querySelectorAll('#chat-list button').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('#chat-list li').forEach(li => {
            if (li.querySelector('button') && li.querySelector('button').onclick.toString().includes(sessionId)) {
                li.querySelector('button').classList.add('active');
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
        // Clear chat history when starting a new chat
        chatMessagesDisplay.innerHTML = '';
        userQuestionTextarea.value = '';
        fileQuestionInput.value = '';
        clearFileSelection();
    };

    // --- Sending Text Messages ---
    const sendTextMessage = async (question) => {
        if (!question.trim()) return;
        showChatArea();
        addMessage(`<p>${question}</p>`, 'user-query');
        userQuestionTextarea.value = '';
        chatInput.value = '';
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
            loadChatSessions();
        } catch (error) {
            spinner.style.display = 'none';
            addMessage('<p class="error-message">Произошла ошибка при получении ответа. Пожалуйста, попробуйте еще раз.</p>', 'ai-response');
        }
    };

    // --- Format AI Response with Articles ---
    const formatAiResponseWithArticles = (responseText, articles) => {
        let html = `<div>${responseText}</div>`;
        if (articles && articles.length > 0) {
            html += `<div class="laws-container">
                        <h3 class="laws-header"><i class="fas fa-gavel"></i> Релевантные статьи законодательства РК</h3>
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
            loadChatSessions();
        } catch (error) {
            fileSpinner.style.display = 'none';
            addMessage('<p class="error-message">Произошла ошибка при анализе документа. Пожалуйста, попробуйте еще раз.</p>', 'ai-response');
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
    showInitialSections();
    loadChatSessions();
    // Если есть текущая сессия — можно автозагрузить историю
    // loadChatHistory(currentSessionId);
});
