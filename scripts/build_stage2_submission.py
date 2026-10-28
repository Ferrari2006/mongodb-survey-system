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
    p=OUT/(NAME+'-可编辑.html')
    html=p.read_text(encoding='utf-8').replace('报告草稿编辑版','报告编辑版').replace('第二阶段报告草稿','第二阶段项目报告')
    p.write_text(html,encoding='utf-8')
    manifest={'stage':'stage2-submission','source':SOURCE.relative_to(ROOT).as_posix(),
        'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'recorded_tests':observed['tests_run'],
        'files':[NAME+'-可编辑.html',NAME+'-可编辑.docx']}
    (OUT/'submission-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Stage-two submission HTML and Word created; previous drafts retained')

if __name__=='__main__':main()
