#!/bin/sh
# Otočené pohledy mapy pro tlačítko otáčení v prohlížeči: render, dlaždice, vánoční vrstvy, náhled a data webu do site/pN/.
# Spouštět až po ./postav.sh (výchozí pohled od JZ, scény v build/ jsou na pohledu nezávislé). Pohled trvá zhruba jako ./postav.sh render.
# ./postav_pohledy.sh        pohled 2 (od severovýchodu, druhá strana města)
# ./postav_pohledy.sh 1 2 3  od SZ, SV a JV (všechny čtyři strany; pozor na limit 20 000 souborů na Cloudflare zdarma)
# Další render (./postav.sh render, pamatky/render_mapa.sh) už hotové pohledy přerenderuje sám u změněných čtverců.
set -e
cd "$(dirname "$0")"
if [ -f .venv/bin/activate ]; then . .venv/bin/activate; else . .venv/Scripts/activate; fi
export PYTHONUTF8=1
PAR=${PAR:-2}
CH=$(python -c "import geo; print(' '.join(f'{i},{j}' for i, j in sorted(geo.CHUNKS)))")
for P in ${*:-2}; do
  export IZO_POHLED=$P
  T0=$(date +%s)
  rm -rf site/p$P/tiles site/p$P/tiles.json && mkdir -p site/p$P/tiles
  echo $CH | tr ' ' '\n' | xargs -P "$PAR" -I{} sh -c '
    c={}; L=build/pohled'$P'_$(echo $c | tr "," "_").log
    ./render_chunk.sh $c > $L 2>&1 || { echo "CHYBA pohled '$P' $c (viz $L)"; exit 255; }
    if [ "$c" = "0,0" ]; then python dzi.py >> $L 2>&1; else python dzi.py --chunk $c >> $L 2>&1; fi || { echo "CHYBA dzi pohled '$P' $c (viz $L)"; exit 255; }
    echo "pohled '$P' hotovo $c"'
  ./vanoce.sh > build/pohled${P}_vanoce.log 2>&1 || { echo "CHYBA vánoce pohled $P (viz build/pohled${P}_vanoce.log)"; exit 1; }
  python preview.py
  python overlay.py | tail -1
  echo "pohled $P hotový za $(( ($(date +%s) - T0) / 60 )) min"
done
unset IZO_POHLED
python set_status.py hotovo
python build_html.py
echo "Hotovo. Otočené pohledy jsou v site/p*/, prohlížeč ukáže tlačítko otáčení."
