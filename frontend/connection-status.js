/**
 * Connection Status Monitor
 * Monitors the backend API health and displays visual status indicators
 */

class ConnectionStatusMonitor {
    constructor(options = {}) {
        this.apiUrl = options.apiUrl || '/api/health';
        this.checkInterval = options.checkInterval || 30000; // 30 seconds
        this.retryInterval = options.retryInterval || 30000; // 30 seconds
        
        this.currentStatus = 'disconnected';
        this.intervalId = null;
        this.retryTimeoutId = null;
        
        this.statusElement = null;
        
        this.init();
    }

    init() {
        this.createStatusElement();
        this.insertStatusElement();
        this.startHealthChecks();
    }

    createStatusElement() {
        const statusContainer = document.createElement('div');
        statusContainer.id = 'connection-status';
        statusContainer.className = 'connection-status';
        
        const statusIcon = document.createElement('div');
        statusIcon.className = 'status-icon';
        
        const statusText = document.createElement('span');
        statusText.className = 'status-text';
        statusText.textContent = 'Проверка соединения...';
        
        statusContainer.appendChild(statusIcon);
        statusContainer.appendChild(statusText);
        
        this.statusElement = statusContainer;
    }

    insertStatusElement() {
        const header = document.querySelector('header');
        if (header) {
            header.appendChild(this.statusElement);
        } else {
            document.body.insertBefore(this.statusElement, document.body.firstChild);
        }
    }

    updateStatus(status, message = '') {
        if (!this.statusElement) return;
        
        this.currentStatus = status;
        
        const statusIcon = this.statusElement.querySelector('.status-icon');
        const statusText = this.statusElement.querySelector('.status-text');
        
        // Remove existing status classes
        this.statusElement.classList.remove('connected', 'disconnected', 'error', 'checking');
        
        // Add new status class and update content
        switch (status) {
            case 'connected':
                this.statusElement.classList.add('connected');
                statusText.textContent = 'Подключено';
                break;
            case 'disconnected':
                this.statusElement.classList.add('disconnected');
                statusText.textContent = 'Отключено';
                break;
            case 'error':
                this.statusElement.classList.add('error');
                statusText.textContent = message || 'Ошибка соединения';
                break;
            case 'checking':
                this.statusElement.classList.add('checking');
                statusText.textContent = 'Проверка...';
                break;
        }
    }

    async checkHealth() {
        try {
            this.updateStatus('checking');
            
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
            
            const response = await fetch(this.apiUrl, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                },
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (response.ok) {
                const data = await response.json();
                if (data.status === 'healthy') {
                    this.updateStatus('connected');
                    this.clearRetryTimeout();
                    return true;
                } else {
                    this.updateStatus('error', 'Сервер недоступен');
                    this.scheduleRetry();
                    return false;
                }
            } else {
                this.updateStatus('error', `HTTP ${response.status}`);
                this.scheduleRetry();
                return false;
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                this.updateStatus('error', 'Превышено время ожидания');
            } else {
                this.updateStatus('disconnected');
            }
            this.scheduleRetry();
            return false;
        }
    }

    scheduleRetry() {
        if (this.retryTimeoutId) {
            clearTimeout(this.retryTimeoutId);
        }
        
        // Only schedule retry if not already connected
        if (this.currentStatus !== 'connected') {
            this.retryTimeoutId = setTimeout(() => {
                this.checkHealth();
            }, this.retryInterval);
        }
    }

    clearRetryTimeout() {
        if (this.retryTimeoutId) {
            clearTimeout(this.retryTimeoutId);
            this.retryTimeoutId = null;
        }
    }

    startHealthChecks() {
        // Perform initial check
        this.checkHealth();
        
        // Schedule regular checks
        this.intervalId = setInterval(() => {
            this.checkHealth();
        }, this.checkInterval);
    }

    stopHealthChecks() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        this.clearRetryTimeout();
    }

    destroy() {
        this.stopHealthChecks();
        if (this.statusElement) {
            this.statusElement.remove();
        }
    }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize connection monitor
    window.connectionMonitor = new ConnectionStatusMonitor({
        apiUrl: window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1') 
            ? '/health' 
            : '/api/health',
        checkInterval: 30000,
        retryInterval: 30000
    });
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (window.connectionMonitor) {
        window.connectionMonitor.destroy();
    }
});