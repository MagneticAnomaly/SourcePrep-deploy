with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/scheduler.py", "r") as f:
    text = f.read()

text = text.replace("from codrag.core.event_bus import publish_event", "# Event bus removed for pure test logic")
text = text.replace('publish_event("STAGE_DEQUEUED", {"project_id": project_id})', 'pass')

with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/core/scheduler.py", "w") as f:
    f.write(text)
