#!/bin/sh
# vyrenderuje jeden čtverec mapy: ./render_chunk.sh 0,-1 [varianty]
# okraje s řezem zeminou se berou ze scény (strany bez souseda), všechny čtverce s průhledným pozadím
# rozlišení (0,2 nebo 0,1 m na pixel) si render.mjs vezme z "rozliseni" v mesto.json
set -e
C=$1; shift; V=${*:-"autumn winter spring summer lights"}
if [ "$C" = "0,0" ]; then D=build; else D=build/c$(echo $C | tr ',' '_'); fi
G="gx0=-1646.34559672906 gy1=988.7958500237901"
# otočení mapy (geo.py POHLED): IZO_POHLED=1..3 renderuje pohled od SZ, SV, JV do tiles_<varianta>_p1..3
P=${IZO_POHLED:-0}; G="$G az=$((225 + 90 * P))"; S=""; [ "$P" = 0 ] || S="_p$P"
for s in $V; do
  # výstup do logu a kontrola návratového kódu node (dřív rozhodoval grep a pád renderu prošel jako HOTOVO)
  if [ "$s" = xmas_winter ] || [ "$s" = xmas_autumn ] || [ "$s" = led ]; then     # průhledné vrstvy (vanoce.sh)
    rm -rf $D/tiles_$s$S
    node render.mjs dir=$D out=$D/tiles_$s$S season=$( [ "$s" = xmas_autumn ] && echo autumn || echo winter ) mode=${s%%_*} alpha=1 $G > $D/render_$s$S.log 2>&1 || { tail -5 $D/render_$s$S.log; echo "RENDER SELHAL $C $s"; exit 1; }
  elif [ "$s" = lights ]; then
    node render.mjs dir=$D out=$D/tiles_lights$S season=autumn mode=lights alpha=1 $G > $D/render_$s$S.log 2>&1 || { tail -5 $D/render_$s$S.log; echo "RENDER SELHAL $C $s"; exit 1; }
  else
    node render.mjs dir=$D out=$D/tiles_$s$S season=$s alpha=1 $G > $D/render_$s$S.log 2>&1 || { tail -5 $D/render_$s$S.log; echo "RENDER SELHAL $C $s"; exit 1; }
  fi
  grep -c dlaždice $D/render_$s$S.log || true          # vrstvy xmas/led můžou mít 0 dlaždic
done
echo HOTOVO $C
