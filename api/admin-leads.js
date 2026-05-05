// api/admin-leads.js
// Bezpečný přístup k leads přes service role key (uložen v env proměnné)

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', 'https://www.svjenergie.cz');
  res.setHeader('Access-Control-Allow-Methods', 'GET, PATCH, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') return res.status(200).end();

  // Ověř že volající je přihlášený uživatel (anon token)
  const authHeader = req.headers.authorization;
  if (!authHeader) return res.status(401).json({ error: 'Chybí autorizace' });

  const SUPA_URL = 'https://aeypeepckmbejdcotdss.supabase.co';
  const SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;
  const ANON_KEY = process.env.SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFleXBlZXBja21iZWpkY290ZHNzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzczOTkyNjAsImV4cCI6MjA5Mjk3NTI2MH0.JjYiI3bcL1ds1vAkFq59Z0WhNCLAd8oekX6GF4Zq5bA';

  // Ověř uživatele přes jeho token
  const userToken = authHeader.replace('Bearer ', '');
  const userRes = await fetch(SUPA_URL + '/auth/v1/user', {
    headers: { 'apikey': ANON_KEY, 'Authorization': 'Bearer ' + userToken }
  });
  if (!userRes.ok) return res.status(401).json({ error: 'Neplatný token' });
  const user = await userRes.json();

  // Povol jen admin email
  const ADMIN_EMAIL = process.env.ADMIN_EMAIL || '';
  if (ADMIN_EMAIL && user.email?.toLowerCase() !== ADMIN_EMAIL.toLowerCase()) {
    return res.status(403).json({ error: 'Nemáte oprávnění' });
  }

  // GET — načíst leady
  if (req.method === 'GET') {
    const r = await fetch(SUPA_URL + '/rest/v1/leads?order=created_at.desc&limit=500', {
      headers: {
        'apikey': SERVICE_KEY,
        'Authorization': 'Bearer ' + SERVICE_KEY,
        'Content-Type': 'application/json'
      }
    });
    const data = await r.json();
    const leads = Array.isArray(data) ? data : [];
    res.setHeader('Cache-Control', 'no-store');
    return res.status(200).json(leads);
  }

  // PATCH — změnit stav leadu
  if (req.method === 'PATCH') {
    const { id, stav } = req.body;
    if (!id || !stav) return res.status(400).json({ error: 'Chybí id nebo stav' });
    const r = await fetch(SUPA_URL + '/rest/v1/leads?id=eq.' + id, {
      method: 'PATCH',
      headers: {
        'apikey': SERVICE_KEY,
        'Authorization': 'Bearer ' + SERVICE_KEY,
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
      },
      body: JSON.stringify({ stav })
    });
    return res.status(r.ok ? 200 : 500).json({ ok: r.ok });
  }

  return res.status(405).json({ error: 'Method not allowed' });
}
