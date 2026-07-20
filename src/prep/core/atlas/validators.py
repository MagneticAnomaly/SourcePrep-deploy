"""
Atlas LLM output validators.

Runs after `_postprocess` and before persistence. Catches three failure
modes observed in dogfood (item #4 of the 2026-05-05 epistemic-audit pass):

1. Prompt-restatement leak — the model echoes its own instructions in
   first-person planning prose ("I need to write...", "Let me parse...")
   instead of producing the requested labeled sections.
2. Repeating-token loop — sampler gets stuck and emits the same single
   character or short n-gram for hundreds of tokens (observed: a
   1500-char run of "加油").
3. Missing required section markers — output has neither IDENTITY:,
   STACK:, SEGMENT:, ROLE:, nor any other expected label, indicating
   the model didn't follow the structural prompt.

Existing length gate (`len < MIN_ATLAS_CHARS // 2`) caught only empty
output; the failures above all produce long-but-garbage content.
"""
from __future__ import annotations

# First-person prompt-restatement openers. Lowercased, matched on the first
# non-empty line stripped of whitespace.
_PROMPT_LEAK_OPENERS: tuple[str, ...] = (
    "i need to",
    "i'll write",
    "i will write",
    "i must write",
    "i'm going to",
    "let me parse",
    "let me write",
    "let me analyze",
    "let me start",
    "let me begin",
    "let me think",
    "okay, let me",
    "ok, let me",
    "alright, let me",
    "first, let me",
    "first, i",
    "sure, here",
    "here is the",
    "here's the",
    "here is my",
    "here's my",
)

# Section labels the prompts (prompts.py) require. Detection is case-insensitive
# and substring-based — any one is enough to consider the output structured.
_REQUIRED_SECTION_MARKERS: tuple[str, ...] = (
    "IDENTITY:",
    "STACK:",
    "ARCHITECTURE:",
    "FLOW:",
    "CROSS-CUTTING:",
    "WORKSPACE MAP:",
    "SEGMENT:",
    "ROLE:",
    "KEY FILES:",
    "INTERNAL FLOW:",
    "DEPENDENCIES:",
    "STATUS:",
    "MODULES (",
    "KEY DOMAINS:",
)

# A single non-whitespace character repeated more than this many times in a row
# is treated as a sampler loop. 30 is well above any natural occurrence
# (e.g. "===" dividers, repeated punctuation in code) but well below the
# observed loops (1500+).
_MAX_REPEAT_RUN = 30

# Same for short n-gram repeats (e.g. "加油加油加油..."). 8 consecutive
# repeats of a 2-4 char unit indicates a loop. Natural prose rarely repeats
# any short unit more than 3-4 times.
_MAX_NGRAM_REPEAT = 8


def detect_repeat_attack(text: str) -> str | None:
    """Detect single-char or short n-gram repetition loops.

    Returns a short reason string if a loop is detected, else None.
    """
    if not text:
        return None

    # Single-char run
    run_char = text[0]
    run_len = 1
    for ch in text[1:]:
        if ch == run_char:
            run_len += 1
            if run_len > _MAX_REPEAT_RUN and not run_char.isspace():
                return f"single-char repeat run: {run_char!r} x {run_len}"
        else:
            run_char = ch
            run_len = 1

    # Short n-gram repeat (2-4 chars). For each starting position, see if the
    # next n chars repeat consecutively. Skip n-grams that are pure whitespace
    # or that consist of a single repeated character (those are governed by
    # the single-char run check above so we don't double-flag "===" or "  ").
    for n in (2, 3, 4):
        if len(text) < n * _MAX_NGRAM_REPEAT:
            continue
        i = 0
        limit = len(text) - n * _MAX_NGRAM_REPEAT
        while i <= limit:
            ngram = text[i : i + n]
            if ngram.isspace() or len(set(ngram)) == 1:
                i += 1
                continue
            count = 1
            j = i + n
            while j + n <= len(text) and text[j : j + n] == ngram:
                count += 1
                j += n
                if count > _MAX_NGRAM_REPEAT:
                    return f"{n}-char ngram repeat: {ngram!r} x {count}"
            # Skip past the run we just measured to avoid quadratic re-checking
            i = max(i + 1, i + count * n)
    return None


def detect_prompt_leak(text: str) -> str | None:
    """Detect first-person prompt-restatement openings.

    If the first non-empty line starts with an expected section marker we
    consider the output OK regardless of any later prose. Otherwise, if it
    starts with a known first-person planning phrase, reject.
    """
    if not text:
        return None
    stripped = text.lstrip()
    if not stripped:
        return None
    first_line = stripped.split("\n", 1)[0].strip()
    if not first_line:
        return None
    upper = first_line.upper()
    for marker in _REQUIRED_SECTION_MARKERS:
        if upper.startswith(marker):
            return None
    lower = first_line.lower()
    for opener in _PROMPT_LEAK_OPENERS:
        if lower.startswith(opener):
            return f"prompt-leak opener: {first_line[:60]!r}"
    return None


def detect_missing_sections(text: str) -> str | None:
    """Reject output that contains none of the expected section markers."""
    if not text:
        return None
    upper = text.upper()
    if any(marker in upper for marker in _REQUIRED_SECTION_MARKERS):
        return None
    return "no expected section markers found (e.g. IDENTITY:, STACK:, SEGMENT:, MODULES)"


def validate_atlas_content(text: str) -> str | None:
    """Run all atlas-content validators. Returns rejection reason or None.

    Order matters: prompt-leak is checked first because it's the most
    specific signal of model misbehavior; repeat-attack second because it
    can ride alongside otherwise-OK structure; missing-sections last as the
    weakest signal.
    """
    for fn in (detect_prompt_leak, detect_repeat_attack, detect_missing_sections):
        reason = fn(text)
        if reason is not None:
            return reason
    return None
