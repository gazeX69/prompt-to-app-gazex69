import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.core.provider_registry import list_providers, set_default_provider, get_provider, ProviderRegistry

router = APIRouter()

class SetDefaultRequest(BaseModel):
    provider: str

class TestProviderRequest(BaseModel):
    provider: str
    model: str = None

class ProviderInstanceRequest(BaseModel):
    name: str = None
    provider_type: str
    api_key: str = None
    base_url: str = None
    model: str = None
    priority: int = 5
    is_enabled: bool = True

@router.get("/providers")
def get_providers():
    """List all registered AI providers and their status."""
    try:
        return list_providers()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/providers/default")
def change_default_provider(req: SetDefaultRequest):
    """Change the default/active AI provider."""
    try:
        set_default_provider(req.provider)
        return {"success": True, "message": f"Default provider changed to {req.provider}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/providers/test")
def test_provider(req: TestProviderRequest):
    """Test connection/completions for a specific provider."""
    try:
        prov = get_provider(req.provider)
        if not prov.is_available():
            return {
                "success": False,
                "message": f"Provider {req.provider} is not configured/available (missing API keys)"
            }
        
        # Make a quick test completion request
        system_prompt = "You are a test assistant."
        user_prompt = "Say only 'OK' if you can read this."
        response = prov.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=req.model,
            max_tokens=10,
            temperature=0.0
        )
        return {
            "success": True,
            "message": "Connection test succeeded",
            "response": response.strip()
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection test failed: {str(e)}"
        }

@router.get("/providers/instances")
def get_provider_instances():
    """List all configured AI provider instances."""
    try:
        return ProviderRegistry.get_instance().list_instances()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/providers/instances")
def add_provider_instance(req: ProviderInstanceRequest):
    """Add a new AI provider instance."""
    try:
        new_inst = ProviderRegistry.get_instance().add_instance(req.dict())
        return {"success": True, "instance": new_inst}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/providers/instances/{id}")
def update_provider_instance(id: str, req: ProviderInstanceRequest):
    """Update an existing AI provider instance."""
    try:
        updated = ProviderRegistry.get_instance().update_instance(id, req.dict())
        return {"success": True, "instance": updated}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/providers/instances/{id}")
def delete_provider_instance(id: str):
    """Delete an AI provider instance."""
    try:
        ProviderRegistry.get_instance().delete_instance(id)
        return {"success": True, "message": f"Instance {id} deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/providers/instances/{id}/test")
def test_provider_instance(id: str):
    """Test connection for a specific AI provider instance."""
    try:
        prov = get_provider(id)
        response = prov.complete(
            system_prompt="You are a test assistant.",
            user_prompt="Say only 'OK' if you can read this.",
            max_tokens=10,
            temperature=0.0
        )
        return {
            "success": True,
            "message": "Connection test succeeded",
            "response": response.strip()
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection test failed: {str(e)}"
        }


class RecordEventRequest(BaseModel):
    event_type: str
    details: dict = None

@router.get("/reliability")
def get_reliability_metrics():
    """Retrieve system reliability metrics."""
    from backend.core.reliability import ReliabilityTracker
    try:
        return ReliabilityTracker.get_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reliability/event")
def record_reliability_event(req: RecordEventRequest):
    """Record a system reliability lifecycle event."""
    from backend.core.reliability import ReliabilityTracker
    try:
        ReliabilityTracker.record_event(req.event_type, req.details)
        return {"success": True, "message": f"Recorded event: {req.event_type}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/telemetry/stats")
def get_telemetry_stats():
    """Retrieve summarized AI model usage and performance metrics."""
    from backend.services.telemetry_service import TelemetryService
    try:
        return TelemetryService.get_summary_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/telemetry/logs")
def get_telemetry_logs(limit: int = 100):
    """Retrieve detailed logs of recent AI calls."""
    from backend.services.telemetry_service import TelemetryService
    try:
        return TelemetryService.get_recent_logs(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/telemetry/logs")
def clear_telemetry_logs():
    """Reset and erase all stored telemetry and failover logs."""
    from backend.services.telemetry_service import TelemetryService
    try:
        TelemetryService.clear_logs()
        return {"success": True, "message": "Telemetry logs cleared successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


