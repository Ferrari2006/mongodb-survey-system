"""Expand the known draft validator without deleting old documents."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import create_app
from backend.database import migrate_drafts

if __name__ == "__main__":
    app = create_app()
    try:
        print("Migrated surveys:", migrate_drafts(app.extensions["db"]))
    finally:
        app.extensions["mongo_client"].close()
