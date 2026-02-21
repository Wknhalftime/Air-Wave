"""Clear the database (drop all tables and recreate from current models).

Usage:
    poetry run python -m airwave.scripts.clear_db
"""
import asyncio

from airwave.core.db import init_db

if __name__ == "__main__":
    asyncio.run(init_db(force=True))
    print("Database cleared and tables recreated.")
