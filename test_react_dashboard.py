"""React pipeline integration test."""
import asyncio
import httpx
import socketio
import time
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

BACKEND_URL = 'http://127.0.0.1:8000'
PROJECT_ID = f'react-{int(time.time())}'
events = []


async def test():
    sio = socketio.AsyncClient()

    @sio.on('connect')
    async def on_connect():
        print(f'[EVENT] connect (sid={sio.sid})')

    @sio.on('agent_state')
    async def on_state(s):
        events.append(('agent_state', s))
        print(f'[EVENT] agent_state = {s}')

    @sio.on('terminal_line')
    async def on_line(d):
        text = d.get('text', '')
        t = d.get('type', '?')
        events.append(('terminal_line', text, t))
        if t in ('stderr', 'info'):
            print(f'[EVENT] terminal_line [{t}] {text[:150]}')

    @sio.on('preview_ready')
    async def on_preview(d):
        events.append(('preview_ready', d))
        print(f'[EVENT] preview_ready = {d}')

    print(f'[TEST] Connecting to {BACKEND_URL} ...')
    await sio.connect(BACKEND_URL)
    print('[TEST] Connected')

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(f'{BACKEND_URL}/generate', json={
            'prompt': 'buat dashboard admin react dengan tailwind',
            'project_id': PROJECT_ID,
            'auto_repair': True,
            'enabled_skills': ['react-vite']
        })
        print(f'[TEST] POST status={resp.status_code}')

    deadline = time.time() + 300
    while time.time() < deadline:
        await asyncio.sleep(0.5)
        states = [e for e in events if e[0] == 'agent_state']
        if states and states[-1][1] in ('success', 'failed'):
            print(f'\n[TEST] Terminal state: {states[-1][1]}')
            await asyncio.sleep(1)
            print(f'\n=== RESULTS ({len(events)} events) ===')
            for e in events:
                if e[0] == 'terminal_line':
                    print(f'  [{e[2]}] {e[1][:200]}')
                elif e[0] == 'agent_state':
                    print(f'  state = {e[1]}')
                elif e[0] == 'preview_ready':
                    print(f'  preview_ready = {e[1]}')
                else:
                    print(f'  {e[0]}')
            await sio.disconnect()
            return states[-1][1] == 'success'

    print('[TEST] TIMEOUT')
    await sio.disconnect()
    return False


if __name__ == '__main__':
    # Kill leftover vite dev servers
    subprocess.run(['taskkill', '/F', '/IM', 'node.exe'], capture_output=True)
    time.sleep(2)
    result = asyncio.run(test())
    print(f'\n[TEST] {"PASS" if result else "FAIL"}')
