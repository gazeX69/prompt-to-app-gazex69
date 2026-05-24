import asyncio
import uuid
import time
from backend.models.schemas import GenerateRequest
from backend.orchestrator.project_orchestrator import generate_project_async
from backend.main import _register_builtin_skills

async def run_shadow_test():
    _register_builtin_skills()
    project_id = f"shadow_test_{uuid.uuid4().hex[:6]}"
    print(f"Running Shadow Planner Validation on project: {project_id}")
    
    sequence = [
        "create a React todo app"
    ]
    
    total = len(sequence)
    results = []
    
    for i, prompt in enumerate(sequence):
        print(f"\n{'='*50}")
        print(f"RUN {i+1}/{total}: {prompt}")
        print(f"{'='*50}")
        
        req = GenerateRequest(project_id=project_id, prompt=prompt)
        start_t = time.time()
        
        try:
            res = await generate_project_async(req)
            duration = time.time() - start_t
            if res.success:
                print(f"[Run {i+1}] SUCCESS in {duration:.1f}s")
                results.append((prompt, True, duration, None))
            else:
                print(f"[Run {i+1}] FAILED gracefully in {duration:.1f}s. Error: {res.error}")
                results.append((prompt, False, duration, res.error))
        except Exception as e:
            duration = time.time() - start_t
            print(f"[Run {i+1}] CRASHED unexpectedly: {e}")
            results.append((prompt, False, duration, str(e)))
            
        await asyncio.sleep(2)
        
    print("\n\n" + "="*50)
    print("SHADOW MODE TEST RESULTS")
    print("="*50)
    for i, (prompt, success, dur, err) in enumerate(results):
        status = "PASS" if success else "FAIL"
        print(f"Run {i+1:02d} | {status:25s} | {dur:4.1f}s | {prompt[:40]}...")

if __name__ == "__main__":
    asyncio.run(run_shadow_test())
