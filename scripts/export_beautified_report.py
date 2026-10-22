"""Create separate editable copies with new figures; never overwrite user drafts."""
import base64
import hashlib
import json
import re
from pathlib import Path

from export_editable_report import Element, NAME, OUTPUT, ROOT, Reader, make_word


def elements(node):
    yield node
    for child in node.children:
        if isinstance(child, Element):
            yield from elements(child)


def uri(path, mime):
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def main():
    source = OUTPUT / (NAME + "-网页编辑版.html")
    html_output = OUTPUT / (NAME + "-图表美化编辑版.html")
    word_output = OUTPUT / (NAME + "-图表美化可编辑.docx")
    if html_output.exists() or word_output.exists():
        raise SystemExit("Beautified copies exist. Preserve edits; use a new destination or back up first.")
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    html = source.read_text(encoding="utf-8")
    figures = [
        ("stage1-data-model-refined", "五集合关联与嵌入式题目结构", "图1"),
        ("stage1-statistics-refined", "依据2026年10月21日真实测试记录重绘的多选统计与数字题核对", "图2"),
    ]
    count = 0
    def replace_image(match):
        nonlocal count
        filename, alt, _ = figures[count]
        count += 1
        src = uri(ROOT / "reports" / "images" / (filename + ".svg"), "image/svg+xml")
        return f'<img src="{src}" alt="{alt}" contenteditable="false" data-word-width-cm="16.9" />'
    html = re.sub(r"<img\b[^>]*>", replace_image, html)
    if count != 2:
        raise ValueError(f"Expected two source figures, got {count}")
    old_caption = "图2　表格与条形图同时显示次数和比例，多选之和可超过100%。"
    new_caption = "图2　依据2026年10月21日实际验证数据重绘。多选有效回答2份，各选项次数与比例分别显示；数字0计入平均。"
    if html.count(old_caption) != 1:
        raise ValueError("The source figure caption changed; review user edits before replacing.")
    html = html.replace(old_caption, new_caption)
    # Keep each figure and its existing caption together when printing.
    html, wrapped = re.subn(r"(<p><img\b[^>]*>\s*</p>)\s*(<p>图[12][\s\S]*?</p>)",
                            r'<figure class="report-figure">\1\2</figure>', html)
    assert wrapped == 2
    css = ".report-figure{margin:18px 0;break-inside:avoid}.report-figure p{margin:7px 0}.report-figure p:last-child{font-size:12px;color:#506575;line-height:1.6}.report-figure img{width:100%;max-height:none}@media print{.report-figure p:last-child{font-size:9pt}.report-figure{margin:12px 0}}"
    html = html.replace("</style>", css + "</style>", 1)
    html = html.replace("<title>第一阶段报告 可编辑版</title>", "<title>第一阶段报告 图表美化编辑版</title>")
    html = html.replace("<strong>报告编辑版</strong>", "<strong>报告图表美化版</strong>")
    html = html.replace(NAME + "-我的修改.html", NAME + "-图表美化-我的修改.html")
    html_output.write_text(html, encoding="utf-8")

    reader = Reader()
    reader.feed(html)
    report = next(n for n in elements(reader.root) if n.attrs.get("id") == "report")
    image_nodes = [n for n in elements(report) if n.tag == "img"]
    for node, (filename, _, _) in zip(image_nodes, figures):
        # Word uses high-resolution rasters; HTML retains editable vector sources.
        node.attrs["src"] = uri(ROOT / "reports" / "images" / (filename + ".png"), "image/png")
    paragraphs, tables = make_word(report, word_output)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    qa = {"source": source.name, "source_sha256": before, "source_unchanged": True,
          "html": html_output.name, "word": word_output.name,
          "paragraphs": paragraphs, "tables": tables, "figures": len(image_nodes),
          "data_source": "tests/results/参考借鉴优化-2026-10-21.md"}
    dest = ROOT / "tmp" / "refined-report"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "export.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(qa, ensure_ascii=True))


if __name__ == "__main__":
    main()
