import json
import statistics
from pathlib import Path
from collections import Counter, defaultdict
import sys

def load_jsonl(path):
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return [json.loads(line) for line in f]

def load_json(path):
    if not path.exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_augmentation(base_dir):
    print(f"\n--- Augmentation Analysis ({base_dir}) ---")
    aug_path = base_dir / "trace_augmented.jsonl"
    entries = load_jsonl(aug_path)
    
    if not entries:
        print("No augmentation data found.")
        return

    total = len(entries)
    confidences = [e.get('confidence', 0) for e in entries]
    roles = [e.get('role', 'unknown') for e in entries]
    models = [e.get('model', 'unknown') for e in entries]
    summaries = [e.get('summary', '') for e in entries]
    
    synthetic_reasons = [str(m).split(':')[1] if ':' in str(m) else 'unknown' for m in models if str(m).startswith('synthetic')]
    synthetic_count = len(synthetic_reasons)
    
    print(f"Total entries: {total}")
    print(f"Synthetic entries: {synthetic_count} ({synthetic_count/total:.1%})")
    if synthetic_reasons:
        print("  Reasons:")
        for r, c in Counter(synthetic_reasons).most_common():
            print(f"    - {r}: {c}")
    
    if confidences:
        print(f"Confidence: Avg={statistics.mean(confidences):.2f}, Median={statistics.median(confidences):.2f}")
    
    print("Top Roles:")
    for role, count in Counter(roles).most_common(5):
        print(f"  - {role}: {count}")

    avg_summary_len = statistics.mean(len(s) for s in summaries) if summaries else 0
    print(f"Avg Summary Length: {avg_summary_len:.0f} chars")

# Inline scoring logic to avoid imports
SCORE_WEIGHTS = {
    "summary_confidence": 0.20,
    "validation_status": 0.15,
    "neighbor_coverage": 0.20,
    "cross_reference_density": 0.15,
    "enrichment_depth": 0.15,
    "staleness_check": 0.15,
}

def compute_composite_score_inline(node_id, augmentation, epistemic_entry, neighbor_ids, enriched_ids, cross_ref_count, current_hashes):
    # 1. Summary confidence
    c1 = float(augmentation.get("confidence", 0.0)) if augmentation else 0.0

    # 2. Validation status
    # Presence of epistemic entry (Pass 2+) counts as validation by 14b model
    if epistemic_entry:
        c2 = 1.0
    elif augmentation and augmentation.get("validated"):
        validated_by = augmentation.get("validated_by", "")
        c2 = 1.0 if "14b" in str(validated_by) else 0.6
    else:
        c2 = 0.0

    # 3. Neighbor coverage
    if not neighbor_ids:
        c3 = 0.5
    else:
        enriched = sum(1 for n in neighbor_ids if n in enriched_ids)
        c3 = enriched / len(neighbor_ids)

    # 4. Cross-reference density (sigmoid-like: saturates at 4)
    c4 = min(1.0, cross_ref_count / 4.0)

    # 5. Enrichment depth
    pass_num = epistemic_entry.get("pass_number", 2) if epistemic_entry else 0
    if not epistemic_entry:
        c5 = 0.0
    elif pass_num >= 4:
        c5 = 1.0
    elif pass_num >= 3:
        c5 = 0.75
    else:
        c5 = 0.5  # Pass 2

    # 6. Staleness check
    file_path = node_id.replace("file:", "", 1) if node_id.startswith("file:") else ""
    aug_hash = augmentation.get("file_hash") if augmentation else None
    current_hash = current_hashes.get(file_path)
    if aug_hash and current_hash:
        c6 = 1.0 if aug_hash == current_hash else 0.0
    else:
        c6 = 0.3  # unknown

    # Weighted sum
    composite = (
        SCORE_WEIGHTS["summary_confidence"] * c1
        + SCORE_WEIGHTS["validation_status"] * c2
        + SCORE_WEIGHTS["neighbor_coverage"] * c3
        + SCORE_WEIGHTS["cross_reference_density"] * c4
        + SCORE_WEIGHTS["enrichment_depth"] * c5
        + SCORE_WEIGHTS["staleness_check"] * c6
    )
    return round(composite, 3)

def analyze_epistemic(base_dir):
    print(f"\n--- Epistemic Analysis ({base_dir}) ---")
    epi_path = base_dir / "trace_epistemic.jsonl"
    aug_path = base_dir / "trace_augmented.jsonl"
    edge_path = base_dir / "trace_edges.jsonl"
    manifest_path = base_dir / "trace_manifest.json"
    
    entries = load_jsonl(epi_path)
    if not entries:
        print("No epistemic data found.")
        return

    # Load necessary data for scoring
    augmentations = {d['node_id']: d for d in load_jsonl(aug_path)}
    epistemic_map = {d['node_id']: d for d in entries}
    edges = load_jsonl(edge_path)
    manifest = load_json(manifest_path)
    current_hashes = manifest.get('file_hashes', {})
    
    # Build graph info
    adjacency = defaultdict(set)
    cross_refs = defaultdict(int)
    for e in edges:
        src, tgt = e.get("source"), e.get("target")
        if src and tgt:
            adjacency[src].add(tgt)
            adjacency[tgt].add(src)
        if e.get("kind") in ("references", "links_to"):
            cross_refs[src] += 1
            
    enriched_ids = set(epistemic_map.keys())
    
    # Compute scores
    scores = []
    for nid, entry in epistemic_map.items():
        score = compute_composite_score_inline(
            nid, 
            augmentations.get(nid), 
            entry, 
            adjacency.get(nid, set()), 
            enriched_ids, 
            cross_refs.get(nid, 0), 
            current_hashes
        )
        scores.append(score)

    total = len(entries)
    print(f"Total Enriched Nodes: {total}")
    
    if scores:
        print(f"\nComposite Scores (Projected):")
        print(f"  Mean: {statistics.mean(scores):.3f}")
        print(f"  Median: {statistics.median(scores):.3f}")
        settled = sum(1 for s in scores if s >= 0.60)
        print(f"  Settled (>= 0.60): {settled} ({settled/total:.1%})")
        print(f"  Score Weights: {SCORE_WEIGHTS}")

    layers = [e.get('architecture_layer', 'unknown') for e in entries]
    tech_debt = [e.get('tech_debt', []) for e in entries]
    patterns = [e.get('design_patterns', []) for e in entries]
    staleness = [e.get('staleness_risk', 'unknown') for e in entries]
    
    print(f"Total enriched: {total}")
    
    print("Architecture Layers:")
    for layer, count in Counter(layers).most_common(5):
        print(f"  - {layer}: {count}")
    
    # Filter out empty or "None" debt
    valid_debt_lists = []
    for t in tech_debt:
        if not t: continue
        # Filter items in the list
        items = [i for i in t if i and str(i).lower() != "none"]
        if items:
            valid_debt_lists.append(items)

    nodes_with_debt = len(valid_debt_lists)
    print(f"Nodes with Tech Debt: {nodes_with_debt} ({nodes_with_debt/total:.1%})")
    
    if valid_debt_lists:
        print("  Sample Tech Debt:")
        all_debt = []
        for sublist in valid_debt_lists:
            for item in sublist:
                if isinstance(item, dict):
                    # Try to extract a meaningful string or just dump it
                    all_debt.append(item.get('description', str(item)))
                else:
                    all_debt.append(str(item))
        
        for debt, count in Counter(all_debt).most_common(5):
            print(f"    - {debt}: {count}")
    
    nodes_with_patterns = sum(1 for p in patterns if p)
    print(f"Nodes with Patterns: {nodes_with_patterns} ({nodes_with_patterns/total:.1%})")
    
    print("Staleness Risk:")
    for risk, count in Counter(staleness).most_common(5):
        print(f"  - {risk}: {count}")

def analyze_clustering(base_dir):
    print(f"\n--- Clustering Analysis ({base_dir}) ---")
    mod_path = base_dir / "trace_modules.jsonl"
    entries = load_jsonl(mod_path)
    
    if not entries:
        print("No module data found.")
        return

    print(f"Total Modules: {len(entries)}")
    for mod in entries:
        members = mod.get('member_files', [])
        print(f"  - {mod.get('name')} ({mod.get('architecture_layer')}): {len(members)} files")

def analyze_knowledge(base_dir):
    print(f"\n--- Knowledge Analysis ({base_dir}) ---")
    know_path = base_dir / "knowledge_documents.json"
    docs = load_json(know_path)
    
    if not docs:
        print("No knowledge documents found.")
        return
        
    if isinstance(docs, dict):
        docs = list(docs.values())
        
    print(f"Total Chunks: {len(docs)}")
    
    content_lens = [len(d.get('content', '')) for d in docs]
    if content_lens:
        print(f"Chunk Size: Avg={statistics.mean(content_lens):.0f} chars, Max={max(content_lens)}")
        
    sources = Counter(d.get('source_id', '').split(':')[0] for d in docs)
    print("Chunk Source Types:")
    for stype, count in sources.most_common():
        print(f"  - {stype}: {count}")

if __name__ == "__main__":
    dirs = ["TEST/.codrag", "TEST2/.codrag"]
    if len(sys.argv) > 1:
        dirs = sys.argv[1:]
        
    for d in dirs:
        path = Path(d)
        if not path.exists():
            print(f"Path not found: {path}")
            continue
            
        print(f"\n{'='*40}")
        print(f"ANALYZING: {path}")
        print(f"{'='*40}")
        
        analyze_augmentation(path)
        analyze_epistemic(path)
        analyze_clustering(path)
        analyze_knowledge(path)
