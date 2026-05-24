import asyncio
import uuid
import sys
from backend.models.schemas import GenerateRequest
from backend.orchestrator.project_orchestrator import generate_project_async
from backend.main import _register_builtin_skills

async def run_tests():
    _register_builtin_skills()
    project_id = f"test_truth_{uuid.uuid4().hex[:6]}"
    print(f"Running Phase 2B Step 2 Test on project: {project_id}")
    
    prompts = [
        "make login with php"
    ]
    
    for i, prompt in enumerate(prompts):
        print(f"\n======================================")
        print(f"RUNNING TEST {i+1}: {prompt}")
        print(f"======================================")
        req = GenerateRequest(project_id=project_id, prompt=prompt)
        try:
            res = await generate_project_async(req)
            if not res.success:
                print(f"Test {i+1} failed: {res.error}")
            else:
                print(f"Test {i+1} succeeded.")
        except Exception as e:
            print(f"Exception during test {i+1}: {e}")

if __name__ == "__main__":
    asyncio.run(run_tests())
