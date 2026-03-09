import os

path = "src/codrag/api/routers/llm.py"
with open(path, 'r') as f:
    content = f.read()

# Make sure proxy_models returns ModelInfo structs
content = content.replace("models: List[Any] = []", "models: List[Dict[str, Any]] = []")

ollama_block_old = """
        if req.provider == "ollama":
            r = requests.get(f"{url}/api/tags", timeout=5)
            if r.status_code == 200:
                data = r.json()
                for m in data.get("models", []):
                    if isinstance(m, dict) and "name" in m:
                        models.append(m["name"])
"""
ollama_block_new = """
        if req.provider == "ollama":
            r = requests.get(f"{url}/api/tags", timeout=5)
            if r.status_code == 200:
                data = r.json()
                for m in data.get("models", []):
                    if isinstance(m, dict) and "name" in m:
                        models.append({
                            "id": m["name"],
                            "name": m["name"],
                        })
"""
content = content.replace(ollama_block_old, ollama_block_new)

openai_block_old = """
        elif req.provider in ("openai", "openai-compatible", "lm-studio", "anthropic"):
            headers = {}
            if req.api_key:
                headers["Authorization"] = f"Bearer {req.api_key}"
            
            target = f"{url}/models"
            if "v1" not in url and req.provider != "anthropic":
                 target = f"{url}/v1/models"
            
            r = requests.get(target, headers=headers, timeout=5)
            if r.status_code == 200:
                data = r.json()
                for m in data.get("data", []):
                    if isinstance(m, dict) and "id" in m:
                        models.append(m["id"])
"""
openai_block_new = """
        elif req.provider in ("openai", "openai-compatible", "lm-studio", "anthropic"):
            headers = {}
            if req.api_key:
                headers["Authorization"] = f"Bearer {req.api_key}"
            
            target = f"{url}/models"
            if "v1" not in url and req.provider != "anthropic":
                 target = f"{url}/v1/models"
            
            r = requests.get(target, headers=headers, timeout=5)
            if r.status_code == 200:
                data = r.json()
                for m in data.get("data", []):
                    if isinstance(m, dict) and "id" in m:
                        models.append({
                            "id": m["id"],
                            "name": m["id"],
                            "context_length": m.get("context_length") # LM studio sometimes provides this
                        })
"""
content = content.replace(openai_block_old, openai_block_new)

google_block_old = """
        elif req.provider == "google":
            params = {"key": req.api_key} if req.api_key else {}
            target = f"{url}/v1beta/models"
            r = requests.get(target, params=params, timeout=5)
            if r.status_code == 200:
                data = r.json()
                for m in data.get("models", []):
                    if isinstance(m, dict) and "name" in m:
                        # Gemini returns names like 'models/gemini-pro', so we can strip the 'models/' prefix or keep it
                        name = m["name"].replace("models/", "") if m["name"].startswith("models/") else m["name"]
                        models.append(name)
"""
google_block_new = """
        elif req.provider == "google":
            params = {"key": req.api_key} if req.api_key else {}
            target = f"{url}/v1beta/models"
            r = requests.get(target, params=params, timeout=5)
            if r.status_code == 200:
                data = r.json()
                for m in data.get("models", []):
                    if isinstance(m, dict) and "name" in m:
                        name = m["name"].replace("models/", "") if m["name"].startswith("models/") else m["name"]
                        models.append({
                            "id": name,
                            "name": m.get("displayName", name),
                            "context_length": m.get("inputTokenLimit")
                        })
"""
content = content.replace(google_block_old, google_block_new)

with open(path, 'w') as f:
    f.write(content)
print("Updated routers")
