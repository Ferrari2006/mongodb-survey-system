"""MongoDB collection validators and indexes for the implemented milestone."""

from pymongo.errors import CollectionInvalid


SCHEMAS = {
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
                       "status": {"enum": ["draft"]}, "questions": {"bsonType": "array"},
                       "revision": {"bsonType": "int", "minimum": 1},
                       "schema_version": {"bsonType": "int", "minimum": 1},
                       "created_at": {"bsonType": "date"}, "updated_at": {"bsonType": "date"}}
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
    db.sessions.create_index("expires_at", expireAfterSeconds=0, name="session_expiry")
    db.surveys.create_index([("owner_id", 1), ("updated_at", -1)], name="owner_updated")
