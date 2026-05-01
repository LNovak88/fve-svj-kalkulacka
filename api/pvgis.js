// api/pvgis.js
// PVGIS proxy pro Vercel — obchází CORS při volání z prohlížeče
// Umístění: /api/pvgis.js v kořeni repozitáře
// Vercel automaticky zpřístupní na /api/pvgis

export default async function handler(req, res) {
  // CORS hlavičky
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const { lat, lon, peakpower, angle, aspect } = req.query;

  if (!lat || !lon || !peakpower || !angle || aspect === undefined) {
    return res.status(400).json({ error: 'Chybí parametry: lat, lon, peakpower, angle, aspect' });
  }

  const params = new URLSearchParams({
    lat, lon, peakpower,
    loss: 14,
    angle, aspect,
    outputformat: 'json',
    browser: 0,
    pvcalculation: 1,
    pvtechchoice: 'crystSi',
    mountingplace: 'building',
    trackingtype: 0,
    usehorizon: 1,
    tmy: 1
  });

  const url = `https://re.jrc.ec.europa.eu/api/v5_2/seriescalc?${params.toString()}`;

  try {
    const response = await fetch(url, {
      signal: AbortSignal.timeout(25000),
      headers: { 'User-Agent': 'SVJEnergie/1.0' }
    });

    if (!response.ok) {
      return res.status(response.status).json({ error: `PVGIS HTTP ${response.status}` });
    }

    const data = await response.json();
    // Cache 24 hodin na Vercel Edge
    res.setHeader('Cache-Control', 's-maxage=86400, stale-while-revalidate');
    return res.status(200).json(data);

  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
}
