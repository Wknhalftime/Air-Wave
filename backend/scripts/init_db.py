"""Initialize the database (create tables). Run from backend with backend's venv.

  From backend directory (recommended):
    poetry run python scripts/init_db.py

  Or with backend venv activated:
    poetry run python scripts/init_db.py

  If you use the repo-root .venv, run from repo root so backend/src is on path:
    python backend/scripts/init_db.py
"""
import sys
from pathlib import Path

# Ensure backend/src is on path so "airwave" can be imported (works from backend or repo root)
_script = Path(__file__).resolve()
_backend = _script.parent.parent  # backend/
_src = _backend / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

import asyncio
from airwave.core.db import init_db

if __name__ == "__main__":
    asyncio.run(init_db())
    print("Database tables ready.")
