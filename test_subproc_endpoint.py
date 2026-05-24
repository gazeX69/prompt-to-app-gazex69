"""Test endpoint to check subprocess under uvicorn."""
import asyncio
from fastapi import FastAPI

app = FastAPI()


@app.get("/test-subprocess")
async def test_subprocess():
    policy = asyncio.get_event_loop_policy()
    loop = asyncio.get_running_loop()
    result = {
        "policy": type(policy).__name__,
        "loop": type(loop).__name__,
        "has_subprocess_exec": hasattr(loop, "subprocess_exec"),
    }
    try:
        proc = await asyncio.create_subprocess_exec(
            "cmd", "/c", "echo", "hello",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        result["subprocess_ok"] = True
        result["output"] = out.decode().strip()
    except Exception as e:
        result["subprocess_ok"] = False
        result["error_type"] = type(e).__name__
        result["error"] = str(e)
        result["error_repr"] = repr(e)
    return result
