// netlify/functions/pvgis.js
// PVGIS proxy — obchází CORS omezení při volání z prohlížeče
// Nasazení: tento soubor vložit do /netlify/functions/ v GitHub repozitáři
// Netlify Functions jsou zdarma (125 000 volání/měsíc)

exports.handler = async function(event) {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json'
  };

  // Preflight CORS
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers, body: '' };
  }

  const params = event.queryStringParameters || {};
  const required = ['lat','lon','peakpower','angle','aspect'];
  for (const p of required) {
    if (!params[p]) {
      return { statusCode: 400, headers, body: JSON.stringify({ error: `Chybí parametr: ${p}` }) };
    }
  }

  const pvgisParams = new URLSearchParams({
    lat: params.lat,
    lon: params.lon,
    peakpower: params.peakpower,
    loss: params.loss || 14,
    angle: params.angle,
    aspect: params.aspect,
    outputformat: 'json',
    browser: 0,
    pvcalculation: 1,
    pvtechchoice: 'crystSi',
    mountingplace: 'building',
    trackingtype: 0,
    usehorizon: 1,
    tmy: 1
  });

  try {
    const fetch = (await import('node-fetch')).default;
    const url = `https://re.jrc.ec.europa.eu/api/v5_2/seriescalc?${pvgisParams.toString()}`;
    const response = await fetch(url, { timeout: 25000 });

    if (!response.ok) {
      return {
        statusCode: response.status,
        headers,
        body: JSON.stringify({ error: `PVGIS HTTP ${response.status}` })
      };
    }

    const data = await response.json();
    return { statusCode: 200, headers, body: JSON.stringify(data) };

  } catch (err) {
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ error: err.message })
    };
  }
};
