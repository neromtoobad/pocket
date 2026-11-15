"""Render writeup/ARTICLE.md into space_static/article.html (same look as the Space's index.html).

usage: python build_article_page.py
"""
from pathlib import Path
import re
import markdown

ROOT = Path(__file__).resolve().parent
md = (ROOT.parent / "writeup/ARTICLE.md").read_text()
# repo-relative links -> GitHub
md = re.sub(r"^> \[!(WARNING|NOTE|TIP|IMPORTANT|CAUTION)\]\s*\n?", "> ", md, flags=re.M)
md = re.sub(r"\]\((?!https?://|#)([^)]+)\)",r"](https://github.com/neromtoobad/pocket/blob/main/\1)", md)
body = markdown.markdown(md, extensions=["tables", "fenced_code", "toc", "sane_lists"])
title = re.search(r"^# (.+)$", md, re.M).group(1) if re.search(r"^# (.+)$", md, re.M) else "Pocket"

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pocket write-up</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{ --bg:#fafaf8; --panel:#fff; --ink:#1b1d1f; --muted:#646a70; --line:#e4e4df; --accent:#1f6f5c; --accent-soft:#e5f1ed; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.65 Inter, system-ui, sans-serif; }}
  .top {{ border-bottom:1px solid var(--line); background:var(--panel); }}
  .top div {{ max-width:860px; margin:0 auto; padding:12px 16px; display:flex; gap:18px; flex-wrap:wrap; font-size:14px; }}
  .top a {{ color:var(--accent); text-decoration:none; font-weight:500; }}
  main {{ max-width:860px; margin:0 auto; padding:24px 16px 80px; }}
  h1 {{ font-size:30px; line-height:1.25; margin:8px 0 16px; }}
  h2 {{ font-size:22px; margin:44px 0 10px; padding-top:12px; border-top:1px solid var(--line); }}
  h3 {{ font-size:18px; margin:28px 0 8px; }}
  a {{ color:var(--accent); }}
  .tbl {{ overflow-x:auto; margin:14px 0; }}
  table {{ border-collapse:collapse; font-size:14px; background:var(--panel); }}
  th, td {{ border:1px solid var(--line); padding:6px 10px; text-align:left; vertical-align:top; }}
  th {{ background:#f2f2ee; font-weight:600; }}
  code {{ font:13px "JetBrains Mono", monospace; background:#efefea; padding:1px 4px; border-radius:4px; }}
  pre {{ background:#1b1d1f; color:#f2f2ee; padding:14px; border-radius:8px; overflow-x:auto; }}
  pre code {{ background:none; color:inherit; padding:0; }}
  blockquote {{ margin:16px 0; padding:10px 14px; background:var(--accent-soft); border-left:3px solid var(--accent); border-radius:4px; }}
  img {{ max-width:100%; }}
</style>
</head>
<body>
<div class="top"><div><a href="index.html">Results explorer</a><a href="https://huggingface.co/datasets/MOREN808/pocket-safety-evals">Dataset</a><a href="https://huggingface.co/MOREN808/tiny-aya-global-pocket-gguf">GGUF builds</a><a href="https://github.com/neromtoobad/pocket">Code</a></div></div>
<main>
{body}
</main>
</body>
</html>
"""
page = page.replace("<table>", '<div class="tbl"><table>').replace("</table>", "</table></div>")
(ROOT / "space_static/article.html").write_text(page)
print("wrote space_static/article.html", len(page) // 1024, "KB")
