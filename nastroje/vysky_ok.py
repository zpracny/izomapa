# výšky budov z DMP OK (ČÚZK, rastr 0,5 m) tam, kde je laser DMP 1G nemá nebo se výrazně liší (novostavby, budovy s více výškami
# pod jedním půdorysem): python nastroje/vysky_ok.py  ->  assets/dmp_ok.json (id -> [medián, p90] nad terénem), build/dmp_ok_kontrola.csv
# Jen budovy od 150 m² (u malých kazí měření koruny stromů). prep.py je použije jako doplněk assets/dmp_vysky.json.
import glob, json, os, sys; sys.path.insert(0, '.')
import numpy as np, pyarrow.parquet as pq, shapely, geo, odlitek
from pyproj import Transformer
T = Transformer.from_crs(4326, 5514, always_xy=True)
Z = np.load('build/dmr_grid.npz'); G = Z['g'].astype(float); gx0, gy0, gr = float(Z['x0']), float(Z['y0']), float(Z['res'])
DMP = json.load(open('assets/dmp_vysky.json')) if os.path.exists('assets/dmp_vysky.json') else {}
out, rows, seen = {}, [], set()
for f in sorted(glob.glob('data_c*/building.parquet')) + ['data/building.parquet']:
    for b in pq.read_table(f, columns=['id', 'geometry', 'sources', 'class']).to_pylist():
        if b['id'] in seen or not b['sources'] or not any(s['dataset'] == 'OpenStreetMap' for s in b['sources']): continue
        seen.add(b['id'])
        if b['class'] in ('garage', 'garages', 'carport', 'shed', 'roof', 'greenhouse'): continue
        g = shapely.from_wkb(b['geometry'])
        if g.geom_type != 'Polygon': continue
        x0, y0, x1, y1 = g.bounds; JX0, JY0 = T.transform(x0, y0); JX1, JY1 = T.transform(x1, y1)
        if (JX1 - JX0) * (JY1 - JY0) < 150: continue
        X, Y = np.meshgrid(np.arange(JX0, JX1, 0.5), np.arange(JY0, JY1, 0.5))
        p = shapely.transform(g, lambda c: np.column_stack(T.transform(c[:, 0], c[:, 1])))
        if p.area < 150: continue
        m = shapely.contains_xy(p.buffer(-1.0), X, Y)
        if m.sum() < 200: continue
        z = odlitek.dsm(X[m], Y[m]); gi = G[np.clip(np.floor((Y[m] - gy0) / gr).astype(int), 0, G.shape[0] - 1), np.clip(np.floor((X[m] - gx0) / gr).astype(int), 0, G.shape[1] - 1)]
        h = (z - gi)[np.isfinite(z)]
        if len(h) < 200: continue
        med, p90 = float(np.median(h)), float(np.percentile(h, 90)); old = DMP.get(b['id'])
        if med < 2.5: continue
        if old is None or abs(old[0] - med) > 4:
            out[b['id']] = [round(med, 1), round(p90, 1)]
            c = g.centroid; rows.append((round(abs((old[0] if old else 3.3) - med), 1), b['id'], round(p.area), old, round(med, 1), round(p90, 1), round(c.y, 6), round(c.x, 6)))
json.dump(out, open('assets/dmp_ok.json', 'w'))
rows.sort(reverse=True)
open('build/dmp_ok_kontrola.csv', 'w').write('rozdil;id;plocha;dmp1g;median;p90;lat;lon\n' + '\n'.join(';'.join(map(str, r)) for r in rows))
print('budov prověřeno', len(seen), 'doplněno nebo opraveno', len(out), 'z toho bez laseru', sum(1 for r in rows if r[3] is None))
