  // světla vozidel v noci: sesbírat za celý snímek a nakreslit třemi cestami (kužely, přední, zadní) místo stovek fill()
  const LIGHTS_SX = 0.35, NL = { beams: [], head: [], tail: [] };
  function flushLights(night, sx) {
    if (NL.beams.length) {
      const a = Math.min(1, (night - 0.3) / 0.4), q = Math.max(1, sx * 3);
      ctx.globalAlpha = a * 0.35; ctx.fillStyle = '#ffe7a3'; ctx.beginPath();
      for (const b of NL.beams) { b.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.closePath(); }
      ctx.fill(); ctx.globalAlpha = a;
      ctx.fillStyle = '#fff4c8'; ctx.beginPath(); for (const [x, y] of NL.head) ctx.rect(x - q / 2, y - q / 2, q, q); ctx.fill();
      ctx.fillStyle = '#ff3b2f'; ctx.beginPath(); for (const [x, y] of NL.tail) ctx.rect(x - q / 2, y - q / 2, q, q); ctx.fill();
      ctx.globalAlpha = 1;
    }
    NL.beams.length = NL.head.length = NL.tail.length = 0;
  }
  function drawVehicle(o, len, wid, col, sx, ox, oy, night, isBus, lights = 3) {   // lights: 1 přední, 2 zadní
    const L = Math.hypot(o.dx, o.dy) || 1, fx_ = o.dx / L * (o.dirSign || 1), fy_ = o.dy / L * (o.dirSign || 1);
    const sxv = -fy_, syv = fx_;
    const lane = o.lane ?? 1.6, cxw = o.x - sxv * lane, cyw = o.y - syv * lane;
    const h0 = o.z ?? gz(cxw, cyw);                                            // výška silnice (na mostovce mostovka), jinak terén
    const base = toImg(cxw, cyw, h0);
    const nd = ndirOf(isBus), k = ((Math.round(Math.atan2(fy_, fx_) / (Math.PI * 2) * nd) % nd) + nd) % nd;
    const spr = vehicleSprite(col, k, isBus, len, wid, state.season === 'winter');
    drawBehindTrees(spr.c, base[0] + spr.x0, base[1] + spr.y0, spr.c.width, spr.c.height, cxw, cyw, h0, sx, ox, oy);
    if (night > 0.3 && !o.noLights && sx >= LIGHTS_SX) {                                    // světla jen při přiblížení; kreslí se najednou (flushLights)
      const P = (s, t, h) => { const p = toImg(cxw + fx_ * s + sxv * t, cyw + fy_ * s + syv * t, h0 + h); return [ox + p[0] * sx, oy + p[1] * sx]; };
      const hid = (s, t, h) => { const x = cxw + fx_ * s + sxv * t, y = cyw + fy_ * s + syv * t, [ix, iy] = toImg(x, y, h0 + h); return occluded(ix, iy, depth(x, y, h0 + h)); };   // za domem
      const l = len / 2, w = wid / 2;
      if (lights & 1 && !hid(l, 0, 0.6)) {                    // kužel jen po první dům v cestě (nesvítí skrz)
        let d = 0; for (const q of [3.5, 7, 10.5, 14]) { if (hid(l + q, 0, 0.1) || hid(l + q, -w - q * 0.28, 0.1) || hid(l + q, w + q * 0.28, 0.1)) break; d = q; }
        if (d) NL.beams.push([P(l, -w, 0.6), P(l + d, -w - d * 0.28, 0.1), P(l + d, w + d * 0.28, 0.1), P(l, w, 0.6)]);
      }
      for (const t of [-w * 0.7, w * 0.7]) { if (lights & 1 && !hid(l, t, 0.7)) NL.head.push(P(l, t, 0.7)); if (lights & 2 && !hid(-l, t, 0.7)) NL.tail.push(P(-l, t, 0.7)); }
    }
    return true;
  }
  // vánoční stromy (mesto.json "vanocni_strom"): strom samotný je ve vrstvě výzdoby (render.html mode=xmas), tady jen blikající světýlka
  // na jeho patrech. Tvar pater musí odpovídat render.html: patro i má spodek 1,2 + 1,75 i m, výšku 3 m a poloměr 3,7 − 0,56 i m.
  const xmasTrees = ({{XMAS_LL}} || []).map(([lat, lon], n) => {
    const x = (lon - cam.lon0) * cam.kx, y = (lat - cam.lat0) * cam.ky, g = gz(x, y), lights = [];
    for (let i = 0; i < 6; i++) {
      const z0 = 1.2 + i * 1.75, r = 3.7 - i * 0.56;
      for (let k = 0; k < 7 - i; k++) {
        const u = 0.12 + rnd(n * 100 + i * 10 + k) * 0.6, a = (225 + (rnd(n * 100 + i * 10 + k + 5) - 0.5) * 150) * Math.PI / 180;   // přivrácená strana (pohled od JZ)
        lights.push(toImg(x + Math.cos(a) * r * (1 - u), y + Math.sin(a) * r * (1 - u), g + z0 + 3.0 * u));
      }
    }
    return { c: toImg(x, y, g + 7), lights };
  });
  // kluziště (mesto.json "kluziste": [{lat, lon, d: délka m, s: šířka m, a: natočení delší strany ve ° od východu}]): jen v zimě
  const rinks = ({{KLUZISTE}} || []).map((k, i) => {
    const cx = (k.lon - cam.lon0) * cam.kx, cy = (k.lat - cam.lat0) * cam.ky, a = (k.a || 0) * Math.PI / 180, L = k.d || 40, W = k.s || 20;
    const ux = Math.cos(a), uy = Math.sin(a);
    const at = (s, t) => [cx + ux * s - uy * t, cy + uy * s + ux * t];
    const h = Math.max(...[-1, 0, 1].flatMap((i) => [-1, 0, 1].map((j) => gz(...at(i * L / 2, j * W / 2))))) + 0.12;   // vršek ledu jako v render.html
    const sk = Array.from({ length: Math.max(4, Math.round(L * W / 70)) }, (_, j) => ({ r: 0.3 + rnd(i * 50 + j) * 0.65, ph: rnd(i * 50 + j + 7) * 6.283,
      v: (0.18 + rnd(i * 50 + j + 3) * 0.2) * (j % 6 ? 1 : -1), col: SKIC[j % SKIC.length], hat: SKIC[(j * 3 + 1) % SKIC.length] }));
    return { at, ring: [at(-L / 2, -W / 2), at(L / 2, -W / 2), at(L / 2, W / 2), at(-L / 2, W / 2)], h, L, W, sk };
  });
  // vánoční stánky (mesto.json "vanocni_stanky"): stánky jsou ve vrstvě výzdoby (render.html mode=xmas), tady jen noční osvětlení.
  // Rozměry musí odpovídat render.html: stánek w × 2,4 m, okap 2,2 m, pult na straně −t, okénko 0,95–1,95 m.
  const stalls = [];
  for (const k of {{STANKY}} || []) {
    const n = k.n || 5, wS = k.w || 3.0, m = k.m ?? 1.2, a = (k.a || 0) * Math.PI / 180, ux = Math.cos(a), uy = Math.sin(a);
    const x0 = (k.lon - cam.lon0) * cam.kx, y0 = (k.lat - cam.lat0) * cam.ky;
    for (let i = 0; i < n; i++) {
      const sc = (i - (n - 1) / 2) * (wS + m), cx = x0 + ux * sc, cy = y0 + uy * sc, g = gz(cx, cy);
      const P = (s, t, h) => toImg(cx + ux * s - uy * t, cy + uy * s + ux * t, g + h), l = wS / 2;
      stalls.push({ c: P(0, 0, 1),
        win: [P(-l + 0.25, -1.23, 0.95), P(l - 0.25, -1.23, 0.95), P(l - 0.25, -1.23, 1.95), P(-l + 0.25, -1.23, 1.95)],
        pool: [P(-l - 0.8, -1.3, 0), P(l + 0.8, -1.3, 0), P(l + 2.2, -5.5, 0), P(-l - 2.2, -5.5, 0)],
        bulbs: Array.from({ length: 6 }, (_, j) => P(-l + 0.25 + j * (wS - 0.5) / 5, -1.45, 1.9)) });
    }
  }
  // světelné sochy (assets/vanoce.json "svetla"): socha je ve vrstvě výzdoby (render.html mode=xmas), tady světýlka na řetězech
  // a modrá záře v kašně. Profil řetězů musí odpovídat render.html.
  const glowsX = ({{SVETLA}} || []).map((k, n) => {
    const x = (k.lon - cam.lon0) * cam.kx, y = (k.lat - cam.lat0) * cam.ky, g = gz(x, y), r = k.r || 3.2, h = k.h || 5.5, pts = [];
    const prof = [[[0.35, h - 1.0], [1.5, h - 1.6], [1.5, 0.5]], [[1.5, h - 1.9], [r * 0.75, h - 1.8], [r, h - 2.6], [r, 0.5]]];
    for (let j = 0; j < 26; j++) {
      const th = (j / 26) * 2 * Math.PI, c = Math.cos(th), s = Math.sin(th);
      if (Math.sin(th - Math.PI / 4) > 0.35) continue;            // odvrácená strana (pohled od JZ) je za sochou
      for (const pl of prof) for (let i = 0; i + 1 < pl.length; i++) for (let u = 0; u < 1; u += 0.34) {
        const rr = pl[i][0] + (pl[i + 1][0] - pl[i][0]) * u, zz = pl[i][1] + (pl[i + 1][1] - pl[i][1]) * u;
        pts.push(toImg(x + c * rr, y + s * rr, g + zz));
      }
    }
    const pool = Array.from({ length: 16 }, (_, j) => toImg(x + Math.cos(j / 8 * Math.PI) * (r + 0.6), y + Math.sin(j / 8 * Math.PI) * (r + 0.6), g + 0.45));
    return { c: toImg(x, y, g + h / 2), ball: toImg(x, y, g + h - 0.5), pts, pool, n };
  });
  // bruslaři na zamrzlých rybnících (mesto.json "rybniky", zapíná administrace): elipsy uvnitř vodní plochy rybníka
  const pondSk = {};                                            // název rybníka -> bruslaři [cx, cy, rx, ph, v, col, hat] v pixelech obrázku
  const skH = toImg(0, 0, 1.7)[1] - toImg(0, 0, 0)[1];          // výška postavy 1,7 m v pixelech obrázku (záporná)
  onChunk.push((wk, d) => {
    for (const r of RYBNIKY) {
      if (pondSk[r.nazev]) continue;
      const x = (r.lon - cam.lon0) * cam.kx, y = (r.lat - cam.lat0) * cam.ky, [px, py] = toImg(x, y, gz(x, y));
      const P = d.water.ponds.find((p) => inPoly(px, py, p)); if (!P) continue;
      let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (const [a, b] of P) { x0 = Math.min(x0, a); y0 = Math.min(y0, b); x1 = Math.max(x1, a); y1 = Math.max(y1, b); }
      const n = Math.min(40, Math.max(6, Math.round((x1 - x0) * (y1 - y0) * cam.mpp * cam.mpp / 900))), out = [];
      for (let k = 0; out.length < n && k < n * 30; k++) {
        const cx = x0 + rnd(k * 7 + 1) * (x1 - x0), cy = y0 + rnd(k * 11 + 2) * (y1 - y0), rx = (4 + rnd(k * 13 + 3) * 14) / cam.mpp;
        if ([0, 1, 2, 3, 4, 5, 6, 7].every((q) => inPoly(cx + Math.cos(q * 0.785) * rx, cy + Math.sin(q * 0.785) * rx * 0.5, P)))
          out.push([cx, cy, rx, rnd(k * 17) * 6.283, (0.25 + rnd(k * 19) * 0.3) * (k % 5 ? 1 : -1), SKIC[k % SKIC.length], SKIC[(k * 3 + 1) % SKIC.length], wk]);
      }
      pondSk[r.nazev] = out;
    }
  });
  // svíčky na hrobech (overlay/<čtverec>.json "svicky": [x, y obrázku, náhoda]), kreslí se večer
  const svicky = [], SVB = 512, svGrid = new Map();             // mřížka po 512 px obrázku: každý snímek jen buňky ve výřezu
  onChunk.push((k, d) => {
    for (const [x, y, u] of d.svicky || []) {
      const q = [x, y, u, k], key = Math.floor(x / SVB) + ',' + Math.floor(y / SVB);
      svicky.push(q); if (!svGrid.has(key)) svGrid.set(key, []); svGrid.get(key).push(q);
    }
  });
