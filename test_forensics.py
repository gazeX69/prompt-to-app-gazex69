import asyncio
import urllib.request
import uuid
import os
import shutil
import time
from backend.models.schemas import GenerateRequest
from backend.orchestrator.project_orchestrator import generate_project_async
from backend.main import _register_builtin_skills
from backend.sandbox.executor import _runtime_registry
from playwright.async_api import async_playwright

async def run_forensics():
    _register_builtin_skills()
    project_id = f"forensic_{uuid.uuid4().hex[:6]}"
    print(f"Running Forensic Test on project: {project_id}")
    
    req = GenerateRequest(project_id=project_id, prompt="make login with php")
    res = await generate_project_async(req)
    
    entry = _runtime_registry.get(project_id)
    if not entry:
        print("No runtime found!")
        return
        
    preview_url = entry.preview_url
    run_id = entry.run_id
    
    print(f"[PreviewForensics] backend_url={preview_url}")
    iframe_url = f"{preview_url}/?run_id={run_id}&t={int(time.time() * 1000)}"
    print(f"[PreviewForensics] iframe_url={iframe_url}")
    print(f"[PreviewForensics] url_match={preview_url == iframe_url}")
    
    # Task 3: Compare Query Parameter Behavior
    # Fetch /
    req_root = urllib.request.urlopen(preview_url)
    resp_root = req_root.read().decode('utf-8', errors='replace')
    
    # Fetch /?run_id=...
    req_runid = urllib.request.urlopen(iframe_url)
    resp_runid = req_runid.read().decode('utf-8', errors='replace')
    
    run_dir = os.path.join(os.getcwd(), "workspaces", project_id, run_id)
    os.makedirs(run_dir, exist_ok=True)
    
    with open(os.path.join(run_dir, "response_root.html"), "w", encoding="utf-8") as f:
        f.write(resp_root)
    with open(os.path.join(run_dir, "response_runid.html"), "w", encoding="utf-8") as f:
        f.write(resp_runid)
        
    print(f"Response / length: {len(resp_root)}")
    print(f"Response /?run_id=... length: {len(resp_runid)}")
    
    # Task 2: Playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Test 1: Root
        page = await browser.new_page()
        await page.goto(preview_url, wait_until='networkidle')
        await page.screenshot(path=os.path.join(run_dir, "runtime_dom.png"))
        
        runtime_dom_html = await page.evaluate("() => document.body.innerHTML")
        runtime_dom_text = await page.evaluate("() => document.body.innerText")
        with open(os.path.join(run_dir, "runtime_dom.html"), "w", encoding="utf-8") as f:
            f.write(runtime_dom_html)
            
        print(f"Playwright Root visible text count: {len(runtime_dom_text.strip())}")
        
        # Test 2: Iframe
        page2 = await browser.new_page()
        await page2.goto(iframe_url, wait_until='networkidle')
        await page2.screenshot(path=os.path.join(run_dir, "playwright_screenshot.png"))
        
        iframe_dom_html = await page2.evaluate("() => document.body.innerHTML")
        iframe_dom_text = await page2.evaluate("() => document.body.innerText")
        with open(os.path.join(run_dir, "iframe_dom.html"), "w", encoding="utf-8") as f:
            f.write(iframe_dom_html)
            
        print(f"Playwright Iframe visible text count: {len(iframe_dom_text.strip())}")
        
        await browser.close()
        
    print("Forensics complete.")

if __name__ == "__main__":
    asyncio.run(run_forensics())
