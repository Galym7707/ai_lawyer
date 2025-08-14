/**
 * Connection Testing Utilities
 * Provides comprehensive connection testing with retry logic, error categorization,
 * and user-friendly status reporting for the legal AI assistant frontend.
 */

/* ========= CONFIGURATION ========= */
const CONNECTION_CONFIG = {
  // Default configuration - can be overridden
  defaults: {
    maxRetries: 3,
    baseTimeout: 5000,
    maxTimeout: 30000,
    retryDelayBase: 1000,
    retryDelayMax: 10000,
    exponentialBackoffMultiplier: 2,
    jitterFactor: 0.1,
    healthCheckInterval: 30000,
    connectionTimeout: 10000
  },
  
  // Environment-specific overrides
  environments: {
    development: {
      maxRetries: 2,
      baseTimeout: 3000,
      healthCheckInterval: 15000
    },
    staging: {
      maxRetries: 4,
      baseTimeout: 8000,
      healthCheckInterval: 45000
    },
    production: {
      maxRetries: 5,
      baseTimeout: 10000,
      maxTimeout: 45000,
      healthCheckInterval: 60000
    }
  },

  // Get merged configuration for current environment
  get(environment = 'production') {
    const envConfig = this.environments[environment] || {};
    return { ...this.defaults, ...envConfig };
  }
};

/* ========= ERROR TYPES AND CATEGORIZATION ========= */
const ERROR_TYPES = {
  NETWORK: 'network',
  TIMEOUT: 'timeout', 
  SERVER: 'server',
  CLIENT: 'client',
  UNKNOWN: 'unknown'
};

const ERROR_MESSAGES = {
  [ERROR_TYPES.NETWORK]: {
    title: 'Проблема с сетью',
    description: 'Не удается подключиться к серверу. Проверьте интернет-соединение.',
    icon: '🌐',
    suggestions: [
      'Проверьте интернет-соединение',
      'Попробуйте обновить страницу',
      'Убедитесь, что сервер доступен'
    ]
  },
  [ERROR_TYPES.TIMEOUT]: {
    title: 'Превышено время ожидания',
    description: 'Сервер слишком долго отвечает на запрос.',
    icon: '⏱️',
    suggestions: [
      'Попробуйте еще раз через несколько секунд',
      'Проверьте стабильность соединения',
      'Возможно, сервер перегружен'
    ]
  },
  [ERROR_TYPES.SERVER]: {
    title: 'Ошибка сервера',
    description: 'Сервер вернул ошибку при обработке запроса.',
    icon: '🔧',
    suggestions: [
      'Повторите попытку через несколько минут',
      'Проблема на стороне сервера',
      'Обратитесь в поддержку, если проблема продолжается'
    ]
  },
  [ERROR_TYPES.CLIENT]: {
    title: 'Ошибка клиента',
    description: 'Некорректный запрос или проблема с данными.',
    icon: '❌',
    suggestions: [
      'Проверьте введенные данные',
      'Убедитесь в корректности запроса',
      'Попробуйте обновить страницу'
    ]
  },
  [ERROR_TYPES.UNKNOWN]: {
    title: 'Неизвестная ошибка',
    description: 'Произошла неожиданная ошибка.',
    icon: '❓',
    suggestions: [
      'Попробуйте обновить страницу',
      'Повторите попытку',
      'Обратитесь в поддержку'
    ]
  }
};

/* ========= UTILITY FUNCTIONS ========= */
function categorizeError(error) {
  if (!error) return ERROR_TYPES.UNKNOWN;
  
  const message = error.message?.toLowerCase() || '';
  const name = error.name?.toLowerCase() || '';
  
  // Network errors
  if (name === 'typeerror' && message.includes('failed to fetch')) {
    return ERROR_TYPES.NETWORK;
  }
  if (message.includes('network') || message.includes('connection')) {
    return ERROR_TYPES.NETWORK;
  }
  
  // Timeout errors
  if (name === 'aborterror' || message.includes('timeout')) {
    return ERROR_TYPES.TIMEOUT;
  }
  
  // Server errors (5xx)
  if (error.status >= 500) {
    return ERROR_TYPES.SERVER;
  }
  
  // Client errors (4xx)
  if (error.status >= 400 && error.status < 500) {
    return ERROR_TYPES.CLIENT;
  }
  
  return ERROR_TYPES.UNKNOWN;
}

function calculateRetryDelay(attempt, config) {
  const baseDelay = config.retryDelayBase;
  const multiplier = config.exponentialBackoffMultiplier;
  const jitter = config.jitterFactor;
  
  // Exponential backoff: baseDelay * (multiplier ^ attempt)
  const exponentialDelay = baseDelay * Math.pow(multiplier, attempt);
  
  // Add jitter to prevent thundering herd
  const jitterAmount = exponentialDelay * jitter * Math.random();
  const finalDelay = exponentialDelay + jitterAmount;
  
  // Cap at maximum delay
  return Math.min(finalDelay, config.retryDelayMax);
}

function createTimeoutPromise(timeoutMs, controller) {
  return new Promise((_, reject) => {
    const timeoutId = setTimeout(() => {
      controller.abort();
      const error = new Error(`Request timeout after ${timeoutMs}ms`);
      error.name = 'AbortError';
      reject(error);
    }, timeoutMs);
    
    // Clear timeout if the controller is aborted for other reasons
    controller.signal.addEventListener('abort', () => {
      clearTimeout(timeoutId);
    });
  });
}

/* ========= CORE CONNECTION TESTING ========= */
class ConnectionTester {
  constructor(config = {}) {
    this.config = { ...CONNECTION_CONFIG.get(), ...config };
    this.listeners = new Set();
    this.lastConnectionStatus = null;
    this.isHealthChecking = false;
    this.healthCheckTimer = null;
  }

  addEventListener(callback) {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  notifyListeners(event) {
    this.listeners.forEach(listener => {
      try {
        listener(event);
      } catch (error) {
        console.error('Error in connection event listener:', error);
      }
    });
  }

  async testConnection(url = '/api/health', options = {}) {
    const controller = new AbortController();
    const timeoutMs = options.timeout || this.config.baseTimeout;
    
    try {
      const timeoutPromise = createTimeoutPromise(timeoutMs, controller);
      
      const fetchPromise = fetch(url, {
        method: 'GET',
        signal: controller.signal,
        credentials: 'include',
        cache: 'no-cache',
        ...options
      });

      const response = await Promise.race([fetchPromise, timeoutPromise]);
      
      if (!response.ok) {
        const error = new Error(`HTTP ${response.status}: ${response.statusText}`);
        error.status = response.status;
        error.response = response;
        throw error;
      }

      return { success: true, response, latency: Date.now() };
    } catch (error) {
      const errorType = categorizeError(error);
      return {
        success: false,
        error,
        errorType,
        message: ERROR_MESSAGES[errorType]
      };
    }
  }

  async testConnectionWithRetry(url = '/api/health', options = {}) {
    const startTime = Date.now();
    let lastError = null;
    let attempt = 0;

    const retryOptions = {
      maxRetries: options.maxRetries ?? this.config.maxRetries,
      onRetry: options.onRetry || (() => {})
    };

    this.notifyListeners({
      type: 'connection_test_start',
      url,
      maxRetries: retryOptions.maxRetries
    });

    while (attempt <= retryOptions.maxRetries) {
      try {
        this.notifyListeners({
          type: 'connection_attempt',
          attempt: attempt + 1,
          maxRetries: retryOptions.maxRetries + 1,
          url
        });

        const result = await this.testConnection(url, options);
        
        if (result.success) {
          const totalTime = Date.now() - startTime;
          const successResult = {
            ...result,
            attempts: attempt + 1,
            totalTime,
            retriesUsed: attempt
          };

          this.notifyListeners({
            type: 'connection_success',
            result: successResult
          });

          return successResult;
        }

        lastError = result.error;
        
        // Don't retry client errors (4xx) except for specific cases
        if (result.errorType === ERROR_TYPES.CLIENT && 
            result.error.status !== 429) { // Don't retry except rate limiting
          break;
        }

      } catch (error) {
        lastError = error;
      }

      // If we've exhausted retries, break
      if (attempt >= retryOptions.maxRetries) {
        break;
      }

      // Calculate delay and wait before next attempt
      const delay = calculateRetryDelay(attempt, this.config);
      
      this.notifyListeners({
        type: 'connection_retry',
        attempt: attempt + 1,
        delay,
        error: lastError
      });

      await retryOptions.onRetry(attempt + 1, delay, lastError);
      await new Promise(resolve => setTimeout(resolve, delay));
      
      attempt++;
    }

    // All retries failed
    const errorType = categorizeError(lastError);
    const totalTime = Date.now() - startTime;
    const failureResult = {
      success: false,
      error: lastError,
      errorType,
      message: ERROR_MESSAGES[errorType],
      attempts: attempt + 1,
      totalTime
    };

    this.notifyListeners({
      type: 'connection_failure',
      result: failureResult
    });

    return failureResult;
  }

  startHealthCheck(url = '/api/health') {
    if (this.isHealthChecking) {
      return;
    }

    this.isHealthChecking = true;
    
    const runHealthCheck = async () => {
      if (!this.isHealthChecking) return;

      try {
        const result = await this.testConnection(url, {
          timeout: this.config.connectionTimeout
        });

        const isHealthy = result.success;
        
        // Only notify if status changed
        if (this.lastConnectionStatus !== isHealthy) {
          this.lastConnectionStatus = isHealthy;
          this.notifyListeners({
            type: 'health_check_status_change',
            isHealthy,
            result
          });
        }

      } catch (error) {
        console.error('Health check error:', error);
      }

      // Schedule next check
      if (this.isHealthChecking) {
        this.healthCheckTimer = setTimeout(runHealthCheck, this.config.healthCheckInterval);
      }
    };

    // Start immediately
    runHealthCheck();
  }

  stopHealthCheck() {
    this.isHealthChecking = false;
    if (this.healthCheckTimer) {
      clearTimeout(this.healthCheckTimer);
      this.healthCheckTimer = null;
    }
  }

  dispose() {
    this.stopHealthCheck();
    this.listeners.clear();
  }
}

/* ========= UI COMPONENTS ========= */
class ConnectionStatusUI {
  constructor(container, options = {}) {
    this.container = typeof container === 'string' 
      ? document.querySelector(container) 
      : container;
    
    this.options = {
      showDetails: true,
      showRetryButton: true,
      autoHide: false,
      autoHideDelay: 5000,
      ...options
    };

    this.currentStatus = null;
    this.isVisible = false;
    this.hideTimer = null;

    this.createUI();
  }

  createUI() {
    this.element = document.createElement('div');
    this.element.className = 'connection-status-container';
    this.element.style.display = 'none';

    this.element.innerHTML = `
      <div class="connection-status-content">
        <div class="connection-status-header">
          <span class="connection-status-icon"></span>
          <span class="connection-status-title"></span>
          <button class="connection-status-close" title="Закрыть">×</button>
        </div>
        <div class="connection-status-body">
          <p class="connection-status-description"></p>
          <div class="connection-status-details" style="display: none;">
            <div class="connection-status-attempts"></div>
            <div class="connection-status-time"></div>
            <div class="connection-status-suggestions"></div>
          </div>
          <div class="connection-status-actions">
            <button class="connection-retry-btn">Повторить</button>
            <button class="connection-details-toggle">Подробности</button>
          </div>
        </div>
        <div class="connection-status-progress">
          <div class="connection-status-progress-bar"></div>
        </div>
      </div>
    `;

    this.container.appendChild(this.element);
    this.bindEvents();
  }

  bindEvents() {
    const closeBtn = this.element.querySelector('.connection-status-close');
    const retryBtn = this.element.querySelector('.connection-retry-btn');
    const detailsToggle = this.element.querySelector('.connection-details-toggle');

    closeBtn.onclick = () => this.hide();
    retryBtn.onclick = () => this.onRetry && this.onRetry();
    detailsToggle.onclick = () => this.toggleDetails();
  }

  show(status, options = {}) {
    this.currentStatus = status;
    
    const icon = this.element.querySelector('.connection-status-icon');
    const title = this.element.querySelector('.connection-status-title');
    const description = this.element.querySelector('.connection-status-description');
    const retryBtn = this.element.querySelector('.connection-retry-btn');

    // Set status class
    this.element.className = `connection-status-container connection-status-${status.type || 'info'}`;

    // Set content based on status
    if (status.type === 'success') {
      icon.textContent = '✅';
      title.textContent = 'Соединение установлено';
      description.textContent = `Подключение к серверу восстановлено за ${status.totalTime || 0}мс`;
      retryBtn.style.display = 'none';
    } else if (status.type === 'error') {
      const errorInfo = status.message || ERROR_MESSAGES[ERROR_TYPES.UNKNOWN];
      icon.textContent = errorInfo.icon;
      title.textContent = errorInfo.title;
      description.textContent = errorInfo.description;
      retryBtn.style.display = this.options.showRetryButton ? 'inline-block' : 'none';
      
      this.updateErrorDetails(status);
    } else if (status.type === 'testing') {
      icon.textContent = '🔄';
      title.textContent = 'Проверка соединения...';
      description.textContent = `Попытка ${status.attempt || 1} из ${status.maxAttempts || 1}`;
      retryBtn.style.display = 'none';
      
      this.updateProgress(status.attempt, status.maxAttempts);
    }

    this.element.style.display = 'block';
    this.isVisible = true;

    // Auto-hide for success messages
    if (this.options.autoHide && status.type === 'success') {
      this.scheduleHide();
    }

    // Animate in
    requestAnimationFrame(() => {
      this.element.classList.add('connection-status-visible');
    });
  }

  updateErrorDetails(status) {
    if (!this.options.showDetails) return;

    const details = this.element.querySelector('.connection-status-details');
    const attempts = this.element.querySelector('.connection-status-attempts');
    const time = this.element.querySelector('.connection-status-time');
    const suggestions = this.element.querySelector('.connection-status-suggestions');

    if (status.attempts) {
      attempts.textContent = `Попыток подключения: ${status.attempts}`;
      attempts.style.display = 'block';
    }

    if (status.totalTime) {
      time.textContent = `Общее время: ${status.totalTime}мс`;
      time.style.display = 'block';
    }

    if (status.message && status.message.suggestions) {
      const suggestionsList = status.message.suggestions
        .map(s => `<li>${s}</li>`)
        .join('');
      suggestions.innerHTML = `<strong>Рекомендации:</strong><ul>${suggestionsList}</ul>`;
      suggestions.style.display = 'block';
    }
  }

  updateProgress(current, total) {
    const progressBar = this.element.querySelector('.connection-status-progress-bar');
    const progress = total > 0 ? (current / total) * 100 : 0;
    progressBar.style.width = `${progress}%`;
  }

  toggleDetails() {
    const details = this.element.querySelector('.connection-status-details');
    const toggle = this.element.querySelector('.connection-details-toggle');
    
    if (details.style.display === 'none') {
      details.style.display = 'block';
      toggle.textContent = 'Скрыть подробности';
    } else {
      details.style.display = 'none';
      toggle.textContent = 'Подробности';
    }
  }

  hide() {
    if (!this.isVisible) return;

    this.element.classList.remove('connection-status-visible');
    
    setTimeout(() => {
      this.element.style.display = 'none';
      this.isVisible = false;
    }, 300); // Match CSS transition

    if (this.hideTimer) {
      clearTimeout(this.hideTimer);
      this.hideTimer = null;
    }
  }

  scheduleHide() {
    if (this.hideTimer) {
      clearTimeout(this.hideTimer);
    }
    
    this.hideTimer = setTimeout(() => {
      this.hide();
    }, this.options.autoHideDelay);
  }

  setRetryHandler(handler) {
    this.onRetry = handler;
  }

  destroy() {
    if (this.hideTimer) {
      clearTimeout(this.hideTimer);
    }
    if (this.element && this.element.parentNode) {
      this.element.parentNode.removeChild(this.element);
    }
  }
}

/* ========= ENHANCED API WRAPPER ========= */
class EnhancedAPIClient {
  constructor(options = {}) {
    this.baseURL = options.baseURL || '/api';
    this.tester = new ConnectionTester(options.connectionConfig);
    this.statusUI = null;
    
    if (options.statusContainer) {
      this.statusUI = new ConnectionStatusUI(options.statusContainer, options.statusUIOptions);
      this.setupStatusUIIntegration();
    }

    this.defaultOptions = {
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      },
      ...options.defaultFetchOptions
    };
  }

  setupStatusUIIntegration() {
    this.tester.addEventListener((event) => {
      switch (event.type) {
        case 'connection_test_start':
          this.statusUI.show({
            type: 'testing',
            attempt: 1,
            maxAttempts: event.maxRetries + 1
          });
          break;
          
        case 'connection_attempt':
          this.statusUI.show({
            type: 'testing',
            attempt: event.attempt,
            maxAttempts: event.maxRetries
          });
          break;
          
        case 'connection_success':
          this.statusUI.show({
            type: 'success',
            ...event.result
          });
          break;
          
        case 'connection_failure':
          this.statusUI.show({
            type: 'error',
            ...event.result
          });
          break;
      }
    });

    if (this.statusUI) {
      this.statusUI.setRetryHandler(() => {
        this.testConnection();
      });
    }
  }

  async testConnection() {
    return this.tester.testConnectionWithRetry();
  }

  async request(path, options = {}) {
    const url = `${this.baseURL}${path}`;
    const mergedOptions = { ...this.defaultOptions, ...options };

    // Test connection first if this is the first request or if explicitly requested
    if (options.testConnection) {
      const connectionResult = await this.tester.testConnectionWithRetry();
      if (!connectionResult.success) {
        throw new Error(`Connection failed: ${connectionResult.message.description}`);
      }
    }

    return this.tester.testConnectionWithRetry(url, {
      method: options.method || 'GET',
      ...mergedOptions,
      onRetry: async (attempt, delay, error) => {
        // Custom retry logic can be added here
        console.log(`Retrying API request (attempt ${attempt}) after ${delay}ms:`, error.message);
      }
    });
  }

  // Convenience methods
  async get(path, options = {}) {
    return this.request(path, { ...options, method: 'GET' });
  }

  async post(path, data, options = {}) {
    return this.request(path, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  async upload(path, formData, options = {}) {
    const uploadOptions = { ...options };
    delete uploadOptions.headers; // Let browser set Content-Type for FormData
    
    return this.request(path, {
      ...uploadOptions,
      method: 'POST',
      body: formData
    });
  }

  startHealthCheck() {
    this.tester.startHealthCheck();
  }

  stopHealthCheck() {
    this.tester.stopHealthCheck();
  }

  dispose() {
    this.tester.dispose();
    if (this.statusUI) {
      this.statusUI.destroy();
    }
  }
}

/* ========= GLOBAL EXPORTS ========= */
window.ConnectionUtils = {
  ConnectionTester,
  ConnectionStatusUI,
  EnhancedAPIClient,
  CONNECTION_CONFIG,
  ERROR_TYPES,
  ERROR_MESSAGES,
  categorizeError,
  calculateRetryDelay
};

// Backward compatibility
window.connectionTester = new ConnectionTester();
window.enhancedAPI = new EnhancedAPIClient();