with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/services/pipeline/orchestrator.py", "r") as f:
    text = f.read()

# Replace the single line check with the MultiProjectCoordinator logic
old_code = """        # Phase 45D: Check scheduler capacity before starting the stage.
        # If the compute node is full, park the pipeline in QUEUED state.
        if not pipeline_scheduler.can_start(run.project_id, stage):
            pipeline_scheduler.enqueue(run.project_id, stage)
            if run.can_transition(Event.ENQUEUE):
                run.transition(Event.ENQUEUE, detail=f"waiting for compute slot ({stage.value})")
            logger.info(
                "Pipeline %s/%s — stage %s queued (compute node full)",
                run.project_id, run.group, stage.value,
            )
            if pfl:
                pfl.log(stage.value, "Queued — waiting for compute capacity")
            return

        # Acquire a scheduler slot for this stage
        pipeline_scheduler.acquire(run.project_id, stage)"""

new_code = """        # Phase 45D: Check MultiProjectCoordinator capacity before starting the stage.
        # If the compute node is full, park the pipeline in QUEUED state.
        try:
            from codrag.core.scheduler import get_coordinator
            coordinator = get_coordinator()
            # For now, default to local node. Future: read from stage requirements
            node_id = "node_local"
            
            # Queue type check to only enforce slot requests on LLM stages
            if queue_type == QueueType.LLM:
                if not coordinator.request_slot(run.project_id, stage.value, node_id):
                    if run.can_transition(Event.ENQUEUE):
                        run.transition(Event.ENQUEUE, detail=f"waiting for compute slot ({stage.value})")
                    logger.info(
                        "Pipeline %s/%s — stage %s queued (compute node full)",
                        run.project_id, run.group, stage.value,
                    )
                    if pfl:
                        pfl.log(stage.value, "Queued — waiting for compute capacity")
                    return
        except Exception as e:
            logger.warning(f"Failed to request compute slot, bypassing coordinator: {e}")
            pass

        # Capacity available -> acquire slot and transition to RUNNING"""

if old_code in text:
    text = text.replace(old_code, new_code)
    with open("/Volumes/4TB-BAD/HumanAI/CoDRAG/src/codrag/services/pipeline/orchestrator.py", "w") as f:
        f.write(text)
    print("Patched orchestrator successfully.")
else:
    print("Old code not found in orchestrator.py!")
