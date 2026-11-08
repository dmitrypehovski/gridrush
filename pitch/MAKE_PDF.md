# Rebuild the one-pager PDF

```bash
cd gridrush
python3 pitch/build_onepager.py
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --no-sandbox --disable-gpu \
  --user-data-dir="$PWD/.chrome-profile-pdf" --no-pdf-header-footer \
  --print-to-pdf="$PWD/pitch/GRIDRUSH-one-pager.pdf" \
  --virtual-time-budget=3000 "file://$PWD/pitch/one-pager.html"
```

Numbers come from `results/loop.json` and `results/powerflow.json`; nothing is hardcoded.
A4 landscape, one page. Preview image: `pitch/one-pager-preview.png`.
