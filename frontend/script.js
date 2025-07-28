/* =========   GLOBAL API HELPERS   ========= */
const API_BASE = '/api'; // Use Vercel proxy

async function apiFetch(path, options = {}, retries = 2) {
  for (let i = 0; i <= retries; i++) {
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        credentials: 'include',
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${await response.text()}`);
      }
      return response;
    } catch (e) {
      if (i < retries) {
        console.warn(`Retry ${i + 1}/${retries} for ${path}: ${e.message}`);
        await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
        continue;
      }
      throw e;
    }
  }
}

async function safeJson(res) {
  const type = res.headers.get('content-type') || '';
  if (type.includes('application/json')) return res.json();
  const text = await res.text();
  throw new Error(text.slice(0, 300) || `HTTP ${res.status}`);
}

/* =========   MAIN SCRIPT   ========= */
document.addEventListener('DOMContentLoaded', () => {
  /* ----------  DOM ---------- */
  const initialSections      = document.getElementById('initial-sections');
  const currentChatContainer = document.getElementById('current-chat-container');
  const chatMessagesDisplay  = document.getElementById('chat-messages-display');
  const userQuestionTextarea = document.getElementById('userQuestion');
  const submitBtn            = document.getElementById('send-initial-message');
  const chatInput            = document.getElementById('chat-input');
  const sendButton           = document.getElementById('send-button');
  const newChatBtn           = document.getElementById('start-new-conversation-sidebar');
  const spinner              = document.getElementById('spinner');
  const fileSpinner          = document.getElementById('fileSpinner');
  const chatList             = document.getElementById('chat-list');

  // Элементы формы для загрузки файла в отдельной секции
  const fileUploadInput      = document.getElementById('file-upload');
  const fileNameDisplay      = document.getElementById('file-name');
  const clearFileBtn         = document.getElementById('clearFileBtn');
  const fileQuestionInput    = document.getElementById('file-question');
  const fileInfo             = document.getElementById('file-info');
  const uploadButton         = document.getElementById('upload-button');

  // Новые элементы для загрузки файла прямо из чата
  const chatFileUploadInput  = document.getElementById('chat-file-upload');
  const attachFileButton     = document.getElementById('attach-file-button');

  // Навигация
  const homeLink             = document.getElementById('home-link');
  const aboutLinkNav         = document.getElementById('about-link-nav');

  /* ----------  STATE ---------- */
  let currentSessionId = localStorage.getItem('currentSessionId') || 'default';
  let uploadedFile = null;

  /* ----------  FILE UPLOAD IN CHAT ---------- */
  // кнопка‑скрепка открывает диалог выбора файла
  attachFileButton.onclick = () => {
    chatFileUploadInput.click();
  };

  // когда файл выбран, сохраняем его и сразу отправляем вместе с текстом
  chatFileUploadInput.onchange = (event) => {
    const file = event.target.files[0];
    if (file) {
      uploadedFile = file;
      sendText(chatInput.value);
    }
  };

  /* ----------  HELPERS ---------- */
  function showInitialSections() {
    initialSections.style.display = 'block';
    currentChatContainer.style.display = 'none';
    clearChatMessages();
    userQuestionTextarea.value = '';
    chatInput.value = '';
    clearFile();
  }

  function showChatContainer() {
    initialSections.style.display = 'none';
    currentChatContainer.style.display = 'flex';
  }

  function clearChatMessages() {
    chatMessagesDisplay.innerHTML = `
      <div id="spinner" style="display: none;">
          <p>ИИ-юрист анализирует ваш запрос...</p>
          <div class="loader"></div>
      </div>
      <div id="fileSpinner" style="display: none;">
          <p>ИИ-юрист анализирует ваш документ...</p>
          <div class="loader"></div>
      </div>
    `;
  }

  function addMessage(text, senderClass) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('chat-bubble', senderClass);
    messageElement.innerHTML = text;
    chatMessagesDisplay.appendChild(messageElement);
    chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight;
    if (text.includes("Ошибка:")) {
      messageElement.innerHTML = `<p class="error-message">${text}</p>`;
    }
  }

  async function loadChatSessions() {
    chatList.innerHTML = '<p>Загрузка истории...</p>';
    try {
      const res = await apiFetch('/get-all-sessions-summary');
      const data = await safeJson(res);
      chatList.innerHTML = '';
      if (data.sessions && data.sessions.length > 0) {
        data.sessions.forEach(session => {
          const li = document.createElement('li');
          li.dataset.sessionId = session.id;

          // название чата в отдельном span, чтобы по нему можно было кликнуть
          const spanTitle = document.createElement('span');
          spanTitle.textContent = session.title;
          spanTitle.onclick = () => loadConversation(session.id);
          li.appendChild(spanTitle);

          // кнопка удаления с иконкой корзины
          const delBtn = document.createElement('button');
          delBtn.classList.add('delete-chat-btn');
          delBtn.innerHTML = '<i class="fas fa-trash"></i>';
          delBtn.onclick = async (e) => {
            e.stopPropagation();
            if (confirm('Удалить этот чат?')) {
              try {
                await apiFetch(`/delete-session?session_id=${session.id}`, { method: 'DELETE' });
                // если удалён текущий чат, переключаемся на новый
                if (currentSessionId === session.id) {
                  await startNewChat();
                }
                await loadChatSessions();
                highlightSession(currentSessionId);
              } catch (err) {
                alert(`Не удалось удалить чат: ${err.message}`);
              }
            }
          };
          li.appendChild(delBtn);

          chatList.appendChild(li);
        });
      } else {
        chatList.innerHTML = '<p>История чатов пуста.</p>';
      }
    } catch (e) {
      console.error('Ошибка загрузки сессий:', e);
      chatList.innerHTML =
        `<p class="error-message">Ошибка загрузки истории: ${e.message}. Проверьте подключение к серверу.</p>`;
    }
  }

  async function loadConversation(sessionId) {
    currentSessionId = sessionId;
    localStorage.setItem('currentSessionId', currentSessionId);
    showChatContainer();
    clearChatMessages();
    highlightSession(sessionId);
    try {
      const res = await apiFetch(`/get-history?session_id=${sessionId}`);
      const data = await safeJson(res);
      if (data.history) {
        data.history.forEach(msg => {
          addMessage(msg.content, msg.role === 'user' ? 'user-message' : 'ai-response');
        });
      }
    } catch (e) {
      console.error('Ошибка загрузки истории беседы:', e);
      addMessage(
        `<p class="error-message">Ошибка загрузки истории беседы: ${e.message}. Проверьте подключение к серверу.</p>`,
        'ai-response'
      );
    }
  }

  function highlightSession(sessionId) {
    document.querySelectorAll('#chat-list li').forEach(li => {
      li.classList.remove('active');
    });
    const activeLi = document.querySelector(`[data-session-id="${sessionId}"]`);
    if (activeLi) {
      activeLi.classList.add('active');
    }
  }

  async function startNewChat() {
    currentSessionId = crypto.randomUUID();
    localStorage.setItem('currentSessionId', currentSessionId);
    showChatContainer();
    clearChatMessages();
    highlightSession(currentSessionId);
    await loadChatSessions();
    highlightSession(currentSessionId);
  }

  function clearFile() {
    uploadedFile = null;
    fileUploadInput.value = '';
    fileNameDisplay.textContent = 'Файл не выбран';
    fileQuestionInput.value = '';
    fileInfo.style.display = 'none';
    uploadButton.disabled = true;
    // очищаем также скрытый input из чата, чтобы можно было выбрать тот же файл повторно
    if (chatFileUploadInput) {
      chatFileUploadInput.value = '';
    }
  }

  async function sendText(text) {
    showChatContainer();
    if (!text.trim() && !uploadedFile) return;
  
    // Показываем соответствующий спиннер
    if (uploadedFile) {
      if (fileSpinner) fileSpinner.style.display = 'block';
      if (spinner) spinner.style.display = 'none';
    } else {
      if (spinner) spinner.style.display = 'block';
      if (fileSpinner) fileSpinner.style.display = 'none';
    }
  
    // Отображаем сообщение пользователя
    const messageText = uploadedFile ? fileQuestionInput.value || text : text;
    addMessage(messageText, 'user-message');
    userQuestionTextarea.value = '';
    chatInput.value = '';
  
    try {
      let res;
      if (uploadedFile) {
        // отправка файла
        const formData = new FormData();
        formData.append('file', uploadedFile);
        formData.append('question', messageText);
        formData.append('session_id', currentSessionId);
        res = await apiFetch('/upload-document', {
          method: 'POST',
          body: formData
        });
      } else {
        // отправка текста
        res = await apiFetch('/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: text, session_id: currentSessionId })
        });
      }
  
      // Создаём «заглушку» для ответа ИИ
      const aiMessageElement = document.createElement('div');
      aiMessageElement.classList.add('chat-bubble', 'ai-response');
      aiMessageElement.textContent = uploadedFile
        ? 'ИИ-юрист анализирует ваш документ…'
        : 'ИИ-юрист анализирует ваш запрос…';
      chatMessagesDisplay.appendChild(aiMessageElement);
      chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight;
  
      // Читаем поток ответа и обновляем элемент по мере получения данных
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let aiFullResponse = '';
      // Скрываем спиннеры
      if (spinner) spinner.style.display = 'none';
      if (fileSpinner) fileSpinner.style.display = 'none';
  
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        aiFullResponse += chunk;
        aiMessageElement.innerHTML = aiFullResponse;
        chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight;
      }
  
      // Если сервер прислал сообщение об ошибке, заменяем содержимое
      if (aiFullResponse.includes("Ошибка:")) {
        aiMessageElement.innerHTML = `<p class="error-message">${aiFullResponse}</p>`;
      }
  
      await loadChatSessions();
      highlightSession(currentSessionId);
  
    } catch (e) {
      // Скрываем спиннеры в случае ошибки
      if (spinner) spinner.style.display = 'none';
      if (fileSpinner) fileSpinner.style.display = 'none';
      console.error(e);
      addMessage(
        `<p class="error-message">Ошибка: ${e.message}. Проверьте подключение к серверу.</p>`,
        'ai-response'
      );
    }
  
    // Сбрасываем файл после отправки
    clearFile();
  }


  /* ----------  EVENTS ---------- */
  // Отправка начального вопроса из текстового поля на главном экране
  submitBtn.onclick = e => {
    e.preventDefault();
    sendText(userQuestionTextarea.value);
  };

  // Отправка текста из чата
  sendButton.onclick = e => {
    e.preventDefault();
    sendText(chatInput.value);
  };

  // Новый чат
  newChatBtn.onclick = startNewChat;

  // Отправка по Enter в chatInput
  chatInput.onkeydown = e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendText(chatInput.value);
    }
  };

  // Отправка по Enter в начальном textarea
  userQuestionTextarea.onkeydown = e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendText(userQuestionTextarea.value);
    }
  };

  // Загрузка файла в отдельной секции
  fileUploadInput.onchange = (event) => {
    const file = event.target.files[0];
    if (file) {
      uploadedFile = file;
      fileNameDisplay.textContent = file.name;
      fileInfo.style.display = 'block';
      uploadButton.disabled = false;
    } else {
      clearFile();
    }
  };

  // Очистка файла в отдельной секции
  if (clearFileBtn) {
    clearFileBtn.onclick = clearFile;
  }

  // Переход домой
  homeLink.onclick = e => {
    e.preventDefault();
    showInitialSections();
  };

  // Ссылка "О проекте"
  aboutLinkNav.onclick = e => {
    e.preventDefault();
    document.getElementById('about').scrollIntoView({ behavior: 'smooth' });
    showInitialSections();
  };

  /* ----------  INIT ---------- */
  showInitialSections();
  loadChatSessions().then(() => {
    if (
      currentSessionId !== 'default' &&
      document.querySelector(`[data-session-id="${currentSessionId}"]`)
    ) {
      loadConversation(currentSessionId);
    } else {
      startNewChat();
    }
  });
});
