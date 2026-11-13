# stáhne fotky z Wikimedia Commons (zmenšené na 1600 px) do fotky/<složka>/ a zapíše licenci a autora do ZDROJE.txt
# python nastroje/commons.py složka "File:Název 1.jpg" "File:Název 2.jpg" …     (pomalu, Commons jinak vrací HTTP 429)
import json, os, re, subprocess, sys, time, urllib.parse
d = 'fotky/' + sys.argv[1]; os.makedirs(d, exist_ok=True); UA = 'izomapa/1.0'
for t in sys.argv[2:]:
    u = 'https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo&iiprop=url|extmetadata&iiurlwidth=1600&format=json&titles=' + urllib.parse.quote(t)
    r = json.loads(subprocess.run(['curl', '-s', '-m', '60', '-A', UA, u], capture_output=True, text=True).stdout or '{}')
    for p in r.get('query', {}).get('pages', {}).values():
        ii = (p.get('imageinfo') or [None])[0]
        if not ii: print('nenalezeno', t); continue
        m = ii.get('extmetadata', {}); f = re.sub(r'[^\w.\-]+', '_', t.split(':', 1)[1])
        subprocess.run(['curl', '-sL', '-m', '120', '-A', UA, '-o', f'{d}/{f}', ii.get('thumburl') or ii['url']])
        lic = m.get('LicenseShortName', {}).get('value', '?'); au = re.sub(r'<[^>]+>', '', m.get('Artist', {}).get('value', '?')).strip()
        if not os.path.exists(f'{d}/ZDROJE.txt'): open(f'{d}/ZDROJE.txt', 'w', encoding='utf8').write('soubor\tlicence\tautor\tstránka na Wikimedia Commons\n')
        open(f'{d}/ZDROJE.txt', 'a', encoding='utf8').write(f"{f}\t{lic}\t{au}\t{ii.get('descriptionurl', '')}\n")
        print(f, lic, au[:40], os.path.getsize(f'{d}/{f}'))
    time.sleep(4)
