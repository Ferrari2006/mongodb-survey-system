"""Build a database diagram and redraw recorded statistics without new results.

The old diagram and real browser screenshot remain untouched. The statistics
figure is generated with ReportLab from the recorded 2026-10-21 synthetic run.
"""
from html import escape
from pathlib import Path

from reportlab.graphics import renderSVG
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "reports" / "images"
INK, MUTED, TEAL = "#183449", "#506575", "#167D8D"
PALE, LINE, WHITE = "#F2F7F9", "#C7D5DE", "#FFFFFF"


def database_svg():
    items = []
    def text(x, y, value, size=22, fill=INK, weight="400", **attrs):
        extra = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
        items.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" {extra}>{escape(value)}</text>')

    def rect(x, y, w, h, fill=WHITE, stroke=LINE, radius=10):
        items.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')

    def card(x, y, w, h, title, meaning):
        rect(x, y, w, h)
        items.append(f'<path d="M{x+1} {y+10}Q{x+1} {y+1} {x+10} {y+1}H{x+w-10}Q{x+w-1} {y+1} {x+w-1} {y+10}V{y+57}H{x+1}Z" fill="{PALE}"/>')
        text(x+20, y+36, title, 27, INK, "700")
        text(x+w-18, y+35, meaning, 20, MUTED, text_anchor="end")

    items.append('<rect width="1200" height="738" rx="12" fill="white"/>')
    text(32, 45, "问卷系统的五个集合", 32, INK, "700")
    text(32, 81, "题目随问卷读取；进度与正式答卷独立保存", 22, MUTED)
    card(32, 114, 300, 178, "users", "账号")
    text(52, 207, "username / password_hash", 20)
    text(52, 246, "created_at", 22)
    text(52, 277, "密码以哈希保存", 20, MUTED)
    card(490, 114, 678, 282, "surveys", "问卷定义")
    text(512, 191, "owner_id / title / status / revision", 22)
    rect(512, 210, 634, 165, PALE)
    text(532, 247, "questions[]", 25, TEAL, "700")
    text(1126, 247, "嵌入数组", 20, TEAL, text_anchor="end")
    text(532, 286, "id / type / title / required", 22)
    text(532, 321, "options[] / validation / jumps[]", 22)
    text(532, 354, "题目、选项与跳转规则一起获取", 20, MUTED)
    card(32, 368, 300, 164, "sessions", "登录会话")
    text(52, 459, "_id：令牌摘要", 22)
    text(52, 496, "user_id / expires_at", 22)
    card(490, 488, 312, 160, "fill_progress", "进度")
    text(510, 579, "answers{} / revision", 21)
    text(510, 619, "已确认的答案，不计统计", 20, MUTED)
    card(850, 488, 318, 160, "responses", "正式答卷")
    text(870, 579, "answers[] / path[]", 22)
    text(870, 619, "逐份保存，作为统计来源", 20, TEAL)
    items.append(f'<g fill="none" stroke="{MUTED}" stroke-width="2" marker-end="url(#arrow)"><path d="M332 219H488"/><path d="M182 292V366"/><path d="M646 396V486"/><path d="M1009 396V486"/></g>')
    text(411, 178, "owner_id", 20, MUTED, text_anchor="middle")
    text(411, 205, "1:N 创建", 19, MUTED, text_anchor="middle")
    text(201, 337, "user_id · 1:N", 20, MUTED)
    text(662, 449, "survey_id · 1:N", 20, MUTED)
    text(1025, 449, "survey_id", 20, MUTED)
    text(1025, 476, "1:N", 19, MUTED)
    items.append(f'<line x1="32" y1="675" x2="1168" y2="675" stroke="{LINE}"/>')
    text(32, 703, "实线表示 ID 引用；进度与正式答卷也通过 user_id 关联用户。", 20, MUTED)
    text(32, 731, "全部 _id 使用字符串；关系由后端校验，箭头不代表数据库外键或跨集合事务。", 20, MUTED)
    return '''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="738" viewBox="0 0 1200 738" role="img" aria-labelledby="title desc">
<title id="title">问卷系统的五个 MongoDB 集合及题目嵌入结构</title>
<desc id="desc">users 通过 owner_id 关联 surveys，通过 user_id 关联 sessions。surveys 内嵌 questions 数组，包含选项、校验和跳转规则。fill_progress 和 responses 引用 survey_id 与 user_id，前者保存已确认进度但不计统计，后者保存正式答卷并用于统计。</desc>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#506575"/></marker></defs>
<g font-family="Microsoft YaHei, SimHei, sans-serif">''' + "\n".join(items) + "</g></svg>\n"


def statistics_svg():
    # These constants reproduce the existing source record, not a fresh run.
    total, skipped, numeric_values = 3, 1, [0, 8]
    rows = [("图书馆", 2), ("食堂", 2), ("体育设施", 0)]
    denominator = total - skipped
    assert denominator == 2 and sum(numeric_values) / len(numeric_values) == 4
    pdfmetrics.registerFont(TTFont("ReportChinese", "C:/Windows/Fonts/simhei.ttf"))
    from reportlab.lib.colors import HexColor
    drawing = Drawing(1200, 664)
    def rect(x, y, w, h, fill=WHITE, stroke=None, radius=0):
        drawing.add(Rect(x, 664-y-h, w, h, rx=radius, ry=radius,
                         fillColor=HexColor(fill), strokeColor=HexColor(stroke) if stroke else None,
                         strokeWidth=1))
    def text(x, y, value, size=22, fill=INK, anchor="start"):
        drawing.add(String(x, 664-y, value, fontName="ReportChinese", fontSize=size,
                           fillColor=HexColor(fill), textAnchor=anchor))
    def line(x1, y1, x2, y2, fill=LINE):
        drawing.add(Line(x1, 664-y1, x2, 664-y2, strokeColor=HexColor(fill), strokeWidth=1))

    rect(0, 0, 1200, 664)
    text(32, 45, "统计口径与验证结果", 32)
    text(32, 81, "依据 2026-10-21 独立测试记录重绘 · 合成答卷", 22, MUTED)
    for x, value, label in [(32, "3 份", "整卷正式答卷"), (419, "2 份", "本多选题有效回答"), (806, "1 份", "跳过本题")]:
        rect(x, 109, 362, 95, PALE, LINE, 8)
        text(x+22, 150, value, 31, TEAL)
        text(x+22, 184, label, 21, MUTED)
    text(32, 247, "多选题各选项被选择的次数与比例", 24)
    text(1014, 247, "次数", 21, MUTED, "end")
    text(1160, 247, "比例", 21, MUTED, "end")
    x0, plot_width = 226, 655
    for percentage in [0, 50, 100]:
        x = x0 + plot_width * percentage/100
        line(x, 286, x, 430)
        text(x, 279, f"{percentage}%", 18, MUTED, "middle")
    for y, (label, count) in zip([317, 365, 413], rows):
        percent = count / denominator * 100
        text(32, y+7, label, 23)
        rect(x0, y-16, plot_width, 28, "#EAF1F4", radius=3)
        if count:
            rect(x0, y-16, plot_width*percent/100, 28, TEAL, radius=3)
        else:
            line(x0, y-17, x0, y+13, MUTED)
        text(1014, y+7, f"{count}", 24, INK, "end")
        text(1160, y+7, f"{percent:.1f}%", 24, TEAL if count else MUTED, "end")
    text(32, 469, "分母 = 实际回答本题的 2 份答卷；每人可选多项，比例之和可超过 100%。", 21, MUTED)
    rect(32, 495, 1136, 92, PALE, LINE, 8)
    text(54, 535, "数字题核对", 23)
    text(54, 568, "0 也是有效数值", 20, MUTED)
    text(425, 535, "原始值 0、8", 24)
    text(425, 568, "2 份有效回答", 20, MUTED)
    text(900, 535, "平均值 4", 27, TEAL)
    text(900, 568, "(0 + 8) ÷ 2", 20, MUTED)
    line(32, 612, 1168, 612)
    text(32, 644, "数据来源：tests/results/参考借鉴优化-2026-10-21.md", 20, MUTED)
    svg = renderSVG.drawToString(drawing)
    # Use installed Chinese fonts when the SVG is displayed in the browser.
    svg = svg.replace("font-family: ReportChinese", "font-family: Microsoft YaHei, SimHei, sans-serif")
    svg = svg.replace("<svg ", '<svg role="img" aria-labelledby="title desc" ', 1)
    at = svg.index(">", svg.index("<svg")) + 1
    svg = svg[:at] + '<title id="title">测试问卷多选统计及数字平均值核对</title><desc id="desc">3份正式答卷中2份回答本多选题，图书馆和食堂各2次即100%，体育设施0次即0%。数字有效值为0和8，平均值4。这是依据2026年10月21日验证记录重绘的图，不是新的运行截图。</desc>' + svg[at:]
    return svg


if __name__ == "__main__":
    IMAGES.mkdir(parents=True, exist_ok=True)
    for name, data in [("stage1-data-model-refined.svg", database_svg()),
                       ("stage1-statistics-refined.svg", statistics_svg())]:
        (IMAGES / name).write_text(data, encoding="utf-8")
        print(IMAGES / name)
