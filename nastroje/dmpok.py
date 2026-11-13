# DMP OK (ČÚZK, CC BY 4.0): model povrchu z obrazové korelace, rastr 0,5 m. Stáhne listy pro dominanty s "odlitek": true
# (assets/dominanty.json) do build/dmpok/; odlitek.py z nich bere skutečný tvar střech.   python nastroje/dmpok.py [--dominanty | --vse]  (--dominanty = listy pro všechny dominanty, kvůli měření výšek)
import json, os, re, subprocess, sys; sys.path.insert(0, '.')
import geo
D = 'build/dmpok/'; os.makedirs(D, exist_ok=True)
A = D + 'atom.xml'; UA = ['-A', 'izomapa/1.0']
if not os.path.exists(A): subprocess.run(['curl', '-sL', '-m', '300', *UA, '-o', A, 'https://atom.cuzk.gov.cz/DMPOK-SJTSK-TIFF/DMPOK-SJTSK-TIFF.xml'], check=True)
sheets = []
for e in open(A, encoding='utf8').read().split('<entry>')[1:]:
    p = re.search(r'<georss:polygon>(.*?)<', e); k = re.search(r'DMPOK-SJTSK-TIFF_([A-Z0-9]+)\.xml', e)
    if p and k:
        v = list(map(float, p.group(1).split())); sheets.append((k.group(1), min(v[0::2]), min(v[1::2]), max(v[0::2]), max(v[1::2])))
if '--vse' in sys.argv:        # listy přes celou mapu (kvůli nastroje/vysky_ok.py), ~65 MB na list
    import numpy as np
    X0, Y0, X1, Y1 = geo.extent(geo.MARGIN + 100)
    ll = [geo.to_lonlat(x, y) for x in np.linspace(X0, X1, 15) for y in np.linspace(Y0, Y1, 15)]
    lo0, lo1, la0, la1 = min(p[0] for p in ll), max(p[0] for p in ll), min(p[1] for p in ll), max(p[1] for p in ll)
    use = sorted({n for n, a0, o0, a1, o1 in sheets if a1 > la0 and a0 < la1 and o1 > lo0 and o0 < lo1})
else:
    doms = [d for d in json.load(open('assets/dominanty.json', encoding='utf-8')) if d.get('spec', {}).get('odlitek') or '--dominanty' in sys.argv]
    m = 0.0012          # ~100 m kolem bodu dominanty
    use = sorted({n for d in doms for n, a0, o0, a1, o1 in sheets if a1 > d['lat'] - m and a0 < d['lat'] + m and o1 > d['lon'] - m * 1.5 and o0 < d['lon'] + m * 1.5})
print('listů DMP OK', len(use), flush=True)
for n in use:
    if os.path.exists(f'{D}{n}.tif'): continue
    subprocess.run(['curl', '-sL', '-m', '900', *UA, '-o', f'{D}{n}.zip', f'https://openzu.cuzk.gov.cz/opendata/DMPOK-TIFF/epsg-5514/{n}.zip'], check=True)
    subprocess.run(['unzip', '-oq', f'{D}{n}.zip', '-d', D], check=True); os.remove(f'{D}{n}.zip'); print(n, flush=True)
