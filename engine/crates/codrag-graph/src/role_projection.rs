//! Role Projection Engine for CoDRAG (Phase 64D).
//!
//! Ports the scoring hot path from Python to Rust. Scores every indexed file
//! against a `RoleVector` using:
//!   - Architecture layer matching
//!   - Domain tag affinity (fuzzy + synonym cluster matching)
//!   - Audience bonus (TAG_TO_AUDIENCE lookup)
//!   - Graph centrality (normalized in-degree)
//!   - Epistemic confidence
//!
//! All data is read from existing pipeline outputs (trace_epistemic.jsonl,
//! trace_edges.jsonl). Zero LLM calls.
//!
//! Performance target: <5ms for 1K files (vs ~200ms in Python).

use std::collections::HashMap;
use std::io::BufRead;
use std::path::Path;

use rustc_hash::FxHashMap;
use serde::{Deserialize, Serialize};

// ── Synonym clusters for fuzzy domain-tag matching ─────────────────────

/// Pre-computed synonym cluster index.
/// Maps lowercased tag → cluster index for O(1) synonym lookups.
fn build_synonym_index() -> FxHashMap<&'static str, u8> {
    let clusters: &[&[&str]] = &[
        &["ui", "presentation", "frontend", "component", "view", "layout", "widget"],
        &["api", "endpoint", "route", "handler", "controller", "rest", "graphql"],
        &["auth", "authentication", "authorization", "permission", "security", "token", "credential"],
        &["data", "database", "persistence", "storage", "model", "schema", "orm", "migration"],
        &["deploy", "infrastructure", "devops", "ci-cd", "docker", "kubernetes", "helm", "terraform"],
        &["test", "testing", "spec", "qa", "quality", "coverage", "e2e"],
        &["build", "compile", "bundle", "webpack", "vite", "toolchain", "packaging"],
        &["docs", "documentation", "readme", "guide", "reference", "wiki"],
        &["state", "state-management", "store", "context", "redux", "zustand"],
        &["style", "css", "theme", "design-system", "design-token", "styling", "sass"],
        &["monitoring", "observability", "logging", "metrics", "tracing", "telemetry"],
        &["ml", "machine-learning", "ai", "model-training", "inference", "embedding"],
    ];

    let mut map = FxHashMap::default();
    for (idx, cluster) in clusters.iter().enumerate() {
        for &tag in *cluster {
            map.insert(tag, idx as u8);
        }
    }
    map
}

// ── TAG_TO_AUDIENCE heuristic mapping ──────────────────────────────────

/// Maps domain_tag → list of role_ids that "own" files with that tag.
/// Provides a scoring bonus when a file's tags indicate it belongs to the
/// requesting role's domain.
fn build_tag_to_audience() -> FxHashMap<&'static str, &'static [&'static str]> {
    let mut map = FxHashMap::default();
    // Frontend / Design
    map.insert("ui", &["design", "full_stack", "intern"][..]);
    map.insert("frontend", &["design", "full_stack"][..]);
    map.insert("react", &["full_stack", "design"][..]);
    map.insert("vue", &["full_stack", "design"][..]);
    map.insert("svelte", &["full_stack", "design"][..]);
    map.insert("styling", &["design"][..]);
    map.insert("component", &["design", "full_stack"][..]);
    map.insert("design-system", &["design"][..]);
    map.insert("a11y", &["design", "qa"][..]);
    map.insert("animation", &["design"][..]);
    // Backend / Engineering
    map.insert("backend", &["engineering"][..]);
    map.insert("core", &["engineering", "architect"][..]);
    map.insert("engine", &["engineering", "architect"][..]);
    map.insert("python", &["engineering"][..]);
    map.insert("typescript", &["engineering", "full_stack"][..]);
    map.insert("systems", &["engineering", "devops"][..]);
    // API
    map.insert("api", &["engineering", "full_stack", "architect"][..]);
    map.insert("graphql", &["engineering", "full_stack"][..]);
    map.insert("grpc", &["engineering", "devops"][..]);
    map.insert("rest", &["engineering", "full_stack"][..]);
    // Data
    map.insert("database", &["data_engineer", "engineering"][..]);
    map.insert("data", &["data_engineer"][..]);
    map.insert("orm", &["data_engineer", "engineering"][..]);
    map.insert("query", &["data_engineer"][..]);
    map.insert("data-persistence", &["data_engineer", "engineering"][..]);
    map.insert("schema", &["data_engineer", "engineering"][..]);
    map.insert("analytics", &["data_engineer", "product"][..]);
    // Security / Auth
    map.insert("auth", &["security", "engineering"][..]);
    map.insert("security", &["security"][..]);
    map.insert("token", &["security", "engineering"][..]);
    map.insert("permission", &["security"][..]);
    map.insert("encryption", &["security"][..]);
    map.insert("compliance", &["security", "ceo"][..]);
    // DevOps / Infra
    map.insert("infrastructure", &["devops"][..]);
    map.insert("deploy", &["devops"][..]);
    map.insert("docker", &["devops"][..]);
    map.insert("ci-cd", &["devops"][..]);
    map.insert("terraform", &["devops"][..]);
    map.insert("config", &["devops", "engineering"][..]);
    map.insert("monitoring", &["devops", "qa"][..]);
    map.insert("pipeline", &["devops", "data_engineer"][..]);
    // Testing / QA
    map.insert("test", &["qa", "engineering"][..]);
    map.insert("testing", &["qa"][..]);
    map.insert("coverage", &["qa"][..]);
    map.insert("e2e", &["qa"][..]);
    // Product / Business
    map.insert("monetization", &["product", "ceo"][..]);
    map.insert("billing", &["product", "ceo"][..]);
    map.insert("user-facing", &["product", "design"][..]);
    map.insert("onboarding", &["product", "intern"][..]);
    map.insert("feature-flag", &["product", "engineering"][..]);
    // Documentation / Writing
    map.insert("documentation", &["writer", "intern"][..]);
    map.insert("readme", &["writer", "intern"][..]);
    map.insert("guide", &["writer", "intern"][..]);
    // Architecture
    map.insert("architecture", &["architect", "cto", "ceo"][..]);
    map.insert("integration", &["architect", "engineering"][..]);
    map.insert("strategy", &["cto", "ceo", "product"][..]);
    // CLI / Tooling
    map.insert("cli", &["engineering", "devops"][..]);
    map.insert("tooling", &["engineering", "devops"][..]);
    map
}

// ── Scoring weights ────────────────────────────────────────────────────

const WEIGHT_LAYER_MATCH: f32 = 0.25;
const WEIGHT_TAG_AFFINITY: f32 = 0.30;
const WEIGHT_AUDIENCE_BONUS: f32 = 0.10;
const WEIGHT_CENTRALITY: f32 = 0.20;
const WEIGHT_CONFIDENCE: f32 = 0.15;

// ── Data types ─────────────────────────────────────────────────────────

/// Epistemic annotation loaded from trace_epistemic.jsonl.
#[derive(Debug, Clone, Deserialize)]
pub struct EpistemicAnnotation {
    pub node_id: String,
    #[serde(default)]
    pub file_path: String,
    #[serde(default)]
    pub architecture_layer: String,
    #[serde(default)]
    pub domain_tags: Vec<String>,
    #[serde(default = "default_confidence")]
    pub epistemic_confidence: f32,
    #[serde(default)]
    pub extended_summary: String,
}

fn default_confidence() -> f32 {
    0.5
}

/// Role vector deserialized from Python-side JSON.
/// Mirrors the Python `RoleVector` dataclass.
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct RoleVector {
    pub role_id: String,
    #[serde(default)]
    pub display_name: String,
    #[serde(default)]
    pub layer_weights: HashMap<String, f32>,
    #[serde(default)]
    pub domain_affinity: Vec<String>,
    #[serde(default = "default_centrality")]
    pub centrality_weight: f32,
    #[serde(default = "default_detail")]
    pub detail_level: f32,
    #[serde(default = "default_max_chars")]
    pub max_chars: usize,
}

fn default_centrality() -> f32 {
    0.5
}
fn default_detail() -> f32 {
    0.7
}
fn default_max_chars() -> usize {
    3000
}

/// A scored file result returned to Python.
#[derive(Debug, Clone)]
pub struct ScoredFile {
    pub file_path: String,
    pub score: f32,
    pub architecture_layer: String,
    pub domain_tags: Vec<String>,
    pub epistemic_confidence: f32,
    pub extended_summary: String,
}

// ── Path-based heuristic tables (structural fallback) ──────────────────

/// Infer architecture_layer from file path when epistemic data is absent.
fn infer_layer_from_path(file_path: &str) -> &'static str {
    let lower = file_path.to_lowercase();
    let lower = lower.replace('\\', "/");
    let parts: Vec<&str> = lower.split('/').collect();
    // Exclude filename — only look at directory segments
    let dir_segments: Vec<&str> = if parts.len() > 1 {
        parts[..parts.len() - 1].to_vec()
    } else {
        Vec::new()
    };

    // Order matters: test dirs first to avoid false positives
    let rules: &[(&[&str], &str)] = &[
        (&["test", "tests", "spec", "fixture", "__test__", "__tests__", "e2e"], "testing"),
        (&["api", "routes", "endpoint", "handler", "views", "controller"], "presentation"),
        (&["ui", "component", "page", "layout", "widget", "screen"], "presentation"),
        (&["core", "engine", "service", "logic", "domain", "usecase"], "business_logic"),
        (&["db", "model", "schema", "migration", "orm", "repository"], "data_access"),
        (&["auth", "security", "permission", "rbac", "crypto", "token"], "security"),
        (&["deploy", "docker", "k8s", "infra", "ci", "terraform", "helm"], "infrastructure"),
        (&["config", "settings", "env", "dotenv"], "configuration"),
        (&["util", "helper", "lib", "shared", "common"], "utility"),
        (&["cli", "cmd", "command"], "presentation"),
        (&["plugin", "extension", "addon", "middleware"], "integration"),
        (&["doc", "docs", "readme", "guide"], "documentation"),
    ];

    for (keywords, layer) in rules {
        for kw in *keywords {
            if dir_segments.iter().any(|s| s == kw) {
                return layer;
            }
        }
    }
    "unknown"
}

/// Infer domain_tags from file path and extension.
fn infer_tags_from_path(file_path: &str) -> Vec<String> {
    let lower = file_path.to_lowercase();
    let mut tags: Vec<String> = Vec::new();

    // Extension-based tags (longer suffixes first for .test.py etc.)
    let ext_rules: &[(&str, &[&str])] = &[
        (".test.py", &["test", "backend"]),
        (".test.ts", &["test", "frontend"]),
        (".test.tsx", &["test", "frontend"]),
        (".spec.ts", &["test", "frontend"]),
        (".spec.tsx", &["test", "frontend"]),
        (".tsx", &["ui", "frontend", "react"]),
        (".jsx", &["ui", "frontend", "react"]),
        (".vue", &["ui", "frontend", "vue"]),
        (".svelte", &["ui", "frontend", "svelte"]),
        (".css", &["ui", "styling"]),
        (".scss", &["ui", "styling"]),
        (".html", &["ui", "frontend"]),
        (".py", &["backend", "python"]),
        (".rs", &["backend", "systems"]),
        (".go", &["backend", "go"]),
        (".java", &["backend", "java"]),
        (".kt", &["backend", "kotlin"]),
        (".rb", &["backend", "ruby"]),
        (".ts", &["backend", "typescript"]),
        (".js", &["backend", "javascript"]),
        (".sql", &["database", "query"]),
        (".prisma", &["database", "orm"]),
        (".proto", &["api", "grpc"]),
        (".graphql", &["api", "graphql"]),
        (".yaml", &["config", "infrastructure"]),
        (".yml", &["config", "infrastructure"]),
        (".toml", &["config"]),
        (".json", &["config", "data"]),
        (".tf", &["infrastructure", "terraform"]),
        (".dockerfile", &["infrastructure", "docker"]),
        (".md", &["documentation"]),
    ];

    for (ext, ext_tags) in ext_rules {
        if lower.ends_with(ext) {
            for t in *ext_tags {
                tags.push(t.to_string());
            }
            break;
        }
    }

    // Path-keyword tags
    let path_keywords: &[(&str, &str)] = &[
        ("api", "api"), ("rest", "api"), ("graphql", "graphql"),
        ("auth", "auth"), ("security", "security"),
        ("test", "test"), ("tests", "test"), ("__tests__", "test"),
        ("deploy", "deploy"), ("infra", "infrastructure"),
        ("docker", "docker"), ("ci", "ci-cd"),
        ("config", "config"), ("settings", "config"),
        ("ui", "ui"), ("frontend", "frontend"), ("components", "ui"),
        ("core", "core"), ("engine", "engine"),
        ("db", "database"), ("models", "database"),
        ("migration", "database"), ("seed", "database"),
        ("docs", "documentation"), ("scripts", "tooling"),
        ("cli", "cli"),
    ];

    let lower_slash = lower.replace('\\', "/");
    let parts: Vec<&str> = lower_slash.split('/').collect();
    for part in &parts {
        for (kw, tag) in path_keywords {
            if part == kw && !tags.iter().any(|t| t == *tag) {
                tags.push(tag.to_string());
            }
        }
    }

    tags.truncate(5);
    tags
}

// ── Scoring functions ──────────────────────────────────────────────────

/// Compute max fuzzy affinity between a file's tags and a role's keywords.
///
/// Three strategies per (tag, keyword) pair:
///   1. Exact match           → 1.0
///   2. Substring containment → 0.7
///   3. Synonym cluster match → 0.5
fn max_tag_affinity(
    file_tags: &[String],
    affinity_keywords: &[String],
    synonym_index: &FxHashMap<&str, u8>,
) -> f32 {
    if file_tags.is_empty() || affinity_keywords.is_empty() {
        return 0.0;
    }

    let mut best: f32 = 0.0;

    for tag in file_tags {
        let tl = tag.to_lowercase().replace('-', " ").replace('_', " ");
        for kw in affinity_keywords {
            let kl = kw.to_lowercase().replace('-', " ").replace('_', " ");

            // 1. Exact match
            if tl == kl {
                return 1.0; // Can't beat 1.0
            }

            // 2. Substring (either direction)
            if kl.contains(&tl) || tl.contains(&kl) {
                best = best.max(0.7);
                continue;
            }

            // 3. Synonym cluster match
            if best < 0.5 {
                let tl_dash = tl.replace(' ', "-");
                let kl_dash = kl.replace(' ', "-");
                if let (Some(&t_idx), Some(&k_idx)) = (
                    synonym_index.get(tl_dash.as_str()),
                    synonym_index.get(kl_dash.as_str()),
                ) {
                    if t_idx == k_idx {
                        best = 0.5;
                    }
                }
            }
        }
    }

    best
}

/// Compute audience bonus: what fraction of a file's tags list this role
/// as an audience member.
fn compute_audience_bonus(
    domain_tags: &[String],
    role_id: &str,
    tag_to_audience: &FxHashMap<&str, &[&str]>,
) -> f32 {
    if domain_tags.is_empty() {
        return 0.0;
    }

    let mut matches: u32 = 0;
    for tag in domain_tags {
        let tag_lower = tag.to_lowercase().replace('_', "-");
        if let Some(audience) = tag_to_audience.get(tag_lower.as_str()) {
            if audience.contains(&role_id) {
                matches += 1;
            }
        }
    }

    (matches as f32 / domain_tags.len().max(1) as f32).min(1.0)
}

/// Compute how relevant a file is to a given role (0.0-1.0).
///
/// Components:
///   1. Architecture layer match (0.25): role.layer_weights[file.layer]
///   2. Domain tag affinity (0.30):      fuzzy match file tags vs role keywords
///   3. Audience bonus (0.10):           TAG_TO_AUDIENCE role ownership
///   4. Graph centrality (0.20):         normalized in_degree × centrality_weight
///   5. Epistemic confidence (0.15):     prefers well-understood files
fn compute_role_relevance(
    architecture_layer: &str,
    domain_tags: &[String],
    epistemic_confidence: f32,
    in_degree: u32,
    max_degree: u32,
    role: &RoleVector,
    synonym_index: &FxHashMap<&str, u8>,
    tag_to_audience: &FxHashMap<&str, &[&str]>,
) -> f32 {
    // 1. Layer match
    let layer_score = role
        .layer_weights
        .get(architecture_layer)
        .copied()
        .unwrap_or(0.1);

    // 2. Tag affinity
    let tag_score = max_tag_affinity(domain_tags, &role.domain_affinity, synonym_index);

    // 3. Audience bonus
    let audience_score = compute_audience_bonus(domain_tags, &role.role_id, tag_to_audience);

    // 4. Centrality
    let centrality_score = if max_degree > 0 {
        let norm = (in_degree as f32 / (max_degree as f32 * 0.3).max(1.0)).min(1.0);
        norm * role.centrality_weight
    } else {
        0.0
    };

    // 5. Confidence
    let confidence_score = epistemic_confidence.clamp(0.0, 1.0);

    // Weighted composite
    let relevance = WEIGHT_LAYER_MATCH * layer_score
        + WEIGHT_TAG_AFFINITY * tag_score
        + WEIGHT_CENTRALITY * centrality_score
        + WEIGHT_AUDIENCE_BONUS * audience_score
        + WEIGHT_CONFIDENCE * confidence_score;

    // Round to 4 decimal places (match Python behavior)
    (relevance.min(1.0) * 10000.0).round() / 10000.0
}

// ── Data loading helpers ───────────────────────────────────────────────

/// Load epistemic entries from trace_epistemic.jsonl.
/// Returns a map of node_id → EpistemicAnnotation.
fn load_epistemic_entries(index_dir: &Path) -> HashMap<String, EpistemicAnnotation> {
    let path = index_dir.join("trace_epistemic.jsonl");
    let mut entries = HashMap::new();

    let file = match std::fs::File::open(&path) {
        Ok(f) => f,
        Err(_) => return entries,
    };

    let reader = std::io::BufReader::new(file);
    for line in reader.lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => continue,
        };
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        match serde_json::from_str::<EpistemicAnnotation>(trimmed) {
            Ok(entry) => {
                entries.insert(entry.node_id.clone(), entry);
            }
            Err(_) => continue,
        }
    }
    entries
}

/// Load file entries from trace_nodes.jsonl as synthetic epistemic entries.
/// Used as a fallback when trace_epistemic.jsonl doesn't exist.
fn load_trace_nodes_fallback(index_dir: &Path) -> HashMap<String, EpistemicAnnotation> {
    let path = index_dir.join("trace_nodes.jsonl");
    let mut entries = HashMap::new();

    let file = match std::fs::File::open(&path) {
        Ok(f) => f,
        Err(_) => return entries,
    };

    #[derive(Deserialize)]
    struct NodeEntry {
        #[serde(default)]
        node_id: String,
        #[serde(default)]
        summary: String,
    }

    let reader = std::io::BufReader::new(file);
    for line in reader.lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => continue,
        };
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        match serde_json::from_str::<NodeEntry>(trimmed) {
            Ok(entry) => {
                if !entry.node_id.starts_with("file:") {
                    continue;
                }
                let file_path = entry.node_id[5..].to_string();
                let node_id_clone = entry.node_id.clone();
                entries.insert(
                    node_id_clone,
                    EpistemicAnnotation {
                        node_id: entry.node_id,
                        file_path: file_path.clone(),
                        architecture_layer: infer_layer_from_path(&file_path).to_string(),
                        domain_tags: infer_tags_from_path(&file_path),
                        epistemic_confidence: 0.5,
                        extended_summary: entry.summary,
                    },
                );
            }
            Err(_) => continue,
        }
    }
    entries
}

/// Compute in-degree for each file node from trace edge files.
fn compute_in_degrees(index_dir: &Path) -> HashMap<String, u32> {
    let mut degrees: HashMap<String, u32> = HashMap::new();

    for fname in &["trace_edges.jsonl", "trace_inferred_edges.jsonl"] {
        let path = index_dir.join(fname);
        let file = match std::fs::File::open(&path) {
            Ok(f) => f,
            Err(_) => continue,
        };

        #[derive(Deserialize)]
        struct EdgeEntry {
            #[serde(default)]
            target: String,
        }

        let reader = std::io::BufReader::new(file);
        for line in reader.lines() {
            let line = match line {
                Ok(l) => l,
                Err(_) => continue,
            };
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }
            match serde_json::from_str::<EdgeEntry>(trimmed) {
                Ok(entry) => {
                    if entry.target.starts_with("file:") {
                        *degrees.entry(entry.target).or_insert(0) += 1;
                    }
                }
                Err(_) => continue,
            }
        }
    }
    degrees
}

// ── Main scoring entry point ───────────────────────────────────────────

/// Score all files against a role vector and return sorted results.
///
/// This is the main entry point called from the PyO3 bridge.
/// Loads epistemic data and edge data from `index_dir`, scores every file
/// node, and returns `(file_path, score, architecture_layer, domain_tags,
/// confidence, summary)` tuples sorted by relevance descending.
///
/// Falls back to trace_nodes.jsonl if trace_epistemic.jsonl doesn't exist.
pub fn score_files_for_role(
    index_dir: &Path,
    role: &RoleVector,
) -> Vec<ScoredFile> {
    // Build lookup tables
    let synonym_index = build_synonym_index();
    let tag_to_audience = build_tag_to_audience();

    // Load epistemic data (or fallback to structural inference)
    let mut epistemic = load_epistemic_entries(index_dir);
    if epistemic.is_empty() {
        epistemic = load_trace_nodes_fallback(index_dir);
        if epistemic.is_empty() {
            return Vec::new();
        }
        log::debug!(
            "Role projection: using structural fallback ({} files from trace_nodes)",
            epistemic.len()
        );
    }

    // Compute in-degrees
    let in_degrees = compute_in_degrees(index_dir);
    let max_degree = in_degrees.values().copied().max().unwrap_or(0);

    // Score every file
    let mut scored: Vec<ScoredFile> = Vec::with_capacity(epistemic.len());

    for (node_id, entry) in &epistemic {
        if !node_id.starts_with("file:") {
            continue;
        }

        let file_path = &node_id[5..]; // Strip "file:" prefix
        let in_degree = in_degrees.get(node_id).copied().unwrap_or(0);

        let score = compute_role_relevance(
            &entry.architecture_layer,
            &entry.domain_tags,
            entry.epistemic_confidence,
            in_degree,
            max_degree,
            role,
            &synonym_index,
            &tag_to_audience,
        );

        scored.push(ScoredFile {
            file_path: file_path.to_string(),
            score,
            architecture_layer: entry.architecture_layer.clone(),
            domain_tags: entry.domain_tags.clone(),
            epistemic_confidence: entry.epistemic_confidence,
            extended_summary: entry.extended_summary.clone(),
        });
    }

    // Sort by relevance (descending), then by path (ascending) for stability
    scored.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.file_path.cmp(&b.file_path))
    });

    scored
}

// ── Tests ──────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_synonym_index() {
        let idx = build_synonym_index();
        // "ui" and "frontend" should be in the same cluster
        assert_eq!(idx.get("ui"), idx.get("frontend"));
        // "api" and "rest" should be in the same cluster
        assert_eq!(idx.get("api"), idx.get("rest"));
        // "ui" and "api" should NOT be in the same cluster
        assert_ne!(idx.get("ui"), idx.get("api"));
    }

    #[test]
    fn test_tag_to_audience() {
        let map = build_tag_to_audience();
        let ui_audience = map.get("ui").unwrap();
        assert!(ui_audience.contains(&"design"));
        assert!(ui_audience.contains(&"full_stack"));
    }

    #[test]
    fn test_max_tag_affinity_exact() {
        let idx = build_synonym_index();
        let tags = vec!["api".to_string(), "backend".to_string()];
        let keywords = vec!["api".to_string()];
        assert_eq!(max_tag_affinity(&tags, &keywords, &idx), 1.0);
    }

    #[test]
    fn test_max_tag_affinity_substring() {
        let idx = build_synonym_index();
        let tags = vec!["authentication".to_string()];
        let keywords = vec!["auth".to_string()];
        assert_eq!(max_tag_affinity(&tags, &keywords, &idx), 0.7);
    }

    #[test]
    fn test_max_tag_affinity_synonym() {
        let idx = build_synonym_index();
        let tags = vec!["frontend".to_string()];
        let keywords = vec!["ui".to_string()];
        // "frontend" and "ui" are synonyms → 0.5
        // But "ui" is a substring of... no. They're separate words.
        // However, "ui" and "frontend" — "ui" is NOT contained in "frontend"
        // and "frontend" is NOT contained in "ui". So exact=no, substring=no →
        // synonym should fire.
        assert_eq!(max_tag_affinity(&tags, &keywords, &idx), 0.5);
    }

    #[test]
    fn test_max_tag_affinity_empty() {
        let idx = build_synonym_index();
        assert_eq!(max_tag_affinity(&[], &["api".to_string()], &idx), 0.0);
        assert_eq!(
            max_tag_affinity(&["api".to_string()], &[], &idx),
            0.0
        );
    }

    #[test]
    fn test_audience_bonus_match() {
        let map = build_tag_to_audience();
        let tags = vec!["ui".to_string(), "frontend".to_string()];
        let score = compute_audience_bonus(&tags, "design", &map);
        assert!(score > 0.0, "Design should have audience bonus for ui+frontend");
        assert_eq!(score, 1.0); // Both tags list "design" as audience
    }

    #[test]
    fn test_audience_bonus_no_match() {
        let map = build_tag_to_audience();
        let tags = vec!["infrastructure".to_string()];
        let score = compute_audience_bonus(&tags, "design", &map);
        assert_eq!(score, 0.0);
    }

    #[test]
    fn test_compute_role_relevance() {
        let syn = build_synonym_index();
        let aud = build_tag_to_audience();

        let role = RoleVector {
            role_id: "engineering".to_string(),
            display_name: "Software Engineer".to_string(),
            layer_weights: {
                let mut m = HashMap::new();
                m.insert("business_logic".to_string(), 0.9f32);
                m.insert("presentation".to_string(), 0.5f32);
                m
            },
            domain_affinity: vec!["api".to_string(), "architecture".to_string()],
            centrality_weight: 0.5,
            detail_level: 0.8,
            max_chars: 3500,
        };

        let score = compute_role_relevance(
            "business_logic",
            &["api".to_string(), "backend".to_string()],
            0.8,
            10,
            50,
            &role,
            &syn,
            &aud,
        );

        // Should be a reasonably high score for an engineering role looking at
        // a business_logic API file
        assert!(score > 0.4, "Score should be > 0.4, got {}", score);
        assert!(score <= 1.0, "Score should be <= 1.0, got {}", score);
    }

    #[test]
    fn test_infer_layer_from_path() {
        assert_eq!(infer_layer_from_path("src/api/routes.py"), "presentation");
        assert_eq!(infer_layer_from_path("src/core/engine.py"), "business_logic");
        assert_eq!(infer_layer_from_path("tests/test_api.py"), "testing");
        assert_eq!(infer_layer_from_path("deploy/docker/Dockerfile"), "infrastructure");
        assert_eq!(infer_layer_from_path("README.md"), "unknown");
    }

    #[test]
    fn test_infer_tags_from_path() {
        let tags = infer_tags_from_path("src/ui/Button.tsx");
        assert!(tags.contains(&"ui".to_string()));
        assert!(tags.contains(&"frontend".to_string()));

        let tags = infer_tags_from_path("src/core/engine.py");
        assert!(tags.contains(&"backend".to_string()));
        assert!(tags.contains(&"core".to_string()));
    }
}
