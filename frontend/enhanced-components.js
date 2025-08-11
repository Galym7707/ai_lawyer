/* Enhanced UI Components for Teg Legal Chat Application */

// Enhanced transition functions
function showInitialSectionsEnhanced() {
  const initialSections = document.getElementById('initial-sections');
  const currentChatContainer = document.getElementById('current-chat-container');
  
  currentChatContainer.classList.remove('fade-in');
  initialSections.classList.remove('fade-out');
  
  setTimeout(() => {
    initialSections.style.display = 'block';
    currentChatContainer.style.display = 'none';
    clearChatMessages();
    document.getElementById('userQuestion').value = '';
    document.getElementById('chat-input').value = '';
    clearFile();
  }, 200);
}

function showChatContainerEnhanced() {
  const initialSections = document.getElementById('initial-sections');
  const currentChatContainer = document.getElementById('current-chat-container');
  
  initialSections.classList.add('fade-out');
  
  setTimeout(() => {
    initialSections.style.display = 'none';
    currentChatContainer.style.display = 'flex';
    setTimeout(() => {
      currentChatContainer.classList.add('fade-in');
    }, 50);
  }, 400);
}

// Create skeleton loading components
function createSkeletonChatMessage(type = 'ai') {
  const skeleton = document.createElement('div');
  skeleton.classList.add('skeleton', 'skeleton-chat-message', type);
  return skeleton;
}

function createSkeletonSidebarItem() {
  const skeleton = document.createElement('div');
  skeleton.classList.add('skeleton', 'skeleton-sidebar-item');
  return skeleton;
}

function showChatSkeleton() {
  const chatMessagesDisplay = document.getElementById('chat-messages-display');
  const skeletonAi = createSkeletonChatMessage('ai');
  chatMessagesDisplay.appendChild(skeletonAi);
  return skeletonAi;
}

function showSidebarSkeleton() {
  const chatList = document.getElementById('chat-list');
  chatList.innerHTML = '';
  for (let i = 0; i < 3; i++) {
    const skeleton = createSkeletonSidebarItem();
    chatList.appendChild(skeleton);
  }
}

// Enhanced error display
function showError(type, title, description, actions = []) {
  const errorContainer = document.createElement('div');
  errorContainer.classList.add('error-container', `${type}-error`);

  const iconMap = {
    connection: 'fas fa-wifi',
    upload: 'fas fa-upload',
    api: 'fas fa-exclamation-triangle',
    validation: 'fas fa-info-circle'
  };

  errorContainer.innerHTML = `
    <i class="error-icon ${iconMap[type] || iconMap.api}"></i>
    <div class="error-content">
      <div class="error-title">${title}</div>
      <div class="error-description">${description}</div>
      ${actions.length > 0 ? `<div class="error-actions">${actions.map(action => 
        `<button class="error-action-btn ${action.primary ? 'primary' : ''}" onclick="${action.handler}">${action.text}</button>`
      ).join('')}</div>` : ''}
    </div>
    <button class="error-dismiss" onclick="this.parentElement.remove()">
      <i class="fas fa-times"></i>
    </button>
  `;

  // Add to chat display or main content
  const currentChatContainer = document.getElementById('current-chat-container');
  if (currentChatContainer.style.display === 'flex') {
    const chatMessagesDisplay = document.getElementById('chat-messages-display');
    chatMessagesDisplay.appendChild(errorContainer);
    chatMessagesDisplay.scrollTop = chatMessagesDisplay.scrollHeight;
  } else {
    const mainContent = document.querySelector('.main-content-area');
    mainContent.insertBefore(errorContainer, mainContent.firstChild);
  }

  // Auto-dismiss after 10 seconds for non-critical errors
  if (type !== 'connection') {
    setTimeout(() => {
      if (errorContainer.parentElement) {
        errorContainer.remove();
      }
    }, 10000);
  }

  return errorContainer;
}

// Connection status indicator
function createConnectionStatus() {
  const statusDiv = document.createElement('div');
  statusDiv.classList.add('connection-status');
  statusDiv.innerHTML = `
    <div class="connection-indicator"></div>
    <span class="connection-text">Подключение...</span>
  `;
  document.body.appendChild(statusDiv);
  return statusDiv;
}

let connectionStatus;

function updateConnectionStatus(isOnline) {
  if (!connectionStatus) {
    connectionStatus = createConnectionStatus();
  }
  
  connectionStatus.classList.toggle('online', isOnline);
  connectionStatus.classList.toggle('offline', !isOnline);
  connectionStatus.classList.add('show');
  
  const text = connectionStatus.querySelector('.connection-text');
  text.textContent = isOnline ? 'В сети' : 'Нет соединения';
  
  if (isOnline) {
    setTimeout(() => {
      connectionStatus.classList.remove('show');
    }, 3000);
  }
}

// Enhanced loading with skeleton
function showLoadingWithSkeleton(type = 'chat') {
  if (type === 'chat') {
    const skeleton = showChatSkeleton();
    return skeleton;
  } else if (type === 'sidebar') {
    showSidebarSkeleton();
  }
}

// Error handling helpers
function handleConnectionError(error) {
  showError('connection', 'Проблема с подключением', 
    'Не удается подключиться к серверу. Проверьте интернет-соединение.', 
    [
      { text: 'Повторить', handler: 'location.reload()', primary: true },
      { text: 'Подробнее', handler: 'console.log("Connection error:", error)' }
    ]);
}

function handleUploadError(error) {
  showError('upload', 'Ошибка загрузки файла', 
    `Не удалось загрузить файл: ${error.message || 'неизвестная ошибка'}`, 
    [
      { text: 'Попробовать снова', handler: 'document.getElementById("file-upload").click()', primary: true }
    ]);
}

function handleApiError(error) {
  showError('api', 'Ошибка API', 
    `Произошла ошибка при обработке запроса: ${error.message || 'неизвестная ошибка'}`, 
    [
      { text: 'Повторить', handler: 'location.reload()' }
    ]);
}

function handleValidationError(message) {
  showError('validation', 'Проверьте данные', message);
}

// Initialize enhanced components on DOM load
document.addEventListener('DOMContentLoaded', () => {
  // Initialize connection status monitoring
  connectionStatus = createConnectionStatus();
  
  // Monitor connection status
  window.addEventListener('online', () => updateConnectionStatus(true));
  window.addEventListener('offline', () => updateConnectionStatus(false));
  
  // Check initial connection status
  if (navigator.onLine) {
    updateConnectionStatus(true);
  } else {
    updateConnectionStatus(false);
  }
});

// Export functions for use in main script
window.enhancedComponents = {
  showInitialSectionsEnhanced,
  showChatContainerEnhanced,
  createSkeletonChatMessage,
  createSkeletonSidebarItem,
  showChatSkeleton,
  showSidebarSkeleton,
  showError,
  showLoadingWithSkeleton,
  handleConnectionError,
  handleUploadError,
  handleApiError,
  handleValidationError,
  updateConnectionStatus
};