#!/usr/bin/env python3
"""Run qwen3.5:27b NO-THINK only via Ollama on mini-redis-rust.

Scores results against ground truth, then loads the existing LM Studio
think-ON results for side-by-side comparison.

Usage:
    python scripts/benchmark_nothink_only.py
    python scripts/benchmark_nothink_only.py --files 5
"""

import json
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OLLAMA_BASE = "http://127.0.0.1:11434"
MODEL = "qwen3.5:27b"
REPO_NAME = "mini-redis-rust"
REPO_PATH = PROJECT_ROOT / "tests" / "eval" / "real_repos" / REPO_NAME

# Prior LM Studio think-ON results (epistemic pass, from results/model_comparison_1772656324)
PRIOR_THINK_RESULTS = PROJECT_ROOT / "results" / "model_comparison_1772656324" / "results.json"

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


# ── Ollama Client ─────────────────────────────────────────────────────

def ollama_chat(system: str, user: str) -> Tuple[float, str, int, float]:
    """Call Ollama with think=False, return (wall_time, text, tokens, tok/s)."""
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 2048},
        "think": False,
    }
    payload = json.dumps(body).encode()
    req = Request(f"{OLLAMA_BASE}/api/chat", data=payload, headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read())
    dt = time.monotonic() - t0
    text = data.get("message", {}).get("content", "")
    eval_count = data.get("eval_count", 0)
    eval_dur = data.get("eval_duration", 1) / 1e9
    tps = eval_count / eval_dur if eval_dur > 0 else 0
    return dt, text, eval_count, tps


def parse_json(text: str) -> Optional[Dict[str, Any]]:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
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
    expected_roles = {r.lower() for r in gt.get("expected_roles", set())}
    scores["role"] = 1.0 if role in expected_roles else 0.0

    summary = parsed.get("summary", "").lower()
    must_contain = gt.get("summary_must_contain", [])
    must_not = gt.get("summary_must_not_contain", [])
    contain_hits = sum(1 for w in must_contain if w.lower() in summary)
    contain_score = contain_hits / len(must_contain) if must_contain else 1.0
    not_hits = sum(1 for w in must_not if w.lower() in summary)
    not_score = 1.0 - (not_hits / len(must_not)) if must_not else 1.0
    scores["summary"] = contain_score * 0.7 + not_score * 0.3

    exports = {e.lower() for e in parsed.get("key_exports", [])}
    expected_exports = {e.lower() for e in gt.get("key_exports", set())}
    scores["exports"] = len(exports & expected_exports) / len(expected_exports) if expected_exports else 1.0

    scores["total"] = scores["role"] * 0.3 + scores["summary"] * 0.4 + scores["exports"] * 0.3
    return scores


def score_epistemic(parsed: Dict[str, Any], gt: Dict[str, Any]) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    layer = parsed.get("architecture_layer", "").lower()
    expected_layers = {l.lower() for l in gt.get("expected_layers", set())}
    scores["layer"] = 1.0 if layer in expected_layers else 0.0

    tags = {t.lower() for t in parsed.get("domain_tags", [])}
    expected_tags = {t.lower() for t in gt.get("domain_tags", set())}
    if expected_tags and tags:
        overlap = len(tags & expected_tags)
        partial = sum(0.5 for t in tags if any(t in et or et in t for et in expected_tags) and t not in expected_tags)
        scores["tags"] = min(1.0, (overlap + partial) / len(expected_tags))
    else:
        scores["tags"] = 0.0

    summary = parsed.get("extended_summary", "").lower()
    must_contain = gt.get("summary_must_contain", [])
    must_not = gt.get("summary_must_not_contain", [])
    contain_hits = sum(1 for w in must_contain if w.lower() in summary)
    contain_score = contain_hits / len(must_contain) if must_contain else 1.0
    not_hits = sum(1 for w in must_not if w.lower() in summary)
    not_score = 1.0 - (not_hits / len(must_not)) if must_not else 1.0
    scores["summary"] = contain_score * 0.7 + not_score * 0.3

    scores["total"] = scores["layer"] * 0.25 + scores["tags"] * 0.25 + scores["summary"] * 0.5
    return scores


# ── Load prior think results ─────────────────────────────────────────

def load_prior_think_epistemic() -> Dict[str, Dict[str, Any]]:
    """Load epistemic results from the LM Studio think-ON run."""
    if not PRIOR_THINK_RESULTS.exists():
        return {}
    with open(PRIOR_THINK_RESULTS) as f:
        data = json.load(f)
    results = {}
    for entry in data.get("raw", {}).get("qwen3.5-27b", {}).get("epistemic", []):
        fp = entry.get("file_path", "")
        if entry.get("json_parsed"):
            results[fp] = entry
    return results


# ── Main ──────────────────────────────────────────────────────────────

def run(max_files: Optional[int] = None):
    gt_files = []
    for rel_path in sorted(GROUND_TRUTH.keys()):
        full = REPO_PATH / rel_path
        if full.exists():
            gt_files.append((rel_path, full))
    if max_files:
        gt_files = gt_files[:max_files]

    prior_think = load_prior_think_epistemic()

    print(f"\n{'='*70}")
    print(f"  NO-THINK BENCHMARK: qwen3.5:27b via Ollama")
    print(f"  Files: {len(gt_files)} | Prior think results: {len(prior_think)}")
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
        print(f"    ⚡ augment", end="", flush=True)
        dt, text, toks, tps = ollama_chat(FILE_ROLE_SYSTEM, prompt)
        parsed = parse_json(text)
        aug_entry = {
            "file": rel_path, "wall_time": dt, "tokens": toks, "tps": tps,
            "parsed": parsed is not None, "raw": text[:200],
        }
        if parsed:
            scores = score_augment(parsed, gt)
            aug_entry.update({
                "confidence": parsed.get("confidence", 0),
                "summary": parsed.get("summary", ""),
                "role": parsed.get("role", ""),
                "exports": parsed.get("key_exports", []),
                "role_score": scores["role"],
                "summary_score": scores["summary"],
                "export_score": scores["exports"],
                "total_score": scores["total"],
            })
            print(f"  {dt:.1f}s  {toks}tok  {tps:.0f}t/s  score={scores['total']:.2f}  role={parsed.get('role','?')}")
        else:
            aug_entry["total_score"] = 0
            print(f"  {dt:.1f}s  {toks}tok  ✗ parse fail")
        aug_results.append(aug_entry)

        # Epistemic
        p1_summary = parsed.get("summary", "(unavailable)") if parsed else "(unavailable)"
        p1_role = parsed.get("role", "unknown") if parsed else "unknown"
        ep_prompt = EPISTEMIC_PROMPT.format(
            file_path=rel_path, pass1_summary=p1_summary,
            pass1_role=p1_role, source_excerpt=excerpt,
        )
        print(f"    ⚡ epist.", end="", flush=True)
        dt, text, toks, tps = ollama_chat(EPISTEMIC_SYSTEM, ep_prompt)
        parsed = parse_json(text)
        epi_entry = {
            "file": rel_path, "wall_time": dt, "tokens": toks, "tps": tps,
            "parsed": parsed is not None, "raw": text[:200],
        }
        if parsed:
            scores = score_epistemic(parsed, gt)
            epi_entry.update({
                "confidence": parsed.get("epistemic_confidence", 0),
                "summary": parsed.get("extended_summary", ""),
                "tags": parsed.get("domain_tags", []),
                "layer": parsed.get("architecture_layer", ""),
                "layer_score": scores["layer"],
                "tag_score": scores["tags"],
                "summary_score": scores["summary"],
                "total_score": scores["total"],
            })
            print(f"  {dt:.1f}s  {toks}tok  {tps:.0f}t/s  score={scores['total']:.2f}  layer={parsed.get('architecture_layer','?')}")
        else:
            epi_entry["total_score"] = 0
            print(f"  {dt:.1f}s  {toks}tok  ✗ parse fail")
        epi_results.append(epi_entry)

    # ── Report ────────────────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print(f"  NO-THINK RESULTS (qwen3.5:27b, Ollama)")
    print(f"{'='*70}\n")

    valid_aug = [r for r in aug_results if r["parsed"]]
    valid_epi = [r for r in epi_results if r["parsed"]]

    print(f"  AUGMENTATION")
    print(f"  {'─'*50}")
    print(f"  Parse rate:      {len(valid_aug)}/{len(aug_results)} ({len(valid_aug)/len(aug_results):.0%})")
    if valid_aug:
        print(f"  Avg quality:     {statistics.mean([r['total_score'] for r in valid_aug]):.2f}")
        print(f"  Avg confidence:  {statistics.mean([r['confidence'] for r in valid_aug]):.2f}")
        print(f"  Avg time:        {statistics.mean([r['wall_time'] for r in valid_aug]):.1f}s")
        print(f"  Avg tok/s:       {statistics.mean([r['tps'] for r in valid_aug]):.0f}")
        print(f"  Total time:      {sum(r['wall_time'] for r in aug_results):.0f}s")
        print(f"  Roles:           {[r['role'] for r in valid_aug]}")

    print(f"\n  EPISTEMIC")
    print(f"  {'─'*50}")
    print(f"  Parse rate:      {len(valid_epi)}/{len(epi_results)} ({len(valid_epi)/len(epi_results):.0%})")
    if valid_epi:
        print(f"  Avg quality:     {statistics.mean([r['total_score'] for r in valid_epi]):.2f}")
        print(f"  Avg confidence:  {statistics.mean([r['confidence'] for r in valid_epi]):.2f}")
        print(f"  Avg time:        {statistics.mean([r['wall_time'] for r in valid_epi]):.1f}s")
        print(f"  Avg tok/s:       {statistics.mean([r['tps'] for r in valid_epi]):.0f}")
        print(f"  Total time:      {sum(r['wall_time'] for r in epi_results):.0f}s")
        print(f"  Layers:          {[r['layer'] for r in valid_epi]}")

    # ── Compare with prior think results ──────────────────────────────
    if prior_think:
        print(f"\n\n{'='*70}")
        print(f"  THINK vs NO-THINK COMPARISON (Epistemic)")
        print(f"  Think: LM Studio qwen3.5-27b-mxfp8 | No-Think: Ollama qwen3.5:27b")
        print(f"{'='*70}\n")

        # Score the prior think results against same ground truth
        think_scored = []
        for rel_path, _ in gt_files:
            # Map rel_path to the file_path format used in prior results
            prior = prior_think.get(rel_path)
            if not prior:
                # Try alternate path formats
                for pk in prior_think:
                    if pk.endswith(rel_path) or rel_path.endswith(pk):
                        prior = prior_think[pk]
                        break
            if prior:
                gt = GROUND_TRUTH.get(rel_path, {})
                if gt:
                    scores = score_epistemic(prior, gt)
                    think_scored.append({
                        "file": rel_path,
                        "total_score": scores["total"],
                        "layer_score": scores["layer"],
                        "tag_score": scores["tags"],
                        "summary_score": scores["summary"],
                        "confidence": prior.get("confidence", prior.get("epistemic_confidence", 0)),
                        "wall_time": prior.get("wall_time_s", prior.get("wall_time", 0)),
                        "summary": prior.get("summary", prior.get("extended_summary", "")),
                        "layer": prior.get("architecture_layer", ""),
                        "tags": prior.get("domain_tags", []),
                    })

        if think_scored:
            print(f"  {'File':<24} {'Think':>7} {'NoThink':>7} {'T time':>7} {'NT time':>7}")
            print(f"  {'─'*60}")
            for i, (rel_path, _) in enumerate(gt_files):
                nt = next((r for r in valid_epi if r["file"] == rel_path), None)
                th = next((r for r in think_scored if r["file"] == rel_path), None)
                ts = f"{th['total_score']:.2f}" if th else "—"
                ns = f"{nt['total_score']:.2f}" if nt else "—"
                tt = f"{th['wall_time']:.0f}s" if th else "—"
                nt_t = f"{nt['wall_time']:.0f}s" if nt else "—"
                print(f"  {rel_path:<24} {ts:>7} {ns:>7} {tt:>7} {nt_t:>7}")

            t_scores = [r["total_score"] for r in think_scored]
            n_scores = [r["total_score"] for r in valid_epi]
            if t_scores and n_scores:
                # Only compare files present in both
                common_files = set(r["file"] for r in think_scored) & set(r["file"] for r in valid_epi)
                t_common = [r["total_score"] for r in think_scored if r["file"] in common_files]
                n_common = [r["total_score"] for r in valid_epi if r["file"] in common_files]
                if t_common and n_common:
                    t_avg = statistics.mean(t_common)
                    n_avg = statistics.mean(n_common)
                    print(f"\n  {'Metric':<25} {'Think':>10} {'No-Think':>10}")
                    print(f"  {'─'*50}")
                    print(f"  {'Avg quality (common)':<25} {t_avg:>10.2f} {n_avg:>10.2f}")
                    t_conf = statistics.mean([r["confidence"] for r in think_scored if r["file"] in common_files])
                    n_conf = statistics.mean([r["confidence"] for r in valid_epi if r["file"] in common_files])
                    print(f"  {'Avg confidence':<25} {t_conf:>10.2f} {n_conf:>10.2f}")
                    t_time = sum(r["wall_time"] for r in think_scored if r["file"] in common_files)
                    n_time = sum(r["wall_time"] for r in valid_epi if r["file"] in common_files)
                    speedup = t_time / n_time if n_time > 0 else 0
                    print(f"  {'Total time':<25} {t_time:>9.0f}s {n_time:>9.0f}s")
                    print(f"  {'Speedup':<25} {'':>10} {speedup:>9.0f}×")

    # Save
    outdir = PROJECT_ROOT / "results" / f"nothink_{int(time.time())}"
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "results.json", "w") as f:
        json.dump({"augment": aug_results, "epistemic": epi_results}, f, indent=2)
    print(f"\n  Saved to {outdir / 'results.json'}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--files", type=int, default=None)
    args = parser.parse_args()
    run(max_files=args.files)
