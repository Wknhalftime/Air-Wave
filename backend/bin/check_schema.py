import os
import sqlite3


def check():
    db_path = os.path.join(os.getcwd(), "data", "airwave.db.bak")
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    try:
        # Check broadcast_logs
        print("--- broadcast_logs ---")
        cols = cur.execute("PRAGMA table_info(broadcast_logs)").fetchall()
        for c in cols:
            print(c)

        # Check identity_bridge
        print("\n--- identity_bridge ---")
        cols = cur.execute("PRAGMA table_info(identity_bridge)").fetchall()
        for c in cols:
            print(c)

    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        con.close()


if __name__ == "__main__":
    check()
