// frontend/script.js (Версия 3.1 - Исправленная и расширенная)

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

        if (spinner) spinner.style.display = 'block';
        responseBox.innerHTML = '';
        const submitBtn = document.getElementById('submitBtn');
        submitBtn.disabled = true;
        userQuestionInput.disabled = true;

        let fullAiText = "";

        try {
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

    // --- DRAG & DROP FILE LOGIC + Лимит размера, поддержка расширений ---
    const dropArea = document.getElementById('drag-and-drop-area');
    const fileInput = document.getElementById('fileInput');
    const fileChosen = document.getElementById('file-chosen');
    const clearBtn = document.getElementById('clearBtn');
    const analyzeBtn = document.getElementById('fileSubmitBtn');
    const fileSpinner = document.querySelector('.spinner');
    let selectedFile = null;
    const MAX_SIZE = 1024 ** 3; // 1 GB

    function handleFile(file) {
        if (!file) return;
        if (file.size > MAX_SIZE) {
            alert("Максимальный размер – 1 ГБ");
            clearSelectedFile();
            return;
        }
        // Если нужны ограничения по расширениям — добавить тут
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

    // --- ОБНОВЛЁННЫЙ submit handler для file-form с проверкой analysis ---
    document.getElementById("file-form").addEventListener("submit", async e => {
        e.preventDefault();
        if (!selectedFile) return;
    
        responseBox.innerHTML = "";
        fileSpinner.style.display = "inline-block";
        analyzeBtn.disabled = true;
        fileInput.disabled = true;
    
        try {
            const formData = new FormData();
            formData.append("file", selectedFile);
    
            const res = await fetch("https://ai-lawyer.up.railway.app/analyze-file", {
                method: "POST",
                body: formData,
            });
    
            if (!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.error || `Ошибка сервера: ${res.status}`);
            }
            const data = await res.json();
            if (!data.analysis) {
                throw new Error(`Пустой ответ от сервера: ${JSON.stringify(data)}`);
            }
    
            // Отправляем на финальную обработку
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
            clearSelectedFile();
        }
    });
});
