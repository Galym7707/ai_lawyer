module.exports = async (req, res) => {
  const backendUrl = 'https://ai-lawyer.up.railway.app';
  // если вы ещё не удалили префикс /api, добавьте сюда .replace(/^\/api/, '')
  const url = new URL(req.url, backendUrl).href;

  try {
    const response = await fetch(url, {
      method: req.method,
      headers: {
        ...req.headers,
        Host: new URL(backendUrl).host,
      },
      body: req.method !== 'GET' && req.method !== 'HEAD' ? req.body : undefined,
    });

    // прочитаем тело как текст
    const data = await response.text();

    // передаём оригинальный Content-Type, чтобы safeJson понимал тип ответа
    const backendContentType = response.headers.get('content-type');
    if (backendContentType) {
      res.setHeader('Content-Type', backendContentType);
    }

    // CORS‑заголовки
    res.setHeader('Access-Control-Allow-Origin', 'https://ai-lawyer-tau.vercel.app');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

    res.status(response.status).send(data);
  } catch (e) {
    console.error('Proxy error:', e);
    res.status(500).send('Proxy error: ' + e.message);
  }
};
