// api/[...path].js
// Catch-all прокси: любой запрос на /api/* → на Railway backend

const getFetch = async () => {
  if (typeof fetch === 'function') return fetch;
  const { default: nodeFetch } = await import('node-fetch');
  return nodeFetch;
};

async function readRawBody(req) {
  return await new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', c => chunks.push(Buffer.isBuffer(c) ? c : Buffer.from(c)));
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

export default async function handler(req, res) {
  try {
    const method = (req.method || 'GET').toUpperCase();

    // В Vercel установи одну из переменных:
    // RAILWAY_BACKEND_URL=https://ai-lawyer.up.railway.app
    // или BACKEND_URL=...
    const backendBase =
      (process.env.RAILWAY_BACKEND_URL || process.env.BACKEND_URL || '').trim();

    if (!backendBase) {
      return res.status(500).json({
        error: 'CONFIGURATION_ERROR',
        message:
          'Backend URL not configured. Set RAILWAY_BACKEND_URL (or BACKEND_URL), e.g. https://ai-lawyer.up.railway.app',
      });
    }
    if (!/^https?:\/\//i.test(backendBase)) {
      return res.status(500).json({
        error: 'CONFIGURATION_ERROR',
        message:
          'Invalid backend URL. It must start with http:// or https://. Current: ' +
          backendBase,
      });
    }

    const base = new URL(backendBase).toString();

    // Путь после /api (учитываем и /api/proxy/* если когда-то был такой)
    const urlPath =
      '/' +
      (Array.isArray(req.query?.path) ? req.query.path.join('/') : '')
        .replace(/^\/+/, '');

    const stripped = (req.url || '')
      .replace(/^\/api(?:\/proxy)?/, '') // срежем /api или /api/proxy
      .split('?')[0] || '/';

    const targetPath = urlPath !== '/' ? urlPath : stripped || '/';

    // Query string
    const qs = req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : '';

    // Полный целевой URL
    const targetUrl = new URL(targetPath + qs, base).toString();

    // Диагностика: GET /api/__diag
    if (targetPath === '/__diag') {
      const diag = {
        status: 'ok',
        timestamp: new Date().toISOString(),
        backendBase: base,
        targetUrl,
        env: {
          RAILWAY_BACKEND_URL: process.env.RAILWAY_BACKEND_URL || null,
          BACKEND_URL: process.env.BACKEND_URL || null,
          VERCEL_ENV: process.env.VERCEL_ENV || null,
        },
      };
      try {
        const f = await getFetch();
        const r = await f(new URL('/health', base).toString());
        diag.health = { ok: r.ok, status: r.status };
      } catch (e) {
        diag.health = { ok: false, error: String(e?.message || e) };
      }
      return res.status(200).json(diag);
    }

    // Тело запроса (для POST/PUT/…)
    let body;
    const ct = (req.headers['content-type'] || '').toLowerCase();
    if (!['GET', 'HEAD'].includes(method)) {
      const raw = await readRawBody(req);
      body = ct.includes('application/json') ? raw.toString('utf8') : raw;
    }

    // Проброс важных заголовков
    const headers = {};
    if (req.headers['content-type']) headers['Content-Type'] = req.headers['content-type'];
    if (req.headers['authorization']) headers['Authorization'] = req.headers['authorization'];
    if (req.headers['cookie']) headers['Cookie'] = req.headers['cookie'];

    const f = await getFetch();
    const r = await f(targetUrl, { method, headers, body });

    // Проксируем ответ
    res.status(r.status);
    const contentType = r.headers.get('content-type') || 'text/plain; charset=utf-8';
    res.setHeader('Content-Type', contentType);

    // Для простоты читаем текстом (фронту подходит и для stream HTML)
    const text = await r.text();
    res.send(text);
  } catch (e) {
    console.error('Proxy error:', e);
    res.status(500).json({
      error: 'FUNCTION_INVOCATION_FAILED',
      message: e?.message || 'Unknown error',
    });
  }
}
