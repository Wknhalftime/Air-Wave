"""Find artists whose names contain collaboration keywords (duet, feat., vs, etc.).

Usage:
    poetry run python -m airwave.scripts.find_artists_with_collab_keywords
"""
import os
import re

from sqlalchemy import create_engine, text

from airwave.core.config import settings

COLLAB_PATTERNS = [r"duet", r"feat\.?", r"\bft\.?", r"featuring", r"\bvs\.?", r"\bf\.\b"]


def name_has_collab_keyword(name: str) -> bool:
    lower = name.lower()
    return any(re.search(p, lower, re.IGNORECASE) for p in COLLAB_PATTERNS)


def main():
    url = os.environ.get("AIRWAVE_DATABASE_URL")
    if not url:
        url = f"sqlite:///{settings.DB_PATH.resolve().as_posix()}"
    else:
        url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    engine = create_engine(url)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, name FROM artists ORDER BY name")).fetchall()
    affected = [(r[0], r[1]) for r in rows if name_has_collab_keyword(r[1])]
    if not affected:
        print("No artists found with collaboration keywords in name.")
        return
    print(f"Found {len(affected)} artist(s):")
    for aid, name in affected:
        print(f"  {aid:6} | {name}")


if __name__ == "__main__":
    main()
