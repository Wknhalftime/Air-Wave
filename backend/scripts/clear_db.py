"""Clear the database (drop all tables and recreate from current models).

  From backend directory:
    poetry run python scripts/clear_db.py

  From repo root (with pip install -e backend):
    python backend/scripts/clear_db.py
"""
import sys
from pathlib import Path

_script = Path(__file__).resolve()
_backend = _script.parent.parent
_src = _backend / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

import asyncio
from airwave.core.db import init_db

if __name__ == "__main__":
    asyncio.run(init_db(force=True))
    print("Database cleared and tables recreated.")
