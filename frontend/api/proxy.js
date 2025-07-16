module.exports = async (req, res) => {
  const backendUrl = 'https://ai-lawyer.up.railway.app';
  const url = new URL(req.url, backendUrl).href;

  try {
    const response = await fetch(url, {
      method: req.method,
      headers: {
        ...req.headers,
        'Host': new URL(backendUrl).host,
      },
      body: req.method !== 'GET' && req.method !== 'HEAD' ? req.body : undefined,
    });

    const data = await response.text();
    res.setHeader('Access-Control-Allow-Origin', 'https://ai-lawyer-tau.vercel.app');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
    res.status(response.status).send(data);
  } catch (e) {
    console.error('Proxy error:', e);
    res.status(500).send('Proxy error: ' + e.message);
  }
};
