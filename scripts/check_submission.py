"""Read-only checks of stage-one deliverable consistency; does not run tests."""
import json
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
        if "data:image/png;base64," not in report:
            errors.append("Report screenshot must be embedded in the printable HTML")
    link = "https://github.com/Ferrari2006/mongodb-survey-system"
    if report.find(link) < 0 or not 0 <= report.find(link) < report.find("<h1>"):
        errors.append("Repository link must appear before report title")
    for name in ("README.md", "reports/第一阶段完成报告.md"):
        if f"{count}项" not in (ROOT / name).read_text(encoding="utf-8"):
            errors.append(f"Recorded test count missing in {name}")
    if f"{count}项" not in report:
        errors.append("HTML test count differs from recorded result")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"PASS: required files, schema, report and {count} recorded test results agree.")
    print("This checks saved evidence, not current code execution or PDF layout.")
    print("Still verify teacher repository access, print PDF, and confirm platform submission.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
