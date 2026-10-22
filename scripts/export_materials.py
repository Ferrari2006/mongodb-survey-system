"""Export tracked MongoDB schema and a printable report from their source files."""
import json
import base64
import mimetypes
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.database import SCHEMAS


def main():
    schema_dir = ROOT / "database"
    schema_dir.mkdir(exist_ok=True)
    (schema_dir / "schema.json").write_text(json.dumps(SCHEMAS, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    try:
        import mistune
    except ImportError:
        raise SystemExit("Schema exported. Optional HTML export requires: pip install -r requirements-report.txt")
    source = ROOT / "reports" / "第一阶段完成报告.md"
    body = mistune.create_markdown(escape=True, plugins=["table"])(source.read_text(encoding="utf-8"))
    # Embed local report figures, so the printable HTML also works when moved.
    image_dir = (ROOT / "reports" / "images").resolve()
    def embed(match):
        path = (ROOT / "reports" / match.group(1)).resolve()
        if not path.is_relative_to(image_dir):
            raise ValueError("Report images must stay inside reports/images")
        mime = mimetypes.guess_type(path.name)[0]
        if mime not in ("image/png", "image/jpeg", "image/svg+xml"):
            raise ValueError(f"Unsupported report image: {path.name}")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'src="data:{mime};base64,{encoded}"'
    body = re.sub(r'src="(images/[^\"]+)"', embed, body)
    css = """body{font-family:'Microsoft YaHei',sans-serif;color:#202730;max-width:880px;margin:40px auto;padding:0 24px;line-height:1.8;font-size:15px}h1{font-size:27px}h2{font-size:20px;margin-top:28px;color:#111}table{width:100%;border-collapse:collapse;font-size:13px}th,td{border:1px solid #bbc3cc;padding:7px;text-align:left}th{background:#f0f3f7}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#245287}@page{size:A4;margin:18mm} @media print{body{margin:0;padding:0;max-width:none;font-size:11pt}h1,h2,h3{break-after:avoid}tr{break-inside:avoid}p{orphans:3;widows:3}}"""
    css += "img{display:block;max-width:100%;height:auto;margin:14px auto}thead{display:table-header-group}img{break-inside:avoid}td,th{overflow-wrap:anywhere}th:first-child{width:18%;min-width:95px}td code{font-size:.9em}pre{background:#f5f7fa;border:1px solid #d9e0e8;padding:10px 14px;font-size:12px;line-height:1.55}blockquote{margin:14px 0;padding:3px 16px;border-left:3px solid #647d98;color:#455568}h3{font-size:16px}"
    css += "body{font-family:'SimSun','Songti SC','Microsoft YaHei',serif;line-height:1.7}h1,h2,h3{font-family:'SimHei','Microsoft YaHei',sans-serif}h1{text-align:center;font-size:25px;padding:14px 0;border-top:1px solid #737f8b;border-bottom:1px solid #737f8b}h1+p{text-align:center;font-size:13px}body>p:first-child{font-size:13px}h2{color:#182735}table{line-height:1.55}code{overflow-wrap:anywhere}pre code{overflow-wrap:normal}@media print{body{font-size:10.5pt;line-height:1.65}h1{font-size:19pt}h2{font-size:14pt;margin-top:20px}h3{font-size:11.5pt}table{font-size:9pt}pre{font-size:8.5pt}img{max-height:185mm;object-fit:contain}}"
    output = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>第一阶段完成报告</title><style>'+css+'</style></head><body>'+body+'</body></html>'
    destination = source.with_suffix(".html")
    destination.write_text(output, encoding="utf-8")
    submission = ROOT / "第一阶段" / "提交材料"
    submission.mkdir(parents=True, exist_ok=True)
    (submission / "2026_ECNU_PJ1_1_温正泽.html").write_text(output, encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
