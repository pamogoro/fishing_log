import sqlite3
import pandas as pd

DB_PATH = "fishing_log.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def fetch_all():
    with get_conn() as conn:
        return pd.read_sql("SELECT * FROM fishing_log ORDER BY date DESC, id DESC", conn)
