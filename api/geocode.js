// /api/geocode.js — Vercel serverless proxy pro Nominatim geocoding
// Obchází Render (který se uspává) a řeší CORS pro svjenergie.cz

export default async function handler(req, res) {
  // CORS hlavičky — vždy
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const q = req.query.q;
  if (!q || q.length < 2) {
    return res.status(200).json([]);
  }

  try {
    const url = new URL('https://nominatim.openstreetmap.org/search');
    url.searchParams.set('q', `${q}, Česká republika`);
    url.searchParams.set('format', 'json');
    url.searchParams.set('limit', '5');
    url.searchParams.set('addressdetails', '1');
    url.searchParams.set('countrycodes', 'cz');

    const response = await fetch(url.toString(), {
      headers: {
        'User-Agent': 'FVE-SVJ-Kalkulacka/2.2 (svjenergie.cz; lnovak88@seznam.cz)',
        'Accept': 'application/json',
        'Accept-Language': 'cs,en',
      },
      signal: AbortSignal.timeout(8000),
    });

    if (!response.ok) {
      return res.status(200).json([]);
    }

    const data = await response.json();
    return res.status(200).json(Array.isArray(data) ? data : []);
  } catch (err) {
    // Nikdy nevracet 500 — CORS by pak chyběl
    console.error('Geocode error:', err.message);
    return res.status(200).json([]);
  }
}
