import os
import sqlite3


def get_path():
    db_path = os.path.join(os.getcwd(), "data", "airwave.db")
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    try:
        res = cur.execute(
            "SELECT path FROM tracks WHERE path NOT LIKE 'virtual:%' LIMIT 1"
        ).fetchone()
        if res:
            print(f"FOUND_PATH: {res[0]}")
        else:
            print("NO_PATH_FOUND")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        con.close()


if __name__ == "__main__":
    get_path()
