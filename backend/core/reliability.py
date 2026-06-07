import logging
import json
from datetime import datetime, timezone
from backend.memory.db import get_connection

logger = logging.getLogger(__name__)

class ReliabilityTracker:
    @staticmethod
    def record_event(event_type: str, details: dict = None) -> None:
        """
        Record a reliability event (e.g., 'start', 'stop', 'failure').
        """
        try:
            details_str = json.dumps(details) if details else None
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO reliability_metrics (event_type, details) VALUES (?, ?)",
                    (event_type, details_str)
                )
                conn.commit()
        except Exception as e:
            logger.exception("Failed to record reliability event: %s", e)

    @staticmethod
    def get_metrics() -> dict:
        """
        Calculates Uptime, Downtime, Availability, and MTBF from events.
        """
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT event_type, timestamp FROM reliability_metrics ORDER BY timestamp ASC")
                rows = cursor.fetchall()
        except Exception as e:
            logger.exception("Failed to retrieve reliability metrics: %s", e)
            return {"availability": 1.0, "mtbf_hours": 0.0, "total_failures": 0}

        if not rows:
            # Seed default metrics if no history exists yet
            return {
                "availability": 1.0,
                "mtbf_hours": 24.0,
                "uptime_seconds": 3600,
                "downtime_seconds": 0,
                "total_failures": 0
            }

        # Parse events to compute uptime and downtime segments
        # SQLite timestamps are UTC by default in string format "YYYY-MM-DD HH:MM:SS"
        parsed_events = []
        for r in rows:
            try:
                # Add timezone info to parse safely
                dt = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
            except ValueError:
                # Fallback if standard format
                dt = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            parsed_events.append((r["event_type"], dt))

        uptime_seconds = 0.0
        downtime_seconds = 0.0
        failures = 0
        
        current_state = None  # 'up', 'down', None
        last_change_time = None

        for event_type, dt in parsed_events:
            if event_type == "start":
                if current_state == "down" and last_change_time:
                    downtime_seconds += (dt - last_change_time).total_seconds()
                current_state = "up"
                last_change_time = dt
            elif event_type == "stop":
                if current_state == "up" and last_change_time:
                    uptime_seconds += (dt - last_change_time).total_seconds()
                current_state = "stopped"
                last_change_time = dt
            elif event_type == "failure":
                failures += 1
                if current_state == "up" and last_change_time:
                    uptime_seconds += (dt - last_change_time).total_seconds()
                current_state = "down"
                last_change_time = dt

        # Handle active segment up to now
        now = datetime.now(timezone.utc)
        if current_state == "up" and last_change_time:
            uptime_seconds += (now - last_change_time).total_seconds()
        elif current_state == "down" and last_change_time:
            downtime_seconds += (now - last_change_time).total_seconds()

        # Add safe default constants if no failures occurred or duration is tiny
        if uptime_seconds == 0 and downtime_seconds == 0:
            availability = 1.0
        else:
            availability = uptime_seconds / (uptime_seconds + downtime_seconds)

        mtbf_hours = (uptime_seconds / 3600.0) / failures if failures > 0 else (uptime_seconds / 3600.0)

        return {
            "availability": round(availability, 4),
            "mtbf_hours": round(mtbf_hours, 2),
            "uptime_seconds": int(uptime_seconds),
            "downtime_seconds": int(downtime_seconds),
            "total_failures": failures
        }
