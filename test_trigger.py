import urllib.request, json
def trigger(pid, ptype, prompt):
    url = "http://127.0.0.1:8000/generate"
    data = {"project_id": pid, "project_type": ptype, "prompt": prompt}
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req)
trigger("php-test-2", "vanilla", "buat login php")
trigger("react-test-2", "vite-react", "buat todo react")
