import asyncio
import uuid
import sys
from backend.models.schemas import GenerateRequest
from backend.orchestrator.project_orchestrator import generate_project_async
from backend.main import _register_builtin_skills

async def run_tests():
    _register_builtin_skills()
    project_id = f"test_project_{uuid.uuid4().hex[:6]}"
    
    prompts = [
        "create a login page",
        "create a task list app",
        "create a calculator app"
    ]
    
    for i, prompt in enumerate(prompts):
        print(f"\n==================== TEST {i+1} ====================")
        print(f"Prompt: {prompt}")
        req = GenerateRequest(
            project_id=project_id,
            prompt=prompt
        )
        
        try:
            res = await generate_project_async(req)
            print(f"Success: {res.success}")
            if not res.success:
                print(f"Error: {res.error}")
        except Exception as e:
            print(f"Unhandled Exception: {e}")

if __name__ == "__main__":
    asyncio.run(run_tests())
