// frontend/api/proxy.js

// Если Node < 18, загружаем node-fetch динамически
const getFetch = async () => {
  if (typeof fetch === 'function') return fetch;
  const { default: nodeFetch } = await import('node-fetch');
  return nodeFetch;
};

export default async function handler(req, res) {
  // Адрес бэкенда: используем переменную окружения или Railway‑URL по умолчанию
  const backendBase =
    process.env.RAILWAY_BACKEND_URL || 'https://ai-lawyer.up.railway.app';

  // Убираем префикс /api, чтобы получить исходный путь запроса
  // и аккуратно собираем полный URL (с учётом query‑параметров)
  const backendUrl = new URL(
    req.url.replace(/^\/api/, ''),
    backendBase
  ).toString();

  const method = req.method;

  try {
    const fetchFunc = await getFetch();

    const backendResponse = await fetchFunc(backendUrl, {
      method,
      headers: {
        // Пробрасываем только необходимые заголовки
        'Content-Type': req.headers['content-type'] || 'application/json',
        Authorization: req.headers['authorization'] || '',
      },
      body: ['POST', 'PUT', 'PATCH'].includes(method)
        ? req.body
        : undefined,
    });

    // Прокидываем тип контента и статус код от бэкенда
    res.setHeader(
      'Content-Type',
      backendResponse.headers.get('content-type') || 'application/json'
    );
    res.status(backendResponse.status);

    // Получаем ответ как текст — безопасно для любых типов
    const data = await backendResponse.text();
    res.send(data);
  } catch (error) {
    console.error('❌ Proxy error:', error);
    // Любая ошибка прокси приводит к 502
    res
      .status(502)
      .json({ error: 'Bad gateway: backend not reachable.' });
  }
}
