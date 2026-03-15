import re

with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/mcp/server.py", "r") as f:
    content = f.read()

# We need to change _resolve_project_id to resolve paths in override.
# Let's see how _resolve_project_id handles override.
