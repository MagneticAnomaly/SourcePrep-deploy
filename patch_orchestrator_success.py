import re

with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/services/pipeline/orchestrator.py", "r") as f:
    text = f.read()

# Make sure we release the slot on SUCCESS too, before advancing the pipeline
old_code = """        else:
            # Stage completed successfully — Phase 25: save checkpoint
            self._save_checkpoint(matching_run)
            # Advance to next stage
            matching_run.current_stage_index += 1
            if matching_run.can_transition(Event.STAGE_COMPLETED):
                matching_run.transition(Event.STAGE_COMPLETED)"""

new_code = """        else:
            # Phase 45D: release scheduler slot on success
            queue_type = STAGE_QUEUE_TYPE.get(stage, QueueType.LLM)
            if queue_type == QueueType.LLM:
                try:
                    from codrag.core.scheduler import get_coordinator
                    coordinator = get_coordinator()
                    # For now, default to local node
                    node_id = "node_local"
                    coordinator.release_slot(node_id)
                except Exception as e:
                    logger.warning(f"Failed to release compute slot: {e}")
                    
            # Stage completed successfully — Phase 25: save checkpoint
            self._save_checkpoint(matching_run)
            # Advance to next stage
            matching_run.current_stage_index += 1
            if matching_run.can_transition(Event.STAGE_COMPLETED):
                matching_run.transition(Event.STAGE_COMPLETED)"""

if old_code in text:
    text = text.replace(old_code, new_code)
    with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/services/pipeline/orchestrator.py", "w") as f:
        f.write(text)
    print("Patched orchestrator success release successfully.")
else:
    print("Old success release code not found!")
