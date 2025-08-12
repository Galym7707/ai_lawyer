// frontend/api/proxy/[...path].js

// Динамически подключаем node-fetch при необходимости (если fetch не глобальный)
const getFetch = async () => {
  if (typeof fetch === 'function') return fetch;
  const { default: nodeFetch } = await import('node-fetch');
  return nodeFetch;
};

// Читаем сырое тело запроса (нужно для JSON и multipart)
async function readRawBody(req) {
  return await new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', chunk => chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)));
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

export default async function handler(req, res) {
  try {
    const method = (req.method || 'GET').toUpperCase();

    // Environment variable validation
    const backendUrl = process.env.RAILWAY_BACKEND_URL || process.env.BACKEND_URL;
    
    if (!backendUrl) {
      console.error('❌ REQUIRED: RAILWAY_BACKEND_URL or BACKEND_URL is not set.');
      console.error('   Description: Backend API URL for the legal assistant');
      console.error('   Example: https://ai-lawyer.up.railway.app');
      return res.status(500).json({
        error: 'CONFIGURATION_ERROR',
        message: 'Backend URL not configured. Please set RAILWAY_BACKEND_URL or BACKEND_URL environment variable.',
        example: 'https://ai-lawyer.up.railway.app'
      });
    }
    
    if (!backendUrl.startsWith('http://') && !backendUrl.startsWith('https://')) {
      console.error(`❌ INVALID: Backend URL must start with http:// or https://. Current: ${backendUrl}`);
      return res.status(500).json({
        error: 'CONFIGURATION_ERROR',
        message: 'Invalid backend URL format. Must start with http:// or https://',
        current: backendUrl.substring(0, 50),
        example: 'https://ai-lawyer.up.railway.app'
      });
    }

    // База бэкенда из переменной окружения (обязательно укажите её в Vercel!)
    const rawBase = backendUrl.trim();
    // Валидация URL базы (если некорректна — бросим понятную ошибку)
    const validatedBase = new URL(rawBase).toString();

    // Путь для бэкенда: пробуем взять из req.query.path, иначе срежем префикс из req.url
    let targetPath = '/';
    try {
      const { path = [] } = req.query || {};
      if (Array.isArray(path) && path.length > 0) {
        targetPath = '/' + path.join('/');
      } else {
        targetPath = req.url.replace(/^\/api\/proxy/, '').split('?')[0] || '/';
      }
    } catch (_) {
      targetPath = req.url.replace(/^\/api\/proxy/, '').split('?')[0] || '/';
    }

    // Query-строка, если была
    const queryString = req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : '';
    const backendUrlFull = new URL(targetPath + queryString, validatedBase).toString();

    // Enhanced diagnostics endpoint for debugging deployment issues: /api/__diag
    if (targetPath === '/__diag') {
      const diagnostics = {
        status: 'success',
        timestamp: new Date().toISOString(),
        environment: {
          node_version: process.version,
          platform: process.platform,
          vercel_region: process.env.VERCEL_REGION || 'unknown',
          vercel_env: process.env.VERCEL_ENV || 'unknown'
        },
        proxy_configuration: {
          backend_url_env_var: process.env.RAILWAY_BACKEND_URL || process.env.BACKEND_URL || null,
          backend_url_raw: rawBase,
          backend_url_validated: validatedBase,
          current_request: {
            method: method,
            target_path: targetPath,
            query_string: queryString,
            constructed_backend_url: backendUrlFull,
            user_agent: req.headers['user-agent'] || null,
            content_type: req.headers['content-type'] || null
          }
        },
        environment_variables: {
          railway_backend_url: {
            value: process.env.RAILWAY_BACKEND_URL || null,
            status: process.env.RAILWAY_BACKEND_URL ? 'present' : 'missing'
          },
          backend_url: {
            value: process.env.BACKEND_URL || null,
            status: process.env.BACKEND_URL ? 'present' : 'missing'
          },
          vercel_url: {
            value: process.env.VERCEL_URL || null,
            status: process.env.VERCEL_URL ? 'present' : 'missing'
          },
          vercel_branch_url: {
            value: process.env.VERCEL_BRANCH_URL || null,
            status: process.env.VERCEL_BRANCH_URL ? 'present' : 'missing'
          }
        },
        connection_validation: {
          backend_url_valid: false,
          backend_reachable: false,
          validation_error: null,
          response_time_ms: null
        }
      };

      // Validate backend URL format
      try {
        new URL(validatedBase);
        diagnostics.connection_validation.backend_url_valid = true;
      } catch (urlError) {
        diagnostics.connection_validation.validation_error = `Invalid backend URL format: ${urlError.message}`;
      }

      // Test backend connectivity
      if (diagnostics.connection_validation.backend_url_valid) {
        try {
          const fetchFunc = await getFetch();
          const startTime = Date.now();
          const healthCheckResponse = await fetchFunc(`${validatedBase}/health`, {
            method: 'GET',
            timeout: 10000 // 10 second timeout
          });
          const responseTime = Date.now() - startTime;
          
          diagnostics.connection_validation.backend_reachable = healthCheckResponse.ok;
          diagnostics.connection_validation.response_time_ms = responseTime;
          
          if (!healthCheckResponse.ok) {
            diagnostics.connection_validation.validation_error = `Backend responded with status: ${healthCheckResponse.status}`;
          }
        } catch (connectionError) {
          diagnostics.connection_validation.validation_error = `Connection failed: ${connectionError.message}`;
        }
      }

      // Check for common configuration issues
      const configurationIssues = [];
      if (!process.env.RAILWAY_BACKEND_URL && !process.env.BACKEND_URL) {
        configurationIssues.push('RAILWAY_BACKEND_URL or BACKEND_URL environment variable is not set');
      }
      if (!diagnostics.connection_validation.backend_url_valid) {
        configurationIssues.push('Backend URL format is invalid');
      }
      if (!diagnostics.connection_validation.backend_reachable) {
        configurationIssues.push('Backend server is not reachable');
      }

      diagnostics.configuration_issues = configurationIssues;
      diagnostics.overall_status = configurationIssues.length === 0 ? 'healthy' : 'issues_detected';

      res.status(200).json(diagnostics);
      return;
    }

    // Собираем тело запроса
    let requestBody;
    const contentType = (req.headers['content-type'] || '').toLowerCase();
    if (!['GET', 'HEAD'].includes(method)) {
      // Считываем сырое тело (Buffer)
      const rawBody = await readRawBody(req);
      if (contentType.includes('application/json')) {
        // Для JSON — передаём строку
        requestBody = rawBody.length ? rawBody.toString('utf8') : undefined;
      } else {
        // Для остальных типов — передаём как Buffer (сохраняем boundary и т.п.)
        requestBody = rawBody.length ? rawBody : undefined;
      }
    }

    const fetchFunc = await getFetch();

    // Прокидываем только безопасные/нужные заголовки
    const headersToForward = {};
    if (req.headers['content-type']) headersToForward['Content-Type'] = req.headers['content-type'];
    if (req.headers['authorization']) headersToForward['Authorization'] = req.headers['authorization'];
    if (req.headers['cookie']) headersToForward['Cookie'] = req.headers['cookie'];

    // Логируем ключевые значения для отладки в Vercel Function Logs
    console.log('[proxy] method=', method, 'base=', validatedBase, 'path=', targetPath, 'url=', backendUrlFull);

    // Выполняем запрос к бэкенду
    const backendResponse = await fetchFunc(backendUrlFull, {
      method,
      headers: headersToForward,
      body: requestBody,
    });

    // Прокидываем ответ бэкенда как есть
    const contentTypeFromBackend = backendResponse.headers.get('content-type') || 'application/json; charset=utf-8';
    res.status(backendResponse.status);
    res.setHeader('Content-Type', contentTypeFromBackend);
    const data = await backendResponse.text();
    res.send(data);
  } catch (error) {
    // Детальный лог на сервере Vercel, чтобы увидеть реальную причину 500
    console.error('❌ Proxy handler failed:', error);
    res.status(500).json({
      error: 'FUNCTION_INVOCATION_FAILED',
      message: error && error.message ? error.message : 'Unknown error',
    });
  }
}