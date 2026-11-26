  // ---------- služby z otevřených registrů (nastroje/sluzby.py, overlay.py) ----------
  // v kartě budovy „V budově“ po skupinách (lékaři, školy, pošta…), Balíkovna boxy, nabíječky a služby mimo budovy jako značky na mapě
  const SL_PORADI = ['Nemocnice', 'Poliklinika', 'Praktický lékař', 'Dětský lékař', 'Zubař', 'Dentální hygiena', 'Gynekologie', 'Lékař specialista',
    'Fyzioterapie', 'Logopedie', 'Odběrové místo', 'Lékárna', 'Zdravotnické potřeby', 'Oční optika', 'Zdravotní služby', 'Záchranná služba',
    'Mateřská škola', 'Základní škola', 'Základní umělecká škola', 'Střední škola', 'Vyšší odborná škola', 'Dům dětí a mládeže', 'Domov mládeže',
    'Pošta', 'Balíkovna', 'Balíkovna box', 'Dobíjecí stanice'];
  const SL_MN = { 'Praktický lékař': 'Praktičtí lékaři', 'Dětský lékař': 'Dětští lékaři', 'Zubař': 'Zubaři', 'Lékař specialista': 'Lékaři specialisté',
    'Lékárna': 'Lékárny', 'Oční optika': 'Oční optiky', 'Odběrové místo': 'Odběrová místa', 'Mateřská škola': 'Mateřské školy', 'Základní škola': 'Základní školy',
    'Střední škola': 'Střední školy', 'Pošta': 'Pošty', 'Balíkovna': 'Balíkovny', 'Balíkovna box': 'Balíkovna boxy', 'Dobíjecí stanice': 'Dobíjecí stanice' };
  const slPor = (k) => { const i = SL_PORADI.indexOf(k); return i < 0 ? 99 : i; };
  const SL_TITUL = /škola|Nemocnice|Poliklinika|Pošta|Dům dětí|Domov mládeže/;
  function renderSluzby(sl) {
    const box = $('cardSl'); box.replaceChildren(); box.hidden = !(sl && sl.length);
    if (box.hidden) return;
    const g = new Map();
    for (const s of sl) { if (!g.has(s[0])) g.set(s[0], []); g.get(s[0]).push(s); }
    const h = document.createElement('h3'); h.textContent = 'V budově'; box.append(h);
    for (const k of [...g.keys()].sort((a, b) => slPor(a) - slPor(b))) {
      const it = g.get(k), det = document.createElement('details'), sum = document.createElement('summary');
      det.open = sl.length <= 6;
      sum.textContent = it.length > 1 ? `${SL_MN[k] || k} (${it.length})` : k;
      const ul = document.createElement('ul');
      for (const [, n, d] of it.sort((a, b) => a[1].localeCompare(b[1], 'cs'))) {
        const li = document.createElement('li'); li.textContent = n;
        if (d) { const sm = document.createElement('small'); sm.textContent = ' · ' + d; li.append(sm); }
        ul.append(li);
      }
      det.append(sum, ul); box.append(det);
    }
  }
  // značky mimo budovy: [lat, lon, kategorie, název, podrobnost] -> poloha v obrázku (jako rozcestníky), jen ve čtvercích mapy
  const SLZ = (OV.sluzby || []).map(([lat, lon, kat, n, dt]) => {
    const x = (lon - cam.lon0) * cam.kx, y = (lat - cam.lat0) * cam.ky, g = gz(x, y), [ix, iy] = toImg(x, y, g);
    return { lat, lon, kat, n, dt, ix, iy, x, y, d: depth(x, y, g), h: (iy - toImg(x, y, g + 2.2)[1]) };
  }).filter((r) => cam.grounds.some((q) => Math.abs(r.x - q.cx) <= cam.half && Math.abs(r.y - q.cy) <= cam.half));
  const SL_ZN = { 'Dobíjecí stanice': ['#2f9e5b', '⚡'], 'Balíkovna box': ['#f2b705', 'B'], 'Balíkovna': ['#f2b705', 'B'], 'Pošta': ['#f2b705', 'P'] };
  const slAt = (ix, iy) => {                                // značka pod kurzorem (do ~16 px na obrazovce)
    const scr = viewer.viewport.getContainerSize().x / (viewer.viewport.getBounds(true).width * W);
    if (scr < 0.35) return null;
    let best = null, bd = Math.max(16 / scr, 14);
    for (const r of SLZ) { const d = Math.hypot(r.ix - ix, (r.iy - r.h) - iy); if (d < bd) { bd = d; best = r; } }
    return best;
  };
  const showSl = (r) => showCard({ title: r.n, text: r.dt || null, lon: r.lon, lat: r.lat, rows: [['Typ', r.kat]] });
  function drawSluzby(sx, ox, oy, vis) {                         // sloupek s barevnou cedulkou a znakem; po najetí myší název
    if (sx <= 0.35) return;
    for (const r of SLZ) {
      if (!vis(r.ix, r.iy, 40) || occluded(r.ix, r.iy, r.d)) continue;
      const [col, zn] = SL_ZN[r.kat] || ['#3f6fb5', '•'];
      const X = Math.round(ox + r.ix * sx), Y = Math.round(oy + r.iy * sx), u = Math.max(2, Math.round(sx * 2.2)), H = Math.round(r.h * sx), s = u * 4;
      ctx.fillStyle = '#5d6168'; ctx.fillRect(X - Math.ceil(u / 3), Y - H, Math.max(1, Math.ceil(u * 0.6)), H);
      ctx.fillStyle = '#1b2333'; ctx.fillRect(X - s / 2 - 1, Y - H - s - 1, s + 2, s + 2);
      ctx.fillStyle = col; ctx.fillRect(X - s / 2, Y - H - s, s, s);
      ctx.fillStyle = '#fff'; ctx.font = `bold ${Math.round(s * 0.8)}px system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(zn, X, Y - H - s / 2 + 1); ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
      if (state.hoverSl === r) {
        ctx.font = `bold ${Math.max(11, Math.round(12 * Math.min(1.4, sx)))}px system-ui, sans-serif`;
        const lab = `${r.kat}: ${r.n}`, tw = ctx.measureText(lab).width, bx = X - tw / 2 - 5, by = Y - H - s - 24;
        ctx.fillStyle = 'rgba(27,35,51,.92)'; ctx.fillRect(bx, by, tw + 10, 18); ctx.fillStyle = col; ctx.fillRect(bx, by + 17, tw + 10, 2);
        ctx.fillStyle = '#e9e6dc'; ctx.textBaseline = 'middle'; ctx.fillText(lab, bx + 5, by + 9); ctx.textBaseline = 'alphabetic';
      }
    }
  }
