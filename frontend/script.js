
/* =========   GLOBAL API HELPERS   ========= */
const API_BASE = window.location.hostname.includes('vercel.app')
  ? 'https://ai-lawyer.up.railway.app'   // production backend
  : 'http://localhost:5000';             // local dev

async function apiFetch(path, options = {}, retries = 2) {
  for (let i = 0; i <= retries; i++) {
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        credentials: 'include', // Include cookies for sessions if needed
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
  const fileUploadInput      = document.getElementById('file-upload');
  const fileNameDisplay      = document.getElementById('file-name');
  const clearFileBtn         = document.getElementById('clearFileBtn');
  const fileQuestionInput    = document.getElementById('file-question');
  const homeLink             = document.getElementById('home-link');
  const aboutLinkNav         = document.getElementById('about-link-nav');
  const fileInfo             = document.getElementById('file-info');
  const uploadButton         = document.getElementById('upload-button');

  /* ----------  STATE ---------- */
  let currentSessionId = localStorage.getItem('currentSessionId') || 'default';
  let uploadedFile = null;

  if (clearFileBtn) {
    clearFileBtn.onclick = clearFile;
  }

  uploadButton.disabled = !uploadedFile;

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
          li.textContent = session.title;
          li.addEventListener('click', () => loadConversation(session.id));
          chatList.appendChild(li);
        });
      } else {
        chatList.innerHTML = '<p>История чатов пуста.</p>';
      }
    } catch (e) {
      console.error('Ошибка загрузки сессий:', e);
      chatList.innerHTML = `<p class="error-message">Ошибка загрузки истории: ${e.message}. Проверьте подключение к серверу или настройки CORS.</p>`;
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
      addMessage(`<p class="error-message">Ошибка загрузки истории беседы: ${e.message}. Проверьте подключение к серверу или настройки CORS.</p>`, 'ai-response');
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
  }

  async function sendText(text) {
    showChatContainer();
    if (!text.trim() && !uploadedFile) return;

    if (uploadedFile) {
      fileSpinner.style.display = 'block';
      spinner.style.display = 'none';
    } else {
      spinner.style.display = 'block';
      fileSpinner.style.display = 'none';
    }

    const messageText = uploadedFile ? fileQuestionInput.value || text : text;
    addMessage(messageText, 'user-message');
    userQuestionTextarea.value = '';
    chatInput.value = '';

    try {
      let res;
      if (uploadedFile) {
        const formData = new FormData();
        formData.append('file', uploadedFile);
        formData.append('question', messageText);
        formData.append('session_id', currentSessionId);

        res = await apiFetch('/upload-document', {
          method: 'POST',
          body: formData
        });
      } else {
        res = await apiFetch('/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: text, session_id: currentSessionId })
        });
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let aiFullResponse = '';

      spinner.style.display = 'none';
      fileSpinner.style.display = 'none';

      const aiMessageElement = document.createElement('div');
      aiMessageElement.classList.add('chat-bubble', 'ai-response');
      chatMessagesDisplay.appendChild(aiMessageElement);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        aiFullResponse += chunk;
        aiMessageElement.innerHTML = aiFullResponse;
        chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight;
      }

      if (aiFullResponse.includes("Ошибка:")) {
        aiMessageElement.innerHTML = `<p class="error-message">${aiFullResponse}</p>`;
      }

      await loadChatSessions();
      highlightSession(currentSessionId);
    } catch (e) {
      spinner.style.display = 'none';
      fileSpinner.style.display = 'none';
      console.error(e);
      addMessage(`<p class="error-message">Ошибка: ${e.message}. Проверьте подключение к серверу или настройки CORS.</p>`, 'ai-response');
    }
    clearFile();
  }

  /* ----------  EVENTS ---------- */
  submitBtn.onclick = e => { e.preventDefault(); sendText(userQuestionTextarea.value); };
  sendButton.onclick = e => { e.preventDefault(); sendText(chatInput.value); };
  newChatBtn.onclick = startNewChat;

  chatInput.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendText(chatInput.value); } };
  userQuestionTextarea.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendText(userQuestionTextarea.value); } };

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

  clearFileBtn.onclick = clearFile;

  homeLink.onclick = e => {
    e.preventDefault();
    showInitialSections();
  };

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
