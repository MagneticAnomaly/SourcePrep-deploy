"""
Query preprocessing for Prep (Phase 34e F).

Lightweight cleanup for better embedding similarity without
destroying semantic content.  Extracted from projects.py router
(Refactor 2, GAP-3) so it can be reused by MCP, CLI, and scripts.
"""
from __future__ import annotations

import re

# F2: Conversational filler prefixes to strip
_FILLER_PREFIXES = re.compile(
    r"^(?:"
    r"(?:please|pls|plz)\s+|"
    r"can you\s+|could you\s+|would you\s+|"
    r"i (?:want|need|would like) (?:you )?to\s+|"
    r"help me\s+|"
    r"i'm (?:trying|looking|wanting) to\s+|"
    r"show me\s+|"
    r"let's\s+|"
    r"go ahead and\s+|"
    r"i'd like (?:you )?to\s+"
    r")+",
    re.IGNORECASE,
)

# F3: Code entity patterns to preserve (not stripped)
_CODE_ENTITY = re.compile(
    r"[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+|"   # dotted names: os.path.join
    r"[a-z]+(?:[A-Z][a-z]+)+|"             # camelCase: getUserName
    r"[A-Z][a-z]+(?:[A-Z][a-z]+)+|"        # PascalCase: UserManager
    r"[a-zA-Z_]+(?:_[a-zA-Z_]+)+|"         # snake_case: get_user_name
    r"[\w./\\]+\.\w{1,5}"                  # file paths: src/utils.py
)

_MAX_QUERY_CHARS = 300  # F1: Truncation limit


def preprocess_query(query: str) -> str:
    """Lightweight query preprocessing for better retrieval.

    F1: Truncate to 300 chars (embedding models plateau on long queries).
    F2: Strip conversational filler prefixes.
    F3: Preserve code entities (camelCase, snake_case, dotted names, paths).
    """
    q = query.strip()
    if not q:
        return q

    # F2: Strip conversational filler from the start
    q = _FILLER_PREFIXES.sub("", q).strip()

    # F1: Truncate — break at last word boundary before limit
    if len(q) > _MAX_QUERY_CHARS:
        cut = q[:_MAX_QUERY_CHARS]
        last_space = cut.rfind(" ")
        if last_space > _MAX_QUERY_CHARS // 2:
            q = cut[:last_space]
        else:
            q = cut

    return q
