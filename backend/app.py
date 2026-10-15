"""Application factory for accounts and questionnaire draft management."""

import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import Flask, g, jsonify, request
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

from backend.database import initialize
from backend.validation import DomainError, question, require, string


def now():
    return datetime.now(timezone.utc)


def create_app(config=None):
    app = Flask(__name__, static_folder=str(Path(__file__).resolve().parents[1] / "frontend"), static_url_path="/static")
    app.config.update(MONGO_URI=os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/"),
                      MONGO_DB=os.getenv("MONGO_DB", "mongodb_survey_course"), MAX_CONTENT_LENGTH=256 * 1024)
    app.config.update(config or {})
    client = MongoClient(app.config["MONGO_URI"], serverSelectionTimeoutMS=5000, tz_aware=True)
    db = client[app.config["MONGO_DB"]]
    initialize(db)
    app.extensions["mongo_client"], app.extensions["db"] = client, db

    def payload(allowed):
        require(request.is_json, "请求须使用 application/json")
        data = request.get_json()
        require(isinstance(data, dict), "请求体须为JSON对象")
        require(not (set(data) - set(allowed)), "请求包含未支持的字段")
        return data

    def login_required(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                raise DomainError("请先登录", 401, "unauthorized")
            digest = hashlib.sha256(auth[7:].encode()).hexdigest()
            session = db.sessions.find_one({"_id": digest, "expires_at": {"$gt": now()}})
            if not session:
                raise DomainError("登录已失效，请重新登录", 401, "unauthorized")
            g.user_id, g.token_hash = session["user_id"], digest
            return fn(*args, **kwargs)
        return wrapped

    def owned(sid):
        survey = db.surveys.find_one({"_id": sid, "owner_id": g.user_id})
        if not survey:
            raise DomainError("问卷不存在或无权访问", 404, "not_found")
        return survey

    def save(survey, revision):
        require(type(revision) is int, "必须提供整数revision")
        survey["updated_at"] = now()
        survey["revision"] = revision + 1
        result = db.surveys.replace_one({"_id": survey["_id"], "owner_id": g.user_id,
                                         "revision": revision, "status": "draft"}, survey)
        if not result.matched_count:
            raise DomainError("问卷已被修改，请刷新后重试", 409, "revision_conflict")
        return jsonify(survey)

    @app.errorhandler(DomainError)
    def domain_error(exc):
        return jsonify(error={"code": exc.code, "message": exc.message}), exc.status

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error={"code": "http_error", "message": exc.description}), exc.code

    @app.errorhandler(PyMongoError)
    def db_error(exc):
        app.logger.error("Database failure: %s", type(exc).__name__)
        return jsonify(error={"code": "database_unavailable", "message": "数据库操作失败，请稍后重试"}), 503

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/favicon.ico")
    def favicon():
        return "", 204

    @app.get("/api/health")
    def health():
        db.command("ping")
        return jsonify(status="ok", milestone="accounts-and-drafts")

    @app.post("/api/auth/register")
    def register():
        data = payload({"username", "password"})
        username = string(data.get("username"), "用户名", 3, 32).lower()
        require(bool(re.fullmatch(r"[a-z0-9_]+", username)), "用户名仅支持英文字母、数字和下划线")
        password = data.get("password")
        require(isinstance(password, str) and 8 <= len(password) <= 128, "密码长度须为8～128位")
        user = {"_id": uuid4().hex, "username": username, "password_hash": generate_password_hash(password), "created_at": now()}
        try:
            db.users.insert_one(user)
        except DuplicateKeyError:
            raise DomainError("用户名已存在", 409, "username_exists") from None
        return jsonify(id=user["_id"], username=username), 201

    @app.post("/api/auth/login")
    def login():
        data = payload({"username", "password"})
        username = string(data.get("username"), "用户名", 3, 32).lower()
        password = data.get("password")
        require(isinstance(password, str) and 8 <= len(password) <= 128, "密码长度须为8～128位")
        user = db.users.find_one({"username": username})
        if not user or not check_password_hash(user["password_hash"], password):
            raise DomainError("用户名或密码错误", 401, "invalid_credentials")
        token = secrets.token_urlsafe(32)
        expiry = now() + timedelta(hours=8)
        db.sessions.insert_one({"_id": hashlib.sha256(token.encode()).hexdigest(), "user_id": user["_id"], "expires_at": expiry})
        return jsonify(token=token, expires_at=expiry, username=user["username"])

    @app.get("/api/auth/me")
    @login_required
    def me():
        user = db.users.find_one({"_id": g.user_id}, {"password_hash": 0})
        return jsonify(user)

    @app.post("/api/auth/logout")
    @login_required
    def logout():
        db.sessions.delete_one({"_id": g.token_hash})
        return jsonify(message="已退出登录")

    @app.get("/api/surveys")
    @login_required
    def list_surveys():
        try:
            page = int(request.args.get("page", "1"))
        except ValueError:
            raise DomainError("page须为正整数") from None
        require(1 <= page <= 10000, "page须在1～10000之间")
        query = {"owner_id": g.user_id}
        return jsonify(items=list(db.surveys.find(query, {"questions": 0}).sort("updated_at", -1).skip((page - 1) * 20).limit(20)),
                       page=page, total=db.surveys.count_documents(query))

    @app.post("/api/surveys")
    @login_required
    def create_survey():
        data = payload({"title", "description"})
        survey = {"_id": uuid4().hex, "owner_id": g.user_id,
                  "title": string(data.get("title"), "标题", 1, 200),
                  "description": string(data.get("description", ""), "说明", 0, 2000),
                  "status": "draft", "questions": [], "revision": 1, "schema_version": 1,
                  "created_at": now(), "updated_at": now()}
        db.surveys.insert_one(survey)
        return jsonify(survey), 201

    @app.get("/api/surveys/<sid>")
    @login_required
    def get_survey(sid):
        return jsonify(owned(sid))

    @app.patch("/api/surveys/<sid>")
    @login_required
    def edit_survey(sid):
        data = payload({"title", "description", "revision"})
        survey = owned(sid)
        if "title" in data:
            survey["title"] = string(data["title"], "标题", 1, 200)
        if "description" in data:
            survey["description"] = string(data["description"], "说明", 0, 2000)
        return save(survey, data.get("revision"))

    @app.post("/api/surveys/<sid>/questions")
    @login_required
    def add_question(sid):
        data = payload({"question", "revision"})
        survey = owned(sid)
        item = question(data.get("question"))
        require(len(survey["questions"]) < 100, "每份问卷最多100题")
        require(item["id"] not in {q["id"] for q in survey["questions"]}, "题目ID不能重复")
        survey["questions"].append(item)
        return save(survey, data.get("revision"))

    @app.put("/api/surveys/<sid>/questions/<qid>")
    @login_required
    def edit_question(sid, qid):
        data = payload({"question", "revision"})
        survey = owned(sid)
        item = question(data.get("question"))
        require(item["id"] == qid, "编辑时不能改变题目ID")
        require(any(q["id"] == qid for q in survey["questions"]), "题目不存在")
        survey["questions"] = [item if q["id"] == qid else q for q in survey["questions"]]
        return save(survey, data.get("revision"))

    @app.delete("/api/surveys/<sid>/questions/<qid>")
    @login_required
    def delete_question(sid, qid):
        data = payload({"revision"})
        survey = owned(sid)
        require(any(q["id"] == qid for q in survey["questions"]), "题目不存在")
        survey["questions"] = [q for q in survey["questions"] if q["id"] != qid]
        return save(survey, data.get("revision"))

    @app.post("/api/surveys/<sid>/questions/<qid>/validate")
    @login_required
    def preview_validation(sid, qid):
        from backend.validation import validate_answer
        data = payload({"value"})
        survey = owned(sid)
        item = next((q for q in survey["questions"] if q["id"] == qid), None)
        require(item is not None, "题目不存在")
        return jsonify(valid=True, value=validate_answer(item, data.get("value")))

    return app
