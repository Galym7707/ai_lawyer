/**
 * Integration Tests for Frontend-Backend Connectivity
 * Tests the health check endpoint, API calls, error handling, and proxy functionality
 */

class IntegrationTestRunner {
    constructor() {
        this.apiBase = '/api';
        this.testResults = new Map();
        this.currentTest = null;
        this.deviceId = this.generateDeviceId();
        this.sessionId = `${this.deviceId}_${crypto.randomUUID()}`;
        
        this.initializeEventListeners();
    }

    generateDeviceId() {
        const userAgent = navigator.userAgent;
        const randomString = crypto.randomUUID();
        return btoa(userAgent + randomString).replace(/=/g, '').substring(0, 16);
    }

    initializeEventListeners() {
        document.getElementById('run-all-btn').addEventListener('click', () => this.runAllTests());
        document.getElementById('run-selected-btn').addEventListener('click', () => this.runSelectedTests());
        document.getElementById('clear-results-btn').addEventListener('click', () => this.clearResults());
    }

    log(testName, message, isError = false) {
        const output = document.getElementById(`${testName}-output`);
        if (!output) return;
        
        const timestamp = new Date().toLocaleTimeString();
        const prefix = isError ? '❌' : '✅';
        const newMessage = `[${timestamp}] ${prefix} ${message}\n`;
        
        output.textContent += newMessage;
        output.scrollTop = output.scrollHeight;
    }

    updateTestStatus(testName, status) {
        const container = document.querySelector(`[data-test="${testName}"]`);
        if (!container) return;
        
        const statusElement = container.querySelector('.test-status');
        statusElement.className = `test-status status-${status}`;
        
        switch (status) {
            case 'running':
                statusElement.textContent = 'RUNNING';
                break;
            case 'success':
                statusElement.textContent = 'PASSED';
                break;
            case 'error':
                statusElement.textContent = 'FAILED';
                break;
            default:
                statusElement.textContent = 'PENDING';
        }
    }

    clearResults() {
        const outputs = document.querySelectorAll('.test-output');
        outputs.forEach(output => {
            output.textContent = 'Waiting to run...';
        });
        
        document.querySelectorAll('.test-status').forEach(status => {
            status.className = 'test-status status-pending';
            status.textContent = 'PENDING';
        });
        
        this.testResults.clear();
        this.updateSummary();
    }

    async runAllTests() {
        this.clearResults();
        const tests = [
            'health-check',
            'api-base',
            'session-management',
            'error-handling',
            'connection-status',
            'ai-ask',
            'performance'
        ];
        
        for (const testName of tests) {
            await this.runTest(testName);
        }
        
        this.updateSummary();
    }

    async runSelectedTests() {
        this.clearResults();
        const checkboxes = document.querySelectorAll('input[type="checkbox"]:checked');
        const selectedTests = Array.from(checkboxes).map(cb => {
            const container = cb.closest('.test-container');
            return container ? container.dataset.test : null;
        }).filter(Boolean);
        
        for (const testName of selectedTests) {
            await this.runTest(testName);
        }
        
        this.updateSummary();
    }

    async runTest(testName) {
        this.currentTest = testName;
        this.updateTestStatus(testName, 'running');
        
        try {
            switch (testName) {
                case 'health-check':
                    await this.testHealthCheck();
                    break;
                case 'api-base':
                    await this.testAPIBase();
                    break;
                case 'session-management':
                    await this.testSessionManagement();
                    break;
                case 'error-handling':
                    await this.testErrorHandling();
                    break;
                case 'connection-status':
                    await this.testConnectionStatus();
                    break;
                case 'ai-ask':
                    await this.testAIAsk();
                    break;
                case 'performance':
                    await this.testPerformance();
                    break;
                default:
                    throw new Error(`Unknown test: ${testName}`);
            }
            
            this.testResults.set(testName, { status: 'success', error: null });
            this.updateTestStatus(testName, 'success');
            this.log(testName, `Test completed successfully`);
            
        } catch (error) {
            this.testResults.set(testName, { status: 'error', error: error.message });
            this.updateTestStatus(testName, 'error');
            this.log(testName, `Test failed: ${error.message}`, true);
        }
    }

    async testHealthCheck() {
        this.log('health-check', 'Testing health check endpoint...');
        
        const startTime = Date.now();
        const response = await fetch(`${this.apiBase}/health`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            cache: 'no-cache'
        });
        
        const responseTime = Date.now() - startTime;
        
        if (!response.ok) {
            throw new Error(`Health check failed with status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.status !== 'healthy') {
            throw new Error(`Health check returned unhealthy status: ${data.status}`);
        }
        
        this.log('health-check', `Health check passed in ${responseTime}ms`);
        this.log('health-check', `Response: ${JSON.stringify(data, null, 2)}`);
    }

    async testAPIBase() {
        this.log('api-base', 'Testing API base connectivity...');
        
        // Test different endpoints to verify proxy configuration
        const endpoints = [
            '/health',
            '/get-all-sessions-summary'
        ];
        
        for (const endpoint of endpoints) {
            const startTime = Date.now();
            const response = await fetch(`${this.apiBase}${endpoint}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const responseTime = Date.now() - startTime;
            
            if (!response.ok && response.status !== 404) {
                throw new Error(`API endpoint ${endpoint} failed with status: ${response.status}`);
            }
            
            this.log('api-base', `${endpoint}: ${response.status} (${responseTime}ms)`);
        }
        
        this.log('api-base', 'API base connectivity test completed');
    }

    async testSessionManagement() {
        this.log('session-management', 'Testing session management endpoints...');
        
        // Test getting all sessions
        this.log('session-management', 'Testing get-all-sessions-summary...');
        const sessionsResponse = await fetch(`${this.apiBase}/get-all-sessions-summary`);
        
        if (!sessionsResponse.ok) {
            throw new Error(`Failed to get sessions: ${sessionsResponse.status}`);
        }
        
        const sessionsData = await sessionsResponse.json();
        this.log('session-management', `Sessions response: ${JSON.stringify(sessionsData, null, 2)}`);
        
        // Test getting history for a specific session (should return empty or error gracefully)
        this.log('session-management', 'Testing get-history endpoint...');
        const historyResponse = await fetch(`${this.apiBase}/get-history?session_id=${this.sessionId}`);
        
        // This might return 404 or empty history, both are acceptable
        if (historyResponse.ok) {
            const historyData = await historyResponse.json();
            this.log('session-management', `History response: ${JSON.stringify(historyData, null, 2)}`);
        } else {
            this.log('session-management', `History response status: ${historyResponse.status} (expected for new session)`);
        }
    }

    async testErrorHandling() {
        this.log('error-handling', 'Testing error handling scenarios...');
        
        // Test invalid endpoint
        this.log('error-handling', 'Testing invalid endpoint...');
        const invalidResponse = await fetch(`${this.apiBase}/invalid-endpoint-12345`);
        
        if (invalidResponse.status !== 404 && invalidResponse.status !== 502) {
            this.log('error-handling', `Expected 404 or 502, got ${invalidResponse.status}`);
        } else {
            this.log('error-handling', `Invalid endpoint correctly returned ${invalidResponse.status}`);
        }
        
        // Test malformed request
        this.log('error-handling', 'Testing malformed request to ask endpoint...');
        try {
            const malformedResponse = await fetch(`${this.apiBase}/ask`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: 'invalid-json'
            });
            
            this.log('error-handling', `Malformed request returned status: ${malformedResponse.status}`);
            
            if (malformedResponse.status >= 400) {
                this.log('error-handling', 'Malformed request correctly handled');
            }
        } catch (error) {
            this.log('error-handling', `Malformed request error handled: ${error.message}`);
        }
        
        // Test timeout scenario (simulated)
        this.log('error-handling', 'Testing timeout handling...');
        try {
            const controller = new AbortController();
            setTimeout(() => controller.abort(), 100); // Very short timeout
            
            await fetch(`${this.apiBase}/health`, {
                signal: controller.signal
            });
        } catch (error) {
            if (error.name === 'AbortError') {
                this.log('error-handling', 'Timeout handling works correctly');
            } else {
                this.log('error-handling', `Unexpected error: ${error.message}`);
            }
        }
    }

    async testConnectionStatus() {
        this.log('connection-status', 'Testing connection status monitor...');
        
        // Create a temporary connection monitor
        const testMonitor = new (window.ConnectionStatusMonitor || class {
            constructor() {
                this.apiUrl = `${window.location.origin}/api/health`;
            }
            async checkHealth() {
                try {
                    const response = await fetch(this.apiUrl);
                    return response.ok;
                } catch {
                    return false;
                }
            }
            destroy() {}
        })({
            apiUrl: `${this.apiBase}/health`,
            checkInterval: 5000,
            retryInterval: 5000
        });
        
        this.log('connection-status', 'Testing connection status check...');
        const healthResult = await testMonitor.checkHealth();
        
        if (healthResult) {
            this.log('connection-status', 'Connection status monitor working correctly');
        } else {
            this.log('connection-status', 'Connection status monitor detected disconnection');
        }
        
        // Test status updates
        if (window.connectionMonitor) {
            this.log('connection-status', 'Global connection monitor is active');
            const currentStatus = window.connectionMonitor.currentStatus;
            this.log('connection-status', `Current status: ${currentStatus}`);
        } else {
            this.log('connection-status', 'Global connection monitor not found');
        }
        
        testMonitor.destroy();
    }

    async testAIAsk() {
        this.log('ai-ask', 'Testing AI ask endpoint...');
        
        const testQuestion = 'Что такое гражданское право Казахстана?';
        const requestBody = {
            question: testQuestion,
            session_id: this.sessionId
        };
        
        this.log('ai-ask', `Sending question: "${testQuestion}"`);
        
        const startTime = Date.now();
        const response = await fetch(`${this.apiBase}/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });
        
        const responseTime = Date.now() - startTime;
        
        if (!response.ok) {
            throw new Error(`AI ask endpoint failed with status: ${response.status}`);
        }
        
        this.log('ai-ask', `Response received in ${responseTime}ms`);
        
        // Test streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let responseText = '';
        let chunkCount = 0;
        
        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                responseText += chunk;
                chunkCount++;
            }
            
            this.log('ai-ask', `Received ${chunkCount} chunks, total length: ${responseText.length} characters`);
            
            if (responseText.length === 0) {
                throw new Error('Empty response received from AI');
            }
            
            this.log('ai-ask', `Response preview: "${responseText.substring(0, 200)}..."`);
            
        } catch (streamError) {
            throw new Error(`Streaming error: ${streamError.message}`);
        }
    }

    async testPerformance() {
        this.log('performance', 'Testing API performance metrics...');
        
        const tests = [
            { endpoint: '/health', name: 'Health Check' },
            { endpoint: '/get-all-sessions-summary', name: 'Sessions Summary' }
        ];
        
        for (const test of tests) {
            this.log('performance', `Testing ${test.name} performance...`);
            
            const times = [];
            const iterations = 3;
            
            for (let i = 0; i < iterations; i++) {
                const startTime = performance.now();
                
                try {
                    const response = await fetch(`${this.apiBase}${test.endpoint}`);
                    const endTime = performance.now();
                    
                    if (response.ok) {
                        times.push(endTime - startTime);
                    }
                } catch (error) {
                    this.log('performance', `Error in iteration ${i + 1}: ${error.message}`);
                }
                
                // Small delay between requests
                await new Promise(resolve => setTimeout(resolve, 100));
            }
            
            if (times.length > 0) {
                const avgTime = times.reduce((a, b) => a + b, 0) / times.length;
                const minTime = Math.min(...times);
                const maxTime = Math.max(...times);
                
                this.log('performance', `${test.name} - Avg: ${avgTime.toFixed(2)}ms, Min: ${minTime.toFixed(2)}ms, Max: ${maxTime.toFixed(2)}ms`);
            }
        }
        
        // Test concurrent requests
        this.log('performance', 'Testing concurrent health checks...');
        const concurrentPromises = Array(3).fill().map(() => 
            fetch(`${this.apiBase}/health`).then(r => r.ok)
        );
        
        const concurrentResults = await Promise.all(concurrentPromises);
        const successfulRequests = concurrentResults.filter(Boolean).length;
        
        this.log('performance', `Concurrent requests: ${successfulRequests}/${concurrentPromises.length} successful`);
    }

    updateSummary() {
        const summaryElement = document.getElementById('test-summary');
        const results = Array.from(this.testResults.values());
        const total = results.length;
        const passed = results.filter(r => r.status === 'success').length;
        const failed = results.filter(r => r.status === 'error').length;
        
        let indicator = 'disconnected';
        let message = 'Ready to run tests...';
        
        if (total > 0) {
            if (failed === 0) {
                indicator = 'connected';
                message = `All ${passed} tests passed ✅`;
            } else if (passed > 0) {
                indicator = 'checking';
                message = `${passed} passed, ${failed} failed ⚠️`;
            } else {
                indicator = 'disconnected';
                message = `All ${failed} tests failed ❌`;
            }
        }
        
        summaryElement.innerHTML = `
            <span class="connection-indicator ${indicator}"></span>
            ${message}
        `;
        
        if (total > 0) {
            summaryElement.innerHTML += `<br><small>Total: ${total}, Passed: ${passed}, Failed: ${failed}</small>`;
        }
    }
}

// Initialize test runner when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.integrationTestRunner = new IntegrationTestRunner();
});

// Export for potential external use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = IntegrationTestRunner;
}