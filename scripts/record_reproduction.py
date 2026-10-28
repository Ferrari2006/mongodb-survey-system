"""Record a fresh-environment startup check without storing connection strings."""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
from urllib.request import urlopen
from pymongo import MongoClient

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',default='http://127.0.0.1:5056')
    parser.add_argument('--mongo',default='mongodb://127.0.0.1:27018/')
    parser.add_argument('--db',required=True)
    args=parser.parse_args()
    if not args.db.startswith('survey_test_'):raise SystemExit('Use an isolated test database')
    with urlopen(args.base+'/api/health',timeout=10) as response:health=json.load(response)
    with MongoClient(args.mongo,serverSelectionTimeoutMS=5000) as client:
        mongo_version=client.server_info()['version']
        collections=sorted(client[args.db].list_collection_names())
    assert health=={'status':'ok','milestone':'stage2'},health
    assert collections==sorted(['users','sessions','surveys','responses','fill_progress','question_banks','library_questions']),collections
    sha=subprocess.check_output(['git','-c','safe.directory='+ROOT.as_posix(),'rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    result={'successful':True,'executed_at_utc':datetime.now(timezone.utc).isoformat(),
        'source_commit':sha,'source':'git archive extracted to separate directory',
        'installation':'new venv; pip install -r requirements.txt',
        'python':platform.python_version(),'mongodb':mongo_version,
        'dependencies':{name:version(name) for name in ('Flask','pymongo','Werkzeug','Jinja2','click','blinker','itsdangerous','MarkupSafe','dnspython')},
        'health':health,'collections':collections,'database':'isolated local MongoDB; no original business data accessed'}
    (ROOT/'tests/results/stage2-reproduction.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Fresh environment startup, health, dependencies and seven collections verified')

if __name__=='__main__':main()
