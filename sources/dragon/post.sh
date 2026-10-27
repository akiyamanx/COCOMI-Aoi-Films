#!/bin/bash
# usage: post.sh "<frame pattern>" out.mp4 [crf]
IN="$1"; OUT="$2"; CRF=${3:-18}
VF="[0:v]format=gbrp16le,eq=contrast=1.07:brightness=0.02:gamma=1.06:saturation=1.1,curves=r='0/0 0.5/0.5 1/1':b='0/0.02 0.5/0.5 1/0.97',split[a][b];\
[b]curves=all='0/0 0.7/0 1/0.6',gblur=sigma=20:steps=2,colorchannelmixer=rr=1.0:gg=0.9:bb=0.75[bl];\
[a][bl]blend=all_mode=screen:all_opacity=0.35,vignette=angle=PI/4.5,\
noise=alls=6:allf=t+u,format=yuv420p[out]"
ffmpeg -y -loglevel error -framerate 24 -start_number 0 -i "$IN" -i audio.wav -filter_complex "$VF" -map "[out]" -map 1:a \
  -c:v libx264 -preset slow -crf $CRF -pix_fmt yuv420p -movflags +faststart -c:a aac -b:a 160k -shortest "$OUT"
