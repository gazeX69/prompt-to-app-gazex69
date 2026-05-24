import asyncio
import os
import uuid
import sys
from backend.sandbox.executor import run_dev_server_array_async

async def main():
    project_id = f"test_{uuid.uuid4().hex[:6]}"
    run_1 = "run_111"
    run_2 = "run_222"
    
    # Fake workspaces
    ws1 = os.path.join("workspaces", project_id, run_1)
    ws2 = os.path.join("workspaces", project_id, run_2)
    os.makedirs(ws1, exist_ok=True)
    os.makedirs(ws2, exist_ok=True)
    
    # We will use python's http.server as a mock dev server
    print("\n--- LAUNCHING FIRST DEV SERVER ---")
    res1 = await run_dev_server_array_async(
        project_id=project_id,
        args=[sys.executable, "-m", "http.server", "8081"],
        run_id=run_1,
        port_pattern=r"Serving HTTP on .* port (\d+)"
    )
    print("res1:", res1)
    
    # Wait a bit
    await asyncio.sleep(2)
    
    print("\n--- LAUNCHING SECOND DEV SERVER (SHOULD CLEANUP) ---")
    res2 = await run_dev_server_array_async(
        project_id=project_id,
        args=[sys.executable, "-m", "http.server", "8082"],
        run_id=run_2,
        port_pattern=r"Serving HTTP on .* port (\d+)"
    )
    print("res2:", res2)

if __name__ == "__main__":
    asyncio.run(main())
