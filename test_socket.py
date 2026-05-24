import asyncio
import socketio
import sys

sio = socketio.AsyncClient()

@sio.on('connect')
async def on_connect():
    print("Connected to backend!")
    
@sio.on('terminal_line')
async def on_terminal_line(data):
    print(f"[{data.get('type')}] {data.get('text')}")

@sio.on('agent_state')
async def on_agent_state(data):
    print(f"[STATE] {data}")

@sio.on('preview_ready')
async def on_preview_ready(data):
    print(f"[PREVIEW] {data}")

async def main():
    await sio.connect('http://127.0.0.1:8000')
    await sio.wait()

if __name__ == '__main__':
    asyncio.run(main())
