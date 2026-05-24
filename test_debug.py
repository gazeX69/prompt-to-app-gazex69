"""
Debug test: full pipeline integration test with detailed event tracing.
"""
import asyncio
import httpx
import socketio
import time
import sys
import subprocess

sys.path.insert(0, r'C:\Users\gaze\Documents\cobacoba\ai-agent')
from backend.sandbox.executor import run_dev_server_array_async

BACKEND_URL = 'http://127.0.0.1:8000'
PROJECT_ID = f'test2-{int(time.time())}'
events = []


async def test_full_pipeline():
    # Kill any leftover PHP
    subprocess.run(['taskkill', '/F', '/IM', 'php.exe'], capture_output=True)
    await asyncio.sleep(1)

    sio = socketio.AsyncClient()

    @sio.on('connect')
    async def on_connect():
        events.append(('connect', time.time()))
        print(f'[EVENT] connect')

    @sio.on('agent_state')
    async def on_state(s):
        events.append(('agent_state', s, time.time()))
        print(f'[EVENT] agent_state = {s}')

    @sio.on('terminal_line')
    async def on_line(d):
        text = d.get('text', '')[:120]
        t = d.get('type', '?')
        events.append(('terminal_line', text, t))
        print(f'[EVENT] terminal_line [{t}] {text}')

    @sio.on('preview_ready')
    async def on_preview(d):
        events.append(('preview_ready', d))
        print(f'[EVENT] preview_ready = {d}')

    await sio.connect(BACKEND_URL, transports=['websocket'])
    print('[TEST] Socket connected')

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f'{BACKEND_URL}/generate', json={
            'prompt': 'buat halaman login sederhana dengan php',
            'project_id': PROJECT_ID,
            'auto_repair': True,
            'enabled_skills': ['php-basic']
        })
        print(f'[TEST] POST status={resp.status_code} body={resp.text[:200]}')

    deadline = time.time() + 60
    while time.time() < deadline:
        await asyncio.sleep(0.5)
        states = [e for e in events if e[0] == 'agent_state']
        if states and states[-1][1] in ('success', 'failed'):
            print(f'\n[TEST] Terminal state: {states[-1][1]}')
            await asyncio.sleep(1)
            print('\n=== FULL EVENT SEQUENCE ===')
            for e in events:
                print(f'  {e[0]}: {e[1]}')
            await sio.disconnect()
            return

    print('[TEST] TIMEOUT - no terminal state')
    await sio.disconnect()


async def test_direct_executor():
    """Test executor directly on the project"""
    print('\n=== DIRECT EXECUTOR TEST ===')
    print(f'Project: {PROJECT_ID}')
    
    # First check if workspace exists
    import os
    ws = f'C:\\Users\\gaze\\Documents\\cobacoba\\ai-agent\\workspaces\\{PROJECT_ID}'
    print(f'Workspace exists: {os.path.isdir(ws)}')
    if os.path.isdir(ws):
        print(f'Files: {os.listdir(ws)}')
    
    result = await run_dev_server_array_async(
        PROJECT_ID,
        ['php', '-S', '127.0.0.1:3001'],
        port_pattern=r'http://(?:localhost|127\.0\.0\.1):(\d+)'
    )
    print(f'Executor result: success={result.success} error={result.error} exit={result.exit_code}')
    print(f'Stdout: {(result.stdout or "")[:200]}')
    print(f'Stderr: {(result.stderr or "")[:200]}')


if __name__ == '__main__':
    import sys
    if '--exec' in sys.argv:
        asyncio.run(test_direct_executor())
    else:
        asyncio.run(test_full_pipeline())
