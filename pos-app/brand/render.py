"""Regenerate the Android loading-screen images from brand/ring.svg.

    cd pos-app && python3 brand/render.py      # needs: pip install cairosvg pillow

Writes:
  - android/app/src/main/res/drawable*/splash.png   ring + wordmark (pre-Android 12,
    and the window background while the counter page loads)
  - android/app/src/main/res/drawable-nodpi/splash_icon.png   Android 12+ launch icon

www/offline.html carries its own inline copy of the ring; update it by hand if
the SVG changes.
"""
import glob
import io
import os

import cairosvg
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, '..', 'android', 'app', 'src', 'main', 'res')
SVG = os.path.join(HERE, 'ring.svg')


def ring(px: int) -> Image.Image:
    png = cairosvg.svg2png(url=SVG, output_width=px, output_height=px)
    return Image.open(io.BytesIO(png)).convert('RGBA')


def main() -> None:
    word = Image.open(os.path.join(HERE, 'wordmark.png')).convert('RGBA')
    word = word.crop(word.getbbox())

    for path in glob.glob(os.path.join(RES, 'drawable*', 'splash.png')):
        w, h = Image.open(path).size
        m = min(w, h)
        canvas = Image.new('RGBA', (w, h), 'white')
        rs = int(m * 0.42)
        ww = int(m * 0.46)
        wh = int(word.height * ww / word.width)
        gap = int(m * 0.01)
        top = (h - (rs + gap + wh)) // 2 - int(m * 0.03)
        canvas.alpha_composite(ring(rs), ((w - rs) // 2, top))
        canvas.alpha_composite(word.resize((ww, wh), Image.LANCZOS), ((w - ww) // 2, top + rs + gap))
        canvas.convert('RGB').save(path)

    # Android 12+ splash icon: 288dp canvas; only the central circle shows.
    os.makedirs(os.path.join(RES, 'drawable-nodpi'), exist_ok=True)
    icon = Image.new('RGBA', (1152, 1152), (0, 0, 0, 0))
    icon.alpha_composite(ring(760), (196, 196))
    icon.save(os.path.join(RES, 'drawable-nodpi', 'splash_icon.png'))
    print('Loading-screen images regenerated.')


if __name__ == '__main__':
    main()
