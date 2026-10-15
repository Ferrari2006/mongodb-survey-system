"""Real MongoDB integration tests; only delete the randomly named test database."""
import hashlib
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

from pymongo.errors import WriteError
from backend.app import create_app, now


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_name = "survey_test_" + uuid4().hex
        cls.app = create_app({"TESTING": True, "MONGO_DB": cls.db_name,
                              "MONGO_URI": os.getenv("TEST_MONGO_URI", "mongodb://127.0.0.1:27017/")})
        cls.db = cls.app.extensions["db"]

    @classmethod
    def tearDownClass(cls):
        if not cls.db_name.startswith("survey_test_"):
            raise RuntimeError("Refusing to delete a non-test database")
        cls.app.extensions["mongo_client"].drop_database(cls.db_name)
        cls.app.extensions["mongo_client"].close()

    def setUp(self):
        self.client = self.app.test_client()
        self.name = "u" + uuid4().hex[:12]
        self.client.post("/api/auth/register", json={"username": self.name, "password": "Test-only-123"})
        login = self.client.post("/api/auth/login", json={"username": self.name, "password": "Test-only-123"})
        self.token = login.json["token"]
        self.headers = {"Authorization": "Bearer " + self.token}

    def call(self, method, path, body=None):
        return self.client.open(path, method=method, json=body, headers=self.headers)

    def survey(self):
        response = self.call("POST", "/api/surveys", {"title": "校园体验", "description": "调查说明"})
        assert response.status_code == 201, response.json
        return response.json

    def test_auth_password_and_logout(self):
        user = self.db.users.find_one({"username": self.name})
        assert user["password_hash"] != "Test-only-123"
        assert "password_hash" not in self.call("GET", "/api/auth/me").json
        assert self.client.post("/api/auth/login", json={"username": self.name, "password": "wrong-pass"}).status_code == 401
        assert self.client.post("/api/auth/register", json={"username": self.name.upper(), "password": "Test-only-123"}).status_code == 409
        assert self.db.sessions.find_one({"_id": hashlib.sha256(self.token.encode()).hexdigest()})
        assert self.call("POST", "/api/auth/logout", {}).status_code == 200
        assert self.call("GET", "/api/surveys").status_code == 401

    def test_unauthenticated_and_expired(self):
        assert self.client.get("/api/surveys").status_code == 401
        self.db.sessions.update_one({"_id": hashlib.sha256(self.token.encode()).hexdigest()}, {"$set": {"expires_at": now()-timedelta(seconds=1)}})
        assert self.call("GET", "/api/surveys").status_code == 401

    def test_create_edit_and_owner_isolation(self):
        survey = self.survey()
        sid = survey["_id"]
        assert self.call("GET", "/api/surveys").json["total"] == 1
        assert self.call("PATCH", f"/api/surveys/{sid}", {"title": "新标题", "revision": 1}).status_code == 200
        assert self.db.surveys.find_one({"_id": sid})["title"] == "新标题"
        other = self.app.test_client()
        name = "u"+uuid4().hex[:12]
        other.post("/api/auth/register", json={"username": name, "password": "Other-pass-123"})
        other_token = other.post("/api/auth/login", json={"username": name, "password": "Other-pass-123"}).json["token"]
        headers = {"Authorization": "Bearer "+other_token}
        assert other.get("/api/surveys", headers=headers).json["total"] == 0
        assert other.get(f"/api/surveys/{sid}", headers=headers).status_code == 404
        assert other.patch(f"/api/surveys/{sid}", headers=headers, json={"title": "越权", "revision": 2}).status_code == 404
        assert self.call("POST", "/api/surveys", {"title": "越权", "owner_id": "other"}).status_code == 400

    def test_question_crud_and_preview(self):
        survey = self.survey()
        path = f"/api/surveys/{survey['_id']}/questions"
        q = {"id": "age", "title": "年龄", "type": "number", "required": True,
             "validation": {"min": 0, "max": 120, "integer": True}}
        result = self.call("POST", path, {"revision": 1, "question": q})
        assert result.status_code == 200 and result.json["revision"] == 2
        assert self.call("POST", path, {"revision": 2, "question": q}).status_code == 400
        assert self.call("POST", path+"/age/validate", {"value": 120}).status_code == 200
        assert self.call("POST", path+"/age/validate", {"value": 121}).status_code == 400
        q["validation"]["max"] = 100
        assert self.call("PUT", path+"/age", {"revision": 2, "question": q}).status_code == 200
        assert self.call("DELETE", path+"/age", {"revision": 3}).json["questions"] == []

    def test_invalid_question_does_not_write(self):
        survey = self.survey()
        result = self.call("POST", f"/api/surveys/{survey['_id']}/questions", {"revision": 1, "question": {"id": "q", "title": "年龄", "type": "number", "validation": {"min": 100, "max": 0}}})
        assert result.status_code == 400
        current = self.db.surveys.find_one({"_id": survey["_id"]})
        assert current["questions"] == [] and current["revision"] == 1

    def test_optimistic_concurrent_edit(self):
        survey = self.survey()
        def update(title):
            with self.app.test_client() as client:
                return client.patch(f"/api/surveys/{survey['_id']}", json={"title": title, "revision": 1}, headers=self.headers).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(update, ["版本A", "版本B"]))
        assert sorted(statuses) == [200, 409], statuses
        assert self.db.surveys.find_one({"_id": survey["_id"]})["revision"] == 2

    def test_malformed_requests_and_schema(self):
        assert self.call("POST", "/api/surveys", []).status_code == 400
        assert self.call("POST", "/api/surveys", {"title": " "}).status_code == 400
        assert self.call("GET", "/api/surveys?page=bad").status_code == 400
        assert self.call("GET", "/api/surveys?page=-1").status_code == 400
        assert self.client.post("/api/auth/register", data="not-json").status_code == 400
        assert self.client.post("/api/auth/register", data="{", content_type="application/json").status_code == 400
        with self.assertRaises(WriteError):
            self.db.users.insert_one({"_id": uuid4().hex, "username": "missing-fields"})
