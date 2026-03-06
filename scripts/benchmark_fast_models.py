#!/usr/bin/env python3
"""Fast-model shootout: qwen3.5:35b-a3b vs qwen3.5:9b vs baselines.

All via Ollama with think=false. Compares against prior results for
qwen3-14b (LM Studio) and qwen3.5:27b (Ollama no-think).

Tests on 5 mini-redis-rust files with ground truth scoring.
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
OLLAMA_BASE = "http://127.0.0.1:11434"
REPO_NAME = "mini-redis-rust"
REPO_PATH = PROJECT_ROOT / "tests" / "eval" / "real_repos" / REPO_NAME

MODELS_TO_TEST = [
    ("qwen3.5:35b-a3b", "35b-a3b (MoE 3B active)"),
    ("qwen3.5:9b", "9b (dense)"),
    ("qwen3.5:4b", "4b (dense)"),
]

NOTHINK_RESULTS = PROJECT_ROOT / "results" / "nothink_1772736578" / "results.json"

# ── Ground Truth (5 key files) ────────────────────────────────────────

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
    "src/cmd/get.rs": {
        "expected_roles": {"handler", "api", "core", "business_logic", "command"},
        "summary_must_contain": ["get", "command", "key"],
        "summary_must_not_contain": ["set command", "subscribe"],
        "domain_tags": {"redis", "command", "get", "key-value"},
        "expected_layers": {"business_logic", "presentation"},
        "key_exports": {"Get"},
    },
    "src/frame.rs": {
        "expected_roles": {"model", "core", "data", "utility", "infrastructure"},
        "summary_must_contain": ["frame", "RESP", "protocol"],
        "summary_must_not_contain": ["database", "server start"],
        "domain_tags": {"protocol", "RESP", "frame", "parsing", "serialization", "redis"},
        "expected_layers": {"data", "infrastructure", "business_logic"},
        "key_exports": {"Frame"},
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

JSON response:"""

EPISTEMIC_SYSTEM = """You are an expert software architect performing deep analysis of a codebase.
You produce structured, accurate analysis grounded in the actual code and documentation.
You MUST respond with valid JSON only."""

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

JSON response:"""


# ── Ollama Client ─────────────────────────────────────────────────────

def ollama_chat(model: str, system: str, user: str) -> Tuple[float, str, int, float]:
    body = {
        "model": model,
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
    for pattern in [r"```(?:json)?\s*\n?(.*?)```", r"\{.*\}"]:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            candidate = m.group(1).strip() if "```" in pattern else m.group(0)
            try: return json.loads(candidate)
            except json.JSONDecodeError: continue
    try: return json.loads(text)
    except json.JSONDecodeError: return None


def extract_imports(c: str) -> List[str]:
    return re.findall(r"^(?:use |extern crate |mod ).*", c, re.MULTILINE)[:10]

def extract_symbols(c: str) -> List[str]:
    return re.findall(r"(?:pub\s+)?(?:fn|struct|enum|trait|impl|type|const|static)\s+(\w+)", c, re.MULTILINE)[:15]


def score_augment(p: Dict, gt: Dict) -> Dict[str, float]:
    s: Dict[str, float] = {}
    s["role"] = 1.0 if p.get("role", "").lower() in {r.lower() for r in gt.get("expected_roles", set())} else 0.0
    summary = p.get("summary", "").lower()
    mc, mn = gt.get("summary_must_contain", []), gt.get("summary_must_not_contain", [])
    cs = sum(1 for w in mc if w.lower() in summary) / len(mc) if mc else 1.0
    ns = 1.0 - (sum(1 for w in mn if w.lower() in summary) / len(mn)) if mn else 1.0
    s["summary"] = cs * 0.7 + ns * 0.3
    exports = {e.lower() for e in p.get("key_exports", [])}
    expected = {e.lower() for e in gt.get("key_exports", set())}
    s["exports"] = len(exports & expected) / len(expected) if expected else 1.0
    s["total"] = s["role"] * 0.3 + s["summary"] * 0.4 + s["exports"] * 0.3
    return s


def score_epistemic(p: Dict, gt: Dict) -> Dict[str, float]:
    s: Dict[str, float] = {}
    s["layer"] = 1.0 if p.get("architecture_layer", "").lower() in {l.lower() for l in gt.get("expected_layers", set())} else 0.0
    tags = {t.lower() for t in p.get("domain_tags", [])}
    etags = {t.lower() for t in gt.get("domain_tags", set())}
    if etags and tags:
        overlap = len(tags & etags)
        partial = sum(0.5 for t in tags if any(t in et or et in t for et in etags) and t not in etags)
        s["tags"] = min(1.0, (overlap + partial) / len(etags))
    else:
        s["tags"] = 0.0
    summary = p.get("extended_summary", "").lower()
    mc, mn = gt.get("summary_must_contain", []), gt.get("summary_must_not_contain", [])
    cs = sum(1 for w in mc if w.lower() in summary) / len(mc) if mc else 1.0
    ns = 1.0 - (sum(1 for w in mn if w.lower() in summary) / len(mn)) if mn else 1.0
    s["summary"] = cs * 0.7 + ns * 0.3
    s["total"] = s["layer"] * 0.25 + s["tags"] * 0.25 + s["summary"] * 0.5
    return s


# ── Main ──────────────────────────────────────────────────────────────

def run():
    gt_files = [(rp, REPO_PATH / rp) for rp in sorted(GROUND_TRUTH) if (REPO_PATH / rp).exists()]

    print(f"\n{'='*70}")
    print(f"  FAST MODEL SHOOTOUT (Ollama, think=false)")
    print(f"  Files: {len(gt_files)} | Models: {len(MODELS_TO_TEST)}")
    print(f"{'='*70}")

    all_results: Dict[str, Dict[str, List]] = {}

    for model_id, model_label in MODELS_TO_TEST:
        print(f"\n  ── {model_label} ({model_id}) ──\n")
        aug_results = []
        epi_results = []

        for rel_path, full_path in gt_files:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            imports = extract_imports(content)
            symbols = extract_symbols(content)
            head = "\n".join(content.splitlines()[:120])
            excerpt = "\n".join(content.splitlines()[:200])
            gt = GROUND_TRUTH[rel_path]

            # Augmentation
            prompt = FILE_ROLE_PROMPT.format(
                file_path=rel_path,
                symbol_names=", ".join(symbols) if symbols else "(none)",
                imports="; ".join(imports) if imports else "(none)",
                head=head,
            )
            print(f"    {rel_path:<24}", end="", flush=True)
            dt, text, toks, tps = ollama_chat(model_id, FILE_ROLE_SYSTEM, prompt)
            parsed = parse_json(text)
            ae = {"file": rel_path, "wall_time": dt, "tokens": toks, "tps": tps, "parsed": parsed is not None}
            if parsed:
                sc = score_augment(parsed, gt)
                ae.update({"total_score": sc["total"], "confidence": parsed.get("confidence", 0),
                           "summary": parsed.get("summary", ""), "role": parsed.get("role", ""),
                           "exports": parsed.get("key_exports", [])})
                print(f"  aug={sc['total']:.2f}", end="")
            else:
                ae["total_score"] = 0
                print(f"  aug=FAIL", end="")
            aug_results.append(ae)

            # Epistemic
            p1s = parsed.get("summary", "?") if parsed else "?"
            p1r = parsed.get("role", "?") if parsed else "?"
            ep = EPISTEMIC_PROMPT.format(file_path=rel_path, pass1_summary=p1s, pass1_role=p1r, source_excerpt=excerpt)
            dt2, text2, toks2, tps2 = ollama_chat(model_id, EPISTEMIC_SYSTEM, ep)
            parsed2 = parse_json(text2)
            ee = {"file": rel_path, "wall_time": dt2, "tokens": toks2, "tps": tps2, "parsed": parsed2 is not None}
            if parsed2:
                sc2 = score_epistemic(parsed2, gt)
                ee.update({"total_score": sc2["total"], "confidence": parsed2.get("epistemic_confidence", 0),
                           "summary": parsed2.get("extended_summary", ""), "layer": parsed2.get("architecture_layer", ""),
                           "tags": parsed2.get("domain_tags", [])})
                print(f"  epi={sc2['total']:.2f}", end="")
            else:
                ee["total_score"] = 0
                print(f"  epi=FAIL", end="")
            epi_results.append(ee)

            total_time = ae["wall_time"] + ee["wall_time"]
            total_toks = ae["tokens"] + ee["tokens"]
            avg_tps = (ae.get("tps", 0) + ee.get("tps", 0)) / 2
            print(f"  {total_time:.0f}s  {total_toks}tok  {avg_tps:.0f}t/s")

        all_results[model_label] = {"augment": aug_results, "epistemic": epi_results}

    # ── Load 27b no-think for comparison ──────────────────────────────
    nt27 = {"augment": {}, "epistemic": {}}
    if NOTHINK_RESULTS.exists():
        with open(NOTHINK_RESULTS) as f:
            nt = json.load(f)
        for r in nt["augment"]:
            if r["parsed"] and r["file"] in GROUND_TRUTH:
                nt27["augment"][r["file"]] = r
        for r in nt["epistemic"]:
            if r["parsed"] and r["file"] in GROUND_TRUTH:
                nt27["epistemic"][r["file"]] = r

    # ── Report ────────────────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print(f"  RESULTS COMPARISON")
    print(f"{'='*70}\n")

    # Add prior results as pseudo-entries
    model_labels = [ml for _, ml in MODELS_TO_TEST]
    model_labels.append("27b no-think (prior)")
    model_labels.append("14b think-on (prior)")

    # Build summary table
    print(f"  {'Model':<28} {'Aug Q':>6} {'Epi Q':>6} {'Aug Parse':>10} {'Epi Parse':>10} {'Aug t/f':>8} {'Epi t/f':>8} {'tok/s':>6}")
    print(f"  {'─'*90}")

    for _, ml in MODELS_TO_TEST:
        res = all_results[ml]
        va = [r for r in res["augment"] if r["parsed"]]
        ve = [r for r in res["epistemic"] if r["parsed"]]
        aq = f"{statistics.mean([r['total_score'] for r in va]):.2f}" if va else "—"
        eq = f"{statistics.mean([r['total_score'] for r in ve]):.2f}" if ve else "—"
        ap = f"{len(va)}/{len(res['augment'])}"
        ep = f"{len(ve)}/{len(res['epistemic'])}"
        at = f"{statistics.mean([r['wall_time'] for r in res['augment']]):.1f}s"
        et = f"{statistics.mean([r['wall_time'] for r in res['epistemic']]):.1f}s"
        tps_vals = [r['tps'] for r in res['augment'] + res['epistemic'] if r.get('tps', 0) > 0]
        avg_tps = f"{statistics.mean(tps_vals):.0f}" if tps_vals else "—"
        print(f"  {ml:<28} {aq:>6} {eq:>6} {ap:>10} {ep:>10} {at:>8} {et:>8} {avg_tps:>6}")

    # 27b no-think prior
    if nt27["augment"]:
        va27 = list(nt27["augment"].values())
        ve27 = list(nt27["epistemic"].values())
        aq = f"{statistics.mean([r['total_score'] for r in va27]):.2f}"
        eq = f"{statistics.mean([r['total_score'] for r in ve27]):.2f}" if ve27 else "—"
        at = f"{statistics.mean([r['wall_time'] for r in va27]):.1f}s"
        et = f"{statistics.mean([r['wall_time'] for r in ve27]):.1f}s" if ve27 else "—"
        print(f"  {'27b no-think (Ollama)':<28} {aq:>6} {eq:>6} {'10/10':>10} {'10/10':>10} {at:>8} {et:>8} {'11':>6}")

    # 14b prior (estimated from earlier benchmark)
    print(f"  {'14b think-on (LM Studio)':<28} {'~0.86':>6} {'~0.85':>6} {'9/10':>10} {'10/10':>10} {'18.2s':>8} {'8.2s':>8} {'23':>6}")

    # Per-file comparison
    print(f"\n  PER-FILE AUGMENTATION")
    header = f"  {'File':<24}"
    for _, ml in MODELS_TO_TEST:
        short = ml.split("(")[0].strip()
        header += f" {short:>10}"
    header += f" {'27b-NT':>10}"
    print(header)
    print(f"  {'─'*24 + '─' * 11 * (len(MODELS_TO_TEST) + 1)}")

    for fp in sorted(GROUND_TRUTH):
        line = f"  {fp:<24}"
        for _, ml in MODELS_TO_TEST:
            r = next((x for x in all_results[ml]["augment"] if x["file"] == fp), None)
            if r and r["parsed"]:
                line += f" {r['total_score']:>9.2f}"
            else:
                line += f" {'FAIL':>10}"
        nt_r = nt27["augment"].get(fp)
        line += f" {nt_r['total_score']:>9.2f}" if nt_r else f" {'—':>10}"
        print(line)

    print(f"\n  PER-FILE EPISTEMIC")
    header = f"  {'File':<24}"
    for _, ml in MODELS_TO_TEST:
        short = ml.split("(")[0].strip()
        header += f" {short:>10}"
    header += f" {'27b-NT':>10}"
    print(header)
    print(f"  {'─'*24 + '─' * 11 * (len(MODELS_TO_TEST) + 1)}")

    for fp in sorted(GROUND_TRUTH):
        line = f"  {fp:<24}"
        for _, ml in MODELS_TO_TEST:
            r = next((x for x in all_results[ml]["epistemic"] if x["file"] == fp), None)
            if r and r["parsed"]:
                line += f" {r['total_score']:>9.2f}"
            else:
                line += f" {'FAIL':>10}"
        nt_r = nt27["epistemic"].get(fp)
        line += f" {nt_r['total_score']:>9.2f}" if nt_r else f" {'—':>10}"
        print(line)

    # Save
    outdir = PROJECT_ROOT / "results" / f"fast_shootout_{int(time.time())}"
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Saved to {outdir / 'results.json'}")


if __name__ == "__main__":
    # Check models
    try:
        req = Request(f"{OLLAMA_BASE}/api/tags")
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        available = {m["name"] for m in data.get("models", [])}
        for model_id, label in MODELS_TO_TEST:
            if model_id in available:
                print(f"  ✓ {model_id}")
            else:
                print(f"  ✗ {model_id} — need to pull: ollama pull {model_id}")
    except URLError:
        print("ERROR: Ollama not running")
        sys.exit(1)

    run()
