"""Persisted valid prefixes, account isolation and optimistic progress revisions."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

from backend.app import now
import tests.test_stage1 as stage


class ProgressTests(unittest.TestCase):
    setUpClass = classmethod(stage.Stage1Tests.setUpClass.__func__)
    tearDownClass = classmethod(stage.Stage1Tests.tearDownClass.__func__)
    setUp = stage.Stage1Tests.setUp
    call = stage.Stage1Tests.call
    ready = stage.Stage1Tests.ready
    submit = stage.Stage1Tests.submit

    def fixture(self, repeat=False):
        survey = self.ready([stage.choice(jumps=[{"op":"eq", "value":"a", "target":"q3"}]),
                             {"id":"q2", "title":"必答文字", "type":"text", "required":True},
                             {"id":"q3", "title":"数字", "type":"number", "required":True,
                              "validation":{"min":0,"max":120}}], repeat=repeat, anonymous=True)
        return survey, f"/api/public/surveys/{survey['_id']}/progress"

    def test_restore_prefix_isolation_and_no_statistics(self):
        survey, url = self.fixture()
        assert self.client.get(url).status_code == 401
        assert self.call("GET",url).json == {"progress":None}
        body = {"answers":{"q1":"a"}, "revision":0, "anonymous":True, "request_id":uuid4().hex}
        assert self.call("PUT",url,body).json["revision"] == 1
        # A new HTTP client models a refresh; state resides in MongoDB, not process memory.
        restored = self.app.test_client().get(url,headers=self.headers).json["progress"]
        assert restored["answers"] == {"q1":"a"} and restored["anonymous"] is True
        assert not {"user_id","_id"} & set(restored)
        other = self.app.test_client()
        name = "u"+uuid4().hex[:12]
        other.post("/api/auth/register",json={"username":name,"password":"Other-pass-123"})
        token = other.post("/api/auth/login",json={"username":name,"password":"Other-pass-123"}).json["token"]
        assert other.get(url,headers={"Authorization":"Bearer "+token}).json["progress"] is None
        assert self.call("GET",f"/api/surveys/{survey['_id']}/statistics").json["response_count"] == 0
        assert self.call("GET",f"/api/surveys/{survey['_id']}/responses").json["total"] == 0

    def test_validation_branch_changes_and_submit_cleanup(self):
        survey,url = self.fixture()
        rid = uuid4().hex
        body = {"answers":{"q1":"a","q3":0},"revision":0,"request_id":rid}
        assert self.call("PUT",url,body).status_code == 200
        # Returning to the first question deletes the valid suffix, including a legal zero answer.
        assert self.call("PUT",url,{**body,"revision":1,"answers":{}}).json["revision"] == 2
        for bad in ({"q1":"a","q2":"hidden"}, {"q1":"b","q3":0}, {"q1":"a","q3":121}):
            assert self.call("PUT",url,{**body,"revision":2,"answers":bad}).status_code == 400
        assert self.call("GET",url).json["progress"]["answers"] == {}
        answers = {"q1":"b","q2":"修改分支","q3":0}
        assert self.call("PUT",url,{**body,"revision":2,"answers":answers}).json["revision"] == 3
        first = self.submit(survey,answers=answers,request_id=rid)
        assert first.status_code == 201
        assert self.call("GET",url).json["progress"] is None
        assert self.call("PUT",url,{**body,"revision":0}).status_code == 409
        assert self.submit(survey,answers=answers,request_id=rid).json["id"] == first.json["id"]
        assert self.db.responses.count_documents({"survey_id":survey['_id']}) == 1

    def test_concurrent_progress_and_survey_availability(self):
        survey,url = self.fixture(repeat=True)
        body = {"answers":{"q1":"a"},"revision":0,"request_id":uuid4().hex}
        def send(_):
            with self.app.test_client() as client:
                return client.put(url,headers=self.headers,json=body).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(send,range(2))) == [200,409]
        assert self.call("PUT",url,{**body,"revision":1}).json["revision"] == 2
        assert self.call("PUT",url,{**body,"revision":1}).status_code == 409
        assert self.call("PUT",url,{**body,"revision":2,"request_id":uuid4().hex}).status_code == 409
        self.db.surveys.update_one({"_id":survey['_id']},{"$set":{"deadline":now()-timedelta(seconds=1)}})
        assert self.call("GET",url).status_code == 410
        assert self.call("PUT",url,{**body,"revision":2}).status_code == 410

    def test_repeat_attempts_keep_distinct_submissions(self):
        survey,url = self.fixture(repeat=True)
        for _ in range(2):
            rid = uuid4().hex
            body = {"answers":{"q1":"a","q3":0},"revision":0,"request_id":rid}
            assert self.call("PUT",url,body).status_code == 200
            assert self.submit(survey,answers=body["answers"],request_id=rid).status_code == 201
            assert self.call("GET",url).json["progress"] is None
        assert self.db.responses.count_documents({"survey_id":survey['_id']}) == 2

    def test_zero_numeric_jump(self):
        qs = [stage.question({"id":"q1","title":"零值分支","type":"number", "required":True,
                              "jumps":[{"op":"eq","value":0,"target":"END"}]}),
              stage.question({"id":"q2","title":"后续必答","type":"text","required":True})]
        assert stage.evaluate(qs,{"q1":0},complete=True)["path"] == ["q1"]
