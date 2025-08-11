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

    // База бэкенда из переменной окружения (обязательно укажите её в Vercel!)
    const rawBase = (process.env.RAILWAY_BACKEND_URL || 'https://ai-lawyer.up.railway.app').trim();
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
    const backendUrl = new URL(targetPath + queryString, validatedBase).toString();

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

    // Выполняем запрос к бэкенду
    const backendResponse = await fetchFunc(backendUrl, {
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
