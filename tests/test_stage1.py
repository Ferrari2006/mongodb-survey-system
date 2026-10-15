import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

from backend.app import now
from backend.database import SCHEMAS, migrate_drafts
from backend.logic import evaluate, validate_jumps
from backend.validation import DomainError, question
import tests.test_api as api_tests


def choice(qid="q1", kind="single", required=True, jumps=None):
    return {"id": qid, "title": qid, "type": kind, "required": required,
            "options": [{"id": x, "label": x.upper()} for x in "abc"],
            "jumps": jumps or []}


class JumpTests(unittest.TestCase):
    def test_single_branch_and_skipped_required(self):
        qs = [question(choice(jumps=[{"op": "eq", "value": "a", "target": "q3"}])),
              question({"id": "q2", "title": "被跳过的必答题", "type": "text", "required": True}),
              question({"id": "q3", "title": "年龄", "type": "number", "required": True})]
        assert evaluate(qs, {"q1": "a"})["next_question_id"] == "q3"
        result = evaluate(qs, {"q1": "a", "q3": 18}, complete=True)
        assert result["path"] == ["q1", "q3"]
        with self.assertRaises(DomainError):
            evaluate(qs, {"q1": "a", "q2": "伪造", "q3": 18}, complete=True)

    def test_multi_numeric_priority_and_default(self):
        qs = [question(choice(kind="multiple", jumps=[{"op": "any", "value": ["a"], "target": "END"},
                                                       {"op": "all", "value": ["a", "b"], "target": "q2"}])),
              question({"id": "q2", "title": "数值", "type": "number", "jumps": [{"op": "gte", "value": 18, "target": "END"}]}),
              question({"id": "q3", "title": "文字", "type": "text"})]
        assert evaluate(qs, {"q1": ["a", "b"]})["complete"]
        assert evaluate(qs, {"q1": ["c"]})["next_question_id"] == "q2"
        assert evaluate(qs, {"q1": ["c"], "q2": 18})["complete"]
        assert evaluate(qs, {"q1": ["c"], "q2": 17})["next_question_id"] == "q3"
        qs[0]["jumps"] = [{"op": "all", "value": ["a", "b"], "target": "END"}]
        assert evaluate(qs, {"q1": ["a", "b"]})["complete"]
        assert evaluate(qs, {"q1": ["a"]})["next_question_id"] == "q2"
        for op, value, expected in (("eq",18,True),("lt",17,True),("lt",18,False),
                                    ("lte",18,True),("gt",19,True),("gt",18,False),("gte",18,True)):
            numeric = [question({"id":"n1","title":"数值","type":"number","jumps":[{"op":op,"value":18,"target":"END"}]}),
                       question({"id":"n2","title":"后续","type":"text"})]
            with self.subTest(op=op,value=value):
                assert evaluate(numeric, {"n1":value})["complete"] is expected

    def test_reject_cycles_missing_target_bad_rule(self):
        for rule in ({"op":"eq","value":"a","target":"q1"}, {"op":"eq","value":"a","target":"missing"},
                     {"op":"eq","value":"z","target":"END"}, {"op":"bad","value":"a","target":"END"}):
            with self.subTest(rule=rule), self.assertRaises(DomainError):
                validate_jumps([question(choice(jumps=[rule]))], publishing=True)

    def test_missing_and_optional_answers(self):
        qs = [question({"id":"q1","title":"选答","type":"text"})]
        assert evaluate(qs, {})["next_question_id"] == "q1"
        assert evaluate(qs, {"q1": None}, complete=True)["answers"] == []
        with self.assertRaises(DomainError):
            evaluate(qs, {}, complete=True)
        with self.assertRaises(DomainError):
            evaluate(qs, {"unknown": "x"})


class Stage1Tests(unittest.TestCase):
    setUpClass = classmethod(api_tests.ApiTests.setUpClass.__func__)
    tearDownClass = classmethod(api_tests.ApiTests.tearDownClass.__func__)
    setUp = api_tests.ApiTests.setUp
    call = api_tests.ApiTests.call
    survey = api_tests.ApiTests.survey

    def ready(self, questions=None, repeat=False, anonymous=False):
        survey = self.call("POST", "/api/surveys", {"title": "完整流程测试", "allow_repeat": repeat,
                           "allow_anonymous": anonymous}).json
        for q in questions or [choice()]:
            r = self.call("POST", f"/api/surveys/{survey['_id']}/questions", {"revision": survey["revision"], "question": q})
            assert r.status_code == 200, r.json
            survey = r.json
        r = self.call("POST", f"/api/surveys/{survey['_id']}/publish", {"revision": survey["revision"]})
        assert r.status_code == 200, r.json
        return r.json

    def submit(self, survey, answers=None, anonymous=False, request_id=None):
        return self.call("POST", f"/api/public/surveys/{survey['_id']}/responses", {
            "answers": answers or {"q1": "a"}, "anonymous": anonymous, "request_id": request_id or uuid4().hex})

    def test_publish_share_close_and_freeze(self):
        empty = self.survey()
        sid = empty["_id"]
        assert self.call("POST", f"/api/surveys/{sid}/publish", {"revision": 1}).status_code == 400
        assert self.call("GET", f"/api/public/surveys/{sid}").status_code == 404
        survey = self.ready()
        sid = survey["_id"]
        assert self.client.get(f"/survey/{sid}").status_code == 200
        assert self.client.get(f"/api/public/surveys/{sid}").status_code == 401
        assert self.call("GET", f"/api/public/surveys/{sid}").status_code == 200
        assert self.call("PATCH", f"/api/surveys/{sid}", {"revision": survey["revision"], "title":"试图修改"}).status_code == 400
        assert self.call("POST", f"/api/surveys/{sid}/close", {"revision": survey["revision"]}).status_code == 200
        assert self.submit(survey).status_code == 404

    def test_deadline_and_invalid_publication(self):
        assert self.call("POST", "/api/surveys", {"title":"x", "deadline":"2027-01-01T00:00"}).status_code == 400
        assert self.call("POST", "/api/surveys", {"title":"x", "allow_repeat":"yes"}).status_code == 400
        survey = self.ready()
        self.db.surveys.update_one({"_id":survey["_id"]}, {"$set":{"deadline":now()-timedelta(seconds=1)}})
        assert self.submit(survey).status_code == 410
        assert self.call("GET", f"/api/public/surveys/{survey['_id']}").status_code == 410
        draft = self.survey()
        draft = self.call("POST", f"/api/surveys/{draft['_id']}/questions", {"revision":1, "question":choice(jumps=[{"op":"eq","value":"a","target":"unknown"}])}).json
        assert self.call("POST", f"/api/surveys/{draft['_id']}/publish", {"revision":draft["revision"]}).status_code == 400

    def test_submission_repeat_and_idempotency(self):
        survey = self.ready()
        request_id = uuid4().hex
        first = self.submit(survey, request_id=request_id)
        assert first.status_code == 201
        again = self.submit(survey, request_id=request_id)
        assert again.status_code == 200 and again.json["id"] == first.json["id"]
        assert self.submit(survey).status_code == 409
        assert self.db.responses.count_documents({"survey_id":survey["_id"]}) == 1
        def different_user(_):
            with self.app.test_client() as client:
                name="u"+uuid4().hex[:12]
                client.post("/api/auth/register",json={"username":name,"password":"Other-pass-123"})
                token=client.post("/api/auth/login",json={"username":name,"password":"Other-pass-123"}).json["token"]
                return client.post(f"/api/public/surveys/{survey['_id']}/responses",headers={"Authorization":"Bearer "+token},
                                   json={"answers":{"q1":"b"},"request_id":uuid4().hex}).status_code
        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses=list(pool.map(different_user,range(4)))
        assert statuses == [201]*4, statuses
        assert self.db.responses.count_documents({"survey_id":survey["_id"]}) == 5
        repeat = self.ready(repeat=True)
        assert self.submit(repeat).status_code == 201
        assert self.submit(repeat).status_code == 201

    def test_concurrent_nonrepeat_submission(self):
        survey = self.ready()
        def send(_):
            with self.app.test_client() as client:
                return client.post(f"/api/public/surveys/{survey['_id']}/responses", headers=self.headers,
                                   json={"answers":{"q1":"a"}, "request_id":uuid4().hex}).status_code
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(send, range(4)))
        assert sorted(results) == [201,409,409,409], results
        assert self.db.responses.count_documents({"survey_id":survey["_id"]}) == 1

    def test_anonymous_visibility_and_permissions(self):
        survey = self.ready(anonymous=True)
        assert self.submit(survey, anonymous=True).status_code == 201
        result = self.call("GET", f"/api/surveys/{survey['_id']}/responses").json
        item = result["items"][0]
        assert item["respondent"] == "匿名"
        assert not {"user_id","submission_key","request_id"} & set(item)
        normal = self.ready()
        assert self.submit(normal, anonymous=True).status_code == 400
        assert self.submit(normal).status_code == 201
        assert self.call("GET", f"/api/surveys/{normal['_id']}/responses").json["items"][0]["respondent"] == self.name
        other = self.app.test_client()
        name="u"+uuid4().hex[:12]
        other.post("/api/auth/register",json={"username":name,"password":"Other-pass-123"})
        t=other.post("/api/auth/login",json={"username":name,"password":"Other-pass-123"}).json["token"]
        for suffix in ("statistics", "responses"):
            assert other.get(f"/api/surveys/{survey['_id']}/{suffix}",headers={"Authorization":"Bearer "+t}).status_code == 404
        assert other.get(f"/api/public/surveys/{survey['_id']}",headers={"Authorization":"Bearer "+t}).status_code == 200

    def test_server_path_and_no_invalid_writes(self):
        survey = self.ready([choice(jumps=[{"op":"eq","value":"a","target":"q3"}]),
                             {"id":"q2","title":"必答被跳过","type":"text","required":True},
                             {"id":"q3","title":"数字","type":"number","required":True,"validation":{"min":0,"max":120}}], repeat=True)
        assert self.submit(survey, {"q1":"a","q3":121}).status_code == 400
        assert self.submit(survey, {"q1":"a","q2":"伪造","q3":18}).status_code == 400
        assert self.submit(survey, {"q1":"b","q3":18}).status_code == 400
        assert self.db.responses.count_documents({"survey_id":survey["_id"]}) == 0
        assert self.submit(survey, {"q1":"a","q3":18}).status_code == 201
        assert self.db.responses.find_one({"survey_id":survey["_id"]})["path"] == ["q1","q3"]

    def test_aggregation_exact_counts_and_average(self):
        survey = self.ready([choice(), choice("q2","multiple"),
                             {"id":"q3","title":"分数","type":"number"},
                             {"id":"q4","title":"备注","type":"text"}], repeat=True)
        rows = [{"q1":"a","q2":["a","b"],"q3":10,"q4":"甲"},
                {"q1":"b","q2":["b"],"q3":20,"q4":"乙"},
                {"q1":"a","q2":["a"],"q3":None,"q4":None}]
        for answers in rows:
            assert self.submit(survey, answers).status_code == 201
        stats = self.call("GET", f"/api/surveys/{survey['_id']}/statistics").json
        assert stats["response_count"] == 3
        q1,q2,q3,q4 = stats["questions"]
        assert [o["count"] for o in q1["options"]] == [2,1,0]
        assert [o["count"] for o in q2["options"]] == [2,2,0]
        assert q3["average"] == 15 and q3["answer_count"] == 2
        assert sorted(q4["values"]) == ["乙","甲"]
        single = self.call("GET", f"/api/surveys/{survey['_id']}/questions/q3/statistics").json
        assert len(single["questions"]) == 1 and single["questions"][0]["average"] == 15

    def test_empty_statistics_and_legacy_migration(self):
        survey = self.ready([{"id":"q1","title":"数字","type":"number"}])
        stats = self.call("GET", f"/api/surveys/{survey['_id']}/statistics").json
        assert stats["response_count"] == 0 and stats["questions"][0]["average"] is None
        # Emulate the known original validator; migration preserves existing data.
        old = {**SCHEMAS["surveys"], "properties":{**SCHEMAS["surveys"]["properties"], "status":{"enum":["draft"]}}}
        self.db.command("collMod","surveys",validator={"$jsonSchema":old})
        try:
            before=self.db.surveys.count_documents({})
            assert migrate_drafts(self.db) == before
            assert migrate_drafts(self.db) == before
            assert self.db.surveys.find_one({"_id":survey["_id"]})["title"] == survey["title"]
        finally:
            self.db.command("collMod","surveys",validator={"$jsonSchema":SCHEMAS["surveys"]})
