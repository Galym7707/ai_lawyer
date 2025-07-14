/* =========   GLOBAL API HELPERS   ========= */
const API_BASE = window.location.hostname.includes('vercel.app')
  ? 'https://ai-lawyer.up.railway.app'   // production backend
  : 'http://localhost:5000';             // local dev

function apiFetch(path, options = {}) {
  return fetch(`${API_BASE}${path}`, options);
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
  const submitBtn            = document.getElementById('submitBtn');
  const chatInput            = document.getElementById('chat-input');
  const sendButton           = document.getElementById('send-button');
  const newChatBtn           = document.getElementById('start-new-conversation-sidebar');
  const spinner              = document.getElementById('spinner');
  const fileSpinner          = document.getElementById('fileSpinner');
  const chatList             = document.getElementById('chat-list');

  /* ----------  FILE-UPLOAD DOM ---------- */
  const dragArea          = document.getElementById('drag-and-drop-area');
  const fileInput         = document.getElementById('file-input');
  const fileQuestionInput = document.getElementById('file-question-input');
  const fileSubmitBtn     = document.getElementById('file-submit-btn');
  const fileChosenSpan    = document.getElementById('file-chosen');
  const clearBtn          = document.getElementById('clear-btn');

  /* ----------  CONSTANTS & STATE ---------- */
  const MAX_FILE_MB    = 1024;
  const MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024;
  const welcomeMessage = '<p>👋 Привет! Я ваш ИИ-юрист. Задайте вопрос или загрузите документ.</p>';

  let currentSessionId = localStorage.getItem('currentSessionId') || 'default';
  let currentFile      = null;

  /* ----------  HELPERS ---------- */
  const scrollToBottom = () => {
    chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight;
  };

  const showChatArea = () => {
    initialSections.style.display = 'none';
    currentChatContainer.style.display = 'block';
  };

  const showInitialSections = () => {
    initialSections.style.display = 'block';
    currentChatContainer.style.display = 'none';
  };

  // MODIFIED: Use marked.parse() for AI responses
  const addMessage = (html, cssClass = 'ai-response') => {
    const div = document.createElement('div');
    div.classList.add('chat-bubble', cssClass);
    if (cssClass === 'ai-response') {
        div.innerHTML = marked.parse(html); // Render Markdown for AI responses
    } else {
        div.innerHTML = `<p>${html}</p>`; // Wrap user queries in a paragraph
    }
    chatMessagesDisplay.appendChild(div);
    scrollToBottom();
  };

  /* ----------  CHAT HISTORY ---------- */
  async function loadChatHistory(sessionId) {
    chatMessagesDisplay.innerHTML = '';
    spinner.style.display = 'block';
    try {
      const res   = await apiFetch(`/get-history?session_id=${encodeURIComponent(sessionId)}`);
      const data  = await safeJson(res);
      spinner.style.display = 'none';

      if (data.history?.length) {
        data.history.forEach(msg =>
          // MODIFIED: Ensure historical AI messages are also rendered with Markdown
          addMessage(msg.content, msg.role === 'user' ? 'user-query' : 'ai-response'));
      } else {
        addMessage(welcomeMessage, 'ai-response');
      }
    } catch (e) {
      spinner.style.display = 'none';
      console.error(e);
      addMessage(`<p class="error-message">Ошибка загрузки истории: ${e.message}</p>`, 'ai-response');
    }
  }

  /* ----------  SIDEBAR SESSIONS ---------- */
  async function loadChatSessions() {
    chatList.innerHTML = '<p>Загрузка...</p>';
    try {
      const res  = await apiFetch('/get-all-sessions-summary');
      const data = await safeJson(res);
      chatList.innerHTML = '';

      if (data.sessions?.length) {
        data.sessions.sort((a, b) => b.id.localeCompare(a.id));
        data.sessions.forEach(s => {
          const li = document.createElement('li');
          li.textContent     = s.title || 'Без названия';
          li.dataset.sessionId = s.id;
          li.onclick = () => {
            currentSessionId = s.id;
            localStorage.setItem('currentSessionId', s.id);
            highlightSession(s.id);
            loadChatHistory(s.id);
            showChatArea();
          };
          chatList.appendChild(li);
        });
      } else {
        chatList.innerHTML = '<p>Чатов нет</p>';
      }
    } catch (e) {
      console.error(e);
      chatList.innerHTML = '<p class="error-message">Ошибка списка чатов</p>';
    }
  }

  const highlightSession = id => {
    document.querySelectorAll('#chat-list li')
      .forEach(li => li.classList.toggle('active', li.dataset.sessionId === id));
  };

  /* ----------  NEW CHAT ---------- */
  const startNewChat = () => {
    currentSessionId = 'default';
    localStorage.setItem('currentSessionId', 'default');
    highlightSession(null);
    showInitialSections();
    chatMessagesDisplay.innerHTML = '';
    userQuestionTextarea.value = chatInput.value = '';
    fileQuestionInput.value = '';
    clearFile();
  };

  /* ----------  SEND TEXT ---------- */
  async function sendText(msg) {
    msg = msg.trim();
    if (!msg) return;

    showChatArea();
    addMessage(msg, 'user-query'); // User queries are not Markdown
    userQuestionTextarea.value = chatInput.value = '';
    spinner.style.display = 'block';

    try {
      const res = await apiFetch('/ask', {
        method : 'POST',
        headers: {'Content-Type': 'application/json'},
        body   : JSON.stringify({question: msg, session_id: currentSessionId})
      });
      const data = await safeJson(res);
      spinner.style.display = 'none';

      if (data.error) {
        addMessage(`<p class="error-message">${data.error}</p>`, 'ai-response');
      } else {
        addMessage(data.answer, 'ai-response'); // AI answers are Markdown
        currentSessionId = data.session_id;
        localStorage.setItem('currentSessionId', currentSessionId);
        loadChatSessions();
      }
    } catch (e) {
      spinner.style.display = 'none';
      console.error(e);
      addMessage(`<p class="error-message">Ошибка: ${e.message}</p>`, 'ai-response');
    }
  }

  /* ----------  FILE UPLOAD ---------- */
  const clearFile = () => {
    currentFile      = null;
    fileInput.value  = '';
    fileChosenSpan.textContent = 'Файл не выбран';
    fileSubmitBtn.disabled = clearBtn.disabled = true;
  };

  const pickFile = file => {
    if (file.size > MAX_FILE_BYTES) {
      alert(`Файл > ${MAX_FILE_MB} МБ, выберите другой.`);
      clearFile();
      return;
    }
    currentFile = file;
    fileChosenSpan.textContent = file.name;
    fileSubmitBtn.disabled = clearBtn.disabled = false;
    fileQuestionInput.focus();
  };

  dragArea.ondragover = e => { e.preventDefault(); dragArea.classList.add('highlight'); };
  dragArea.ondragleave = () => dragArea.classList.remove('highlight');
  dragArea.ondrop = e => {
    e.preventDefault();
    dragArea.classList.remove('highlight');
    if (e.dataTransfer.files[0]) pickFile(e.dataTransfer.files[0]);
  };

  fileInput.onchange = e => e.target.files[0] && pickFile(e.target.files[0]);
  clearBtn.onclick   = clearFile;

  fileSubmitBtn.onclick = async e => {
    e.preventDefault();
    if (!currentFile) return;

    showChatArea();
    const q  = fileQuestionInput.value.trim();
    addMessage(
      `**Документ:** ${currentFile.name}` +
      (q ? `\n**Вопрос:** ${q}` : ''),
      'user-query'
    );
    fileSpinner.style.display = 'block';

    try {
      const fd = new FormData();
      fd.append('file', currentFile);
      fd.append('question', q);
      fd.append('session_id', currentSessionId);

      const res  = await apiFetch('/upload-document', {method: 'POST', body: fd});
      const data = await safeJson(res);
      fileSpinner.style.display = 'none';

      if (data.error) {
        addMessage(`<p class="error-message">${data.error}</p>`, 'ai-response');
      } else {
        const answerText = data.answer ?? data.response ?? data.text ?? '';
        if (answerText) addMessage(answerText, 'ai-response'); // AI answers are Markdown

        if (data.session_id) {
          currentSessionId = data.session_id;
          localStorage.setItem('currentSessionId', currentSessionId);
        }
        loadChatSessions();
        highlightSession(currentSessionId);
      }
    } catch (e) {
      fileSpinner.style.display = 'none';
      console.error(e);
      addMessage(`<p class="error-message">Ошибка: ${e.message}</p>`, 'ai-response');
    }
    clearFile();
  };

  /* ----------  EVENTS ---------- */
  submitBtn.onclick      = e => { e.preventDefault(); sendText(userQuestionTextarea.value); };
  sendButton.onclick     = e => { e.preventDefault(); sendText(chatInput.value); };
  newChatBtn.onclick     = startNewChat;

  chatInput.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendText(chatInput.value); } };
  userQuestionTextarea.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendText(userQuestionTextarea.value); } };

  /* ----------  INIT ---------- */
  showInitialSections();
  loadChatSessions().then(() => {
    if (
      currentSessionId !== 'default' && 
      document.querySelector(`[data-session-id="${currentSessionId}"]`)
    ) {
      loadChatHistory(currentSessionId);
      showChatArea();
    } else {
      addMessage(welcomeMessage, 'ai-response');
    }
  });
});
