#!/usr/bin/env python3
"""Benchmark qwen3.5-27b think=ON vs think=OFF via Ollama.

Runs both augmentation and epistemic prompts on real files, then scores
quality against human-written ground truth.

Usage:
    python scripts/benchmark_think_comparison.py
    python scripts/benchmark_think_comparison.py --files 5
"""

import argparse
import json
import os
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OLLAMA_BASE = "http://127.0.0.1:11434"
MODEL = "qwen3.5:27b"
REPO_NAME = "mini-redis-rust"
REPO_PATH = PROJECT_ROOT / "tests" / "eval" / "real_repos" / REPO_NAME

# ── Ground Truth ──────────────────────────────────────────────────────
# Human-written expected values for mini-redis-rust core files.
# Used to score model quality objectively.

GROUND_TRUTH: Dict[str, Dict[str, Any]] = {
    "src/db.rs": {
        "role": "core",
        "expected_roles": {"core", "data", "model", "storage"},
        "summary_must_contain": ["database", "key", "value"],
        "summary_must_not_contain": ["CLI", "command-line", "HTTP"],
        "domain_tags": {"redis", "storage", "data", "state", "key-value", "database", "cache", "in-memory"},
        "architecture_layer": "data",
        "expected_layers": {"data", "business_logic", "infrastructure"},
        "key_exports": {"Db", "DbDropGuard"},
    },
    "src/server.rs": {
        "role": "core",
        "expected_roles": {"core", "infrastructure", "api", "handler"},
        "summary_must_contain": ["server", "listen", "connection"],
        "summary_must_not_contain": ["CLI", "database schema"],
        "domain_tags": {"server", "networking", "tcp", "async", "tokio", "connection"},
        "architecture_layer": "infrastructure",
        "expected_layers": {"infrastructure", "business_logic"},
        "key_exports": {"Listener", "Handler", "run"},
    },
    "src/connection.rs": {
        "role": "infrastructure",
        "expected_roles": {"infrastructure", "core", "utility", "networking"},
        "summary_must_contain": ["connection", "frame", "read", "write"],
        "summary_must_not_contain": ["database", "CLI"],
        "domain_tags": {"networking", "tcp", "connection", "protocol", "framing", "io", "async"},
        "architecture_layer": "infrastructure",
        "expected_layers": {"infrastructure"},
        "key_exports": {"Connection"},
    },
    "src/frame.rs": {
        "role": "model",
        "expected_roles": {"model", "core", "data", "utility", "infrastructure"},
        "summary_must_contain": ["frame", "RESP", "protocol"],
        "summary_must_not_contain": ["database", "server start"],
        "domain_tags": {"protocol", "RESP", "frame", "parsing", "serialization", "redis"},
        "architecture_layer": "data",
        "expected_layers": {"data", "infrastructure", "business_logic"},
        "key_exports": {"Frame"},
    },
    "src/cmd/get.rs": {
        "role": "handler",
        "expected_roles": {"handler", "api", "core", "business_logic", "command"},
        "summary_must_contain": ["get", "command", "key"],
        "summary_must_not_contain": ["set command", "subscribe"],
        "domain_tags": {"redis", "command", "get", "key-value"},
        "architecture_layer": "business_logic",
        "expected_layers": {"business_logic", "presentation"},
        "key_exports": {"Get"},
    },
    "src/cmd/set.rs": {
        "role": "handler",
        "expected_roles": {"handler", "api", "core", "business_logic", "command"},
        "summary_must_contain": ["set", "command", "key"],
        "summary_must_not_contain": ["get command", "subscribe"],
        "domain_tags": {"redis", "command", "set", "key-value", "expiry", "ttl"},
        "architecture_layer": "business_logic",
        "expected_layers": {"business_logic", "presentation"},
        "key_exports": {"Set"},
    },
    "src/cmd/subscribe.rs": {
        "role": "handler",
        "expected_roles": {"handler", "api", "core", "business_logic", "command"},
        "summary_must_contain": ["subscribe", "channel", "pub"],
        "summary_must_not_contain": ["get command", "set command"],
        "domain_tags": {"redis", "pubsub", "subscribe", "messaging", "channel"},
        "architecture_layer": "business_logic",
        "expected_layers": {"business_logic", "presentation"},
        "key_exports": {"Subscribe", "Unsubscribe"},
    },
    "src/parse.rs": {
        "role": "utility",
        "expected_roles": {"utility", "infrastructure", "core"},
        "summary_must_contain": ["parse", "frame", "command"],
        "summary_must_not_contain": ["database", "server"],
        "domain_tags": {"parsing", "protocol", "command", "frame"},
        "architecture_layer": "infrastructure",
        "expected_layers": {"infrastructure", "data", "business_logic"},
        "key_exports": {"Parse"},
    },
    "src/shutdown.rs": {
        "role": "utility",
        "expected_roles": {"utility", "infrastructure", "core"},
        "summary_must_contain": ["shutdown", "signal", "notify"],
        "summary_must_not_contain": ["database", "command"],
        "domain_tags": {"shutdown", "signal", "async", "lifecycle", "graceful"},
        "architecture_layer": "infrastructure",
        "expected_layers": {"infrastructure"},
        "key_exports": {"Shutdown"},
    },
    "src/clients/client.rs": {
        "role": "api",
        "expected_roles": {"api", "core", "utility", "client"},
        "summary_must_contain": ["client", "connect", "command"],
        "summary_must_not_contain": ["server listen", "database"],
        "domain_tags": {"client", "redis", "networking", "async", "api"},
        "architecture_layer": "infrastructure",
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


# ── Ollama Client ─────────────────────────────────────────────────────

def ollama_chat(system: str, user: str, think: bool) -> Tuple[float, str, int, float]:
    """Call Ollama, return (wall_time, text, token_count, tok_per_sec)."""
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 4096},
        "think": think,
    }
    payload = json.dumps(body).encode()
    req = Request(f"{OLLAMA_BASE}/api/chat", data=payload, headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
    dt = time.monotonic() - t0
    text = data.get("message", {}).get("content", "")
    eval_count = data.get("eval_count", 0)
    eval_dur = data.get("eval_duration", 1) / 1e9
    tps = eval_count / eval_dur if eval_dur > 0 else 0
    return dt, text, eval_count, tps


def parse_json(text: str) -> Optional[Dict[str, Any]]:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Try extracting from markdown fence
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ── File helpers ──────────────────────────────────────────────────────

def extract_imports(content: str) -> List[str]:
    return re.findall(r"^(?:use |extern crate |mod ).*", content, re.MULTILINE)[:10]

def extract_symbols(content: str) -> List[str]:
    return re.findall(r"(?:pub\s+)?(?:fn|struct|enum|trait|impl|type|const|static)\s+(\w+)", content, re.MULTILINE)[:15]


# ── Quality Scoring ───────────────────────────────────────────────────

@dataclass
class QualityScore:
    file_path: str
    mode: str  # "think" or "nothink"
    task: str  # "augment" or "epistemic"
    json_parsed: bool = False
    wall_time: float = 0.0
    tokens: int = 0
    tps: float = 0.0
    confidence: float = 0.0
    # Scores (0-1)
    role_score: float = 0.0
    summary_score: float = 0.0
    tag_score: float = 0.0
    layer_score: float = 0.0
    export_score: float = 0.0
    total_score: float = 0.0
    # Raw
    summary: str = ""
    role: str = ""
    tags: List[str] = field(default_factory=list)
    layer: str = ""
    exports: List[str] = field(default_factory=list)
    error: str = ""


def score_augment(parsed: Dict[str, Any], gt: Dict[str, Any]) -> Dict[str, float]:
    """Score augmentation output against ground truth."""
    scores: Dict[str, float] = {}

    # Role accuracy: 1.0 if exact match with any expected role
    role = parsed.get("role", "").lower()
    expected_roles = {r.lower() for r in gt.get("expected_roles", set())}
    scores["role"] = 1.0 if role in expected_roles else 0.0

    # Summary: check must_contain and must_not_contain
    summary = parsed.get("summary", "").lower()
    must_contain = gt.get("summary_must_contain", [])
    must_not = gt.get("summary_must_not_contain", [])
    contain_hits = sum(1 for w in must_contain if w.lower() in summary)
    contain_score = contain_hits / len(must_contain) if must_contain else 1.0
    not_hits = sum(1 for w in must_not if w.lower() in summary)
    not_score = 1.0 - (not_hits / len(must_not)) if must_not else 1.0
    scores["summary"] = (contain_score * 0.7 + not_score * 0.3)

    # Key exports overlap
    exports = {e.lower() for e in parsed.get("key_exports", [])}
    expected_exports = {e.lower() for e in gt.get("key_exports", set())}
    if expected_exports:
        overlap = len(exports & expected_exports)
        scores["exports"] = overlap / len(expected_exports)
    else:
        scores["exports"] = 1.0

    scores["total"] = (scores["role"] * 0.3 + scores["summary"] * 0.4 + scores["exports"] * 0.3)
    return scores


def score_epistemic(parsed: Dict[str, Any], gt: Dict[str, Any]) -> Dict[str, float]:
    """Score epistemic output against ground truth."""
    scores: Dict[str, float] = {}

    # Architecture layer
    layer = parsed.get("architecture_layer", "").lower()
    expected_layers = {l.lower() for l in gt.get("expected_layers", set())}
    scores["layer"] = 1.0 if layer in expected_layers else 0.0

    # Domain tags overlap (fuzzy — partial credit for related tags)
    tags = {t.lower() for t in parsed.get("domain_tags", [])}
    expected_tags = {t.lower() for t in gt.get("domain_tags", set())}
    if expected_tags and tags:
        # Exact overlap
        overlap = len(tags & expected_tags)
        # Partial credit for substring matches
        partial = 0
        for t in tags:
            for et in expected_tags:
                if t in et or et in t:
                    partial += 0.5
                    break
        scores["tags"] = min(1.0, (overlap + partial) / len(expected_tags))
    else:
        scores["tags"] = 0.0

    # Summary quality
    summary = parsed.get("extended_summary", "").lower()
    must_contain = gt.get("summary_must_contain", [])
    must_not = gt.get("summary_must_not_contain", [])
    contain_hits = sum(1 for w in must_contain if w.lower() in summary)
    contain_score = contain_hits / len(must_contain) if must_contain else 1.0
    not_hits = sum(1 for w in must_not if w.lower() in summary)
    not_score = 1.0 - (not_hits / len(must_not)) if must_not else 1.0
    scores["summary"] = (contain_score * 0.7 + not_score * 0.3)

    scores["total"] = (scores["layer"] * 0.25 + scores["tags"] * 0.25 + scores["summary"] * 0.5)
    return scores


# ── Main Runner ───────────────────────────────────────────────────────

def run_benchmark(max_files: Optional[int] = None):
    # Discover files that have ground truth
    gt_files = []
    for rel_path in sorted(GROUND_TRUTH.keys()):
        full = REPO_PATH / rel_path
        if full.exists():
            gt_files.append((rel_path, full))
    if max_files:
        gt_files = gt_files[:max_files]

    print(f"\n{'='*70}")
    print(f"  THINK vs NO-THINK: qwen3.5:27b on {REPO_NAME}")
    print(f"  Files: {len(gt_files)} (with ground truth)")
    print(f"{'='*70}\n")

    results: Dict[str, List[QualityScore]] = {
        "think_augment": [], "nothink_augment": [],
        "think_epistemic": [], "nothink_epistemic": [],
    }

    for rel_path, full_path in gt_files:
        content = full_path.read_text(encoding="utf-8", errors="replace")
        imports = extract_imports(content)
        symbols = extract_symbols(content)
        head = "\n".join(content.splitlines()[:120])
        excerpt = "\n".join(content.splitlines()[:200])
        gt = GROUND_TRUTH[rel_path]

        print(f"\n  ── {rel_path} ──")

        for think_mode in [True, False]:
            mode_label = "think" if think_mode else "nothink"
            mode_icon = "🧠" if think_mode else "⚡"

            # --- Augmentation ---
            prompt = FILE_ROLE_PROMPT.format(
                file_path=rel_path,
                symbol_names=", ".join(symbols) if symbols else "(none)",
                imports="; ".join(imports) if imports else "(none)",
                head=head,
                content_label="First 120 lines",
            )

            qs = QualityScore(file_path=rel_path, mode=mode_label, task="augment")
            print(f"    {mode_icon} augment [{mode_label}]", end="", flush=True)
            try:
                dt, text, toks, tps = ollama_chat(FILE_ROLE_SYSTEM, prompt, think=think_mode)
                qs.wall_time = dt
                qs.tokens = toks
                qs.tps = tps
                parsed = parse_json(text)
                if parsed:
                    qs.json_parsed = True
                    qs.confidence = float(parsed.get("confidence", 0))
                    qs.summary = parsed.get("summary", "")
                    qs.role = parsed.get("role", "")
                    qs.exports = parsed.get("key_exports", [])
                    scores = score_augment(parsed, gt)
                    qs.role_score = scores["role"]
                    qs.summary_score = scores["summary"]
                    qs.export_score = scores["exports"]
                    qs.total_score = scores["total"]
                else:
                    qs.error = "JSON parse failed"
            except Exception as e:
                qs.error = str(e)

            results[f"{mode_label}_augment"].append(qs)
            status = f"score={qs.total_score:.2f}" if qs.json_parsed else f"✗ {qs.error}"
            print(f"  {dt:.1f}s  {toks}tok  {tps:.0f}t/s  {status}")

            # --- Epistemic ---
            ep_prompt = EPISTEMIC_PROMPT.format(
                file_path=rel_path,
                pass1_summary=qs.summary if qs.json_parsed else "(unavailable)",
                pass1_role=qs.role if qs.json_parsed else "unknown",
                source_excerpt=excerpt,
            )

            eqs = QualityScore(file_path=rel_path, mode=mode_label, task="epistemic")
            print(f"    {mode_icon} epist.  [{mode_label}]", end="", flush=True)
            try:
                dt, text, toks, tps = ollama_chat(EPISTEMIC_SYSTEM, ep_prompt, think=think_mode)
                eqs.wall_time = dt
                eqs.tokens = toks
                eqs.tps = tps
                parsed = parse_json(text)
                if parsed:
                    eqs.json_parsed = True
                    eqs.confidence = float(parsed.get("epistemic_confidence", 0))
                    eqs.summary = parsed.get("extended_summary", "")
                    eqs.tags = parsed.get("domain_tags", [])
                    eqs.layer = parsed.get("architecture_layer", "")
                    scores = score_epistemic(parsed, gt)
                    eqs.layer_score = scores["layer"]
                    eqs.tag_score = scores["tags"]
                    eqs.summary_score = scores["summary"]
                    eqs.total_score = scores["total"]
                else:
                    eqs.error = "JSON parse failed"
            except Exception as e:
                eqs.error = str(e)

            results[f"{mode_label}_epistemic"].append(eqs)
            status = f"score={eqs.total_score:.2f}" if eqs.json_parsed else f"✗ {eqs.error}"
            print(f"  {dt:.1f}s  {toks}tok  {tps:.0f}t/s  {status}")

    # ── Report ────────────────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print(f"  RESULTS")
    print(f"{'='*70}\n")

    for task in ["augment", "epistemic"]:
        think_list = results[f"think_{task}"]
        nothink_list = results[f"nothink_{task}"]

        t_parsed = [r for r in think_list if r.json_parsed]
        n_parsed = [r for r in nothink_list if r.json_parsed]

        print(f"  {task.upper()}")
        print(f"  {'─'*50}")
        print(f"  {'Metric':<25} {'Think':>10} {'No-Think':>10} {'Winner':>8}")
        print(f"  {'─'*50}")

        t_time = sum(r.wall_time for r in think_list)
        n_time = sum(r.wall_time for r in nothink_list)
        speedup = t_time / n_time if n_time > 0 else 0
        print(f"  {'Total time':<25} {t_time:>9.0f}s {n_time:>9.0f}s {'NT ' + f'{speedup:.0f}×':>8}")

        t_toks = sum(r.tokens for r in think_list)
        n_toks = sum(r.tokens for r in nothink_list)
        print(f"  {'Total tokens':<25} {t_toks:>10} {n_toks:>10} {'NT':>8}")

        t_parse = len(t_parsed) / len(think_list) if think_list else 0
        n_parse = len(n_parsed) / len(nothink_list) if nothink_list else 0
        w = "NT" if n_parse >= t_parse else "T"
        print(f"  {'JSON parse rate':<25} {t_parse:>9.0%} {n_parse:>9.0%} {w:>8}")

        if t_parsed and n_parsed:
            t_conf = statistics.mean([r.confidence for r in t_parsed])
            n_conf = statistics.mean([r.confidence for r in n_parsed])
            w = "T" if t_conf > n_conf + 0.02 else ("NT" if n_conf > t_conf + 0.02 else "TIE")
            print(f"  {'Avg confidence':<25} {t_conf:>10.2f} {n_conf:>10.2f} {w:>8}")

            t_qual = statistics.mean([r.total_score for r in t_parsed])
            n_qual = statistics.mean([r.total_score for r in n_parsed])
            w = "T" if t_qual > n_qual + 0.02 else ("NT" if n_qual > t_qual + 0.02 else "TIE")
            print(f"  {'Avg quality score':<25} {t_qual:>10.2f} {n_qual:>10.2f} {w:>8}")

            t_sumlen = statistics.mean([len(r.summary) for r in t_parsed])
            n_sumlen = statistics.mean([len(r.summary) for r in n_parsed])
            print(f"  {'Avg summary len':<25} {t_sumlen:>9.0f}c {n_sumlen:>9.0f}c")

        print()

    # Per-file detail
    print(f"  PER-FILE QUALITY SCORES")
    print(f"  {'─'*70}")
    print(f"  {'File':<28} {'Task':<10} {'Think':>7} {'NoThink':>7} {'Δ':>6}")
    print(f"  {'─'*70}")
    for rel_path, _ in gt_files:
        for task in ["augment", "epistemic"]:
            t = next((r for r in results[f"think_{task}"] if r.file_path == rel_path), None)
            n = next((r for r in results[f"nothink_{task}"] if r.file_path == rel_path), None)
            ts = f"{t.total_score:.2f}" if t and t.json_parsed else "FAIL"
            ns = f"{n.total_score:.2f}" if n and n.json_parsed else "FAIL"
            if t and n and t.json_parsed and n.json_parsed:
                delta = n.total_score - t.total_score
                ds = f"{delta:+.2f}"
            else:
                ds = "—"
            fname = rel_path[:26]
            print(f"  {fname:<28} {task:<10} {ts:>7} {ns:>7} {ds:>6}")

    # Save results
    outdir = PROJECT_ROOT / "results" / f"think_comparison_{int(time.time())}"
    outdir.mkdir(parents=True, exist_ok=True)
    serializable = {}
    for key, rlist in results.items():
        serializable[key] = [{
            "file": r.file_path, "mode": r.mode, "task": r.task,
            "wall_time": r.wall_time, "tokens": r.tokens, "tps": r.tps,
            "json_parsed": r.json_parsed, "confidence": r.confidence,
            "role_score": r.role_score, "summary_score": r.summary_score,
            "tag_score": r.tag_score, "layer_score": r.layer_score,
            "export_score": r.export_score, "total_score": r.total_score,
            "summary": r.summary, "role": r.role, "tags": r.tags,
            "layer": r.layer, "exports": r.exports, "error": r.error,
        } for r in rlist]

    with open(outdir / "results.json", "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"\n  Saved to {outdir / 'results.json'}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=int, default=None, help="Max files (default: all with ground truth)")
    args = parser.parse_args()

    # Verify Ollama
    try:
        req = Request(f"{OLLAMA_BASE}/api/tags")
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        models = [m["name"] for m in data.get("models", [])]
        if MODEL not in models:
            print(f"ERROR: {MODEL} not in Ollama. Available: {models}")
            sys.exit(1)
        print(f"✓ Ollama has {MODEL}")
    except URLError:
        print(f"ERROR: Cannot connect to Ollama at {OLLAMA_BASE}")
        sys.exit(1)

    run_benchmark(max_files=args.files)


if __name__ == "__main__":
    main()
