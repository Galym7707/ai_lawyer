// frontend/api/[...path].js
export const config = {
  api: { bodyParser: false }, // нужно для проксирования FormData (upload)
};

const BACKEND_URL =
  process.env.BACKEND_URL || process.env.RAILWAY_BACKEND_URL;

function joinURL(base, suffix) {
  return `${base.replace(/\/+$/, '')}/${suffix.replace(/^\/+/, '')}`;
}

export default async function handler(req, res) {
  try {
    if (!BACKEND_URL) {
      res.status(500).json({ error: 'BACKEND_URL is not configured' });
      return;
    }

    // вычислим путь за /api/
    const { slug = [] } = req.query; // [...path] -> массив
    const subpath = Array.isArray(slug) ? slug.join('/') : String(slug || '');

    const targetUrl = joinURL(BACKEND_URL, subpath) +
      (req.url.includes('?') ? '?' + req.url.split('?')[1] : '');

    // соберём заголовки (уберём host и ненужные vercel-заголовки)
    const headers = new Headers();
    for (const [k, v] of Object.entries(req.headers)) {
      if (!v) continue;
      if (['host', 'content-length'].includes(k.toLowerCase())) continue;
      headers.set(k, Array.isArray(v) ? v.join(',') : v);
    }

    const init = {
      method: req.method,
      headers,
      // передаём сырое тело как ReadableStream
      body: req.method === 'GET' || req.method === 'HEAD' ? undefined : req,
      redirect: 'manual',
    };

    const response = await fetch(targetUrl, init);

    // прокинем статус/заголовки/тело назад клиенту
    res.status(response.status);
    response.headers.forEach((value, key) => {
      // не даём переопределять transfer-encoding и т.п.
      if (['content-encoding', 'transfer-encoding'].includes(key)) return;
      res.setHeader(key, value);
    });

    // потоково отдадим тело
    const reader = response.body?.getReader?.();
    if (!reader) {
      const buf = Buffer.from(await response.arrayBuffer());
      res.send(buf);
      return;
    }
    // stream pipe
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      res.write(Buffer.from(value));
    }
    res.end();
  } catch (err) {
    console.error('Proxy error:', err);
    res.status(502).json({ error: 'Bad gateway', detail: String(err) });
  }
}
