"""Refine saved report wording and editing ergonomics without replacing drafts."""
import hashlib
import json
import re
from pathlib import Path

from export_editable_report import NAME, OUTPUT, ROOT, Reader, Element, make_word
from layout_academic_report import nodes, data_uri, configure_word

SOURCE = OUTPUT / (NAME + '-排版核对编辑版.html')
TARGET = OUTPUT / (NAME + '-科学复核优化版.html')
WORD = OUTPUT / (NAME + '-科学复核可编辑.docx')
QA = ROOT / 'tmp/science-refinement'

CHANGES = [
('这些设计把填写连续性、路径正确性和统计可复核性联系起来，代码与验证记录对应说明其作用。',
 '下文结合集合、填写流程和测试记录说明这些设计的作用与限制。'),
('Lab2的CRUD、条件查询和嵌套字段应用于账号、问卷、题目和答卷管理；Lab3的索引、数组展开及分组聚合用于防重和统计。数据库操作与业务目的对应：例如多选答案先展开再计数，数字使用avg，条件更新和唯一索引用于处理并发，未为展示语法增加无用功能。',
 'Lab2的CRUD、条件查询和嵌套字段用于账号、问卷与答卷管理；Lab3的索引和聚合用于防重与统计。具体包括展开多选答案后计数、用$avg求数字均值，以及用条件更新和唯一索引处理并发。'),
('2026年10月21日的独立浏览器检查使用3份合成答卷：1份跳过多选与数字题，另外2份均选择图书馆和食堂，数字分别为0和8。因此多选本题分母为2，两项各100%，数字平均4。图中分母取实际回答该题的份数，不能用整卷3份替代。',
 '图2使用2026年10月21日的独立合成问卷，核对跳题后的单题分母、零次选项和数值0的处理。该图与表5使用不同测试数据：图2检查界面统计口径，表5验证API聚合结果，二者不能混合计数。'),
('在第一阶段完善时，AI复核“每次填写都应该被保存”的解释风险，提出独立fill_progress方案，新增GET/PUT接口、进度修订号和提交清理；随后用数据库及浏览器验证恢复、分支修改、匿名偏好和统计隔离。该方案及代码由AI提出并实施，人工提供任务和保留既有成果的约束，未将其改写成学生独立发明。',
 '复核“每次填写都应该被保存”时，AI提出独立fill_progress方案，补充GET/PUT接口、进度修订号及提交清理，并用数据库和浏览器验证恢复、分支修改、匿名偏好与统计隔离。人工提出任务及保留已有成果的约束，方案和代码由AI提出并实施。'),
('AI生成的方案与代码需要同时检查需求解释、边界输入和完整流程。开发中实际遇到以下情况，修正由AI根据复核与用户反馈实施；人工提出的问题和AI执行的修改分别记录。',
 '表8归纳AI输出在需求解释、边界和完整流程中的问题。人工反馈与AI复核共同推动修正，执行者及验证依据保留在日志中。'),
('对需求措辞的解释不够具体。“每次填写保存”没有单独明确未提交进度的恢复行为',
 '“每次填写保存”未明确未提交进度如何恢复'),
('需求复核后明确已确认进度与正式答卷的区别，新增fill_progress及恢复、清理规则',
 '区分已确认进度和正式答卷，补充fill_progress及恢复、清理规则'),
('生成校验遗漏边界。空数组可能被当成选填文本空值，整数范围0.2～0.8没有合法整数',
 '校验遗漏空数组类型和0.2～0.8内无整数的边界'),
('代码复核后收紧类型判断，在题目定义时检查区间内存在整数，并补回归',
 '收紧类型判断，定义题目时检查整数区间，并补回归'),
('单个步骤看似正确，组合后仍有缺口。多次统计可能读到不同批答卷；合法整卷文本可能超过请求上限；版本条件未绑定校验快照',
 '组合流程遗漏统计读取一致性、整卷容量及校验快照绑定'),
('对完整数据流和并发时序补检查，改用同批facet、协调容量并绑定revision；用真实数据库验证',
 '改用同批facet，协调请求上限并绑定revision；用真实数据库回归'),
('输出方向需要进一步约束。按参考组织报告后，用户要求突出原有功能及课堂重点',
 '参考报告的组织方式未充分突出本项目功能和课堂重点'),
('根据明确反馈，以本项目进度、路径、答卷与统计重组正文，保留功能和历史，不移用参考经历',
 '按用户反馈重组进度、路径、答卷与统计的说明，保留功能及历史'),
('自动化执行还出现过工具适配问题：AI生成的多行浏览器脚本直接传入Windows终端时报解析错误，改为从文件加载；包含原生确认框的脚本被CLI中断，改用API准备测试前置数据后重新执行。它们属于验证工具与脚本配合的问题，不能等同业务算法错误，也不能将中断的运行记为通过。最终完整成功执行才写入结果记录。',
 '工具执行也出现过失败：多行浏览器脚本传入Windows终端时报解析错误，改为从文件加载；原生确认框导致CLI中断，改用API准备前置数据后重跑。失败过程保留，只有最终完整执行才记为通过，并与业务算法问题区分。'),
('这些经历说明，给AI的任务需要明确保存语义、业务边界和验收样例；得到代码后仍要检查实际入库结果。遇到异常先确认属于需求、程序还是环境，再要求AI修改对应部分，并保留修正前后的证据。',
 '后续引导AI时，应先明确保存语义、业务边界和验收样例，再检查实际入库结果；定位需求、程序或环境问题后，修改对应部分并保留证据。'),
('人工参与集中在明确要求、选择开发重点、纠正参考使用方向和反馈验收目标；具体Schema、规则解释器和代码修正主要由AI完成。现有结论依据保存的自动化与浏览器记录，不将尚未记录的个人操作写成已完成验收。实际各轮模型未核实，不推测填写。',
 '人工负责明确要求、选择开发重点、纠正参考使用方向及反馈验收目标；Schema、规则解释器和代码修正主要由AI完成。结果依据已保存的自动化及浏览器记录，未记录的个人操作不列为验收；各轮实际模型未核实。'),
]


def create_html():
    if TARGET.exists():raise SystemExit('Refinement exists; preserve edits.')
    source=SOURCE.read_text(encoding='utf-8');html=source
    for old,new in CHANGES:
        if html.count(old)!=1:raise ValueError('Saved source changed; review before replacement: '+old[:30])
        html=html.replace(old,new)
    attribution='<p class="tool-reference">报告辅助工具：Scientific Writing与Scientific Visualization用于表述一致性及图表检查。来源：Kassis T., Agarwal V., He Y., Patel D., Brueckner A. M. (2026). <em>Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents</em>. <a href="https://doi.org/10.48550/arXiv.2609.00065">doi:10.48550/arXiv.2609.00065</a>。</p>'
    html=html.replace('<h2>七、总结与后续演进</h2>',attribution+'<h2>七、总结与后续演进</h2>')
    extra='#report .tool-reference{font-size:9pt;line-height:1.45;color:#444;margin:8pt 0}#section-nav{max-width:230px;padding:7px;border:1px solid #718291;border-radius:4px;font:13px Microsoft YaHei}#report h2{scroll-margin-top:100px}'
    html=html.replace('</style>',extra+'</style>',1)
    html=html.replace('<strong>报告排版核对版</strong>','<strong>报告科学复核版</strong><label for="section-nav">章节</label><select id="section-nav" aria-label="跳转到报告章节"><option value="">选择章节</option></select>',1)
    html=html.replace(NAME+'-排版核对-我的修改.html',NAME+'-科学复核-我的修改.html')
    html=html.replace('<title>第一阶段报告 排版核对编辑版</title>','<title>第一阶段报告 科学复核优化版</title>')
    navigation="""<script>(()=>{const nav=document.getElementById('section-nav');document.querySelectorAll('#report h2').forEach((heading,i)=>{heading.id='report-section-'+(i+1);const option=document.createElement('option');option.value=heading.id;option.textContent=heading.textContent;nav.append(option)});nav.addEventListener('change',()=>{if(nav.value)document.getElementById(nav.value).scrollIntoView({behavior:'smooth',block:'start'})});document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();document.getElementById('save-copy').click()}})})();</script>"""
    # Regenerate options on each load so saved copies do not accumulate them.
    navigation=navigation.replace("const nav=document.getElementById('section-nav');", "const nav=document.getElementById('section-nav');nav.replaceChildren(new Option('选择章节',''));")
    html=html.replace('</body>',navigation+'</body>')
    TARGET.write_text(html,encoding='utf-8')
    QA.mkdir(parents=True,exist_ok=True)
    (QA/'rewrites.json').write_text(json.dumps({'source':SOURCE.name,'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'edits':CHANGES,'new_html':TARGET.name},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Saved separate refinement HTML.')


def create_word():
    if WORD.exists():raise SystemExit('Word refinement exists; preserve it.')
    reader=Reader();reader.feed(TARGET.read_text(encoding='utf-8'))
    report=next(n for n in nodes(reader.root) if n.attrs.get('id')=='report')
    for n in list(nodes(report)):
        n.children=[c for c in n.children if not(isinstance(c,Element) and c.tag=='colgroup')]
        if n.tag=='img':
            name='stage1-data-model-refined' if '五集合' in n.attrs.get('alt','') else 'stage1-statistics-academic'
            n.attrs['src']=data_uri(ROOT/'reports/images'/(name+'.png'),'image/png')
            n.attrs['data-word-width-cm']='16.8'
    make_word(report,WORD)
    configure_word(WORD)
    from docx import Document
    from docx.shared import Pt
    doc=Document(WORD)
    for p in doc.paragraphs:
        if p.text.startswith('报告辅助工具：'):
            p.paragraph_format.line_spacing=1.25
            for r in p.runs:r.font.size=Pt(9)
    doc.save(WORD)
    print('Saved separate refinement Word.')


if __name__=='__main__':
    import sys
    create_word() if '--word' in sys.argv else create_html()
