import numpy as np
"""Z web/app.html a mesto.json vyrobí site/index.html (texty, meta, sitemap).
Pokud existuje složka obce/*.json, vyrobí pro každou obec i site/index_<obec>.html a site/obce/<obec>/og.jpg."""
import html, json, os, re
from urllib.parse import urljoin
from PIL import Image
import geo
from geo import MESTO


def og_obrazek(out='site/og.jpg', W=1200, H=630, dolu=1, latlon=None):
    """náhled pro sdílení (og:image) 1200×630: výřez středu města z letních dlaždic (o úroveň menší než plné rozlišení)"""
    t = json.load(open('site/tiles.json')); base = t['base']
    x, y = geo.to_local(float(latlon[1]), float(latlon[0])) if latlon else (0, 0)
    x, y = float(np.ravel(x)[0]), float(np.ravel(y)[0])        # to_local vrací pole i pro jeden bod
    k = 2 ** dolu; vx, vy, _ = geo.view(x, y, 0)
    img = Image.new('RGB', (W, H), (27, 33, 48))
    # výřez se skládá ze všech čtverců (střed může ležet u hrany čtverce); vzdálenější čtverce se kreslí dřív
    sady = [t['summer']] + [c['summer'] for c in (t.get('chunks') or {}).values() if c.get('summer')]
    for s in sorted(sady, key=lambda q: q.get('y1', base['y1']), reverse=True):
        I = s['Image']; url = 'site/' + I['Url'].rstrip('/'); T = int(I['TileSize'])
        if not os.path.isdir(url): continue
        lv = max(int(n) for n in os.listdir(url) if n.isdigit()) - dolu
        cx, cy = (vx - s.get('x0', base['x0'])) / base['mpp'] / k, (s.get('y1', base['y1']) - vy) / base['mpp'] / k
        x0, y0 = int(round(cx - W / 2)), int(round(cy - H / 2))
        for i in range(max(0, x0 // T), (x0 + W) // T + 1):
            for j in range(max(0, y0 // T), (y0 + H) // T + 1):
                f = f'{url}/{lv}/{i}_{j}.webp'
                if os.path.exists(f):
                    q = Image.open(f).convert('RGBA'); img.paste(q, (i * T - x0, j * T - y0), q)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    img.save(out, quality=85)


SABLONA = open('web/app.html', encoding='utf-8').read()
E = lambda t: html.escape(t or '', quote=True)


def postav_stranku(M, html_out='site/index.html', og_cesta='og.jpg', je_obec=False, page_url=None):
    site_url = (M.get('url') or '').rstrip('/')          # plná adresa webu (kvůli og:image a sitemap); prázdné = bez nich
    page_url = page_url or (site_url + '/' if site_url else '')
    obrazek_url = urljoin(site_url + '/', og_cesta) if site_url else ''
    mhd = M.get('mhd') or {}
    pohled = M.get('pohled')
    strom = M.get('vanocni_strom')
    if isinstance(strom, list) and strom and isinstance(strom[0], list): strom = strom[0]      # víc stromů: náhled podle prvního
    fill = {
        'TITULEK': E(M['titulek']), 'POPIS': E(M['popis']), 'MESTO': E(M['nazev']), 'H1_A': E(M['h1'][0]), 'H1_B': E(M['h1'][1]),
        'PODTITUL': E(M['podtitul']),
        'HLASENI': 'true' if M.get('hlaseni') else 'false',
        'FOTKY': 'true' if M.get('hlaseni') and M.get('fotky') else 'false',   # fotky k hlášení (R2, hlaseni/worker.js)
        'VITR': 'true' if M.get('vitr') else 'false',
        'POCASI': 'true' if M.get('pocasi') else 'false',
        'POHLED': json.dumps(pohled if isinstance(pohled, list) and len(pohled) >= 2 else None),
        # autor mapy města: "autor": {"jmeno", "url" (nepovinně), "text" (nepovinně, např. „Mapu Příbrami připravil“)}
        'AUTOR': (lambda a: f'<p>{E(a.get("text") or "Mapu připravil")} ' + (f'<a href="{E(a["url"])}" target="_blank" rel="noopener">{E(a["jmeno"])}</a>' if a.get('url') else E(a['jmeno'])) + '.</p>')(M['autor']) if isinstance(M.get('autor'), dict) and M['autor'].get('jmeno') else '',
        'DOMU_CELEK': 'true' if M.get('domu_celek') else 'false',
        'STROM': json.dumps(strom if isinstance(strom, list) and len(strom) == 2 and all(isinstance(v, (int, float)) for v in strom) else None),   # seznam stromů kreslí overlay.json
        'XMAS_LL': json.dumps((lambda v: v if v and isinstance(v[0], list) else [v] if v else [])(M.get('vanocni_strom'))),   # vánoční stromy [[lat, lon], ...]
        'KLUZISTE': json.dumps(M.get('kluziste') or []),
        'STANKY': json.dumps(M.get('vanocni_stanky') or []),
        'VANOCE': json.dumps(M.get('vanoce') or None),                 # termín vánoční vrstvy {"od": "11-11", "do": "01-06"} (assets/vanoce.json)
        'RYBNIKY': json.dumps([{'nazev': r['nazev'], 'lat': r['lat'], 'lon': r['lon']} for r in M.get('rybniky') or []], ensure_ascii=False),
        'OBEC': json.dumps(M.get('nazev') if je_obec else None, ensure_ascii=False),
        'VLAK': json.dumps({'vychozi': (M.get('vlak') or {}).get('vychozi', 'regionova') if isinstance(M.get('vlak'), dict) else M.get('vlak', 'regionova'), 'linky': M['vlak'].get('linky', {}) if isinstance(M.get('vlak'), dict) else {}}),
        'DOPRAVA_ZDROJ': ', intenzity dopravy © <a href="https://www.rsd.cz/silnice-a-dalnice/scitani-dopravy" target="_blank" rel="noopener">ŘSD ČR</a> (Celostátní sčítání dopravy)' if M.get('doprava') else '',
        'RUIAN_ZDROJ': ', typy budov z RÚIAN' if os.path.exists('assets/ruian_budovy.json') else '',
        'VITR_ZDROJ': ', ' + ('počasí a vítr' if M.get('pocasi') and M.get('vitr') else 'počasí' if M.get('pocasi') else 'vítr') + ' © <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a> (CC BY 4.0)' if M.get('vitr') or M.get('pocasi') else '',
        'MHD_ZDROJ': f', jízdní řády MHD © <a href="{E(mhd["zdroj_url"])}" target="_blank" rel="noopener">{E(mhd["zdroj"])}</a>'
                     if mhd.get('gtfs') and mhd.get('zdroj') else '',
    }
    app = re.sub(r'\{\{(\w+)\}\}', lambda m: fill[m.group(1)], SABLONA)
    og = f'''<meta property="og:image" content="{E(obrazek_url)}">
<meta property="og:url" content="{E(page_url)}">
<link rel="canonical" href="{E(page_url)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{E(obrazek_url)}">
''' if site_url else ''
    LD = json.dumps({'@context': 'https://schema.org', '@type': 'WebApplication', 'name': M['titulek'], 'description': M['popis'],
                     'inLanguage': 'cs', 'applicationCategory': 'TravelApplication', 'operatingSystem': 'Web',
                     'spatialCoverage': {'@type': 'Place', 'name': M['nazev']},
                     'isBasedOn': ['https://www.openstreetmap.org/', 'https://overturemaps.org/', 'https://geoportal.cuzk.cz/']},
                    ensure_ascii=False)
    head = f'''<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta property="og:title" content="{E(M['titulek'])}">
<meta property="og:description" content="{E(M['popis'])}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{E(M['titulek'])}">
<meta property="og:locale" content="cs_CZ">
{og}<script type="application/ld+json">{LD}</script>
<style>:root{{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}}body{{margin:0;font:14px system-ui}}[hidden]{{display:none!important}}</style>
'''
    body_start = app.index('</style>') + len('</style>')
    page = head + app[:body_start] + '\n</head>\n<body>\n' + app[body_start:] + '\n</body>\n</html>\n'
    open(html_out, 'w', encoding='utf-8').write(page)
    print(html_out, len(page))
    # og:image: vyrobí se jednou ze středu města/obce; vlastní soubor (1200×630) se nepřepisuje
    og_out = f'site/{og_cesta}'
    latlon = (pohled[:2] if isinstance(pohled, list) and len(pohled) >= 2 else strom if isinstance(strom, list) and len(strom) == 2 else None)
    if (site_url or je_obec) and not os.path.exists(og_out) and os.path.exists('site/tiles.json'):
        og_obrazek(og_out, latlon=latlon); print(og_out)


postav_stranku(MESTO)
SITE_URL = (MESTO.get('url') or '').rstrip('/')
open('site/robots.txt', 'w').write('User-agent: *\nAllow: /\n' + (f'Sitemap: {SITE_URL}/sitemap.xml\n' if SITE_URL else ''))
if SITE_URL:
    open('site/sitemap.xml', 'w').write(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{SITE_URL}/</loc></url></urlset>\n')
if MESTO.get('hlaseni'):                              # volitelná administrace hlášení (server v hlaseni/)
    open('site/admin.html', 'w', encoding='utf-8').write(open('hlaseni/admin.html', encoding='utf-8').read()
        .replace('{{RYBNIKY}}', json.dumps([r['nazev'] for r in MESTO.get('rybniky') or []], ensure_ascii=False))
        .replace('{{VANOCE}}', json.dumps(MESTO.get('vanoce') or None)))

if os.path.isdir('obce'):
    for f in sorted(os.listdir('obce')):
        if not f.endswith('.json'): continue
        slug = f[:-5]
        obec = json.load(open(f'obce/{f}', encoding='utf-8'))
        obec_url = obec.get('url') or (urljoin(SITE_URL + '/', f'index_{slug}.html') if SITE_URL else None)
        postav_stranku({**MESTO, **obec, 'url': SITE_URL}, html_out=f'site/index_{slug}.html', og_cesta=f'obce/{slug}/og.jpg', je_obec=True, page_url=obec_url)
