/**
 * Environment variable validation module for Kaz Legal Bot frontend.
 * Работает в чисто статическом фронтенде (без сборщика) и допускает
 * использование прокси /api на Vercel как корректный BACKEND_URL.
 */

(function () {
    // Экспортируемые функции/переменные будут висеть на window и (если нужно) на module.exports
    function getEnvironmentVariable(varName) {
      // 1) Инлайн-конфиг (если подключите <script> с window.__ENV__)
      if (typeof window !== 'undefined') {
        if (window.__ENV__ && window.__ENV__[varName]) return String(window.__ENV__[varName]);
        if (window.env && window.env[varName]) return String(window.env[varName]);
        if (varName === 'BACKEND_URL' && typeof window.BACKEND_URL === 'string') return window.BACKEND_URL;
      }
  
      // 2) В среде сборщика (на всякий) — не обязателен для статического варианта
      if (typeof process !== 'undefined' && process.env && process.env[varName]) {
        return String(process.env[varName]);
      }
  
      // 3) Значения по умолчанию для статического деплоя
      const fallbacks = {
        BACKEND_URL: '/api',      // Через Vercel proxy-функцию
        API_TIMEOUT: '30000',
        MAX_FILE_SIZE: '16777216',
      };
      return fallbacks[varName];
    }
  
    function isValidBackendUrl(value) {
      if (!value) return false;
      const v = String(value).trim();
  
      // Разрешаем абсолютные http(s) адреса
      if (/^https?:\/\/.+/i.test(v)) return true;
  
      // Разрешаем прокси на Vercel: /api И /api/*
      if (v === '/api' || v.startsWith('/api/')) return true;
  
      return false;
    }
  
    function validateEnvironmentVariables() {
      const errors = [];
      const warnings = [];
  
      // Обязательные переменные
      const requiredVars = {
        BACKEND_URL: {
          description: 'Backend API URL for the legal assistant',
          example: 'https://ai-lawyer.up.railway.app  (или /api при использовании Vercel Proxy)',
          validator: isValidBackendUrl,
        },
      };
  
      // Необязательные, но желательные
      const optionalVars = {
        API_TIMEOUT: {
          description: 'Timeout for API requests in milliseconds',
          example: '30000',
          validator: (x) => x && !isNaN(parseInt(x, 10)) && parseInt(x, 10) > 0,
        },
        MAX_FILE_SIZE: {
          description: 'Maximum file upload size in bytes',
          example: '16777216',
          validator: (x) => x && !isNaN(parseInt(x, 10)) && parseInt(x, 10) > 0,
        },
      };
  
      // Проверяем обязательные
      for (const [name, cfg] of Object.entries(requiredVars)) {
        const val = getEnvironmentVariable(name);
        if (!val) {
          errors.push(`❌ REQUIRED: ${name} is not set.`);
          errors.push(`   Description: ${cfg.description}`);
          errors.push(`   Example: ${cfg.example}`);
        } else if (!cfg.validator(val)) {
          // Особый случай: если пользователь оставил '/api', это валидно (через прокси), но проверка выше уже бы пропустила.
          errors.push(`❌ INVALID: ${name} has invalid format.`);
          errors.push(`   Current value: ${String(val).slice(0, 80)}${String(val).length > 80 ? '…' : ''}`);
          errors.push(`   Expected: Absolute URL (https://…) or '/api' when using Vercel proxy.`);
        }
      }
  
      // Проверяем необязательные
      for (const [name, cfg] of Object.entries(optionalVars)) {
        const val = getEnvironmentVariable(name);
        if (!val) {
          warnings.push(`⚠️ OPTIONAL: ${name} is not set.`);
          warnings.push(`   Description: ${cfg.description}`);
          warnings.push(`   Example: ${cfg.example}`);
        } else if (!cfg.validator(val)) {
          warnings.push(`⚠️ INVALID: ${name} has invalid format.`);
          warnings.push(`   Current value: ${String(val).slice(0, 80)}${String(val).length > 80 ? '…' : ''}`);
          warnings.push(`   Expected: ${cfg.example}`);
        }
      }
  
      // Пишем предупреждения (не блокируем работу)
      if (warnings.length) {
        console.warn('⚠️ Environment Variable Warnings:');
        warnings.forEach((w) => console.warn('   ' + w));
        console.warn('');
      }
  
      // Если есть ошибки — показываем аккуратно. НО:
      // если BACKEND_URL === '/api' (или '/api/*'), это валидно — ошибок быть не должно.
      if (errors.length) {
        const msg = [
          '❌ Environment Variable Validation Failed!',
          '='.repeat(60),
          ...errors,
          '='.repeat(60),
          'Please configure the required environment variables.',
          '',
          'For development examples:',
          'BACKEND_URL=https://ai-lawyer.up.railway.app   (или BACKEND_URL=/api при Vercel proxy)',
          'API_TIMEOUT=30000',
          'MAX_FILE_SIZE=16777216',
          '',
          'The application may not work correctly without proper configuration.',
        ].join('\n');
  
        console.error(msg);
  
        // Показываем диалог ТОЛЬКО если значение действительно некорректно и это не прокси.
        const backend = getEnvironmentVariable('BACKEND_URL');
        const usingProxy = backend && (backend === '/api' || backend.startsWith('/api/'));
        if (!usingProxy) {
          showEnvironmentErrorDialog(errors);
        }
        return false;
      }
  
      console.log('✅ Environment variable validation successful!');
      return true;
    }
  
    function showEnvironmentErrorDialog(errors) {
      try {
        const dialog = document.createElement('div');
        dialog.className = 'env-error-dialog';
        dialog.innerHTML = `
          <div class="env-error-content">
            <h2>⚠️ Configuration Error</h2>
            <p>The application is missing required configuration.</p>
            <details>
              <summary>Technical Details</summary>
              <pre>${errors.map((e) => escapeHtml(e)).join('\n')}</pre>
            </details>
            <button type="button" id="env-error-close">Close</button>
          </div>
        `;
  
        const style = document.createElement('style');
        style.textContent = `
          .env-error-dialog {
            position: fixed; inset: 0;
            background: rgba(0,0,0,.8);
            display: flex; align-items: center; justify-content: center;
            z-index: 10000;
          }
          .env-error-content {
            background: #fff; color: #111;
            padding: 1.5rem; border-radius: 10px; width: min(90vw, 640px);
            max-height: 80vh; overflow: auto; box-shadow: 0 10px 30px rgba(0,0,0,.4);
            font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
          }
          .env-error-content h2 { margin: 0 0 .75rem 0; color: #d32f2f; }
          .env-error-content pre {
            background: #f6f8fa; border: 1px solid #e5e7eb; border-radius: 6px;
            padding: .75rem; overflow: auto; font-size: .85rem;
          }
          .env-error-content button {
            margin-top: .9rem; background: #1976d2; color: #fff; border: 0;
            padding: .5rem 1rem; border-radius: 6px; cursor: pointer;
          }
          .env-error-content button:hover { background: #1565c0; }
        `;
  
        document.head.appendChild(style);
        document.body.appendChild(dialog);
        dialog.querySelector('#env-error-close')?.addEventListener('click', () => dialog.remove());
      } catch (e) {
        console.error('Failed to show environment error dialog:', e);
      }
    }
  
    function escapeHtml(s) {
      return String(s)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
    }
  
    // Экспорт
    if (typeof window !== 'undefined') {
      window.validateEnvironmentVariables = validateEnvironmentVariables;
      window.getEnvironmentVariable = getEnvironmentVariable;
    }
    if (typeof module !== 'undefined' && module.exports) {
      module.exports = { validateEnvironmentVariables, getEnvironmentVariable };
    }
  
    // Автозапуск, кроме тестовых страниц
    if (typeof window !== 'undefined' && !window.location.pathname.includes('test')) {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', validateEnvironmentVariables);
      } else {
        validateEnvironmentVariables();
      }
    }
  })();
  