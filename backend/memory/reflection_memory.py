from backend.memory.db import get_connection

class ReflectionMemory:
    @staticmethod
    def record_repair(project_id: str, failure_type: str, stderr: str, stdout: str, patch_summary: str, success: bool):
        with get_connection() as conn:
            conn.execute('''
                INSERT INTO reflection_memory (project_id, failure_type, stderr, stdout, patch_summary, success)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (project_id, failure_type, stderr, stdout, patch_summary, success))
            conn.commit()

    @staticmethod
    def get_past_repairs(project_id: str):
        with get_connection() as conn:
            cur = conn.execute('SELECT * FROM reflection_memory WHERE project_id = ? ORDER BY created_at DESC', (project_id,))
            return [dict(row) for row in cur.fetchall()]
