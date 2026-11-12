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
                status TEXT NOT NULL DEFAULT 'not_started' CHECK(status IN ('not_started', 'in_progress', 'done', 'later')),
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

        migrate_status_check(cursor)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_stack_name ON assignments(stack_name);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_due_date ON assignments(due_date);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON assignments(status);")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_external_id ON assignments(external_id);")


def migrate_status_check(cursor):
    """Older databases only allow not_started/in_progress/done. SQLite cannot
    change a CHECK constraint in place, so rebuild the table with the 'later'
    (Saved for later) status allowed, keeping every row and its id."""
    row = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'assignments'"
    ).fetchone()
    if not row or "'later'" in row[0]:
        return

    # All-or-nothing: if anything fails, the original table is left untouched.
    cursor.execute("SAVEPOINT add_later_status")
    try:
        _rebuild_assignments(cursor)
        cursor.execute("RELEASE add_later_status")
    except Exception:
        cursor.execute("ROLLBACK TO add_later_status")
        cursor.execute("RELEASE add_later_status")
        raise

def _rebuild_assignments(cursor):
    cursor.execute("DROP TABLE IF EXISTS assignments_new")
    cursor.execute("""
        CREATE TABLE assignments_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            course TEXT NOT NULL,
            stack_name TEXT NOT NULL DEFAULT 'General',
            due_date TEXT NOT NULL,
            due_time TEXT,
            status TEXT NOT NULL DEFAULT 'not_started' CHECK(status IN ('not_started', 'in_progress', 'done', 'later')),
            link TEXT,
            external_id TEXT
        );
    """)
    cursor.execute("""
        INSERT INTO assignments_new (id, title, course, stack_name, due_date, due_time, status, link, external_id)
        SELECT id, title, course, stack_name, due_date, due_time, status, link, external_id FROM assignments
    """)
    cursor.execute("DROP TABLE assignments")
    cursor.execute("ALTER TABLE assignments_new RENAME TO assignments")
    # Indexes were dropped with the old table; init_db recreates them right after this.
