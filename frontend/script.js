// Убедимся, что скрипт запускается после полной загрузки страницы
document.addEventListener('DOMContentLoaded', () => {

    // Находим элементы в HTML по их ID
    const submitBtn = document.getElementById('submitBtn');
    const userQuestionInput = document.getElementById('userQuestion');
    const responseBox = document.getElementById('response');
    const spinner = document.getElementById('spinner');

    // Получаем форму, чтобы обрабатывать отправку и по нажатию Enter
    const form = submitBtn.form;
    if (!form) {
        console.error('Кнопка отправки должна быть внутри тега <form>');
        return;
    }

    // Вешаем обработчик на событие "submit" формы
    form.addEventListener('submit', async (e) => {
        // Предотвращаем стандартную перезагрузку страницы при отправке формы
        e.preventDefault();

        const question = userQuestionInput.value.trim();
        if (!question) {
            responseBox.innerHTML = '<p style="color: #ffc107;">❗ Пожалуйста, введите ваш вопрос.</p>';
            return;
        }

        // --- Обновляем интерфейс перед запросом ---
        if (spinner) spinner.style.display = 'block'; // Показываем спиннер
        responseBox.innerHTML = ''; // Очищаем предыдущий ответ
        submitBtn.disabled = true; // Делаем кнопку неактивной
        userQuestionInput.disabled = true; // И поле ввода тоже

        try {
            // --- Отправляем запрос на ваш бэкенд ---
            // URL взят из вашего оригинального скрипта
            const response = await fetch('https://ai-lawyer.up.railway.app/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ question }),
            });

            if (!response.ok) {
                // Если сервер вернул ошибку (например, 500)
                const errorText = await response.text();
                throw new Error(errorText || `Ошибка сервера: ${response.status}`);
            }

            // --- ГЛАВНОЕ ИЗМЕНЕНИЕ: Обработка потокового ответа ---
            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            
            // Скрываем спиннер, как только получили первый кусочек данных
            if (spinner) spinner.style.display = 'none';

            // Читаем поток по частям, пока он не закончится
            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    break; // Поток завершен
                }
                
                // Декодируем полученный фрагмент данных (это уже готовый HTML)
                const chunk = decoder.decode(value, { stream: true });
                // Добавляем его в блок ответа
                responseBox.innerHTML += chunk;

                // Автоматически прокручиваем вниз по мере поступления ответа
                responseBox.scrollTop = responseBox.scrollHeight;
            }

        } catch (err) {
            // Обрабатываем ошибки сети или ошибки сервера
            if (spinner) spinner.style.display = 'none'; // Прячем спиннер в случае ошибки
            responseBox.innerHTML = `<p style="color: #dc3545;">🚫 <strong>Произошла ошибка:</strong> ${err.message}</p>`;
        } finally {
            // --- Возвращаем интерфейс в исходное состояние ---
            submitBtn.disabled = false; // Снова делаем кнопку активной
            userQuestionInput.disabled = false;
            userQuestionInput.value = ''; // Очищаем поле ввода
            userQuestionInput.focus(); // Ставим курсор обратно в поле ввода
        }
    });
});
