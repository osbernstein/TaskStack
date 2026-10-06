import sqlite3

DB_FILE = "assignments.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );
        """)

        # Table to store tags scoped to stacks
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stack_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stack_name TEXT NOT NULL,
                tag_name TEXT NOT NULL,
                UNIQUE(stack_name, tag_name)
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                course TEXT NOT NULL,
                stack_name TEXT NOT NULL DEFAULT 'General',
                due_date TEXT NOT NULL,
                due_time TEXT,
                status TEXT NOT NULL DEFAULT 'not_started' CHECK(status IN ('not_started', 'in_progress', 'done')),
                link TEXT,
                external_id TEXT
            );
        """)

        cursor = conn.cursor()
        cols = [c[1] for c in cursor.execute("PRAGMA table_info(assignments)").fetchall()]
        if "stack_name" not in cols:
            cursor.execute("ALTER TABLE assignments ADD COLUMN stack_name TEXT NOT NULL DEFAULT 'General'")
        if "external_id" not in cols:
            cursor.execute("ALTER TABLE assignments ADD COLUMN external_id TEXT")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_stack_name ON assignments(stack_name);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_due_date ON assignments(due_date);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON assignments(status);")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_external_id ON assignments(external_id);")
