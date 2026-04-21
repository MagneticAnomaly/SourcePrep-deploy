"""
ModelAwareness — State machine for LLM model lifecycle management.

Tracks which models are loaded, active, persistent, or evicted across all
providers (Ollama, LM Studio, cloud APIs).  Replaces the ad-hoc VRAM
lifecycle helpers in the pipeline orchestrator.

Phase 44C — see docs/Phase44_LLM-Mapping/MODEL_AWARENESS_STATE_MACHINE.md
"""
from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ── Provider classification ───────────────────────────────────────

CLOUD_PROVIDERS: Set[str] = {"openai", "anthropic", "google", "openai-compatible"}
LOCAL_PROVIDERS: Set[str] = {"ollama", "lm-studio"}

# LM Studio defaults to 4096 context which is too small for most Prep tasks.
# Unlike Ollama (where num_ctx is set per-request), LM Studio sets context_length
# at model load time only.  16384 covers all pipeline tasks comfortably.
_LMSTUDIO_DEFAULT_CONTEXT_LENGTH = 16384


def is_cloud_provider(provider: str) -> bool:
    return provider in CLOUD_PROVIDERS


def is_manageable_provider(provider: str) -> bool:
    """Can we programmatically load/unload models for this provider?"""
    return provider in ("ollama", "lm-studio")


# ── State Enum ────────────────────────────────────────────────────────

class ModelState(enum.Enum):
    IDLE = "idle"              # Not loaded, not needed
    LOADING = "loading"        # Preload in progress (Ollama / LM Studio)
    READY = "ready"            # Loaded in VRAM, available for inference
    ACTIVE = "active"          # Currently processing a pipeline stage
    UNLOADING = "unloading"    # Being unloaded from VRAM
    EVICTED = "evicted"        # Was persistent, force-removed for VRAM pressure
    CLOUD = "cloud"            # Cloud endpoint — always "ready"


# ── Model Slot ────────────────────────────────────────────────────

ModelIdentity = Tuple[str, str]  # (endpoint_id, model_name)


@dataclass
class ModelSlot:
    """Tracks the state of a single model identity."""
    identity: ModelIdentity
    provider: str
    endpoint_url: str
    state: ModelState
    persistent: bool = False          # always_on flag
    task_id: Optional[str] = None     # current PrepTaskId if ACTIVE
    last_used: float = field(default_factory=time.monotonic)
    eviction_warning: bool = False    # True if was evicted (for UI indicator)
    api_key: Optional[str] = None

    @property
    def is_cloud(self) -> bool:
        return is_cloud_provider(self.provider)

    @property
    def is_manageable(self) -> bool:
        return is_manageable_provider(self.provider)

    @property
    def is_loaded(self) -> bool:
        return self.state in (ModelState.READY, ModelState.ACTIVE)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity": list(self.identity),
            "provider": self.provider,
            "state": self.state.value,
            "persistent": self.persistent,
            "task_id": self.task_id,
            "eviction_warning": self.eviction_warning,
            "is_cloud": self.is_cloud,
        }


# ── Event types for SSE / UI notifications ────────────────────────

class ModelEvent(enum.Enum):
    ACQUIRED = "model_acquired"
    RELEASED = "model_released"
    EVICTED = "model_evicted"
    RESTORED = "model_restored"
    LOAD_FAILED = "model_load_failed"
    MISMATCH_WARNING = "model_mismatch_warning"


@dataclass
class ModelAwarenessEvent:
    event_type: ModelEvent
    identity: ModelIdentity
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.event_type.value,
            "endpoint_id": self.identity[0],
            "model": self.identity[1],
            "detail": self.detail,
        }


# ── State Machine ─────────────────────────────────────────────────

class ModelAwareness:
    """Global singleton tracking all model states across all providers.

    Thread-safe.  All mutations go through the lock.

    Usage::

        slot = model_awareness.acquire("catalogue")
        # ... do LLM work ...
        model_awareness.release("catalogue")
    """

    def __init__(self) -> None:
        self._slots: Dict[ModelIdentity, ModelSlot] = {}
        self._lock = threading.Lock()
        self._listeners: List[Callable[[ModelAwarenessEvent], None]] = []

    # ── Listener API (for SSE / UI push) ──────────────────────────

    def add_listener(self, fn: Callable[[ModelAwarenessEvent], None]) -> None:
        self._listeners.append(fn)

    def _emit(self, event: ModelAwarenessEvent) -> None:
        for fn in self._listeners:
            try:
                fn(event)
            except Exception:
                logger.debug("ModelAwareness listener error", exc_info=True)

    # ── Core API ──────────────────────────────────────────────────

    def acquire(self, task_id: str) -> Optional[ModelSlot]:
        """Acquire a model for a pipeline task.

        Resolves task_id → model identity via the config, then ensures
        the model is loaded (or is a cloud model).  Returns the slot,
        or None if no model is configured for this task.

        This is the main entry point called by the pipeline orchestrator
        before each stage begins.
        """
        from prep.server import _get_model_identity_for_task

        identity = _get_model_identity_for_task(task_id)
        if identity is None:
            return None

        endpoint_id, model_name = identity
        provider, endpoint_url, api_key, persistent = self._resolve_endpoint_details(endpoint_id)

        if provider is None:
            logger.warning("acquire(%s): endpoint %s not found", task_id, endpoint_id)
            return None

        with self._lock:
            slot = self._slots.get(identity)

            # ── Cloud providers: always ready ──
            if is_cloud_provider(provider):
                if slot is None:
                    slot = ModelSlot(
                        identity=identity,
                        provider=provider,
                        endpoint_url=endpoint_url,
                        state=ModelState.CLOUD,
                        persistent=False,
                        api_key=api_key,
                    )
                    self._slots[identity] = slot
                slot.state = ModelState.CLOUD
                slot.task_id = task_id
                slot.last_used = time.monotonic()
                return slot

            # ── Already loaded? ──
            if slot and slot.is_loaded:
                slot.state = ModelState.ACTIVE
                slot.task_id = task_id
                slot.last_used = time.monotonic()
                self._emit(ModelAwarenessEvent(
                    ModelEvent.ACQUIRED, identity,
                    f"Already loaded, activated for {task_id}",
                ))
                return slot

            # ── Evicted slot being re-acquired ──
            if slot and slot.state == ModelState.EVICTED:
                slot.eviction_warning = False  # Clear on re-acquire

            # ── Need to load ──
            if slot is None:
                slot = ModelSlot(
                    identity=identity,
                    provider=provider,
                    endpoint_url=endpoint_url,
                    state=ModelState.IDLE,
                    persistent=persistent,
                    api_key=api_key,
                )
                self._slots[identity] = slot
            else:
                slot.persistent = persistent

        # Outside lock: do the actual loading (may be slow)
        loaded = self._load_model(slot, task_id)

        with self._lock:
            if loaded:
                slot.state = ModelState.ACTIVE
                slot.task_id = task_id
                slot.last_used = time.monotonic()
                self._emit(ModelAwarenessEvent(
                    ModelEvent.ACQUIRED, identity,
                    f"Loaded and activated for {task_id}",
                ))
                return slot
            else:
                slot.state = ModelState.IDLE
                self._emit(ModelAwarenessEvent(
                    ModelEvent.LOAD_FAILED, identity,
                    f"Failed to load for {task_id}",
                ))
                return None

    def release(self, task_id: str, unload: bool = True) -> None:
        """Release a model after a pipeline task completes.

        If unload=True and the model is not persistent, unloads it from VRAM.
        If the model is persistent, it stays READY.
        """
        from prep.server import _get_model_identity_for_task

        identity = _get_model_identity_for_task(task_id)
        if identity is None:
            return

        with self._lock:
            slot = self._slots.get(identity)
            if slot is None:
                return

            if slot.state == ModelState.CLOUD:
                slot.task_id = None
                return

            if slot.state != ModelState.ACTIVE:
                # Not active — nothing to release
                return

            slot.task_id = None
            slot.last_used = time.monotonic()

            if slot.persistent or not unload:
                slot.state = ModelState.READY
                self._emit(ModelAwarenessEvent(
                    ModelEvent.RELEASED, identity,
                    f"Released {task_id}, staying READY (persistent={slot.persistent})",
                ))
                # Check if any evicted models can be restored
                self._try_restore_evicted()
                return

            # Non-persistent: unload
            slot.state = ModelState.UNLOADING

        # Outside lock: do the actual unload
        self._unload_model(slot)

        with self._lock:
            slot.state = ModelState.IDLE
            self._emit(ModelAwarenessEvent(
                ModelEvent.RELEASED, identity,
                f"Released and unloaded {task_id}",
            ))
            # Check if any evicted models can be restored
            self._try_restore_evicted()

    def release_group(self, task_ids: List[str], unload: bool = True) -> None:
        """Release all models used by a set of tasks (e.g. a pipeline group).

        Deduplicates by identity so shared models are only released once.
        """
        from prep.server import _get_model_identity_for_task

        seen: Set[ModelIdentity] = set()
        for task_id in task_ids:
            identity = _get_model_identity_for_task(task_id)
            if identity and identity not in seen:
                seen.add(identity)
                self.release(task_id, unload=unload)

    def evict(self, identity: ModelIdentity) -> bool:
        """Force-evict a model from VRAM, even if persistent.

        Used when VRAM pressure requires freeing space for a higher-priority task.
        Sets the eviction_warning flag so the UI can show a warning indicator.

        Returns True if the model was successfully evicted.
        """
        with self._lock:
            slot = self._slots.get(identity)
            if slot is None or slot.state == ModelState.CLOUD:
                return False
            if slot.state == ModelState.ACTIVE:
                logger.warning("Cannot evict ACTIVE model %s", identity)
                return False
            if not slot.is_loaded:
                return True  # Already not loaded

            was_persistent = slot.persistent
            slot.state = ModelState.UNLOADING

        # Outside lock: unload
        self._unload_model(slot)

        with self._lock:
            slot.state = ModelState.EVICTED if was_persistent else ModelState.IDLE
            slot.eviction_warning = was_persistent
            if was_persistent:
                self._emit(ModelAwarenessEvent(
                    ModelEvent.EVICTED, identity,
                    "Evicted persistent model due to VRAM pressure",
                ))
            return True

    def ensure_room_for(self, identity: ModelIdentity) -> bool:
        """Ensure there's VRAM room for the given model identity.

        Eviction order:
        1. Non-persistent READY models (LRU first)
        2. Persistent READY models (LRU first)

        Returns True if room was made (or already available).
        Returns False if we couldn't free enough space (all models are ACTIVE).

        NOTE: Phase 2 will add actual VRAM size estimation.
        For Phase 1, we use a simple heuristic: only one local model
        loaded at a time (matching current behavior).
        """
        with self._lock:
            slot = self._slots.get(identity)
            if slot and slot.is_loaded:
                return True  # Already loaded

            # Collect loaded local models (excluding the target)
            loaded_local = [
                s for s in self._slots.values()
                if s.is_loaded and s.is_manageable and s.identity != identity
            ]

            if not loaded_local:
                return True  # Nothing to evict, room is available

            # Sort: non-persistent first, then by LRU
            candidates = sorted(
                loaded_local,
                key=lambda s: (s.persistent, s.last_used),
            )

        # Evict candidates until we have room (Phase 1: evict all others)
        for candidate in candidates:
            if candidate.state == ModelState.ACTIVE:
                continue  # Can't evict active models
            self.evict(candidate.identity)
            return True  # Phase 1: one eviction is enough

        # All loaded models are ACTIVE — can't make room
        logger.warning(
            "Cannot make room for %s — all loaded models are ACTIVE", identity
        )
        return False

    # ── Status API (for UI) ───────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Return current state of all tracked models."""
        with self._lock:
            return {
                "slots": {
                    f"{ident[0]}:{ident[1]}": slot.to_dict()
                    for ident, slot in self._slots.items()
                },
                "eviction_warnings": [
                    slot.to_dict()
                    for slot in self._slots.values()
                    if slot.eviction_warning
                ],
            }

    def get_slot(self, identity: ModelIdentity) -> Optional[ModelSlot]:
        with self._lock:
            return self._slots.get(identity)

    def clear(self) -> None:
        """Reset all state. Used in tests."""
        with self._lock:
            self._slots.clear()

    # ── Internal helpers ──────────────────────────────────────────

    def _resolve_endpoint_details(self, endpoint_id: str) -> Tuple[
        Optional[str], str, Optional[str], bool
    ]:
        """Resolve endpoint_id → (provider, url, api_key, persistent).

        Reads from the current UI config.
        """
        from prep.server import _load_ui_config

        ui_cfg = _load_ui_config()
        llm_cfg = ui_cfg.get("llm_config") or {}
        endpoints = llm_cfg.get("saved_endpoints") or []
        endpoint = next((ep for ep in endpoints if ep.get("id") == endpoint_id), None)

        if not endpoint:
            return None, "", None, False

        provider = endpoint.get("provider", "ollama")
        url = endpoint.get("url", "")
        api_key = endpoint.get("api_key")

        # Determine persistent flag from the task's assignment
        # (checked at acquire time, not here — but we need a default)
        persistent = False

        return provider, url, api_key, persistent

    def _load_model(self, slot: ModelSlot, task_id: str) -> bool:
        """Load a model into VRAM. Provider-specific."""
        if slot.is_cloud:
            return True

        if not slot.is_manageable:
            return True  # Unmanaged providers: assume ready

        # Ensure VRAM room (evict other models if needed)
        room_ok = self.ensure_room_for(slot.identity)
        if not room_ok:
            logger.error(
                "Cannot load %s for %s — no VRAM room available",
                slot.identity[1], task_id,
            )
            return False

        # Cloud models (Ollama :cloud suffix) run on remote GPUs — no local
        # VRAM to warm up.  Preloading wastes a cloud concurrency slot
        # (Free=1, Pro=3, Max=10) and causes 429 for the actual pipeline call.
        if slot.is_cloud:
            logger.debug(
                "Skipping preload for cloud model %s — no local VRAM to warm",
                slot.identity[1],
            )
            with self._lock:
                slot.state = ModelState.READY
            return True

        with self._lock:
            slot.state = ModelState.LOADING

        from prep.core.model_readiness import ModelStatus

        if slot.provider == "lm-studio":
            from prep.core.model_readiness import lmstudio_ensure_ready
            result = lmstudio_ensure_ready(
                slot.endpoint_url,
                slot.identity[1],
                timeout_s=300,
                context_length=_LMSTUDIO_DEFAULT_CONTEXT_LENGTH,
            )
        else:
            from prep.core.model_readiness import ollama_ensure_ready
            result = ollama_ensure_ready(
                slot.endpoint_url,
                slot.identity[1],
                timeout_s=300,
            )

        return result.status == ModelStatus.READY

    def _unload_model(self, slot: ModelSlot) -> bool:
        """Unload a model from VRAM. Provider-specific."""
        if slot.is_cloud or not slot.is_manageable:
            return True
        # Ollama cloud models (e.g. kimi-k2.5:cloud) run on remote GPUs —
        # no local VRAM to free.  Sending keep_alive=0 wastes a cloud slot.
        if ":cloud" in (slot.identity[1] or "").lower():
            return True

        if slot.provider == "lm-studio":
            from prep.core.model_readiness import lmstudio_unload
            return lmstudio_unload(slot.endpoint_url, slot.identity[1])

        # Ollama (default)
        try:
            import requests
            resp = requests.post(
                f"{slot.endpoint_url}/api/generate",
                json={
                    "model": slot.identity[1],
                    "prompt": "",
                    "keep_alive": 0,
                    "stream": False,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info("Unloaded model %s from VRAM", slot.identity[1])
                return True
            logger.warning(
                "Unload request for %s returned %d",
                slot.identity[1], resp.status_code,
            )
            return False
        except Exception as e:
            logger.warning("Failed to unload model %s: %s", slot.identity[1], e)
            return False

    def _try_restore_evicted(self) -> None:
        """Try to restore any evicted persistent models.

        Called after a model is released. Checks if there's room to
        reload evicted persistent models.
        """
        evicted = [
            s for s in self._slots.values()
            if s.state == ModelState.EVICTED and s.persistent
        ]
        if not evicted:
            return

        # Sort by last_used (most recently used first)
        evicted.sort(key=lambda s: s.last_used, reverse=True)

        for slot in evicted:
            # Cloud models don't need restore — nothing local to reload
            if slot.is_cloud:
                slot.state = ModelState.READY
                continue

            # Check if there's room (don't evict others to restore)
            loaded_local = [
                s for s in self._slots.values()
                if s.is_loaded and s.is_manageable
            ]
            # Phase 1: only one local model at a time
            if loaded_local:
                break  # No room

            # Restore outside the lock
            logger.info("Restoring evicted persistent model %s", slot.identity[1])
            slot.state = ModelState.LOADING

            from prep.core.model_readiness import ModelStatus
            if slot.provider == "lm-studio":
                from prep.core.model_readiness import lmstudio_ensure_ready
                result = lmstudio_ensure_ready(
                    slot.endpoint_url,
                    slot.identity[1],
                    timeout_s=120,
                    context_length=_LMSTUDIO_DEFAULT_CONTEXT_LENGTH,
                )
            else:
                from prep.core.model_readiness import ollama_ensure_ready
                result = ollama_ensure_ready(
                    slot.endpoint_url,
                    slot.identity[1],
                    timeout_s=120,
                )
            if result.status == ModelStatus.READY:
                slot.state = ModelState.READY
                slot.eviction_warning = False
                self._emit(ModelAwarenessEvent(
                    ModelEvent.RESTORED, slot.identity,
                    "Persistent model restored after VRAM pressure relieved",
                ))
            else:
                slot.state = ModelState.EVICTED
                logger.warning(
                    "Failed to restore evicted model %s", slot.identity[1]
                )


# ── Singleton ─────────────────────────────────────────────────────

model_awareness = ModelAwareness()
