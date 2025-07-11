// frontend/script.js (Версия 4.4 - Улучшенный UX, строгая юрисдикция РК, приоритет уточняющих вопросов)

document.addEventListener('DOMContentLoaded', () => {
    // --- SESSION ID LOGIC ---
    const SESSION_KEY = "kazlaw_current_session_id";
    function generateSessionId() {
        return Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
    }
    function getSessionId() {
        let id = localStorage.getItem(SESSION_KEY);
        if (!id) {
            id = generateSessionId();
            localStorage.setItem(SESSION_KEY, id);
        }
        return id;
    }
    function setSessionId(id) {
        if (id) {
            localStorage.setItem(SESSION_KEY, id);
            currentSessionId = id; // Обновляем глобальную переменную
        }
    }

    // --- DOM Elements ---
    const chatForm = document.getElementById('chat-form');
    const userQuestionInput = document.getElementById('userQuestion');
    const submitBtn = document.getElementById('submitBtn');
    const currentChatArea = document.getElementById('current-chat-area'); // Главная область для текущего чата
    const spinner = document.getElementById('spinner');

    const fileForm = document.getElementById('file-form');
    const fileInput = document.getElementById('fileInput');
    const fileChosen = document.getElementById('file-chosen');
    const clearBtn = document.getElementById('clearBtn');
    const analyzeBtn = document.getElementById('fileSubmitBtn');
    const fileSpinner = document.getElementById('fileSpinner');
    const fileQuestionInput = document.getElementById('fileQuestion');
    const dragAndDropArea = document.getElementById('drag-and-drop-area');

    // Новые элементы для истории чатов и динамического отображения
    const chatList = document.getElementById('chat-list');
    const startNewConversationSidebarBtn = document.getElementById('start-new-conversation-sidebar');
    const initialSections = document.getElementById('initial-sections'); // Контейнер для "О проекте" и "Задайте вопрос"

    let currentSessionId = getSessionId(); // Инициализируем текущий ID сессии при загрузке

    const MAX_FILE_SIZE = 1024 * 1024 * 1024; // 1 GB

    // --- INITIAL LOAD ---
    // Загружаем и отображаем историю чатов в сайдбаре при загрузке страницы
    loadAndDisplayAllSessionsSummary();

    // При первой загрузке страницы, проверяем, есть ли история для текущей сессии
    // и либо показываем ее, либо начальные секции
    async function initializeDisplay() {
        try {
            const response = await fetch(`https://ai-lawyer.up.railway.app/get-history?session_id=${currentSessionId}`);
            const data = await response.json();
            if (data.history && data.history.length > 0) {
                loadSpecificConversation(currentSessionId); // Если есть история, загружаем ее
            } else {
                showInitialSections(); // Иначе показываем начальные секции
            }
        } catch (error) {
            console.error("Ошибка при проверке истории сессии:", error);
            showInitialSections(); // В случае ошибки также показываем начальные секции
        }
    }
    initializeDisplay();


    // --- CHAT LOGIC ---
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = userQuestionInput.value.trim();
        if (!question) return;

        hideInitialSections(); // Скрываем начальные секции
        currentChatArea.style.display = 'flex'; // Показываем область чата (flex, т.к. внутри элементы flex)
        currentChatArea.innerHTML = ''; // Очищаем область чата для нового запроса

        // Добавляем вопрос пользователя в currentChatArea сразу
        addMessageToChatArea('user', question);
        userQuestionInput.value = ''; // Очищаем поле ввода
        submitBtn.disabled = true;
        userQuestionInput.disabled = true;
        spinner.style.display = 'block'; // Показываем спиннер

        let fullAiText = "";
        
        try {
            const streamResponse = await fetch('https://ai-lawyer.up.railway.app/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Session-Id': currentSessionId
                },
                body: JSON.stringify({ question, session_id: currentSessionId }),
            });

            if (!streamResponse.ok) {
                const errorText = await streamResponse.text();
                throw new Error(`Ошибка сервера при стриминге: ${streamResponse.status} - ${errorText}`);
            }

            const reader = streamResponse.body.getReader();
            const decoder = new TextDecoder('utf-8');

            spinner.style.display = 'none'; // Скрываем спиннер после начала стриминга
            
            // Создаем div для ответа ИИ, чтобы потом обновить его HTML
            const aiMessageDiv = document.createElement('div');
            aiMessageDiv.classList.add('ai-message');
            currentChatArea.appendChild(aiMessageDiv);
            currentChatArea.scrollTop = currentChatArea.scrollHeight; // Прокручиваем к последнему сообщению

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const textChunk = decoder.decode(value, { stream: true });
                fullAiText += textChunk;
                aiMessageDiv.textContent = fullAiText; // Обновляем текст в "сыром" виде
                currentChatArea.scrollTop = currentChatArea.scrollHeight; // Прокручиваем при получении чанков
            }

            // Теперь отправляем полный текст на финальную обработку
            // Показываем спиннер форматирования
            aiMessageDiv.innerHTML = '<div id="spinner-final" style="text-align:center; padding: 20px;"><p>Форматирование и поиск статей...</p><div class="loader"></div></div>';
            currentChatArea.scrollTop = currentChatArea.scrollHeight;

            const processResponse = await fetch('https://ai-lawyer.up.railway.app/process-full-text', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Session-Id': currentSessionId
                },
                body: JSON.stringify({ question, full_ai_text: fullAiText, session_id: currentSessionId }),
            });

            if (!processResponse.ok) {
                const errorData = await processResponse.json();
                throw new Error(`Ошибка сервера при обработке: ${processResponse.status} - ${errorData.error || 'Неизвестная ошибка'}`);
            }
            const data = await processResponse.json();
            aiMessageDiv.innerHTML = data.html || ""; // Вставляем отформатированный HTML

            if (data.session_id) setSessionId(data.session_id);

        } catch (error) {
            spinner.style.display = 'none';
            addMessageToChatArea('ai', `<div class="ai-message error-message">🚫 Произошла критическая ошибка: ${error.message}</div>`);
        } finally {
            submitBtn.disabled = false;
            userQuestionInput.disabled = false;
            userQuestionInput.focus();
            loadAndDisplayAllSessionsSummary(); // Обновляем историю в сайдбаре после ответа
            currentChatArea.scrollTop = currentChatArea.scrollHeight; // Финальная прокрутка
        }
    });

    // --- DRAG & DROP FILE LOGIC ---
    let selectedFile = null; // Переменная для хранения выбранного файла

    function handleFile(file) {
        if (!file) return;
        if (file.size > MAX_FILE_SIZE) {
            alert("Максимальный размер файла – 1 ГБ");
            clearSelectedFile();
            return;
        }
        const allowedExtensions = ['.pdf', '.docx', '.doc', '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.gif'];
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        if (!allowedExtensions.includes(fileExtension)) {
            alert(`Файл '${file.name}' имеет неподдерживаемый формат. Поддерживаются PDF, DOCX, DOC, и изображения.`);
            clearSelectedFile();
            return;
        }

        fileChosen.textContent = file.name;
        clearBtn.disabled = false;
        analyzeBtn.disabled = false;
        selectedFile = file;
    }

    function clearSelectedFile() {
        selectedFile = null;
        fileInput.value = "";
        fileChosen.textContent = "Файл не выбран";
        clearBtn.disabled = true;
        analyzeBtn.disabled = true;
        fileQuestionInput.value = ""; // Очищаем вопрос к файлу
    }

    ["dragenter", "dragover"].forEach(evt =>
        dragAndDropArea.addEventListener(evt, e => { e.preventDefault(); dragAndDropArea.classList.add("highlight"); })
    );
    ["dragleave", "drop"].forEach(evt =>
        dragAndDropArea.addEventListener(evt, e => {
            e.preventDefault();
            dragAndDropArea.classList.remove("highlight");
            if (evt === "drop") handleFile(e.dataTransfer.files[0]);
        })
    );

    fileInput.addEventListener("change", e => handleFile(e.target.files[0]));
    clearBtn.addEventListener("click", clearSelectedFile);

    // --- SUBMIT FILE ANALYSIS ---
    fileForm.addEventListener("submit", async e => {
        e.preventDefault();
        if (!selectedFile) return;

        hideInitialSections(); // Скрываем начальные секции
        currentChatArea.style.display = 'flex'; // Показываем область чата
        currentChatArea.innerHTML = ''; // Очищаем область чата для нового запроса

        fileSpinner.style.display = "block";
        analyzeBtn.disabled = true;
        fileInput.disabled = true;
        fileQuestionInput.disabled = true;

        const fileQuestion = fileQuestionInput.value.trim();

        // Добавляем информацию о загрузке файла в currentChatArea сразу
        addMessageToChatArea('user', `Загружен файл: ${selectedFile.name}${fileQuestion ? '. Вопрос: ' + fileQuestion : ''}`);
        currentChatArea.scrollTop = currentChatArea.scrollHeight;

        try {
            const formData = new FormData();
            formData.append("file", selectedFile);
            if (fileQuestion) formData.append("question", fileQuestion);
            formData.append("session_id", currentSessionId);

            const res = await fetch("https://ai-lawyer.up.railway.app/analyze-file", {
                method: "POST",
                body: formData,
            });

            if (!res.ok) {
                let errorData;
                try { errorData = await res.json(); } catch { errorData = {error: 'Неизвестная ошибка сервера'}; }
                throw new Error(errorData?.error || `Ошибка сервера: ${res.status}`);
            }
            const data = await res.json();
            if (!data.analysis || typeof data.analysis !== 'string') {
                throw new Error(`Ответ ИИ не содержит текст анализа.`);
            }
            if (data.session_id) setSessionId(data.session_id);

            // Создаем div для ответа ИИ
            const aiMessageDiv = document.createElement('div');
            aiMessageDiv.classList.add('ai-message');
            currentChatArea.appendChild(aiMessageDiv);
            aiMessageDiv.innerHTML = '<div id="spinner-final" style="text-align:center; padding: 20px;"><p>Форматирование и поиск статей...</p><div class="loader"></div></div>';
            currentChatArea.scrollTop = currentChatArea.scrollHeight;


            // Финальная обработка (поиск статей)
            const htmlRes = await fetch("https://ai-lawyer.up.railway.app/process-full-text", {
                method: "POST",
                headers: {
                    'Content-Type': 'application/json',
                    'Session-Id': currentSessionId
                },
                body: JSON.stringify({
                    question: fileQuestion || selectedFile.name,
                    full_ai_text: data.analysis,
                    session_id: currentSessionId
                })
            });

            const final = await htmlRes.json();
            aiMessageDiv.innerHTML = final.html || "";

            if (final.session_id) setSessionId(final.session_id);

        } catch (err) {
            addMessageToChatArea('ai', `<div class="ai-message error-message">🚫 Ошибка анализа файла: ${err.message}</div>`);
        } finally {
            fileSpinner.style.display = "none";
            analyzeBtn.disabled = false;
            fileInput.disabled = false;
            fileQuestionInput.disabled = false;
            clearSelectedFile();
            loadAndDisplayAllSessionsSummary(); // Обновляем историю после ответа
            currentChatArea.scrollTop = currentChatArea.scrollHeight;
        }
    });

    // --- КНОПКА "НОВЫЙ ЧАТ" (в сайдбаре) ---
    startNewConversationSidebarBtn.addEventListener("click", async () => {
        await startNewConversation();
    });

    // --- Функция для запуска нового диалога ---
    async function startNewConversation() {
        // Очищаем историю текущей сессии на сервере
        try {
            await fetch("https://ai-lawyer.up.railway.app/clear-history", {
                method: "POST",
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: currentSessionId })
            });
        } catch (error) {
            console.error("Ошибка при очистке истории на сервере:", error);
        }

        // Генерируем новый session_id и очищаем все на клиенте
        setSessionId(generateSessionId());
        currentChatArea.innerHTML = ''; // Очищаем основную область ответов
        userQuestionInput.value = '';
        userQuestionInput.disabled = false;
        fileQuestionInput.value = '';
        clearSelectedFile();
        submitBtn.disabled = false;
        analyzeBtn.disabled = true;
        if (spinner) spinner.style.display = 'none';
        if (fileSpinner) fileSpinner.style.display = 'none';
        userQuestionInput.focus();
        loadAndDisplayAllSessionsSummary(); // Обновляем список чатов в сайдбаре
        updateActiveChatInList(currentSessionId); // Устанавливаем новый чат как активный
        showInitialSections(); // Показываем начальные секции
    }

    // --- Функция для добавления сообщений в currentChatArea ---
    function addMessageToChatArea(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add(role === 'user' ? 'user-message' : 'ai-message');
        messageDiv.innerHTML = role === 'user' ? `<p>${content}</p>` : content; 
        currentChatArea.appendChild(messageDiv);
        currentChatArea.scrollTop = currentChatArea.scrollHeight; // Прокручиваем вниз
    }

    // --- Загрузка и отображение сводки всех сессий для сайдбара ---
    async function loadAndDisplayAllSessionsSummary() {
        chatList.innerHTML = '<p>Загрузка истории...</p>';
        try {
            const response = await fetch('https://ai-lawyer.up.railway.app/get-all-sessions-summary');
            if (!response.ok) {
                throw new Error(`Ошибка загрузки сводки сессий: ${response.status}`);
            }
            const data = await response.json();
            const sessions = data.sessions;

            chatList.innerHTML = '';
            if (sessions && sessions.length > 0) {
                sessions.forEach(session => {
                    const li = document.createElement('li');
                    const button = document.createElement('button');
                    button.textContent = session.title;
                    button.dataset.sessionId = session.id;
                    button.addEventListener('click', () => loadSpecificConversation(session.id));
                    li.appendChild(button);
                    chatList.appendChild(li);
                });
            } else {
                chatList.innerHTML = '<p>Пока нет истории диалогов.</p>';
            }
            updateActiveChatInList(currentSessionId); // Выделяем активный чат
        } catch (error) {
            console.error("Ошибка при загрузке сводки сессий:", error);
            chatList.innerHTML = `<p style="color:red;">Не удалось загрузить историю: ${error.message}</p>`;
        }
    }

    // --- Функция для загрузки конкретного диалога в область чата ---
    async function loadSpecificConversation(sessionIdToLoad) {
        setSessionId(sessionIdToLoad);
        updateActiveChatInList(sessionIdToLoad);

        hideInitialSections(); // Скрываем начальные секции
        currentChatArea.style.display = 'flex'; // Показываем область чата
        currentChatArea.innerHTML = ''; // Очищаем текущий чат

        spinner.style.display = 'block';

        try {
            const response = await fetch(`https://ai-lawyer.up.railway.app/get-history?session_id=${sessionIdToLoad}`);
            if (!response.ok) {
                throw new Error(`Ошибка загрузки конкретного диалога: ${response.status}`);
            }
            const data = await response.json();
            const history = data.history;

            if (history && history.length > 0) {
                for (const msg of history) {
                    if (msg.role === 'user') {
                        addMessageToChatArea('user', msg.content);
                    } else if (msg.role === 'model') {
                        // Для ответов модели повторно вызываем process-full-text, чтобы получить форматированный HTML
                        const processResponse = await fetch('https://ai-lawyer.up.railway.app/process-full-text', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                question: msg.content.substring(0, 50), // Используем часть ответа как "вопрос" для поиска статей
                                full_ai_text: msg.content,
                                session_id: sessionIdToLoad
                            }),
                        });
                        const processedData = await processResponse.json();
                        addMessageToChatArea('ai', processedData.html || processedData.error || "Ошибка загрузки ответа.");
                    }
                }
            } else {
                addMessageToChatArea('ai', 'История для этой сессии пуста. Задайте свой первый вопрос!');
            }
            currentChatArea.scrollTop = currentChatArea.scrollHeight; // Прокручиваем к последнему ответу
        } catch (error) {
            console.error("Ошибка при загрузке конкретного диалога:", error);
            addMessageToChatArea('ai', `<div class="ai-message error-message">🚫 Не удалось загрузить диалог: ${error.message}</div>`);
        } finally {
            spinner.style.display = 'none';
        }
    }

    // --- Функция для выделения активного чата в сайдбаре ---
    function updateActiveChatInList(activeId) {
        const chatButtons = chatList.querySelectorAll('button');
        chatButtons.forEach(button => {
            if (button.dataset.sessionId === activeId) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
    }

    // Вспомогательные функции для управления видимостью секций
    function showInitialSections() {
        initialSections.style.display = 'flex';
        currentChatArea.style.display = 'none';
    }

    function hideInitialSections() {
        initialSections.style.display = 'none';
    }
});
