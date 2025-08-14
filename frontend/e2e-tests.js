/**
 * End-to-End Test Suite for Frontend-Backend Integration
 * Comprehensive testing of proxy configuration, API connectivity, and error handling
 */

class E2ETestSuite {
    constructor() {
        this.apiBase = '/api';
        this.testResults = new Map();
        this.totalTests = 0;
        this.completedTests = 0;
        this.deviceId = this.generateDeviceId();
        this.sessionId = `test_${this.deviceId}_${Date.now()}`;
        
        this.criticalTests = [
            'proxy-config',
            'health-reliability',
            'api-coverage',
            'connection-monitor'
        ];
        
        this.validationTests = [
            'error-recovery',
            'session-persistence',
            'streaming-response'
        ];
        
        this.init();
    }

    generateDeviceId() {
        return btoa(navigator.userAgent + crypto.randomUUID()).replace(/[^a-zA-Z0-9]/g, '').substring(0, 16);
    }

    init() {
        this.bindEvents();
        this.updateConnectionStatus('checking', 'Initializing test suite...');
        this.checkInitialConnection();
    }

    bindEvents() {
        document.getElementById('run-full-suite').addEventListener('click', () => this.runFullSuite());
        document.getElementById('run-critical').addEventListener('click', () => this.runCriticalTests());
        document.getElementById('run-validation').addEventListener('click', () => this.runValidationTests());
        document.getElementById('reset-tests').addEventListener('click', () => this.resetTests());
    }

    async checkInitialConnection() {
        try {
            const response = await fetch(`${this.apiBase}/health`, { timeout: 5000 });
            if (response.ok) {
                this.updateConnectionStatus('connected', 'Backend connected - Ready to test');
            } else {
                this.updateConnectionStatus('disconnected', `Backend returned ${response.status}`);
            }
        } catch (error) {
            this.updateConnectionStatus('disconnected', `Connection failed: ${error.message}`);
        }
    }

    updateConnectionStatus(status, message) {
        const indicator = document.getElementById('connection-indicator');
        const statusText = document.getElementById('connection-status');
        
        indicator.className = `status-indicator indicator-${status}`;
        statusText.textContent = message;
    }

    updateProgress() {
        const progressText = document.getElementById('test-progress');
        const progressFill = document.getElementById('progress-fill');
        
        progressText.textContent = `${this.completedTests}/${this.totalTests} Tests Completed`;
        
        const percentage = this.totalTests > 0 ? (this.completedTests / this.totalTests) * 100 : 0;
        progressFill.style.width = `${percentage}%`;
    }

    logToTest(testName, message, type = 'info') {
        const output = document.getElementById(`${testName}-output`);
        if (!output) return;
        
        const timestamp = new Date().toLocaleTimeString();
        const icon = type === 'error' ? '❌' : type === 'success' ? '✅' : type === 'warning' ? '⚠️' : 'ℹ️';
        
        const newLine = `[${timestamp}] ${icon} ${message}\n`;
        output.textContent += newLine;
        output.scrollTop = output.scrollHeight;
    }

    updateTestStatus(testName, status) {
        const card = document.querySelector(`[data-test="${testName}"]`);
        if (!card) return;
        
        const badge = card.querySelector('.test-badge');
        const statusText = {
            'pending': 'PENDING',
            'running': 'RUNNING',
            'success': 'PASSED',
            'error': 'FAILED'
        };
        
        card.className = `test-card ${status}`;
        badge.className = `test-badge badge-${status}`;
        badge.textContent = statusText[status] || 'UNKNOWN';
    }

    resetTests() {
        this.testResults.clear();
        this.completedTests = 0;
        this.totalTests = 0;
        
        // Reset all test cards
        document.querySelectorAll('.test-card').forEach(card => {
            card.className = 'test-card';
            const output = card.querySelector('.test-output');
            if (output) output.textContent = 'Waiting to run...';
        });
        
        document.querySelectorAll('.test-badge').forEach(badge => {
            badge.className = 'test-badge badge-pending';
            badge.textContent = 'PENDING';
        });
        
        this.updateProgress();
        this.checkInitialConnection();
    }

    async runFullSuite() {
        const allTests = [
            'proxy-config',
            'health-reliability',
            'api-coverage',
            'error-recovery',
            'connection-monitor',
            'session-persistence',
            'streaming-response',
            'performance-metrics',
            'file-upload'
        ];
        
        await this.runTestSuite(allTests);
    }

    async runCriticalTests() {
        await this.runTestSuite(this.criticalTests);
    }

    async runValidationTests() {
        await this.runTestSuite(this.validationTests);
    }

    async runTestSuite(tests) {
        this.completedTests = 0;
        this.totalTests = tests.length;
        this.updateProgress();
        
        for (const testName of tests) {
            await this.runTest(testName);
            this.completedTests++;
            this.updateProgress();
        }
        
        this.generateSummary();
    }

    async runTest(testName) {
        this.updateTestStatus(testName, 'running');
        this.logToTest(testName, `Starting ${testName} test...`);
        
        try {
            switch (testName) {
                case 'proxy-config':
                    await this.testProxyConfiguration();
                    break;
                case 'health-reliability':
                    await this.testHealthReliability();
                    break;
                case 'api-coverage':
                    await this.testAPICoverage();
                    break;
                case 'error-recovery':
                    await this.testErrorRecovery();
                    break;
                case 'connection-monitor':
                    await this.testConnectionMonitor();
                    break;
                case 'session-persistence':
                    await this.testSessionPersistence();
                    break;
                case 'streaming-response':
                    await this.testStreamingResponse();
                    break;
                case 'performance-metrics':
                    await this.testPerformanceMetrics();
                    break;
                case 'file-upload':
                    await this.testFileUpload();
                    break;
                default:
                    throw new Error(`Unknown test: ${testName}`);
            }
            
            this.testResults.set(testName, { status: 'success' });
            this.updateTestStatus(testName, 'success');
            this.logToTest(testName, 'Test completed successfully', 'success');
            
        } catch (error) {
            this.testResults.set(testName, { status: 'error', error: error.message });
            this.updateTestStatus(testName, 'error');
            this.logToTest(testName, `Test failed: ${error.message}`, 'error');
        }
    }

    async testProxyConfiguration() {
        this.logToTest('proxy-config', 'Testing Vercel proxy configuration...');
        
        // Test proxy URL construction
        const testUrls = [
            '/health',
            '/get-all-sessions-summary',
            '/ask',
            '/upload-document'
        ];
        
        for (const url of testUrls) {
            const fullUrl = `${this.apiBase}${url}`;
            this.logToTest('proxy-config', `Testing URL construction: ${fullUrl}`);
            
            try {
                const response = await fetch(fullUrl, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                // We expect different status codes for different endpoints
                if (url === '/health' && !response.ok) {
                    throw new Error(`Health endpoint failed: ${response.status}`);
                }
                
                this.logToTest('proxy-config', `${url}: ${response.status} (${response.statusText})`);
                
            } catch (error) {
                if (url === '/health') {
                    throw new Error(`Critical proxy failure on ${url}: ${error.message}`);
                }
                this.logToTest('proxy-config', `${url}: ${error.message}`, 'warning');
            }
        }
        
        // Test CORS headers
        this.logToTest('proxy-config', 'Testing CORS configuration...');
        const corsResponse = await fetch(`${this.apiBase}/health`);
        const corsHeaders = corsResponse.headers.get('access-control-allow-origin');
        
        if (corsHeaders) {
            this.logToTest('proxy-config', `CORS headers present: ${corsHeaders}`, 'success');
        } else {
            this.logToTest('proxy-config', 'CORS headers missing', 'warning');
        }
    }

    async testHealthReliability() {
        this.logToTest('health-reliability', 'Testing health endpoint reliability...');
        
        const iterations = 5;
        const results = [];
        
        for (let i = 0; i < iterations; i++) {
            const startTime = performance.now();
            
            try {
                const response = await fetch(`${this.apiBase}/health`);
                const endTime = performance.now();
                const responseTime = endTime - startTime;
                
                if (response.ok) {
                    const data = await response.json();
                    results.push({ success: true, time: responseTime, data });
                    this.logToTest('health-reliability', `Attempt ${i + 1}: Success (${responseTime.toFixed(2)}ms)`);
                } else {
                    results.push({ success: false, time: responseTime, status: response.status });
                    this.logToTest('health-reliability', `Attempt ${i + 1}: Failed ${response.status}`, 'error');
                }
            } catch (error) {
                results.push({ success: false, error: error.message });
                this.logToTest('health-reliability', `Attempt ${i + 1}: Error - ${error.message}`, 'error');
            }
            
            // Small delay between requests
            await new Promise(resolve => setTimeout(resolve, 200));
        }
        
        const successCount = results.filter(r => r.success).length;
        const avgTime = results
            .filter(r => r.success && r.time)
            .reduce((sum, r) => sum + r.time, 0) / Math.max(1, successCount);
        
        this.logToTest('health-reliability', `Reliability: ${successCount}/${iterations} (${(successCount/iterations*100).toFixed(1)}%)`);
        this.logToTest('health-reliability', `Average response time: ${avgTime.toFixed(2)}ms`);
        
        if (successCount < iterations * 0.8) {
            throw new Error(`Low reliability: ${successCount}/${iterations} successful`);
        }
    }

    async testAPICoverage() {
        this.logToTest('api-coverage', 'Testing API endpoint coverage...');
        
        const endpoints = [
            { path: '/health', method: 'GET', expectSuccess: true },
            { path: '/get-all-sessions-summary', method: 'GET', expectSuccess: true },
            { path: '/get-history', method: 'GET', expectSuccess: false, params: '?session_id=nonexistent' },
            { path: '/ask', method: 'POST', expectSuccess: false, body: { question: 'test' } }
        ];
        
        let successfulEndpoints = 0;
        
        for (const endpoint of endpoints) {
            try {
                const url = `${this.apiBase}${endpoint.path}${endpoint.params || ''}`;
                const options = {
                    method: endpoint.method,
                    headers: { 'Content-Type': 'application/json' }
                };
                
                if (endpoint.body) {
                    options.body = JSON.stringify(endpoint.body);
                }
                
                const response = await fetch(url, options);
                
                if (endpoint.expectSuccess && response.ok) {
                    successfulEndpoints++;
                    this.logToTest('api-coverage', `${endpoint.method} ${endpoint.path}: ✅ ${response.status}`, 'success');
                } else if (!endpoint.expectSuccess) {
                    this.logToTest('api-coverage', `${endpoint.method} ${endpoint.path}: 📝 ${response.status} (expected)`);
                } else {
                    this.logToTest('api-coverage', `${endpoint.method} ${endpoint.path}: ❌ ${response.status}`, 'error');
                }
                
            } catch (error) {
                this.logToTest('api-coverage', `${endpoint.method} ${endpoint.path}: Error - ${error.message}`, 'error');
            }
        }
        
        this.logToTest('api-coverage', `Coverage: ${successfulEndpoints} critical endpoints accessible`);
    }

    async testErrorRecovery() {
        this.logToTest('error-recovery', 'Testing error recovery mechanisms...');
        
        // Test 404 handling
        try {
            const response = await fetch(`${this.apiBase}/nonexistent-endpoint-${Date.now()}`);
            this.logToTest('error-recovery', `404 test: ${response.status} ${response.statusText}`);
        } catch (error) {
            this.logToTest('error-recovery', `404 test error: ${error.message}`);
        }
        
        // Test timeout handling
        this.logToTest('error-recovery', 'Testing timeout handling...');
        try {
            const controller = new AbortController();
            setTimeout(() => controller.abort(), 1000);
            
            await fetch(`${this.apiBase}/health`, {
                signal: controller.signal
            });
        } catch (error) {
            if (error.name === 'AbortError') {
                this.logToTest('error-recovery', 'Timeout handling: ✅ AbortError caught', 'success');
            } else {
                this.logToTest('error-recovery', `Unexpected error: ${error.message}`, 'warning');
            }
        }
        
        // Test malformed request handling
        try {
            const response = await fetch(`${this.apiBase}/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: 'invalid-json-data'
            });
            
            this.logToTest('error-recovery', `Malformed request: ${response.status}`, 
                response.status >= 400 ? 'success' : 'warning');
        } catch (error) {
            this.logToTest('error-recovery', `Malformed request error: ${error.message}`);
        }
    }

    async testConnectionMonitor() {
        this.logToTest('connection-monitor', 'Testing connection monitoring...');
        
        // Check if connection monitor exists
        if (window.connectionMonitor) {
            this.logToTest('connection-monitor', '✅ Global connection monitor found', 'success');
            
            const currentStatus = window.connectionMonitor.currentStatus;
            this.logToTest('connection-monitor', `Current status: ${currentStatus}`);
            
            // Test manual health check
            try {
                const healthResult = await window.connectionMonitor.checkHealth();
                this.logToTest('connection-monitor', `Manual health check: ${healthResult ? 'Success' : 'Failed'}`,
                    healthResult ? 'success' : 'error');
            } catch (error) {
                this.logToTest('connection-monitor', `Health check error: ${error.message}`, 'error');
            }
        } else {
            this.logToTest('connection-monitor', '⚠️ Global connection monitor not found', 'warning');
        }
        
        // Test status element presence
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            this.logToTest('connection-monitor', '✅ Connection status element found', 'success');
        } else {
            this.logToTest('connection-monitor', '⚠️ Connection status element missing', 'warning');
        }
    }

    async testSessionPersistence() {
        this.logToTest('session-persistence', 'Testing session persistence...');
        
        // Test creating a session
        try {
            const response = await fetch(`${this.apiBase}/get-all-sessions-summary`);
            
            if (response.ok) {
                const data = await response.json();
                this.logToTest('session-persistence', `Sessions endpoint: ✅ ${response.status}`, 'success');
                this.logToTest('session-persistence', `Found ${data.sessions?.length || 0} sessions`);
            } else {
                throw new Error(`Sessions endpoint failed: ${response.status}`);
            }
        } catch (error) {
            throw new Error(`Session management test failed: ${error.message}`);
        }
        
        // Test session storage
        const testSessionId = `test_${Date.now()}`;
        sessionStorage.setItem('testSessionId', testSessionId);
        
        const retrievedSessionId = sessionStorage.getItem('testSessionId');
        if (retrievedSessionId === testSessionId) {
            this.logToTest('session-persistence', '✅ Session storage working', 'success');
            sessionStorage.removeItem('testSessionId');
        } else {
            throw new Error('Session storage not working');
        }
    }

    async testStreamingResponse() {
        this.logToTest('streaming-response', 'Testing streaming response functionality...');
        
        const testQuestion = 'Что такое право?';
        
        try {
            const response = await fetch(`${this.apiBase}/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question: testQuestion,
                    session_id: this.sessionId
                })
            });
            
            if (!response.ok) {
                throw new Error(`Ask endpoint failed: ${response.status}`);
            }
            
            this.logToTest('streaming-response', '✅ Ask endpoint accessible', 'success');
            
            // Test if response body is readable stream
            if (response.body && response.body.getReader) {
                this.logToTest('streaming-response', '✅ Streaming response supported', 'success');
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let chunks = 0;
                let totalLength = 0;
                
                try {
                    while (chunks < 5) { // Limit to avoid long waits
                        const { done, value } = await reader.read();
                        if (done) break;
                        
                        const chunk = decoder.decode(value, { stream: true });
                        chunks++;
                        totalLength += chunk.length;
                    }
                    
                    this.logToTest('streaming-response', `Received ${chunks} chunks, ${totalLength} characters`);
                } finally {
                    reader.releaseLock();
                }
            } else {
                this.logToTest('streaming-response', '⚠️ No streaming support detected', 'warning');
            }
            
        } catch (error) {
            throw new Error(`Streaming test failed: ${error.message}`);
        }
    }

    async testPerformanceMetrics() {
        this.logToTest('performance-metrics', 'Testing performance metrics...');
        
        const performanceTests = [
            { name: 'Health Check', endpoint: '/health' },
            { name: 'Sessions Summary', endpoint: '/get-all-sessions-summary' }
        ];
        
        for (const test of performanceTests) {
            const measurements = [];
            
            for (let i = 0; i < 3; i++) {
                const startTime = performance.now();
                
                try {
                    const response = await fetch(`${this.apiBase}${test.endpoint}`);
                    const endTime = performance.now();
                    
                    if (response.ok) {
                        measurements.push(endTime - startTime);
                    }
                } catch (error) {
                    this.logToTest('performance-metrics', `${test.name} error: ${error.message}`, 'warning');
                }
                
                await new Promise(resolve => setTimeout(resolve, 100));
            }
            
            if (measurements.length > 0) {
                const avg = measurements.reduce((a, b) => a + b, 0) / measurements.length;
                const min = Math.min(...measurements);
                const max = Math.max(...measurements);
                
                this.logToTest('performance-metrics', 
                    `${test.name}: ${avg.toFixed(2)}ms avg (${min.toFixed(2)}-${max.toFixed(2)}ms)`);
            }
        }
    }

    async testFileUpload() {
        this.logToTest('file-upload', 'Testing file upload functionality...');
        
        // Create a test file
        const testContent = 'Test document content for legal analysis';
        const testFile = new Blob([testContent], { type: 'text/plain' });
        
        const formData = new FormData();
        formData.append('file', testFile, 'test-document.txt');
        formData.append('question', 'Analyze this document');
        formData.append('session_id', this.sessionId);
        
        try {
            const response = await fetch(`${this.apiBase}/upload-document`, {
                method: 'POST',
                body: formData
            });
            
            this.logToTest('file-upload', `Upload endpoint response: ${response.status}`);
            
            if (response.status === 200 || response.status === 422) {
                this.logToTest('file-upload', '✅ Upload endpoint accessible', 'success');
            } else if (response.status === 413) {
                this.logToTest('file-upload', '📏 File size limits working', 'success');
            } else {
                this.logToTest('file-upload', `Unexpected status: ${response.status}`, 'warning');
            }
            
        } catch (error) {
            throw new Error(`File upload test failed: ${error.message}`);
        }
    }

    generateSummary() {
        const results = Array.from(this.testResults.values());
        const passed = results.filter(r => r.status === 'success').length;
        const failed = results.filter(r => r.status === 'error').length;
        
        if (failed === 0) {
            this.updateConnectionStatus('connected', `All ${passed} tests passed ✅`);
        } else {
            this.updateConnectionStatus('disconnected', `${failed} tests failed, ${passed} passed`);
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.e2eTestSuite = new E2ETestSuite();
});

// Export for potential external use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = E2ETestSuite;
}