#!/bin/bash
# Phase 40 Quick Smoke Test (~10-15 min)
# Tests 2 small models on 1 tiny repo with concurrency 1 and 2
# Validates: imports work, pipeline runs, think tags stripped, JSON parsed
#
# Usage: bash scripts/benchmark_quick.sh

set -e
cd "$(dirname "$0")/.."

PYTHON=".venv/bin/python3"
if [ ! -f "$PYTHON" ]; then
    PYTHON=".venv_build/bin/python3"
fi
if [ ! -f "$PYTHON" ]; then
    PYTHON="python3"
fi

REPO="tests/eval/real_repos/mini-redis-rust"
OUT_DIR="results/quick_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT_DIR"

echo "============================================================"
echo "Phase 40 Quick Smoke Test"
echo "Python: $PYTHON"
echo "Repo:   $REPO"
echo "Output: $OUT_DIR"
echo "============================================================"
echo ""

# Track failures
FAILURES=0
TESTS=0

run_test() {
    local label="$1"
    local model="$2"
    local conc="$3"
    local outfile="$4"
    TESTS=$((TESTS + 1))
    
    echo "[$TESTS] $label (model=$model, c=$conc)"
    
    if $PYTHON scripts/benchmark_concurrency.py \
        --model "$model" \
        --concurrency "$conc" \
        --repo-path "$REPO" \
        --output "$outfile" \
        --stages fast 2>&1 | tail -5; then
        
        if [ -f "$outfile" ]; then
            STATUS=$($PYTHON -c "import json; d=json.load(open('$outfile')); print(d.get('status','?'))")
            DURATION=$($PYTHON -c "import json; d=json.load(open('$outfile')); print(d.get('total_duration_s', 0))")
            echo "  → Status: $STATUS  Duration: ${DURATION}s"
            if [ "$STATUS" != "completed" ]; then
                echo "  ✗ FAILED"
                FAILURES=$((FAILURES + 1))
            else
                echo "  ✓ PASSED"
            fi
        else
            echo "  ✗ FAILED (no output file)"
            FAILURES=$((FAILURES + 1))
        fi
    else
        echo "  ✗ FAILED (script error)"
        FAILURES=$((FAILURES + 1))
    fi
    echo ""
}

# Clean the test repo's index first
echo "Cleaning test repo index..."
rm -f "$REPO/.codrag/trace_augmented.jsonl" \
      "$REPO/.codrag/trace_augmented_manifest.json" \
      "$REPO/.codrag/trace_epistemic.jsonl" \
      "$REPO/.codrag/trace_inferred_edges.jsonl" \
      "$REPO/.codrag/trace_inferred_manifest.json" \
      "$REPO/.codrag/trace_modules.jsonl" 2>/dev/null || true
echo ""

# Test 1: qwen3:4b-instruct, concurrency=1 (baseline)
run_test "Fast model, sequential" "qwen3:4b-instruct" 1 "$OUT_DIR/fast_c1.json"

# Clean between runs
rm -f "$REPO/.codrag/trace_augmented.jsonl" \
      "$REPO/.codrag/trace_augmented_manifest.json" \
      "$REPO/.codrag/trace_inferred_edges.jsonl" \
      "$REPO/.codrag/trace_inferred_manifest.json" 2>/dev/null || true

# Test 2: qwen3:4b-instruct, concurrency=2
run_test "Fast model, concurrent" "qwen3:4b-instruct" 2 "$OUT_DIR/fast_c2.json"

# Clean between runs
rm -f "$REPO/.codrag/trace_augmented.jsonl" \
      "$REPO/.codrag/trace_augmented_manifest.json" \
      "$REPO/.codrag/trace_inferred_edges.jsonl" \
      "$REPO/.codrag/trace_inferred_manifest.json" 2>/dev/null || true

# Test 3: qwen3:8b, concurrency=1
run_test "Standard model, sequential" "qwen3:8b" 1 "$OUT_DIR/std_c1.json"

# Clean between runs
rm -f "$REPO/.codrag/trace_augmented.jsonl" \
      "$REPO/.codrag/trace_augmented_manifest.json" \
      "$REPO/.codrag/trace_inferred_edges.jsonl" \
      "$REPO/.codrag/trace_inferred_manifest.json" 2>/dev/null || true

# Test 4: qwen3:8b, concurrency=2
run_test "Standard model, concurrent" "qwen3:8b" 2 "$OUT_DIR/std_c2.json"

# Summary
echo "============================================================"
echo "RESULTS: $((TESTS - FAILURES))/$TESTS passed"
if [ $FAILURES -gt 0 ]; then
    echo "STATUS: SOME FAILURES"
else
    echo "STATUS: ALL PASSED"
fi

# Show speedup if both runs completed
if [ -f "$OUT_DIR/fast_c1.json" ] && [ -f "$OUT_DIR/fast_c2.json" ]; then
    $PYTHON -c "
import json
c1 = json.load(open('$OUT_DIR/fast_c1.json'))
c2 = json.load(open('$OUT_DIR/fast_c2.json'))
t1 = c1.get('total_duration_s', 0)
t2 = c2.get('total_duration_s', 0)
if t1 > 0 and t2 > 0:
    print(f'  qwen3:4b-instruct: c1={t1:.1f}s  c2={t2:.1f}s  speedup={t1/t2:.2f}x')
" 2>/dev/null || true
fi

if [ -f "$OUT_DIR/std_c1.json" ] && [ -f "$OUT_DIR/std_c2.json" ]; then
    $PYTHON -c "
import json
c1 = json.load(open('$OUT_DIR/std_c1.json'))
c2 = json.load(open('$OUT_DIR/std_c2.json'))
t1 = c1.get('total_duration_s', 0)
t2 = c2.get('total_duration_s', 0)
if t1 > 0 and t2 > 0:
    print(f'  qwen3:8b: c1={t1:.1f}s  c2={t2:.1f}s  speedup={t1/t2:.2f}x')
" 2>/dev/null || true
fi

echo "Output: $OUT_DIR"
echo "============================================================"

exit $FAILURES
