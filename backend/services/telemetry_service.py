import os
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from backend.memory.db import get_connection

logger = logging.getLogger(__name__)

# Estimate pricing (USD per 1M tokens)
# Source: Standard pricing for common models
MODEL_PRICING = {
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "o1-preview": {"input": 15.00, "output": 60.00},
    "o1-mini": {"input": 3.00, "output": 12.00},
    # Qwen
    "qwen-plus": {"input": 0.54, "output": 1.62},
    "qwen-turbo": {"input": 0.14, "output": 0.42},
    "qwen-max": {"input": 2.80, "output": 8.40},
    # Gemini
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    # Anthropic Claude
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    # Local LLM is free!
    "local": {"input": 0.0, "output": 0.0}
}

class TelemetryService:
    @staticmethod
    def calculate_cost(provider_type: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate the estimated USD cost of a completion call."""
        if provider_type == "local":
            return 0.0
            
        # Try matching exact model name first
        pricing = None
        for key, value in MODEL_PRICING.items():
            if key in model.lower():
                pricing = value
                break
                
        if not pricing:
            # Fallback based on provider type if model not found
            if provider_type == "openai":
                pricing = MODEL_PRICING["gpt-4o-mini"]
            elif provider_type == "qwen":
                pricing = MODEL_PRICING["qwen-plus"]
            elif provider_type == "gemini":
                pricing = MODEL_PRICING["gemini-1.5-flash"]
            elif provider_type == "anthropic":
                pricing = MODEL_PRICING["claude-3-5-haiku-20241022"]
            else:
                pricing = {"input": 0.50, "output": 1.50}  # Generic model average
                
        input_cost = (prompt_tokens / 1_000_000.0) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000.0) * pricing["output"]
        return input_cost + output_cost

    @staticmethod
    def calculate_saved_cost(provider_type: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost saved by using a local model instead of a paid model like Claude 3.5 Sonnet."""
        if provider_type != "local":
            return 0.0
            
        # Compare to a standard paid developer model, e.g. Claude 3.5 Sonnet
        pricing = MODEL_PRICING["claude-3-5-sonnet-20241022"]
        input_cost = (prompt_tokens / 1_000_000.0) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000.0) * pricing["output"]
        return input_cost + output_cost

    @staticmethod
    def log_call(
        provider_id: str,
        provider_name: str,
        provider_type: str,
        model: str,
        latency_ms: int,
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
        status: str,
        error_message: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        response: Optional[str] = None
    ):
        """Log an LLM call to telemetry_log table, with prompt/response truncation to avoid db bloat."""
        try:
            # Handle token fallbacks if none returned
            p_tokens = prompt_tokens or len(system_prompt or "") // 4 + len(user_prompt or "") // 4
            c_tokens = completion_tokens or len(response or "") // 4
            t_tokens = p_tokens + c_tokens
            
            # Truncate prompt/responses to 4000 characters to prevent db bloat
            sys_preview = system_prompt[:4000] + "\n... (truncated)" if system_prompt and len(system_prompt) > 4000 else system_prompt
            usr_preview = user_prompt[:4000] + "\n... (truncated)" if user_prompt and len(user_prompt) > 4000 else user_prompt
            resp_preview = response[:4000] + "\n... (truncated)" if response and len(response) > 4000 else response
            
            cost = TelemetryService.calculate_cost(provider_type, model, p_tokens, c_tokens) if status == "success" else 0.0
            
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO ai_telemetry_log (
                        provider_id, provider_name, provider_type, model, latency_ms,
                        prompt_tokens, completion_tokens, total_tokens, cost, status,
                        error_message, system_prompt_preview, user_prompt_preview, response_preview
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        provider_id, provider_name, provider_type, model, latency_ms,
                        p_tokens, c_tokens, t_tokens, cost, status,
                        error_message, sys_preview, usr_preview, resp_preview
                    )
                )
                conn.commit()
        except Exception as e:
            logger.exception("Failed to write AI telemetry log: %s", e)

    @staticmethod
    def log_failover(
        failed_id: str,
        failed_name: str,
        failed_type: str,
        error_message: str,
        next_id: str,
        next_name: str,
        next_type: str
    ):
        """Log an agent failover event."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO ai_failover_log (
                        failed_provider_id, failed_provider_name, failed_provider_type, error_message,
                        next_provider_id, next_provider_name, next_provider_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        failed_id, failed_name, failed_type, error_message,
                        next_id, next_name, next_type
                    )
                )
                conn.commit()
        except Exception as e:
            logger.exception("Failed to write AI failover log: %s", e)

    @staticmethod
    def get_summary_stats() -> Dict[str, any]:
        """Aggregate stats for UI dashboard charts and cards."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                
                # Overall Stats
                cursor.execute(
                    """
                    SELECT 
                        COUNT(*) as total_calls,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_calls,
                        AVG(CASE WHEN status = 'success' THEN latency_ms ELSE NULL END) as avg_latency,
                        SUM(prompt_tokens) as total_prompt_tokens,
                        SUM(completion_tokens) as total_completion_tokens,
                        SUM(total_tokens) as total_tokens,
                        SUM(cost) as total_cost
                    FROM ai_telemetry_log
                    """
                )
                overall = cursor.fetchone()
                
                # Cost saved by local LLM calls
                cursor.execute(
                    """
                    SELECT prompt_tokens, completion_tokens, model
                    FROM ai_telemetry_log
                    WHERE provider_type = 'local' AND status = 'success'
                    """
                )
                local_calls = cursor.fetchall()
                total_saved = 0.0
                for c in local_calls:
                    total_saved += TelemetryService.calculate_saved_cost("local", c["model"], c["prompt_tokens"], c["completion_tokens"])
                
                # Provider Performance Breakdowns
                cursor.execute(
                    """
                    SELECT 
                        provider_name,
                        provider_type,
                        model,
                        COUNT(*) as calls,
                        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                        AVG(CASE WHEN status = 'success' THEN latency_ms ELSE NULL END) as avg_lat,
                        SUM(total_tokens) as tokens,
                        SUM(cost) as cost
                    FROM ai_telemetry_log
                    GROUP BY provider_name, provider_type, model
                    """
                )
                providers_db = cursor.fetchall()
                
                providers_list = []
                for p in providers_db:
                    success_rate = round(p["success"] / p["calls"], 4) if p["calls"] > 0 else 1.0
                    providers_list.append({
                        "provider_name": p["provider_name"],
                        "provider_type": p["provider_type"],
                        "model": p["model"],
                        "calls": p["calls"],
                        "success_rate": success_rate,
                        "avg_latency_ms": int(p["avg_lat"] or 0),
                        "total_tokens": p["tokens"] or 0,
                        "cost": round(p["cost"] or 0.0, 4)
                    })
                    
                # Failover Event Count
                cursor.execute("SELECT COUNT(*) FROM ai_failover_log")
                failover_count = cursor.fetchone()[0]
                
            total_calls = overall["total_calls"] or 0
            success_calls = overall["success_calls"] or 0
            success_rate = round(success_calls / total_calls, 4) if total_calls > 0 else 1.0
            
            return {
                "total_calls": total_calls,
                "success_rate": success_rate,
                "avg_latency_ms": int(overall["avg_latency"] or 0),
                "total_prompt_tokens": overall["total_prompt_tokens"] or 0,
                "total_completion_tokens": overall["total_completion_tokens"] or 0,
                "total_tokens": overall["total_tokens"] or 0,
                "total_cost": round(overall["total_cost"] or 0.0, 4),
                "total_saved_usd": round(total_saved, 4),
                "failover_count": failover_count,
                "providers": providers_list
            }
        except Exception as e:
            logger.exception("Failed to query telemetry summary stats: %s", e)
            return {
                "total_calls": 0,
                "success_rate": 1.0,
                "avg_latency_ms": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "total_saved_usd": 0.0,
                "failover_count": 0,
                "providers": []
            }

    @staticmethod
    def get_recent_logs(limit: int = 50) -> List[Dict[str, any]]:
        """Fetch recent LLM call logs."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    SELECT * FROM ai_telemetry_log
                    ORDER BY timestamp DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,)
                )

                rows = cursor.fetchall()
                
            logs = []
            for r in rows:
                logs.append({
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "provider_id": r["provider_id"],
                    "provider_name": r["provider_name"],
                    "provider_type": r["provider_type"],
                    "model": r["model"],
                    "latency_ms": r["latency_ms"],
                    "prompt_tokens": r["prompt_tokens"],
                    "completion_tokens": r["completion_tokens"],
                    "total_tokens": r["total_tokens"],
                    "cost": round(r["cost"] or 0.0, 4),
                    "status": r["status"],
                    "error_message": r["error_message"],
                    "system_prompt": r["system_prompt_preview"],
                    "user_prompt": r["user_prompt_preview"],
                    "response": r["response_preview"]
                })
            return logs
        except Exception as e:
            logger.exception("Failed to query telemetry logs: %s", e)
            return []

    @staticmethod
    def clear_logs():
        """Reset all logs."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM ai_telemetry_log")
                cursor.execute("DELETE FROM ai_failover_log")
                conn.commit()
        except Exception as e:
            logger.exception("Failed to clear telemetry: %s", e)
