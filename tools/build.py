#!/usr/bin/env python3
"""
Portfolio build step.  Run it after editing content or adding images:

    python3 tools/build.py

What it does, all of it idempotent (safe to run any number of times):

  1. Makes resized WebP + JPEG versions of every image the site actually uses,
     into public/media/opt/ . Animated GIFs become MP4 + WebM, which are
     roughly 85% smaller for the same motion.
  2. Writes data/img.json and injects it into assets/app.js, so the browser
     knows each image's real dimensions and can reserve space before it loads.
  3. Splits data/site.json into data/core.json + projects/field/research.json,
     so the home page no longer downloads every project to show three
     paragraphs. site.json stays the file Pages CMS edits; these are derived.
  4. Rebuilds the nine HTML shells with assets/style.css inlined and the
     page's data preloaded.

Requires: pillow (pip install pillow) and ffmpeg (only if you use animated GIFs).
"""
import json, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(ROOT, "public", "media")
OUT = os.path.join(MEDIA, "opt")
VERSION_FILE = os.path.join(ROOT, "data", ".version")

try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is required:  pip install pillow")

THUMB_W = [400, 800]   # card thumbnails sit in a 250-420px slot
FULL_W = [880, 1600]   # item-page figures sit in an ~820px column
HEAVY = ("projects", "field", "research")

site = json.load(open(os.path.join(ROOT, "data", "site.json")))
os.makedirs(OUT, exist_ok=True)
n = lambda p: (p or "").lstrip("/")

thumbs, fulls = set(), set()
for key in ("projects", "field"):
    for it in site.get(key, []):
        if it.get("thumb"):
            thumbs.add(n(it["thumb"]))
        for m in it.get("maps") or []:
            fulls.add(n(m))
        for s in it.get("sections") or []:
            if s.get("img"):
                fulls.add(n(s["img"]))
for g in site.get("research", []):
    for x in g.get("items", []):
        for s in x.get("sections") or []:
            if s.get("img"):
                fulls.add(n(s["img"]))

manifest, made, skipped = {}, 0, 0
slug = lambda p: re.sub(r"[^A-Za-z0-9]+", "-", os.path.splitext(os.path.basename(p))[0]).strip("-").lower()


def fresh(src, dst):
    """True when dst already exists and is newer than its source."""
    return os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src)


def raster(path, widths, kind):
    global made, skipped
    src = os.path.join(ROOT, path)
    if not os.path.exists(src):
        print("  ! missing, skipped:", path)
        return
    with Image.open(src) as im:
        im = im.convert("RGBA") if im.mode in ("P", "LA", "RGBA") else im.convert("RGB")
        w0, h0 = im.size
        flatsrc = os.path.splitext(path)[1].lower() == ".png"  # screenshots/maps: keep text crisp
        s, ent = slug(path), {"w": w0, "h": h0, "kind": kind, "webp": [], "jpg": []}
        picked = sorted(set([w for w in widths if w < w0] + [min(w0, widths[-1])]))
        for tw in picked:
            th = max(1, round(h0 * tw / w0))
            wp, jp = os.path.join(OUT, f"{s}-{tw}.webp"), os.path.join(OUT, f"{s}-{tw}.jpg")
            if fresh(src, wp) and fresh(src, jp):
                skipped += 1
            else:
                rs = im.resize((tw, th), Image.LANCZOS)
                flat = rs
                if rs.mode == "RGBA":
                    bg = Image.new("RGB", rs.size, (255, 255, 255))
                    bg.paste(rs, mask=rs.split()[-1])
                    flat = bg
                rs.save(wp, "WEBP", quality=84 if flatsrc else 76, method=6)
                flat.save(jp, "JPEG", quality=84 if flatsrc else 80, optimize=True, progressive=True)
                made += 1
            ent["webp"].append([f"opt/{s}-{tw}.webp", tw])
            ent["jpg"].append([f"opt/{s}-{tw}.jpg", tw])
        manifest[path] = ent


def gif(path):
    """Animated GIF -> MP4 + WebM. Same loop, a fraction of the bytes."""
    global made
    src = os.path.join(ROOT, path)
    with Image.open(src) as im:
        frames, w0 = getattr(im, "n_frames", 1), im.size[0]
    if frames <= 1:
        return raster(path, FULL_W, "full")
    if not shutil.which("ffmpeg"):
        print("  ! ffmpeg not found, leaving", path, "as a GIF")
        return
    s = slug(path)
    tw = min(880, w0) - (min(880, w0) % 2)
    mp4, webm = os.path.join(OUT, f"{s}.mp4"), os.path.join(OUT, f"{s}.webm")
    poster = os.path.join(OUT, f"{s}-poster.jpg")
    if not (fresh(src, mp4) and fresh(src, webm) and fresh(src, poster)):
        vf = f"scale={tw}:-2:flags=lanczos"
        q = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vf", vf]
        subprocess.run(q + ["-movflags", "+faststart", "-pix_fmt", "yuv420p", "-c:v", "libx264",
                            "-crf", "28", "-preset", "slow", "-an", mp4], check=True)
        subprocess.run(q + ["-c:v", "libvpx-vp9", "-crf", "36", "-b:v", "0", "-an", webm], check=True)
        subprocess.run(q + ["-frames:v", "1", "-q:v", "4", poster], check=True)
        made += 3
    with Image.open(poster) as pm:
        pw, ph = pm.size
    manifest[path] = {"w": pw, "h": ph, "kind": "video", "mp4": f"opt/{s}.mp4",
                      "webm": f"opt/{s}.webm", "poster": f"opt/{s}-poster.jpg"}


for p in sorted(thumbs):
    gif(p) if p.lower().endswith(".gif") else raster(p, THUMB_W, "thumb")
for p in sorted(fulls - thumbs):
    gif(p) if p.lower().endswith(".gif") else raster(p, FULL_W, "full")

# sidebar portrait: shown at 150px, so don't ship anything bigger than 300
photo = n(site.get("photo", ""))
if photo and os.path.exists(os.path.join(ROOT, photo)):
    with Image.open(os.path.join(ROOT, photo)) as im:
        im = im.convert("RGB")
        for tw in (150, 300):
            th = max(1, round(im.size[1] * tw / im.size[0]))
            rs = im.resize((tw, th), Image.LANCZOS)
            rs.save(os.path.join(ROOT, "assets", f"photo-{tw}.webp"), "WEBP", quality=82, method=6)
            rs.save(os.path.join(ROOT, "assets", f"photo-{tw}.jpg"), "JPEG", quality=84, optimize=True)

# a 256px favicon is ~77KB for a 16px slot; 32px is ~2KB
fav = os.path.join(ROOT, "favicon.png")
if os.path.exists(fav):
    with Image.open(fav) as im:
        im = im.convert("RGBA")
        im.resize((32, 32), Image.LANCZOS).save(os.path.join(ROOT, "favicon-32.png"), "PNG", optimize=True)
        im.resize((180, 180), Image.LANCZOS).save(os.path.join(ROOT, "apple-touch-icon.png"), "PNG", optimize=True)

json.dump(manifest, open(os.path.join(ROOT, "data", "img.json"), "w"), separators=(",", ":"))

# --- inject the manifest into app.js between its markers ---------------------
appf = os.path.join(ROOT, "assets", "app.js")
app = open(appf).read()
blob = "const IM=" + json.dumps(manifest, separators=(",", ":")) + ";"
app2, cnt = re.subn(r"/\*IMG-MANIFEST\*/.*?/\*END-IMG-MANIFEST\*/",
                    "/*IMG-MANIFEST*/\n" + blob + "\n/*END-IMG-MANIFEST*/", app, flags=re.S)
if not cnt:
    sys.exit("! assets/app.js is missing its /*IMG-MANIFEST*/ markers")
open(appf, "w").write(app2)

# --- split site.json so no page fetches lists it will never render -----------
core = {k: v for k, v in site.items() if k not in HEAVY}
json.dump(core, open(os.path.join(ROOT, "data", "core.json"), "w"), separators=(",", ":"))
for k in HEAVY:
    json.dump({k: site.get(k, [])}, open(os.path.join(ROOT, "data", f"{k}.json"), "w"),
              separators=(",", ":"))

# --- cache version: bump only when content changed, so caches stay warm ------
stamp = json.dumps([manifest, core, {k: site.get(k) for k in HEAVY}], sort_keys=True)
import hashlib
VERSION = hashlib.md5(stamp.encode()).hexdigest()[:8]
open(VERSION_FILE, "w").write(VERSION)
app3 = re.sub(r"const V='[^']*'", f"const V='{VERSION}'", open(appf).read(), count=1)
open(appf, "w").write(app3)

# --- HTML shells -------------------------------------------------------------
PAGES = {"index.html": "home", "projects.html": "projects", "field.html": "field",
         "research.html": "research", "blog.html": "blog", "about.html": "about",
         "contact.html": "contact", "privacy.html": "privacy", "item.html": "item"}
EXTRA = {"projects": "projects", "field": "field", "research": "research",
         "blog": "blog", "item": "projects"}
css = open(os.path.join(ROOT, "assets", "style.css")).read()
name = site.get("name", "Portfolio")
desc = (site.get("title") or "")[:150]
for f, page in PAGES.items():
    ex = EXTRA.get(page)
    pre = f'<link rel="preload" href="data/{ex}.json?v={VERSION}" as="fetch" crossorigin>' if ex else ""
    open(os.path.join(ROOT, f), "w").write(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{name}</title><meta name="description" content="{desc}">'
        '<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png">'
        '<link rel="apple-touch-icon" href="apple-touch-icon.png">'
        f'<link rel="preload" href="data/core.json?v={VERSION}" as="fetch" crossorigin>{pre}'
        f'<link rel="preload" href="assets/app.js?v={VERSION}" as="script">'
        f'<style>{css}</style><script src="assets/app.js?v={VERSION}" defer></script>'
        f'</head><body data-page="{page}">'
        '<noscript><p style="padding:40px;font:15px/1.6 system-ui">This portfolio needs '
        'JavaScript enabled to display its content.</p></noscript></body></html>')

kb = lambda p: os.path.getsize(os.path.join(ROOT, p)) / 1024
print(f"images: {made} written, {skipped} already current, {len(manifest)} in manifest")
print(f"data:   core {kb('data/core.json'):.0f}KB | " +
      " | ".join(f"{k} {kb('data/'+k+'.json'):.0f}KB" for k in HEAVY) +
      f"   (site.json {kb('data/site.json'):.0f}KB stays the CMS source)")
print(f"html:   {len(PAGES)} shells rebuilt, cache version {VERSION}")

unused = sorted(set(os.listdir(MEDIA)) - {os.path.basename(p) for p in manifest} - {"opt"})
if unused:
    tot = sum(os.path.getsize(os.path.join(MEDIA, u)) for u in unused if os.path.isfile(os.path.join(MEDIA, u)))
    print(f"note:   {len(unused)} file(s) in public/media are not referenced by site.json "
          f"({tot/1048576:.1f}MB). Safe to delete if you don't plan to use them.")
