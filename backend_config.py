import re

with open('src/codrag/services/config_manager.py', 'r') as f:
    content = f.read()

# Make sure compute_nodes is initialized in default config
default_cfg_str = """
        "saved_endpoints": [
            {
                "id": "ep_ollama_local",
                "name": "Local Ollama",
                "provider": "ollama",
                "url": "http://127.0.0.1:11434"
            }
        ],
        "compute_nodes": [],
"""

content = re.sub(
    r'(\s*"saved_endpoints": \[\n\s*\{\n\s*"id": "ep_ollama_local",\n\s*"name": "Local Ollama",\n\s*"provider": "ollama",\n\s*"url": "http://127\.0\.0\.1:11434"\n\s*\}\n\s*\],)',
    default_cfg_str,
    content,
    count=1
)

with open('src/codrag/services/config_manager.py', 'w') as f:
    f.write(content)
