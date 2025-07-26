export default async function handler(req, res) {
  const backendBase = process.env.RAILWAY_BACKEND_URL || "http://localhost:8080";

  const url = `${backendBase}${req.url.replace(/^\/api/, "")}`;
  const method = req.method;

  try {
    const backendResponse = await fetch(url, {
      method,
      headers: {
        'Content-Type': req.headers['content-type'] || 'application/json',
        'Authorization': req.headers['authorization'] || '',
      },
      body: ['POST', 'PUT', 'PATCH'].includes(method)
        ? req.body
        : undefined,
    });

    // Forward headers like Content-Type
    res.setHeader('Content-Type', backendResponse.headers.get('content-type') || 'application/json');
    res.status(backendResponse.status);

    const data = await backendResponse.text(); // Use text to avoid premature JSON parse
    res.send(data);
  } catch (error) {
    console.error("❌ Proxy error:", error);
    res.status(502).json({ error: "Bad gateway: backend not reachable." });
  }
}
