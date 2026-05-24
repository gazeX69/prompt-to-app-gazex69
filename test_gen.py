import urllib.request
import json
import urllib.error

url = "http://127.0.0.1:8000/generate"
data = {
    "project_id": "test-123",
    "prompt": "Make a simple hello world app",
    "project_type": "vite-react-tailwind"
}

req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as res:
        print(res.read().decode())
except urllib.error.HTTPError as e:
    print(f"HTTPError {e.code}: {e.read().decode()}")
except Exception as e:
    print(e)
