"""LLM prompt templates for Digital Custodian safety verification."""
from __future__ import annotations
from typing import List

def render_safety_verification_prompt(
    file_path: str, file_contents: str, dependent_count: int,
    import_list: List[str], module_name: str, domain_tags: List[str],
) -> str:
    imports_str = ", ".join(import_list) if import_list else "(none)"
    tags_str = ", ".join(domain_tags) if domain_tags else "(none)"
    lines = file_contents.splitlines()[:200]
    truncated = "\n".join(lines)
    return f"""You are reviewing a code file to determine if it is truly dead (safe to delete).

File: {file_path}
File contents (first 200 lines):
```
{truncated}
```

CoDRAG analysis:
- Dependents (static imports): {dependent_count} (should be 0)
- This file imports: {imports_str}
- Module membership: {module_name}
- Domain tags: {tags_str}

Answer these questions:
1. Could this file be imported dynamically (importlib, __import__, exec)?
2. Could this file be referenced via string-based paths (config files, env vars)?
3. Is this file a public API entry point (exposed via __init__.py, __all__)?
4. Is this file part of a plugin system or extension mechanism?
5. Could this file be a CLI entry point, test fixture, or script?
6. Is there any reason a human might want to keep this file?

If ANY answer is "yes" or "uncertain", classify as NEEDS_REVIEW.
If ALL answers are "no", classify as SAFE_TO_DELETE.
Never default to SAFE_TO_DELETE if uncertain.

Return JSON: {{"classification": "SAFE_TO_DELETE" | "NEEDS_REVIEW" | "KEEP", "reason": "..."}}"""

SAFETY_VERIFICATION_SYSTEM = """You are a conservative code safety reviewer.
You output ONLY valid JSON with "classification" and "reason" fields.
When in doubt, classify as NEEDS_REVIEW — false positives are acceptable, false negatives are not."""

def render_archive_readme(
    original_paths: List[str], reason: str, finding_id: str, archived_at: str,
) -> str:
    files_list = "\n".join(f"- `{p}`" for p in original_paths)
    return f"""# Archived by Digital Custodian

**Archived at:** {archived_at}
**CoDRAG Finding:** {finding_id}
**Reason:** {reason}

## Original Locations

{files_list}

## Restore Instructions

To restore these files, cherry-pick the archive commit or copy them
back from this directory to their original locations.
"""
