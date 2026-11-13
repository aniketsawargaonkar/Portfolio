# Aniket Sawargaonkar: portfolio
Upload the CONTENTS of this folder to the root of a new GitHub repo. Settings > Pages > Deploy from a branch > main / root.
Images: upload to public/media, then type their path (for example public/media/odisha.jpg) in the Thumbnail or Map fields.
Contact form: the first message triggers a one-time FormSubmit activation email to your inbox. Click it once.
You can preview by double-clicking index.html (uses data/site.js). After upload, the live site reads data/site.json, which Pages CMS edits.

---

## Performance build

The site is a client-rendered static site, so a few generated files do the heavy
lifting. Run this after changing content or adding images:

```bash
pip install pillow        # one-off; ffmpeg too if you use animated GIFs
python3 tools/build.py
```

It is safe to run any number of times. `.github/workflows/build.yml` runs it
automatically on push, so edits made in Pages CMS stay optimised without you
doing anything.

**Edit these:** `data/site.json`, `data/blog.json`, `assets/app.js`,
`assets/style.css`, and anything in `public/media/`.

**Don't edit these — the build overwrites them:** the nine `*.html` files,
`data/core.json`, `data/projects.json`, `data/field.json`, `data/research.json`,
`data/img.json`, `public/media/opt/`, `assets/photo-*.{jpg,webp}`,
`favicon-32.png`, `apple-touch-icon.png`.

Originals in `public/media/` are never modified — resized copies go to
`public/media/opt/`. Keep the originals; the build needs them.
