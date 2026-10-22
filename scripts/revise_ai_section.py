"""Rewrite AI-use prose from recorded work, retaining issues and attribution."""
import re
from pathlib import Path
from export_editable_report import ROOT,OUTPUT,NAME,Element
from layout_academic_report import nodes
from finalize_stage1_report import fragment,serialize
import align_stage1_delivery as align

EDITOR=OUTPUT/(NAME+'-AI过程修订编辑版.html')
WORD=OUTPUT/(NAME+'-AI过程修订可编辑.docx')


def paragraph(text):
    node=Element('p');node.children=fragment(text);return node


def build():
    if EDITOR.exists():raise SystemExit('Preserve saved revision.')
    source=OUTPUT/(NAME+'-最终提交编辑版.html');html=source.read_text(encoding='utf-8');report=align.parse_report(html)
    children=report.children
    start=next(i for i,n in enumerate(children) if isinstance(n,Element) and n.tag=='h2' and n.text().startswith('六、'))
    end=next(i for i,n in enumerate(children) if isinstance(n,Element) and n.tag=='h2' and n.text().startswith('七、'))
    original=children[start:end]
    headings=[n for n in original if isinstance(n,Element) and n.tag=='h3']
    tables=[n for n in original if isinstance(n,Element) and n.attrs.get('class','').startswith('table-block')]
    assert len(headings)==4 and len(tables)==2
    tool=next(n for n in original if isinstance(n,Element) and n.tag=='p' and n.text().startswith('报告辅助工具'))
    headings[0].children=['6.1 AI帮助完成的工作']
    headings[1].children=['6.2 我的引导与实际调整']
    headings[3].children=['6.4 设计思考与分工']
    # The historical export bug involved the then-numbered Figure 2, not current Figure 3.
    for node in nodes(tables[0]):
        node.children=[c.replace('“保留之前已经实现的比较好的功能”并以课堂补充为准','“保留之前已经实现的比较好的功能”') if isinstance(c,str) else c for c in node.children]
    for node in nodes(tables[1]):
        node.children=[c.replace('以“表8”或“图3”开头的正文','以表号或图号开头的正文').replace('参考报告的组织方式未充分突出本项目功能和课堂重点','报告未充分突出后端、数据库及已实现功能') if isinstance(c,str) else c for c in node.children]
    section=[original[0],
        paragraph('本项目主要使用Codex辅助需求整理、系统设计、代码实现和测试排查。我先提供作业文件和课堂补充，再根据阶段要求、已有功能和实际反馈逐步补充约束。开发过程中，AI多次修改方案和程序，相关提示、修改位置与执行结果保存在<code>ai_logs/</code>。这部分按实际记录说明AI的作用、出现的问题，以及我的反馈怎样影响后续工作。'),
        headings[0],
        paragraph('在需求整理阶段，AI将账号、问卷、题型、跳转、提交和统计等要求拆成模块，并列出匿名、重复填写、规则优先级等需要说明的约定。我补充老师强调的后端逻辑、数据库设计、测试和AI使用记录，要求先完成第一阶段；文件未说明的地方先按原文推进，不把暂定规则写成教师要求。'),
        paragraph('在设计与实现阶段，AI承担了主要的编码工作，包括Flask接口、PyMongo数据读写、题目校验、有效路径计算、进度恢复及聚合统计，也整理了Schema、API和运行说明。五个集合的具体字段、进度修订号和索引等方案主要由AI提出并实现；我的参与集中在提供课程约束、确定工作顺序和反馈保留哪些已有功能。'),
        paragraph('在验证阶段，AI编写并执行逻辑测试、API测试和浏览器检查，保存输入、预期与实际结果。2026年10月22日的完整自动化运行通过38项，后续排版和材料检查没有计入这38项。测试也暴露了校验类型、并发保存、统计读取和长文本容量等问题，相关修正与重跑依据见测试记录。'),
        headings[1],
        paragraph('我对AI的要求随着材料补充而逐步明确。例如，我先说明“先按照现有的做吧，没有的话以文件为准”，随后提供老师关于Schema、后端逻辑和测试的课堂说明。我还要求保留已经实现的功能，先完成第一阶段，再进行第二阶段扩展。AI据此调整开发顺序和报告内容，继续保留进度恢复、有效路径和统计口径等功能及说明。'),
        tables[0],
        paragraph('一次较具体的迭代是填写进度的处理。复核“每次填写都应该被保存”后，AI提出把已确认进度与正式答卷分开，补充<code>fill_progress</code>、GET/PUT接口、修订号和提交清理。已有数据库与浏览器记录验证了刷新恢复、改答后的分支清理、匿名偏好和统计隔离。这项方案及代码由AI完成，不将其写成我独立实现的功能。'),
        headings[2],
        paragraph('AI输出仍需核对。能完成正常流程，并不代表边界和组合操作都正确；报告写得完整，也不代表字段说明已经与源码一致。表8保留了本项目中实际发现的问题、处理办法及依据。'),
        tables[1],
        paragraph('工具执行也出现过失败：Windows终端直接传入多行浏览器脚本时报解析错误，后来改为从文件加载；一次浏览器测试被原生确认框打断，改用API准备前置数据后重跑。最近增加第三张图时，Word导出器仍固定检查两张图，导致断言失败，随后改为按输入的实际图数校验。这些失败由AI排查并修正，不能算作首次执行已通过。'),
        paragraph('因此，引导AI时需要给出可以检查的输入和结果，例如“跳过必答题后应能提交”“数字0应计入平均值”“同一请求重试不能多保存一份”。修改后再核对接口响应和数据库效果，区分需求解释、业务程序与执行环境的问题。这里只列已有依据的检查，不把未执行的人工操作或计划写成完成结果。'),
        headings[3],
        paragraph('我在协作中重点提出的要求是：先完成第一阶段、以后再扩展；后端和数据库优先；保留旧数据和已实现的功能；报告应与实际代码和测试结果对应。因此，图示和报告采用本项目的Flask、PyMongo、五集合与发布冻结规则，尚未完成的版本管理和跨问卷统计不写成已有功能。'),
        paragraph('这些约束影响了最后的取舍：进度与答卷分开，未提交内容不进入统计；后端重新计算路径，避免只靠页面隐藏题目；发布后冻结题目，先保护已有答案的含义，再为第二阶段保留扩展空间。具体技术方案、Schema、规则解释器和修正代码主要由AI完成。已有结果以仓库中的实际运行记录为依据，各轮具体模型未逐一核实，不作推测。'),
        tool]
    report.children=children[:start]+section+children[end:]
    report.children.insert(0,Element('div',{'id':'page-header-preview','contenteditable':'false'}));report.children[0].children=fragment('<span>数据管理系统课程设计 · 第一阶段</span><span>温正泽 10244304404</span>')
    html=re.sub(r'(<main\b[^>]*>)[\s\S]*?(</main>)',lambda m:m.group(1)+''.join(serialize(c) for c in report.children)+m.group(2),html,count=1)
    html=html.replace('最终提交编辑版','AI过程修订编辑版').replace('报告最终提交版','报告AI过程修订版').replace(NAME+'-最终提交-我的修改.html',NAME+'-AI过程修订-我的修改.html')
    EDITOR.write_text(html,encoding='utf-8')
    # Chapters 1–5 and 7 retain identical text; only Chapter 6 is rewritten.
    before=align.parse_report(source.read_text(encoding='utf-8')).text();after=align.parse_report(html).text()
    for begin,finish in [('一、','六、'),('七、',None)]:
        b=before[before.index(begin):before.index(finish) if finish else None]
        a=after[after.index(begin):after.index(finish) if finish else None]
        assert re.sub(r'\s+','',a)==re.sub(r'\s+','',b)
    print('AI-use chapter revised; other chapters unchanged.')


if __name__=='__main__':
    import sys
    if '--word' in sys.argv:
        import integrate_layered_diagrams as d
        d.EDITOR=EDITOR;d.WORD=WORD;d.word()
    elif '--sync' in sys.argv:align.WORD=WORD;align.sync(EDITOR)
    else:build()
