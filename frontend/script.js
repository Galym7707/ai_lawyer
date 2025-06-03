const submitBtn = document.getElementById('submitBtn');
const userQuestion = document.getElementById('userQuestion');
const responseBox = document.getElementById('response');

submitBtn.addEventListener('click', async () => {
  const question = userQuestion.value.trim();
  if (!question) {
    responseBox.innerHTML = '❗ Пожалуйста, введите ваш вопрос.';
    return;
  }

  responseBox.innerHTML = '⏳ Обрабатываем ваш запрос...';

  try {
    const res = await fetch('/ask', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ question })
    });

    const data = await res.json();

    if (data.answer) {
      // Заменяем переносы строк на <br> и отображаем HTML
      const formattedAnswer = data.answer.replace(/\n/g, '<br>');
      responseBox.innerHTML = formattedAnswer;
    } else if (data.error) {
      responseBox.innerHTML = `🚫 <strong>Ошибка:</strong> ${data.error}`;
    } else {
      responseBox.innerHTML = '⚠️ Непредвиденная ошибка. Попробуйте позже.';
    }
  } catch (err) {
    responseBox.innerHTML = `🚫 Ошибка соединения: ${err.message}`;
  }
});
