"""Run real tests and save their observed result, not a handwritten pass list."""
import json
import platform
import sys
import time
import unittest
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class RecordedResult(unittest.TextTestResult):
    def startTest(self, test):
        super().startTest(test)
        self.started = time.perf_counter()

    def record(self, test, outcome):
        records.append({"test": test.id(), "outcome": outcome,
                        "seconds": round(time.perf_counter() - self.started, 4)})

    def addSuccess(self, test):
        super().addSuccess(test)
        self.record(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.record(test, "failed")

    def addError(self, test, err):
        super().addError(test, err)
        self.record(test, "error")


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("Run without -O: these tests use Python assert.")
    records = []
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    report = {"executed_at_utc": datetime.now(timezone.utc).isoformat(),
              "python": platform.python_version(), "dependencies": {name: version(name) for name in ("Flask", "pymongo")},
              "database": "real MongoDB; random survey_test_ database, cleaned after integration tests",
              "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "successful": result.wasSuccessful(), "cases": records}
    destination = ROOT / "tests" / "results" / "latest.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
