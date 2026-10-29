"""Check current patch separately from the retained submitted report and evidence."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def digest(path):
    raw=path.read_bytes()
    return {hashlib.sha256(raw).hexdigest(),hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()}

def main():
    from backend.database import SCHEMAS
    from check_stage2 import routes
    receipt=json.loads((ROOT/'tests/results/stage2-patch-manifest.json').read_text(encoding='utf-8'))
    for name,expected in receipt['files_sha256'].items():
        assert expected in digest(ROOT/name),'Patch evidence differs: '+name
    schema=json.loads((ROOT/'database/schema-stage2-patch.json').read_text(encoding='utf-8'))
    assert SCHEMAS==schema,'Patched Schema differs'
    observed=json.loads((ROOT/receipt['test_result']).read_text(encoding='utf-8'))
    assert observed['successful'] and observed['tests_run']==62
    assert len(observed['cases'])==62 and all(c['outcome']=='passed' for c in observed['cases'])
    submitted=ROOT/'第二阶段/提交材料'
    for name,expected in receipt['submitted_sha256'].items():
        assert expected in digest(ROOT/name),'Submitted material changed: '+name
    manifest=json.loads((submitted/'submission-manifest.json').read_text(encoding='utf-8'))
    assert manifest['recorded_tests']==58
    for name,expected in manifest['files_sha256'].items():
        assert expected in digest(submitted/name),'Submitted artifact changed: '+name
    for name,expected in manifest['stage1_preserved_sha256'].items():
        assert expected in digest(ROOT/name),'Stage-one evidence changed: '+name
    for name,expected in manifest['evidence_sha256'].items():
        assert expected in digest(ROOT/name),'Submitted evidence changed: '+name
    assert len(routes('backend/app.py')|routes('backend/library.py'))==36
    print('Post-submission patch: 62 observed tests passed; current application and Schema match patch receipt.')
    print('Submitted 8-page report, 58-test evidence and stage-one materials preserved; checked separately from patched code.')

if __name__=='__main__':main()
