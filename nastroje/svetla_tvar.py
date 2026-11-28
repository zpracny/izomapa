"""Tvary světelných soch z řetězů (assets/vanoce.json "svetla", "typ": koule | labut | venec).

Socha = seznam čar {'c': [r, g, b] barva drátu ve dne, 'w': tloušťka m, 'l': barva světýlek, 'p': [[dx, dy, z], …]};
'w': 0 = vyplněná plocha (vějíř z prvního bodu, bez světýlek), aby socha z hustých řetězů nebyla v pixel artu jen pavučina.
(dx východ, dy sever v metrech od středu sochy, z nad terénem). Stejné čáry kreslí render (prep.py -> scene.glows,
render.html) i prohlížeč (build_html.py -> SVETLA, světýlka v 84-kresleni-vozidel.js), takže si odpovídají.
Typ "fontana" (výchozí, bez čar) kreslí render.html a prohlížeč po svém.
"""
import math

ZLATA, BILA, ZELENA = [1.0, 0.90, 0.60], [0.95, 0.98, 1.0], [0.16, 0.30, 0.17]
ZLATA_PL, BILA_PL = [0.84, 0.68, 0.38], [0.70, 0.80, 0.92]       # výplň mezi řetězy (tmavší než dráty)


def _cara(p, c, w, l):
    return {'c': c, 'w': w, 'l': l, 'p': [[round(x, 2), round(y, 2), round(z, 2)] for x, y, z in p]}


def _plocha(p, c):
    return _cara(p, c, 0, None)


def _elipsa(cx, cy, z, rx, ry, n=16):
    return [(cx + rx * math.cos(u * 2 * math.pi / n), cy + ry * math.sin(u * 2 * math.pi / n), z) for u in range(n)]


def _krivka(body, n=8):
    """Catmull-Rom přes body (hladká čára)."""
    out = []
    P = [body[0]] + list(body) + [body[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in range(3)))
    out.append(tuple(body[-1]))
    return out


def koule(r=1.5, z0=0.0):
    zc = z0 + r
    cary = [_plocha(_elipsa(0, 0, zc + dz, math.sqrt(r * r - dz * dz), math.sqrt(r * r - dz * dz)), BILA_PL)   # plná koule z vrstev
            for dz in [r * (k / 7 - 1) * 0.97 for k in range(15)]]
    r *= 1.04                                             # dráty těsně nad povrchem
    for k in range(6):                                    # poledníky (silné dráty, ať je síť v pixel artu vidět)
        a = k * math.pi / 6
        cary.append(_cara([(math.cos(a) * r * math.sin(t * math.pi / 24), math.sin(a) * r * math.sin(t * math.pi / 24), zc + r * math.cos(t * math.pi / 24))
                           for t in range(25)], BILA, 0.22, '#e8f4ff'))
    for k in range(1, 5):                                 # rovnoběžky
        t = k * math.pi / 5; rr, z = r * math.sin(t), zc + r * math.cos(t)
        cary.append(_cara([(rr * math.cos(u * math.pi / 16), rr * math.sin(u * math.pi / 16), z) for u in range(33)], BILA, 0.22, '#e8f4ff'))
    return cary


def labut(s=1.0, z0=0.0):
    """Labuť se zdviženými křídly a esovitým krkem; x dopředu (k hlavě), y do boku, z nahoru."""
    cary, pl = [], []
    for k in range(7):                                    # plné tělo z vodorovných vrstev
        dz = (k / 6 * 2 - 1) * 0.55; q = math.sqrt(1 - (dz / 0.6) ** 2)
        pl.append(_elipsa(-0.2, 0, 0.75 + dz, 1.4 * q, 0.8 * q))
    def tel(x, u):                                        # bod na povrchu těla: x podél, u úhel kolem osy
        q = max(0.0, 1 - ((x + 0.2) / 1.45) ** 2)
        hy, hz = 0.85 * math.sqrt(q), 0.6 * math.sqrt(q)
        z = 0.75 + hz * math.sin(u) + (max(0.0, -0.9 - x) * 0.9 if math.sin(u) > -0.3 else 0)   # ocas se zvedá
        return (x, hy * math.cos(u), max(0.05, z))
    for k in range(14):                                   # podélné čáry těla
        u = -math.pi / 2 + k * math.pi / 13 * 2
        cary.append([tel(-1.64 + i * 0.12, u) for i in range(25)])
    for x in (-1.2, -0.7, -0.2, 0.3, 0.8):                # žebra těla
        cary.append([tel(x, u * math.pi / 8) for u in range(17)])
    osa = _krivka([(0.85, 0, 1.0), (1.35, 0, 1.6), (1.3, 0, 2.3), (0.95, 0, 2.85), (1.05, 0, 3.3), (1.45, 0, 3.35), (1.75, 0, 3.0)], 6)
    for k in range(5):                                    # krk a hlava: trubka kolem osy
        a = k * 2 * math.pi / 5
        cary.append([(x + 0.17 * math.cos(a) * 0.6, 0.17 * math.sin(a), z + 0.17 * math.cos(a) * 0.6) for x, y, z in osa])
    for sy in (1, -1):                                    # křídla: obrys a pera od kořene
        obrys = _krivka([(0.25, 0.65, 1.3), (0.45, 1.05, 2.4), (-0.25, 1.35, 3.55), (-1.35, 1.5, 4.1), (-1.65, 1.25, 3.2), (-1.25, 0.95, 2.0), (-0.75, 0.7, 1.3)], 6)
        cary.append([(x, sy * y, z) for x, y, z in obrys])
        pl.append([(-0.25, sy * 0.7, 1.4)] + [(x, sy * y * 0.97, z) for x, y, z in obrys])   # křídlo vyplněné
        for j in range(3, len(obrys) - 3, 2):
            x1, y1, z1 = obrys[j]
            cary.append([(-0.25 + (x1 + 0.25) * t / 6, sy * (0.7 + (y1 - 0.7) * t / 6), 1.4 + (z1 - 1.4) * t / 6) for t in range(7)])
    sk = lambda c: [(x * s, y * s, z0 + z * s) for x, y, z in c]
    return [_plocha(sk(c), ZLATA_PL) for c in pl] + [_cara(sk(c), ZLATA, 0.18, '#ffd98a') for c in cary]


def venec(r=2.0, z0=0.0, svicky=(1.7, 2.3, 1.5, 2.0)):
    """Adventní věnec ze zelených větví se světýlky a čtyřmi svíčkami z bílých řetězů se zlatým plamenem."""
    cary = []
    for dr, dz in ((-0.18, 0.5), (0.18, 0.5), (0, 0.68), (0, 0.36)):
        cary.append(_cara([((r + dr) * math.cos(u * math.pi / 24), (r + dr) * math.sin(u * math.pi / 24), z0 + dz) for u in range(49)], ZELENA, 0.3, '#ffc85a'))
    for i, h in enumerate(svicky):
        a = i * math.pi / 2 + math.pi / 4; cx, cy = r * math.cos(a), r * math.sin(a); rs = 0.28
        for k in range(6):                                # svislé řetězy válce
            b = k * math.pi / 3
            cary.append(_cara([(cx + rs * math.cos(b), cy + rs * math.sin(b), z0 + 0.5 + h * t / 4) for t in range(5)], BILA, 0.22, '#f4f8ff'))
        for t in (0.5, h / 2 + 0.5, h + 0.5):            # obruče
            cary.append(_cara([(cx + rs * math.cos(u * math.pi / 6), cy + rs * math.sin(u * math.pi / 6), z0 + t) for u in range(13)], BILA, 0.12, '#f4f8ff'))
        zt = z0 + h + 0.55
        for ux, uy in ((1, 0), (0, 1)):                   # plamen: dvě zkřížené kapky
            kapka = _krivka([(0, 0, 0), (0.2, 0, 0.18), (0.16, 0, 0.45), (0, 0, 0.72), (-0.16, 0, 0.45), (-0.2, 0, 0.18), (0, 0, 0)], 4)
            cary.append(_cara([(cx + x * ux, cy + x * uy, zt + z) for x, _, z in kapka], ZLATA, 0.1, '#ffcf5a'))
    return cary


def zahon(A=4.0, B=1.7, z0=0.0):
    """Oválný záhon (zakrytá kašna) z jedlových větví posetý modrými světýlky."""
    return [_cara([(A * q * math.cos(u * math.pi / 24), B * q * math.sin(u * math.pi / 24), z0 + 0.05 * (1 - q)) for u in range(49)], ZELENA, 0.45, '#3a5cff')
            for q in (1.0, 0.8, 0.6, 0.4, 0.2)]


def tvar(k):
    """Čáry sochy z položky vanoce.json, otočené o k['a'] (° od východu, kam míří hlava labutě)."""
    t = k.get('typ', 'fontana')
    z0 = k.get('z0', 0.0)
    if t == 'koule': cary = koule(k.get('r', 1.5), z0)
    elif t == 'labut': cary = labut(k.get('s', 1.0), z0)
    elif t == 'venec': cary = venec(k.get('r', 2.0), z0)
    elif t == 'zahon': cary = zahon(k.get('d', 8.0) / 2, k.get('s', 3.4) / 2, z0)
    else: return None
    a = math.radians(k.get('a', 0)); ca, sa = math.cos(a), math.sin(a)
    for c in cary: c['p'] = [[round(x * ca - y * sa, 2), round(x * sa + y * ca, 2), z] for x, y, z in c['p']]
    return cary


def rozmer(cary):
    """(poloměr, výška) sochy pro výběr dlaždic."""
    return (max(math.hypot(x, y) for c in cary for x, y, _ in c['p']), max(z for c in cary for _, _, z in c['p']))
