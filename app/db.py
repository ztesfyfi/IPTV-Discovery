import os, sqlite3
from pathlib import Path
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "database" / "iptv.db"

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS channels(id TEXT PRIMARY KEY,name TEXT NOT NULL,group_name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS aliases(alias TEXT PRIMARY KEY,channel_id TEXT NOT NULL REFERENCES channels(id));
        CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,source_type TEXT NOT NULL,source_url TEXT,trust_level TEXT NOT NULL DEFAULT 'C',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS candidates(id INTEGER PRIMARY KEY AUTOINCREMENT,channel_id TEXT REFERENCES channels(id),name_raw TEXT NOT NULL,url TEXT NOT NULL UNIQUE,source_id INTEGER REFERENCES sources(id),protocol TEXT,status TEXT NOT NULL DEFAULT 'pending',last_status_code INTEGER,latency_ms REAL,width INTEGER,height INTEGER,fps REAL,bitrate INTEGER,codec TEXT,last_checked TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS checks(id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id INTEGER NOT NULL REFERENCES candidates(id),ok INTEGER NOT NULL,status_code INTEGER,latency_ms REAL,detail TEXT,checked_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
