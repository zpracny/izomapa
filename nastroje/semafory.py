# semafory z OpenStreetMap (Overpass, ODbL, bez registrace) -> assets/semafory.json: [[lat, lon, druh]]
# druh "k" = křižovatka (highway=traffic_signals), "p" = přechod pro chodce se semaforem (crossing=traffic_signals)
# prep.py je přiřadí kusům silnic (jako přejezdy), web/app.html je střídá a auta na červenou stojí
# spouštět z kořene repa: python nastroje/semafory.py
import json, subprocess, sys; sys.path.insert(0, '.')
import geo

if __name__ == '__main__':
    x0, y0, x1, y1 = geo.extent(geo.MARGIN + 20)
    lo0, la0 = geo.to_lonlat(x0, y0); lo1, la1 = geo.to_lonlat(x1, y1); b = f'{la0},{lo0},{la1},{lo1}'
    q = f'[out:json][timeout:60];(node["highway"="traffic_signals"]({b});node["crossing"="traffic_signals"]({b}););out;'
    t = None
    for url in ('https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter'):   # záložní server
        try:
            t = subprocess.run(['curl', '-s', '-f', '-m', '120', '-A', 'izomapa-tools/1.0', '--data-urlencode', f'data={q}', url],
                               check=True, capture_output=True, text=True).stdout; break
        except subprocess.CalledProcessError: continue
    if t is None: sys.exit('Overpass nedostupný, zkus to později')
    out = sorted({(round(e['lat'], 6), round(e['lon'], 6), 'k' if e['tags'].get('highway') == 'traffic_signals' and e['tags'].get('crossing') != 'traffic_signals' else 'p')
                  for e in json.loads(t)['elements'] if 'lat' in e})
    json.dump([list(v) for v in out], open('assets/semafory.json', 'w'))
    print('semaforů', len(out), 'na křižovatkách', sum(v[2] == 'k' for v in out), 'u přechodů', sum(v[2] == 'p' for v in out))
