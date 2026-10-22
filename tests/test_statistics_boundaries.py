"""Real MongoDB regressions for large valid answers and coherent statistics."""
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from pymongo.collection import Collection

import tests.test_api as api_tests


class StatisticsBoundaryTests(unittest.TestCase):
    setUpClass = classmethod(api_tests.ApiTests.setUpClass.__func__)
    tearDownClass = classmethod(api_tests.ApiTests.tearDownClass.__func__)
    setUp = api_tests.ApiTests.setUp
    call = api_tests.ApiTests.call

    def ready(self, questions):
        survey = self.call("POST", "/api/surveys", {"title": "统计与容量回归", "allow_repeat": True}).json
        for q in questions:
            response = self.call("POST", f"/api/surveys/{survey['_id']}/questions", {"question": q, "revision": survey["revision"]})
            assert response.status_code == 200, response.json
            survey = response.json
        response = self.call("POST", f"/api/surveys/{survey['_id']}/publish", {"revision": survey["revision"]})
        assert response.status_code == 200, response.json
        return response.json

    def submit(self, survey, answers):
        return self.call("POST", f"/api/public/surveys/{survey['_id']}/responses", {"answers": answers, "request_id": uuid4().hex})

    def test_valid_long_chinese_progress_and_submission(self):
        questions = [{"id": f"q{i}", "title": f"文本{i}", "type": "text", "required": True} for i in range(20)]
        survey = self.ready(questions)
        answers = {q["id"]: "汉" * 5000 for q in questions}
        payload = {"answers": answers, "request_id": uuid4().hex, "revision": 0, "anonymous": False}
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        assert len(encoded) > 256 * 1024
        progress = self.client.put(f"/api/public/surveys/{survey['_id']}/progress", data=encoded,
                                   content_type="application/json", headers=self.headers)
        assert progress.status_code == 200, progress.json
        result = self.call("POST", f"/api/public/surveys/{survey['_id']}/responses", {
            "answers": answers, "request_id": payload["request_id"], "anonymous": False})
        assert result.status_code == 201, result.json
        stored = self.db.responses.find_one({"_id": result.json["id"]})
        assert len(stored["answers"]) == 20 and all(len(a["value"]) == 5000 for a in stored["answers"])

    def test_request_above_limit_is_rejected(self):
        limit = self.app.config["MAX_CONTENT_LENGTH"]
        body = b'{"username":"' + b'x' * limit + b'","password":"test-only-123"}'
        response = self.client.post("/api/auth/login", data=body, content_type="application/json")
        assert response.status_code == 413 and response.json["error"]

    def test_statistics_stay_coherent_when_submission_arrives_between_reads(self):
        survey = self.ready([
            {"id": "q1", "title": "选择", "type": "single", "required": True,
             "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]},
            {"id": "q2", "title": "分数", "type": "number", "required": True}])
        assert self.submit(survey, {"q1": "a", "q2": 0}).status_code == 201
        aggregate = Collection.aggregate
        inserted = False

        def read_then_submit(collection, *args, **kwargs):
            nonlocal inserted
            rows = list(aggregate(collection, *args, **kwargs))
            if collection.name == "responses" and collection.database.name == self.db.name and not inserted:
                inserted = True
                # Actual Mongo write scheduled immediately after a statistics read.
                assert self.submit(survey, {"q1": "a", "q2": 8}).status_code == 201
            return iter(rows)

        with patch.object(Collection, "aggregate", read_then_submit):
            response = self.call("GET", f"/api/surveys/{survey['_id']}/statistics")
        assert response.status_code == 200 and inserted
        stats = response.json
        single, number = stats["questions"]
        assert stats["response_count"] == single["answer_count"] == number["answer_count"]
        assert single["options"][0]["count"] == single["answer_count"]
        assert len(number["values"]) == number["answer_count"]
        assert number["average"] == sum(number["values"]) / len(number["values"])
        assert self.db.responses.count_documents({"survey_id": survey["_id"]}) == 2
        fresh = self.call("GET", f"/api/surveys/{survey['_id']}/statistics").json
        assert fresh["response_count"] == 2 and fresh["questions"][1]["average"] == 4
