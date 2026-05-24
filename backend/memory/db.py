import sqlite3
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("MEMORY_DB_PATH", "orchestrator_memory.db"))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    logger.info(f"Initializing Memory DB at {DB_PATH}")
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Project Memory
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_memory (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ecosystem TEXT,
                architecture_notes TEXT
            )
        ''')
        
        # Reflection / Repair Memory
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reflection_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT,
                failure_type TEXT,
                stderr TEXT,
                stdout TEXT,
                patch_summary TEXT,
                success BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES project_memory(id)
            )
        ''')
        
        # Task Memory
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT,
                task_description TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES project_memory(id)
            )
        ''')
        
        conn.commit()

# Ensure DB is initialized on import
init_db()
