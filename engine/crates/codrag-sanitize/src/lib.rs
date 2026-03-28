//! Content sanitization for CoDRAG.
//!
//! Provides high-performance Rust implementations of security-critical text processing:
//! - Code fence escaping (prevents prompt injection via triple-backtick breakout)
//! - Invisible Unicode stripping (defends against "Rules File Backdoor" attacks)
//! - NFKC normalization (collapses homoglyphs to prevent EchoLeak-style attacks)
//! - Secret detection (scans for well-known API key and credential patterns)

use once_cell::sync::Lazy;
use regex::Regex;
use unicode_normalization::UnicodeNormalization;

// ── Code fence sanitization ──────────────────────────────────────────────────

static TRIPLE_BACKTICK_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"`{3,}").unwrap());

/// Escape runs of 3+ backticks to prevent markdown code fence breakout.
///
/// Replaces runs of 3+ backticks with 2 real backticks followed by
/// LEFT SINGLE QUOTATION MARK (U+2018) characters for the remainder.
/// This preserves visual appearance while preventing fence boundaries.
pub fn sanitize_code_fences(content: &str) -> String {
    if !content.contains("```") {
        return content.to_string();
    }
    TRIPLE_BACKTICK_RE
        .replace_all(content, |caps: &regex::Captures| {
            let run_len = caps[0].len();
            let mut result = String::with_capacity(run_len);
            result.push_str("``");
            for _ in 0..(run_len - 2) {
                result.push('\u{2018}');
            }
            result
        })
        .into_owned()
}

// ── Invisible Unicode stripping ──────────────────────────────────────────────

/// Check if a character is an invisible Unicode character that should be stripped.
#[inline]
fn is_invisible_char(c: char) -> bool {
    matches!(c,
        '\u{200b}' | '\u{200c}' | '\u{200d}' | '\u{200e}' | '\u{200f}'
        | '\u{2060}' | '\u{2061}' | '\u{2062}' | '\u{2063}' | '\u{2064}'
        | '\u{2066}' | '\u{2067}' | '\u{2068}' | '\u{2069}'
        | '\u{206a}' | '\u{206b}' | '\u{206c}' | '\u{206d}' | '\u{206e}' | '\u{206f}'
        | '\u{feff}' | '\u{fff9}' | '\u{fffa}' | '\u{fffb}'
    ) || ('\u{E0000}'..='\u{E007F}').contains(&c)
}

/// Remove invisible Unicode characters from text.
pub fn strip_invisible_unicode(text: &str) -> String {
    if !text.chars().any(is_invisible_char) {
        return text.to_string();
    }
    text.chars().filter(|c| !is_invisible_char(*c)).collect()
}

/// Check if text contains any invisible Unicode characters.
pub fn has_invisible_unicode(text: &str) -> bool {
    text.chars().any(is_invisible_char)
}

// ── NFKC normalization ───────────────────────────────────────────────────────

/// Apply Unicode NFKC normalization to collapse homoglyphs.
pub fn normalize_nfkc(text: &str) -> String {
    text.nfkc().collect()
}

// ── Secret detection ─────────────────────────────────────────────────────────

/// Build the secret patterns lazily. We use a function to construct the
/// regex strings to avoid raw string delimiter issues with embedded quotes.
fn build_secret_patterns() -> Vec<(Regex, &'static str)> {
    let patterns: Vec<(&str, &'static str)> = vec![
        (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
        (r"(?:aws_secret_access_key|aws_secret)\s*[:=]\s*['\x22]?[A-Za-z0-9/+=]{40}", "AWS Secret Key"),
        (r"gh[ps]_[A-Za-z0-9_]{36,}", "GitHub Token"),
        (r"gho_[A-Za-z0-9_]{36,}", "GitHub OAuth Token"),
        (r"xox[bporas]-[0-9A-Za-z\-]{10,}", "Slack Token"),
        (r"sk-[A-Za-z0-9]{20,}", "OpenAI API Key"),
        (r"sk-ant-[A-Za-z0-9\-]{20,}", "Anthropic API Key"),
        (r"AIza[0-9A-Za-z\-_]{35}", "Google API Key"),
        (r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "Private Key"),
        (r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_.+/=]+", "JWT Token"),
    ];

    // The generic secret pattern needs special handling because it contains quotes
    let generic_pattern = "(?i)(?:api[_\\-]?key|secret[_\\-]?key|password|token|credential)[^=\\n\\r]{0,20}[:=]\\s*['\"][^\\s'\"]{8,}['\"]";

    let mut result: Vec<(Regex, &'static str)> = patterns
        .into_iter()
        .map(|(pat, desc)| (Regex::new(pat).unwrap(), desc))
        .collect();

    result.push((Regex::new(generic_pattern).unwrap(), "Generic Secret"));
    result
}

static SECRET_PATTERNS: Lazy<Vec<(Regex, &'static str)>> = Lazy::new(build_secret_patterns);

/// Scan content for well-known secret patterns.
///
/// Returns a list of matched pattern descriptions.
/// Does NOT modify content. Used for security health checks.
pub fn detect_secrets(content: &str) -> Vec<String> {
    SECRET_PATTERNS
        .iter()
        .filter_map(|(pattern, description)| {
            if pattern.is_match(content) {
                Some(description.to_string())
            } else {
                None
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── Code fence tests ─────────────────────────────────────

    #[test]
    fn test_no_backticks_unchanged() {
        let content = "def hello(): pass";
        assert_eq!(sanitize_code_fences(content), content);
    }

    #[test]
    fn test_single_backtick_unchanged() {
        let content = "Use `foo` for inline code";
        assert_eq!(sanitize_code_fences(content), content);
    }

    #[test]
    fn test_double_backtick_unchanged() {
        let content = "Use ``foo`` for escaped code";
        assert_eq!(sanitize_code_fences(content), content);
    }

    #[test]
    fn test_triple_backtick_escaped() {
        let content = "```\nmalicious breakout\n```";
        let result = sanitize_code_fences(content);
        assert!(!result.contains("```"));
        assert!(result.contains('\u{2018}'));
    }

    #[test]
    fn test_quadruple_backtick_escaped() {
        let content = "````\nfour backticks\n````";
        let result = sanitize_code_fences(content);
        assert!(!result.contains("````"));
        assert!(!result.contains("```"));
    }

    #[test]
    fn test_empty_string() {
        assert_eq!(sanitize_code_fences(""), "");
    }

    #[test]
    fn test_preserves_single_and_double_in_escaped() {
        let content = "```";
        let result = sanitize_code_fences(content);
        assert!(result.starts_with("``"));
        assert_eq!(result.chars().count(), 3); // 2 backticks + 1 curly quote
    }

    // ── Invisible Unicode tests ──────────────────────────────

    #[test]
    fn test_strip_zero_width_space() {
        assert_eq!(strip_invisible_unicode("hello\u{200b}world"), "helloworld");
    }

    #[test]
    fn test_strip_zero_width_joiner() {
        assert_eq!(strip_invisible_unicode("foo\u{200d}bar"), "foobar");
    }

    #[test]
    fn test_strip_bidi_markers() {
        assert_eq!(strip_invisible_unicode("left\u{200e}right\u{200f}"), "leftright");
    }

    #[test]
    fn test_strip_word_joiner() {
        assert_eq!(strip_invisible_unicode("word\u{2060}joiner"), "wordjoiner");
    }

    #[test]
    fn test_strip_bom() {
        assert_eq!(strip_invisible_unicode("\u{feff}content"), "content");
    }

    #[test]
    fn test_strip_directional_isolates() {
        assert_eq!(
            strip_invisible_unicode("a\u{2066}b\u{2067}c\u{2068}d\u{2069}e"),
            "abcde"
        );
    }

    #[test]
    fn test_clean_text_unchanged() {
        let text = "normal ASCII text";
        assert_eq!(strip_invisible_unicode(text), text);
    }

    #[test]
    fn test_unicode_emoji_preserved() {
        let text = "hello \u{1F30D} world";
        assert_eq!(strip_invisible_unicode(text), text);
    }

    #[test]
    fn test_cjk_preserved() {
        let text = "\u{65E5}\u{672C}\u{8A9E}";
        assert_eq!(strip_invisible_unicode(text), text);
    }

    #[test]
    fn test_detect_finds_invisible() {
        assert!(has_invisible_unicode("hello\u{200b}world"));
    }

    #[test]
    fn test_detect_clean_text() {
        assert!(!has_invisible_unicode("clean text"));
    }

    #[test]
    fn test_detect_empty() {
        assert!(!has_invisible_unicode(""));
    }

    #[test]
    fn test_multiple_invisible_chars_stripped() {
        let text = "Normal rule\u{200b}\u{200c}\u{200d}\u{2060}\u{feff}: Use React";
        let result = strip_invisible_unicode(text);
        assert_eq!(result, "Normal rule: Use React");
        assert!(result.len() < text.len());
    }

    // ── NFKC normalization tests ─────────────────────────────

    #[test]
    fn test_nfkc_ascii_unchanged() {
        let text = "normal ASCII text";
        assert_eq!(normalize_nfkc(text), text);
    }

    #[test]
    fn test_nfkc_fullwidth_collapsed() {
        // Fullwidth A, B, C -> ASCII A, B, C
        let text = "\u{FF21}\u{FF22}\u{FF23}";
        assert_eq!(normalize_nfkc(text), "ABC");
    }

    #[test]
    fn test_nfkc_empty() {
        assert_eq!(normalize_nfkc(""), "");
    }

    // ── Secret detection tests ───────────────────────────────

    #[test]
    fn test_detects_aws_access_key() {
        let content = "key = AKIAIOSFODNN7EXAMPLE";
        let secrets = detect_secrets(content);
        assert!(!secrets.is_empty());
    }

    #[test]
    fn test_detects_github_token() {
        let content = "token = ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijkl";
        let secrets = detect_secrets(content);
        assert!(!secrets.is_empty());
    }

    #[test]
    fn test_detects_openai_key() {
        let content = "OPENAI_API_KEY = sk-abcdefghijklmnopqrstuvwxyz12345678";
        let secrets = detect_secrets(content);
        assert!(!secrets.is_empty());
    }

    #[test]
    fn test_detects_private_key_header() {
        let content = "-----BEGIN RSA PRIVATE KEY-----\ndata here";
        let secrets = detect_secrets(content);
        assert!(!secrets.is_empty());
    }

    #[test]
    fn test_no_secrets_in_clean_content() {
        let content = "def hello(): return 42";
        let secrets = detect_secrets(content);
        assert!(secrets.is_empty());
    }

    #[test]
    fn test_detects_jwt_token() {
        let header = "eyJhbGciOiJIUzI1NiJ9";
        let payload = "eyJzdWIiOiIxMjM0NTY3ODkwIn0";
        let sig = "abc123def456";
        let content = format!("token = {}.{}.{}", header, payload, sig);
        let secrets = detect_secrets(&content);
        assert!(!secrets.is_empty());
    }
}
