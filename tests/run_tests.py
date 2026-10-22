"""Run real tests and save their observed result, not a handwritten pass list."""
import json
import argparse
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []
        self.started = {}

    def startTest(self, test):
        super().startTest(test)
        self.started[test.id()] = time.perf_counter()

    def record(self, test, outcome):
        started = self.started.get(test.id())
        self.records.append({"test": test.id(), "outcome": outcome,
                             "seconds": round(time.perf_counter() - started, 4) if started is not None else None})

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
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='tests/results/stage2-latest.json', help='Observed result path relative to repository')
    args = parser.parse_args()
    if not __debug__:
        raise SystemExit("Run without -O: these tests use Python assert.")
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    report = {"executed_at_utc": datetime.now(timezone.utc).isoformat(),
              "python": platform.python_version(), "dependencies": {name: version(name) for name in ("Flask", "pymongo")},
              "database": "real MongoDB; random survey_test_ database, cleaned after integration tests",
              "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "successful": result.wasSuccessful(), "cases": result.records}
    destination = (ROOT / args.output).resolve()
    if not destination.is_relative_to(ROOT / 'tests' / 'results'):
        raise SystemExit('Result must stay inside tests/results')
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    raise SystemExit(0 if result.wasSuccessful() else 1)
