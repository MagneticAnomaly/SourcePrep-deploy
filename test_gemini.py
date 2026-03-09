import urllib.request
import ssl
import json
import os

api_key = os.environ.get("GEMINI_API_KEY", "dummy")

url = "https://generativelanguage.googleapis.com/v1beta/models?key=" + api_key
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, context=ctx) as response:
        data = json.loads(response.read().decode())
        for m in data.get("models", []):
            methods = m.get("supportedGenerationMethods", [])
            print(f"{m.get('name')} -> {methods}")
except Exception as e:
    pass
