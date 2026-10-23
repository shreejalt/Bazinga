# How the banner is made

`banner.html` draws one frame of the banner for any time `t` (a 7-second loop: numbered dots, the pencil joining
them, the hand becoming the logo, the name and tagline). `frames.mjs` opens it in headless Chrome and saves every
frame; ffmpeg and gifsicle turn the frames into the GIF:

```bash
npm install playwright
for th in light dark; do
  mkdir -p frames-$th && node frames.mjs "$PWD/banner.html" "$PWD/frames-$th" $th 20
  ffmpeg -framerate 20 -i frames-$th/f%04d.png \
    -vf "fps=15,split[a][b];[a]palettegen=max_colors=40:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" \
    -loop 0 banner-$th.gif
  gifsicle -O3 --lossy=45 banner-$th.gif -o ../banner-$th.gif
done
```
