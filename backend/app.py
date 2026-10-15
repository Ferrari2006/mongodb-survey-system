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
from backend.logic import evaluate, validate_jumps
from backend.statistics import statistics


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
        require(survey["status"] == "draft", "发布后题目与配置固定，请创建新问卷")
        validate_jumps(survey["questions"])
        survey["updated_at"] = now()
        survey["revision"] = revision + 1
        result = db.surveys.replace_one({"_id": survey["_id"], "owner_id": g.user_id,
                                         "revision": revision, "status": "draft"}, survey)
        if not result.matched_count:
            raise DomainError("问卷已被修改，请刷新后重试", 409, "revision_conflict")
        return jsonify(survey)

    def deadline(value):
        if value is None or value == "":
            return None
        require(isinstance(value, str), "截止时间须为带时区的ISO日期")
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise DomainError("截止时间格式不合法") from None
        require(dt.tzinfo is not None and dt.utcoffset() is not None, "截止时间必须包含时区")
        return dt.astimezone(timezone.utc)

    def settings(data, survey):
        for field in ("allow_anonymous", "allow_repeat"):
            if field in data:
                require(type(data[field]) is bool, "匿名和重复填写设置必须为布尔值")
                survey[field] = data[field]
        if "deadline" in data:
            survey["deadline"] = deadline(data["deadline"])

    def available(sid):
        survey = db.surveys.find_one({"_id": sid, "status": "published"})
        if not survey:
            raise DomainError("问卷未发布、已关闭或不存在", 404, "not_available")
        if survey.get("deadline") and survey["deadline"] <= now():
            raise DomainError("问卷已截止", 410, "expired")
        return survey

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

    @app.get("/survey/<sid>")
    def survey_page(sid):
        return app.send_static_file("index.html")

    @app.get("/favicon.ico")
    def favicon():
        return "", 204

    @app.get("/api/health")
    def health():
        db.command("ping")
        return jsonify(status="ok", milestone="stage1")

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
        data = payload({"title", "description", "allow_anonymous", "allow_repeat", "deadline"})
        survey = {"_id": uuid4().hex, "owner_id": g.user_id,
                  "title": string(data.get("title"), "标题", 1, 200),
                  "description": string(data.get("description", ""), "说明", 0, 2000),
                  "status": "draft", "questions": [], "revision": 1, "schema_version": 1,
                  "allow_anonymous": False, "allow_repeat": False, "deadline": None,
                  "created_at": now(), "updated_at": now()}
        settings(data, survey)
        db.surveys.insert_one(survey)
        return jsonify(survey), 201

    @app.get("/api/surveys/<sid>")
    @login_required
    def get_survey(sid):
        return jsonify(owned(sid))

    @app.patch("/api/surveys/<sid>")
    @login_required
    def edit_survey(sid):
        data = payload({"title", "description", "revision", "allow_anonymous", "allow_repeat", "deadline"})
        survey = owned(sid)
        if "title" in data:
            survey["title"] = string(data["title"], "标题", 1, 200)
        if "description" in data:
            survey["description"] = string(data["description"], "说明", 0, 2000)
        settings(data, survey)
        return save(survey, data.get("revision"))

    @app.post("/api/surveys/<sid>/questions")
    @login_required
    def add_question(sid):
        data = payload({"question", "revision"})
        survey = owned(sid)
        item = question(data.get("question"))
        require(item["id"] != "END", "END是结束标识，不能用作题目ID")
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

    @app.post("/api/surveys/<sid>/publish")
    @login_required
    def publish(sid):
        data = payload({"revision"})
        survey = owned(sid)
        require(survey["status"] == "draft", "仅草稿可发布")
        require(type(data.get("revision")) is int, "须提供revision")
        require(bool(survey["questions"]), "空问卷不能发布")
        validate_jumps(survey["questions"], publishing=True)
        require(not survey.get("deadline") or survey["deadline"] > now(), "截止时间必须晚于当前时间")
        result = db.surveys.update_one({"_id": sid, "owner_id": g.user_id, "status": "draft", "revision": data["revision"]},
                                      {"$set": {"status": "published", "published_at": now(), "updated_at": now()}, "$inc": {"revision": 1}})
        if not result.matched_count:
            raise DomainError("问卷已被修改，请刷新", 409, "revision_conflict")
        return jsonify(owned(sid))

    @app.post("/api/surveys/<sid>/close")
    @login_required
    def close(sid):
        data = payload({"revision"})
        survey = owned(sid)
        require(survey["status"] == "published", "仅已发布问卷可关闭")
        require(type(data.get("revision")) is int, "须提供revision")
        result = db.surveys.update_one({"_id": sid, "owner_id": g.user_id, "status": "published", "revision": data["revision"]},
                                      {"$set": {"status": "closed", "updated_at": now()}, "$inc": {"revision": 1}})
        if not result.matched_count:
            raise DomainError("问卷已被修改，请刷新", 409, "revision_conflict")
        return jsonify(owned(sid))

    @app.get("/api/public/surveys/<sid>")
    @login_required
    def public_survey(sid):
        survey = available(sid)
        return jsonify({k: survey.get(k) for k in ("_id", "title", "description", "questions", "revision", "allow_anonymous", "allow_repeat", "deadline")})

    @app.post("/api/public/surveys/<sid>/evaluate")
    @login_required
    def evaluate_path(sid):
        data = payload({"answers"})
        return jsonify(evaluate(available(sid)["questions"], data.get("answers")))

    @app.get("/api/public/surveys/<sid>/progress")
    @login_required
    def get_progress(sid):
        survey = available(sid)
        progress = db.fill_progress.find_one({"survey_id": sid, "user_id": g.user_id})
        if progress and db.responses.find_one({"survey_id": sid, "user_id": g.user_id,
                                               **({"request_id": progress["request_id"]} if survey.get("allow_repeat") else {})}):
            db.fill_progress.delete_one({"_id": progress["_id"], "revision": progress["revision"]})
            progress = None
        if progress:
            require(progress["survey_revision"] == survey["revision"], "问卷版本已变化，原填写进度不可继续")
        return jsonify(progress={k: progress[k] for k in ("answers", "revision", "anonymous", "request_id", "updated_at")} if progress else None)

    @app.put("/api/public/surveys/<sid>/progress")
    @login_required
    def save_progress(sid):
        data = payload({"answers", "revision", "anonymous", "request_id"})
        survey = available(sid)
        revision = data.get("revision")
        require(type(revision) is int and 0 <= revision < 2147483647, "进度revision须为有效非负整数")
        anonymous = data.get("anonymous", False)
        require(type(anonymous) is bool and (not anonymous or survey.get("allow_anonymous")), "匿名设置不合法")
        request_id = string(data.get("request_id"), "request_id", 8, 100)
        state = evaluate(survey["questions"], data.get("answers"))
        # Only a valid prefix is resumable. Never keep hidden or unanswered suffixes.
        require(set(data["answers"]) == set(state["path"]), "进度包含未经过题目，请清理后续答案")
        if db.responses.find_one({"survey_id": sid, "user_id": g.user_id,
                                  **({"request_id": request_id} if survey.get("allow_repeat") else {})}):
            raise DomainError("本次填写已提交，不能保存旧进度", 409, "already_submitted")
        progress = {"survey_id": sid, "user_id": g.user_id, "survey_revision": survey["revision"],
                    "revision": revision + 1, "answers": data["answers"], "anonymous": anonymous,
                    "request_id": request_id, "updated_at": now()}
        if revision == 0:
            progress["_id"] = uuid4().hex
            try:
                db.fill_progress.insert_one(progress)
            except DuplicateKeyError:
                raise DomainError("其他窗口已保存进度，请刷新后继续", 409, "progress_conflict") from None
        else:
            result = db.fill_progress.update_one({"survey_id": sid, "user_id": g.user_id,
                                                  "revision": revision, "request_id": request_id}, {"$set": progress})
            if not result.matched_count:
                raise DomainError("进度已变化，请刷新后继续", 409, "progress_conflict")
        # A submit can race this separate-collection write; hide and remove obsolete progress.
        if db.responses.find_one({"survey_id": sid, "user_id": g.user_id,
                                  **({"request_id": request_id} if survey.get("allow_repeat") else {})}):
            db.fill_progress.delete_one({"survey_id": sid, "user_id": g.user_id, "request_id": request_id})
            raise DomainError("本次填写已提交，请刷新", 409, "already_submitted")
        return jsonify(revision=revision+1, updated_at=progress["updated_at"])

    @app.post("/api/public/surveys/<sid>/responses")
    @login_required
    def submit(sid):
        data = payload({"answers", "anonymous", "request_id"})
        request_id = string(data.get("request_id"), "request_id", 8, 100)
        previous = db.responses.find_one({"survey_id": sid, "user_id": g.user_id, "request_id": request_id})
        if previous:
            db.fill_progress.delete_one({"survey_id": sid, "user_id": g.user_id, "request_id": request_id})
            return jsonify(id=previous["_id"], message="本次提交已保存", replayed=True), 200
        survey = available(sid)
        anonymous = data.get("anonymous", False)
        require(type(anonymous) is bool, "anonymous必须为布尔值")
        require(not anonymous or survey.get("allow_anonymous", False), "问卷不允许匿名提交")
        result = evaluate(survey["questions"], data.get("answers"), complete=True)
        # This conditional write is the admission point. Requests admitted before close may finish afterwards.
        admitted = db.surveys.update_one({"_id": sid, "status": "published", "revision": survey["revision"],
                                          "$or": [{"deadline": None}, {"deadline": {"$gt": now()}}]},
                                         {"$inc": {"admission_count": 1}})
        if not admitted.matched_count:
            raise DomainError("问卷已关闭或截止，请刷新", 409, "not_available")
        response = {"_id": uuid4().hex, "survey_id": sid, "user_id": g.user_id, "anonymous": anonymous,
                    "request_id": request_id, "submission_key": request_id if survey.get("allow_repeat") else "once",
                    "answers": result["answers"], "path": result["path"], "survey_revision": survey["revision"], "created_at": now()}
        try:
            db.responses.insert_one(response)
        except DuplicateKeyError:
            previous = db.responses.find_one({"survey_id": sid, "user_id": g.user_id, "request_id": request_id})
            if previous:
                db.fill_progress.delete_one({"survey_id": sid, "user_id": g.user_id, "request_id": request_id})
                return jsonify(id=previous["_id"], message="本次提交已保存", replayed=True), 200
            raise DomainError("该问卷不允许重复填写", 409, "already_submitted") from None
        db.fill_progress.delete_one({"survey_id": sid, "user_id": g.user_id, "request_id": request_id})
        return jsonify(id=response["_id"], message="提交成功", replayed=False), 201

    @app.get("/api/surveys/<sid>/statistics")
    @login_required
    def survey_statistics(sid):
        return jsonify(statistics(db, owned(sid)))

    @app.get("/api/surveys/<sid>/questions/<qid>/statistics")
    @login_required
    def question_statistics(sid, qid):
        survey = owned(sid)
        require(any(q["id"] == qid for q in survey["questions"]), "题目不存在")
        return jsonify(statistics(db, survey, qid))

    @app.get("/api/surveys/<sid>/responses")
    @login_required
    def list_responses(sid):
        owned(sid)
        try:
            page = int(request.args.get("page", "1"))
        except ValueError:
            raise DomainError("page须为正整数") from None
        require(1 <= page <= 10000, "page须在1～10000之间")
        items = list(db.responses.find({"survey_id": sid}).sort("created_at", -1).skip((page-1)*20).limit(20))
        for item in items:
            uid = item.pop("user_id")
            item.pop("submission_key", None)
            item.pop("request_id", None)
            if not item["anonymous"]:
                user = db.users.find_one({"_id": uid}, {"username": 1})
                item["respondent"] = user["username"] if user else "已注销用户"
            else:
                item["respondent"] = "匿名"
        return jsonify(items=items, page=page, total=db.responses.count_documents({"survey_id": sid}))

    return app
