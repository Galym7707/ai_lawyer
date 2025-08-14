/**
 * Connection Manager
 * Provides high-level connection management with integrated UI components
 * and automatic health monitoring for the legal AI assistant.
 */

class ConnectionManager {
  constructor(options = {}) {
    this.options = {
      environment: 'production',
      enableHealthCheck: true,
      enableStatusNotifications: true,
      enableConnectionOverlay: true,
      statusContainer: '#connection-status-container',
      healthIndicator: '#connection-health-indicator',
      connectionOverlay: '#connection-overlay',
      ...options
    };

    this.apiClient = null;
    this.statusUI = null;
    this.healthIndicator = null;
    this.overlay = null;
    this.isInitialized = false;
    this.lastHealthStatus = null;
    this.overlayVisible = false;
  }

  async initialize() {
    if (this.isInitialized) return;

    try {
      // Initialize API client with connection testing
      this.apiClient = new window.ConnectionUtils.EnhancedAPIClient({
        baseURL: '/api',
        connectionConfig: window.ConnectionUtils.CONNECTION_CONFIG.get(this.options.environment),
        statusContainer: this.options.enableStatusNotifications ? this.options.statusContainer : null,
        statusUIOptions: {
          showDetails: true,
          showRetryButton: true,
          autoHide: true,
          autoHideDelay: 3000
        }
      });

      // Initialize health indicator
      if (this.options.enableHealthCheck) {
        this.initializeHealthIndicator();
      }

      // Initialize connection overlay
      if (this.options.enableConnectionOverlay) {
        this.initializeConnectionOverlay();
      }

      // Set up global error handling
      this.setupGlobalErrorHandling();

      // Start health monitoring
      if (this.options.enableHealthCheck) {
        this.startHealthMonitoring();
      }

      // Initial connection test
      await this.testInitialConnection();

      this.isInitialized = true;
      console.log('✅ Connection Manager initialized successfully');

    } catch (error) {
      console.error('❌ Failed to initialize Connection Manager:', error);
      throw error;
    }
  }

  initializeHealthIndicator() {
    const element = document.querySelector(this.options.healthIndicator);
    if (!element) {
      console.warn('Health indicator element not found:', this.options.healthIndicator);
      return;
    }

    this.healthIndicator = {
      element,
      dot: element.querySelector('.connection-health-dot'),
      text: element.querySelector('.connection-health-text'),
      
      show() {
        element.classList.remove('hidden');
      },
      
      hide() {
        element.classList.add('hidden');
      },
      
      setStatus(status, message) {
        element.className = `connection-health-indicator ${status}`;
        this.text.textContent = message;
      }
    };
  }

  initializeConnectionOverlay() {
    const element = document.querySelector(this.options.connectionOverlay);
    if (!element) {
      console.warn('Connection overlay element not found:', this.options.connectionOverlay);
      return;
    }

    this.overlay = {
      element,
      
      show(title, description, onRetry, onCancel) {
        const titleEl = element.querySelector('.connection-overlay-title');
        const descEl = element.querySelector('.connection-overlay-description');
        const retryBtn = element.querySelector('.connection-overlay-retry');
        const cancelBtn = element.querySelector('.connection-overlay-cancel');

        if (titleEl) titleEl.textContent = title;
        if (descEl) descEl.textContent = description;

        if (retryBtn && onRetry) {
          retryBtn.onclick = onRetry;
        }
        if (cancelBtn && onCancel) {
          cancelBtn.onclick = onCancel;
        }

        element.classList.add('active');
        return element;
      },
      
      hide() {
        element.classList.remove('active');
      }
    };
  }

  setupGlobalErrorHandling() {
    // Enhanced error handling for API requests
    const originalApiFetch = window.apiFetch;
    if (originalApiFetch) {
      window.apiFetch = async (...args) => {
        try {
          return await originalApiFetch(...args);
        } catch (error) {
          this.handleConnectionError(error);
          throw error;
        }
      };
    }

    // Handle unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      if (event.reason && this.isConnectionError(event.reason)) {
        this.handleConnectionError(event.reason);
      }
    });
  }

  async testInitialConnection() {
    if (!this.apiClient) return;

    try {
      if (this.healthIndicator) {
        this.healthIndicator.setStatus('checking', 'Проверка подключения...');
        this.healthIndicator.show();
      }

      const result = await this.apiClient.testConnection();
      
      if (result.success) {
        this.updateHealthStatus(true, 'Подключение установлено');
      } else {
        this.updateHealthStatus(false, 'Ошибка подключения');
        this.showConnectionIssue(result);
      }

    } catch (error) {
      console.error('Initial connection test failed:', error);
      this.updateHealthStatus(false, 'Не удается подключиться');
      this.showConnectionIssue({ error, success: false });
    }
  }

  startHealthMonitoring() {
    if (!this.apiClient) return;

    this.apiClient.tester.addEventListener((event) => {
      switch (event.type) {
        case 'health_check_status_change':
          const isHealthy = event.isHealthy;
          const message = isHealthy ? 'Подключение активно' : 'Соединение потеряно';
          
          this.updateHealthStatus(isHealthy, message);
          
          if (!isHealthy && this.lastHealthStatus === true) {
            // Connection was lost
            this.showConnectionIssue(event.result);
          } else if (isHealthy && this.lastHealthStatus === false) {
            // Connection was restored
            this.hideConnectionIssue();
          }
          break;
      }
    });

    this.apiClient.startHealthCheck();
  }

  updateHealthStatus(isHealthy, message) {
    this.lastHealthStatus = isHealthy;

    if (this.healthIndicator) {
      const status = isHealthy ? 'healthy' : 'unhealthy';
      this.healthIndicator.setStatus(status, message);
      this.healthIndicator.show();
      
      // Auto-hide healthy status after delay
      if (isHealthy) {
        setTimeout(() => {
          if (this.lastHealthStatus === true && this.healthIndicator) {
            this.healthIndicator.hide();
          }
        }, 3000);
      }
    }
  }

  showConnectionIssue(result) {
    if (!this.overlay || this.overlayVisible) return;

    const errorType = result.errorType || window.ConnectionUtils.categorizeError(result.error);
    const errorInfo = window.ConnectionUtils.ERROR_MESSAGES[errorType];
    
    const title = errorInfo?.title || 'Проблема с подключением';
    const description = errorInfo?.description || 'Не удается подключиться к серверу.';

    this.overlay.show(
      title,
      description,
      () => this.retryConnection(),
      () => this.dismissOverlay()
    );

    this.overlayVisible = true;
  }

  hideConnectionIssue() {
    if (this.overlay && this.overlayVisible) {
      this.overlay.hide();
      this.overlayVisible = false;
    }
  }

  async retryConnection() {
    try {
      if (this.healthIndicator) {
        this.healthIndicator.setStatus('checking', 'Повторная проверка...');
        this.healthIndicator.show();
      }

      const result = await this.apiClient.testConnection();
      
      if (result.success) {
        this.updateHealthStatus(true, 'Подключение восстановлено');
        this.hideConnectionIssue();
      } else {
        this.updateHealthStatus(false, 'Подключение не удалось');
        // Keep overlay visible for manual retry
      }

    } catch (error) {
      console.error('Retry connection failed:', error);
      this.updateHealthStatus(false, 'Ошибка повторного подключения');
    }
  }

  dismissOverlay() {
    this.hideConnectionIssue();
  }

  isConnectionError(error) {
    if (!error) return false;
    
    const message = error.message?.toLowerCase() || '';
    const name = error.name?.toLowerCase() || '';
    
    return (
      name === 'typeerror' && message.includes('failed to fetch') ||
      message.includes('network') ||
      message.includes('connection') ||
      message.includes('timeout') ||
      name === 'aborterror' ||
      (error.status >= 500)
    );
  }

  handleConnectionError(error) {
    const errorType = window.ConnectionUtils.categorizeError(error);
    
    // Only show overlay for critical connection issues
    if (errorType === window.ConnectionUtils.ERROR_TYPES.NETWORK || 
        errorType === window.ConnectionUtils.ERROR_TYPES.TIMEOUT) {
      
      this.updateHealthStatus(false, 'Проблема с подключением');
      this.showConnectionIssue({ error, errorType, success: false });
    }
  }

  // Public API for integration with existing code
  async makeRequest(path, options = {}) {
    if (!this.apiClient) {
      throw new Error('Connection Manager not initialized');
    }

    return this.apiClient.request(path, options);
  }

  async get(path, options = {}) {
    return this.makeRequest(path, { ...options, method: 'GET' });
  }

  async post(path, data, options = {}) {
    return this.makeRequest(path, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  async upload(path, formData, options = {}) {
    if (!this.apiClient) {
      throw new Error('Connection Manager not initialized');
    }
    
    return this.apiClient.upload(path, formData, options);
  }

  dispose() {
    if (this.apiClient) {
      this.apiClient.dispose();
    }
    
    if (this.healthIndicator) {
      this.healthIndicator.hide();
    }
    
    if (this.overlay) {
      this.overlay.hide();
    }
    
    this.isInitialized = false;
  }
}

// Enhanced legacy API wrapper
class EnhancedAPIWrapper {
  constructor(connectionManager) {
    this.connectionManager = connectionManager;
  }

  async apiFetch(path, options = {}, retries = 2) {
    try {
      const result = await this.connectionManager.makeRequest(path, {
        ...options,
        maxRetries: retries
      });
      
      if (result.success) {
        return result.response;
      } else {
        throw result.error;
      }
    } catch (error) {
      console.error(`Enhanced API fetch error for ${path}:`, error);
      throw error;
    }
  }

  async safeJson(res) {
    const type = res.headers.get('content-type') || '';
    if (type.includes('application/json')) {
      return res.json();
    }
    
    const text = await res.text();
    throw new Error(text.slice(0, 300) || `HTTP ${res.status}`);
  }
}

// Initialize connection manager on DOM ready
document.addEventListener('DOMContentLoaded', async () => {
  try {
    // Detect environment (you might want to set this based on hostname or config)
    const environment = window.location.hostname === 'localhost' ? 'development' : 'production';
    
    window.connectionManager = new ConnectionManager({
      environment,
      enableHealthCheck: true,
      enableStatusNotifications: true,
      enableConnectionOverlay: true
    });

    await window.connectionManager.initialize();
    
    // Create enhanced API wrapper for backward compatibility
    const apiWrapper = new EnhancedAPIWrapper(window.connectionManager);
    
    // Override global API functions with enhanced versions
    window.apiFetch = apiWrapper.apiFetch.bind(apiWrapper);
    window.safeJson = apiWrapper.safeJson.bind(apiWrapper);
    
    console.log('🚀 Enhanced connection management active');
    
  } catch (error) {
    console.error('❌ Failed to initialize enhanced connection management:', error);
    
    // Fallback to basic functionality
    console.log('⚠️ Falling back to basic connection functionality');
  }
});

// Export for global access
window.ConnectionManager = ConnectionManager;
window.EnhancedAPIWrapper = EnhancedAPIWrapper;