/**
 * Environment variable validation module for Kaz Legal Bot frontend.
 */

function validateEnvironmentVariables() {
    const errors = [];
    const warnings = [];
    
    // Required environment variables for frontend
    const requiredVars = {
        'BACKEND_URL': {
            description: 'Backend API URL for the legal assistant',
            example: 'https://ai-lawyer.up.railway.app',
            validator: (x) => x && (x.startsWith('http://') || x.startsWith('https://'))
        }
    };
    
    // Optional but recommended environment variables
    const optionalVars = {
        'API_TIMEOUT': {
            description: 'Timeout for API requests in milliseconds',
            example: '30000',
            validator: (x) => x && !isNaN(parseInt(x)) && parseInt(x) > 0
        },
        'MAX_FILE_SIZE': {
            description: 'Maximum file upload size in bytes',
            example: '16777216',
            validator: (x) => x && !isNaN(parseInt(x)) && parseInt(x) > 0
        }
    };
    
    // Check required variables
    for (const [varName, config] of Object.entries(requiredVars)) {
        const value = getEnvironmentVariable(varName);
        if (!value) {
            errors.push(`❌ REQUIRED: ${varName} is not set.`);
            errors.push(`   Description: ${config.description}`);
            errors.push(`   Example: ${config.example}`);
        } else if (!config.validator(value)) {
            errors.push(`❌ INVALID: ${varName} has invalid format.`);
            errors.push(`   Current value: ${value.substring(0, 50)}...`);
            errors.push(`   Expected format: ${config.example}`);
        }
    }
    
    // Check optional variables
    for (const [varName, config] of Object.entries(optionalVars)) {
        const value = getEnvironmentVariable(varName);
        if (!value) {
            warnings.push(`⚠️  OPTIONAL: ${varName} is not set.`);
            warnings.push(`   Description: ${config.description}`);
            warnings.push(`   Example: ${config.example}`);
        } else if (!config.validator(value)) {
            warnings.push(`⚠️  INVALID: ${varName} has invalid format.`);
            warnings.push(`   Current value: ${value.substring(0, 50)}`);
            warnings.push(`   Expected format: ${config.example}`);
        }
    }
    
    // Print warnings to console
    if (warnings.length > 0) {
        console.warn('⚠️  Environment Variable Warnings:');
        warnings.forEach(warning => console.warn(`   ${warning}`));
        console.warn('');
    }
    
    // Show error dialog if there are errors
    if (errors.length > 0) {
        const errorMessage = [
            '❌ Environment Variable Validation Failed!',
            '=' * 60,
            ...errors,
            '=' * 60,
            'Please configure the required environment variables.',
            '',
            'For development, you can set these in your build configuration:',
            'BACKEND_URL=https://ai-lawyer.up.railway.app',
            'API_TIMEOUT=30000',
            'MAX_FILE_SIZE=16777216',
            '',
            'The application may not work correctly without proper configuration.'
        ].join('\n');
        
        console.error(errorMessage);
        
        // Show user-friendly error dialog
        showEnvironmentErrorDialog(errors);
        return false;
    }
    
    console.log('✅ Environment variable validation successful!');
    return true;
}

function getEnvironmentVariable(varName) {
    // In a frontend context, environment variables might be:
    // 1. Injected at build time (process.env for webpack/vite)
    // 2. Available as window.env for runtime configuration
    // 3. Hardcoded for static deployments
    
    if (typeof process !== 'undefined' && process.env && process.env[varName]) {
        return process.env[varName];
    }
    
    if (typeof window !== 'undefined' && window.env && window.env[varName]) {
        return window.env[varName];
    }
    
    // Fallback for common variables
    const fallbacks = {
        'BACKEND_URL': '/api', // Uses Vercel proxy by default
        'API_TIMEOUT': '30000',
        'MAX_FILE_SIZE': '16777216'
    };
    
    return fallbacks[varName];
}

function showEnvironmentErrorDialog(errors) {
    // Create error dialog
    const dialog = document.createElement('div');
    dialog.className = 'env-error-dialog';
    dialog.innerHTML = `
        <div class="env-error-content">
            <h2>⚠️ Configuration Error</h2>
            <p>The application is missing required configuration. Please contact your system administrator.</p>
            <details>
                <summary>Technical Details</summary>
                <pre>${errors.join('\n')}</pre>
            </details>
            <button onclick="this.parentElement.parentElement.remove()">Close</button>
        </div>
    `;
    
    // Add styles
    const style = document.createElement('style');
    style.textContent = `
        .env-error-dialog {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 10000;
        }
        .env-error-content {
            background: #fff;
            padding: 2rem;
            border-radius: 8px;
            max-width: 600px;
            max-height: 80vh;
            overflow-y: auto;
        }
        .env-error-content h2 {
            color: #d32f2f;
            margin-top: 0;
        }
        .env-error-content pre {
            background: #f5f5f5;
            padding: 1rem;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 0.8em;
        }
        .env-error-content button {
            background: #1976d2;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            margin-top: 1rem;
        }
        .env-error-content button:hover {
            background: #1565c0;
        }
    `;
    
    document.head.appendChild(style);
    document.body.appendChild(dialog);
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { validateEnvironmentVariables, getEnvironmentVariable };
}

// Auto-validate on load in browser environment (except for test pages)
if (typeof window !== 'undefined' && !window.location.pathname.includes('test')) {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', validateEnvironmentVariables);
    } else {
        validateEnvironmentVariables();
    }
}