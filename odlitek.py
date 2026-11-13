# „odlitek“ budovy z DMP OK (ČÚZK, CC BY 4.0, model povrchu z obrazové korelace, rastr 0,5 m):
# skutečný tvar střech a hmoty dominanty místo odhadu. Listy leží v build/dmpok/*.tif (+ .tfw), stáhne je nastroje/dmpok.py.
# cast(p, ground, href) vrátí mřížku výšek zarovnanou s budovou; kreslí ji render.html (b.ds).
import glob, math, os, subprocess
import numpy as np, shapely, shapely.affinity
from PIL import Image
from pyproj import Transformer
import geo
Image.MAX_IMAGE_PIXELS = None
_T = Transformer.from_crs(4326, 5514, always_xy=True)
_tiles = None; _cache = {}


def _index():
    global _tiles
    if _tiles is None:
        _tiles = []
        for f in sorted(glob.glob('build/dmpok/*.tfw')):
            v = [float(x) for x in open(f).read().split()]; t = f[:-4] + '.tif'
            if os.path.exists(t):
                w, h = Image.open(t).size
                _tiles.append((t, v[0], v[4], v[5], w, h))     # rozlišení, x a y středu levého horního pixelu
    return _tiles


def dsm(X, Y):
    """výška povrchu (Bpv) v bodech S-JTSK, bilineárně; mimo stažené listy NaN"""
    X = np.asarray(X, float); Y = np.asarray(Y, float); out = np.full(X.shape, np.nan)
    for t, res, x0, y0, w, h in _index():
        fi = (X - x0) / res; fj = (y0 - Y) / res
        m = (fi >= 0) & (fi < w - 1) & (fj >= 0) & (fj < h - 1) & np.isnan(out)
        if not m.any(): continue
        if t not in _cache:
            if len(_cache) > 3: _cache.pop(next(iter(_cache)))
            _cache[t] = np.asarray(Image.open(t), dtype=np.float32)
        a = _cache[t]; i0 = np.floor(fi[m]).astype(int); j0 = np.floor(fj[m]).astype(int); tx = fi[m] - i0; ty = fj[m] - j0
        out[m] = a[j0, i0] * (1 - tx) * (1 - ty) + a[j0, i0 + 1] * tx * (1 - ty) + a[j0 + 1, i0] * (1 - tx) * ty + a[j0 + 1, i0 + 1] * tx * ty
    return out


def _win(a, fn):
    p = np.pad(a, 1, mode='edge'); H, W = a.shape
    return fn(np.stack([p[1 + dj:H + 1 + dj, 1 + di:W + 1 + di] for dj in (-1, 0, 1) for di in (-1, 0, 1)]), axis=0)


def _segments(z, m, T):
    """souvislé plochy: sousední buňky (4 směry) s rozdílem výšky pod T"""
    H, W = z.shape; lab = np.full((H, W), -1, int); n = 0
    for j in range(H):
        for i in range(W):
            if not m[j, i] or lab[j, i] >= 0: continue
            st = [(j, i)]; lab[j, i] = n
            while st:
                a, b = st.pop()
                for c, d in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                    if 0 <= c < H and 0 <= d < W and m[c, d] and lab[c, d] < 0 and abs(z[c, d] - z[a, b]) < T:
                        lab[c, d] = n; st.append((c, d))
            n += 1
    return lab, n


def ortho(x0, y0, x1, y1, mpp=0.2):
    """výřez ortofota ČÚZK v místních souřadnicích (osy východ / sever), s mezipamětí v build/odlitek/"""
    os.makedirs('build/odlitek', exist_ok=True)
    w, h = int((x1 - x0) / mpp), int((y1 - y0) / mpp)
    f = f'build/odlitek/o_{x0:.0f}_{y0:.0f}_{w}_{h}.jpg'
    if not os.path.exists(f):
        lo0, la0 = geo.to_lonlat(x0, y0); lo1, la1 = geo.to_lonlat(x1, y1)
        subprocess.run(['curl', '-s', '-m', '120', '-A', 'izomapa-pribram/1.0', '-o', f,
                        'https://ags.cuzk.gov.cz/arcgis1/services/ORTOFOTO/MapServer/WMSServer?SERVICE=WMS&VERSION=1.3.0'
                        f'&REQUEST=GetMap&LAYERS=0&STYLES=&CRS=EPSG:4326&BBOX={la0},{lo0},{la1},{lo1}&WIDTH={w}&HEIGHT={h}&FORMAT=image/jpeg'])
    try: return np.asarray(Image.open(f).convert('RGB')), mpp
    except OSError: return None, mpp


def cast(p, ground, href, off=(0.0, 0.0), step=0.5, minh=2.0, cut=(), T=None, ang=None):
    """p = půdorys v souřadnicích čtverce, off = střed čtverce (mřížka se počítá ve společných souřadnicích, aby vyšla
    v sousedních čtvercích stejně), ground(x, y) = terén scény, href = nula scény (Bpv). cut = půdorysy, které odlévá jiná budova."""
    p = shapely.affinity.translate(p, off[0], off[1]); cut = [shapely.affinity.translate(c, off[0], off[1]) for c in cut]
    T = T or 3.0 * step                                   # skok výšky mezi sousedy, od kterého je to zeď (sklon nad ~72°)
    if ang is None:
        cs = list(p.minimum_rotated_rectangle.exterior.coords); e = max(((cs[k + 1][0] - cs[k][0], cs[k + 1][1] - cs[k][1]) for k in range(4)), key=lambda v: v[0] ** 2 + v[1] ** 2)
        ang = math.atan2(e[1], e[0])
    ca, sa = math.cos(ang), math.sin(ang)
    q = p; xy = np.array(q.exterior.coords)
    s = xy[:, 0] * ca + xy[:, 1] * sa; t = -xy[:, 0] * sa + xy[:, 1] * ca
    s0, t0 = (math.floor(s.min() / step) - 1) * step, (math.floor(t.min() / step) - 1) * step
    nx, ny = int((s.max() - s0) / step) + 3, int((t.max() - t0) / step) + 3
    S, Tt = np.meshgrid(s0 + (np.arange(nx) + 0.5) * step, t0 + (np.arange(ny) + 0.5) * step)
    X = S * ca - Tt * sa; Y = S * sa + Tt * ca                               # společné místní souřadnice
    lon, lat = geo.to_lonlat(X, Y)
    JX, JY = _T.transform(lon, lat)
    z = dsm(JX, JY)
    if np.isnan(z).all(): return None
    z = z - href; g = ground(X - off[0], Y - off[1])
    inside = shapely.contains_xy(q, X, Y)
    for c in cut: inside &= ~shapely.contains_xy(c, X, Y)
    z = np.where(np.isnan(z), g, z)
    z = _win(z, np.median)
    # zostření hran: buňka na rozmazané hraně (velký místní rozsah) přejde k bližšímu z místního minima / maxima
    for _ in range(3):
        lo, hi = _win(z, np.min), _win(z, np.max)
        edge = (hi - lo) > 2.0
        z = np.where(edge, np.where(z - lo < hi - z, lo, hi), z)
    # obrys přesně podle půdorysu: nízké buňky uvnitř (posun půdorysu vůči snímkům, rozmazaná hrana) převezmou výšku
    # nejbližší střechy; velká nízká plocha (dvůr zakreslený jako budova) zůstane prázdná
    good = inside & (z - g > minh); bad = inside & ~good
    bl, bn = _segments(np.zeros_like(z), bad, 1.0)
    big = np.isin(bl, np.nonzero(np.bincount(bl[bl >= 0], minlength=bn) > 30.0 / step ** 2)[0])
    fill = bad & ~big
    for _ in range(40):
        if not fill.any(): break
        pz = np.pad(np.where(good, z, np.nan), 1, constant_values=np.nan)
        nb = np.stack([pz[1 + dj:ny + 1 + dj, 1 + di:nx + 1 + di] for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1))])
        k = np.isfinite(nb).sum(0); v = np.nansum(nb, 0) / np.maximum(k, 1)
        new = fill & (k > 0); z = np.where(new, v, z); good |= new; fill &= ~new
    m = good
    lab, n = _segments(z, m, T)
    # drobné úlomky (pod 1,5 m²) přilepit k sousední ploše s nejbližší výškou
    for _ in range(4):
        cnt = np.bincount(lab[lab >= 0], minlength=n)
        small = (lab >= 0) & (cnt[np.maximum(lab, 0)] < 1.5 / step ** 2)
        if not small.any(): break
        for j, i in zip(*np.nonzero(small)):
            best = None
            for c, d in ((j + 1, i), (j - 1, i), (j, i + 1), (j, i - 1)):
                if 0 <= c < ny and 0 <= d < nx and lab[c, d] >= 0 and not small[c, d]:
                    if best is None or abs(z[c, d] - z[j, i]) < abs(z[best] - z[j, i]): best = (c, d)
            if best: lab[j, i] = lab[best]; z[j, i] = z[best]
    pid, pl = _planes(z, lab, m, step)
    jj, ii = np.mgrid[0:ny, 0:nx]
    zp = np.where(pid >= 0, pl[np.maximum(pid, 0), 0] * (ii + 0.5) * step + pl[np.maximum(pid, 0), 1] * (jj + 0.5) * step + pl[np.maximum(pid, 0), 2], z)
    return {'ang': ang, 'ox': s0 * ca - t0 * sa - off[0], 'oy': s0 * sa + t0 * ca - off[1], 'st': step, 'nx': nx, 'ny': ny,
            'z': zp, 'm': m & (pid >= 0), 'lab': lab, 'pid': pid, 'pl': pl, 'g': g, 'X': X, 'Y': Y}


def _planes(z, lab, m, step, tol=0.6, minc=40):
    """střecha jako několik rovin se spádem jen kolmo ke zdem (mřížka je zarovnaná s budovou): plochá, spád podél s, nebo podél t.
    Opakovaně najde rovinu s nejvíc buňkami, vezme její souvislou část a pokračuje ve zbytku. Vrací číslo roviny pro každou
    buňku a roviny [a, b, c]: z = a·s + b·t + c (s, t v metrech od rohu mřížky). Roviny se protínají v ostrých hřebenech."""
    ny, nx = z.shape; pid = np.full((ny, nx), -1, int); P = []
    rng = np.random.default_rng(7)
    jj, ii = np.mgrid[0:ny, 0:nx]; S = (ii + 0.5) * step; Tt = (jj + 0.5) * step
    def fit(sel):
        zs = z[sel]; n = len(zs); one = np.ones(n); best = None
        for kind, A in ((1, np.stack([S[sel], one], 1)), (2, np.stack([Tt[sel], one], 1))):
            k, c = np.linalg.lstsq(A, zs, rcond=None)[0]; rms = float(np.sqrt(np.mean((A @ [k, c] - zs) ** 2)))
            if best is None or rms < best[0]: best = (rms, [k, 0.0, c] if kind == 1 else [0.0, k, c])
        if n >= 12:                               # střecha šikmo k mřížce (křídlo natočené jinak než zbytek budovy): obecná rovina
            A = np.stack([S[sel], Tt[sel], one], 1); g3 = np.linalg.lstsq(A, zs, rcond=None)[0]; r3 = float(np.sqrt(np.mean((A @ g3 - zs) ** 2)))
            if r3 + 0.15 < best[0]: best = (r3, [float(g3[0]), float(g3[1]), float(g3[2])])
        c = float(np.median(zs)); rf = float(np.sqrt(np.mean((zs - c) ** 2)))
        if math.hypot(best[1][0], best[1][1]) < 0.12: return [0.0, 0.0, c]      # plochá jen střecha se sklonem pod ~7°; šum jinak dělá z mírné střechy terasy
        return best[1]
    def ev(p_): return p_[0] * S + p_[1] * Tt + p_[2]
    def comp(mask, j, i):
        out = np.zeros_like(mask); st = [(j, i)]; out[j, i] = True
        while st:
            a, b = st.pop()
            for c, d in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                if 0 <= c < ny and 0 <= d < nx and mask[c, d] and not out[c, d]: out[c, d] = True; st.append((c, d))
        return out
    for k in np.unique(lab[m]):
        R = (lab == k) & m; fails = 0
        while R.sum() >= minc and fails < 25:
            cj, ci = np.nonzero(R); best = None
            for q in rng.choice(len(cj), min(60, len(cj)), replace=False):
                j, i = cj[q], ci[q]
                w = np.zeros_like(R); w[max(0, j - 5):j + 6, max(0, i - 5):i + 6] = True; w &= R
                if w.sum() < 30: continue
                pl = fit(w); inl = R & (np.abs(ev(pl) - z) < tol)
                if not inl[j, i]: continue
                sc = int(inl.sum())
                if best is None or sc > best[0]: best = (sc, j, i, inl)
            if best is None: break
            cc = comp(best[3], best[1], best[2])
            if cc.sum() < minc: fails += 1; continue
            pl = fit(cc); cc2 = comp(R & (np.abs(ev(pl) - z) < tol), best[1], best[2])
            if cc2.sum() >= cc.sum(): cc = cc2; pl = fit(cc)
            pid[cc] = len(P); P.append(pl); R &= ~cc
    # zbytek: k sousední rovině téže části, když sedí do 2,5 m; jinak vlastní plochá ploška (věžička, komín)
    left = m & (pid < 0)
    for _ in range(40):
        if not left.any(): break
        ch = False
        for j, i in zip(*np.nonzero(left)):
            best = None
            for c, d in ((j + 1, i), (j - 1, i), (j, i + 1), (j, i - 1)):
                if 0 <= c < ny and 0 <= d < nx and pid[c, d] >= 0 and lab[c, d] == lab[j, i]:
                    a, b, c0 = P[pid[c, d]]; r = abs(a * S[j, i] + b * Tt[j, i] + c0 - z[j, i])
                    if r < 2.5 and (best is None or r < best[0]): best = (r, pid[c, d])
            if best: pid[j, i] = best[1]; left[j, i] = False; ch = True
        if not ch: break
    ll, ln = _segments(np.round(z * 2) / 2, left, 0.6)
    for q in range(ln):
        sel = ll == q; pid[sel] = len(P); P.append([0.0, 0.0, float(np.median(z[sel]))])
    P = np.array(P, float) if P else np.zeros((0, 3))
    # sloučit sousední roviny téže části, které jsou skoro stejné (šum rozdělí jednu střechu na pruhy se schůdky)
    for _ in range(60):
        pairs = set()
        for dj, di in ((1, 0), (0, 1)):
            A = pid[dj:, di:] if dj or di else pid; B = pid[:ny - dj, :nx - di]
            ok = (A >= 0) & (B >= 0) & (A != B) & (lab[dj:, di:] == lab[:ny - dj, :nx - di])
            pairs |= set(zip(np.minimum(A[ok], B[ok]).tolist(), np.maximum(A[ok], B[ok]).tolist()))
        best = None
        for a_, b_ in pairs:
            pa, pb = P[a_], P[b_]
            if not any(pa[:2]) and not any(pb[:2]) and abs(pa[2] - pb[2]) < 1.6:      # dvě „terasy“ těsně nad sebou = jedna mírná střecha
                sel = ((pid == a_) | (pid == b_)) & m; pu = fit(sel); rms = float(np.sqrt(np.mean((ev(pu) - z)[sel] ** 2)))
                if rms < 0.75 and (best is None or rms < best[0]): best = (rms, a_, b_)
                continue
            if abs(pa[0] - pb[0]) > 0.12 or abs(pa[1] - pb[1]) > 0.12: continue
            sel = (pid == a_) | (pid == b_); dlt = float(np.mean(np.abs((pa[0] - pb[0]) * S[sel] + (pa[1] - pb[1]) * Tt[sel] + pa[2] - pb[2])))
            if dlt < 0.6 and (best is None or dlt < best[0]): best = (dlt, a_, b_)
        if best is None: break
        _, a_, b_ = best; pid[pid == b_] = a_; P[a_] = fit((pid == a_))
    def val(q): return P[np.maximum(q, 0), 0] * S + P[np.maximum(q, 0), 1] * Tt + P[np.maximum(q, 0), 2]
    # hranice mezi rovinami téže části: buňka patří rovině, která jí sedí líp (rovnější hřebeny)
    for _ in range(4):
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = np.roll(pid, (dj, di), (0, 1)); ql = np.roll(lab, (dj, di), (0, 1))
            ok = m & (q >= 0) & (q != pid) & (ql == lab)
            if dj == 1: ok[0, :] = False
            if dj == -1: ok[-1, :] = False
            if di == 1: ok[:, 0] = False
            if di == -1: ok[:, -1] = False
            sw = ok & (np.abs(val(q) - z) + 0.05 < np.abs(val(pid) - z)); pid[sw] = q[sw]
    # rovnější hranice: buňka převezme rovinu, kterou má většina okolí 3 × 3 (když jí výškově sedí), a pak většina okolí 5 × 5
    # rozhodne i přes výškový skok (zubatá zeď mezi částmi se narovná, tenké výčnělky zmizí)
    for rad, need, chk in ((1, 5, True), (1, 5, True), (2, 13, False), (2, 13, False)):
        pp = np.pad(pid, rad, constant_values=-1); w = range(-rad, rad + 1)
        nb = [pp[rad + dj:ny + rad + dj, rad + di:nx + rad + di] for dj in w for di in w]
        bestc = np.zeros(pid.shape, int); bestk = pid.copy()
        for k in np.unique(pid[m]):
            cnt = sum((q == k).astype(int) for q in nb)
            up = cnt > bestc; bestc = np.where(up, cnt, bestc); bestk = np.where(up, k, bestk)
        sw = m & (bestk != pid) & (bestc >= need)
        if chk: sw &= np.abs(val(bestk) - z) < 1.0
        pid = np.where(sw, bestk, pid)
    return pid, P


def colors(c, fallback):
    """barva každé plochy z ortofota: medián světlejší části (bez stínů); malé a nejisté plochy dostanou fallback"""
    X, Y, lab, m = c['X'], c['Y'], c['lab'], c['m']
    x0, y0, x1, y1 = math.floor(X.min()) - 2, math.floor(Y.min()) - 2, math.ceil(X.max()) + 2, math.ceil(Y.max()) + 2
    img, mpp = ortho(x0, y0, x1, y1)
    out = {}
    if img is None: return {int(k): list(fallback) for k in np.unique(lab[m])}
    px = img[np.clip(((y1 - Y) / mpp).astype(int), 0, img.shape[0] - 1), np.clip(((X - x0) / mpp).astype(int), 0, img.shape[1] - 1)]
    for k in np.unique(lab[m]):
        q = px[(lab == k) & m].astype(int)
        if len(q) < 16: out[int(k)] = list(fallback); continue
        L = q.mean(1); lo, hi = np.percentile(L, 40), np.percentile(L, 90); q = q[(L >= lo) & (L <= hi)]
        out[int(k)] = [int(v) for v in np.median(q, axis=0)] if len(q) else list(fallback)
    return out


def scene(p, ground, href, off, fallback, cut=()):
    """odlitek pro scene.json: mřížka čísel rovin, roviny a barvy; None, když pro místo nejsou stažené listy DMP OK"""
    c = cast(p, ground, href, off=off, cut=cut)
    if c is None or not c['m'].any(): return None
    col = colors(c, fallback); pid, lab, m = c['pid'], c['lab'], c['m']
    cols, pc = [], []
    for k in range(len(c['pl'])):
        sel = (pid == k) & m
        rgb = col.get(int(np.bincount(lab[sel]).argmax()), list(fallback)) if sel.any() else list(fallback)
        if rgb not in cols: cols.append(rgb)
        pc.append(cols.index(rgb))
    rings = [[[round(x, 2), round(y, 2)] for x, y in r.coords[:-1]] for r in [p.exterior] + list(p.interiors)]
    return {'ox': round(c['ox'], 3), 'oy': round(c['oy'], 3), 'ang': round(c['ang'], 5), 'st': c['st'], 'nx': c['nx'], 'ny': c['ny'],
            'pl': [[round(float(a), 4), round(float(b), 4), round(float(z0), 2)] for a, b, z0 in c['pl']], 'pc': pc, 'cols': cols,
            'c': [int(v) for v in np.where(m, pid, -1).ravel()], 'rings': rings,
            'cut': [[[round(x, 2), round(y, 2)] for x, y in q.exterior.coords[:-1]] for q in cut if q.geom_type == 'Polygon'],
            'top': round(float(c['z'][m].max()), 2)}
