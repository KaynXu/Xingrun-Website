import sqlite3
conn = sqlite3.connect('data/lessons.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT id, date, subject, grade, topic, created_at FROM lessons ORDER BY id DESC LIMIT 5')
rows = cur.fetchall()
print("=== Lessons ===")
for r in rows:
    print(dict(r))
cur.execute('SELECT count(*) as cnt FROM lessons')
print("Total lessons:", cur.fetchone()[0])
conn.close()
