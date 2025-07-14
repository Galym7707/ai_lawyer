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
  const homeLink             = document.getElementById('home-link'); // NEW: Home link element
  const aboutLinkNav         = document.getElementById('about-link-nav'); // NEW: About link in nav


  /* ----------  STATE ---------- */
  let currentSessionId = localStorage.getItem('currentSessionId') || 'default';
  let uploadedFile = null;

  /* ----------  HELPERS ---------- */
  function showInitialSections() {
    initialSections.style.display = 'block';
    currentChatContainer.style.display = 'none';
    clearChatMessages();
    userQuestionTextarea.value = ''; // Clear initial question area
    chatInput.value = ''; // Clear chat input area
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

  // Modified addMessage to check for existing HTML tags
  function addMessage(text, senderClass) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('chat-bubble', senderClass);

    // Check if the text already contains common HTML tags.
    // If it does, assume it's HTML and append directly.
    // Otherwise, parse as Markdown.
    const hasHtmlTags = /<[a-z][\s\S]*>/i.test(text);
    if (senderClass === 'ai-response' && !hasHtmlTags) {
        messageElement.innerHTML = marked.parse(text); // Still parse markdown if no HTML
    } else {
        messageElement.innerHTML = text; // Assume it's already HTML or plain text
    }
    
    chatMessagesDisplay.appendChild(messageElement);
    chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight; // Auto-scroll
  }

  async function loadChatSessions() {
    chatList.innerHTML = '<p>Загрузка истории...</p>';
    try {
      const res = await apiFetch('/get-all-sessions-summary');
      const data = await safeJson(res);
      chatList.innerHTML = ''; // Clear loading message

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
      chatList.innerHTML = `<p class="error-message">Ошибка загрузки истории: ${e.message}</p>`;
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
      addMessage(`<p class="error-message">Ошибка загрузки истории беседы: ${e.message}</p>`, 'ai-response');
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
    currentSessionId = crypto.randomUUID(); // Generate a new UUID for the session
    localStorage.setItem('currentSessionId', currentSessionId);
    showChatContainer();
    clearChatMessages();
    highlightSession(currentSessionId); // Highlight new session if it appears in list, otherwise clear highlight
    await loadChatSessions(); // Reload sessions to show new chat
    highlightSession(currentSessionId); // Re-highlight if it's there
  }

  function clearFile() {
    uploadedFile = null;
    fileUploadInput.value = '';
    fileNameDisplay.textContent = 'Файл не выбран';
    fileQuestionInput.value = '';
  }

  async function sendText(text) {
    showChatContainer();
    if (!text.trim() && !uploadedFile) return;

    // Show appropriate spinner and hide the other
    if (uploadedFile) {
        fileSpinner.style.display = 'block';
        spinner.style.display = 'none';
    } else {
        spinner.style.display = 'block';
        fileSpinner.style.display = 'none';
    }

    const messageText = uploadedFile ? fileQuestionInput.value || text : text; // Prioritize fileQuestionInput if file exists
    addMessage(messageText, 'user-message');
    userQuestionTextarea.value = '';
    chatInput.value = '';
    
    try {
      let res;
      if (uploadedFile) {
        const formData = new FormData();
        formData.append('file', uploadedFile);
        formData.append('question', messageText); // Send the text alongside the file
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

      // Hide spinners once first chunk arrives
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
        aiMessageElement.innerHTML = aiFullResponse; // Update in real-time
        chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight;
      }
      
      // After stream finishes, re-set innerHTML to ensure Markdown parsing (if needed)
      // This part now relies on the `addMessage` function logic which checks for HTML.
      // So, aiMessageElement.innerHTML = aiFullResponse should be sufficient if backend sends HTML.
      // If backend sends Markdown, the initial rendering will be raw Markdown, then this final
      // assignment might re-trigger browser's rendering, but for safety, we rely on addMessage.
      // For now, if the backend sends HTML, this will just re-assign the same HTML.
      // If the backend were to send Markdown and we wanted it parsed, we'd need to re-run marked.parse() here,
      // but based on instructions, backend sends HTML.

      if (aiFullResponse.includes("Ошибка:")) { // Simple error check
        aiMessageElement.innerHTML = `<p class="error-message">${aiFullResponse}</p>`;
      }

      loadChatSessions();
      highlightSession(currentSessionId);
      
    } catch (e) {
      spinner.style.display = 'none';
      fileSpinner.style.display = 'none';
      console.error(e);
      addMessage(`<p class="error-message">Ошибка: ${e.message}</p>`, 'ai-response');
    }
    clearFile(); // Clear file input after sending
  };

  /* ----------  EVENTS ---------- */
  submitBtn.onclick  = e => { e.preventDefault(); sendText(userQuestionTextarea.value); };
  sendButton.onclick = e => { e.preventDefault(); sendText(chatInput.value); };
  newChatBtn.onclick = startNewChat;

  chatInput.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendText(chatInput.value); } };
  userQuestionTextarea.onkeydown = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendText(userQuestionTextarea.value); } };

  fileUploadInput.onchange = (event) => {
    const file = event.target.files[0];
    if (file) {
      uploadedFile = file;
      fileNameDisplay.textContent = file.name;
    } else {
      clearFile();
    }
  };

  clearFileBtn.onclick = clearFile;

  // NEW: SPA Navigation handlers
  homeLink.onclick = e => {
    e.preventDefault();
    showInitialSections();
  };

  aboutLinkNav.onclick = e => {
    e.preventDefault();
    document.getElementById('about').scrollIntoView({ behavior: 'smooth' });
    showInitialSections(); // Ensure initial sections are visible if coming from chat
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
      startNewChat(); // Start a new chat if no valid session found
    }
  });
});
