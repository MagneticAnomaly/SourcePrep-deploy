import re

with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/services/pipeline/orchestrator.py", "r") as f:
    text = f.read()

# We need to add the release_slot logic when a stage finishes.
# Find where the stage completes in _on_build_transition
old_code = """        if new_phase == BuildPhase.FAILED:
            # Stage failed — transition to FAILED
            if matching_run.can_transition(Event.FAIL):
                matching_run.transition(Event.FAIL, detail=f"Stage {stage.value} failed")
                # Clean up checkpoint on failure
                self._cleanup_checkpoint(matching_run)
            logger.error("Pipeline %s/%s FAILED at stage %s", matching_run.project_id, matching_run.group, stage.value)
            if pfl:
                pfl.log(stage.value, "Stage FAILED", is_error=True)
                pfl.end_run("failed")
        else:
            # Stage completed successfully — Phase 25: save checkpoint
            self._save_checkpoint(matching_run)
            # Advance to next stage
            matching_run.current_stage_index += 1
            if matching_run.can_transition(Event.STAGE_COMPLETED):
                matching_run.transition(Event.STAGE_COMPLETED)
            
            logger.info(
                "Pipeline %s/%s — stage %s COMPLETED",
                matching_run.project_id, matching_run.group, stage.value,
            )
            if pfl:
                pfl.log(stage.value, "Stage COMPLETED")
            
            self._advance_pipeline(matching_run)"""

new_code = """        # Phase 45D: Release compute slot if it was an LLM stage
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

        if new_phase == BuildPhase.FAILED:
            # Stage failed — transition to FAILED
            if matching_run.can_transition(Event.FAIL):
                matching_run.transition(Event.FAIL, detail=f"Stage {stage.value} failed")
                # Clean up checkpoint on failure
                self._cleanup_checkpoint(matching_run)
            logger.error("Pipeline %s/%s FAILED at stage %s", matching_run.project_id, matching_run.group, stage.value)
            if pfl:
                pfl.log(stage.value, "Stage FAILED", is_error=True)
                pfl.end_run("failed")
        else:
            # Stage completed successfully — Phase 25: save checkpoint
            self._save_checkpoint(matching_run)
            # Advance to next stage
            matching_run.current_stage_index += 1
            if matching_run.can_transition(Event.STAGE_COMPLETED):
                matching_run.transition(Event.STAGE_COMPLETED)
            
            logger.info(
                "Pipeline %s/%s — stage %s COMPLETED",
                matching_run.project_id, matching_run.group, stage.value,
            )
            if pfl:
                pfl.log(stage.value, "Stage COMPLETED")
            
            self._advance_pipeline(matching_run)"""

if old_code in text:
    text = text.replace(old_code, new_code)
    with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/services/pipeline/orchestrator.py", "w") as f:
        f.write(text)
    print("Patched orchestrator release slot successfully.")
else:
    print("Old code not found for release slot patching!")
