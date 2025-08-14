// Serverless proxy for Vercel -> Railway backend
// CommonJS (чтобы не было ESM→CJS варнингов)

const { Readable } = require('stream');

const ALLOWED_HEADERS = [
  // Безопасные/нужные для бэкенда заголовки
  'accept',
  'accept-language',
  'content-type',
  'authorization',
  'x-requested-with',
  'cookie',
];

function setCors(res) {
  // CORS на всякий случай (хотя в one-origin прокси обычно не требуется)
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PUT,PATCH,DELETE,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With');
  res.setHeader('Access-Control-Allow-Credentials', 'true');
  res.setHeader('Access-Control-Max-Age', '86400');
}

module.exports = async (req, res) => {
  try {
    setCors(res);

    // Preflight
    if (req.method === 'OPTIONS') {
      return res.status(204).send('');
    }

    const backendBase =
      process.env.BACKEND_URL ||
      process.env.RAILWAY_BACKEND_URL ||
      '';

    if (!backendBase || !/^https?:\/\//.test(backendBase)) {
      return res
        .status(500)
        .send('Proxy misconfigured: BACKEND_URL is not set or invalid');
    }

    // Мы ожидаем, что vercel.json положит оригинальный путь в query ?path=...
    const { path = '' } = req.query;

    // Собираем целевой URL
    const targetUrl = new URL(path.startsWith('/') ? path : `/${path}`, backendBase);

    // Переносим все query-параметры кроме path
    const sp = new URLSearchParams(req.query);
    sp.delete('path');
    // Если были параметры в исходном запросе, добавим их
    for (const [k, v] of sp.entries()) {
      targetUrl.searchParams.append(k, v);
    }

    // Подготовим заголовки
    const headers = {};
    for (const [k, v] of Object.entries(req.headers)) {
      const name = k.toLowerCase();
      if (ALLOWED_HEADERS.includes(name)) {
        headers[name] = v;
      }
    }
    // Доп. заголовки, полезные для бэкенда
    headers['x-forwarded-host'] = req.headers['host'] || '';
    headers['x-forwarded-proto'] = 'https';

    // Тело запроса (только для методов с телом)
    let body = undefined;
    if (!['GET', 'HEAD'].includes(req.method.toUpperCase())) {
      body = req;
    }

    // Проксируем
    const upstream = await fetch(targetUrl.toString(), {
      method: req.method,
      headers,
      body,
      duplex: body ? 'half' : undefined, // для Node 18 при потоке
    });

    // Пробрасываем статус и важные заголовки
    res.status(upstream.status);
    // Переносим заголовки, кроме hop-by-hop
    upstream.headers.forEach((val, key) => {
      if (!['content-length', 'transfer-encoding', 'connection'].includes(key.toLowerCase())) {
        res.setHeader(key, val);
      }
    });
    setCors(res); // ещё раз, чтобы не потерялись

    // Потоково отдадим тело
    if (upstream.body) {
      // Node18: web ReadableStream → Node Readable
      const nodeStream = Readable.fromWeb
        ? Readable.fromWeb(upstream.body)
        : upstream.body;
      return nodeStream.pipe(res);
    } else {
      const buf = Buffer.from(await upstream.arrayBuffer());
      return res.send(buf);
    }
  } catch (err) {
    console.error('Proxy error:', err);
    setCors(res);
    res.status(502).send(`Proxy error: ${err.message || String(err)}`);
  }
};
