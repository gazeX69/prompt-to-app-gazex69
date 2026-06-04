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

        # Reliability Metrics Memory
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reliability_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT
            )
        ''')

        # AI Telemetry Log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_telemetry_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                provider_id TEXT,
                provider_name TEXT,
                provider_type TEXT,
                model TEXT,
                latency_ms INTEGER,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                cost REAL DEFAULT 0.0,
                status TEXT,
                error_message TEXT,
                system_prompt_preview TEXT,
                user_prompt_preview TEXT,
                response_preview TEXT
            )
        ''')

        # AI Failover Log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_failover_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                failed_provider_id TEXT,
                failed_provider_name TEXT,
                failed_provider_type TEXT,
                error_message TEXT,
                next_provider_id TEXT,
                next_provider_name TEXT,
                next_provider_type TEXT
            )
        ''')
        
        conn.commit()

# Ensure DB is initialized on import
init_db()

