"""Služby v budovách z otevřených registrů -> assets/sluzby.json (lékaři, lékárny, školy, pošty a Balíkovny, dobíjecí stanice).

  python nastroje/sluzby.py            stáhne registry do build/sluzby/ (jen chybějící) a zapíše assets/sluzby.json
  python nastroje/sluzby.py --znovu    stáhne všechno znovu (registry se mění měsíčně až denně)

Zdroje (podmínky v "zdroje" výstupu, patička mapy je uvádí přes build_html.py):
  ÚZIS ČR – Národní registr poskytovatelů zdravotních služeb, místa poskytování (CC BY 4.0), adresa jako kód RÚIAN + GPS
  MŠMT – Rejstřík škol a školských zařízení (CC0), místa vzdělávání s kódem RÚIAN
  SÚKL – seznam lékáren (podmínky užití SÚKL: uvést zdroj), bez polohy: k lékárně z NRPZS (stejné IČO a ulice) doplní název a pohotovost
  Česká pošta – pobočky a Balíkovny (napostu.ceskaposta.cz), WGS84
  MPO – seznam veřejně přístupných dobíjecích stanic (xlsx, odkaz na aktuální soubor ze stránky MPO), WGS84
Poloha: kód adresního místa RÚIAN -> bod adresy z Overture (data_all/address.parquet, record_id = kód RÚIAN), jinak GPS registru.
Bere se jen to, co leží ve čtvercích mapy. Výstup: {"zdroje": [...], "sluzby": [[lat, lon, kat, název, detail], ...]};
k budovám je přiřadí overlay.py (bod v půdorysu, lékaři a školy i do 8 m od budovy), zbytek kreslí prohlížeč jako značky.
"""
import csv, json, os, re, sys, urllib.request, zipfile, xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import geo, shapely, pyarrow.parquet as pq

D = 'build/sluzby'
UA = {'User-Agent': 'izomapa-sluzby/1.0'}
URL = {
    'nrpzs.csv': 'https://datanzis.uzis.gov.cz/data/NR-01-NRPZS/NR-01-06/Otevrena-data-NR-01-06-nrpzs-mista-poskytovani-zdravotnich-sluzeb.csv',
    'sukl.csv': 'https://opendata.sukl.gov.cz/soubory/NKOD/LEKARNY/nkod_lekarny_seznam.csv',
    'posta.xml': 'http://napostu.ceskaposta.cz/vystupy/balikovny.xml',
}
MSMT_KRAJ = {   # krajské soubory rejstříku škol (menší než celá ČR); jinde celá ČR
    'Středočeský kraj': 'https://lkod-ftp.msmt.gov.cz/00022985/3d7ec2fb-4d53-46c4-a80e-542487c989b3/RSSZ-Stredocesky-kraj.jsonld',
}
MSMT_CR = 'https://lkod-ftp.msmt.gov.cz/00022985/88a7c12b-6084-4e47-8b50-46097c6e683f/RSSZ-cela-CR.jsonld'
MPO_STRANKA = 'https://mpo.gov.cz/cz/energetika/statistika/statistika-a-evidence-cerpacich-a-dobijecich-stanic/seznam-verejne-pristupnych-dobijecich-stanic--280706/'
ZDROJE = [
    {'nazev': 'ÚZIS ČR, Národní registr poskytovatelů zdravotních služeb', 'licence': 'CC BY 4.0',
     'autori': 'Zelinková H., Klimeš D., Šnábl I., Májek T., Jarkovský J., Klika P., Vičar M., Jochcová M., Komenda M., Dušek L.',
     'url': 'https://nrpzs.uzis.cz/'},
    {'nazev': 'MŠMT, Rejstřík škol a školských zařízení', 'licence': 'CC0', 'url': 'https://rejstriky.msmt.cz/'},
    {'nazev': 'SÚKL, seznam lékáren', 'licence': 'podmínky užití otevřených dat SÚKL', 'url': 'https://opendata.sukl.gov.cz/podminky-uziti-otevrenych-dat'},
    {'nazev': 'Česká pošta, pobočky a Balíkovny', 'url': 'https://www.ceskaposta.cz/ke-stazeni/zakaznicke-vystupy'},
    {'nazev': 'MPO, seznam veřejně přístupných dobíjecích stanic', 'url': MPO_STRANKA},
]


def stahni(nazev, url, znovu):
    f = f'{D}/{nazev}'
    if os.path.exists(f) and not znovu: return f
    print('stahuji', url, flush=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r, open(f + '.tmp', 'wb') as o:
        while (b := r.read(1 << 20)): o.write(b)
    os.replace(f + '.tmp', f)
    return f


def main():
    znovu = '--znovu' in sys.argv
    os.makedirs(D, exist_ok=True)
    F = {k: stahni(k, u, znovu) for k, u in URL.items()}
    kraj = (geo.MESTO.get('kraj') or 'Středočeský kraj')
    F['msmt.jsonld'] = stahni('msmt.jsonld', MSMT_KRAJ.get(kraj, MSMT_CR), znovu)
    if znovu or not os.path.exists(f'{D}/mpo.xlsx'):
        html = urllib.request.urlopen(urllib.request.Request(MPO_STRANKA, headers=UA), timeout=60).read().decode('utf-8', 'replace')
        m = re.findall(r'href="([^"]*Seznam_ver[^"]*\.xlsx)"', html)
        if m: stahni('mpo.xlsx', urllib.request.urljoin(MPO_STRANKA, m[0]), True)
        else: print('MPO: odkaz na xlsx na stránce nenalezen, nabíječky vynechány')
    F['mpo.xlsx'] = f'{D}/mpo.xlsx'

    CH = {tuple(c) for c in geo.CHUNKS}
    def na_mape(lon, lat):
        return tuple(geo.chunk_of(*geo.to_local(lon, lat))) in CH
    A = {}               # kód RÚIAN -> (lon, lat)
    for r in pq.read_table('data_all/address.parquet', columns=['geometry', 'sources']).to_pylist():
        g = shapely.from_wkb(r['geometry']); k = (r['sources'] or [{}])[0].get('record_id')
        if k: A[str(k)] = (g.x, g.y)
    out = []
    def add(kat, nazev, detail, lon, lat, ruian=None):
        if ruian and str(ruian) in A: lon, lat = A[str(ruian)]
        if lon is None or not na_mape(lon, lat): return
        out.append([round(lat, 6), round(lon, 6), kat, nazev.strip(), (detail or '').strip()])
    def hezky(s):     # „MUDr. TEREZA BARTOŠOVÁ“ -> „MUDr. Tereza Bartošová“ (zkratky typu s.r.o., MUDr. zůstanou)
        return ' '.join(w.capitalize() if w.isupper() and len(w) > 2 and w.isalpha() else w for w in s.split())

    # 1 ÚZIS: druh zařízení -> kategorie (laboratoře bez veřejného vstupu vynechány)
    DRUH = [('prakt. lékaře pro děti', 'Dětský lékař'), ('všeob. prakt. lékaře', 'Praktický lékař'), ('stomatologická laboratoř', None),
            ('stomatologa', 'Zubař'), ('gynekologa', 'Gynekologie'), ('lékaře specialisty', 'Lékař specialista'), ('fyzioterapeuta', 'Fyzioterapie'),
            ('Lékárna', 'Lékárna'), ('Oční optika', 'Oční optika'), ('Nemocnice', 'Nemocnice'), ('Poliklinika', 'Poliklinika'),
            ('laboratoř', None), ('Odběrová', 'Odběrové místo'), ('Zdravotnická záchranná', 'Záchranná služba'), ('', 'Zdravotní služby')]
    seen, LEK = set(), []
    for r in csv.DictReader(open(F['nrpzs.csv'], encoding='utf-8')):
        m = re.match(r'POINT\(([\d.]+) ([\d.]+)\)', r['ZZ_GPS'] or '')
        lat, lon = (float(m.group(1)), float(m.group(2))) if m else (None, None)
        if lat is None and r['ZZ_RUIAN_kod'] not in A: continue
        kat = next(k for s, k in DRUH if s in r['ZZ_druh_nazev'])
        if not kat: continue
        nazev = hezky(r['ZZ_nazev'])
        key = (nazev, kat, r['ZZ_RUIAN_kod'])
        if key in seen: continue
        seen.add(key)
        obor = r['ZZ_obor_pece']
        if kat in ('Zdravotní služby', 'Lékař specialista'):          # upřesnění podle oboru péče
            kat = next((k for s, k in [('praktické lékařství pro děti', 'Dětský lékař'), ('Dentální hygien', 'Dentální hygiena'),
                                       ('logoped', 'Logopedie'), ('lékárenství', 'Zdravotnické potřeby')] if s in obor), kat)
        detail = obor if kat in ('Lékař specialista', 'Zdravotní služby', 'Fyzioterapie') else ''
        n0 = len(out)
        add(kat, nazev, detail[:90], lon, lat, r['ZZ_RUIAN_kod'])
        if kat == 'Lékárna' and len(out) > n0: LEK.append((out[-1], r['poskytovatel_ICO'].lstrip('0'), (r['ZZ_ulice'] or '').lower()))
    # 2 SÚKL (bez polohy): k lékárně z NRPZS se stejným IČO a ulicí doplní název a pohotovost
    for r in csv.DictReader(open(F['sukl.csv'], encoding='utf-8-sig')):
        ul = re.sub(r'\s+\d.*$', '', r['ULICE'] or '').strip().lower()
        u = [s for s, ico, uz in LEK if ico == (r['ICO'] or '').lstrip('0') and ul and uz.startswith(ul)]
        if len(u) == 1:
            u[0][3] = hezky(r['NAZEV'].strip()) or u[0][3]
            if (r['POHOTOVOST'] or '').upper() in ('A', 'ANO', '1'): u[0][4] = 'lékárenská pohotovost'
    # 3 MŠMT: školy podle druhu (jídelny, družiny a poradny vynechány); název právnické osoby, místo vzdělávání podle RÚIAN
    SKOLA = {'A00': 'Mateřská škola', 'B00': 'Základní škola', 'C00': 'Střední škola', 'E00': 'Vyšší odborná škola',
             'F10': 'Základní umělecká škola', 'G40': 'Dům dětí a mládeže', 'H10': 'Domov mládeže'}
    seen = set()
    for po in json.load(open(F['msmt.jsonld'], encoding='utf-8'))['list']:
        for s in po.get('skolyAZarizeni') or []:
            kat = SKOLA.get(s.get('druh'))
            if not kat: continue
            for mv in s.get('mistaVyuky') or [{'adresa': po.get('adresa')}]:
                k = str((mv.get('adresa') or {}).get('kodRUIAN') or '')
                if k not in A or (po.get('redIzo'), kat, k) in seen: continue
                seen.add((po.get('redIzo'), kat, k))
                add(kat, po.get('uplnyNazev') or s.get('uplnyNazev') or kat, '', *A[k], k)
    # 4 Česká pošta (SOUR_X_WGS84 = zeměpisná délka)
    TYP = {'pošta': 'Pošta', 'balíkovna partner': 'Balíkovna', 'balíkovna-BOX': 'Balíkovna box'}
    for ev, el in ET.iterparse(F['posta.xml']):
        if not el.tag.endswith('row'): continue
        g = {c.tag.split('}')[-1]: (c.text or '') for c in el}; el.clear()
        kat = TYP.get(g.get('TYP'))
        try: lon, lat = float(g['SOUR_X_WGS84']), float(g['SOUR_Y_WGS84'])
        except (KeyError, ValueError): continue
        if kat: add(kat, g.get('NAZEV', ''), g.get('ADRESA', ''), lon, lat)
    # 5 MPO (xlsx bez dalších knihoven: hlavička na 6.–7. řádku)
    if os.path.exists(F['mpo.xlsx']):
        z = zipfile.ZipFile(F['mpo.xlsx']); N = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
        ss = [''.join(t.text or '' for t in si.iter(N + 't')) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).iter(N + 'si')]
        rows = []
        for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).iter(N + 'row'):
            v = {}
            for c in row.iter(N + 'c'):
                x = c.find(N + 'v')
                v[re.match(r'[A-Z]+', c.get('r')).group()] = (ss[int(x.text)] if c.get('t') == 's' else x.text) if x is not None else ''
            rows.append(v)
        hi = next(i for i, r in enumerate(rows) if any('lat' in str(x).lower() for x in r.values()))
        hdr = {k: ' '.join(filter(None, [rows[hi - 1].get(k, ''), rows[hi].get(k, '')])).lower() for k in set(rows[hi - 1]) | set(rows[hi])}
        col = lambda s: next(k for k, v in hdr.items() if s in v)
        cla, clo, cop, ckw = col('lat'), col('lon'), col('provozovatel'), col('výkon')
        cbody = next((k for k, v in hdr.items() if 'počet' in v and 'bod' in v), None)
        for v in rows[hi + 1:]:
            try: lat, lon = float(v[cla]), float(v[clo])
            except (KeyError, ValueError): continue
            kw = v.get(ckw, ''); kw = f'{float(kw):g} kW' if re.match(r'^[\d.]+$', kw or '') else ''
            body = v.get(cbody, '') if cbody else ''
            add('Dobíjecí stanice', v.get(cop, '') or 'Dobíjecí stanice', ', '.join(filter(None, [kw, f'{body} nabíjecí body' if body else ''])), lon, lat)
    out.sort(key=lambda s: (s[2], s[3]))
    json.dump({'zdroje': ZDROJE, 'sluzby': out}, open('assets/sluzby.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    from collections import Counter
    print('služeb na mapě', len(out)); [print(f'  {n:4} {k}') for k, n in Counter(s[2] for s in out).most_common()]


if __name__ == '__main__':
    main()
