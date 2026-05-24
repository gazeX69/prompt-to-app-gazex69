import asyncio
import uuid
from backend.models.schemas import GenerateRequest
from backend.orchestrator.project_orchestrator import generate_project_async
from backend.main import _register_builtin_skills

async def run_tests():
    _register_builtin_skills()
    project_id = f"test_project_{uuid.uuid4().hex[:6]}"
    print(f"Running Phase 2B Test on project: {project_id}")
    
    prompts = [
        "create a login page",
        "create a todo list app"
    ]
    
    for i, prompt in enumerate(prompts):
        print(f"\n======================================")
        print(f"RUNNING TEST {i+1}: {prompt}")
        print(f"======================================")
        req = GenerateRequest(project_id=project_id, prompt=prompt)
        try:
            await generate_project_async(req)
        except Exception as e:
            print(f"Exception during test {i+1}: {e}")

if __name__ == "__main__":
    asyncio.run(run_tests())
