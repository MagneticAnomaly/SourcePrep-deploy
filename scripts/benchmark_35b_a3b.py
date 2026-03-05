#!/usr/bin/env python3
"""Benchmark qwen3.5-35b-a3b (MoE, 3B active) via LM Studio.

Runs augmentation + epistemic on mini-redis-rust with ground truth scoring,
then compares against prior 27b-nothink and 14b results.

Usage:
    python scripts/benchmark_35b_a3b.py
"""

import json
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LMSTUDIO_BASE = "http://127.0.0.1:1234/v1"
MODEL_ID = "qwen3.5-35b-a3b"
MODEL_LABEL = "qwen3.5-35b-a3b"
REPO_NAME = "mini-redis-rust"
REPO_PATH = PROJECT_ROOT / "tests" / "eval" / "real_repos" / REPO_NAME

# Prior results for comparison
NOTHINK_RESULTS = PROJECT_ROOT / "results" / "nothink_1772736578" / "results.json"

# ── Ground Truth ──────────────────────────────────────────────────────

GROUND_TRUTH: Dict[str, Dict[str, Any]] = {
    "src/db.rs": {
        "expected_roles": {"core", "data", "model", "storage"},
        "summary_must_contain": ["database", "key", "value"],
        "summary_must_not_contain": ["CLI", "command-line", "HTTP"],
        "domain_tags": {"redis", "storage", "data", "state", "key-value", "database", "cache", "in-memory"},
        "expected_layers": {"data", "business_logic", "infrastructure"},
        "key_exports": {"Db", "DbDropGuard"},
    },
    "src/server.rs": {
        "expected_roles": {"core", "infrastructure", "api", "handler"},
        "summary_must_contain": ["server", "listen", "connection"],
        "summary_must_not_contain": ["CLI", "database schema"],
        "domain_tags": {"server", "networking", "tcp", "async", "tokio", "connection"},
        "expected_layers": {"infrastructure", "business_logic"},
        "key_exports": {"Listener", "Handler", "run"},
    },
    "src/connection.rs": {
        "expected_roles": {"infrastructure", "core", "utility", "networking"},
        "summary_must_contain": ["connection", "frame", "read", "write"],
        "summary_must_not_contain": ["database", "CLI"],
        "domain_tags": {"networking", "tcp", "connection", "protocol", "framing", "io", "async"},
        "expected_layers": {"infrastructure"},
        "key_exports": {"Connection"},
    },
    "src/frame.rs": {
        "expected_roles": {"model", "core", "data", "utility", "infrastructure"},
        "summary_must_contain": ["frame", "RESP", "protocol"],
        "summary_must_not_contain": ["database", "server start"],
        "domain_tags": {"protocol", "RESP", "frame", "parsing", "serialization", "redis"},
        "expected_layers": {"data", "infrastructure", "business_logic"},
        "key_exports": {"Frame"},
    },
    "src/cmd/get.rs": {
        "expected_roles": {"handler", "api", "core", "business_logic", "command"},
        "summary_must_contain": ["get", "command", "key"],
        "summary_must_not_contain": ["set command", "subscribe"],
        "domain_tags": {"redis", "command", "get", "key-value"},
        "expected_layers": {"business_logic", "presentation"},
        "key_exports": {"Get"},
    },
    "src/cmd/set.rs": {
        "expected_roles": {"handler", "api", "core", "business_logic", "command"},
        "summary_must_contain": ["set", "command", "key"],
        "summary_must_not_contain": ["get command", "subscribe"],
        "domain_tags": {"redis", "command", "set", "key-value", "expiry", "ttl"},
        "expected_layers": {"business_logic", "presentation"},
        "key_exports": {"Set"},
    },
    "src/cmd/subscribe.rs": {
        "expected_roles": {"handler", "api", "core", "business_logic", "command"},
        "summary_must_contain": ["subscribe", "channel", "pub"],
        "summary_must_not_contain": ["get command", "set command"],
        "domain_tags": {"redis", "pubsub", "subscribe", "messaging", "channel"},
        "expected_layers": {"business_logic", "presentation"},
        "key_exports": {"Subscribe", "Unsubscribe"},
    },
    "src/parse.rs": {
        "expected_roles": {"utility", "infrastructure", "core"},
        "summary_must_contain": ["parse", "frame", "command"],
        "summary_must_not_contain": ["database", "server"],
        "domain_tags": {"parsing", "protocol", "command", "frame"},
        "expected_layers": {"infrastructure", "data", "business_logic"},
        "key_exports": {"Parse"},
    },
    "src/shutdown.rs": {
        "expected_roles": {"utility", "infrastructure", "core"},
        "summary_must_contain": ["shutdown", "signal", "notify"],
        "summary_must_not_contain": ["database", "command"],
        "domain_tags": {"shutdown", "signal", "async", "lifecycle", "graceful"},
        "expected_layers": {"infrastructure"},
        "key_exports": {"Shutdown"},
    },
    "src/clients/client.rs": {
        "expected_roles": {"api", "core", "utility", "client"},
        "summary_must_contain": ["client", "connect", "command"],
        "summary_must_not_contain": ["server listen", "database"],
        "domain_tags": {"client", "redis", "networking", "async", "api"},
        "expected_layers": {"infrastructure", "presentation", "business_logic"},
        "key_exports": {"Client"},
    },
}

# ── Prompts ───────────────────────────────────────────────────────────

FILE_ROLE_SYSTEM = "You are a code analyst. You classify files by their role in a codebase. You MUST respond with valid JSON only."

FILE_ROLE_PROMPT = """Classify this file's role in the codebase.

File: {file_path}
Symbols defined: {symbol_names}
Imports: {imports}

First 120 lines:
```
{head}
```

Respond with this exact JSON format:
{{"summary": "1 sentence file purpose", "role": "utility", "confidence": 0.85, "key_exports": ["symbol1", "symbol2"], "related_files": ["path/to/related.py"]}}

Where role is one of: api, core, model, utility, config, test, script, ui, documentation, handler, infrastructure, storage, command
related_files: list up to 5 files this file most likely relates to (by path)

JSON response:"""

EPISTEMIC_SYSTEM = """You are an expert software architect performing deep analysis of a codebase.
You produce structured, accurate analysis grounded in the actual code and documentation.
You MUST respond with valid JSON only. No markdown, no explanation outside the JSON."""

EPISTEMIC_PROMPT = """Perform deep epistemic analysis of this code file.

File: {file_path}
Language: rust

Pass 1 summary: {pass1_summary}
Pass 1 role: {pass1_role}

Source excerpt:
```
{source_excerpt}
```

Respond with this exact JSON format:
{{"extended_summary": "2-4 sentence detailed description",
"domain_tags": ["tag1", "tag2"],
"architecture_layer": "business_logic",
"subsystem": "name-of-subsystem",
"staleness_risk": "low",
"epistemic_confidence": 0.85}}

Where architecture_layer is one of: presentation, business_logic, data, infrastructure, configuration, testing, documentation, build, unknown
domain_tags: 1-4 descriptive tags for the domain

JSON response:"""


# ── LM Studio Client ─────────────────────────────────────────────────

def lmstudio_chat(system: str, user: str, max_tokens: int = 8192) -> Tuple[float, str, int, float]:
    """Call LM Studio, return (wall_time, text, token_count, tok_per_sec)."""
    payload = json.dumps({
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "stream": False,
    }).encode("utf-8")
    req = Request(
        f"{LMSTUDIO_BASE}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.monotonic()
    with urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    dt = time.monotonic() - t0
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    comp = usage.get("completion_tokens", 0)
    tps = comp / dt if dt > 0 else 0
    return dt, text, comp, tps


def strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def parse_json(text: str) -> Optional[Dict[str, Any]]:
    text = strip_think(text)
    # Also strip "Thinking Process:" plain-text thinking blocks
    text = re.sub(r"^Thinking Process:.*?(?=\{)", "", text, flags=re.DOTALL).strip()
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1).strip())
        except json.JSONDecodeError: pass
    try: return json.loads(text)
    except json.JSONDecodeError: pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(0))
        except json.JSONDecodeError: pass
    return None


# ── Helpers ───────────────────────────────────────────────────────────

def extract_imports(content: str) -> List[str]:
    return re.findall(r"^(?:use |extern crate |mod ).*", content, re.MULTILINE)[:10]

def extract_symbols(content: str) -> List[str]:
    return re.findall(r"(?:pub\s+)?(?:fn|struct|enum|trait|impl|type|const|static)\s+(\w+)", content, re.MULTILINE)[:15]


def score_augment(parsed: Dict[str, Any], gt: Dict[str, Any]) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    role = parsed.get("role", "").lower()
    scores["role"] = 1.0 if role in {r.lower() for r in gt.get("expected_roles", set())} else 0.0
    summary = parsed.get("summary", "").lower()
    mc = gt.get("summary_must_contain", [])
    mn = gt.get("summary_must_not_contain", [])
    cs = sum(1 for w in mc if w.lower() in summary) / len(mc) if mc else 1.0
    ns = 1.0 - (sum(1 for w in mn if w.lower() in summary) / len(mn)) if mn else 1.0
    scores["summary"] = cs * 0.7 + ns * 0.3
    exports = {e.lower() for e in parsed.get("key_exports", [])}
    expected = {e.lower() for e in gt.get("key_exports", set())}
    scores["exports"] = len(exports & expected) / len(expected) if expected else 1.0
    scores["total"] = scores["role"] * 0.3 + scores["summary"] * 0.4 + scores["exports"] * 0.3
    return scores


def score_epistemic(parsed: Dict[str, Any], gt: Dict[str, Any]) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    layer = parsed.get("architecture_layer", "").lower()
    scores["layer"] = 1.0 if layer in {l.lower() for l in gt.get("expected_layers", set())} else 0.0
    tags = {t.lower() for t in parsed.get("domain_tags", [])}
    etags = {t.lower() for t in gt.get("domain_tags", set())}
    if etags and tags:
        overlap = len(tags & etags)
        partial = sum(0.5 for t in tags if any(t in et or et in t for et in etags) and t not in etags)
        scores["tags"] = min(1.0, (overlap + partial) / len(etags))
    else:
        scores["tags"] = 0.0
    summary = parsed.get("extended_summary", "").lower()
    mc = gt.get("summary_must_contain", [])
    mn = gt.get("summary_must_not_contain", [])
    cs = sum(1 for w in mc if w.lower() in summary) / len(mc) if mc else 1.0
    ns = 1.0 - (sum(1 for w in mn if w.lower() in summary) / len(mn)) if mn else 1.0
    scores["summary"] = cs * 0.7 + ns * 0.3
    scores["total"] = scores["layer"] * 0.25 + scores["tags"] * 0.25 + scores["summary"] * 0.5
    return scores


# ── Main ──────────────────────────────────────────────────────────────

def run():
    gt_files = [(rp, REPO_PATH / rp) for rp in sorted(GROUND_TRUTH) if (REPO_PATH / rp).exists()]

    print(f"\n{'='*70}")
    print(f"  BENCHMARK: {MODEL_LABEL} (MoE 35B, ~3B active)")
    print(f"  Backend: LM Studio MLX | Files: {len(gt_files)}")
    print(f"{'='*70}\n")

    aug_results = []
    epi_results = []

    for rel_path, full_path in gt_files:
        content = full_path.read_text(encoding="utf-8", errors="replace")
        imports = extract_imports(content)
        symbols = extract_symbols(content)
        head = "\n".join(content.splitlines()[:120])
        excerpt = "\n".join(content.splitlines()[:200])
        gt = GROUND_TRUTH[rel_path]

        print(f"  {rel_path}")

        # Augmentation
        prompt = FILE_ROLE_PROMPT.format(
            file_path=rel_path,
            symbol_names=", ".join(symbols) if symbols else "(none)",
            imports="; ".join(imports) if imports else "(none)",
            head=head, content_label="First 120 lines",
        )
        print(f"    augment", end="", flush=True)
        dt, text, toks, tps = lmstudio_chat(FILE_ROLE_SYSTEM, prompt)
        parsed = parse_json(text)
        entry = {"file": rel_path, "wall_time": dt, "tokens": toks, "tps": tps, "parsed": parsed is not None}
        if parsed:
            s = score_augment(parsed, gt)
            entry.update({"confidence": parsed.get("confidence", 0), "summary": parsed.get("summary", ""),
                          "role": parsed.get("role", ""), "exports": parsed.get("key_exports", []),
                          "total_score": s["total"], "role_score": s["role"], "summary_score": s["summary"], "export_score": s["exports"]})
            print(f"  {dt:.1f}s  {toks}tok  {tps:.0f}t/s  score={s['total']:.2f}  role={parsed.get('role','?')}")
        else:
            entry["total_score"] = 0
            entry["error"] = text[:100]
            print(f"  {dt:.1f}s  {toks}tok  ✗ parse fail")
        aug_results.append(entry)

        # Epistemic
        p1s = parsed.get("summary", "(unavailable)") if parsed else "(unavailable)"
        p1r = parsed.get("role", "unknown") if parsed else "unknown"
        ep = EPISTEMIC_PROMPT.format(file_path=rel_path, pass1_summary=p1s, pass1_role=p1r, source_excerpt=excerpt)
        print(f"    epist.", end="", flush=True)
        dt, text, toks, tps = lmstudio_chat(EPISTEMIC_SYSTEM, ep)
        parsed = parse_json(text)
        entry = {"file": rel_path, "wall_time": dt, "tokens": toks, "tps": tps, "parsed": parsed is not None}
        if parsed:
            s = score_epistemic(parsed, gt)
            entry.update({"confidence": parsed.get("epistemic_confidence", 0),
                          "summary": parsed.get("extended_summary", ""),
                          "tags": parsed.get("domain_tags", []),
                          "layer": parsed.get("architecture_layer", ""),
                          "total_score": s["total"], "layer_score": s["layer"], "tag_score": s["tags"], "summary_score": s["summary"]})
            print(f"  {dt:.1f}s  {toks}tok  {tps:.0f}t/s  score={s['total']:.2f}  layer={parsed.get('architecture_layer','?')}")
        else:
            entry["total_score"] = 0
            entry["error"] = text[:100]
            print(f"  {dt:.1f}s  {toks}tok  ✗ parse fail")
        epi_results.append(entry)

    # ── Report ────────────────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print(f"  RESULTS: {MODEL_LABEL}")
    print(f"{'='*70}\n")

    va = [r for r in aug_results if r["parsed"]]
    ve = [r for r in epi_results if r["parsed"]]

    print(f"  AUGMENTATION")
    print(f"  {'─'*50}")
    print(f"  Parse rate:     {len(va)}/{len(aug_results)} ({len(va)/len(aug_results):.0%})")
    if va:
        print(f"  Avg quality:    {statistics.mean([r['total_score'] for r in va]):.2f}")
        print(f"  Avg confidence: {statistics.mean([r['confidence'] for r in va]):.2f}")
        print(f"  Avg time/file:  {statistics.mean([r['wall_time'] for r in va]):.1f}s")
        print(f"  Avg tok/s:      {statistics.mean([r['tps'] for r in va]):.0f}")
        print(f"  Total time:     {sum(r['wall_time'] for r in aug_results):.0f}s")

    print(f"\n  EPISTEMIC")
    print(f"  {'─'*50}")
    print(f"  Parse rate:     {len(ve)}/{len(epi_results)} ({len(ve)/len(epi_results):.0%})")
    if ve:
        print(f"  Avg quality:    {statistics.mean([r['total_score'] for r in ve]):.2f}")
        print(f"  Avg confidence: {statistics.mean([r['confidence'] for r in ve]):.2f}")
        print(f"  Avg time/file:  {statistics.mean([r['wall_time'] for r in ve]):.1f}s")
        print(f"  Avg tok/s:      {statistics.mean([r['tps'] for r in ve]):.0f}")
        print(f"  Total time:     {sum(r['wall_time'] for r in epi_results):.0f}s")

    # ── Compare with prior results ────────────────────────────────────
    print(f"\n\n{'='*70}")
    print(f"  HEAD-TO-HEAD COMPARISON")
    print(f"{'='*70}\n")

    # Load 27b no-think
    nt_aug, nt_epi = {}, {}
    if NOTHINK_RESULTS.exists():
        with open(NOTHINK_RESULTS) as f:
            nt = json.load(f)
        nt_aug = {r["file"]: r for r in nt["augment"] if r["parsed"]}
        nt_epi = {r["file"]: r for r in nt["epistemic"] if r["parsed"]}

    # Per-file augmentation
    print(f"  AUGMENTATION — per file")
    print(f"  {'File':<24} {'35b-a3b':>8} {'27b-NT':>8} {'35b role':<12} {'27b role':<12} {'35b time':>8} {'27b time':>8}")
    print(f"  {'─'*84}")
    for r in aug_results:
        fp = r["file"]
        nt_r = nt_aug.get(fp)
        ts = f"{r['total_score']:.2f}" if r["parsed"] else "FAIL"
        ns = f"{nt_r['total_score']:.2f}" if nt_r else "—"
        tr = r.get("role", "—") if r["parsed"] else "—"
        nr = nt_r.get("role", "—") if nt_r else "—"
        tt = f"{r['wall_time']:.0f}s"
        nt_t = f"{nt_r['wall_time']:.0f}s" if nt_r else "—"
        print(f"  {fp:<24} {ts:>8} {ns:>8} {tr:<12} {nr:<12} {tt:>8} {nt_t:>8}")

    # Per-file epistemic
    print(f"\n  EPISTEMIC — per file")
    print(f"  {'File':<24} {'35b-a3b':>8} {'27b-NT':>8} {'35b layer':<16} {'27b layer':<16} {'35b time':>8} {'27b time':>8}")
    print(f"  {'─'*96}")
    for r in epi_results:
        fp = r["file"]
        nt_r = nt_epi.get(fp)
        ts = f"{r['total_score']:.2f}" if r["parsed"] else "FAIL"
        ns = f"{nt_r['total_score']:.2f}" if nt_r else "—"
        tl = r.get("layer", "—") if r["parsed"] else "—"
        nl = nt_r.get("layer", "—") if nt_r else "—"
        tt = f"{r['wall_time']:.0f}s"
        nt_t = f"{nt_r['wall_time']:.0f}s" if nt_r else "—"
        print(f"  {fp:<24} {ts:>8} {ns:>8} {tl:<16} {nl:<16} {tt:>8} {nt_t:>8}")

    # Aggregate
    if va and nt_aug:
        common = set(r["file"] for r in va) & set(nt_aug.keys())
        if common:
            t_q = statistics.mean([r["total_score"] for r in va if r["file"] in common])
            n_q = statistics.mean([nt_aug[f]["total_score"] for f in common])
            t_t = sum(r["wall_time"] for r in aug_results if r["file"] in common)
            n_t = sum(nt_aug[f]["wall_time"] for f in common)
            print(f"\n  AGGREGATE (augmentation, {len(common)} common files)")
            print(f"  {'─'*50}")
            print(f"  {'Metric':<25} {'35b-a3b':>10} {'27b-NT':>10}")
            print(f"  {'Avg quality':<25} {t_q:>10.2f} {n_q:>10.2f}")
            print(f"  {'Total time':<25} {t_t:>9.0f}s {n_t:>9.0f}s")

    if ve and nt_epi:
        common = set(r["file"] for r in ve) & set(nt_epi.keys())
        if common:
            t_q = statistics.mean([r["total_score"] for r in ve if r["file"] in common])
            n_q = statistics.mean([nt_epi[f]["total_score"] for f in common])
            t_t = sum(r["wall_time"] for r in epi_results if r["file"] in common)
            n_t = sum(nt_epi[f]["wall_time"] for f in common)
            print(f"\n  AGGREGATE (epistemic, {len(common)} common files)")
            print(f"  {'─'*50}")
            print(f"  {'Metric':<25} {'35b-a3b':>10} {'27b-NT':>10}")
            print(f"  {'Avg quality':<25} {t_q:>10.2f} {n_q:>10.2f}")
            print(f"  {'Total time':<25} {t_t:>9.0f}s {n_t:>9.0f}s")

    # Save
    outdir = PROJECT_ROOT / "results" / f"35b_a3b_{int(time.time())}"
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "results.json", "w") as f:
        json.dump({"augment": aug_results, "epistemic": epi_results}, f, indent=2)
    print(f"\n  Saved to {outdir / 'results.json'}")


if __name__ == "__main__":
    # Verify model loaded
    try:
        req = Request(f"{LMSTUDIO_BASE}/models")
        with urlopen(req, timeout=5) as resp:
            models = json.loads(resp.read())
        loaded = [m["id"] for m in models.get("data", [])]
        if MODEL_ID not in loaded:
            print(f"ERROR: {MODEL_ID} not loaded in LM Studio. Available: {[m for m in loaded if 'qwen' in m.lower()]}")
            sys.exit(1)
        print(f"✓ {MODEL_ID} loaded")
    except URLError:
        print("ERROR: Cannot connect to LM Studio")
        sys.exit(1)

    run()
