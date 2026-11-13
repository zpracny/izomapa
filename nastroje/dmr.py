# přesný terén z DMR 5G (ČÚZK, CC BY 4.0, laserové body terénu): python nastroje/dmr.py
# stáhne listy pokrývající mapu do build/dmr/ a vyrobí build/dmr_grid.npz (mřížka 5 m v S-JTSK, výšky Bpv);
# prep.py ji pak použije místo terénu Terrarium (ten zůstane jen mimo pokrytí)
import glob, os, re, subprocess, sys; sys.path.insert(0, '.')
import numpy as np, laspy, geo
from pyproj import Transformer
D = 'build/dmr/'; os.makedirs(D, exist_ok=True)
A = D + 'atom.xml'
if not os.path.exists(A): subprocess.run(['curl', '-sL', '-m', '300', '-o', A, 'https://atom.cuzk.gov.cz/DMR5G-SJTSK/DMR5G-SJTSK.xml'], check=True)
T = Transformer.from_crs(4326, 5514, always_xy=True)
X0, Y0, X1, Y1 = geo.extent(geo.MARGIN + 200)
cx, cy = [], []
for x in np.linspace(X0, X1, 30):
    for y in np.linspace(Y0, Y1, 30):
        lo, la = geo.to_lonlat(x, y); a, b = T.transform(lo, la); cx.append(a); cy.append(b)
KX0, KX1, KY0, KY1 = min(cx), max(cx), min(cy), max(cy)
s = open(A, encoding='utf8').read(); use = []
for e in s.split('<entry>')[1:]:
    p = re.search(r'<georss:polygon>(.*?)<', e); k = re.search(r'DMR5G-SJTSK_([A-Z0-9]+)\.xml', e)
    if not (p and k): continue
    v = list(map(float, p.group(1).split())); la, lo = v[0::2], v[1::2]
    xs, ys = T.transform(lo, la)
    if max(xs) > KX0 and min(xs) < KX1 and max(ys) > KY0 and min(ys) < KY1: use.append(k.group(1))
use = sorted(set(use)); print('listů DMR 5G', len(use), flush=True)
for n in use:
    if glob.glob(f'{D}{n}.la[sz]'): continue
    subprocess.run(['curl', '-sL', '-m', '300', '-o', f'{D}{n}.zip', f'https://openzu.cuzk.cz/opendata/DMR5G/epsg-5514/{n}.zip'], check=True)
    subprocess.run(['unzip', '-oq', f'{D}{n}.zip', '-d', D], check=True); os.remove(f'{D}{n}.zip')
RES = 5.0
gx0, gy0 = np.floor(KX0 / RES) * RES, np.floor(KY0 / RES) * RES
W, H = int((KX1 - gx0) / RES) + 2, int((KY1 - gy0) / RES) + 2
S, C = np.zeros(W * H), np.zeros(W * H)
for f in sorted(glob.glob(f'{D}*.la[sz]')):
    l = laspy.read(f); x, y, z = np.asarray(l.x), np.asarray(l.y), np.asarray(l.z)
    if 'classification' in l.point_format.dimension_names:
        c = np.asarray(l.classification)
        if (c == 2).any(): x, y, z = x[c == 2], y[c == 2], z[c == 2]
    i = ((x - gx0) / RES).astype(int); j = ((y - gy0) / RES).astype(int)
    m = (i >= 0) & (i < W) & (j >= 0) & (j < H)
    k = j[m] * W + i[m]
    S += np.bincount(k, z[m], W * H); C += np.bincount(k, None, W * H)
    print(os.path.basename(f), len(z), flush=True)
G = np.where(C > 0, S / np.maximum(C, 1), np.nan).reshape(H, W)
print('pokryto', round(float(np.isfinite(G).mean()) * 100, 1), '%', flush=True)
# díry (budovy, voda, mimo listy do 300 m) doplnit průměrem sousedů, postupně od okraje díry
known = np.isfinite(G)
for it in range(60):
    if known.all(): break
    Z = np.where(known, G, 0.0); K = known.astype(float)
    pz = np.pad(Z, 1); pk = np.pad(K, 1)
    s9 = sum(pz[1 + a:H + 1 + a, 1 + b:W + 1 + b] for a in (-1, 0, 1) for b in (-1, 0, 1))
    k9 = sum(pk[1 + a:H + 1 + a, 1 + b:W + 1 + b] for a in (-1, 0, 1) for b in (-1, 0, 1))
    new = ~known & (k9 > 0)
    G[new] = s9[new] / k9[new]; known = known | new
np.savez_compressed('build/dmr_grid.npz', g=G.astype(np.float32), x0=gx0, y0=gy0, res=RES)
print('hotovo', W, 'x', H, 'nevyplněno', int((~known).sum()))
