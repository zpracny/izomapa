# semafory z OpenStreetMap (Overpass, ODbL, bez registrace) místo Overture: OSM jich má víc (i přechody, crossing=traffic_signals)
# -> assets/semafory.json ve stejném tvaru jako nastroje/semafory.py: [[lat, lon, křižovatka], ...], body do SHLUK_M = jedna křižovatka
# spouštět z kořene repa: python nastroje/semafory_osm.py (pak overlay.py a build_html.py)
import json, math, subprocess, sys; sys.path.insert(0, '.')
import geo

SHLUK_M = 40

x0, y0, x1, y1 = geo.extent(geo.MARGIN)
lo0, la0 = geo.to_lonlat(x0, y0); lo1, la1 = geo.to_lonlat(x1, y1); b = f'{la0},{lo0},{la1},{lo1}'
q = f'[out:json][timeout:60];(node["highway"="traffic_signals"]({b});node["crossing"="traffic_signals"]({b}););out;'
t = None
for url in ('https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter'):   # záložní server
    try:
        t = subprocess.run(['curl', '-s', '-f', '-m', '120', '-A', 'izomapa-tools/1.0', '--data-urlencode', f'data={q}', url],
                           check=True, capture_output=True, text=True).stdout; break
    except subprocess.CalledProcessError: continue
CACHE = 'build/semafory_osm.json'                 # poslední odpověď Overpassu, když je server přetížený
if t is not None: open(CACHE, 'w').write(t)
else:
    try: t = open(CACHE).read(); print('Overpass nedostupný, beru', CACHE)
    except OSError: sys.exit('Overpass nedostupný, zkus to později')
body = []
for e in json.loads(t)['elements']:
    if 'lat' not in e: continue
    x, y = (float(v) for v in geo.to_local(e['lon'], e['lat']))
    k = e['tags'].get('highway') == 'traffic_signals' and e['tags'].get('crossing') != 'traffic_signals'
    if x0 <= x <= x1 and y0 <= y <= y1: body.append((e['lat'], e['lon'], x, y, k))
body = sorted(set(body))
# shluky: křižovatkové body do SHLUK_M spojit; přechod se přidá ke křižovatce do PRECHOD_M, jinak má vlastní cyklus
# (řetěz přechodů podél ulice by jinak splynul v jednu obří „křižovatku“)
PRECHOD_M = 25
rodic = list(range(len(body)))
def koren(i):
    while rodic[i] != i: rodic[i] = rodic[rodic[i]]; i = rodic[i]
    return i
for i in range(len(body)):
    for k in range(i + 1, len(body)):
        d = math.hypot(body[i][2] - body[k][2], body[i][3] - body[k][3])
        if body[i][4] and body[k][4] and d < SHLUK_M: rodic[koren(k)] = koren(i)
for i in range(len(body)):
    if body[i][4]: continue
    kr = [(math.hypot(body[i][2] - q[2], body[i][3] - q[3]), k) for k, q in enumerate(body) if q[4]]
    if kr and min(kr)[0] < PRECHOD_M: rodic[i] = koren(min(kr)[1])
cislo = {}
out = [[round(la, 7), round(lo, 7), cislo.setdefault(koren(i), len(cislo))] for i, (la, lo, _, _, _) in enumerate(body)]
json.dump(out, open('assets/semafory.json', 'w'))
print('semaforů', len(out), 'křižovatek', len(cislo))
