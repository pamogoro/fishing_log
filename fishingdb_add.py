import sqlite3
conn = sqlite3.connect("fishing_log.db")
cur = conn.cursor()
cur.execute("ALTER TABLE fishing_log ADD COLUMN time TEXT;")
cur.execute("ALTER TABLE fishing_log ADD COLUMN tide_height REAL;")
conn.commit()
conn.close()
print("✅ time と tide_height カラムを追加しました")
