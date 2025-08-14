/**
 * Deployment Validation Script
 * Validates the deployment and proxy configuration in staging/production environments
 */

class DeploymentValidator {
    constructor() {
        this.apiBase = '/api';
        this.validationResults = [];
        this.isProduction = window.location.hostname !== 'localhost' && !window.location.hostname.includes('127.0.0.1');
        
        console.log('🚀 Deployment Validator initialized');
        console.log('Environment:', this.isProduction ? 'Production/Staging' : 'Development');
    }

    async validateDeployment() {
        console.log('🔍 Starting deployment validation...');
        
        try {
            await this.validateProxyConfiguration();
            await this.validateHealthEndpoint();
            await this.validateAPIEndpoints();
            await this.validateErrorHandling();
            await this.validateConnectionMonitoring();
            
            this.generateValidationReport();
            
        } catch (error) {
            console.error('❌ Deployment validation failed:', error);
            this.validationResults.push({
                test: 'Overall Validation',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date().toISOString()
            });
        }
    }

    async validateProxyConfiguration() {
        console.log('🔧 Validating proxy configuration...');
        
        const testEndpoints = [
            '/health',
            '/get-all-sessions-summary'
        ];
        
        for (const endpoint of testEndpoints) {
            try {
                const url = `${this.apiBase}${endpoint}`;
                console.log(`Testing proxy URL: ${url}`);
                
                const response = await fetch(url, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                // Check if we're getting proper responses (not 404s from proxy misconfiguration)
                if (response.status === 404) {
                    throw new Error(`Proxy misconfiguration: ${endpoint} returns 404`);
                }
                
                this.validationResults.push({
                    test: `Proxy Configuration - ${endpoint}`,
                    status: 'PASSED',
                    details: `Status: ${response.status}`,
                    timestamp: new Date().toISOString()
                });
                
                console.log(`✅ ${endpoint}: ${response.status}`);
                
            } catch (error) {
                this.validationResults.push({
                    test: `Proxy Configuration - ${endpoint}`,
                    status: 'FAILED',
                    error: error.message,
                    timestamp: new Date().toISOString()
                });
                
                console.error(`❌ ${endpoint}: ${error.message}`);
            }
        }
    }

    async validateHealthEndpoint() {
        console.log('❤️ Validating health endpoint...');
        
        try {
            const startTime = performance.now();
            const response = await fetch(`${this.apiBase}/health`);
            const endTime = performance.now();
            const responseTime = endTime - startTime;
            
            if (!response.ok) {
                throw new Error(`Health endpoint failed: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.status !== 'healthy') {
                throw new Error(`Backend unhealthy: ${data.status}`);
            }
            
            this.validationResults.push({
                test: 'Health Endpoint',
                status: 'PASSED',
                details: `Response time: ${responseTime.toFixed(2)}ms, Status: ${data.status}`,
                timestamp: new Date().toISOString()
            });
            
            console.log(`✅ Health check passed in ${responseTime.toFixed(2)}ms`);
            
        } catch (error) {
            this.validationResults.push({
                test: 'Health Endpoint',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date().toISOString()
            });
            
            console.error(`❌ Health check failed: ${error.message}`);
            throw error; // Re-throw as this is critical
        }
    }

    async validateAPIEndpoints() {
        console.log('📡 Validating API endpoints...');
        
        const endpoints = [
            { path: '/get-all-sessions-summary', method: 'GET', critical: true },
            { path: '/ask', method: 'POST', critical: false, body: { question: 'test' } }
        ];
        
        for (const endpoint of endpoints) {
            try {
                const options = {
                    method: endpoint.method,
                    headers: {
                        'Content-Type': 'application/json'
                    }
                };
                
                if (endpoint.body) {
                    options.body = JSON.stringify(endpoint.body);
                }
                
                const response = await fetch(`${this.apiBase}${endpoint.path}`, options);
                
                // For non-critical endpoints, we just check they're accessible
                const isAccessible = response.status !== 404 && response.status !== 502;
                
                if (endpoint.critical && !response.ok) {
                    throw new Error(`Critical endpoint failed: ${response.status}`);
                }
                
                this.validationResults.push({
                    test: `API Endpoint - ${endpoint.method} ${endpoint.path}`,
                    status: isAccessible ? 'PASSED' : 'FAILED',
                    details: `Status: ${response.status}`,
                    timestamp: new Date().toISOString()
                });
                
                console.log(`${isAccessible ? '✅' : '❌'} ${endpoint.method} ${endpoint.path}: ${response.status}`);
                
            } catch (error) {
                this.validationResults.push({
                    test: `API Endpoint - ${endpoint.method} ${endpoint.path}`,
                    status: 'FAILED',
                    error: error.message,
                    timestamp: new Date().toISOString()
                });
                
                console.error(`❌ ${endpoint.method} ${endpoint.path}: ${error.message}`);
                
                if (endpoint.critical) {
                    throw error;
                }
            }
        }
    }

    async validateErrorHandling() {
        console.log('🛠️ Validating error handling...');
        
        try {
            // Test 404 handling
            const response = await fetch(`${this.apiBase}/nonexistent-endpoint-${Date.now()}`);
            
            if (response.status === 404 || response.status === 502) {
                this.validationResults.push({
                    test: 'Error Handling - 404',
                    status: 'PASSED',
                    details: `Correctly returned ${response.status}`,
                    timestamp: new Date().toISOString()
                });
                
                console.log(`✅ 404 handling works: ${response.status}`);
            } else {
                throw new Error(`Expected 404/502, got ${response.status}`);
            }
            
        } catch (error) {
            this.validationResults.push({
                test: 'Error Handling',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date().toISOString()
            });
            
            console.error(`❌ Error handling validation failed: ${error.message}`);
        }
    }

    async validateConnectionMonitoring() {
        console.log('📊 Validating connection monitoring...');
        
        try {
            // Check if connection monitor is loaded
            if (window.connectionMonitor) {
                console.log('✅ Connection monitor found');
                
                // Test manual health check
                const healthResult = await window.connectionMonitor.checkHealth();
                
                this.validationResults.push({
                    test: 'Connection Monitoring',
                    status: healthResult ? 'PASSED' : 'WARNING',
                    details: `Manual health check: ${healthResult}`,
                    timestamp: new Date().toISOString()
                });
                
                console.log(`${healthResult ? '✅' : '⚠️'} Connection monitor health check: ${healthResult}`);
                
            } else {
                this.validationResults.push({
                    test: 'Connection Monitoring',
                    status: 'WARNING',
                    details: 'Connection monitor not found',
                    timestamp: new Date().toISOString()
                });
                
                console.log('⚠️ Connection monitor not found');
            }
            
        } catch (error) {
            this.validationResults.push({
                test: 'Connection Monitoring',
                status: 'FAILED',
                error: error.message,
                timestamp: new Date().toISOString()
            });
            
            console.error(`❌ Connection monitoring validation failed: ${error.message}`);
        }
    }

    generateValidationReport() {
        console.log('📋 Generating validation report...');
        
        const passed = this.validationResults.filter(r => r.status === 'PASSED').length;
        const failed = this.validationResults.filter(r => r.status === 'FAILED').length;
        const warnings = this.validationResults.filter(r => r.status === 'WARNING').length;
        
        const report = {
            environment: this.isProduction ? 'Production/Staging' : 'Development',
            timestamp: new Date().toISOString(),
            summary: {
                total: this.validationResults.length,
                passed: passed,
                failed: failed,
                warnings: warnings
            },
            results: this.validationResults
        };
        
        console.log('📊 Validation Report:', report);
        
        // Store report in sessionStorage for access by test runner
        sessionStorage.setItem('deploymentValidationReport', JSON.stringify(report));
        
        // Display summary
        if (failed === 0) {
            console.log(`✅ Deployment validation completed successfully! ${passed} tests passed, ${warnings} warnings`);
        } else {
            console.error(`❌ Deployment validation failed! ${failed} tests failed, ${passed} passed, ${warnings} warnings`);
        }
        
        return report;
    }

    async runContinuousValidation(intervalMs = 300000) { // 5 minutes
        console.log(`🔄 Starting continuous validation (every ${intervalMs/1000}s)`);
        
        const runValidation = async () => {
            try {
                await this.validateHealthEndpoint();
                await this.validateProxyConfiguration();
                console.log('🔄 Continuous validation cycle completed');
            } catch (error) {
                console.error('🔄 Continuous validation cycle failed:', error);
            }
        };
        
        // Run initial validation
        await runValidation();
        
        // Set up interval
        setInterval(runValidation, intervalMs);
    }
}

// Auto-initialize on load
document.addEventListener('DOMContentLoaded', () => {
    window.deploymentValidator = new DeploymentValidator();
    
    // Run validation automatically if in production/staging
    if (window.deploymentValidator.isProduction) {
        console.log('🚀 Running automatic deployment validation...');
        window.deploymentValidator.validateDeployment()
            .then(() => console.log('✅ Automatic validation completed'))
            .catch(error => console.error('❌ Automatic validation failed:', error));
    }
});

// Export for manual use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DeploymentValidator;
}