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

  // GET — načíst leady nebo simulace uživatele
  if (req.method === 'GET') {
    // Všechny simulace všech uživatelů (pro admin-vypocty.html)
    if (req.query.action === 'all_sims') {
      // Načíst všechny simulace
      const sRes = await fetch(
        SUPA_URL + '/rest/v1/simulations?order=created_at.desc&limit=500&select=*',
        { headers: { 'apikey': SERVICE_KEY, 'Authorization': 'Bearer ' + SERVICE_KEY, 'Accept': 'application/json' } }
      );
      const sims = await sRes.json();
      if (!Array.isArray(sims) || !sims.length) return res.status(200).json({ users: [] });

      // Načíst leady pro info o uživatelích (jméno, email, SVJ, pozice)
      const lRes = await fetch(
        SUPA_URL + '/rest/v1/leads?select=email,svj,pozice,jmeno,params&order=created_at.desc&limit=500',
        { headers: { 'apikey': SERVICE_KEY, 'Authorization': 'Bearer ' + SERVICE_KEY, 'Accept': 'application/json' } }
      );
      const leads = await lRes.json();
      const leadByEmail = {};
      if (Array.isArray(leads)) leads.forEach(l => { if(l.email && !leadByEmail[l.email]) leadByEmail[l.email] = l; });

      // Seskupit simulace dle user_id
      const userMap = {};
      sims.forEach(s => {
        if (!s.user_id) return;
        if (!userMap[s.user_id]) userMap[s.user_id] = { sims: [], email: null, name: null };
        userMap[s.user_id].sims.push(s);
        // Zkusit vytáhnout email z params simulace
        if (!userMap[s.user_id].email) {
          try {
            const p = JSON.parse(s.params || '{}');
            // email není v params, ale lokace ano
          } catch(e) {}
        }
      });

      // Načíst emailu uživatelů přes auth admin - zkusit, ale nespoléhat
      let authUsers = [];
      try {
        const uRes = await fetch(
          SUPA_URL + '/auth/v1/admin/users?per_page=500',
          { headers: { 'apikey': SERVICE_KEY, 'Authorization': 'Bearer ' + SERVICE_KEY } }
        );
        if (uRes.ok) {
          const uData = await uRes.json();
          authUsers = uData.users || [];
        }
      } catch(e) { /* admin API nedostupné - pokračujeme bez emailů */ }

      // Sestavit výsledek
      const users = Object.entries(userMap).map(([uid, data]) => {
        const authUser = authUsers.find(u => u.id === uid) || {};
        const email = authUser.email || '';
        const meta = authUser.user_metadata || {};
        const lead = leadByEmail[email] || {};
        // Zkusit jméno z params nejnovější simulace
        let nameFromSim = '';
        try {
          const p = JSON.parse(data.sims[0]?.params || '{}');
          nameFromSim = p.lokace ? p.lokace.split(',')[0] : '';
        } catch(e) {}

        return {
          user: {
            id: uid,
            email: email || '—',
            full_name: meta.full_name || lead.jmeno || email.split('@')[0] || ('Uživatel '+uid.slice(0,6)),
            svj: meta.svj || lead.svj || '',
            pozice: meta.pozice || lead.pozice || '',
          },
          simulations: data.sims.sort((a,b) => new Date(b.created_at) - new Date(a.created_at)).slice(0,10),
        };
      }).sort((a,b) => new Date(b.simulations[0]?.created_at) - new Date(a.simulations[0]?.created_at));

      return res.status(200).json({ users });
    }
    if (req.query.action === 'user_sims' && req.query.email) {
      // Najít user_id dle emailu
      const uRes = await fetch(
        SUPA_URL + '/auth/v1/admin/users?email=' + encodeURIComponent(req.query.email),
        { headers: { 'apikey': SERVICE_KEY, 'Authorization': 'Bearer ' + SERVICE_KEY } }
      );
      const uData = await uRes.json();
      const users = uData.users || [];
      if (!users.length) return res.status(200).json({ simulations: [] });
      const userId = users[0].id;
      // Načíst simulace
      const sRes = await fetch(
        SUPA_URL + '/rest/v1/simulations?user_id=eq.' + userId + '&order=created_at.desc&limit=10',
        {
          headers: {
            'apikey': SERVICE_KEY,
            'Authorization': 'Bearer ' + SERVICE_KEY,
            'Accept': 'application/json',
          }
        }
      );
      const sims = await sRes.json();
      return res.status(200).json({ simulations: Array.isArray(sims) ? sims : [] });
    }
    // Standardní načtení leadů
    const r = await fetch(SUPA_URL + '/rest/v1/leads?order=created_at.desc&limit=500', {
      headers: {
        'apikey': SERVICE_KEY,
        'Authorization': 'Bearer ' + SERVICE_KEY,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Prefer': 'return=representation'
      }
    });
    const text = await r.text();
    console.log('Supabase response status:', r.status);
    console.log('Supabase response:', text.substring(0, 200));
    let data;
    try { data = JSON.parse(text); } catch(e) { data = []; }
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
