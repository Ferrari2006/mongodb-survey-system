"""Create a separate polished report; preserve saved source and older drafts."""
import html as escape_html
import json
import re
from pathlib import Path
from export_editable_report import ROOT, OUTPUT, NAME, Reader, Element
from layout_academic_report import nodes
import align_stage1_delivery as align

EDITOR = OUTPUT / (NAME + '-提交润色编辑版.html')
WORD = OUTPUT / (NAME + '-提交润色可编辑.docx')
LEFT = '数据管理系统课程设计 · 第一阶段'
RIGHT = '温正泽  10244304404'

CSS = '''
/* Final course-report typography: indented prose, three-rule tables. */
body{font:10.5pt/1.5 'SimSun','Songti SC','Times New Roman',serif;color:#111}
#report p{text-align:justify;text-indent:2em;margin:0 0 6pt;line-height:1.5}
#report>.repo-link,#report>.report-meta,#report .table-caption,#report .report-figure p,#report .tool-reference{text-indent:0}
#report>.report-meta{text-align:center}
#report>.repo-link{text-align:left;font-size:9.5pt}
#report h1{font:700 19pt/1.4 'SimHei','Microsoft YaHei',sans-serif;margin:8pt 0 9pt}
#report h2{font-size:13.5pt;margin:17pt 0 7pt}
#report h3{font-size:11.5pt;margin:11pt 0 6pt}
#report .design-point{margin-bottom:5pt}
#report .table-caption{text-align:center;font-size:10pt;line-height:1.4}
#report table{border-top:1.2pt solid #222;border-bottom:1.2pt solid #222;font-size:9.2pt;line-height:1.35}
#report th,#report td{border:0;padding:5pt 6pt;background:white;vertical-align:top}
#report thead th{border-bottom:.7pt solid #555;background:white}
#report td p,#report th p{text-indent:0;margin:0}
#report .report-figure p:last-child{font-size:9pt;line-height:1.5;text-align:left}
#page-header-preview{font:9pt 'SimSun','Times New Roman',serif;color:#444;border-bottom:.7pt solid #333}
@page{size:A4;margin:22mm 20mm 18mm;
@top-left{content:'数据管理系统课程设计 · 第一阶段';width:65%;font:8.5pt 'SimSun',serif;color:#444;vertical-align:bottom;text-align:left;padding-bottom:2mm;border-bottom:.7pt solid #333;margin-bottom:4mm}
@top-right{content:'温正泽  10244304404';width:35%;font:8.5pt 'SimSun',serif;color:#444;vertical-align:bottom;text-align:right;padding-bottom:2mm;border-bottom:.7pt solid #333;margin-bottom:4mm}
@bottom-center{content:counter(page) ' / ' counter(pages);font:9pt 'Times New Roman',serif;color:#555}}
@media print{.table-block{break-inside:auto;page-break-inside:auto}.table-block.keep-table{break-inside:avoid;page-break-inside:avoid}#report p{break-inside:avoid}#editor-bar,#page-header-preview{display:none!important}}
'''


def fragment(value):
    r = Reader(); r.feed(value)
    return r.root.children


def serialize(node):
    if isinstance(node, str):
        return escape_html.escape(node, quote=False)
    attrs = ''.join(' '+k+'="'+escape_html.escape(v or '', quote=True)+'"' for k,v in node.attrs.items())
    if node.tag in ('img','br','hr','meta','link','input','col'):
        return '<'+node.tag+attrs+'>'
    return '<'+node.tag+attrs+'>'+''.join(serialize(c) for c in node.children)+'</'+node.tag+'>'


def build():
    if EDITOR.exists() or WORD.exists():
        raise SystemExit('Final working copy already exists; preserve user edits.')
    source = OUTPUT/(NAME+'-仓库一致编辑版.html')
    html = source.read_text(encoding='utf-8')
    report = align.parse_report(html)
    changes = []

    def replace_paragraph(prefix, new):
        matches = [n for n in nodes(report) if n.tag == 'p' and n.text().startswith(prefix)]
        assert len(matches) == 1, (prefix, len(matches))
        old = matches[0].text(); matches[0].children = fragment(new)
        changes.append({'before':old,'after':matches[0].text()})

    replace_paragraph('结合课堂补充，', '根据课堂补充，开发时先处理集合划分、后端规则和API测试，再补齐页面操作与AI协作记录。报告说明数据库如何组织、跳转和校验如何执行，以及测试发现了什么；完整接口和操作步骤放在README与设计文档中。')
    replace_paragraph('下文结合集合、', '这些做法分别对应进度恢复、分支改答、统计口径和并发操作中的问题，后文结合实现与测试说明。')
    replace_paragraph('如果把所有答卷也嵌入问卷，', '如果把答卷都嵌入问卷，文档会随提交次数增加而不断膨胀；如果把题目和选项全部拆开，读取完整问卷又需要多次关联。本项目将数量有限、经常一起读取的题目配置嵌入问卷，把持续增加的答卷单独保存。会话和填写进度各自清理、更新，不放进正式答卷集合。')
    replace_paragraph('模块边界使题目约束', '题目校验和路径计算分别放在独立模块，便于直接编写测试。接口层处理登录、问卷归属、状态和数据库写入。完整API表、参数与错误码见README和<code>docs/API说明.md</code>。')
    replace_paragraph('后端提交时从第一题重新解释路径，', '提交时，后端从第一题重新计算路径，只检查实际经过的题目，并拒绝夹带被跳过题目的答案。例如，测试中的<code>q1=a → q3</code>可以通过，额外附带q2答案则会被拒绝。页面显示的路径不能直接作为入库依据。')
    replace_paragraph('表8归纳AI输出', '复核AI生成内容时，发现的问题包括需求解释不清、边界条件遗漏，以及报告与代码没有同步。表8列出实际修正过程；其中的代码和材料修改由AI执行，人工提供要求、参考方向和反馈。')
    replace_paragraph('后续引导AI时，', '这些问题说明，只给AI一个功能名称还不够。需要先说明何时保存、何时算提交、哪些输入应被拒绝，再让它写实现和测试。完成后还要检查数据库中的实际记录，区分程序错误、需求理解偏差和工具执行失败。')
    replace_paragraph('第一阶段的实现将', '第一阶段完成了从创建问卷到填写、提交和统计的流程。题目与规则嵌入问卷，已确认进度单独保存；提交时重新校验有效路径，统计只读取正式答卷。稳定ID、条件更新和唯一索引分别处理关联、并发覆盖和重复提交问题。')
    replace_paragraph('当前范围是本地开发服务器', '当前验证范围限于本地开发服务器和课程规模数据。文本统计目前全部返回，数据增长后需要分页；跨集合操作没有事务保证，普通JSON/BSON数值也不承诺任意精度小数。题目共享、版本管理和跨问卷统计留到第二阶段实现。第一阶段的Git基线与旧数据已经保留，后续修改可以据此比较。')

    for parent in list(nodes(report)):
        rewritten=[]
        for child in parent.children:
            if isinstance(child,Element) and child.tag=='ul':
                for li in child.children:
                    if isinstance(li,Element) and li.tag=='li':
                        li.tag='p';li.attrs={'class':'design-point'};rewritten.append(li)
            else:rewritten.append(child)
        parent.children=rewritten
    # Tighten the four feature paragraph labels without removing their content.
    for n in nodes(report):
        if n.tag=='strong':
            replacements={'让保存内容与实际路径一致。':'保存的答案与实际路径一致。',
                          '使统计结果可以解释、可以复核。':'统计分别列出总数与单题分母。',
                          '把常见异常纳入验证。':'补测正常流程以外的边界。'}
            if n.text() in replacements:n.children=[replacements[n.text()]]
    tables=[n for n in nodes(report) if n.tag=='table']
    assert len(tables)==8
    tbody=next(n for n in nodes(tables[-1]) if n.tag=='tbody')
    extra=[
        ('文档中的字段说明没有随代码一起核对', '设计文档曾把ID统称UUID、答案统称数组。对照代码后，改为区分会话令牌摘要、进度答案对象和正式答卷数组，并同步报告入口。', '2026-10-22仓库报告统一与页眉日志；代码、Schema及23个API路由对应检查'),
        ('报告生成脚本误把正文当作图表注释', '以“表8”或“图2”开头的正文被错误套用注释样式。收紧识别条件，并分别渲染Word与HTML，检查字号、对齐和分页。', '2026-10-22科学技能实际复核日志；导出脚本及逐页排版检查')]
    for cells in extra:
        tr=Element('tr')
        for value in cells:
            td=Element('td');td.children=[value];tr.children.append(td)
        tbody.children.append(tr)
    replace_paragraph('工具执行也出现过失败：', '工具执行也有过失败。Windows终端直接接收多行浏览器脚本时出现解析错误，后来改为从文件加载；一次浏览器检查被原生确认框打断，改用API准备前置数据后重新执行。首次失败没有记作通过，最终结果与重跑过程分别保留在日志中。')
    replace_paragraph('完整实际提示、', '实际提示、代码位置、修改者与结果保存在<code>ai_logs/</code>。例如，用户要求“保留之前已经实现的比较好的功能”，之后报告保留了进度恢复和有效路径说明；补充AI问题章节时，也没有删除已有失败记录。')
    report.children.insert(0,Element('div',{'id':'page-header-preview','contenteditable':'false'}))
    report.children[0].children=fragment('<span>'+LEFT+'</span><span>'+RIGHT+'</span>')
    html=re.sub(r'(<main\b[^>]*>)[\s\S]*?(</main>)',lambda m:m.group(1)+''.join(serialize(c) for c in report.children)+m.group(2),html,count=1)
    html=re.sub(r'<section class="table-block"><p class="table-caption">(表[458])',r'<section class="table-block keep-table"><p class="table-caption">\1',html)
    html=html.replace('</style>',CSS+'</style>',1).replace('报告仓库一致版','报告提交编辑版').replace('第一阶段报告 仓库一致编辑版','第一阶段报告 提交编辑版').replace(NAME+'-仓库一致-我的修改.html',NAME+'-提交-我的修改.html')
    EDITOR.write_text(html,encoding='utf-8')
    qa=ROOT/'tmp/final-submission';qa.mkdir(parents=True,exist_ok=True)
    (qa/'rewrites.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),encoding='utf-8')
    assert not re.search(r'\bv[01]\b',align.parse_report(html).text(),re.I)
    print('Created separate final editor; old files preserved.')


def build_word():
    align.EDITOR,align.WORD,align.LEFT,align.RIGHT=EDITOR,WORD,LEFT,RIGHT
    align.word()
    from docx import Document
    from docx.shared import Cm,Pt
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    doc=Document(WORD)
    doc.styles['Normal'].font.size=Pt(10.5)
    for p in doc.paragraphs:
        text=p.text.strip()
        if p.style.name=='Normal' and text and not text.startswith(('课程：','GitHub 仓库','图1','图2','表1','表2','表3','表4','表5','表6','表7','表8','报告辅助工具：','{')) and not p._p.xpath('.//w:drawing'):
            p.paragraph_format.first_line_indent=Pt(21)
            p.paragraph_format.line_spacing=1.4
    for table in doc.tables:
        pr=table._tbl.tblPr
        for old in list(pr.findall(qn('w:tblBorders'))):pr.remove(old)
        borders=OxmlElement('w:tblBorders')
        for edge in ('top','bottom','left','right','insideH','insideV'):
            item=OxmlElement('w:'+edge);item.set(qn('w:val'),'single' if edge in ('top','bottom') else 'nil')
            item.set(qn('w:sz'),'8');item.set(qn('w:color'),'222222');borders.append(item)
        pr.append(borders)
        for i,row in enumerate(table.rows):
            for cell in row.cells:
                tc=cell._tc.get_or_add_tcPr()
                for old in list(tc.findall(qn('w:shd'))):tc.remove(old)
                if i==0:
                    cb=OxmlElement('w:tcBorders');bottom=OxmlElement('w:bottom');bottom.set(qn('w:val'),'single');bottom.set(qn('w:sz'),'4');bottom.set(qn('w:color'),'555555');cb.append(bottom);tc.append(cb)
    doc.save(WORD)


if __name__=='__main__':
    import sys
    if '--word' in sys.argv:build_word()
    elif '--sync' in sys.argv:
        align.WORD=WORD;align.sync(EDITOR)
    else:build()
