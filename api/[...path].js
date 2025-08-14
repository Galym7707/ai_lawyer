// api/[...path].js
'use strict';

/**
 * Универсальный прокси к Railway-бэкенду.
 * Работает для любых /api/* путей, поддерживает:
 * - CORS (включая OPTIONS preflight)
 * - Прозрачный стриминг ответа (чтобы поток из Flask доходил до браузера)
 * - Проброс всех методов/заголовков/куки/квери
 *
 * ОБЯЗАТЕЛЬНО: в настройках проекта Vercel добавь переменную
 * BACKEND_URL=https://ai-lawyer.up.railway.app
 * (или свою фактическую ссылку Railway).
 */

const { URL } = require('url');

function setCors(res, origin) {
  res.setHeader('Access-Control-Allow-Origin', origin || '*');
  res.setHeader('Vary', 'Origin');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,DELETE,PUT,PATCH,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With');
  res.setHeader('Access-Control-Allow-Credentials', 'true');
}

module.exports = async (req, res) => {
  const ORIGIN = req.headers.origin || '*';
  setCors(res, ORIGIN);

  // Preflight
  if (req.method === 'OPTIONS') {
    res.statusCode = 204;
    return res.end();
  }

  const BASE = process.env.BACKEND_URL || process.env.RAILWAY_BACKEND_URL;
  if (!BASE) {
    res.statusCode = 500;
    return res.json({
      error: 'BACKEND_URL is not set on Vercel project',
      hint: 'Set BACKEND_URL in Vercel → Project → Settings → Environment Variables'
    });
  }

  // [...path] приходит в req.query.path как массив/строка
  const pathParam = req.query.path;
  const pathParts = Array.isArray(pathParam)
    ? pathParam
    : (pathParam ? [pathParam] : []);
  const tail = pathParts.join('/');

  // Собираем полный URL на бэкенд
  const target = new URL(BASE.endsWith('/') ? BASE : BASE + '/');
  target.pathname = (target.pathname.endsWith('/') ? target.pathname : target.pathname + '/') + tail;

  // Проброс доп. query (кроме самого параметра "path")
  const incoming = new URL(req.url, 'http://localhost');
  incoming.searchParams.forEach((v, k) => {
    if (k !== 'path') target.searchParams.set(k, v);
  });

  // Готовим заголовки (без Host)
  const headers = new Headers();
  for (const [k, v] of Object.entries(req.headers)) {
    if (k.toLowerCase() === 'host') continue;
    headers.set(k, v);
  }

  // Тело передаем только для не-GET/HEAD
  const method = req.method || 'GET';
  const body = (method === 'GET' || method === 'HEAD') ? undefined : req;

  try {
    const upstream = await fetch(target.toString(), {
      method,
      headers,
      body,
      // важен режим по умолчанию — node18 на Vercel уже с fetch
    });

    // Пробрасываем статус и заголовки от бэка
    res.statusCode = upstream.status;
    upstream.headers.forEach((val, key) => {
      // Перекрываем CORS на наши
      if (/^access-control-allow-/i.test(key)) return;
      res.setHeader(key, val);
    });
    setCors(res, ORIGIN);

    // Стримим тело как есть
    if (upstream.body) {
      upstream.body.pipe(res);
    } else {
      const text = await upstream.text();
      res.end(text);
    }
  } catch (e) {
    res.statusCode = 502;
    res.json({
      error: 'Proxy fetch failed',
      details: e?.message || String(e),
      target: target.toString()
    });
  }
};
