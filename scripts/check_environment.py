"""Read-only startup checks. Never imports create_app or initializes collections."""
import argparse
from datetime import datetime, timezone
from importlib import import_module
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def check(skip_mongo=False):
    checks = []

    def record(name, ok, detail):
        checks.append({"check": name, "status": "passed" if ok else "failed", "detail": detail})

    record("python", sys.version_info >= (3, 10), "Python " + sys.version.split()[0] + "; requires >=3.10")
    installed = {}
    for package, module in (("Flask", "flask"), ("pymongo", "pymongo")):
        try:
            import_module(module)
            installed[package] = version(package)
        except Exception:
            record(package, False, "Cannot import dependency; install requirements.txt")
    pinned = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        if "==" in line and not line.lstrip().startswith("#"):
            key, value = line.strip().split("==", 1)
            pinned[key] = value
    for package, actual in installed.items():
        record(package, actual == pinned.get(package), actual + "; pinned=" + str(pinned.get(package)))
    for name in ("frontend/index.html", "frontend/app.js", "frontend/style.css", "database/schema.json"):
        record(name, (ROOT / name).is_file(), "Required project file")
    try:
        port = int(os.getenv("PORT", "5050"))
        record("port", 1 <= port <= 65535, "PORT must be an integer from 1 to 65535")
    except ValueError:
        record("port", False, "PORT must be an integer from 1 to 65535")
    if skip_mongo:
        checks.append({"check": "mongodb", "status": "not_checked", "detail": "Explicitly skipped; database readiness is unknown"})
    elif "pymongo" in installed:
        client = None
        try:
            from pymongo import MongoClient
            client = MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017/"),
                                 serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, socketTimeoutMS=5000)
            # Validate the configured name without reading or writing its collections.
            client[os.getenv("MONGO_DB", "mongodb_survey_course")]
            client.admin.command("ping")
            record("mongodb", True, "Ping succeeded; collection permissions and API behavior are not tested")
        except Exception as exc:
            # Driver messages can contain URI credentials: emit only the exception type.
            record("mongodb", False, type(exc).__name__ + "; check service, MONGO_URI and MONGO_DB; connection details omitted")
        finally:
            if client is not None:
                client.close()
    else:
        checks.append({"check": "mongodb", "status": "not_checked", "detail": "pymongo unavailable"})
    return {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "read_only": True,
            "successful": not any(c["status"] == "failed" for c in checks), "checks": checks}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-mongo", action="store_true", help="Check local files/dependencies only")
    args = parser.parse_args()
    result = check(args.skip_mongo)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["successful"] else 1)
