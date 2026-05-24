from typing import Optional
from backend.memory.db import get_connection

class ProjectMemory:
    @staticmethod
    def initialize_project(project_id: str, ecosystem: str):
        with get_connection() as conn:
            conn.execute('''
                INSERT OR IGNORE INTO project_memory (id, ecosystem)
                VALUES (?, ?)
            ''', (project_id, ecosystem))
            conn.commit()

    @staticmethod
    def update_architecture_notes(project_id: str, notes: str):
        with get_connection() as conn:
            conn.execute('''
                UPDATE project_memory 
                SET architecture_notes = ? 
                WHERE id = ?
            ''', (notes, project_id))
            conn.commit()

    @staticmethod
    def get_project_state(project_id: str) -> Optional[dict]:
        with get_connection() as conn:
            cur = conn.execute('SELECT * FROM project_memory WHERE id = ?', (project_id,))
            row = cur.fetchone()
            return dict(row) if row else None
