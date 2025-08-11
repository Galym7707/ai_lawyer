// frontend/api/proxy/[...path].js

// Динамически подключаем node-fetch при необходимости (если fetch не глобальный)
const getFetch = async () => {
  if (typeof fetch === 'function') return fetch;
  const { default: nodeFetch } = await import('node-fetch');
  return nodeFetch;
};

export default async function handler(req, res) {
  // Используем переменную окружения или Railway‑домен по умолчанию
  const backendBase =
    process.env.RAILWAY_BACKEND_URL || 'https://ai-lawyer.up.railway.app';

  // Получаем путь из query параметров
  const { path = [] } = req.query;
  const targetPath = '/' + path.join('/');
  
  // Добавляем query параметры если они есть
  const queryString = req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : '';
  const backendUrl = new URL(targetPath + queryString, backendBase).toString();

  const method = req.method.toUpperCase();

  try {
    const fetchFunc = await getFetch();

    // Готовим тело запроса: для application/json сериализуем объект в строку,
    // а для других типов (например, multipart/form-data) отправляем как есть
    let requestBody = undefined;
    if (!['GET', 'HEAD'].includes(method)) {
      const contentType = req.headers['content-type'] || '';
      if (
        contentType.includes('application/json') &&
        typeof req.body === 'object' &&
        req.body !== null
      ) {
        requestBody = JSON.stringify(req.body);
      } else {
        requestBody = req.body;
      }
    }

    const backendResponse = await fetchFunc(backendUrl, {
      method,
      headers: {
        // Прокидываем тип контента и авторизацию, если есть
        'Content-Type': req.headers['content-type'] || 'application/json',
        Authorization: req.headers['authorization'] || '',
      },
      body: requestBody,
    });

    // Прокидываем статус и заголовок Content‑Type от бэкенда
    res.setHeader(
      'Content-Type',
      backendResponse.headers.get('content-type') || 'application/json'
    );
    res.status(backendResponse.status);

    // Читаем тело ответа как текст (подходит и для JSON, и для HTML)
    const data = await backendResponse.text();
    res.send(data);
  } catch (error) {
    console.error('❌ Proxy error:', error);
    // Любая ошибка проксирования — это 502 Bad Gateway
    res.status(502).json({
      error: 'Bad gateway: backend not reachable.',
    });
  }
}
