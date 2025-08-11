/* =========   AI RESPONSE FORMATTER   ========= */
function formatAIResponse(text) {
  // Convert markdown-style formatting to HTML
  let formatted = text;

  // Code blocks (```code```)
  formatted = formatted.replace(/```([\s\S]*?)```/g, '<pre class="code-block"><code>$1</code></pre>');
  
  // Inline code (`code`)
  formatted = formatted.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
  
  // Bold text (**text** or __text__)
  formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong class="bold-text">$1</strong>');
  formatted = formatted.replace(/__(.*?)__/g, '<strong class="bold-text">$1</strong>');
  
  // Italic text (*text* or _text_)
  formatted = formatted.replace(/\*(.*?)\*/g, '<em class="italic-text">$1</em>');
  formatted = formatted.replace(/_(.*?)_/g, '<em class="italic-text">$1</em>');

  // Headers (## Header)
  formatted = formatted.replace(/^### (.*$)/gm, '<h3 class="header-3">$1</h3>');
  formatted = formatted.replace(/^## (.*$)/gm, '<h2 class="header-2">$1</h2>');
  formatted = formatted.replace(/^# (.*$)/gm, '<h1 class="header-1">$1</h1>');

  // Lists (- item or * item)
  formatted = formatted.replace(/^[-*] (.*$)/gm, '<li class="list-item">$1</li>');
  formatted = formatted.replace(/(<li class="list-item">.*<\/li>)/gs, '<ul class="formatted-list">$1</ul>');

  // Numbered lists (1. item)
  formatted = formatted.replace(/^\d+\. (.*$)/gm, '<li class="numbered-item">$1</li>');
  formatted = formatted.replace(/(<li class="numbered-item">.*<\/li>)/gs, '<ol class="numbered-list">$1</ol>');

  // Content type detection and semantic formatting
  const lines = formatted.split('\n');
  const processedLines = lines.map(line => {
    const trimmed = line.trim();
    
    // Warning/Important content (keywords that indicate warnings)
    if (/^(внимание|важно|предупреждение|осторожно|опасность|предостережение|warning|important|caution|danger|note)/i.test(trimmed) ||
        /(!{2,}|⚠️|⛔|🚨)/.test(trimmed)) {
      return `<div class="content-warning">${line}</div>`;
    }
    
    // Positive content (success, completion, good news)
    if (/^(отлично|хорошо|успешно|готово|завершено|успех|правильно|верно|положительно|excellent|good|success|completed|correct|positive)/i.test(trimmed) ||
        /✓|✅|👍|😊|🎉/.test(trimmed)) {
      return `<div class="content-positive">${line}</div>`;
    }
    
    // References (articles, laws, documents, citations)
    if (/^(статья|закон|кодекс|постановление|указ|пункт|часть|глава|раздел|приложение|документ|ссылка|источник|article|law|code|section|chapter|document|reference)/i.test(trimmed) ||
        /\d+\.\d+|\d+\/\d+|№\s*\d+|п\.\s*\d+|ст\.\s*\d+|гл\.\s*\d+/.test(trimmed) ||
        /(https?:\/\/|www\.|\.kz|\.ru|\.com)/.test(trimmed)) {
      return `<div class="content-reference">${line}</div>`;
    }
    
    return line;
  });

  formatted = processedLines.join('\n');
  
  // Convert line breaks to HTML
  formatted = formatted.replace(/\n/g, '<br>');
  
  return formatted;
}

/* =========   AI RESPONSE FORMATTER   ========= */
function formatAIResponse(text) {
  // Convert markdown-style formatting to HTML
  let formatted = text;

  // Code blocks (```code```)
  formatted = formatted.replace(/```([\s\S]*?)```/g, '<pre class="code-block"><code>$1</code></pre>');
  
  // Inline code (`code`)
  formatted = formatted.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
  
  // Bold text (**text** or __text__)
  formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong class="bold-text">$1</strong>');
  formatted = formatted.replace(/__(.*?)__/g, '<strong class="bold-text">$1</strong>');
  
  // Italic text (*text* or _text_)
  formatted = formatted.replace(/\*(.*?)\*/g, '<em class="italic-text">$1</em>');
  formatted = formatted.replace(/_(.*?)_/g, '<em class="italic-text">$1</em>');

  // Headers (## Header)
  formatted = formatted.replace(/^### (.*$)/gm, '<h3 class="header-3">$1</h3>');
  formatted = formatted.replace(/^## (.*$)/gm, '<h2 class="header-2">$1</h2>');
  formatted = formatted.replace(/^# (.*$)/gm, '<h1 class="header-1">$1</h1>');

  // Lists (- item or * item)
  formatted = formatted.replace(/^[-*] (.*$)/gm, '<li class="list-item">$1</li>');
  formatted = formatted.replace(/(<li class="list-item">.*<\/li>)/gs, '<ul class="formatted-list">$1</ul>');

  // Numbered lists (1. item)
  formatted = formatted.replace(/^\d+\. (.*$)/gm, '<li class="numbered-item">$1</li>');
  formatted = formatted.replace(/(<li class="numbered-item">.*<\/li>)/gs, '<ol class="numbered-list">$1</ol>');

  // Content type detection and semantic formatting
  const lines = formatted.split('\n');
  const processedLines = lines.map(line => {
    const trimmed = line.trim();
    
    // Warning/Important content (keywords that indicate warnings)
    if (/^(внимание|важно|предупреждение|осторожно|опасность|предостережение|warning|important|caution|danger|note)/i.test(trimmed) ||
        /(!{2,}|⚠️|⛔|🚨)/.test(trimmed)) {
      return `<div class="content-warning">${line}</div>`;
    }
    
    // Positive content (success, completion, good news)
    if (/^(отлично|хорошо|успешно|готово|завершено|успех|правильно|верно|положительно|excellent|good|success|completed|correct|positive)/i.test(trimmed) ||
        /✓|✅|👍|😊|🎉/.test(trimmed)) {
      return `<div class="content-positive">${line}</div>`;
    }
    
    // References (articles, laws, documents, citations)
    if (/^(статья|закон|кодекс|постановление|указ|пункт|часть|глава|раздел|приложение|документ|ссылка|источник|article|law|code|section|chapter|document|reference)/i.test(trimmed) ||
        /\d+\.\d+|\d+\/\d+|№\s*\d+|п\.\s*\d+|ст\.\s*\d+|гл\.\s*\d+/.test(trimmed) ||
        /(https?:\/\/|www\.|\.kz|\.ru|\.com)/.test(trimmed)) {
      return `<div class="content-reference">${line}</div>`;
    }
    
    return line;
  });

  formatted = processedLines.join('\n');
  
  // Convert line breaks to HTML
  formatted = formatted.replace(/\n/g, '<br>');
  
  return formatted;
}

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
        await new Promise(resolve =>
          setTimeout(resolve, 1000 * (i + 1))
        );
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

/* =========   DEVICE IDENTIFIER   ========= */
function generateDeviceId() {
  const userAgent = navigator.userAgent;
  const randomString = crypto.randomUUID();
  return btoa(userAgent + randomString).replace(/=/g, '');
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
  const fileInfo             = document.getElementById('file-info');
  const uploadButton         = document.getElementById('upload-button');

  const chatFileUploadInput  = document.getElementById('chat-file-upload');
  const attachFileButton     = document.getElementById('attach-file-button');

  const homeLink             = document.getElementById('home-link');
  const aboutLinkNav         = document.getElementById('about-link-nav');

  /* ----------  STATE ---------- */
  let deviceId = sessionStorage.getItem('deviceId');
  if (!deviceId) {
    deviceId = generateDeviceId();
    sessionStorage.setItem('deviceId', deviceId);
  }

  let currentSessionId = sessionStorage.getItem(`sessionId_${deviceId}`);
  if (!currentSessionId) {
    currentSessionId = `${deviceId}_${crypto.randomUUID()}`;
    sessionStorage.setItem(`sessionId_${deviceId}`, currentSessionId);
  }
  let uploadedFile = null;

  /* ----------  FILE UPLOAD IN CHAT ---------- */
  attachFileButton.onclick = () => {
    chatFileUploadInput.click();
  };
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
      const res  = await apiFetch('/get-all-sessions-summary');
      const data = await safeJson(res);

      chatList.innerHTML = '';
      const template = document.getElementById('chat-item-template');

      if (data.sessions && data.sessions.length > 0) {
        const deviceSessions = data.sessions.filter(session => session.id.startsWith(deviceId));
        if (deviceSessions.length > 0) {
          deviceSessions.forEach(session => {
            let li;
            if (template) {
              li = template.cloneNode(true);
              li.id = '';
              li.style.display = 'flex';
            } else {
              li = document.createElement('li');
              li.classList.add('chat-list-item');
              const spanTitle = document.createElement('span');
              spanTitle.classList.add('chat-title');
              li.appendChild(spanTitle);
              const delBtn = document.createElement('button');
              delBtn.classList.add('delete-chat-btn');
              delBtn.type = 'button';
              delBtn.innerHTML = '<i class="fas fa-trash"></i>';
              li.appendChild(delBtn);
            }

            li.dataset.sessionId = session.id;
            const spanTitle = li.querySelector('.chat-title');
            spanTitle.textContent = session.title;
            spanTitle.onclick = () => loadConversation(session.id);

            const delBtn = li.querySelector('.delete-chat-btn');
            delBtn.onclick = async (e) => {
              e.stopPropagation();
              if (confirm('Удалить этот чат?')) {
                try {
                  await apiFetch(`/delete-session?session_id=${session.id}`, { method:'DELETE' });
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

            chatList.appendChild(li);
          });
        } else {
          chatList.innerHTML = '<p>История чатов пуста.</p>';
        }
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
    sessionStorage.setItem(`sessionId_${deviceId}`, currentSessionId);
    showChatContainer();
    clearChatMessages();
    highlightSession(sessionId);
    try {
      const res  = await apiFetch(`/get-history?session_id=${sessionId}`);
      const data = await safeJson(res);
      if (data.history) {
        data.history.forEach(msg => {
          const formattedContent = msg.role === 'user' ? msg.content : formatAIResponse(msg.content);
          addMessage(formattedContent, msg.role === 'user' ? 'user-message' : 'ai-response');
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
    currentSessionId = `${deviceId}_${crypto.randomUUID()}`;
    sessionStorage.setItem(`sessionId_${deviceId}`, currentSessionId);
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
    if (chatFileUploadInput) {
      chatFileUploadInput.value = '';
    }
  }

  async function sendText(text) {
    showChatContainer();
    if (!text.trim() && !uploadedFile) return;

    if (uploadedFile) {
      if (fileSpinner) fileSpinner.style.display = 'block';
      if (spinner)     spinner.style.display     = 'none';
    } else {
      if (spinner)     spinner.style.display     = 'block';
      if (fileSpinner) fileSpinner.style.display = 'none';
    }

    const messageText = uploadedFile ? fileQuestionInput.value || text : text;
    addMessage(messageText, 'user-message');
    userQuestionTextarea.value = '';
    chatInput.value           = '';

    const aiMessageElement = document.createElement('div');
    aiMessageElement.classList.add('chat-bubble','ai-response');
    aiMessageElement.textContent = uploadedFile
      ? 'ИИ-юрист анализирует ваш документ…'
      : 'ИИ-юрист анализирует ваш запрос…';
    chatMessagesDisplay.appendChild(aiMessageElement);
    chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight;

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

      if (spinner)     spinner.style.display     = 'none';
      if (fileSpinner) fileSpinner.style.display = 'none';

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let aiFullResponse = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        aiFullResponse += chunk;
        aiMessageElement.innerHTML = formatAIResponse(aiFullResponse);
        chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight;
      }

      if (aiFullResponse.includes("Ошибка:")) {
        aiMessageElement.innerHTML = `<p class="error-message">${aiFullResponse}</p>`;
      }

      await loadChatSessions();
      highlightSession(currentSessionId);

    } catch (e) {
      if (spinner)     spinner.style.display     = 'none';
      if (fileSpinner) fileSpinner.style.display = 'none';
      console.error(e);
      aiMessageElement.innerHTML =
        `<p class="error-message">Ошибка: ${e.message}. Проверьте подключение к серверу.</p>`;
    }

    clearFile();
  }

  /* ----------  EVENTS ---------- */
  submitBtn.onclick = e => {
    e.preventDefault();
    sendText(userQuestionTextarea.value);
  };
  sendButton.onclick = e => {
    e.preventDefault();
    sendText(chatInput.value);
  };
  newChatBtn.onclick = startNewChat;
  chatInput.onkeydown = e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendText(chatInput.value);
    }
  };
  userQuestionTextarea.onkeydown = e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendText(userQuestionTextarea.value);
    }
  };
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
  if (clearFileBtn) {
    clearFileBtn.onclick = clearFile;
  }
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
    const savedId   = sessionStorage.getItem(`sessionId_${deviceId}`);
    const existingLi = savedId && document.querySelector(`[data-session-id="${savedId}"]`);
    if (existingLi) {
      loadConversation(savedId);
    } else {
      startNewChat();
    }
  });
});
