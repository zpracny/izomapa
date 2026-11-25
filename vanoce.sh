#!/bin/sh
# Vánoční výzdoba (assets/vanoce.json) a led na rybnících (mesto.json "rybniky") jako samostatné průhledné vrstvy.
# Přerenderuje jen čtverce, kde něco je (scéna + vrstvy xmas_winter, xmas_autumn, led), a přestaví web.
# ./vanoce.sh            po každé změně výzdoby nebo rybníků (pár minut)
# Prohlížeč vrstvu zapíná podle data (od/do ve vanoce.json), led podle administrace (/admin, zamrzlé rybníky).
set -e
cd "$(dirname "$0")"
if [ -f .venv/bin/activate ]; then . .venv/bin/activate; else . .venv/Scripts/activate; fi
export PYTHONUTF8=1
dir() { if [ "$1" = "0,0" ]; then echo data; else echo data_c$(echo $1 | tr ',' '_'); fi; }
# čtverce s výzdobou / rybníkem: "i,j:varianty"
PLAN=$(python - <<'EOF'
import geo
from geo import MESTO, HALF, to_local, CHUNKS, chunk_center
def chunks_of(lat, lon, r=0):
    x, y = to_local(lon, lat)
    out = set()
    for c in CHUNKS:
        cx, cy = chunk_center(c)
        if abs(x - cx) <= HALF + r and abs(y - cy) <= HALF + r: out.add(c)
    return out
plan = {}
V = MESTO
for la, lo in (V.get('vanocni_strom') or []): [plan.setdefault(c, set()).add('xmas') for c in chunks_of(la, lo)]
for k in (V.get('kluziste') or []) + (V.get('vanocni_stanky') or []) + (V.get('vanocni_svetla') or []): [plan.setdefault(c, set()).add('xmas') for c in chunks_of(k['lat'], k['lon'], 20)]
for k in V.get('rybniky') or []: [plan.setdefault(c, set()).add('led') for c in chunks_of(k['lat'], k['lon'], 300)]
print(' '.join(f"{c[0]},{c[1]}:" + ','.join(sorted(v)) for c, v in sorted(plan.items())))
EOF
)
echo "čtverce: $PLAN"
KEEP=""
for p in $PLAN; do
  c=${p%%:*}; v=${p#*:}
  python prep.py $(dir $c) $c > /dev/null 2>&1 && echo "scéna $c"
  VAR=""
  case $v in *xmas*) VAR="$VAR xmas_winter xmas_autumn";; esac
  case $v in *led*) VAR="$VAR led";; esac
  ./render_chunk.sh $c $VAR
  D=$( [ "$c" = "0,0" ] && echo build || echo build/c$(echo $c | tr ',' '_') )
  S=$( [ "${IZO_POHLED:-0}" = 0 ] || echo _p$IZO_POHLED )
  OK=""; for x in $VAR; do ls $D/tiles_$x$S/*.png > /dev/null 2>&1 && OK="$OK $x"; done      # bez dlaždic (nic ve čtverci) = bez vrstvy
  [ -z "$OK" ] && continue
  if [ "$c" = "0,0" ]; then python dzi.py $OK; else python dzi.py --chunk $c $OK; fi
  KEEP="$KEEP $c:$(echo $OK | tr ' ' ',')"
done
# z tiles.json pryč vrstvy čtverců, kde už výzdoba / rybník není
python - $KEEP <<'EOF'
import json, sys
keep = {a.split(':')[0]: set(a.split(':')[1].split(',')) for a in sys.argv[1:]}
from geo import SITE
t = json.load(open(f'{SITE}/tiles.json'))
def clean(d, key):
    for v in ('xmas_winter', 'xmas_autumn', 'led'):
        if v in d and v not in keep.get(key, set()): del d[v]; print('odstraněno', key, v)
clean(t, '0,0')
for name, ch in t.get('chunks', {}).items(): clean(ch, f"{ch['chunk'][0]},{ch['chunk'][1]}")
json.dump(t, open(f'{SITE}/tiles.json', 'w'))
EOF
if [ -z "${IZO_POHLED:-}" ]; then                             # otočené pohledy (./postav_pohledy.sh), jsou-li
  for d in site/p1 site/p2 site/p3; do [ -f $d/tiles.json ] && IZO_POHLED=${d#site/p} ./vanoce.sh > /dev/null; done
  python build_html.py
  echo "Hotovo. Nasazení: npx wrangler deploy"
fi
