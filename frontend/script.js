// frontend/script.js (Версия 3.0 - Финальная, с пост-обработкой)

document.addEventListener('DOMContentLoaded', () => {
    // --- CHAT LOGIC ---
    const form = document.getElementById('chat-form');
    const userQuestionInput = document.getElementById('userQuestion');
    const responseBox = document.getElementById('response');
    const spinner = document.getElementById('spinner');
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = userQuestionInput.value.trim();
        if (!question) return;

        // --- Подготовка UI ---
        if (spinner) spinner.style.display = 'block';
        responseBox.innerHTML = '';
        const submitBtn = document.getElementById('submitBtn');
        submitBtn.disabled = true;
        userQuestionInput.disabled = true;

        let fullAiText = "";

        try {
            // --- ЭТАП 1: Получаем "живой" текст ответа от ИИ ---
            const streamResponse = await fetch('https://ai-lawyer.up.railway.app/ask', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ question }),
            });

            if (!streamResponse.ok) throw new Error(`Ошибка сервера при стриминге: ${streamResponse.status}`);
            
            const reader = streamResponse.body.getReader();
            const decoder = new TextDecoder('utf-8');
            
            if (spinner) spinner.style.display = 'none';
            responseBox.style.whiteSpace = "pre-wrap";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const textChunk = decoder.decode(value, { stream: true });
                fullAiText += textChunk;
                responseBox.textContent = fullAiText;
            }
            
            // --- ЭТАП 2: Отправляем полный текст на финальную обработку ---
            responseBox.style.whiteSpace = "normal";
            responseBox.innerHTML = '<div id="spinner-final" style="text-align:center; padding: 20px;"><p>Форматирование и поиск статей...</p><div class="loader"></div></div>';

            const processResponse = await fetch('https://ai-lawyer.up.railway.app/process-full-text', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ question: question, full_ai_text: fullAiText }),
            });

            if (!processResponse.ok) throw new Error(`Ошибка сервера при обработке: ${processResponse.status}`);
            const data = await processResponse.json();
            responseBox.innerHTML = data.html;

        } catch (error) {
            if (spinner) spinner.style.display = 'none';
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
    const fileSpinner = document.querySelector('.spinner'); // для файла (может быть отдельный спиннер)

    ['dragenter', 'dragover'].forEach(event => {
        dropArea.addEventListener(event, e => {
            e.preventDefault(); dropArea.classList.add('highlight');
        });
    });

    ['dragleave', 'drop'].forEach(event => {
        dropArea.addEventListener(event, e => {
            e.preventDefault(); dropArea.classList.remove('highlight');
        });
    });

    dropArea.addEventListener('drop', e => {
        const file = e.dataTransfer.files[0];
        fileInput.files = e.dataTransfer.files;
        fileChosen.textContent = file.name;
        analyzeBtn.disabled = false;
        clearBtn.disabled = false;
    });

    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        fileChosen.textContent = file ? file.name : 'Файл не выбран';
        analyzeBtn.disabled = !file;
        clearBtn.disabled = !file;
    });

    clearBtn.addEventListener('click', () => {
        fileInput.value = '';
        fileChosen.textContent = 'Файл не выбран';
        analyzeBtn.disabled = true;
        clearBtn.disabled = true;
    });

    // --- ОБНОВЛЁННЫЙ submit handler для file-form ---
    document.getElementById("file-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const file = fileInput.files[0];
        if (!file) return;

        responseBox.innerHTML = "";
        fileSpinner.style.display = "inline-block";
        analyzeBtn.disabled = true;
        fileInput.disabled = true;

        try {
            const formData = new FormData();
            formData.append("file", file);

            const res = await fetch("https://ai-lawyer.up.railway.app/analyze-file", {
                method: "POST",
                body: formData,
            });

            if (!res.ok) throw new Error(`Ошибка сервера: ${res.status}`);
            const data = await res.json();

            // ⬇ Переформатирование как и у обычного ответа
            const htmlRes = await fetch("https://ai-lawyer.up.railway.app/process-full-text", {
                method: "POST",
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ question: "", full_ai_text: data.analysis })
            });

            const final = await htmlRes.json();
            responseBox.innerHTML = final.html;

        } catch (err) {
            responseBox.innerHTML = `<p style="color:red;">🚫 Ошибка анализа файла: ${err.message}</p>`;
        } finally {
            fileSpinner.style.display = "none";
            analyzeBtn.disabled = false;
            fileInput.disabled = false;
            fileInput.value = null;
            fileChosen.textContent = 'Файл не выбран';
            clearBtn.disabled = true;
        }
    });
});
