"""Read-only checks of stage-one deliverable consistency; does not run tests."""
import json
import ast
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from backend.database import SCHEMAS
    errors = []
    required = ["README.md", "requirements.txt", ".env.example", "run.py",
                "backend/app.py", "frontend/index.html", "frontend/app.js",
                "database/schema.json", "docs/API说明.md", "docs/数据库与系统设计.md",
                "docs/测试说明.md", "docs/操作与演示.md", "tests/run_tests.py",
                "tests/results/latest.json", "reports/第一阶段完成报告.md",
                "reports/第一阶段完成报告.html",
                "第一阶段/提交材料/2026_ECNU_PJ1_1_温正泽.html"]
    for name in required:
        p = ROOT / name
        if not p.is_file() or p.stat().st_size == 0:
            errors.append(f"Missing or empty: {name}")
    if errors:
        print("\n".join(errors))
        return 1
    if not list((ROOT / "ai_logs").glob("*.md")):
        errors.append("Missing AI collaboration records")
    schema = json.loads((ROOT / "database/schema.json").read_text(encoding="utf-8"))
    if schema != SCHEMAS:
        errors.append("Schema export differs from backend; run scripts/export_materials.py")
    result = json.loads((ROOT / "tests/results/latest.json").read_text(encoding="utf-8"))
    cases = result.get("cases", [])
    count = result.get("tests_run", 0)
    if not result.get("successful") or result.get("errors") != 0 or result.get("failures") != 0:
        errors.append("Latest recorded test execution did not pass")
    if count <= 0 or len(cases) != count or any(c.get("outcome") != "passed" for c in cases):
        errors.append("Test case records do not match successful test count")
    report = (ROOT / "reports/第一阶段完成报告.html").read_text(encoding="utf-8")
    submission = (ROOT / "第一阶段/提交材料/2026_ECNU_PJ1_1_温正泽.html").read_text(encoding="utf-8")
    if report != submission:
        errors.append("Submission HTML differs from report HTML")
    if "![" in (ROOT / "reports/第一阶段完成报告.md").read_text(encoding="utf-8"):
        if not any(t in report for t in ("data:image/png;base64,", "data:image/svg+xml;base64,")):
            errors.append("Report figures must be embedded in the printable HTML")
    link = "https://github.com/Ferrari2006/mongodb-survey-system"
    if report.find(link) < 0 or not 0 <= report.find(link) < report.find("<h1>"):
        errors.append("Repository link must appear before report title")
    for name in ("README.md", "reports/第一阶段完成报告.md"):
        if f"{count}项" not in (ROOT / name).read_text(encoding="utf-8"):
            errors.append(f"Recorded test count missing in {name}")
    if f"{count}项" not in report:
        errors.append("HTML test count differs from recorded result")
    manifest_path = ROOT / "reports/stage1-report-manifest.json"
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        for name, digest in {**manifest["files_sha256"], **manifest["evidence_sha256"]}.items():
            path=ROOT/name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                errors.append(f"Changed after report alignment; review and sync: {name}")
        from align_stage1_delivery import body_hash
        for name in (manifest["editor"],manifest["printable"],manifest["submission"]):
            if body_hash((ROOT/name).read_text(encoding="utf-8"))!=manifest["normalized_body_sha256"]:
                errors.append(f"Report bodies differ: {name}")
        if manifest["recorded_tests"]!=count:
            errors.append("Aligned report test count differs from latest evidence")
    # Compare the full documented API table with the Flask route definitions.
    defined=set()
    for node in ast.walk(ast.parse((ROOT/'backend/app.py').read_text(encoding='utf-8'))):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in ('get','post','put','patch','delete') and node.args and isinstance(node.args[0],ast.Constant):
            path=node.args[0].value
            if isinstance(path,str) and path.startswith('/api/'):
                defined.add((node.func.attr.upper(),re.sub(r'<([^>]+)>',r'{\1}',path)))
    documented=set()
    for line in (ROOT/'docs/API说明.md').read_text(encoding='utf-8').splitlines():
        cells=[c.strip() for c in line.split('|')]
        if len(cells)>3 and cells[1] in ('GET','POST','PUT','PATCH','DELETE'):
            documented.add((cells[1],'/api'+cells[2].split('?')[0]))
    if defined!=documented:
        errors.append(f"API route mismatch: undocumented={sorted(defined-documented)}, unimplemented={sorted(documented-defined)}")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"PASS: required files, schema, {len(defined)} API routes, report copies and {count} recorded test results agree.")
    print("This checks saved evidence, not current code execution or PDF layout.")
    print("Still review the final PDF and confirm platform submission; repository visibility is checked separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
