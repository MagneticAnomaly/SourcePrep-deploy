"""Treatment registry for Phase 53: maps ContentClass to treatment parameters.

Each ContentClass gets a TreatmentConfig that controls how files of that class
are processed during augmentation: context window size, batch size, whether to
use strategic excerpt extraction, and which system prompt to use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .content_class import ContentClass


@dataclass(frozen=True)
class TreatmentConfig:
    """Immutable treatment parameters for a content class.

    Attributes:
        context_lines: Maximum lines of file content to send to the LLM.
        batch_size_divisor: Divide the profile's base batch size by this.
            1 = use full batch size, 5 = batch_size // 5, etc.
            Set to 0 to force batch_size=1 (no batching).
        use_strategic_excerpt: Whether to use section-ranked strategic excerpts
            (True for docs) vs simple file head (False for code/narrative).
        system_prompt_key: Key identifying which system prompt to use.
            Maps to constants in batch_prompts.py.
        max_excerpt_lines: For strategic excerpt, the max total lines to include.
    """

    context_lines: int
    batch_size_divisor: int
    use_strategic_excerpt: bool
    system_prompt_key: str
    max_excerpt_lines: Optional[int] = None


class TreatmentRegistry:
    """Maps ContentClass to TreatmentConfig.

    Usage::

        treatment = TreatmentRegistry.get_treatment(content_class)
        batch_size = profile_batch_size // treatment.batch_size_divisor
    """

    _TREATMENTS = {
        ContentClass.STRUCTURED_CODE: TreatmentConfig(
            context_lines=30,
            batch_size_divisor=1,
            use_strategic_excerpt=False,
            system_prompt_key="file",
        ),
        ContentClass.STRUCTURED_DOCS: TreatmentConfig(
            context_lines=200,
            batch_size_divisor=5,
            use_strategic_excerpt=True,
            system_prompt_key="doc",
            max_excerpt_lines=1000,
        ),
        ContentClass.UNSTRUCTURED_NARRATIVE: TreatmentConfig(
            context_lines=50,
            batch_size_divisor=0,   # force batch_size=1
            use_strategic_excerpt=False,
            system_prompt_key="narrative",
        ),
    }

    @classmethod
    def get_treatment(cls, content_class: ContentClass) -> TreatmentConfig:
        """Get the treatment config for a content class.

        Falls back to STRUCTURED_DOCS treatment for unknown classes.
        """
        return cls._TREATMENTS.get(
            content_class,
            cls._TREATMENTS[ContentClass.STRUCTURED_DOCS],
        )

    @classmethod
    def compute_batch_size(
        cls,
        content_class: ContentClass,
        profile_batch_size: int,
    ) -> int:
        """Compute the effective batch size for a content class.

        Args:
            content_class: The content class.
            profile_batch_size: The base batch size from the batch profile.

        Returns:
            Effective batch size (always >= 1).
        """
        treatment = cls.get_treatment(content_class)
        if treatment.batch_size_divisor == 0:
            return 1
        return max(1, profile_batch_size // treatment.batch_size_divisor)
