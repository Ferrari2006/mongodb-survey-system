"""Validate the stage-two working tree without rewriting submitted stage-one evidence."""
import ast
import json
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def routes(file):
    result=set()
    for n in ast.walk(ast.parse((ROOT/file).read_text(encoding='utf-8'))):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('get','post','put','patch','delete') and n.args and isinstance(n.args[0],ast.Constant):
            path=n.args[0].value
            if isinstance(path,str) and path.startswith('/api/'):
                result.add((n.func.attr.upper(),re.sub(r'<([^>]+)>',r'{\1}',path)))
    return result

def main():
    from backend.database import SCHEMAS
    assert json.loads((ROOT/'database/schema-stage2.json').read_text(encoding='utf-8'))==SCHEMAS,'Stage-two schema mismatch'
    defined=routes('backend/app.py')|routes('backend/library.py')
    documented=set()
    for file in ('docs/API说明.md','第二阶段/API与测试说明.md'):
        for line in (ROOT/file).read_text(encoding='utf-8').splitlines():
            cells=[c.strip() for c in line.split('|')]
            if len(cells)>3 and cells[1] in ('GET','POST','PUT','PATCH','DELETE'):
                path=cells[2].split('?')[0]
                documented.add((cells[1],'/api'+path if not path.startswith('/api/') else path))
    assert defined==documented,f'Route mismatch: {defined^documented}'
    observed=json.loads((ROOT/'tests/results/stage2-latest.json').read_text(encoding='utf-8'))
    assert observed['successful'] and observed['tests_run']==len(observed['cases']) and all(c['outcome']=='passed' for c in observed['cases'])
    browser=json.loads((ROOT/'tests/results/stage2-browser.json').read_text(encoding='utf-8'))
    assert browser['successful'] and not browser['pageErrors']
    # The submission tag is the source of truth for the already submitted report.
    result=subprocess.run(['git','-c','safe.directory='+ROOT.as_posix(),'diff','--name-only','stage1-submission-20261023','--',
        'reports/','第一阶段/提交材料/','database/schema.json','tests/results/latest.json'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=True)
    assert not result.stdout.strip(),'Stage-one evidence changed: '+result.stdout
    draft=ROOT/'第二阶段/报告草稿/draft-manifest.json'
    if draft.exists():
        manifest=json.loads(draft.read_text(encoding='utf-8'))
        source=ROOT/'第二阶段/第二阶段完成报告草稿.md'
        assert hashlib.sha256(source.read_bytes()).hexdigest()==manifest['source_sha256'],'Draft source changed; regenerate drafts'
        assert manifest['recorded_tests']==observed['tests_run'],'Draft test count is stale'
        for name,digest in manifest['files_sha256'].items():
            assert hashlib.sha256((draft.parent/name).read_bytes()).hexdigest()==digest,'Draft changed: '+name
        print(f'Stage-two draft: {manifest["pdf_pages"]} pages; HTML/Word/PDF hashes match reviewed copies.')
    print(f'{len(SCHEMAS)} collections; {len(defined)} API routes; {observed["tests_run"]} observed tests passed; browser passed; stage-one report unchanged.')

if __name__=='__main__':main()
