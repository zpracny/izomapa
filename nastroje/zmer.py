# změří budovu pro dominanty.json: python nastroje/zmer.py lat lon
# vypíše budovu z OSM pod bodem (nebo nejbližší do 25 m): rozměry a natočení (minimální obdélník), id,
# a výšky z DMP OK (build/dmpok, rastr 0,5 m) v m n. m.: terén kolem (5. percentil v pásu 3–8 m za obvodem),
# střecha uvnitř (medián = typická výška, 90. percentil ~ hřeben/atika, maximum = věž, komín, strojovna)
import json, math, sys; sys.path.insert(0, '.')
import numpy as np, pandas as pd, shapely
from shapely.geometry import Point
from pyproj import Transformer
import odlitek

la, lo = float(sys.argv[1]), float(sys.argv[2])
T = Transformer.from_crs('EPSG:4326', 'EPSG:5514', always_xy=True)
b = pd.read_parquet('data_all/building.parquet')
G = shapely.from_wkb(b.geometry.values)
p = Point(lo, la)
d = shapely.distance(G, p)
i = int(np.argmin(d))
if d[i] * 72000 > 25: sys.exit('budova do 25 m nenalezena')
g = G[i]
X, Y = T.transform(*np.array(g.exterior.coords).T)
gs = shapely.Polygon(zip(X, Y))
import geo                                   # natočení v místních souřadnicích mapy (skutečný východ/sever), ne v Křovákovi (ten je tu pootočený ~8°)
gl = shapely.Polygon([geo.to_local(x, y) for x, y in g.exterior.coords])
r = gl.minimum_rotated_rectangle; c = list(r.exterior.coords)
e = sorted([(math.dist(c[k], c[k + 1]), math.degrees(math.atan2(c[k + 1][1] - c[k][1], c[k + 1][0] - c[k][0]))) for k in range(2)], reverse=True)
xx, yy = np.meshgrid(np.arange(gs.bounds[0] - 8, gs.bounds[2] + 8, 0.5), np.arange(gs.bounds[1] - 8, gs.bounds[3] + 8, 0.5))
pts = shapely.points(xx.ravel(), yy.ravel())
uvnitr = shapely.contains(gs.buffer(-0.8), pts); okoli = shapely.contains(gs.buffer(8), pts) & ~shapely.contains(gs.buffer(3), pts)
z = odlitek.dsm(xx.ravel(), yy.ravel())
zi, zo = z[uvnitr & ~np.isnan(z)], z[okoli & ~np.isnan(z)]
nm = b.names.iloc[i]
print(json.dumps({'id': b.id.iloc[i], 'nazev': (nm or {}).get('primary') if nm is not None else None, 'trida': b['class'].iloc[i],
                  'plocha_m2': round(gs.area), 'delka_m': round(e[0][0], 1), 'sirka_m': round(e[1][0], 1),
                  'natoceni_delsi_strany_st_od_vychodu': round(e[0][1] % 180 - (180 if e[0][1] % 180 > 90 else 0), 1),
                  'stred': [round(g.centroid.y, 6), round(g.centroid.x, 6)],
                  'teren_m': round(float(np.percentile(zo, 5)), 1) if len(zo) else None,
                  'strecha_median_m': round(float(np.median(zi)), 1) if len(zi) else None,
                  'strecha_p90_m': round(float(np.percentile(zi, 90)), 1) if len(zi) else None,
                  'strecha_max_m': round(float(zi.max()), 1) if len(zi) else None}, ensure_ascii=False))
