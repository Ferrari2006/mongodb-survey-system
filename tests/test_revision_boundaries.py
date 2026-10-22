"""Bind every edit or state transition to the MongoDB snapshot it validated."""

from contextlib import contextmanager
from copy import deepcopy
import unittest
from unittest.mock import patch

import tests.test_api as api_tests


class RevisionBoundaryTests(unittest.TestCase):
    # Reuse setup helpers without importing an old TestCase into this module:
    # unittest discovery must not collect the previous API tests a second time.
    setUpClass = classmethod(api_tests.ApiTests.setUpClass.__func__)
    tearDownClass = classmethod(api_tests.ApiTests.tearDownClass.__func__)
    setUp = api_tests.ApiTests.setUp
    call = api_tests.ApiTests.call
    survey = api_tests.ApiTests.survey

    def draft_with_question(self):
        survey = self.survey()
        response = self.call("POST", f"/api/surveys/{survey['_id']}/questions", {
            "revision": survey["revision"],
            "question": {"id": "q1", "title": "选择", "type": "single",
                         "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]}})
        assert response.status_code == 200, response.json
        return response.json

    @contextmanager
    def write_after_owned_snapshot(self, survey, changes):
        """Arrange a competing real MongoDB write just after the route's read.

        No DB response is fabricated. Only the scheduling point is intercepted:
        the route receives its actual old snapshot after the competing update.
        """
        collection_type = type(self.db.surveys)
        original = collection_type.find_one
        fired = []
        target_namespace = self.db.surveys.full_name
        owner_id = self.db.users.find_one({"username": self.name})["_id"]
        owned_query = {"_id": survey["_id"], "owner_id": owner_id}

        def read_then_write(collection, query=None, *args, **kwargs):
            snapshot = original(collection, query, *args, **kwargs)
            if collection.full_name == target_namespace and query == owned_query and not fired:
                fired.append(True)
                result = self.db.surveys.update_one(
                    {"_id": survey["_id"], "revision": survey["revision"]},
                    {"$set": changes, "$inc": {"revision": 1}})
                assert result.matched_count == 1
            return snapshot

        with patch.object(collection_type, "find_one", new=read_then_write):
            yield
        assert fired == [True], "The test must interleave after the route reads its owned snapshot"

    def test_future_edit_revision_cannot_overwrite_competing_write(self):
        survey = self.survey()
        sid = survey["_id"]
        with self.write_after_owned_snapshot(survey, {"description": "另一个窗口刚保存的说明"}):
            response = self.call("PATCH", f"/api/surveys/{sid}", {
                "revision": survey["revision"] + 1, "title": "使用旧快照覆盖"})
        assert response.status_code == 409, response.json
        assert response.json["error"]["code"] == "revision_conflict"
        current = self.db.surveys.find_one({"_id": sid})
        assert current["title"] == survey["title"]
        assert current["description"] == "另一个窗口刚保存的说明"
        assert current["revision"] == survey["revision"] + 1

    def test_future_publish_revision_cannot_publish_unvalidated_questions(self):
        survey = self.draft_with_question()
        sid = survey["_id"]
        changed_questions = deepcopy(survey["questions"])
        # A dangling future target is permitted in a draft but must block publish.
        changed_questions[0]["jumps"] = [{"op": "eq", "value": "a", "target": "missing"}]
        with self.write_after_owned_snapshot(survey, {"questions": changed_questions}):
            response = self.call("POST", f"/api/surveys/{sid}/publish", {
                "revision": survey["revision"] + 1})
        assert response.status_code == 409, response.json
        current = self.db.surveys.find_one({"_id": sid})
        assert current["status"] == "draft"
        assert current["questions"] == changed_questions
        # A refreshed request must validate the new definition and reject it too.
        refreshed = self.call("POST", f"/api/surveys/{sid}/publish", {"revision": current["revision"]})
        assert refreshed.status_code == 400, refreshed.json

    def test_matching_revision_still_cas_rejects_write_after_snapshot(self):
        for operation in ("edit", "publish", "close"):
            with self.subTest(operation=operation):
                survey = self.draft_with_question()
                sid = survey["_id"]
                if operation == "close":
                    published = self.call("POST", f"/api/surveys/{sid}/publish", {"revision": survey["revision"]})
                    assert published.status_code == 200, published.json
                    survey = published.json
                with self.write_after_owned_snapshot(survey, {"description": "竞争写入已完成"}):
                    if operation == "edit":
                        response = self.call("PATCH", f"/api/surveys/{sid}", {
                            "revision": survey["revision"], "title": "过期编辑"})
                    else:
                        response = self.call("POST", f"/api/surveys/{sid}/{operation}", {
                            "revision": survey["revision"]})
                assert response.status_code == 409, response.json
                current = self.db.surveys.find_one({"_id": sid})
                assert current["status"] == survey["status"]
                assert current["description"] == "竞争写入已完成"

    def test_revision_type_and_state_errors_keep_existing_priority(self):
        survey = self.draft_with_question()
        sid = survey["_id"]
        for bad_revision in (True, "2", None):
            assert self.call("PATCH", f"/api/surveys/{sid}", {"revision": bad_revision}).status_code == 400
            assert self.call("POST", f"/api/surveys/{sid}/publish", {"revision": bad_revision}).status_code == 400
        # Invalid lifecycle state still takes precedence over a stale revision.
        assert self.call("POST", f"/api/surveys/{sid}/close", {"revision": 999}).status_code == 400
        published = self.call("POST", f"/api/surveys/{sid}/publish", {"revision": survey["revision"]})
        assert published.status_code == 200, published.json
        for bad_revision in (published.json["revision"] - 1, published.json["revision"] + 1):
            assert self.call("POST", f"/api/surveys/{sid}/close", {"revision": bad_revision}).status_code == 409
        assert self.call("PATCH", f"/api/surveys/{sid}", {"revision": 999}).status_code == 400
        assert self.call("POST", f"/api/surveys/{sid}/publish", {"revision": 999}).status_code == 400
        closed = self.call("POST", f"/api/surveys/{sid}/close", {"revision": published.json["revision"]})
        assert closed.status_code == 200, closed.json
        assert self.call("POST", f"/api/surveys/{sid}/close", {"revision": 999}).status_code == 400
