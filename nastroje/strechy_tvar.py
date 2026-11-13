# Tvar střech běžných domů proložený měřením DMP OK (ČÚZK, rastr 0,5 m) místo odhadu.
# Pro každý dům čtverce zkusí plochou, sedlovou a valbovou střechu (každý díl půdorysu s hřebenem podél i napříč),
# výšku okapu a hřebene, a vybere tvar, který nejlíp sedí na měření. Zároveň změří chybu současného modelu (měřák přesnosti).
#   python nastroje/strechy_tvar.py -1,-1 [-1,0 ...] [--zapsat]
# Výstup: build/strechy_tvar_<čtverec>.csv (chyba před a po pro každý dům), s --zapsat i assets/strechy_tvar.json
# (id -> {r, e m n. m., rh, parts ve společných souřadnicích}); prep.py ho použije u domů bez dominanty a vlastního modelu.
# Spouštět z kořene repa po prep.py dotčeného čtverce (bere půdorysy a díly ze scene.json).
import json, math, os, sys; sys.path.insert(0, '.')
import numpy as np, shapely, shapely.affinity
from shapely.geometry import Polygon, Point
from pyproj import Transformer
import geo, odlitek

T = Transformer.from_crs(4326, 5514, always_xy=True)
Z = np.load('build/dmr_grid.npz'); G = Z['g'].astype(float); gx0, gy0, gr = float(Z['x0']), float(Z['y0']), float(Z['res'])
TAN = math.tan(math.radians(40))          # renderer kreslí šikmé střechy nejvýš se sklonem 40°
HREF = geo.HREF
# ortofoto po 0,4 m/px (dlaždice z nastroje/strechy.py): zelené pixely = koruna stromu nad střechou, ty se do proložení neberou
from PIL import Image
OM, OT = 0.4, 1500; OX0, _, _, OY1 = geo.extent(geo.MARGIN + 20); _oc = {}


def green(x, y):
    """x, y ve společných souřadnicích -> True, kde je na ortofotu zeleň"""
    c = np.floor((x - OX0) / OM).astype(int); r = np.floor((OY1 - y) / OM).astype(int); out = np.zeros(x.shape, bool)
    for k in set(zip((c // OT * OT).tolist(), (r // OT * OT).tolist())):
        if k not in _oc:
            if len(_oc) > 12: _oc.pop(next(iter(_oc)))
            try: _oc[k] = np.asarray(Image.open(f'build/orto04/{k[0]}_{k[1]}.jpg').convert('RGB')).astype(int)
            except OSError: _oc[k] = None
        a = _oc[k]
        if a is None: continue
        m = (c // OT * OT == k[0]) & (r // OT * OT == k[1])
        px = a[np.clip(r[m] - k[1], 0, a.shape[0] - 1), np.clip(c[m] - k[0], 0, a.shape[1] - 1)]
        out[m] = (px[:, 1] > px[:, 0] + 5) & (px[:, 1] > px[:, 2] + 5)
    return out


def terrain(X, Y):
    return G[np.clip(np.floor((Y - gy0) / gr).astype(int), 0, G.shape[0] - 1), np.clip(np.floor((X - gx0) / gr).astype(int), 0, G.shape[1] - 1)]


def max_rect(M):
    best = (0, None); h = np.zeros(M.shape[1], int)
    for r in range(M.shape[0]):
        h = np.where(M[r], h + 1, 0); st = []
        for c in range(M.shape[1] + 1):
            cur = h[c] if c < M.shape[1] else 0; start = c
            while st and st[-1][1] >= cur:
                s0, hh = st.pop()
                if hh * (c - s0) > best[0]: best = (hh * (c - s0), (r - hh + 1, s0, r, c - 1))
                start = s0
            st.append((start, cur))
    return best[1]


def roof_parts(p, ang):
    """stejné jako prep.py: půdorys -> obdélníky [cx, cy, úhel, L, W]"""
    cs = 0.6; c0 = p.centroid
    q = shapely.affinity.rotate(p, -ang, origin=c0, use_radians=True)
    minx, miny, maxx, maxy = q.bounds
    xs = np.arange(minx + cs / 2, maxx, cs); ys = np.arange(miny + cs / 2, maxy, cs)
    if len(xs) < 3 or len(ys) < 3: return []
    XX, YY = np.meshgrid(xs, ys); M = shapely.contains_xy(q, XX, YY); total = M.sum(); out = []
    for _ in range(4):
        r = max_rect(M)
        if r is None: break
        r0, c0_, r1, c1 = r; area = (r1 - r0 + 1) * (c1 - c0_ + 1)
        if area < max(0.14 * total, 20 / cs ** 2): break
        w_, h_ = (c1 - c0_ + 1) * cs, (r1 - r0 + 1) * cs
        if min(w_, h_) < 3.0: M[r0:r1 + 1, c0_:c1 + 1] = False; continue
        cx = (xs[c0_] + xs[c1]) / 2; cy = (ys[r0] + ys[r1]) / 2
        pt = shapely.affinity.rotate(Point(cx, cy), ang, origin=c0, use_radians=True)
        a = ang if w_ >= h_ else ang + math.pi / 2
        out.append([pt.x, pt.y, a, max(w_, h_), min(w_, h_)])
        M[r0:r1 + 1, c0_:c1 + 1] = False
    return out


def shape(parts, kind, x, y):
    """tvar střechy 0..1 nad okapem v bodech (x, y) pro každý díl: [počet dílů, bodů] + max. výška dílu (strop sklonu)"""
    F, caps = [], []
    for cx, cy, a, L, W in parts:
        dx, dy = x - cx, y - cy; s = dx * math.cos(a) + dy * math.sin(a); t = -dx * math.sin(a) + dy * math.cos(a)
        hl, hw = L / 2, W / 2
        inside = (np.abs(s) <= hl) & (np.abs(t) <= hw)
        f = 1 - np.abs(t) / hw
        if kind == 'hipped': f = np.minimum(f, (hl - np.abs(s)) / hw)
        F.append(np.where(inside, np.clip(f, 0, 1), 0.0)); caps.append(hw * TAN)
    return np.array(F), np.array(caps)


def surface(kind, parts, e, rh, x, y):
    if kind == 'flat' or not parts: return np.full(x.shape, e)
    F, caps = shape(parts, kind, x, y)
    return e + (F * np.minimum(caps, rh)[:, None]).max(0)


def err(z, m):
    """chyba modelu: průměr absolutních odchylek bez 10 % nejhorších (koruny stromů přes střechu, antény)"""
    d = np.sort(np.abs(z - m)); return float(d[:max(1, int(len(d) * 0.9))].mean())


def fit(kind, parts, x, y, z, emin):
    if kind == 'flat':
        e = max(float(np.median(z)), emin); return err(z, np.full(z.shape, e)), e, 0.0
    F, caps = shape(parts, kind, x, y); best = None
    for rh in np.arange(0.5, 7.01, 0.25):
        m = (F * np.minimum(caps, rh)[:, None]).max(0)
        e = max(float(np.median(z - m)), emin)
        q = err(z, e + m)
        if best is None or q < best[0]: best = (q, e, float(rh))
    return best


def flip(p): return [p[0], p[1], p[2] + math.pi / 2, p[4], p[3]]


def run(ch):
    d = geo.chunk_dir(ch); S = json.load(open(f'{d}/scene.json')); I = json.load(open(f'{d}/info_src.json'))['buildings']
    CX, CY = geo.chunk_center(ch); B = {b['id']: b for b in S['buildings']}
    n_oid = {}
    for q in I: n_oid[q['oid']] = n_oid.get(q['oid'], 0) + 1
    rows, out = [], {}
    for q in I:
        b = B.get(q['id'])
        if not b or b.get('lm') or b.get('gh') or b.get('dn') or n_oid[q['oid']] > 1: continue
        p = Polygon(b['p'])
        if not p.is_valid or p.area < 40: continue
        inner = p.buffer(-0.6)
        if inner.is_empty: continue
        x0, y0, x1, y1 = inner.bounds
        X, Y = np.meshgrid(np.arange(x0, x1, 0.5), np.arange(y0, y1, 0.5)); m = shapely.contains_xy(inner, X, Y)
        x, y = X[m], Y[m]
        if len(x) < 40: continue
        lo, la = geo.to_lonlat(x + CX, y + CY); JX, JY = T.transform(lo, la)
        z = odlitek.dsm(JX, JY) - HREF; ok = np.isfinite(z)
        if ok.sum() < 40: continue
        gr_ = green(x + CX, y + CY); ok &= ~gr_
        if gr_.mean() > 0.4 or ok.sum() < 40: continue      # dům z velké části pod stromy: nechat odhad
        x, y, z = x[ok], y[ok], z[ok]
        gnd = float(np.median(terrain(JX[ok], JY[ok]))) - HREF
        if np.median(z) - gnd < 1.5: continue             # měření ukazuje terén nebo zeleň: dům tu není nebo je pod stromy
        before = err(z, surface(b['r'], b['parts'], b['e'], b['rh'], x, y))
        o = p.minimum_rotated_rectangle; cs = list(o.exterior.coords)[:3]
        e1 = np.subtract(cs[1], cs[0]); e2 = np.subtract(cs[2], cs[1])
        if np.linalg.norm(e1) < np.linalg.norm(e2): e1, e2 = e2, e1
        ang = math.atan2(e1[1], e1[0])
        base = b['parts'] or ([[o.centroid.x, o.centroid.y, ang, float(np.linalg.norm(e1)), float(np.linalg.norm(e2))]]
                              if p.area / max(o.area, 1) > 0.9 else roof_parts(p, ang))
        emin = gnd + 2.2
        cand = [(*fit('flat', [], x, y, z, emin), 'flat', [])]
        if base:
            for mask in range(1 << len(base)):
                ps = [flip(pp) if mask >> k & 1 else pp for k, pp in enumerate(base)]
                for kind in ('gabled', 'hipped'):
                    cand.append((*fit(kind, ps, x, y, z, emin), kind, ps))
        cand.sort(key=lambda c: c[0])
        q_, e, rh, kind, ps = cand[0]
        # šikmá střecha jen když jasně sedí líp než plochá (jinak šum měření vyrobí falešný hřeben)
        fl = next(c for c in cand if c[3] == 'flat')
        if kind != 'flat' and fl[0] - q_ < 0.15: q_, e, rh, kind, ps = fl
        use = before - q_ >= 0.3 and q_ < 1.2           # zapsat jen zřetelné zlepšení se spolehlivým proložením
        rows.append([q['oid'], q['lat'], q['lon'], round(p.area), b['r'], round(before, 2), kind, round(q_, 2), round(e - gnd, 1), round(rh, 2), int(use)])
        if use:
            out[q['oid']] = {'r': kind, 'e': round(e + HREF, 2), 'rh': round(rh, 2),
                             'parts': [[round(pp[0] + CX, 2), round(pp[1] + CY, 2), round(pp[2], 4), round(pp[3], 2), round(pp[4], 2)] for pp in ps]}
    return rows, out


if __name__ == '__main__':
    chs = [tuple(int(v) for v in a.split(',')) for a in sys.argv[1:] if not a.startswith('--')]
    allout = {}
    for ch in chs:
        rows, out = run(ch); allout.update(out)
        f = f'build/strechy_tvar_{ch[0]}_{ch[1]}.csv'
        open(f, 'w', encoding='utf-8').write('id;lat;lon;plocha;strecha_ted;chyba_ted_m;strecha_mereni;chyba_po_m;okap_m;rh_m;pouzito\n' + '\n'.join(';'.join(map(str, r)) for r in rows))
        A = np.array([[r[3], r[5], r[7] if r[10] else r[5]] for r in rows], float)
        w = A[:, 0]
        print(ch, 'domů', len(rows), 'zlepšeno', len(out), f'chyba (vážená plochou) před {np.average(A[:, 1], weights=w):.2f} m, po {np.average(A[:, 2], weights=w):.2f} m', flush=True)
        ch_kinds = {}
        for r in rows:
            if r[10]: ch_kinds[(r[4], r[6])] = ch_kinds.get((r[4], r[6]), 0) + 1
        print('  změny tvaru', sorted(ch_kinds.items(), key=lambda kv: -kv[1]))
    if '--zapsat' in sys.argv:
        old = json.load(open('assets/strechy_tvar.json')) if os.path.exists('assets/strechy_tvar.json') else {}
        old.update(allout); json.dump(old, open('assets/strechy_tvar.json', 'w'), separators=(',', ':'))
        print('zapsáno', len(allout), '-> assets/strechy_tvar.json (celkem', len(old), ')')
