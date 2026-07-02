"""Render the Chinese Markdown report as an A3 landscape HTML document."""

from __future__ import annotations

import argparse
from pathlib import Path

import markdown


CSS = """
@page {
  size: A3 landscape;
  margin: 12mm;
}
html {
  font-family: "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
  color: #172033;
  font-size: 11pt;
  line-height: 1.55;
}
body {
  margin: 0 auto;
  max-width: none;
}
h1, h2, h3 {
  color: #132b50;
  page-break-after: avoid;
}
h1 {
  font-size: 25pt;
  border-bottom: 2px solid #315b8a;
  padding-bottom: 7px;
}
h2 {
  font-size: 18pt;
  margin-top: 24px;
  border-bottom: 1px solid #a9bad0;
}
h3 { font-size: 14pt; }
a {
  color: #155ca2;
  text-decoration: none;
  overflow-wrap: anywhere;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0 18px;
  font-size: 9pt;
  page-break-inside: auto;
}
thead {
  display: table-header-group;
}
tr {
  page-break-inside: avoid;
}
th, td {
  border: 1px solid #9cacbf;
  padding: 5px 7px;
  vertical-align: top;
  overflow-wrap: anywhere;
}
th {
  background: #dce8f5;
  color: #162c48;
}
tr:nth-child(even) td {
  background: #f5f8fb;
}
img {
  max-width: 150px;
  max-height: 110px;
  object-fit: contain;
}
code {
  font-family: Consolas, monospace;
  background: #edf1f5;
  padding: 1px 4px;
}
pre {
  white-space: pre-wrap;
  background: #edf1f5;
  padding: 10px;
}
blockquote {
  border-left: 4px solid #7294ba;
  margin-left: 0;
  padding-left: 12px;
  color: #42556d;
}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("reports/report.md"))
    parser.add_argument("--output", type=Path, default=Path("reports/report_a3.html"))
    args = parser.parse_args()

    source = args.input.resolve()
    output = args.output.resolve()
    body = markdown.markdown(
        source.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>BEHAVIOR 机器人资源图谱</title>
<style>{CSS}</style>
</head>
<body>{body}</body>
</html>
"""
    output.write_text(document, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
