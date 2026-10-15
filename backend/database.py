"""MongoDB collection validators and indexes for the implemented milestone."""

from pymongo.errors import CollectionInvalid


SCHEMAS = {
    "fill_progress": {
        "bsonType": "object",
        "required": ["_id", "survey_id", "user_id", "survey_revision", "revision", "answers", "anonymous", "request_id", "updated_at"],
        "properties": {"_id": {"bsonType": "string"}, "survey_id": {"bsonType": "string"},
                       "user_id": {"bsonType": "string"}, "survey_revision": {"bsonType": "int"},
                       "revision": {"bsonType": "int", "minimum": 1}, "answers": {"bsonType": "object"},
                       "anonymous": {"bsonType": "bool"}, "request_id": {"bsonType": "string"},
                       "updated_at": {"bsonType": "date"}}
    },
    "users": {
        "bsonType": "object", "required": ["_id", "username", "password_hash", "created_at"],
        "properties": {"_id": {"bsonType": "string"}, "username": {"bsonType": "string"},
                       "password_hash": {"bsonType": "string"}, "created_at": {"bsonType": "date"}}
    },
    "sessions": {
        "bsonType": "object", "required": ["_id", "user_id", "expires_at"],
        "properties": {"_id": {"bsonType": "string"}, "user_id": {"bsonType": "string"},
                       "expires_at": {"bsonType": "date"}}
    },
    "surveys": {
        "bsonType": "object",
        "required": ["_id", "owner_id", "title", "status", "questions", "revision", "schema_version", "created_at", "updated_at"],
        "properties": {"_id": {"bsonType": "string"}, "owner_id": {"bsonType": "string"},
                       "title": {"bsonType": "string"}, "description": {"bsonType": "string"},
                       "status": {"enum": ["draft", "published", "closed"]}, "questions": {"bsonType": "array"},
                       "allow_anonymous": {"bsonType": "bool"}, "allow_repeat": {"bsonType": "bool"},
                       "deadline": {"bsonType": ["date", "null"]},
                       "revision": {"bsonType": "int", "minimum": 1},
                       "schema_version": {"bsonType": "int", "minimum": 1},
                       "created_at": {"bsonType": "date"}, "updated_at": {"bsonType": "date"}}
    },
    "responses": {
        "bsonType": "object", "required": ["_id", "survey_id", "user_id", "submission_key", "request_id", "anonymous", "answers", "path", "created_at"],
        "properties": {"_id": {"bsonType": "string"}, "survey_id": {"bsonType": "string"},
                       "user_id": {"bsonType": "string"}, "submission_key": {"bsonType": "string"},
                       "request_id": {"bsonType": "string"}, "anonymous": {"bsonType": "bool"},
                       "answers": {"bsonType": "array"}, "path": {"bsonType": "array"}, "created_at": {"bsonType": "date"}}
    }
}


def initialize(db):
    # Existing validators are not silently replaced: future changes need a migration.
    for name, schema in SCHEMAS.items():
        try:
            db.create_collection(name, validator={"$jsonSchema": schema})
        except CollectionInvalid:
            pass
    db.users.create_index("username", unique=True, name="unique_username")
    db.fill_progress.create_index([("survey_id", 1), ("user_id", 1)], unique=True, name="one_active_progress")
    db.sessions.create_index("expires_at", expireAfterSeconds=0, name="session_expiry")
    db.surveys.create_index([("owner_id", 1), ("updated_at", -1)], name="owner_updated")
    db.responses.create_index([("survey_id", 1), ("user_id", 1), ("submission_key", 1)], unique=True, name="unique_attempt")
    db.responses.create_index([("survey_id", 1), ("user_id", 1), ("request_id", 1)], unique=True, name="idempotent_request")
    db.responses.create_index([("survey_id", 1), ("created_at", -1)], name="survey_responses")


def migrate_drafts(db):
    """Explicit, idempotent expansion from the known accounts-and-drafts milestone."""
    info = list(db.list_collections(filter={"name": "surveys"}))
    old = info[0].get("options", {}).get("validator", {}).get("$jsonSchema", {}) if info else {}
    status = old.get("properties", {}).get("status", {}).get("enum")
    if status not in (["draft"], ["draft", "published", "closed"]):
        raise RuntimeError("Unknown surveys validator; inspect before migration")
    db.command("collMod", "surveys", validator={"$jsonSchema": SCHEMAS["surveys"]})
    for field, default in (("allow_anonymous", False), ("allow_repeat", False), ("deadline", None)):
        db.surveys.update_many({field: {"$exists": False}}, {"$set": {field: default}})
    return db.surveys.count_documents({})
