// frontend/api/[...path].js
// Универсальный прокси Vercel → Railway
// Работает для GET/POST/stream/multipart, безопасно пробрасывает заголовки и тело.

const BACKEND =
  (process.env.RAILWAY_BACKEND_URL || process.env.BACKEND_URL || 'https://ai-lawyer.up.railway.app')
    .replace(/\/+$/, '');

module.exports = async (req, res) => {
  // Быстрый ответ на preflight
  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  try {
    // Собираем путь /api/xxx → /xxx
    const seg = req.query.path;
    const path = Array.isArray(seg) ? seg.join('/') : (seg || '');
    const qIndex = req.url.indexOf('?');
    const qs = qIndex !== -1 ? req.url.slice(qIndex) : '';
    const url = `${BACKEND}/${path}${qs}`;

    // Копируем заголовки и убираем host (иначе прокси может ругаться)
    const headers = { ...req.headers };
    delete headers.host;

    // Читаем тело запроса (кроме GET/HEAD)
    let body = undefined;
    if (!['GET', 'HEAD'].includes(req.method)) {
      const chunks = [];
      for await (const chunk of req) chunks.push(chunk);
      body = Buffer.concat(chunks);
    }

    // Делаем запрос на Railway
    const upstream = await fetch(url, {
      method: req.method,
      headers,
      body,
      redirect: 'manual',
    });

    // Прокидываем статус и заголовки назад клиенту
    res.status(upstream.status);
    upstream.headers.forEach((value, key) => {
      if (key.toLowerCase() === 'content-encoding') return; // избегаем двойного сжатия
      res.setHeader(key, value);
    });

    // Стримим тело ответа
    if (upstream.body) {
      upstream.body.pipe(res);
    } else {
      const text = await upstream.text();
      res.send(text);
    }
  } catch (err) {
    console.error('Proxy error:', err);
    res.status(502).json({ error: 'Bad gateway', detail: String(err) });
  }
};
