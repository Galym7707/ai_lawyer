// frontend/script.js (Версия 4.3 - История чатов, динамический сбор информации, улучшенный UX)

document.addEventListener('DOMContentLoaded', () => {
    // --- SESSION ID LOGIC ---
    const SESSION_KEY = "kazlaw_current_session_id"; // Изменил ключ для ясности
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
        if (id) { // Убедимся, что ID не пустой
            localStorage.setItem(SESSION_KEY, id);
            currentSessionId = id; // Обновляем глобальную переменную
        }
    }

    // --- DOM Elements ---
    const chatForm = document.getElementById('chat-form');
    const userQuestionInput = document.getElementById('userQuestion');
    const submitBtn = document.getElementById('submitBtn');
    const responseBox = document.getElementById('response'); // Основная область для текущего чата
    const spinner = document.getElementById('spinner');
    const newDialogBtn = document.getElementById('new-conversation'); // Кнопка "Новый диалог" в основной секции

    const fileForm = document.getElementById('file-form');
    const fileInput = document.getElementById('fileInput');
    const fileChosen = document.getElementById('file-chosen');
    const clearBtn = document.getElementById('clearBtn'); // Кнопка "Очистить файл"
    const analyzeBtn = document.getElementById('fileSubmitBtn');
    const fileSpinner = document.getElementById('fileSpinner');
    const fileQuestionInput = document.getElementById('fileQuestion');
    const dragAndDropArea = document.getElementById('drag-and-drop-area');

    // Новые элементы для истории чатов
    const chatList = document.getElementById('chat-list'); // Список в сайдбаре
    const startNewConversationSidebarBtn = document.getElementById('start-new-conversation-sidebar'); // Кнопка "Новый чат" в сайдбаре
    const conversationHistoryDisplay = document.getElementById('conversation-history-display'); // Область для просмотра старой истории

    let currentSessionId = getSessionId(); // Инициализируем текущий ID сессии при загрузке

    const MAX_FILE_SIZE = 1024 * 1024 * 1024; // 1 GB

    // --- INITIAL LOAD ---
    // Загружаем и отображаем историю чатов в сайдбаре при загрузке страницы
    loadAndDisplayAllSessionsSummary();

    // --- CHAT LOGIC ---
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = userQuestionInput.value.trim();
        if (!question) return;

        // Добавляем вопрос пользователя в responseBox сразу
        addMessageToResponseBox('user', question);
        userQuestionInput.value = ''; // Очищаем поле ввода
        submitBtn.disabled = true;
        userQuestionInput.disabled = true;
        spinner.style.display = 'block';
        
        let fullAiText = "";

        try {
            const streamResponse = await fetch('https://ai-lawyer.up.railway.app/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Session-Id': currentSessionId // Отправляем текущий session_id
                },
                body: JSON.stringify({ question, session_id: currentSessionId }),
            });

            if (!streamResponse.ok) {
                const errorText = await streamResponse.text();
                throw new Error(`Ошибка сервера при стриминге: ${streamResponse.status} - ${errorText}`);
            }

            const reader = streamResponse.body.getReader();
            const decoder = new TextDecoder('utf-8');

            spinner.style.display = 'none';
            
            // Создаем div для ответа ИИ, чтобы потом обновить его HTML
            const aiMessageDiv = document.createElement('div');
            aiMessageDiv.classList.add('ai-message');
            responseBox.appendChild(aiMessageDiv);
            responseBox.scrollTop = responseBox.scrollHeight; // Прокручиваем к последнему сообщению

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const textChunk = decoder.decode(value, { stream: true });
                fullAiText += textChunk;
                aiMessageDiv.textContent = fullAiText; // Обновляем текст в "сыром" виде
                responseBox.scrollTop = responseBox.scrollHeight; // Прокручиваем при получении чанков
            }

            // Теперь отправляем полный текст на финальную обработку
            aiMessageDiv.innerHTML = '<div id="spinner-final" style="text-align:center; padding: 20px;"><p>Форматирование и поиск статей...</p><div class="loader"></div></div>';
            responseBox.scrollTop = responseBox.scrollHeight; // Прокручиваем к спиннеру форматирования

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

            // Обновляем session_id, если сервер вернул новый (хотя обычно он не меняется в рамках сессии)
            if (data.session_id) setSessionId(data.session_id);

        } catch (error) {
            spinner.style.display = 'none';
            responseBox.innerHTML += `<div class="ai-message error-message">🚫 Произошла критическая ошибка: ${error.message}</div>`; // Добавляем ошибку, а не заменяем
        } finally {
            submitBtn.disabled = false;
            userQuestionInput.disabled = false;
            userQuestionInput.focus();
            loadAndDisplayAllSessionsSummary(); // Обновляем историю в сайдбаре после ответа
            responseBox.scrollTop = responseBox.scrollHeight; // Финальная прокрутка
        }
    });

    // --- DRAG & DROP FILE LOGIC ---
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

        fileSpinner.style.display = "block";
        analyzeBtn.disabled = true;
        fileInput.disabled = true;
        fileQuestionInput.disabled = true;

        const fileQuestion = fileQuestionInput.value.trim();

        // Добавляем информацию о загрузке файла в responseBox сразу
        addMessageToResponseBox('user', `Загружен файл: ${selectedFile.name}${fileQuestion ? '. Вопрос: ' + fileQuestion : ''}`);
        responseBox.scrollTop = responseBox.scrollHeight;

        try {
            const formData = new FormData();
            formData.append("file", selectedFile);
            if (fileQuestion) formData.append("question", fileQuestion);
            formData.append("session_id", currentSessionId);

            const res = await fetch("https://ai-lawyer.up.railway.app/analyze-file", {
                method: "POST",
                body: formData,
                // Headers 'Content-Type': 'multipart/form-data' устанавливается автоматически для FormData
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
            responseBox.appendChild(aiMessageDiv);
            aiMessageDiv.innerHTML = '<div id="spinner-final" style="text-align:center; padding: 20px;"><p>Форматирование и поиск статей...</p><div class="loader"></div></div>';
            responseBox.scrollTop = responseBox.scrollHeight;


            // Финальная обработка (поиск статей)
            const htmlRes = await fetch("https://ai-lawyer.up.railway.app/process-full-text", {
                method: "POST",
                headers: {
                    'Content-Type': 'application/json',
                    'Session-Id': currentSessionId
                },
                body: JSON.stringify({
                    question: fileQuestion || selectedFile.name, // Используем вопрос или имя файла для поиска статей
                    full_ai_text: data.analysis,
                    session_id: currentSessionId
                })
            });

            const final = await htmlRes.json();
            aiMessageDiv.innerHTML = final.html || "";

            if (final.session_id) setSessionId(final.session_id);

        } catch (err) {
            responseBox.innerHTML += `<div class="ai-message error-message">🚫 Ошибка анализа файла: ${err.message}</div>`;
        } finally {
            fileSpinner.style.display = "none";
            analyzeBtn.disabled = false;
            fileInput.disabled = false;
            fileQuestionInput.disabled = false;
            clearSelectedFile();
            loadAndDisplayAllSessionsSummary(); // Обновляем историю после ответа
            responseBox.scrollTop = responseBox.scrollHeight;
        }
    });

    // --- КНОПКА "НАЧАТЬ НОВЫЙ ДИАЛОГ" (основная) ---
    newDialogBtn.addEventListener("click", async () => {
        await startNewConversation();
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
            // Продолжаем очистку на клиенте даже при ошибке сервера
        }

        // Генерируем новый session_id и очищаем все на клиенте
        setSessionId(generateSessionId());
        responseBox.innerHTML = ''; // Очищаем основную область ответов
        userQuestionInput.value = '';
        userQuestionInput.disabled = false;
        fileQuestionInput.value = '';
        clearSelectedFile(); // Очищает выбранный файл и связанные поля
        submitBtn.disabled = false;
        analyzeBtn.disabled = true; // Кнопка анализа файла должна быть disabled, пока файл не выбран
        if (spinner) spinner.style.display = 'none';
        if (fileSpinner) fileSpinner.style.display = 'none';
        userQuestionInput.focus();
        loadAndDisplayAllSessionsSummary(); // Обновляем список чатов в сайдбаре
        updateActiveChatInList(currentSessionId); // Устанавливаем новый чат как активный
        conversationHistoryDisplay.innerHTML = '<p>Выберите диалог из боковой панели или начните новый.</p>'; // Очищаем область просмотра старой истории
    }

    // --- Функция для добавления сообщений в responseBox (текущий чат) ---
    function addMessageToResponseBox(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add(role === 'user' ? 'user-message' : 'ai-message');
        // Для user-сообщений просто текст, для AI - потенциально HTML
        messageDiv.innerHTML = role === 'user' ? `<p>${content}</p>` : content; 
        responseBox.appendChild(messageDiv);
        responseBox.scrollTop = responseBox.scrollHeight; // Прокручиваем вниз
    }

    // --- Загрузка и отображение сводки всех сессий для сайдбара ---
    async function loadAndDisplayAllSessionsSummary() {
        chatList.innerHTML = '<p>Загрузка истории...</p>'; // Показываем загрузку
        try {
            const response = await fetch('https://ai-lawyer.up.railway.app/get-all-sessions-summary');
            if (!response.ok) {
                throw new Error(`Ошибка загрузки сводки сессий: ${response.status}`);
            }
            const data = await response.json();
            const sessions = data.sessions;

            chatList.innerHTML = ''; // Очищаем
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

    // --- Функция для загрузки конкретного диалога в область просмотра истории ---
    async function loadSpecificConversation(sessionIdToLoad) {
        // Устанавливаем эту сессию как текущую
        setSessionId(sessionIdToLoad);
        updateActiveChatInList(sessionIdToLoad); // Выделяем ее в сайдбаре

        // Очищаем основную область чата и показываем спиннер
        responseBox.innerHTML = '';
        conversationHistoryDisplay.innerHTML = '<p>Загрузка диалога...</p>';
        spinner.style.display = 'block';

        try {
            const response = await fetch(`https://ai-lawyer.up.railway.app/get-history?session_id=${sessionIdToLoad}`);
            if (!response.ok) {
                throw new Error(`Ошибка загрузки конкретного диалога: ${response.status}`);
            }
            const data = await response.json();
            const history = data.history;

            conversationHistoryDisplay.innerHTML = ''; // Очищаем область просмотра истории
            responseBox.innerHTML = ''; // Очищаем текущий чат

            if (history && history.length > 0) {
                for (const msg of history) {
                    if (msg.role === 'user') {
                        addMessageToResponseBox('user', msg.content);
                    } else if (msg.role === 'model') {
                        // Для ответов модели повторно вызываем process-full-text, чтобы получить форматированный HTML
                        // Это важно, так как в БД хранится сырой текст, а нам нужен HTML
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
                        addMessageToResponseBox('ai', processedData.html || processedData.error || "Ошибка загрузки ответа.");
                    }
                }
            } else {
                addMessageToResponseBox('ai', 'История для этой сессии пуста.');
            }
            responseBox.scrollTop = responseBox.scrollHeight; // Прокручиваем к последнему ответу
        } catch (error) {
            console.error("Ошибка при загрузке конкретного диалога:", error);
            responseBox.innerHTML = `<div class="ai-message error-message">🚫 Не удалось загрузить диалог: ${error.message}</div>`;
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

    // При загрузке страницы, если есть текущая сессия, загружаем ее
    if (currentSessionId) {
        loadSpecificConversation(currentSessionId);
    }
});
