from prep.services.pipeline.scheduler import pipeline_scheduler
from prep.services.token_telemetry import set_telemetry_context
from prep.core.batch_profiles import get_batch_concurrency

pipeline_scheduler.configure_node("cloud:ep1", 3)
pipeline_scheduler.set_priority("test_project_1", "exclusive")

pipeline_scheduler.acquire("test_project_1", "catalogue", "cloud:ep1")

with set_telemetry_context("test_project_1", "catalogue"):
    w = get_batch_concurrency("openai", node_id="cloud:ep1")
    print("Project 1 exclusive workers on node:", w)
    
    w_auto = get_batch_concurrency("openai", model="gpt-4o")
    print("Project 1 auto-discover workers:", w_auto)

with set_telemetry_context("other", "catalogue"):
    w2 = get_batch_concurrency("openai", node_id="cloud:ep1")
    print("Other project workers on node:", w2)
