import asyncio
import uuid
import time
from backend.models.schemas import GenerateRequest
from backend.orchestrator.project_orchestrator import generate_project_async
from backend.main import _register_builtin_skills

async def run_stress_test():
    _register_builtin_skills()
    project_id = f"stress_test_{uuid.uuid4().hex[:6]}"
    print(f"Running Stress Validation on project: {project_id}")
    
    sequence = [
        "create a React counter app",
        "make login with php",
        "create a React todo app",
        "create a PHP dashboard app",
        "create a Static HTML landing page",
        "create a React calculator app"
    ]
    
    # 3 repetitions
    all_prompts = sequence * 3
    
    # Failure scenarios
    all_prompts.extend([
        "create a broken React app with a missing closing tag syntax error in App.tsx",
        "create a malformed PHP app with a deliberate Parse error missing semicolon",
        "create a React app with an invalid dependency import 'non-existent-module-xyz'"
    ])
    
    total = len(all_prompts)
    results = []
    
    for i, prompt in enumerate(all_prompts):
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
            
        # Give a short breather before the next one to allow port to unbind properly if needed
        # (Though our allocator should handle it immediately anyway!)
        await asyncio.sleep(2)
        
    print("\n\n" + "="*50)
    print("STRESS TEST RESULTS MATRIX")
    print("="*50)
    for i, (prompt, success, dur, err) in enumerate(results):
        status = "PASS" if success else "FAIL"
        # The last 3 are intended to fail, so if they fail gracefully, that's actually a pass for the system!
        if i >= 18:
            if not success:
                status = "PASS (Expected Failure)"
            else:
                status = "FAIL (Should have failed but succeeded?)"
                
        print(f"Run {i+1:02d} | {status:25s} | {dur:4.1f}s | {prompt[:40]}...")

if __name__ == "__main__":
    asyncio.run(run_stress_test())
