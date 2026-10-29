"""Create new stage-two submission artifacts without modifying saved drafts."""
import hashlib
import json
from pathlib import Path
import sys
import build_stage2_draft as template

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'第二阶段/第二阶段完成报告.md'
OUT=ROOT/'第二阶段/提交材料'
NAME='2026_ECNU_PJ1_2_温正泽'

def main():
    OUT.mkdir(exist_ok=True)
    if (OUT/(NAME+'-可编辑.docx')).exists() and '--refresh' not in sys.argv:
        raise SystemExit('Existing submission preserved. Pass --refresh only for generated artifacts, not saved user edits.')
    observed=json.loads((ROOT/'tests/results/stage2-latest.json').read_text(encoding='utf-8'))
    assert observed['successful'] and observed['tests_run']==52
    for name in ('stage2-acceptance.json','stage2-reproduction.json'):
        assert json.loads((ROOT/'tests/results'/name).read_text(encoding='utf-8'))['successful']
    template.SOURCE=SOURCE;template.OUT=OUT;template.NAME=NAME
    blocks=template.blocks();template.build_html(blocks);template.build_word(blocks)
    from docx import Document
    from docx.oxml.ns import qn
    doc=Document(OUT/(NAME+'-可编辑.docx'))
    def set_fonts(paragraph, heading=False):
        for run in paragraph.runs:
            fonts=run._element.get_or_add_rPr().get_or_add_rFonts()
            for attr in list(fonts.attrib):
                if 'theme' in attr.lower():del fonts.attrib[attr]
            for attr in ('ascii','hAnsi','cs'):fonts.set(qn('w:'+attr),'Times New Roman')
            fonts.set(qn('w:eastAsia'),'黑体' if heading else '宋体')
            if heading:run.bold=False
    for paragraph in doc.paragraphs:
        set_fonts(paragraph,paragraph.style.name in ('Title','Heading 1','Heading 2'))
        if paragraph.text.startswith('附录 页面'):paragraph.paragraph_format.page_break_before=True
    for table in doc.tables:
        for i,row in enumerate(table.rows):
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    set_fonts(paragraph,heading=i==0)
                    if i==0:paragraph.paragraph_format.keep_with_next=True
    for section in doc.sections:
        for container in (section.header,section.footer):
            for paragraph in container.paragraphs:set_fonts(paragraph)
    doc.save(OUT/(NAME+'-可编辑.docx'))
    p=OUT/(NAME+'-可编辑.html')
    html=p.read_text(encoding='utf-8').replace('报告草稿编辑版','报告编辑版').replace('第二阶段报告草稿','第二阶段项目报告')
    html=html.replace('</style>','#report h2:last-of-type{break-before:page;page-break-before:always}</style>',1)
    html=html.replace('</style>','''#report{font-family:"Times New Roman","SimSun",serif;}
#report h1,#report h2,#report h3,#report th{font-family:"Times New Roman","SimHei",sans-serif;font-weight:400;}
</style>''',1)
    p.write_text(html,encoding='utf-8')
    manifest={'stage':'stage2-submission','source':SOURCE.relative_to(ROOT).as_posix(),
        'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'recorded_tests':observed['tests_run'],
        'files':[NAME+'-可编辑.html',NAME+'-可编辑.docx']}
    (OUT/'submission-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Stage-two submission HTML and Word created; previous drafts retained')

if __name__=='__main__':main()
