import sys
sys.path.insert(0, "src")
from codrag.services.settings_store import settings
settings.init("/Users/ericbintner/.codrag.data/codrag_settings.db")
from codrag.server import _require_project
proj = _require_project("1d6f0b35-45cb-427b-ae9d-aac3c6371a4b")
print("roots:", proj.roots)
print("exclude_globs:", proj.exclude_globs)
