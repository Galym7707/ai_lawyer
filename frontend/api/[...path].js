// frontend/api/[...path].js
export const config = {
  api: { bodyParser: false }, // нужно для проксирования FormData (upload)
};

const BACKEND_URL =
  process.env.BACKEND_URL || process.env.RAILWAY_BACKEND_URL;

function joinURL(base, suffix) {
  return `${base.replace(/\/+$/, '')}/${suffix.replace(/^\/+/, '')}`;
}

function validateBackendURL(url) {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

export default async function handler(req, res) {
  try {
    if (!BACKEND_URL) {
      res.status(500).json({ error: 'BACKEND_URL is not configured' });
      return;
    }

    if (!validateBackendURL(BACKEND_URL)) {
      console.error(`Invalid BACKEND_URL: ${BACKEND_URL}`);
      res.status(500).json({ error: 'Invalid BACKEND_URL configuration' });
      return;
    }

    // Extract path segments from the [...path] parameter
    // In Next.js, [...path].js creates a query parameter named "path"
    const { path: pathParam = [] } = req.query;
    
    // Ensure pathParam is an array and join segments properly
    let pathSegments;
    if (Array.isArray(pathParam)) {
      pathSegments = pathParam;
    } else if (typeof pathParam === 'string') {
      // Handle single string path - split by '/' in case it's a combined path
      pathSegments = pathParam.split('/').filter(segment => segment.length > 0);
    } else {
      pathSegments = [];
    }
    
    // Join path segments with forward slashes
    const subpath = pathSegments.join('/');
    
    // Extract query string from original URL, excluding the path parameter
    const urlParts = req.url.split('?');
    let queryString = '';
    if (urlParts.length > 1) {
      const params = new URLSearchParams(urlParts[1]);
      // Remove the 'path' parameter as it's used for routing
      params.delete('path');
      queryString = params.toString();
    }
    
    // Construct target URL with proper validation
    const targetUrl = joinURL(BACKEND_URL, subpath) + (queryString ? `?${queryString}` : '');
    
    // Validate the constructed target URL
    if (!validateBackendURL(targetUrl)) {
      console.error(`Constructed invalid target URL: ${targetUrl}`);
      res.status(500).json({ error: 'Invalid target URL constructed' });
      return;
    }
    
    // Log the constructed URL for debugging
    console.log(`Proxying ${req.method} request from ${req.url} to ${targetUrl}`);

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