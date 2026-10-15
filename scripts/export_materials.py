"""Export tracked MongoDB schema and a printable report from their source files."""
import json
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
    css = """body{font-family:'Microsoft YaHei',sans-serif;color:#202730;max-width:880px;margin:40px auto;padding:0 24px;line-height:1.8;font-size:15px}h1{font-size:27px}h2{font-size:20px;margin-top:28px;color:#111}table{width:100%;border-collapse:collapse;font-size:13px}th,td{border:1px solid #bbc3cc;padding:7px;text-align:left}th{background:#f0f3f7}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#245287}@page{size:A4;margin:18mm} @media print{body{margin:0;padding:0;max-width:none;font-size:11pt}h1,h2,h3{break-after:avoid}tr{break-inside:avoid}p{orphans:3;widows:3}}"""
    output = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>第一阶段完成报告</title><style>'+css+'</style></head><body>'+body+'</body></html>'
    destination = source.with_suffix(".html")
    destination.write_text(output, encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
