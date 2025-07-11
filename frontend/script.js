// frontend/script.js (Версия 4.2 - Динамический сбор информации, История чатов, Улучшения UX)

document.addEventListener('DOMContentLoaded', () => {
    // --- SESSION ID LOGIC ---
    const SESSION_KEY = "kazlaw_session_id";
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
        if (id && id !== getSessionId()) localStorage.setItem(SESSION_KEY, id);
    }

    // --- DOM Elements ---
    const form = document.getElementById('chat-form');
    const userQuestionInput = document.getElementById('userQuestion');
    const responseBox = document.getElementById('response');
    const spinner = document.getElementById('spinner');
    const newDialogBtn = document.getElementById('new-conversation');
    const fileForm = document.getElementById('file-form');
    const fileInput = document.getElementById('fileInput');
    const fileChosen = document.getElementById('file-chosen');
    const clearBtn = document.getElementById('clearBtn');
    const analyzeBtn = document.getElementById('fileSubmitBtn');
    const fileSpinner = document.getElementById('fileSpinner');
    const fileQuestionInput = document.getElementById('fileQuestion');
    const conversationHistoryDiv = document.getElementById('conversation-history');

    let selectedFile = null;
    const MAX_SIZE = 1024 ** 3; // 1 GB

    // --- INITIAL LOAD ---
    // Загружаем историю при загрузке страницы
    loadAndDisplayConversationHistory(getSessionId());

    // --- CHAT LOGIC ---
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = userQuestionInput.value.trim();
        if (!question) return;

        spinner.style.display = 'block';
        responseBox.innerHTML = '';
        document.getElementById('submitBtn').disabled = true;
        userQuestionInput.disabled = true;
        
        // Добавляем вопрос пользователя в responseBox сразу
        addMessageToResponseBox('user', question);

        let fullAiText = "";
        let currentSessionId = getSessionId();

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
            // responseBox.style.whiteSpace = "pre-wrap"; // Это может нарушить форматирование HTML, убрал

            // Создаем div для ответа ИИ, чтобы потом обновить его HTML
            const aiMessageDiv = document.createElement('div');
            aiMessageDiv.classList.add('ai-message');
            responseBox.appendChild(aiMessageDiv);

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const textChunk = decoder.decode(value, { stream: true });
                fullAiText += textChunk;
                aiMessageDiv.textContent = fullAiText; // Обновляем текст в "сыром" виде
            }

            // Теперь отправляем полный текст на финальную обработку
            aiMessageDiv.innerHTML = '<div id="spinner-final" style="text-align:center; padding: 20px;"><p>Форматирование и поиск статей...</p><div class="loader"></div></div>';

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

            // Сохраняем session_id, если сервер вернул новый (редко, но на всякий случай)
            if (data.session_id) setSessionId(data.session_id);

        } catch (error) {
            spinner.style.display = 'none';
            responseBox.innerHTML = `<div class="ai-message error-message">🚫 Произошла критическая ошибка: ${error.message}</div>`;
        } finally {
            document.getElementById('submitBtn').disabled = false;
            userQuestionInput.disabled = false;
            userQuestionInput.value = ''; // Очищаем поле ввода
            userQuestionInput.focus();
            loadAndDisplayConversationHistory(getSessionId()); // Обновляем историю после ответа
            responseBox.scrollTop = responseBox.scrollHeight; // Прокручиваем к последнему ответу
        }
    });

    // --- DRAG & DROP FILE LOGIC ---
    const dropArea = document.getElementById('drag-and-drop-area');
    
    function handleFile(file) {
        if (!file) return;
        if (file.size > MAX_SIZE) {
            alert("Максимальный размер файла – 1 ГБ");
            clearSelectedFile();
            return;
        }
        // Проверка типа файла
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
        dropArea.addEventListener(evt, e => { e.preventDefault(); dropArea.classList.add("drag-over"); })
    );
    ["dragleave", "drop"].forEach(evt =>
        dropArea.addEventListener(evt, e => {
            e.preventDefault();
            dropArea.classList.remove("drag-over");
            if (evt === "drop") handleFile(e.dataTransfer.files[0]);
        })
    );

    fileInput.addEventListener("change", e => handleFile(e.target.files[0]));
    clearBtn.addEventListener("click", clearSelectedFile);

    // --- SUBMIT FILE ANALYSIS ---
    fileForm.addEventListener("submit", async e => {
        e.preventDefault();
        if (!selectedFile) return;

        responseBox.innerHTML = "";
        fileSpinner.style.display = "block";

        analyzeBtn.disabled = true;
        fileInput.disabled = true;
        fileQuestionInput.disabled = true;

        let currentSessionId = getSessionId();
        const fileQuestion = fileQuestionInput.value.trim();

        // Добавляем информацию о загрузке файла в responseBox сразу
        addMessageToResponseBox('user', `Загружен файл: ${selectedFile.name}${fileQuestion ? '. Вопрос: ' + fileQuestion : ''}`);


        try {
            // 1. Отправляем файл + вопрос + session_id
            const formData = new FormData();
            formData.append("file", selectedFile);
            if (fileQuestion) formData.append("question", fileQuestion);
            formData.append("session_id", currentSessionId);

            const res = await fetch("https://ai-lawyer.up.railway.app/analyze-file", {
                method: "POST",
                body: formData,
                headers: { 'Session-Id': currentSessionId }
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

            // Создаем div для ответа ИИ, чтобы потом обновить его HTML
            const aiMessageDiv = document.createElement('div');
            aiMessageDiv.classList.add('ai-message');
            responseBox.appendChild(aiMessageDiv);
            aiMessageDiv.innerHTML = '<div id="spinner-final" style="text-align:center; padding: 20px;"><p>Форматирование и поиск статей...</p><div class="loader"></div></div>';


            // 2. Финальная обработка (поиск статей)
            const htmlRes = await fetch("https://ai-lawyer.up.railway.app/process-full-text", {
                method: "POST",
                headers: {
                    'Content-Type': 'application/json',
                    'Session-Id': getSessionId()
                },
                body: JSON.stringify({
                    question: fileQuestion || selectedFile.name, // Используем вопрос или имя файла для поиска статей
                    full_ai_text: data.analysis,
                    session_id: getSessionId()
                })
            });

            const final = await htmlRes.json();
            aiMessageDiv.innerHTML = final.html || "";

            if (final.session_id) setSessionId(final.session_id);

        } catch (err) {
            responseBox.innerHTML = `<div class="ai-message error-message">🚫 Ошибка анализа файла: ${err.message}</div>`;
        } finally {
            fileSpinner.style.display = "none";
            analyzeBtn.disabled = false;
            fileInput.disabled = false;
            fileQuestionInput.disabled = false;
            clearSelectedFile();
            loadAndDisplayConversationHistory(getSessionId()); // Обновляем историю после ответа
            responseBox.scrollTop = responseBox.scrollHeight; // Прокручиваем к последнему ответу
        }
    });

    // --- КНОПКА "НОВЫЙ ДИАЛОГ" ---
    newDialogBtn.addEventListener("click", async () => {
        const currentSessionId = getSessionId();
        // Удаляем историю из базы данных
        try {
            await fetch("https://ai-lawyer.up.railway.app/clear-history", {
                method: "POST",
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ session_id: currentSessionId })
            });
        } catch (error) {
            console.error("Ошибка при очистке истории на сервере:", error);
            // Продолжаем очистку на клиенте даже при ошибке сервера
        }

        // Генерируем новый session_id и очищаем все на клиенте
        setSessionId(generateSessionId());
        responseBox.innerHTML = "";
        userQuestionInput.value = "";
        userQuestionInput.disabled = false;
        fileQuestionInput.value = "";
        clearSelectedFile();
        document.getElementById('submitBtn').disabled = false;
        analyzeBtn.disabled = true;
        if (spinner) spinner.style.display = 'none';
        if (fileSpinner) fileSpinner.style.display = 'none';
        userQuestionInput.focus();
        loadAndDisplayConversationHistory(getSessionId()); // Обновляем историю после очистки
    });

    // --- Функция для добавления сообщений в responseBox ---
    function addMessageToResponseBox(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add(role === 'user' ? 'user-message' : 'ai-message');
        messageDiv.innerHTML = `<p>${content}</p>`; // Используем innerHTML для обработки потенциального HTML
        responseBox.appendChild(messageDiv);
        responseBox.scrollTop = responseBox.scrollHeight; // Прокручиваем вниз
    }

    // --- Загрузка и отображение истории чатов ---
    async function loadAndDisplayConversationHistory(sessionId) {
        conversationHistoryDiv.innerHTML = '<p>Загрузка истории...</p>';
        try {
            const response = await fetch(`https://ai-lawyer.up.railway.app/get-history?session_id=${sessionId}`);
            if (!response.ok) {
                throw new Error(`Ошибка загрузки истории: ${response.status}`);
            }
            const data = await response.json();
            const history = data.history;

            if (history && history.length > 0) {
                conversationHistoryDiv.innerHTML = ''; // Очищаем "Загрузка истории..."
                // Группируем сообщения в диалоги
                let currentDialog = [];
                for (let i = 0; i < history.length; i++) {
                    const msg = history[i];
                    if (msg.role === 'user' && currentDialog.length > 0) {
                        renderDialog(currentDialog);
                        currentDialog = [];
                    }
                    currentDialog.push(msg);
                }
                if (currentDialog.length > 0) {
                    renderDialog(currentDialog);
                }
            } else {
                conversationHistoryDiv.innerHTML = '<p>Пока нет истории диалогов. Начните новую консультацию!</p>';
            }
        } catch (error) {
            console.error("Ошибка при загрузке истории:", error);
            conversationHistoryDiv.innerHTML = `<p style="color:red;">Не удалось загрузить историю: ${error.message}</p>`;
        }
    }

    function renderDialog(dialog) {
        const dialogCard = document.createElement('div');
        dialogCard.classList.add('history-card');
        
        let dialogContentHtml = '';
        dialog.forEach(msg => {
            const class_name = msg.role === 'user' ? 'history-user-message' : 'history-ai-message';
            dialogContentHtml += `<div class="${class_name}">${msg.role === 'user' ? '<strong>Вы:</strong>' : '<strong>ИИ-юрист:</strong>'} ${msg.content.substring(0, 150)}...</div>`; // Показываем часть сообщения
        });

        // Добавляем кнопку "Посмотреть полностью" или "Загрузить диалог"
        const firstUserQuestion = dialog.find(msg => msg.role === 'user');
        const dialogTitle = firstUserQuestion ? firstUserQuestion.content.substring(0, 70) + '...' : 'Диалог без вопроса';

        dialogCard.innerHTML = `
            <div class="history-card-header">
                <h3>${dialogTitle}</h3>
                <button class="load-dialog-btn btn" data-session-id="${getSessionId()}">Загрузить</button>
            </div>
            <div class="history-card-body">
                ${dialogContentHtml}
            </div>
        `;
        conversationHistoryDiv.appendChild(dialogCard);

        // Обработчик для кнопки "Загрузить диалог"
        dialogCard.querySelector('.load-dialog-btn').addEventListener('click', (e) => {
            const currentSessionId = e.target.dataset.sessionId;
            loadSpecificConversation(currentSessionId);
            // Переходим к разделу "Юридическая помощь"
            document.getElementById('help').scrollIntoView({ behavior: 'smooth' });
        });
    }

    // Функция для загрузки конкретного диалога в текущий responseBox
    async function loadSpecificConversation(sessionIdToLoad) {
        setSessionId(sessionIdToLoad); // Устанавливаем эту сессию как текущую
        responseBox.innerHTML = '<p>Загрузка диалога...</p>';
        spinner.style.display = 'block';
        try {
            const response = await fetch(`https://ai-lawyer.up.railway.app/get-history?session_id=${sessionIdToLoad}`);
            if (!response.ok) {
                throw new Error(`Ошибка загрузки конкретного диалога: ${response.status}`);
            }
            const data = await response.json();
            const history = data.history;

            responseBox.innerHTML = ''; // Очищаем, чтобы вставить полный диалог

            for (const msg of history) {
                if (msg.role === 'user') {
                    addMessageToResponseBox('user', msg.content);
                } else if (msg.role === 'model') {
                    // Для ответов модели повторно вызываем process-full-text, чтобы получить форматированный HTML
                    const processResponse = await fetch('https://ai-lawyer.up.railway.app/process-full-text', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Session-Id': sessionIdToLoad
                        },
                        body: JSON.stringify({ question: "", full_ai_text: msg.content, session_id: sessionIdToLoad }), // question тут может быть пустым
                    });
                    const processedData = await processResponse.json();
                    const aiMessageDiv = document.createElement('div');
                    aiMessageDiv.classList.add('ai-message');
                    aiMessageDiv.innerHTML = processedData.html || processedData.error || "Ошибка загрузки ответа.";
                    responseBox.appendChild(aiMessageDiv);
                }
            }
            responseBox.scrollTop = responseBox.scrollHeight; // Прокручиваем к последнему ответу
        } catch (error) {
            console.error("Ошибка при загрузке конкретного диалога:", error);
            responseBox.innerHTML = `<p style="color:red;">Не удалось загрузить диалог: ${error.message}</p>`;
        } finally {
            spinner.style.display = 'none';
        }
    }
});
