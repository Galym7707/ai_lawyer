/**
 * Connection Testing Demo and Configuration Panel
 * Provides a UI for testing connection utilities and configuring settings
 */

class ConnectionDemo {
  constructor() {
    this.isVisible = false;
    this.testResults = [];
    this.currentTest = null;
    this.config = { ...window.ConnectionUtils.CONNECTION_CONFIG.defaults };
  }

  createDemoPanel() {
    const panel = document.createElement('div');
    panel.id = 'connection-demo-panel';
    panel.className = 'connection-demo-panel hidden';
    panel.innerHTML = `
      <div class="demo-panel-header">
        <h3>Connection Testing & Configuration</h3>
        <button class="demo-close-btn" onclick="connectionDemo.hide()">×</button>
      </div>
      
      <div class="demo-tabs">
        <button class="demo-tab active" onclick="connectionDemo.showTab('test')">Testing</button>
        <button class="demo-tab" onclick="connectionDemo.showTab('config')">Configuration</button>
        <button class="demo-tab" onclick="connectionDemo.showTab('results')">Results</button>
      </div>

      <div class="demo-tab-content">
        <!-- Testing Tab -->
        <div id="demo-test-tab" class="demo-tab-panel active">
          <div class="demo-section">
            <h4>Connection Tests</h4>
            <div class="demo-controls">
              <button onclick="connectionDemo.testBasicConnection()" class="demo-btn">
                <i class="fas fa-plug"></i> Basic Connection
              </button>
              <button onclick="connectionDemo.testWithRetry()" class="demo-btn">
                <i class="fas fa-redo"></i> With Retry Logic
              </button>
              <button onclick="connectionDemo.testTimeout()" class="demo-btn">
                <i class="fas fa-clock"></i> Timeout Test
              </button>
              <button onclick="connectionDemo.testNetworkError()" class="demo-btn">
                <i class="fas fa-wifi"></i> Network Error
              </button>
              <button onclick="connectionDemo.testServerError()" class="demo-btn">
                <i class="fas fa-server"></i> Server Error (404)
              </button>
            </div>
            
            <div class="demo-custom-test">
              <h5>Custom Endpoint Test</h5>
              <div class="demo-input-group">
                <input type="text" id="custom-endpoint" placeholder="/api/custom-endpoint" value="/api/health">
                <button onclick="connectionDemo.testCustomEndpoint()" class="demo-btn">Test</button>
              </div>
            </div>
          </div>

          <div class="demo-section">
            <h4>Health Monitoring</h4>
            <div class="demo-controls">
              <button onclick="connectionDemo.startHealthCheck()" class="demo-btn">
                <i class="fas fa-heartbeat"></i> Start Health Check
              </button>
              <button onclick="connectionDemo.stopHealthCheck()" class="demo-btn">
                <i class="fas fa-stop"></i> Stop Health Check
              </button>
              <button onclick="connectionDemo.simulateDisconnection()" class="demo-btn">
                <i class="fas fa-unlink"></i> Simulate Disconnection
              </button>
            </div>
          </div>
        </div>

        <!-- Configuration Tab -->
        <div id="demo-config-tab" class="demo-tab-panel">
          <div class="demo-section">
            <h4>Connection Settings</h4>
            <div class="demo-config-grid">
              <label>Max Retries: <input type="number" id="config-maxRetries" min="0" max="10"></label>
              <label>Base Timeout (ms): <input type="number" id="config-baseTimeout" min="1000" max="30000"></label>
              <label>Retry Delay Base (ms): <input type="number" id="config-retryDelayBase" min="500" max="5000"></label>
              <label>Max Retry Delay (ms): <input type="number" id="config-retryDelayMax" min="1000" max="30000"></label>
              <label>Exponential Multiplier: <input type="number" id="config-exponentialBackoffMultiplier" min="1" max="5" step="0.1"></label>
              <label>Jitter Factor: <input type="number" id="config-jitterFactor" min="0" max="1" step="0.05"></label>
              <label>Health Check Interval (ms): <input type="number" id="config-healthCheckInterval" min="5000" max="300000"></label>
            </div>
            
            <div class="demo-config-actions">
              <button onclick="connectionDemo.loadConfig()" class="demo-btn">Load Current</button>
              <button onclick="connectionDemo.saveConfig()" class="demo-btn">Apply Changes</button>
              <button onclick="connectionDemo.resetConfig()" class="demo-btn">Reset Defaults</button>
            </div>
            
            <div class="demo-presets">
              <h5>Environment Presets</h5>
              <button onclick="connectionDemo.loadPreset('development')" class="demo-preset-btn">Development</button>
              <button onclick="connectionDemo.loadPreset('staging')" class="demo-preset-btn">Staging</button>
              <button onclick="connectionDemo.loadPreset('production')" class="demo-preset-btn">Production</button>
            </div>
          </div>
        </div>

        <!-- Results Tab -->
        <div id="demo-results-tab" class="demo-tab-panel">
          <div class="demo-section">
            <div class="demo-results-header">
              <h4>Test Results</h4>
              <button onclick="connectionDemo.clearResults()" class="demo-btn-small">Clear</button>
            </div>
            <div id="demo-results-list" class="demo-results-list">
              <p class="demo-no-results">No test results yet. Run some tests!</p>
            </div>
          </div>
        </div>
      </div>

      <div class="demo-live-status">
        <div class="demo-status-item">
          <span class="demo-status-label">Connection:</span>
          <span id="demo-connection-status" class="demo-status-value unknown">Unknown</span>
        </div>
        <div class="demo-status-item">
          <span class="demo-status-label">Last Test:</span>
          <span id="demo-last-test" class="demo-status-value">Never</span>
        </div>
        <div class="demo-status-item">
          <span class="demo-status-label">Health Check:</span>
          <span id="demo-health-status" class="demo-status-value">Inactive</span>
        </div>
      </div>
    `;

    document.body.appendChild(panel);
    this.bindEvents();
    this.loadConfig();
    return panel;
  }

  bindEvents() {
    // Add keyboard shortcut (Ctrl+Shift+C) to toggle demo panel
    document.addEventListener('keydown', (e) => {
      if (e.ctrlKey && e.shiftKey && e.code === 'KeyC') {
        e.preventDefault();
        this.toggle();
      }
    });

    // Listen to connection manager events
    if (window.connectionManager && window.connectionManager.apiClient) {
      window.connectionManager.apiClient.tester.addEventListener((event) => {
        this.handleConnectionEvent(event);
      });
    }
  }

  show() {
    if (!document.getElementById('connection-demo-panel')) {
      this.createDemoPanel();
    }
    
    const panel = document.getElementById('connection-demo-panel');
    panel.classList.remove('hidden');
    this.isVisible = true;
  }

  hide() {
    const panel = document.getElementById('connection-demo-panel');
    if (panel) {
      panel.classList.add('hidden');
    }
    this.isVisible = false;
  }

  toggle() {
    if (this.isVisible) {
      this.hide();
    } else {
      this.show();
    }
  }

  showTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.demo-tab').forEach(tab => tab.classList.remove('active'));
    document.querySelector(`.demo-tab:nth-child(${tabName === 'test' ? 1 : tabName === 'config' ? 2 : 3})`).classList.add('active');

    // Update tab panels
    document.querySelectorAll('.demo-tab-panel').forEach(panel => panel.classList.remove('active'));
    document.getElementById(`demo-${tabName}-tab`).classList.add('active');
  }

  async testBasicConnection() {
    this.updateStatus('Testing basic connection...', 'testing');
    
    try {
      const tester = new window.ConnectionUtils.ConnectionTester(this.config);
      const result = await tester.testConnection('/api/health');
      
      this.addResult('Basic Connection', result);
      this.updateStatus(result.success ? 'Connected' : 'Failed', result.success ? 'healthy' : 'error');
      
    } catch (error) {
      this.addResult('Basic Connection', { success: false, error, errorType: 'unknown' });
      this.updateStatus('Error', 'error');
    }
  }

  async testWithRetry() {
    this.updateStatus('Testing with retry logic...', 'testing');
    
    try {
      const tester = new window.ConnectionUtils.ConnectionTester(this.config);
      const result = await tester.testConnectionWithRetry('/api/health', {
        maxRetries: this.config.maxRetries,
        onRetry: (attempt, delay, error) => {
          this.updateStatus(`Retry ${attempt} in ${delay}ms...`, 'testing');
        }
      });
      
      this.addResult('Connection with Retry', result);
      this.updateStatus(result.success ? 'Connected' : 'Failed', result.success ? 'healthy' : 'error');
      
    } catch (error) {
      this.addResult('Connection with Retry', { success: false, error, errorType: 'unknown' });
      this.updateStatus('Error', 'error');
    }
  }

  async testTimeout() {
    this.updateStatus('Testing timeout handling...', 'testing');
    
    try {
      const tester = new window.ConnectionUtils.ConnectionTester({
        ...this.config,
        baseTimeout: 1000 // Very short timeout to trigger timeout error
      });
      
      const result = await tester.testConnectionWithRetry('/api/health', {
        timeout: 1000,
        maxRetries: 1
      });
      
      this.addResult('Timeout Test', result);
      this.updateStatus('Timeout test complete', 'neutral');
      
    } catch (error) {
      this.addResult('Timeout Test', { success: false, error, errorType: 'timeout' });
      this.updateStatus('Timeout occurred', 'error');
    }
  }

  async testNetworkError() {
    this.updateStatus('Testing network error handling...', 'testing');
    
    try {
      const tester = new window.ConnectionUtils.ConnectionTester(this.config);
      const result = await tester.testConnectionWithRetry('http://non-existent-domain.local/api/health');
      
      this.addResult('Network Error Test', result);
      this.updateStatus('Network test complete', 'neutral');
      
    } catch (error) {
      this.addResult('Network Error Test', { success: false, error, errorType: 'network' });
      this.updateStatus('Network error occurred', 'error');
    }
  }

  async testServerError() {
    this.updateStatus('Testing server error handling...', 'testing');
    
    try {
      const tester = new window.ConnectionUtils.ConnectionTester(this.config);
      const result = await tester.testConnectionWithRetry('/api/non-existent-endpoint');
      
      this.addResult('Server Error Test', result);
      this.updateStatus('Server error test complete', 'neutral');
      
    } catch (error) {
      this.addResult('Server Error Test', { success: false, error, errorType: 'server' });
      this.updateStatus('Server error occurred', 'error');
    }
  }

  async testCustomEndpoint() {
    const endpoint = document.getElementById('custom-endpoint').value;
    if (!endpoint) return;

    this.updateStatus(`Testing ${endpoint}...`, 'testing');
    
    try {
      const tester = new window.ConnectionUtils.ConnectionTester(this.config);
      const result = await tester.testConnectionWithRetry(endpoint);
      
      this.addResult(`Custom Endpoint: ${endpoint}`, result);
      this.updateStatus(result.success ? 'Success' : 'Failed', result.success ? 'healthy' : 'error');
      
    } catch (error) {
      this.addResult(`Custom Endpoint: ${endpoint}`, { success: false, error, errorType: 'unknown' });
      this.updateStatus('Error', 'error');
    }
  }

  startHealthCheck() {
    if (window.connectionManager && window.connectionManager.apiClient) {
      window.connectionManager.apiClient.startHealthCheck();
      this.updateHealthStatus('Active');
      this.updateStatus('Health check started', 'healthy');
    } else {
      this.updateStatus('Connection manager not available', 'error');
    }
  }

  stopHealthCheck() {
    if (window.connectionManager && window.connectionManager.apiClient) {
      window.connectionManager.apiClient.stopHealthCheck();
      this.updateHealthStatus('Inactive');
      this.updateStatus('Health check stopped', 'neutral');
    } else {
      this.updateStatus('Connection manager not available', 'error');
    }
  }

  simulateDisconnection() {
    // This is a demo function - in reality you might test against a non-existent endpoint
    this.updateStatus('Simulating disconnection...', 'error');
    
    if (window.connectionManager) {
      const fakeError = new Error('Simulated network error');
      fakeError.name = 'TypeError';
      window.connectionManager.handleConnectionError(fakeError);
    }
  }

  loadConfig() {
    Object.keys(this.config).forEach(key => {
      const input = document.getElementById(`config-${key}`);
      if (input) {
        input.value = this.config[key];
      }
    });
  }

  saveConfig() {
    const newConfig = {};
    Object.keys(this.config).forEach(key => {
      const input = document.getElementById(`config-${key}`);
      if (input) {
        newConfig[key] = input.type === 'number' ? parseFloat(input.value) : input.value;
      }
    });
    
    this.config = { ...this.config, ...newConfig };
    
    // Apply to connection manager if available
    if (window.connectionManager && window.connectionManager.apiClient) {
      window.connectionManager.apiClient.tester.config = { ...this.config };
    }
    
    this.updateStatus('Configuration applied', 'healthy');
  }

  resetConfig() {
    this.config = { ...window.ConnectionUtils.CONNECTION_CONFIG.defaults };
    this.loadConfig();
    this.updateStatus('Configuration reset to defaults', 'neutral');
  }

  loadPreset(environment) {
    const presetConfig = window.ConnectionUtils.CONNECTION_CONFIG.get(environment);
    this.config = { ...presetConfig };
    this.loadConfig();
    this.updateStatus(`${environment} preset loaded`, 'healthy');
  }

  addResult(testName, result) {
    const timestamp = new Date().toLocaleTimeString();
    this.testResults.unshift({
      testName,
      result,
      timestamp
    });

    // Keep only last 20 results
    if (this.testResults.length > 20) {
      this.testResults = this.testResults.slice(0, 20);
    }

    this.renderResults();
    this.updateLastTest(timestamp);
  }

  renderResults() {
    const container = document.getElementById('demo-results-list');
    if (!container) return;

    if (this.testResults.length === 0) {
      container.innerHTML = '<p class="demo-no-results">No test results yet. Run some tests!</p>';
      return;
    }

    container.innerHTML = this.testResults.map(({ testName, result, timestamp }) => {
      const status = result.success ? 'success' : 'error';
      const icon = result.success ? '✅' : '❌';
      const duration = result.totalTime ? `${result.totalTime}ms` : 'N/A';
      const attempts = result.attempts ? `${result.attempts} attempts` : '1 attempt';
      
      let errorDetails = '';
      if (!result.success && result.error) {
        const errorType = result.errorType || window.ConnectionUtils.categorizeError(result.error);
        const errorMessage = result.error.message || 'Unknown error';
        errorDetails = `<div class="demo-error-details">
          <strong>Error Type:</strong> ${errorType}<br>
          <strong>Message:</strong> ${errorMessage.slice(0, 100)}${errorMessage.length > 100 ? '...' : ''}
        </div>`;
      }

      return `
        <div class="demo-result-item ${status}">
          <div class="demo-result-header">
            <span class="demo-result-icon">${icon}</span>
            <span class="demo-result-name">${testName}</span>
            <span class="demo-result-time">${timestamp}</span>
          </div>
          <div class="demo-result-details">
            <span><strong>Duration:</strong> ${duration}</span>
            <span><strong>Attempts:</strong> ${attempts}</span>
          </div>
          ${errorDetails}
        </div>
      `;
    }).join('');
  }

  clearResults() {
    this.testResults = [];
    this.renderResults();
    this.updateLastTest('Never');
  }

  updateStatus(message, type) {
    const statusEl = document.getElementById('demo-connection-status');
    if (statusEl) {
      statusEl.textContent = message;
      statusEl.className = `demo-status-value ${type}`;
    }
  }

  updateLastTest(timestamp) {
    const lastTestEl = document.getElementById('demo-last-test');
    if (lastTestEl) {
      lastTestEl.textContent = timestamp;
    }
  }

  updateHealthStatus(status) {
    const healthEl = document.getElementById('demo-health-status');
    if (healthEl) {
      healthEl.textContent = status;
      healthEl.className = `demo-status-value ${status.toLowerCase()}`;
    }
  }

  handleConnectionEvent(event) {
    switch (event.type) {
      case 'connection_success':
        this.updateStatus('Connected', 'healthy');
        break;
      case 'connection_failure':
        this.updateStatus('Connection failed', 'error');
        break;
      case 'connection_retry':
        this.updateStatus(`Retrying (${event.attempt})...`, 'testing');
        break;
      case 'health_check_status_change':
        this.updateHealthStatus(event.isHealthy ? 'Healthy' : 'Unhealthy');
        this.updateStatus(event.isHealthy ? 'Connected' : 'Disconnected', event.isHealthy ? 'healthy' : 'error');
        break;
    }
  }
}

// Create demo panel styles
const demoStyles = `
<style>
.connection-demo-panel {
  position: fixed;
  top: 50px;
  right: 20px;
  width: 500px;
  max-height: 80vh;
  background: var(--bg-color, #fff);
  border: 1px solid var(--border-color, #ddd);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  z-index: 2000;
  overflow: hidden;
  transition: all 0.3s ease;
  font-size: 13px;
}

.connection-demo-panel.hidden {
  opacity: 0;
  transform: translateX(100%);
  pointer-events: none;
}

.demo-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  background: var(--primary-color, #2196f3);
  color: white;
}

.demo-panel-header h3 {
  margin: 0;
  font-size: 16px;
}

.demo-close-btn {
  background: none;
  border: none;
  color: white;
  font-size: 18px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
}

.demo-close-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.demo-tabs {
  display: flex;
  background: rgba(0, 0, 0, 0.02);
  border-bottom: 1px solid var(--border-color, #ddd);
}

.demo-tab {
  flex: 1;
  padding: 12px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.2s;
}

.demo-tab.active {
  background: var(--bg-color, #fff);
  border-bottom: 2px solid var(--primary-color, #2196f3);
}

.demo-tab:hover:not(.active) {
  background: rgba(0, 0, 0, 0.05);
}

.demo-tab-content {
  max-height: 60vh;
  overflow-y: auto;
  padding: 16px;
}

.demo-tab-panel {
  display: none;
}

.demo-tab-panel.active {
  display: block;
}

.demo-section {
  margin-bottom: 20px;
}

.demo-section h4, .demo-section h5 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: var(--text-color, #333);
}

.demo-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.demo-btn, .demo-btn-small, .demo-preset-btn {
  padding: 8px 12px;
  background: var(--primary-color, #2196f3);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: background 0.2s;
}

.demo-btn-small {
  padding: 4px 8px;
  font-size: 11px;
}

.demo-preset-btn {
  background: var(--secondary-color, #666);
  font-size: 11px;
  padding: 4px 8px;
}

.demo-btn:hover, .demo-btn-small:hover, .demo-preset-btn:hover {
  background: var(--primary-color-hover, #1976d2);
}

.demo-custom-test {
  background: rgba(0, 0, 0, 0.02);
  padding: 12px;
  border-radius: 4px;
  margin-top: 12px;
}

.demo-input-group {
  display: flex;
  gap: 8px;
  align-items: center;
}

.demo-input-group input {
  flex: 1;
  padding: 6px;
  border: 1px solid var(--border-color, #ddd);
  border-radius: 4px;
  font-size: 12px;
}

.demo-config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}

.demo-config-grid label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
}

.demo-config-grid input {
  padding: 6px;
  border: 1px solid var(--border-color, #ddd);
  border-radius: 4px;
  font-size: 12px;
}

.demo-config-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.demo-presets {
  display: flex;
  gap: 4px;
  align-items: center;
}

.demo-results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.demo-results-list {
  max-height: 300px;
  overflow-y: auto;
}

.demo-no-results {
  text-align: center;
  color: var(--text-color-muted, #666);
  font-style: italic;
  margin: 20px 0;
}

.demo-result-item {
  border: 1px solid var(--border-color, #ddd);
  border-radius: 4px;
  margin-bottom: 8px;
  padding: 12px;
}

.demo-result-item.success {
  border-left: 4px solid #4caf50;
}

.demo-result-item.error {
  border-left: 4px solid #f44336;
}

.demo-result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.demo-result-icon {
  font-size: 14px;
}

.demo-result-name {
  font-weight: 600;
  flex: 1;
}

.demo-result-time {
  font-size: 11px;
  color: var(--text-color-muted, #666);
}

.demo-result-details {
  display: flex;
  gap: 16px;
  font-size: 11px;
  color: var(--text-color-muted, #666);
  margin-bottom: 8px;
}

.demo-error-details {
  background: rgba(244, 67, 54, 0.1);
  padding: 8px;
  border-radius: 4px;
  font-size: 11px;
  line-height: 1.4;
}

.demo-live-status {
  background: rgba(0, 0, 0, 0.02);
  padding: 12px;
  border-top: 1px solid var(--border-color, #ddd);
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}

.demo-status-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.demo-status-label {
  font-size: 11px;
  color: var(--text-color-muted, #666);
}

.demo-status-value {
  font-size: 12px;
  font-weight: 600;
}

.demo-status-value.healthy { color: #4caf50; }
.demo-status-value.error { color: #f44336; }
.demo-status-value.testing { color: #ff9800; }
.demo-status-value.neutral { color: var(--text-color, #333); }
.demo-status-value.unknown { color: var(--text-color-muted, #666); }
.demo-status-value.active { color: #4caf50; }
.demo-status-value.inactive { color: var(--text-color-muted, #666); }

/* Dark theme support */
.dark-theme .connection-demo-panel {
  background: var(--bg-color, #2d2d2d);
  border-color: var(--border-color, #444);
  color: var(--text-color, #e0e0e0);
}

.dark-theme .demo-tab.active {
  background: var(--bg-color, #2d2d2d);
}

.dark-theme .demo-custom-test,
.dark-theme .demo-live-status {
  background: rgba(255, 255, 255, 0.02);
}

.dark-theme .demo-error-details {
  background: rgba(244, 67, 54, 0.2);
}

@media (max-width: 768px) {
  .connection-demo-panel {
    right: 10px;
    left: 10px;
    width: auto;
    max-height: 70vh;
  }
  
  .demo-config-grid {
    grid-template-columns: 1fr;
  }
  
  .demo-controls {
    flex-direction: column;
  }
  
  .demo-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
`;

// Inject styles
document.head.insertAdjacentHTML('beforeend', demoStyles);

// Create global demo instance
window.connectionDemo = new ConnectionDemo();

// Add console helper
console.log('🔧 Connection Demo available! Use Ctrl+Shift+C to open the demo panel, or call connectionDemo.show()');