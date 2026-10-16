"""Ensure setup failures are recorded even before a test's timer starts."""
import io
import unittest
from tests.run_tests import RecordedResult


class RecordingTests(unittest.TestCase):
    def test_class_setup_failure_is_recorded(self):
        class BrokenSetup(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise RuntimeError("intentional setup failure")

            def test_never_runs(self):
                raise AssertionError("must not run")

        suite=unittest.defaultTestLoader.loadTestsFromTestCase(BrokenSetup)
        result=unittest.TextTestRunner(stream=io.StringIO(),resultclass=RecordedResult).run(suite)
        assert not result.wasSuccessful() and result.testsRun == 0
        assert len(result.errors) == 1 and len(result.records) == 1
        assert result.records[0]["outcome"] == "error"
        assert result.records[0]["seconds"] is None
