import sqlite3

conn = sqlite3.connect('backend/data/airwave.db')
cursor = conn.cursor()

# Get library_files table schema
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='library_files'")
result = cursor.fetchone()
if result:
    print("LibraryFiles table schema:")
    print(result[0])
    print()

# Get all indexes on library_files table
cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='library_files'")
indexes = cursor.fetchall()
if indexes:
    print("Indexes on library_files table:")
    for idx in indexes:
        if idx[0]:  # Skip auto-created indexes
            print(idx[0])
    print()

# Check for duplicate recordings
cursor.execute("""
    SELECT work_id, title, COUNT(*) as count
    FROM recordings
    GROUP BY work_id, title
    HAVING count > 1
""")
dupes = cursor.fetchall()
if dupes:
    print(f"Duplicate recordings found: {len(dupes)}")
    for row in dupes[:10]:
        print(f"  work_id={row[0]}, title={row[1]!r}, count={row[2]}")
else:
    print("No duplicate recordings found")

conn.close()

