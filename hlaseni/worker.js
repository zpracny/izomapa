// Volitelný server pro hlášení nepřesností (Cloudflare Worker + databáze D1): statický web ze site/,
// POST /api/report uloží hlášení z mapy, /admin je přehled hlášení. Návod je v README (Hlášení nepřesností).
// /admin a /api/admin/* chrání heslo (HTTP Basic, secret ADMIN_PASSWORD: `npx wrangler secret put ADMIN_PASSWORD`).
// Uživatelské jméno se nekontroluje. Ukládá se jen text hlášení a hash IP adresy (kvůli limitu), ne IP samotná.
// Fotky (volitelně, "fotky": true v mesto.json + R2 bucket s bindingem PHOTOS) vidí jen administrace, veřejně se nezobrazují.
import { onRequest as flights } from '../functions/api/flights.js';
const json = (d, s = 200) => new Response(JSON.stringify(d), { status: s, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });

async function sha(s) {
  const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(b)].slice(0, 12).map((x) => x.toString(16).padStart(2, '0')).join('');
}

function isAdmin(req, env) {
  if (!env.ADMIN_PASSWORD) return false;
  const h = req.headers.get('authorization') || '';
  if (!h.startsWith('Basic ')) return false;
  let dec = ''; try { dec = atob(h.slice(6)); } catch { return false; }
  const pass = dec.slice(dec.indexOf(':') + 1);
  // porovnání v konstantním čase
  if (pass.length !== env.ADMIN_PASSWORD.length) return false;
  let d = 0; for (let i = 0; i < pass.length; i++) d |= pass.charCodeAt(i) ^ env.ADMIN_PASSWORD.charCodeAt(i);
  return d === 0;
}

async function report(req, env) {
  // text: JSON; fotka: multipart/form-data s polem 'foto' (prohlížeč ji už zmenšil a odstranil EXIF), uloží se do R2 (binding PHOTOS)
  let d, foto = null;
  const ct = req.headers.get('content-type') || '';
  if (ct.startsWith('multipart/form-data')) {
    let f; try { f = await req.formData(); } catch { return json({ ok: false, err: 'bad form' }, 400); }
    d = Object.fromEntries([...f.entries()].filter(([, v]) => typeof v === 'string'));
    foto = f.get('foto');
    if (!(foto instanceof File) || !foto.size) foto = null;
  } else {
    try { d = await req.json(); } catch { return json({ ok: false, err: 'bad json' }, 400); }
  }
  const target = String(d.target || '').slice(0, 80), note = String(d.note || '').trim().slice(0, 500), kind = foto ? 'foto' : 'text';
  if (!/^(b:[0-9a-f-]{36}|c-?\d+_-?\d+:\d+|pt:-?[\d.]+,-?[\d.]+)$/.test(target)) return json({ ok: false, err: 'bad input', msg: 'Hlášení nejde přiřadit k místu na mapě.' }, 400);
  if (!foto && note.length < 3) return json({ ok: false, err: 'short', msg: 'Napište prosím, co tu nesedí (aspoň pár slov).' }, 400);
  if (foto) {
    if (!env.PHOTOS) return json({ ok: false, err: 'no photos', msg: 'Posílání fotek tu není zapnuté.' }, 400);
    if (d.souhlas !== '1') return json({ ok: false, err: 'consent', msg: 'Pro odeslání fotky je potřeba souhlas s podmínkami.' }, 400);
    if (foto.size > 3 * 1024 * 1024) return json({ ok: false, err: 'big', msg: 'Fotka je moc velká (nejvýš 3 MB).' }, 413);
    const head = new Uint8Array(await foto.slice(0, 3).arrayBuffer());
    if (!(head[0] === 0xff && head[1] === 0xd8 && head[2] === 0xff)) return json({ ok: false, err: 'type', msg: 'Fotka musí být JPEG.' }, 415);
  }
  if (env.TURNSTILE_SECRET) {
    const f = new FormData(); f.append('secret', env.TURNSTILE_SECRET); f.append('response', String(d.token || '')); f.append('remoteip', req.headers.get('cf-connecting-ip') || '');
    const r = await (await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', { method: 'POST', body: f })).json();
    if (!r.success) return json({ ok: false, err: 'captcha' }, 403);
  }
  const day = new Date().toISOString().slice(0, 10), ip = req.headers.get('cf-connecting-ip') || 'local';
  const key = foto ? `foto/${day}/${crypto.randomUUID()}.jpg` : null;
  // text: jedno hlášení objektu za den; fotek k jednomu objektu může být víc (každá má vlastní otisk)
  const who = await sha(ip + '|' + day + '|' + (env.SALT || 'izo') + (key ? '|' + key : ''));
  const dev = await sha(ip + '|dev|' + (env.SALT || 'izo'));
  // limit: 10 textových hlášení a 10 fotek za hodinu z jednoho zařízení (IP)
  const lim = 10;
  const recent = await env.DB.prepare("SELECT COUNT(*) n FROM reports WHERE dev = ? AND kind = ? AND created > datetime('now', '-1 hour')").bind(dev, kind).first();
  if (recent && recent.n >= lim) return json({ ok: false, err: 'limit', msg: foto ? 'Z tohoto zařízení přišlo za poslední hodinu už 10 fotek. Zkuste to prosím později.' : 'Z tohoto zařízení přišlo za poslední hodinu už 10 hlášení. Zkuste to prosím později.' }, 429);
  if (foto) await env.PHOTOS.put(key, foto.stream(), { httpMetadata: { contentType: 'image/jpeg' } });
  try {
    await env.DB.prepare('INSERT INTO reports (target, title, kind, note, lon, lat, who, dev, photo, author, license) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)')
      .bind(target, String(d.title || '').slice(0, 120), kind, note, +d.lon || null, +d.lat || null, who, dev, key,
        foto ? String(d.author || '').trim().slice(0, 80) || null : null, foto ? 'CC BY 4.0' : null).run();
  } catch (e) {
    if (key) await env.PHOTOS.delete(key);
    if (String(e).includes('UNIQUE')) return json({ ok: false, err: 'dup', msg: 'Tohle místo jste dnes už nahlásili, děkuji.' }, 409);
    throw e;
  }
  return json({ ok: true });
}

async function adminPhoto(req, env) {
  const k = new URL(req.url).searchParams.get('k') || '';
  if (!env.PHOTOS || !/^foto\/[\d-]+\/[0-9a-f-]{36}\.jpg$/.test(k)) return new Response('nenalezeno', { status: 404 });
  const o = await env.PHOTOS.get(k);
  if (!o) return new Response('nenalezeno', { status: 404 });
  return new Response(o.body, { headers: { 'content-type': 'image/jpeg', 'cache-control': 'private, max-age=86400' } });
}

async function adminList(req, env) {
  const u = new URL(req.url), min = Math.max(1, +u.searchParams.get('min') || 1), st = u.searchParams.get('status') || 'nove';
  const groups = await env.DB.prepare(
    `SELECT target, MAX(title) title, COUNT(*) n, MAX(created) last, AVG(lon) lon, AVG(lat) lat, (SELECT note FROM reports r2 WHERE r2.target = reports.target ORDER BY created DESC LIMIT 1) note
     , SUM(kind = 'foto') fotek FROM reports WHERE status = ? GROUP BY target HAVING n >= ? ORDER BY n DESC, last DESC LIMIT 500`).bind(st, min).all();
  return json({ groups: groups.results });
}

async function adminDetail(req, env) {
  const t = new URL(req.url).searchParams.get('target') || '';
  const r = await env.DB.prepare('SELECT id, created, kind, note, status, photo, author, license FROM reports WHERE target = ? ORDER BY created DESC').bind(t).all();
  return json({ items: r.results });
}

async function adminSet(req, env) {
  const d = await req.json();
  if (!['nove', 'vyreseno', 'zamitnuto'].includes(d.status)) return json({ ok: false }, 400);
  await env.DB.prepare('UPDATE reports SET status = ? WHERE target = ?').bind(d.status, String(d.target || '')).run();
  return json({ ok: true });
}

// stav mapy nastavovaný v administraci: vánoční výzdoba (auto / on / off) a zamrzlé rybníky (seznam názvů z mesto.json "rybniky").
// Tabulka se založí sama při prvním použití (není potřeba migrace).
const STAV0 = { vanoce: 'auto', zamrzle: [] };
async function stavGet(env) {
  await env.DB.prepare('CREATE TABLE IF NOT EXISTS nastaveni (k TEXT PRIMARY KEY, v TEXT NOT NULL)').run();
  const r = await env.DB.prepare("SELECT v FROM nastaveni WHERE k = 'stav'").first();
  let v = {}; try { v = r ? JSON.parse(r.v) : {}; } catch {}
  return { ...STAV0, ...v };
}
async function stav(env) {
  const v = await stavGet(env);
  return new Response(JSON.stringify(v), { headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'public, max-age=60' } });
}
async function adminStav(req, env) {
  let d; try { d = await req.json(); } catch { return json({ ok: false }, 400); }
  const v = { vanoce: ['auto', 'on', 'off'].includes(d.vanoce) ? d.vanoce : 'auto',
    zamrzle: (Array.isArray(d.zamrzle) ? d.zamrzle : []).map((x) => String(x).slice(0, 60)).slice(0, 20) };
  await stavGet(env);
  await env.DB.prepare("INSERT INTO nastaveni (k, v) VALUES ('stav', ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v").bind(JSON.stringify(v)).run();
  return json({ ok: true, ...v });
}

// zpoždění MHD v reálném čase (volitelné, "polohy": true v mesto.json + secret GOLEMIO_TOKEN z api.golemio.cz):
// GET /api/polohy?bbox=sever,západ,jih,východ -> {"t": čas, "v": [[gtfs_trip_id, zpoždění s, stav], …]}
// Golemio se ptá jednou za 20 s pro všechny návštěvníky (cache), klíč zůstává na serveru.
async function polohy(req, env, ctx) {
  if (!env.GOLEMIO_TOKEN) return json({ v: [], err: 'off' }, 404);
  const bb = (new URL(req.url).searchParams.get('bbox') || '').split(',').map(Number);
  if (bb.length !== 4 || bb.some((v) => !Number.isFinite(v)) || bb[0] <= bb[2] || bb[3] <= bb[1] || bb[0] - bb[2] > 1 || bb[3] - bb[1] > 1.5)
    return json({ v: [], err: 'bbox' }, 400);
  const q = bb.map((v) => v.toFixed(3)).join(',');
  const key = new Request('https://polohy.cache/?' + q), cache = caches.default;
  const hit = await cache.match(key);
  if (hit) return hit;
  let v = [], err = null;
  try {
    const r = await fetch(`https://api.golemio.cz/v2/public/vehiclepositions?boundingBox=${q}`, { headers: { 'X-Access-Token': env.GOLEMIO_TOKEN } });
    if (r.ok) v = ((await r.json()).features || []).map((f) => f.properties || {}).filter((p) => p.gtfs_trip_id).map((p) => [p.gtfs_trip_id, p.delay ?? null, p.state_position || '']);
    else err = r.status;
  } catch (e) { err = 'fetch'; }
  const res = new Response(JSON.stringify({ t: Date.now(), v, ...(err ? { err } : {}) }),
    { headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': `public, max-age=${err ? 60 : 20}` } });
  ctx.waitUntil(cache.put(key, res.clone()));
  return res;
}

export default {
  async fetch(req, env, ctx) {
    const p = new URL(req.url).pathname;
    if (p === '/api/flights') return flights({ request: req });
    if (p === '/api/report' && req.method === 'POST') return report(req, env);
    if (p === '/api/stav' && req.method === 'GET') return stav(env);
    if (p === '/api/polohy' && req.method === 'GET') return polohy(req, env, ctx);
    if (p.startsWith('/api/admin/') || p === '/admin' || p === '/admin.html') {
      if (!isAdmin(req, env)) return new Response('Přihlášení do administrace', { status: 401, headers: { 'www-authenticate': 'Basic realm="izomapa admin", charset="UTF-8"' } });
      if (p === '/api/admin/list') return adminList(req, env);
      if (p === '/api/admin/detail') return adminDetail(req, env);
      if (p === '/api/admin/foto') return adminPhoto(req, env);
      if (p === '/api/admin/status' && req.method === 'POST') return adminSet(req, env);
      if (p === '/api/admin/stav' && req.method === 'POST') return adminStav(req, env);
      if (p === '/admin' || p === '/admin.html') return env.ASSETS.fetch(req);   // assets podávají admin.html na /admin
    }
    return env.ASSETS.fetch(req);
  },
};
