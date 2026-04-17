use codrag_walker::{walk_repo, WalkConfig};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::env;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;
use std::time::SystemTime;

#[derive(Serialize)]
struct Report {
    repo_root: String,
    index_dir: String,
    scanned_at: String,
    disk_files: usize,
    checkpoints: HashMap<String, CheckpointStatus>,
    summary: SummaryConfig,
}

#[derive(Serialize)]
struct CheckpointStatus {
    covered: usize,
    missing: Vec<String>,
}

#[derive(Serialize)]
struct SummaryConfig {
    fully_healed: bool,
    worst_gap: String,
    worst_gap_pct: f64,
    rogue_files: usize,
}

#[derive(Deserialize, Default)]
struct RepoPolicy {
    include_globs: Option<Vec<String>>,
    exclude_globs: Option<Vec<String>>,
}

fn load_policy(index_dir: &Path) -> RepoPolicy {
    let policy_path = index_dir.join("repo_policy.json");
    if let Ok(file) = File::open(&policy_path) {
        if let Ok(policy) = serde_json::from_reader(file) {
            return policy;
        }
    }
    RepoPolicy::default()
}

fn parse_file_paths(index_dir: &Path, file_name: &str, extractor: impl Fn(&serde_json::Value) -> Vec<String>) -> HashSet<String> {
    let mut files = HashSet::new();
    let path = index_dir.join(file_name);
    
    if let Ok(file) = File::open(&path) {
        let reader = BufReader::new(file);
        for line in reader.lines().filter_map(|l| l.ok()) {
            if line.trim().is_empty() {
                continue;
            }
            if let Ok(val) = serde_json::from_str::<serde_json::Value>(&line) {
                for f in extractor(&val) {
                    files.insert(f);
                }
            }
        }
    }
    
    files
}

fn strip_file_prefix(val: &serde_json::Value, key: &str) -> Vec<String> {
    if let Some(id_val) = val.get(key).and_then(|v| v.as_str()) {
        if let Some(stripped) = id_val.strip_prefix("file:") {
            return vec![stripped.to_string()];
        }
    }
    vec![]
}

fn load_extra_excludes(path: &Path) -> Vec<String> {
    // L3 patterns sourced from `project.config.trace.ignore_patterns`.
    // Python resolves these per-request and writes them to a JSON array
    // file; pass the path via `--extra-excludes-file <path>`.
    match File::open(path) {
        Ok(file) => serde_json::from_reader(file).unwrap_or_default(),
        Err(_) => Vec::new(),
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        eprintln!("Usage: codrag-selfheal <repo_root> <index_dir> [--extra-excludes-file <path>]");
        std::process::exit(1);
    }

    let repo_root = Path::new(&args[1]);
    let index_dir = Path::new(&args[2]);

    // Optional L3 patterns (ignore_patterns from project.config.trace).
    let mut extra_excludes: Vec<String> = Vec::new();
    let mut i = 3;
    while i < args.len() {
        if args[i] == "--extra-excludes-file" && i + 1 < args.len() {
            extra_excludes = load_extra_excludes(Path::new(&args[i + 1]));
            i += 2;
        } else {
            eprintln!("Unknown argument: {}", args[i]);
            std::process::exit(1);
        }
    }

    // Load config: L1 (walker defaults) ∪ L2 (repo_policy.json) ∪ L3 (extra_excludes).
    let mut walk_config = WalkConfig::default();
    let policy = load_policy(index_dir);
    if let Some(includes) = policy.include_globs {
        if !includes.is_empty() {
            walk_config.include_globs = includes;
        }
    }
    if let Some(mut excludes) = policy.exclude_globs {
        // Always combine with base exclusions if we override
        let mut default_excludes = WalkConfig::default().exclude_globs;
        default_excludes.append(&mut excludes);
        walk_config.exclude_globs = default_excludes;
    }
    // L3: append any runtime ignore_patterns from the project config.
    if !extra_excludes.is_empty() {
        walk_config.exclude_globs.extend(extra_excludes);
    }
    
    // Scan disk
    let disk_entries = walk_repo(repo_root, &walk_config).unwrap_or_else(|e| {
        eprintln!("Failed to walk repository: {}", e);
        std::process::exit(1);
    });
    
    let disk_files: HashSet<String> = disk_entries.into_iter().map(|e| e.path).collect();
    
    // Stage 1: trace_nodes.jsonl
    let traced = parse_file_paths(index_dir, "trace_nodes.jsonl", |val| {
        if let Some(kind) = val.get("kind").and_then(|k| k.as_str()) {
            if kind == "file" {
                if let Some(path) = val.get("file_path").and_then(|p| p.as_str()) {
                    return vec![path.to_string()];
                }
            }
        }
        vec![]
    });
    
    // Stage 3: trace_augmented.jsonl
    let augmented = parse_file_paths(index_dir, "trace_augmented.jsonl", |val| strip_file_prefix(val, "node_id"));
    
    // Stage 6/10: trace_epistemic.jsonl
    let enriched = parse_file_paths(index_dir, "trace_epistemic.jsonl", |val| strip_file_prefix(val, "node_id"));
    
    // Stage 8: trace_modules.jsonl
    let clustered = parse_file_paths(index_dir, "trace_modules.jsonl", |val| {
        let mut paths = Vec::new();
        if let Some(members) = val.get("member_files").and_then(|m| m.as_array()) {
            for m in members {
                if let Some(m_str) = m.as_str() {
                    if let Some(stripped) = m_str.strip_prefix("file:") {
                        paths.push(stripped.to_string());
                    } else {
                        paths.push(m_str.to_string());
                    }
                }
            }
        }
        paths
    });
    
    let process_checkpoint = |pipeline_files: &HashSet<String>| {
        let mut missing: Vec<String> = disk_files.difference(pipeline_files).cloned().collect();
        missing.sort();
        let covered = disk_files.len().saturating_sub(missing.len());
        CheckpointStatus { covered, missing }
    };
    
    let traced_status = process_checkpoint(&traced);
    let augmented_status = process_checkpoint(&augmented);
    let enriched_status = process_checkpoint(&enriched);
    let clustered_status = process_checkpoint(&clustered);
    
    let mut checkpoints = HashMap::new();
    checkpoints.insert("traced".to_string(), traced_status);
    checkpoints.insert("augmented".to_string(), augmented_status);
    checkpoints.insert("enriched".to_string(), enriched_status);
    checkpoints.insert("clustered".to_string(), clustered_status);
    
    let mut worst_gap = String::from("traced");
    let mut worst_gap_missing = checkpoints["traced"].missing.len();
    
    for (name, status) in &checkpoints {
        if status.missing.len() > worst_gap_missing {
            worst_gap = name.clone();
            worst_gap_missing = status.missing.len();
        }
    }
    
    let total = disk_files.len() as f64;
    let mut worst_gap_pct = 100.0;
    if total > 0.0 {
        worst_gap_pct = ((total - worst_gap_missing as f64) / total) * 100.0;
    }
    
    let report = Report {
        repo_root: repo_root.to_string_lossy().to_string(),
        index_dir: index_dir.to_string_lossy().to_string(),
        scanned_at: format!("{:?}", SystemTime::now()),
        disk_files: disk_files.len(),
        checkpoints,
        summary: SummaryConfig {
            fully_healed: worst_gap_missing == 0,
            worst_gap,
            worst_gap_pct,
            rogue_files: worst_gap_missing,
        },
    };
    
    let json = serde_json::to_string_pretty(&report).unwrap_or_else(|_| "{}".to_string());
    println!("{}", json);
}
