with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/server.py", "r") as f:
    text = f.read()

# Make sure we load scheduler settings at startup
if "pipeline_scheduler.load_from_settings()" not in text:
    old = "from codrag.core.project_registry import project_registry\n    project_registry.init(project_dir)"
    new = "from codrag.core.project_registry import project_registry\n    project_registry.init(project_dir)\n\n    # Phase 45D: Initialize pipeline scheduler with compute node config\n    from codrag.services.pipeline.scheduler import pipeline_scheduler\n    pipeline_scheduler.load_from_settings()"
    text = text.replace(old, new)
    with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/server.py", "w") as f:
        f.write(text)
    print("Patched server.py to initialize scheduler")
