from PIL import Image, ImageDraw, ImageFont
import os

SRC = "app_icons/leagues_page_icon.png"
SIZES = {"apple-touch-icon.png": 180, "icon-192.png": 192, "icon-512.png": 512, "favicon-32.png": 32}

os.makedirs("app_icons/prod", exist_ok=True)
os.makedirs("app_icons/staging_env", exist_ok=True)  # 'staging' dir name is .gitignored

master = Image.open(SRC).convert("RGB")
W, H = master.size  # 1024 x 1024

def _font(px):
    for path in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\Arialbd.ttf", r"C:\Windows\Fonts\arial.ttf"):
        try:
            return ImageFont.truetype(path, px)
        except Exception:
            continue
    return ImageFont.load_default()

# --- Staging banner master: bottom ribbon with "STAGING" ---
staging_master = master.copy()
d = ImageDraw.Draw(staging_master)
band_h = int(H * 0.22)
y0 = H - band_h
d.rectangle([0, y0, W, H], fill=(232, 89, 12))          # bold orange ribbon
d.rectangle([0, y0, W, y0 + int(H*0.012)], fill=(255, 255, 255))  # thin top accent line
text = "STAGING"
fnt = _font(int(band_h * 0.62))
tb = d.textbbox((0, 0), text, font=fnt)
tw, th = tb[2] - tb[0], tb[3] - tb[1]
d.text(((W - tw) / 2 - tb[0], y0 + (band_h - th) / 2 - tb[1]), text, font=fnt,
       fill=(255, 255, 255), stroke_width=max(2, int(band_h*0.03)), stroke_fill=(120, 40, 0))

for variant, base in (("prod", master), ("staging_env", staging_master)):
    for fname, size in SIZES.items():
        img = base.resize((size, size), Image.LANCZOS)
        img.save(f"app_icons/{variant}/{fname}")
        print(f"  app_icons/{variant}/{fname}  ({size}x{size})")
print("done")
