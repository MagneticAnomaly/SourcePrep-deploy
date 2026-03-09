import re

with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/services/pipeline/orchestrator.py", "r") as f:
    text = f.read()

# We need to add the release_slot logic when a stage finishes in _on_build_transition
old_code = """                # Phase 45D: release scheduler slot and resume any queued pipeline
                next_entry = pipeline_scheduler.release(project_id, stage)
                if next_entry:
                    self._resume_queued_pipeline(next_entry.project_id, next_entry.stage)"""

new_code = """                # Phase 45D: release scheduler slot and resume any queued pipeline
                queue_type = STAGE_QUEUE_TYPE.get(stage, QueueType.LLM)
                if queue_type == QueueType.LLM:
                    try:
                        from codrag.core.scheduler import get_coordinator
                        coordinator = get_coordinator()
                        # For now, default to local node
                        node_id = "node_local"
                        coordinator.release_slot(node_id)
                    except Exception as e:
                        logger.warning(f"Failed to release compute slot: {e}")"""

if old_code in text:
    text = text.replace(old_code, new_code)
    with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/services/pipeline/orchestrator.py", "w") as f:
        f.write(text)
    print("Patched orchestrator release slot successfully.")
else:
    print("Old code not found for release slot patching!")
