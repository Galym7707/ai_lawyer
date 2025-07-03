// frontend/script.js (Версия 3.2 - UX, session, fileQuestion, new dialog)

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

    // --- CHAT LOGIC ---
    const form = document.getElementById('chat-form');
    const userQuestionInput = document.getElementById('userQuestion');
    const responseBox = document.getElementById('response');
    const spinner = document.getElementById('spinner');
    const newDialogBtn = document.getElementById('new-conversation');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = userQuestionInput.value.trim();
        if (!question) return;

        spinner.style.display = 'block';
        responseBox.innerHTML = '';
        const submitBtn = document.getElementById('submitBtn');
        submitBtn.disabled = true;
        userQuestionInput.disabled = true;

        let fullAiText = "";
        let session_id = getSessionId();

        try {
            const streamResponse = await fetch('https://ai-lawyer.up.railway.app/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Session-Id': session_id
                },
                body: JSON.stringify({ question, session_id }),
            });

            if (!streamResponse.ok) throw new Error(`Ошибка сервера при стриминге: ${streamResponse.status}`);

            const reader = streamResponse.body.getReader();
            const decoder = new TextDecoder('utf-8');

            spinner.style.display = 'none';
            responseBox.style.whiteSpace = "pre-wrap";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const textChunk = decoder.decode(value, { stream: true });
                fullAiText += textChunk;
                responseBox.textContent = fullAiText;
            }

            responseBox.style.whiteSpace = "normal";
            responseBox.innerHTML = '<div id="spinner-final" style="text-align:center; padding: 20px;"><p>Форматирование и поиск статей...</p><div class="loader"></div></div>';

            // Финальная обработка + session_id
            const processResponse = await fetch('https://ai-lawyer.up.railway.app/process-full-text', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Session-Id': session_id
                },
                body: JSON.stringify({ question, full_ai_text: fullAiText, session_id }),
            });

            if (!processResponse.ok) throw new Error(`Ошибка сервера при обработке: ${processResponse.status}`);
            const data = await processResponse.json();
            responseBox.innerHTML = data.html || "";

            // Сохраняем session_id, если сервер вернул новый
            if (data.session_id) setSessionId(data.session_id);

        } catch (error) {
            spinner.style.display = 'none';
            responseBox.innerHTML = `<p style="color:red;">🚫 Произошла критическая ошибка: ${error.message}</p>`;
        } finally {
            submitBtn.disabled = false;
            userQuestionInput.disabled = false;
            userQuestionInput.focus();
        }
    });

    // --- DRAG & DROP FILE LOGIC ---
    const dropArea = document.getElementById('drag-and-drop-area');
    const fileInput = document.getElementById('fileInput');
    const fileChosen = document.getElementById('file-chosen');
    const clearBtn = document.getElementById('clearBtn');
    const analyzeBtn = document.getElementById('fileSubmitBtn');
    const fileSpinner = document.getElementById('fileSpinner');
    const fileQuestionInput = document.getElementById('fileQuestion');
    let selectedFile = null;
    const MAX_SIZE = 1024 ** 3; // 1 GB

    function handleFile(file) {
        if (!file) return;
        if (file.size > MAX_SIZE) {
            alert("Максимальный размер – 1 ГБ");
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
        fileQuestionInput.value = "";
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
    document.getElementById("file-form").addEventListener("submit", async e => {
        e.preventDefault();
        if (!selectedFile) return;

        responseBox.innerHTML = "";
        fileSpinner.style.display = "block";

        analyzeBtn.disabled = true;
        fileInput.disabled = true;
        fileQuestionInput.disabled = true;

        let session_id = getSessionId();
        const fileQuestion = fileQuestionInput.value.trim();

        try {
            // 1. Отправляем файл + вопрос + session_id
            const formData = new FormData();
            formData.append("file", selectedFile);
            if (fileQuestion) formData.append("question", fileQuestion);
            formData.append("session_id", session_id);

            const res = await fetch("https://ai-lawyer.up.railway.app/analyze-file", {
                method: "POST",
                body: formData,
                headers: { 'Session-Id': session_id }
            });

            if (!res.ok) {
                let errorData;
                try { errorData = await res.json(); } catch { }
                throw new Error(errorData?.error || `Ошибка сервера: ${res.status}`);
            }
            const data = await res.json();
            if (!data.analysis || typeof data.analysis !== 'string') {
                throw new Error(`Ответ ИИ не содержит текст анализа.`);
            }
            if (data.session_id) setSessionId(data.session_id);

            // 2. Финальная обработка
            const htmlRes = await fetch("https://ai-lawyer.up.railway.app/process-full-text", {
                method: "POST",
                headers: {
                    'Content-Type': 'application/json',
                    'Session-Id': getSessionId()
                },
                body: JSON.stringify({
                    question: fileQuestion,
                    full_ai_text: data.analysis,
                    session_id: getSessionId()
                })
            });

            const final = await htmlRes.json();
            responseBox.innerHTML = final.html || "";

            if (final.session_id) setSessionId(final.session_id);

        } catch (err) {
            responseBox.innerHTML = `<p style="color:red;">🚫 Ошибка анализа файла: ${err.message}</p>`;
        } finally {
            fileSpinner.style.display = "none";
            analyzeBtn.disabled = false;
            fileInput.disabled = false;
            fileQuestionInput.disabled = false;
            clearSelectedFile();
        }
    });

    // --- КНОПКА "НОВЫЙ ДИАЛОГ" ---
    newDialogBtn.addEventListener("click", () => {
        // Новый session_id, очистка всего
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
    });
});
