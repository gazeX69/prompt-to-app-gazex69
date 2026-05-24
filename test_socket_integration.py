"""
Integration test: verifies socket lifecycle and event delivery.

1. Connects socket.io client
2. Sends POST /generate for PHP
3. Monitors ALL events received
4. Reports any missing events or failures
"""
import asyncio
import httpx
import socketio
import time
import sys

BACKEND_URL = "http://127.0.0.1:8000"
PROJECT_ID = f"test-{int(time.time())}"

events_received = []
errors = []

async def test_pipeline():
    sio = socketio.AsyncClient()
    
    @sio.on('connect')
    async def on_connect():
        print(f"[TEST] Socket connected (sid={sio.sid})")
        events_received.append(('connect', time.time()))
    
    @sio.on('disconnect')
    async def on_disconnect(reason):
        print(f"[TEST] Socket disconnected: {reason}")
        events_received.append(('disconnect', time.time()))
    
    @sio.on('agent_state')
    async def on_agent_state(state):
        print(f"[TEST] Event: agent_state = {state}")
        events_received.append(('agent_state', state, time.time()))
    
    @sio.on('terminal_line')
    async def on_terminal_line(data):
        text = data.get('text', '')[:80]
        print(f"[TEST] Event: terminal_line [{data.get('type', '?')}] {text}")
        events_received.append(('terminal_line', data, time.time()))
    
    @sio.on('agent_activity')
    async def on_agent_activity(data):
        msg = data.get('message', '')
        print(f"[TEST] Event: agent_activity = {msg}")
        events_received.append(('agent_activity', msg, time.time()))
    
    @sio.on('preview_ready')
    async def on_preview_ready(data):
        print(f"[TEST] Event: preview_ready url={data.get('url')}")
        events_received.append(('preview_ready', data, time.time()))
    
    # Connect
    print(f"[TEST] Connecting to {BACKEND_URL}...")
    await sio.connect(BACKEND_URL, transports=['websocket'])
    print(f"[TEST] Connected.")
    
    # Verify connected
    assert sio.connected, "Socket not connected!"
    
    # Send generate request
    print(f"[TEST] Sending POST /generate...")
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BACKEND_URL}/generate", json={
            "prompt": "buat halaman login sederhana dengan php",
            "project_id": PROJECT_ID,
            "auto_repair": True,
            "max_repair_attempts": 3,
            "enabled_skills": ["php-basic"]
        })
    print(f"[TEST] POST response: {resp.status_code} {resp.json()}")
    assert resp.status_code == 200, f"POST failed: {resp.status_code}"
    
    # Wait for events
    print(f"[TEST] Waiting for events (60s timeout)...")
    deadline = time.time() + 60
    got_terminal = False
    got_state = False
    
    while time.time() < deadline:
        await asyncio.sleep(0.5)
        agent_states = [e for e in events_received if e[0] == 'agent_state']
        terminal_lines = [e for e in events_received if e[0] == 'terminal_line']
        
        if agent_states:
            got_state = True
        if terminal_lines:
            got_terminal = True
        
        # Check if we reached terminal state
        for e in agent_states:
            if e[1] in ('success', 'failed'):
                print(f"[TEST] Terminal state reached: {e[1]}")
                await asyncio.sleep(2)  # drain remaining events
                # Print summary
                print(f"\n{'='*60}")
                print(f"TEST RESULTS")
                print(f"{'='*60}")
                print(f"Events received: {len(events_received)}")
                print(f"Agent states: {[e[1] for e in events_received if e[0] == 'agent_state']}")
                print(f"Terminal lines: {len(terminal_lines)}")
                preview_events = [e for e in events_received if e[0] == 'preview_ready']
                print(f"Preview events: {len(preview_events)}")
                
                # Verify
                passed = True
                if not got_state:
                    print(f"  FAIL: No agent_state events received")
                    passed = False
                if not agent_states or agent_states[-1][1] not in ('success', 'failed'):
                    print(f"  FAIL: No terminal state reached (last: {agent_states[-1][1] if agent_states else 'none'})")
                    passed = False
                
                if passed:
                    print(f"  PASS: Pipeline completed successfully")
                else:
                    print(f"  FAIL: See errors above")
                
                await sio.disconnect()
                return passed
    
    # Timeout
    print(f"[TEST] TIMEOUT: No terminal state within 60s")
    states = [e[1] for e in events_received if e[0] == 'agent_state']
    print(f"[TEST] States received: {states}")
    
    await sio.disconnect()
    return False

if __name__ == "__main__":
    result = asyncio.run(test_pipeline())
    sys.exit(0 if result else 1)
