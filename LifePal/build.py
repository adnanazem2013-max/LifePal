from pathlib import Path
root = Path(__file__).resolve().parent
html = '<!doctype html>\n<html lang="en" dir="ltr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#080c14"><meta name="description" content="LifePal — a thoughtful local workspace for life and business."><title>LifePal · Your everyday OS</title><style>' + (root/'style.css').read_text(encoding='utf-8') + '</style></head><body><div id="app"></div><div id="toast" role="status" aria-live="polite"></div><script>' + (root/'app.js').read_text(encoding='utf-8') + '</script></body></html>'
(root/'index.html').write_text(html, encoding='utf-8')
print('Built index.html — open it directly in your browser.')
