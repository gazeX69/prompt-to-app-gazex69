import asyncio
import json
import logging
import os
import httpx

logger = logging.getLogger(__name__)

class RuntimeClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or os.getenv("RUNTIME_BASE_URL", "http://127.0.0.1:3001")
        self._event_callback = None

    def set_event_callback(self, callback):
        """Callback format: async def callback(event_type: str, payload: dict)"""
        self._event_callback = callback

    async def create_workspace(self) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/runtime/workspace/create")
            resp.raise_for_status()
            return resp.json()

    async def run_command(self, cmd_id: str, command: str, args: list, cwd: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/runtime/command/run", json={
                "id": cmd_id,
                "command": command,
                "args": args,
                "cwd": cwd
            })
            resp.raise_for_status()
            return resp.json()

    async def start_dev(
        self,
        cmd_id: str,
        cwd: str,
        port: int | None = None,
        auto_increment_ports: bool = True,
        max_port_attempts: int = 10,
        health_timeout_ms: int = 30000,
    ) -> dict:
        payload = {
            "id": cmd_id,
            "cwd": cwd,
            "autoIncrementPorts": auto_increment_ports,
            "maxPortAttempts": max_port_attempts,
            "healthTimeoutMs": health_timeout_ms,
        }
        if port is not None:
            payload["port"] = port
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/runtime/dev/start", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def stop_dev(self, cmd_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/runtime/dev/stop", json={
                "id": cmd_id
            })
            resp.raise_for_status()
            return resp.json()

    async def start_event_stream(self):
        """Infinite loop to consume SSE stream from runtime with retry logic."""
        while True:
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    logger.info(f"Connecting to Runtime SSE at {self.base_url}/runtime/events")
                    async with client.stream("GET", f"{self.base_url}/runtime/events") as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str:
                                    try:
                                        event = json.loads(data_str)
                                        if self._event_callback:
                                            await self._event_callback(event.get("type"), event.get("payload", {}))
                                    except json.JSONDecodeError:
                                        pass
            except Exception as e:
                logger.error(f"Runtime connection lost or unavailable: {e}. Retrying in 5 seconds...")
                if self._event_callback:
                    await self._event_callback("RUNTIME_DISCONNECTED", {"error": str(e)})
            
            await asyncio.sleep(5)

runtime_client = RuntimeClient()
