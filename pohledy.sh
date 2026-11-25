#!/bin/sh
# Udržuje otočené pohledy mapy (site/p1..p3, postavené ./postav_pohledy.sh) v souladu s výchozím pohledem:
# ./pohledy.sh ctverec 0,-1 [varianty]   přerenderuje čtverec a jeho dlaždice v každém existujícím otočeném pohledu
# ./pohledy.sh web                       náhled a klikací vrstva (overlay) v každém existujícím otočeném pohledu
# Volají ho render_ctverec.sh, pamatky/render_mapa.sh a postav.sh; bez otočených pohledů nedělá nic.
set -e
cd "$(dirname "$0")"
co=$1; shift
for d in site/p1 site/p2 site/p3; do
  [ -f $d/tiles.json ] || continue
  export IZO_POHLED=${d#site/p}
  if [ "$co" = ctverec ]; then
    C=$1; shift
    ./render_chunk.sh $C "$@"
    if [ "$C" = "0,0" ]; then python dzi.py "$@"; else python dzi.py --chunk $C "$@"; fi
    set -- $C "$@"
  elif [ "$co" = web ]; then
    python preview.py > /dev/null && python overlay.py | tail -1
  fi
done
