"""Initialize the database (create tables).

Usage:
    poetry run python -m airwave.scripts.init_db
"""
import asyncio

from airwave.core.db import init_db

if __name__ == "__main__":
    asyncio.run(init_db())
    print("Database tables ready.")
