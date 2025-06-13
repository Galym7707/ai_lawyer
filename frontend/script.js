// frontend/script.js (Версия 3.0 - Финальная, с пост-обработкой)

document.addEventListener('DOMContentLoaded', () => {
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
        responseBox.innerHTML = ''; // Полная очистка
        const submitBtn = document.getElementById('submitBtn');
        submitBtn.disabled = true;
        userQuestionInput.disabled = true;

        let fullAiText = ""; // Переменная для накопления полного текста от ИИ

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
            
            if (spinner) spinner.style.display = 'none'; // Прячем спиннер с первым же фрагментом
            responseBox.style.whiteSpace = "pre-wrap"; // ВАЖНО: сохраняем переносы строк для сырого текста

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const textChunk = decoder.decode(value, { stream: true });
                fullAiText += textChunk; // Накапливаем текст
                responseBox.textContent = fullAiText; // Отображаем как простой текст
            }
            
            // --- ЭТАП 2: Отправляем полный текст на финальную обработку ---
            responseBox.style.whiteSpace = "normal"; // Возвращаем обычный режим отображения
            responseBox.innerHTML = '<div id="spinner-final" style="text-align:center; padding: 20px;"><p>Форматирование и поиск статей...</p><div class="loader"></div></div>';


            const processResponse = await fetch('https://ai-lawyer.up.railway.app/process-full-text', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ question: question, full_ai_text: fullAiText }),
            });

            if (!processResponse.ok) throw new Error(`Ошибка сервера при обработке: ${processResponse.status}`);

            const data = await processResponse.json();
            
            // Заменяем временный текст на финальный, красиво отформатированный HTML
            responseBox.innerHTML = data.html;

        } catch (error) {
            if (spinner) spinner.style.display = 'none';
            responseBox.innerHTML = `<p style="color:red;">🚫 Произошла критическая ошибка: ${error.message}</p>`;
        } finally {
            // --- Возвращаем UI в исходное состояние ---
            submitBtn.disabled = false;
            userQuestionInput.disabled = false;
            userQuestionInput.focus();
        }
    });
});
