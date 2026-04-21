"""
Content sanitization for CoDRAG context output and LLM input.

EA-B5:  Sanitize content rendered inside markdown code fences to prevent
        prompt injection via triple-backtick breakout.
EA-B10: Strip invisible Unicode characters that can carry hidden instructions
        (zero-width joiners, bidirectional markers, etc.).

These functions are called from index.py, layered_index.py, and the
LLM pipeline stages to protect against:
  - OWASP LLM01: Prompt Injection
  - OWASP LLM02: Sensitive Information Disclosure
  - "Rules File Backdoor" attacks (Pillar Security, Mar 2025)
"""

from __future__ import annotations

import fnmatch as _fnmatch
import re
import logging
import unicodedata
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── EA-B5: Code fence sanitization ────────────────────────────

# Pattern to match triple backticks (possibly with language specifier)
_TRIPLE_BACKTICK_RE = re.compile(r"(`{3,})")


def sanitize_code_fence_content(content: str) -> str:
    """Escape triple backticks inside content to prevent markdown code fence breakout.

    When CoDRAG assembles context, document content is wrapped in triple-backtick
    fences. If the content itself contains triple backticks, an attacker could
    break out of the fence and inject arbitrary markdown/instructions.

    This replaces runs of 3+ backticks with the same number of single-quote
    characters (U+2018 LEFT SINGLE QUOTATION MARK), which are visually similar
    but cannot form a markdown code fence boundary.
    """
    if "```" not in content:
        return content
    return _TRIPLE_BACKTICK_RE.sub(_escape_backtick_run, content)


def _escape_backtick_run(match: re.Match) -> str:
    """Replace a run of 3+ backticks with visually similar non-fence characters."""
    run = match.group(1)
    # Replace with: 2 real backticks + the rest as LEFT SINGLE QUOTATION MARK
    # This preserves visual appearance but can never form a fence boundary
    return "``" + "\u2018" * (len(run) - 2)


# ── EA-B10: Invisible Unicode stripping ───────────────────────

# Unicode categories that should not appear in source code or config files.
# These are used in "Rules File Backdoor" attacks to hide instructions.
_INVISIBLE_CHARS = (
    "\u200b"  # Zero-width space
    "\u200c"  # Zero-width non-joiner
    "\u200d"  # Zero-width joiner
    "\u200e"  # Left-to-right mark
    "\u200f"  # Right-to-left mark
    "\u2060"  # Word joiner
    "\u2061"  # Function application
    "\u2062"  # Invisible times
    "\u2063"  # Invisible separator
    "\u2064"  # Invisible plus
    "\u2066"  # Left-to-right isolate
    "\u2067"  # Right-to-left isolate
    "\u2068"  # First strong isolate
    "\u2069"  # Pop directional isolate
    "\u206a"  # Inhibit symmetric swapping
    "\u206b"  # Activate symmetric swapping
    "\u206c"  # Inhibit Arabic form shaping
    "\u206d"  # Activate Arabic form shaping
    "\u206e"  # National digit shapes
    "\u206f"  # Nominal digit shapes
    "\ufeff"  # Zero-width no-break space (BOM)
    "\ufff9"  # Interlinear annotation anchor
    "\ufffa"  # Interlinear annotation separator
    "\ufffb"  # Interlinear annotation terminator
)

_INVISIBLE_RE = re.compile("[" + re.escape(_INVISIBLE_CHARS) + "]")


def strip_invisible_unicode(text: str) -> str:
    """Remove invisible Unicode characters that could carry hidden instructions.

    Returns the cleaned text. These characters are used in "Rules File Backdoor"
    attacks where AI reads hidden instructions that human reviewers can't see.
    Also strips Plane 14 tag characters (U+E0000 to U+E007F) used for hidden text.
    """
    text = _INVISIBLE_RE.sub("", text)
    # Strip Plane 14 language tag characters (U+E0000 - U+E007F)
    return re.sub(r'[\U000e0000-\U000e007f]', '', text)


def detect_invisible_unicode(text: str) -> bool:
    """Check if text contains invisible Unicode characters.

    Returns True if any invisible characters are found. Use this for
    security health checks and config file validation without modifying content.
    """
    if _INVISIBLE_RE.search(text):
        return True
    if re.search(r'[\U000e0000-\U000e007f]', text):
        return True
    return False


# ── NFKC normalization (Finding F: EchoLeak-style homoglyph attacks) ──

def normalize_nfkc(text: str) -> str:
    """Apply Unicode NFKC normalization to collapse homoglyphs.

    EchoLeak (CVE-2025-32711) demonstrated that attackers use character
    substitutions (e.g., fullwidth Latin, Cyrillic lookalikes) to bypass
    naive string-matching filters. NFKC normalization maps these to their
    canonical ASCII equivalents.

    This is a CORE protection — zero quality impact on legitimate source code.
    """
    return unicodedata.normalize("NFKC", text)


# ── Well-known secret patterns (from LLM Guard / Presidio research) ──

BUILTIN_SECRET_PATTERNS: List[re.Pattern] = [
    re.compile(r"AKIA[0-9A-Z]{16}"),                                        # AWS Access Key
    re.compile(r"(?:aws_secret_access_key|aws_secret)\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}"),  # AWS Secret
    re.compile(r"gh[ps]_[A-Za-z0-9_]{36,}"),                                # GitHub Token
    re.compile(r"gho_[A-Za-z0-9_]{36,}"),                                   # GitHub OAuth
    re.compile(r"xox[bporas]-[0-9A-Za-z\-]{10,}"),                          # Slack Token
    re.compile(r"sk-[A-Za-z0-9]{20,}"),                                     # OpenAI API Key
    re.compile(r"sk-ant-[A-Za-z0-9\-]{20,}"),                               # Anthropic API Key
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),                                  # Google API Key
    re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),   # Private Key Header
    re.compile(r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_.+/=]+"),  # JWT Token
    re.compile(r"(?i)(?:api[_\-]?key|secret[_\-]?key|password|token|credential)[^=\n\r]{0,20}[:=]\s*['\"][^\s'\"]{8,}['\"]"),  # Generic secrets
]


def detect_secrets(content: str) -> List[str]:
    """Scan content for well-known secret patterns.

    Returns a list of matched pattern descriptions. Does NOT modify content.
    Used for security health checks and IT visibility (Check 14).
    """
    found = []
    for pattern in BUILTIN_SECRET_PATTERNS:
        if pattern.search(content):
            found.append(pattern.pattern[:60])
    return found


def sanitize_llm_input(content: str, source_path: Optional[str] = None) -> str:
    """Sanitize content before sending to an LLM for enrichment.

    CORE protection (all tiers, always-on):
    1. Strip invisible Unicode (Rules File Backdoor defense)
    2. NFKC normalize (EchoLeak homoglyph defense)

    This is the primary defense against prompt injection via repository content.
    Zero quality impact — these characters should never be in legitimate source code.
    """
    if not content:
        return content

    # Step 1: Strip invisible Unicode
    cleaned = strip_invisible_unicode(content)
    if len(cleaned) != len(content):
        chars_removed = len(content) - len(cleaned)
        logger.warning(
            "SECURITY: Stripped %d invisible Unicode characters from %s before LLM call. "
            "This may indicate a prompt injection attempt.",
            chars_removed,
            source_path or "content",
        )
        try:
            from prep.core.audit_log import get_audit_log
            get_audit_log().record(
                event_type="unicode_injection_detected",
                severity="warning",
                message=f"Stripped {chars_removed} invisible Unicode chars from {source_path or 'content'}",
                metadata={"chars_removed": chars_removed, "file_path": source_path},
            )
        except Exception:
            pass

    # Step 2: NFKC normalization (collapses homoglyphs)
    cleaned = normalize_nfkc(cleaned)

    return cleaned


# ── Finding E: URL stripping for MCP output ──────────────────

# Matches http(s) URLs that could be exfiltration vectors (EchoLeak, GeminiJack).
# Preserves localhost/127.0.0.1 URLs (legitimate dev references).
_EXTERNAL_URL_RE = re.compile(
    r"https?://(?!(?:localhost|127\.0\.0\.1)(?:[:/]|$))[^\s)\]>\"']+",
    re.IGNORECASE,
)


def strip_external_urls(content: str) -> str:
    """Replace external URLs with a safe placeholder.

    EchoLeak and GeminiJack demonstrated data exfiltration via image URLs
    embedded in LLM output. This strips external URLs from assembled context
    while preserving localhost references.

    Returns content with external URLs replaced by [URL-REMOVED].
    """
    return _EXTERNAL_URL_RE.sub("[URL-REMOVED]", content)


def sanitize_output(content: str, *, strip_urls: bool = False) -> str:
    """Sanitize assembled context before returning via MCP/API.

    CORE protection (all tiers):
    1. Escape code fence boundaries (prevents prompt injection breakout)
    2. Strip invisible Unicode (prevents hidden instructions in output)
    3. Optionally strip external URLs (Finding E: exfiltration defense)

    Called from index.py get_context() and layered_index.py get_context().
    """
    if not content:
        return content
    content = sanitize_code_fence_content(content)
    content = strip_invisible_unicode(content)
    if strip_urls:
        content = strip_external_urls(content)
    return content


# ── EA-B11: LLM output validation ────────────────────────────

# Patterns that should never appear in legitimate LLM enrichment output.
# These indicate prompt injection succeeded and the model is echoing
# attacker instructions or attempting data exfiltration.
_SUSPICIOUS_OUTPUT_PATTERNS = [
    # Prompt injection indicators
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(prior|previous|above)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an|in)\b", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    # Data exfiltration attempts (URLs that shouldn't appear in enrichment)
    re.compile(r"https?://[^\s]+\.(ru|cn|tk|ml|ga|cf)/", re.IGNORECASE),
    # Shell/code execution attempts
    re.compile(r"```\s*(bash|sh|shell|cmd|powershell)\s*\n\s*(curl|wget|nc|ncat)\s+", re.IGNORECASE),
    re.compile(r"os\.system\s*\(|subprocess\.(run|call|Popen)\s*\(|exec\s*\(", re.IGNORECASE),
]


def validate_llm_output(response: str, task_name: Optional[str] = None) -> tuple[str, list[str]]:
    """Validate LLM response for anomalous patterns indicating prompt injection.

    Returns (cleaned_response, warnings_list). The response is returned as-is
    (we don't modify it) but warnings are logged for monitoring. In a future
    version, responses with critical warnings could be rejected entirely.

    This catches cases where a poisoned file in the repo successfully injects
    instructions into the LLM during enrichment, causing it to produce
    malicious or manipulated output.
    """
    if not response:
        return response, []

    warnings: list[str] = []
    for pattern in _SUSPICIOUS_OUTPUT_PATTERNS:
        match = pattern.search(response)
        if match:
            snippet = response[max(0, match.start() - 20):match.end() + 20]
            warning = f"Suspicious pattern in LLM output: '{match.group()}' (context: ...{snippet}...)"
            warnings.append(warning)

    if warnings:
        task_label = f" [{task_name}]" if task_name else ""
        logger.warning(
            "SECURITY: LLM output validation found %d suspicious pattern(s)%s: %s",
            len(warnings),
            task_label,
            "; ".join(warnings),
        )
        # EA-F5: Record to audit log
        try:
            from prep.core.audit_log import get_audit_log
            get_audit_log().record(
                "suspicious_llm_output",
                f"LLM output validation found {len(warnings)} suspicious pattern(s){task_label}",
                pattern_count=len(warnings),
                task=task_name,
            )
        except Exception:
            pass

    return response, warnings


# ── EA-F1/F3/F4: DLP enforcement ─────────────────────────────

def is_file_blocked_by_dlp(
    file_path: str,
    never_send_globs: Optional[list] = None,
) -> bool:
    """Check if a file should be excluded from ALL LLM API calls.

    Returns True if the file matches any pattern in never_send_globs.
    Uses PurePath.match() for ** glob support, with fnmatch fallback.
    Case-insensitive to prevent bypasses like 'SeCrEt.txt' evading '*secret*'.
    """
    if not never_send_globs or not file_path:
        return False
    from pathlib import PurePath
    
    # Lowercase for case-insensitive matching
    p_lower = PurePath(file_path.lower())
    path_lower = file_path.lower()
    
    for pattern in never_send_globs:
        pat_lower = pattern.lower()
        try:
            if p_lower.match(pat_lower):
                logger.info("DLP: File '%s' blocked by never_send_glob '%s'", file_path, pattern)
                return True
        except (ValueError, TypeError):
            # Fallback to fnmatch for simple patterns
            if _fnmatch.fnmatch(path_lower, pat_lower):
                logger.info("DLP: File '%s' blocked by never_send_glob '%s'", file_path, pattern)
                return True
    return False


def is_provider_approved_for_data(
    provider: str,
    allowed_destinations: Optional[list] = None,
) -> bool:
    """Check if a provider is approved to receive source code.

    Returns True if:
    - No allowed_destinations configured (no restriction)
    - Provider is in the allowed list
    - Provider is a local provider (ollama, lm-studio) — local never leaves the machine
    """
    if not allowed_destinations:
        return True  # No restriction
    LOCAL = {"ollama", "lm-studio"}
    if provider in LOCAL:
        return True  # Local providers never send data externally
    return provider in allowed_destinations


def check_dlp_before_llm_call(
    provider: str,
    file_paths: Optional[list] = None,
    *,
    never_send_globs: Optional[list] = None,
    allowed_destinations: Optional[list] = None,
    block_unapproved_cloud: bool = False,
) -> tuple[bool, str]:
    """Pre-flight DLP check before sending code to an LLM.

    Returns (allowed, reason). If allowed is False, the LLM call should
    be skipped and the reason logged.

    Args:
        provider: The LLM provider name
        file_paths: List of file paths being sent in this call
        never_send_globs: Glob patterns for files that should never be sent
        allowed_destinations: List of approved provider names for data
        block_unapproved_cloud: If True, block calls to unapproved cloud providers
    """
    # Check provider approval
    if block_unapproved_cloud and not is_provider_approved_for_data(provider, allowed_destinations):
        reason = (
            f"DLP BLOCKED: Provider '{provider}' is not in the approved data destinations "
            f"({allowed_destinations}). Source code will not be sent."
        )
        logger.warning(reason)
        try:
            from prep.core.audit_log import audit_log
            audit_log.record(
                "dlp_provider_blocked",
                reason,
                provider=provider,
                allowed_destinations=allowed_destinations,
            )
        except Exception:
            pass
        return False, reason

    # Check individual files
    if file_paths and never_send_globs:
        blocked_files = [f for f in file_paths if is_file_blocked_by_dlp(f, never_send_globs)]
        if blocked_files:
            reason = (
                f"DLP: {len(blocked_files)} file(s) blocked by never_send_globs: "
                f"{', '.join(blocked_files[:5])}"
                f"{'...' if len(blocked_files) > 5 else ''}"
            )
            logger.info(reason)
            # Don't block the entire call — just note which files were excluded
            # The caller should filter these files out before sending

    return True, ""


def redact_secrets_in_content(content: str, redact_patterns: Optional[list] = None) -> str:
    """Strip inline secrets from content before sending to an LLM.

    Applies regex patterns from the admin data_policy.redact_patterns config.
    Each pattern should match secret-like content (API keys, passwords, tokens).
    Matched content is replaced with [REDACTED].

    Returns the redacted content string.
    """
    if not redact_patterns or not content:
        return content

    redacted = content
    total_redactions = 0
    for pattern_str in redact_patterns:
        try:
            pattern = re.compile(pattern_str)
            new_content, count = pattern.subn("[REDACTED]", redacted)
            if count > 0:
                total_redactions += count
                redacted = new_content
        except re.error as e:
            logger.warning("DLP: Invalid redact_pattern '%s': %s", pattern_str, e)

    if total_redactions > 0:
        logger.info("DLP: Redacted %d secret(s) from content before LLM call", total_redactions)

    return redacted
