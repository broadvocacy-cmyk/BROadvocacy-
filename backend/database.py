import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "broadvocacy.db")


class Database:
    def _conn(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    charges TEXT,
                    jurisdiction TEXT,
                    notes TEXT DEFAULT '',
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    content TEXT,
                    analysis TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (case_id) REFERENCES cases(id)
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (case_id) REFERENCES cases(id)
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    type TEXT DEFAULT 'other',
                    due_date TEXT,
                    completed INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (case_id) REFERENCES cases(id)
                );
            """)

    # ── Cases ──────────────────────────────────────────────────────────────

    def create_case(self, data):
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO cases (name, client_name, charges, jurisdiction, notes) VALUES (?,?,?,?,?)",
                (data["name"], data["client_name"], data["charges"],
                 data["jurisdiction"], data.get("notes", "")),
            )
            return cur.lastrowid

    def list_cases(self):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM cases ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_case(self, case_id):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM cases WHERE id=?", (case_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_case(self, case_id, data):
        with self._conn() as conn:
            conn.execute(
                "UPDATE cases SET name=?, client_name=?, charges=?, jurisdiction=?, notes=?, status=? WHERE id=?",
                (data["name"], data["client_name"], data["charges"],
                 data["jurisdiction"], data.get("notes", ""),
                 data.get("status", "active"), case_id),
            )

    def get_case_context(self, case_id):
        case = self.get_case(case_id)
        if not case:
            return {}
        case["documents"] = self.list_documents(case_id)
        return case

    # ── Documents ──────────────────────────────────────────────────────────

    def add_document(self, case_id, filename, content):
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO documents (case_id, filename, content) VALUES (?,?,?)",
                (case_id, filename, content),
            )
            return cur.lastrowid

    def update_document_analysis(self, doc_id, analysis):
        with self._conn() as conn:
            conn.execute(
                "UPDATE documents SET analysis=? WHERE id=?", (analysis, doc_id)
            )

    def list_documents(self, case_id):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, filename, analysis, created_at FROM documents WHERE case_id=? ORDER BY created_at",
                (case_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_document(self, doc_id):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id=?", (doc_id,)
            ).fetchone()
            return dict(row) if row else None

    # ── Chat ───────────────────────────────────────────────────────────────

    def add_chat_message(self, case_id, role, content):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO chat_messages (case_id, role, content) VALUES (?,?,?)",
                (case_id, role, content),
            )

    def get_chat_history(self, case_id):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM chat_messages WHERE case_id=? ORDER BY created_at",
                (case_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def clear_chat(self, case_id):
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM chat_messages WHERE case_id=?", (case_id,)
            )

    # ── Tasks ──────────────────────────────────────────────────────────────

    def create_task(self, data):
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO tasks (case_id, title, description, type, due_date) VALUES (?,?,?,?,?)",
                (data["case_id"], data["title"], data.get("description", ""),
                 data.get("type", "other"), data.get("due_date")),
            )
            return cur.lastrowid

    def list_tasks(self, case_id):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE case_id=? ORDER BY completed, due_date NULLS LAST, created_at",
                (case_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update_task(self, task_id, updates):
        with self._conn() as conn:
            if "completed" in updates:
                conn.execute(
                    "UPDATE tasks SET completed=? WHERE id=?",
                    (1 if updates["completed"] else 0, task_id),
                )
            if "title" in updates:
                conn.execute(
                    "UPDATE tasks SET title=? WHERE id=?",
                    (updates["title"], task_id),
                )

    def delete_task(self, task_id):
        with self._conn() as conn:
            conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))


db = Database()
