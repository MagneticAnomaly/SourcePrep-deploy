# Zed Research & Integration Opportunities for CoDRAG

**Research Date**: March 25, 2026  
**Status**: Initial Research Complete  
**Researcher**: CoDRAG Team

---

## Executive Summary

Zed is a high-performance, multiplayer code editor built by the creators of Atom and Tree-sitter. After extensive research into their infrastructure, CI/CD pipeline, download hosting, and extension system, I've identified numerous opportunities for integration with CoDRAG.

This document provides a comprehensive analysis of Zed's architecture and multiple integration pathways for CoDRAG, from quick-win MCP server extensions to deep native integrations.

---

## Table of Contents

1. [Zed's CI/CD Pipeline Architecture](#1-zeds-cicd-pipeline-architecture)
2. [Download Hosting Infrastructure](#2-download-hosting-infrastructure)
3. [Extension System & MCP Integration](#3-extension-system--mcp-integration)
4. [Integration Opportunities for CoDRAG](#4-integration-opportunities-for-codrag)
5. [Technical Deep Dive: Zed Extension Development](#5-technical-deep-dive-zed-extension-development)
6. [Infrastructure Recommendations for CoDRAG](#6-infrastructure-recommendations-for-codrag)
7. [Research Action Items](#7-research-action-items)
8. [Competitive Analysis: Zed vs VSCode Extensions](#8-competitive-analysis-zed-vs-vscode-extensions)
9. [Next Steps & Recommendations](#9-next-steps--recommendations)
10. [Key Takeaways](#10-key-takeaways)

---

## 1. Zed's CI/CD Pipeline Architecture

### 1.1 Infrastructure Overview

**Key Findings:**
- **Custom GitHub Actions runners**: Zed uses namespace-specific runners (`namespace-profile-mac-large`, `namespace-profile-16x32-ubuntu-2204`, `self-32vcpu-windows-2022`)
- **Multi-platform builds**: macOS (x86_64 + aarch64), Linux (x86_64 + aarch64), Windows (x86_64 + aarch64)
- **Build caching**: Uses `sccache` with Cloudflare R2 for distributed compilation caching
- **Artifact management**: GitHub Actions artifacts → DigitalOcean Spaces for hosting

### 1.2 Release Workflow

```
Tag Push (v*) → Test Suite → Clippy Checks → Bundle All Platforms → 
Upload to GitHub Release → Validate Assets → Auto-publish (if -pre)
```

**Key Components:**

#### Testing Phase
- **Test Runner**: `cargo nextest` across all platforms (60-minute timeout)
- **Platforms Tested**: macOS, Linux, Windows
- **Postgres Service**: Required for Linux tests (postgres:15)

#### Compilation Phase
- **Cache Strategy**: `sccache` with Cloudflare R2 backend
- **Environment Variables**:
  - `R2_ACCOUNT_ID`
  - `R2_ACCESS_KEY_ID`
  - `R2_SECRET_ACCESS_KEY`
  - `SCCACHE_BUCKET: sccache-zed`

#### Code Quality Checks
- **Clippy**: Rust linting across all platforms
- **Script Validation**: `shellcheck` + `actionlint` for CI/CD workflows
- **Format Check**: `cargo fmt --all --check`

#### Signing & Notarization
- **macOS**: Apple notarization certificates (certificate, password, key, issuer ID)
- **Windows**: Azure Code Signing (tenant ID, client credentials, cert profile)
- **Linux**: No signing required

#### Diagnostics & Monitoring
- **Sentry Integration**: Crash reporting and error tracking
- **Environment Variables**:
  - `ZED_CLIENT_CHECKSUM_SEED`
  - `ZED_MINIDUMP_ENDPOINT`

### 1.3 Nightly Build Pipeline

**Schedule**: Daily at 7 AM UTC

```
Schedule → Bundle All Platforms → Upload to DigitalOcean Spaces → 
Update Nightly Tag → Create Sentry Release
```

**Key Differences from Stable:**
- No clippy checks (faster turnaround)
- Version format: `{crate-version}+nightly.{run_number}.{git_sha}`
- Direct upload to blob store (no GitHub Release)
- Automatic nightly tag update

---

## 2. Download Hosting Infrastructure

### 2.1 Current Setup

**Stable Releases:**
- **Primary Host**: GitHub Releases
- **Assets per Release**: 12 files (6 platforms × client + remote server)
  - `Zed-aarch64.dmg` (macOS ARM64)
  - `Zed-x86_64.dmg` (macOS Intel)
  - `zed-linux-aarch64.tar.gz` (Linux ARM64)
  - `zed-linux-x86_64.tar.gz` (Linux Intel)
  - `Zed-aarch64.exe` (Windows ARM64)
  - `Zed-x86_64.exe` (Windows Intel)
  - Plus remote server binaries for each platform

**Nightly Builds:**
- **Provider**: DigitalOcean Spaces (S3-compatible)
- **Region**: NYC3 (`nyc3.digitaloceanspaces.com`)
- **Bucket**: `zed-nightly-host`
- **Access**: Public-read ACL for all artifacts

**Download Script:**
```bash
curl -f https://zed.dev/install.sh | sh
```

### 2.2 Architecture Diagram

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   GitHub        │────▶│  DigitalOcean    │────▶│   Users         │
│   Releases      │     │   Spaces (S3)    │     │                 │
│   (Stable)      │     │   (Nightly)      │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │
         ▼                       ▼
    GitHub API            DigitalOcean Spaces API
```

### 2.3 Blob Store Implementation

Zed uses a custom shell script for uploading to DigitalOcean Spaces:

```bash
#!/usr/bin/env bash
set -euo pipefail
source script/lib/blob-store.sh

bucket_name="zed-nightly-host"
version=$(./script/get-crate-version zed)+nightly."${GITHUB_RUN_NUMBER}.${GITHUB_SHA}"

for file_to_upload in ./release-artifacts/*; do
    [ -f "$file_to_upload" ] || continue
    upload_to_blob_store_public $bucket_name "$file_to_upload" "nightly/$(basename "$file_to_upload")"
    upload_to_blob_store_public $bucket_name "$file_to_upload" "${version}/$(basename "$file_to_upload")"
    rm -f "$file_to_upload"
done

echo -n ${version} > ./release-artifacts/latest-sha
upload_to_blob_store_public $bucket_name "release-artifacts/latest-sha" "nightly/latest-sha"
```

**Key Functions:**
- `upload_to_blob_store_public`: Makes files publicly accessible (public-read ACL)
- `upload_to_blob_store`: Private uploads (for internal use)
- Signature generation using AWS-compatible authentication

### 2.4 Key Insights for CoDRAG

**What We Can Learn:**
1. **Hybrid approach**: Use GitHub for stable releases + object storage for nightlies
2. **Versioned paths**: Store both version-specific and `latest` pointers
3. **Multi-region CDN**: DigitalOcean Spaces can be paired with CDN for global distribution
4. **Checksum validation**: SHA-256 hashes for all artifacts (security best practice)
5. **Dual storage**: Both `nightly/` and `{version}/` paths enable easy rollback

---

## 3. Extension System & MCP Integration

### 3.1 Extension Types Supported

Zed supports multiple extension categories:
- **Themes** (syntax highlighting, icon themes)
- **Language Support** (grammars, LSP integration)
- **Debuggers** (DAP extensions)
- **Agent Servers** (ACP-based AI agents) ⭐ *High relevance to CoDRAG*
- **MCP Servers** (Model Context Protocol) ⭐ *Direct integration opportunity*

### 3.2 MCP Server Extensions (v0.221+)

**Architecture:**
```toml
[context_servers.my-context-server]
# Implemented in Rust extension code
fn context_server_command(...) -> Result<zed::Command>
```

**Implementation Pattern:**
- Rust extension implements `context_server_command` method on `zed::Extension` trait
- Returns command, args, and environment variables for MCP server
- Can download binaries from external sources (GitHub Releases, npm) during command execution

**Code Example:**
```rust
impl zed::Extension for MyExtension {
    fn context_server_command(
        &mut self,
        context_server_id: &ContextServerId,
        project: &zed::Project,
    ) -> Result<zed::Command> {
        Ok(zed::Command {
            command: get_path_to_context_server_executable()?,
            args: get_args_for_context_server()?,
            env: get_env_for_context_server()?,
        })
    }
}
```

**Current MCP Extensions:** Available at `zed.dev/extensions?filter=context-servers`

### 3.3 Agent Server Extensions (ACP)

**Architecture:**
```toml
[agent_servers.my-agent]
name = "My Agent"

[agent_servers.my-agent.targets.darwin-aarch64]
archive = "https://github.com/owner/repo/releases/download/v1.0.0/agent-darwin-arm64.tar.gz"
cmd = "./agent"
args = ["--serve"]
sha256 = "abc123..."

[agent_servers.my-agent.targets.linux-x86_64]
archive = "..."
cmd = "./agent"
args = ["--serve"]
sha256 = "def456..."

[agent_servers.my-agent.targets.windows-x86_64]
archive = "..."
cmd = "./agent.exe"
args = ["--serve"]
sha256 = "ghi789..."

[agent_servers.my-agent.env]
AGENT_LOG_LEVEL = "info"
```

**Key Features:**
- **Multi-platform support**: macOS (x86_64 + aarch64), Linux (x86_64 + aarch64), Windows (x86_64 + aarch64)
- **SHA-256 hash validation**: Supply chain security for downloaded binaries
- **Environment variable configuration**: Agent-level + target-level overrides
- **Background process management**: ACP protocol for agent communication

**Installation Process:**
1. User installs extension via Zed's Extensions tab
2. Zed downloads appropriate archive for user's platform
3. Archive extracted to cache directory
4. Agent server launched with specified command and arguments
5. Environment variables set as configured
6. Agent runs in background, ready to assist via ACP

### 3.4 ACP Registry (Preferred Method)

**Starting from v0.221.x**, the **ACP Registry** is now the preferred installation method:
- **URL**: `https://agentclientprotocol.com/registry`
- **Deprecation path**: Traditional Agent Server extensions will be deprecated in favor of ACP Registry
- **Benefits**: Centralized discovery, version management, and installation

**Note**: Agent Server extensions are still functional but will eventually be deprecated.

---

## 4. Integration Opportunities for CoDRAG

### 4.1 Immediate Opportunities (MCP)

#### Option A: Zed MCP Extension (Recommended Starting Point)

**Description**: Create a native CoDRAG MCP server extension for Zed

**Implementation Steps:**
1. Build Rust extension using `zed::Extension` trait
2. Implement `context_server_command()` to spawn CoDRAG MCP server
3. Package with platform-specific binaries (6 combinations)
4. Publish to Zed extension registry

**Pros:**
- Native integration with Zed's Agent Panel
- Leverages existing CoDRAG MCP infrastructure
- Direct access to Zed's RAG capabilities
- Lower barrier than full ACP implementation

**Cons:**
- Requires Rust development (Zed extension API)
- Must maintain platform-specific binaries
- Limited to MCP protocol features

**Estimated Effort**: 2-3 weeks (learning curve + implementation)

**Technical Requirements:**
```rust
use zed::{Extension, ExtensionApi, ContextServerId, Project, Command};

struct CoDRAGMCP;

impl Extension for CoDRAGMCP {
    fn new() -> Self { Self }

    fn context_server_command(
        &mut self,
        id: &ContextServerId,
        project: &Project,
    ) -> Result<Command> {
        Ok(Command {
            command: "/path/to/codrag-mcp".into(),
            args: vec!["--project".into(), project.path().to_string()],
            env: vec![("CODRAG_CONFIG".into(), config_path)],
        })
    }
}

zed::register_extension!(CoDRAGMCP);
```

#### Option B: Standalone MCP Server with Zed Integration

**Description**: Keep CoDRAG as standalone MCP server, add Zed-specific configuration

**Implementation Steps:**
1. Document CoDRAG MCP server setup for Zed users
2. Create `extension.toml` template for manual installation
3. Provide download scripts (like Zed's `install.sh`)

**Pros:**
- Faster to implement
- No Rust development required
- Works with existing CoDRAG infrastructure

**Cons:**
- Less seamless than native extension
- Manual installation required
- No Agent Panel integration

**Estimated Effort**: 1 week (documentation + scripts)

### 4.2 Medium-Term Opportunities (ACP Agent Server)

#### Option C: CoDRAG ACP Agent Server

**Description**: Package CoDRAG as an ACP-based agent server for Zed

**Implementation Steps:**
1. Implement ACP protocol client/server (if not already done)
2. Create multi-platform binaries (6 combinations)
3. Package as extension with `extension.toml`
4. Publish to ACP Registry

**Pros:**
- Deep integration with Zed's AI features
- Access to ACP ecosystem
- Future-proof (ACP is the direction Zed is heading)
- Better user experience than MCP

**Cons:**
- Requires ACP protocol implementation
- 6 platform builds to maintain
- Longer development timeline

**Estimated Effort**: 4-6 weeks (ACP implementation + packaging)

**Extension.toml Structure:**
```toml
id = "codrag-agent"
name = "CoDRAG Agent"
version = "0.1.0"

[agent_servers.codrag]
name = "CoDRAG Assistant"

[agent_servers.codrag.targets.darwin-aarch64]
archive = "https://cdn.zed.dev/codrag/darwin-aarch64.tar.gz"
cmd = "./codrag-agent"
args = ["serve"]
sha256 = "abc123def456..."

[agent_servers.codrag.targets.linux-x86_64]
archive = "https://cdn.zed.dev/codrag/linux-x86_64.tar.gz"
cmd = "./codrag-agent"
args = ["serve"]
sha256 = "def456ghi789..."

[agent_servers.codrag.targets.windows-x86_64]
archive = "https://cdn.zed.dev/codrag/windows-x86_64.zip"
cmd = "./codrag-agent.exe"
args = ["serve"]
sha256 = "ghi789jkl012..."

[agent_servers.codrag.env]
CODRAG_API_KEY = "your-api-key"
```

### 4.3 Long-Term Opportunities (Deeper Integration)

#### Option D: CoDRAG as Zed Extension with RAG Engine

**Description**: Full integration similar to VSCode extension but for Zed

**Features:**
- Native file system access (Zed's extension API)
- Direct RAG pipeline integration
- Custom UI components in Zed (if supported)
- Shared state with Zed's document model

**Pros:**
- Best possible user experience
- Tight integration with editor features
- Competitive advantage over standalone MCP

**Cons:**
- Significant Rust development required
- Must keep pace with Zed's API changes
- Platform-specific build complexity

**Estimated Effort**: 8-12 weeks (full implementation)

#### Option E: CoDRAG Plugin Architecture for Zed

**Description**: Build a plugin system that mirrors VSCode extension but optimized for CoDRAG

**Features:**
- Custom command palette integration
- Inline code suggestions (like edit prediction)
- Agent panel with CoDRAG-specific UI
- Project-aware RAG context

**Pros:**
- Differentiated from generic MCP servers
- Leverages Zed's performance characteristics
- Can add unique features not possible with standard MCP

**Cons:**
- Requires deep Zed API knowledge
- Complex architecture decisions
- Maintenance burden

**Estimated Effort**: 10-16 weeks (research + implementation)

---

## 5. Technical Deep Dive: Zed Extension Development

### 5.1 Extension.toml Structure

**Basic Extension Manifest:**
```toml
id = "codrag-mcp"
name = "CoDRAG MCP Server"
version = "0.1.0"
authors = ["Your Name <your@email.com>"]
description = "CoDRAG RAG integration for Zed"

# Platform-specific binaries (for Agent Servers)
[targets.linux-x86_64]
archive = "https://your-cdn.com/codrag-linux-x86_64.tar.gz"
sha256 = "abc123..."

[targets.darwin-aarch64]
archive = "https://your-cdn.com/codrag-darwin-aarch64.tar.gz"
sha256 = "def456..."

# MCP Server configuration (context servers)
[context_servers.codrag]
name = "CoDRAG"

# Or Agent Server configuration (ACP)
[agent_servers.codrag]
name = "CoDRAG Assistant"

[agent_servers.codrag.targets.linux-x86_64]
archive = "https://your-cdn.com/codrag-agent-linux-x86_64.tar.gz"
cmd = "./codrag-agent"
args = ["serve"]
sha256 = "ghi789..."

[agent_servers.codrag.targets.darwin-aarch64]
archive = "https://your-cdn.com/codrag-agent-darwin-aarch64.tar.gz"
cmd = "./codrag-agent"
args = ["serve"]
sha256 = "jkl012..."

[agent_servers.codrag.targets.windows-x86_64]
archive = "https://your-cdn.com/codrag-agent-windows-x86_64.zip"
cmd = "./codrag-agent.exe"
args = ["serve"]
sha256 = "mno345..."

[agent_servers.codrag.env]
CODRAG_CONFIG_PATH = "/path/to/config"
```

### 5.2 Rust Extension Boilerplate

**Minimal MCP Server Extension:**
```rust
use zed::{Extension, ExtensionApi, ContextServerId, Project, Command};

struct CoDRAGExtension;

impl Extension for CoDRAGExtension {
    fn new() -> Self {
        Self
    }

    fn context_server_command(
        &mut self,
        context_server_id: &ContextServerId,
        project: &zed::Project,
    ) -> Result<zed::Command> {
        // Download binary if needed (optional)
        // Return command to spawn MCP server
        Ok(zed::Command {
            command: "/path/to/codrag-mcp".into(),
            args: vec!["--project".into(), project.path().to_string()],
            env: vec![("CODRAG_CONFIG".into(), config_path)],
        })
    }
}

zed::register_extension!(CoDRAGExtension);
```

**Complete Extension with Binary Download:**
```rust
use zed::{Extension, ExtensionApi, ContextServerId, Project, Command};
use std::process::Command as StdCommand;

struct CoDRAGExtension {
    api: ExtensionApi,
}

impl Extension for CoDRAGExtension {
    fn new(api: ExtensionApi) -> Self {
        Self { api }
    }

    fn context_server_command(
        &mut self,
        context_server_id: &ContextServerId,
        project: &Project,
    ) -> Result<Command> {
        let binary_path = self.ensure_binary_downloaded()?;
        
        Ok(Command {
            command: binary_path,
            args: vec![
                "--project".into(), 
                project.path().to_string()
            ],
            env: vec![
                ("CODRAG_API_KEY".into(), self.api.config()?.unwrap_or_default()),
            ],
        })
    }
}

impl CoDRAGExtension {
    fn ensure_binary_downloaded(&self) -> Result<String> {
        // Check if binary exists in cache
        // If not, download from CDN
        // Verify SHA-256 hash
        Ok(binary_path)
    }
}

zed::register_extension!(CoDRAGExtension);
```

### 5.3 Build & Distribution Strategy

**Recommended Approach:**
1. **CI/CD**: Use GitHub Actions (like Zed's workflow)
2. **Artifacts**: Upload to Cloudflare R2 or DigitalOcean Spaces
3. **Versioning**: Semantic versioning with GitHub Releases
4. **CDN**: Cloudflare Pages/Workers for global distribution

**Directory Structure:**
```
codrag-zed-extension/
├── extension.toml                    # Extension manifest
├── Cargo.toml                        # Rust workspace
├── crates/
│   ├── codrag-mcp/                   # MCP server implementation
│   │   └── src/
│   │       └── main.rs              # Extension entry point
│   └── codrag-agent/                # ACP agent (optional)
├── script/
│   ├── build-linux.sh               # Linux build script
│   ├── build-mac.sh                 # macOS build script
│   └── build-windows.ps1            # Windows build script
├── .github/
│   └── workflows/
│       ├── release.yml              # Like Zed's release workflow
│       └── publish-extension.yml    # Extension publishing
├── README.md                        # Documentation
└── LICENSE                          # License file
```

**Build Scripts (similar to Zed):**

`script/build-linux.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

cargo build --release --target x86_64-unknown-linux-gnu
tar -czf codrag-linux-x86_64.tar.gz target/x86_64-unknown-linux-gnu/release/codrag-mcp
sha256sum codrag-linux-x86_64.tar.gz > codrag-linux-x86_64.sha256
```

`script/build-mac.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

# Build for both architectures
cargo build --release --target aarch64-apple-darwin
cargo build --release --target x86_64-apple-darwin

# Create universal binary (optional)
lipo -create \
  target/aarch64-apple-darwin/release/codrag-mcp \
  target/x86_64-apple-darwin/release/codrag-mcp \
  -output codrag-mac

# Package as DMG (optional)
# ... DMG creation logic
```

`script/build-windows.ps1`:
```powershell
#!/usr/bin/env pwsh
set -euo pipefail

# Build for both architectures
cargo build --release --target x86_64-pc-windows-msvc
cargo build --release --target aarch64-pc-windows-msvc

# Package as ZIP
Compress-Archive -Path target/x86_64-pc-windows-msvc/release/codrag-mcp.exe `
  -DestinationPath codrag-windows-x86_64.zip

# Calculate SHA-256
certutil -hashfile codrag-windows-x86_64.zip SHA256 | Out-File codrag-windows-x86_64.sha256
```

---

## 6. Infrastructure Recommendations for CoDRAG

### 6.1 Download Hosting (Like Zed)

**Recommended Stack:**
```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   GitHub        │────▶│  Cloudflare      │────▶│   Users         │
│   Releases      │     │   R2 / Pages     │     │                 │
│   (Stable)      │     │  (Nightly/CDN)   │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

**Why Cloudflare R2:**
- S3-compatible API (like Zed's DigitalOcean Spaces)
- No egress fees (important for large binaries)
- Global CDN integration
- Better pricing than AWS S3 ($0.015/GB vs $0.023/GB)
- Free egress to Cloudflare Workers

**Implementation:**
```bash
# Upload to R2 (similar to Zed's blob-store.sh)
aws s3 cp codrag-linux-x86_64.tar.gz \
  s3://codrag-downloads/nightly/codrag-linux-x86_64.tar.gz \
  --endpoint-url https://<account-id>.r2.cloudflarestorage.com

# Make public
aws s3 cp codrag-linux-x86_64.tar.gz \
  s3://codrag-downloads/nightly/codrag-linux-x86_64.tar.gz \
  --acl public-read \
  --endpoint-url https://<account-id>.r2.cloudflarestorage.com

# Upload versioned path
aws s3 cp codrag-linux-x86_64.tar.gz \
  s3://codrag-downloads/nightly/v0.1.0/codrag-linux-x86_64.tar.gz \
  --acl public-read \
  --endpoint-url https://<account-id>.r2.cloudflarestorage.com

# Upload latest-sha
echo "v0.1.0" > latest-sha
aws s3 cp latest-sha \
  s3://codrag-downloads/nightly/latest-sha \
  --acl public-read \
  --endpoint-url https://<account-id>.r2.cloudflarestorage.com
```

**Directory Structure in R2:**
```
codrag-downloads/
├── stable/
│   ├── v0.1.0/
│   │   ├── codrag-linux-x86_64.tar.gz
│   │   ├── codrag-darwin-aarch64.tar.gz
│   │   └── ...
│   ├── v0.2.0/
│   │   └── ...
│   └── latest-sha → v0.2.0
├── nightly/
│   ├── 12345-abc123def/
│   │   └── ...
│   ├── 12346-ghi789jkl/
│   │   └── ...
│   └── latest-sha → 12346-ghi789jkl
```

### 6.2 CI/CD Pipeline (Like Zed)

**Recommended Workflow:**
```yaml
name: Release
on:
  push:
    tags:
      - 'v*'

env:
  CARGO_TERM_COLOR: always
  RUST_BACKTRACE: '1'

jobs:
  test:
    if: github.repository_owner == 'codrag' || github.repository_owner == 'your-org'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          clean: false
      
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Install Rust
        uses: dtolnay/rust-action@stable
      
      - name: Run Tests
        run: cargo test --workspace

  clippy:
    if: github.repository_owner == 'codrag' || github.repository_owner == 'your-org'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install Rust
        uses: dtolnay/rust-action@stable
      
      - name: Run Clippy
        run: cargo clippy --workspace --all-targets

  build-linux-x86_64:
    needs: [test, clippy]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install Rust
        uses: dtolnay/rust-action@stable
      
      - name: Build
        run: cargo build --release
      
      - uses: actions/upload-artifact@v4
        with:
          name: codrag-linux-x86_64.tar.gz
          path: target/release/codrag

  build-linux-aarch64:
    needs: [test, clippy]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install Rust (aarch64)
        uses: dtolnay/rust-action@stable
      
      - name: Install cross
        run: cargo install cross
      
      - name: Build (aarch64)
        run: cross build --release --target aarch64-unknown-linux-gnu
      
      - uses: actions/upload-artifact@v4
        with:
          name: codrag-linux-aarch64.tar.gz
          path: target/aarch64-unknown-linux-gnu/release/codrag

  build-mac-x86_64:
    needs: [test, clippy]
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install Rust
        uses: dtolnay/rust-action@stable
      
      - name: Build (x86_64)
        run: cargo build --release --target x86_64-apple-darwin
      
      - uses: actions/upload-artifact@v4
        with:
          name: codrag-darwin-x86_64.tar.gz
          path: target/x86_64-apple-darwin/release/codrag

  build-mac-aarch64:
    needs: [test, clippy]
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install Rust
        uses: dtolnay/rust-action@stable
      
      - name: Build (aarch64)
        run: cargo build --release --target aarch64-apple-darwin
      
      - uses: actions/upload-artifact@v4
        with:
          name: codrag-darwin-aarch64.tar.gz
          path: target/aarch64-apple-darwin/release/codrag

  build-windows-x86_64:
    needs: [test, clippy]
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install Rust
        uses: dtolnay/rust-action@stable
      
      - name: Build (x86_64)
        run: cargo build --release
      
      - uses: actions/upload-artifact@v4
        with:
          name: codrag-windows-x86_64.zip
          path: target/release/codrag.exe

  build-windows-aarch64:
    needs: [test, clippy]
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Install Rust (aarch64)
        uses: dtolnay/rust-action@stable
      
      - name: Build (aarch64)
        run: cargo build --release --target aarch64-pc-windows-msvc
      
      - uses: actions/upload-artifact@v4
        with:
          name: codrag-windows-aarch64.zip
          path: target/aarch64-pc-windows-msvc/release/codrag.exe

  upload-release:
    needs: [build-linux-x86_64, build-linux-aarch64, build-mac-x86_64, 
            build-mac-aarch64, build-windows-x86_64, build-windows-aarch64]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Download Artifacts
        uses: actions/download-artifact@v4
      
      - name: Create GitHub Release
        run: |
          gh release create ${{ github.ref_name }} \
            codrag-linux-x86_64.tar.gz \
            codrag-linux-aarch64.tar.gz \
            codrag-darwin-x86_64.tar.gz \
            codrag-darwin-aarch64.tar.gz \
            codrag-windows-x86_64.zip \
            codrag-windows-aarch64.zip \
            --repo=codrag/codrag-zed-extension \
            --title="Release ${{ github.ref_name }}" \
            --generate-notes
      
      - name: Upload to Cloudflare R2 (Stable)
        run: |
          # Upload all artifacts to versioned path
          aws s3 cp codrag-linux-x86_64.tar.gz \
            s3://codrag-downloads/stable/${{ github.ref_name }}/ \
            --endpoint-url https://<account-id>.r2.cloudflarestorage.com
      
      - name: Update latest-sha
        run: |
          echo "${{ github.ref_name }}" > latest-sha
          aws s3 cp latest-sha \
            s3://codrag-downloads/stable/latest-sha \
            --endpoint-url https://<account-id>.r2.cloudflarestorage.com

  validate-release:
    needs: [upload-release]
    runs-on: ubuntu-latest
    steps:
      - name: Validate Release Assets
        run: |
          EXPECTED_ASSETS='["codrag-linux-x86_64.tar.gz", "codrag-linux-aarch64.tar.gz", 
                           "codrag-darwin-x86_64.tar.gz", "codrag-darwin-aarch64.tar.gz",
                           "codrag-windows-x86_64.zip", "codrag-windows-aarch64.zip"]'
          TAG="${{ github.ref_name }}"

          ACTUAL_ASSETS=$(gh release view "$TAG" --repo=codrag/codrag-zed-extension \
            --json assets -q '[.assets[].name]')

          MISSING_ASSETS=$(echo "$EXPECTED_ASSETS" | jq -r --argjson actual "$ACTUAL_ASSETS" \
            '. - $actual | .[]')

          if [ -n "$MISSING_ASSETS" ]; then
              echo "Error: The following assets are missing from the release:"
              echo "$MISSING_ASSETS"
              exit 1
          fi

          echo "All expected assets are present in the release."
```

### 6.3 Version Resolution (Like Zed)

**Pattern from Zed:**
```
nightly/latest-sha → Contains latest commit SHA or version
nightly/{version}/ → Versioned artifacts
```

**Implementation:**
```bash
# After successful build
echo "$GITHUB_SHA" > release-artifacts/latest-sha

# Upload to R2
aws s3 cp release-artifacts/latest-sha \
  s3://codrag-downloads/nightly/latest-sha \
  --endpoint-url https://<account-id>.r2.cloudflarestorage.com

# Users can fetch latest version
LATEST_SHA=$(curl -s https://codrag-downloads.nyc3.r2.cloudflarestorage.com/nightly/latest-sha)
curl -O https://codrag-downloads.nyc3.r2.cloudflarestorage.com/nightly/$LATEST_SHA/codrag-linux-x86_64.tar.gz
```

**Download Script Example:**
```bash
#!/usr/bin/env bash
set -euo pipefail

# Detect platform
detect_platform() {
    case "$(uname -s)" in
        Darwin*)
            if [[ $(uname -m) == "arm64" ]]; then
                echo "darwin-aarch64"
            else
                echo "darwin-x86_64"
            fi
            ;;
        Linux*)
            if [[ $(uname -m) == "aarch64" ]]; then
                echo "linux-aarch64"
            else
                echo "linux-x86_64"
            fi
            ;;
        MINGW*|MSYS*|CYGWIN*)
            if [[ $(uname -m) == "aarch64" ]]; then
                echo "windows-aarch64"
            else
                echo "windows-x86_64"
            fi
            ;;
        *)
            echo "Unknown platform: $(uname -s)" >&2
            exit 1
            ;;
    esac
}

PLATFORM=$(detect_platform)
BASE_URL="https://codrag-downloads.nyc3.r2.cloudflarestorage.com"

# For stable releases
VERSION=$(curl -s ${BASE_URL}/stable/latest-sha)
ARCHIVE="${PLATFORM}.tar.gz"

curl -L "${BASE_URL}/stable/${VERSION}/${ARCHIVE}" | tar -xzf -
```

---

## 7. Research Action Items

### Priority 1: MCP Server Extension (2-3 weeks)
- [ ] **Week 1**: Research Zed's Rust extension API documentation
  - Study existing extensions on `zed.dev/extensions`
  - Review Zed's extension source code in GitHub
  - Set up development environment with Zed nightly build
  
- [ ] **Week 2**: Create basic `extension.toml` structure
  - Define extension manifest with proper TOML schema
  - Implement `context_server_command()` method
  - Create build scripts for all platforms
  
- [ ] **Week 3**: Test with local Zed build
  - Install extension as dev extension in Zed
  - Verify MCP server spawns correctly
  - Test with Agent Panel integration
  - Publish to extension registry

### Priority 2: Infrastructure Setup (1 week)
- [ ] **Day 1**: Set up Cloudflare R2 bucket for downloads
  - Create bucket `codrag-downloads`
  - Configure CORS and public access policies
  - Set up AWS CLI with R2 credentials
  
- [ ] **Day 2**: Create CI/CD pipeline (GitHub Actions)
  - Implement multi-platform build workflow
  - Add artifact upload to R2
  - Set up version resolution (latest-sha)
  
- [ ] **Day 3**: Implement multi-platform builds
  - Create build scripts for Linux, macOS, Windows
  - Add SHA-256 hash generation
  - Test builds locally
  
- [ ] **Day 4**: Set up version resolution (like Zed's nightly)
  - Implement `latest-sha` file management
  - Create download script for users
  
- [ ] **Day 5**: Documentation and testing
  - Write installation instructions
  - Test end-to-end download flow

### Priority 3: ACP Agent Server (4-6 weeks)
- [ ] **Week 1**: Study ACP protocol specification
  - Read `agentclientprotocol.com` documentation
  - Review existing ACP agents in Zed extensions
  - Understand protocol message formats
  
- [ ] **Week 2**: Implement ACP client/server in CoDRAG
  - Add ACP protocol support to existing MCP server
  - Implement message serialization/deserialization
  - Add agent panel integration
  
- [ ] **Week 3**: Create multi-platform agent binaries
  - Build for all 6 platform/architecture combinations
  - Package as archives with proper structure
  - Generate SHA-256 hashes
  
- [ ] **Week 4**: Package as extension with `extension.toml`
  - Define agent server configuration
  - Add environment variable support
  - Test installation in Zed
  
- [ ] **Week 5**: Publish to ACP Registry
  - Register extension with registry
  - Update documentation
  - Test end-to-end installation
  
- [ ] **Week 6**: User testing and iteration
  - Gather feedback from early adopters
  - Fix bugs and improve UX
  - Plan next iteration

### Priority 4: Deep Integration (8-12 weeks)
- [ ] **Weeks 1-2**: Research Zed's document model API
  - Study Zed's extension API documentation
  - Review source code for document access patterns
  - Understand event system and subscriptions
  
- [ ] **Weeks 3-4**: Design CoDRAG-specific UI components
  - Plan custom panels and views
  - Design state management for RAG context
  - Create mockups and prototypes
  
- [ ] **Weeks 5-8**: Implement project-aware RAG context
  - Integrate with Zed's file system API
  - Add document indexing for RAG
  - Implement real-time context updates
  
- [ ] **Weeks 9-10**: Add inline suggestions feature
  - Implement edit prediction (like Zed's native feature)
  - Add keyboard shortcuts for acceptance/rejection
  - Optimize for low latency
  
- [ ] **Weeks 11-12**: Testing and polish
  - End-to-end testing across platforms
  - Performance optimization
  - Documentation and user guides

---

## 8. Competitive Analysis: Zed vs VSCode Extensions

| Feature | VSCode Extension | Zed Extension |
|---------|-----------------|---------------|
| **Language** | TypeScript/JavaScript | Rust |
| **Runtime** | Node.js (V8) | Native binary |
| **Performance** | Good (JS runtime overhead) | Excellent (native, zero overhead) |
| **Extension Size** | Larger (bundled dependencies) | Smaller (static binary, no deps) |
| **Security** | Sandboxed (Node.js context) | Sandboxed (Zed extension sandbox) |
| **MCP Support** | Via `@vscode/mcp` package | Native (`context_server`) |
| **Agent Support** | Custom protocols (varies) | ACP (standardized, growing ecosystem) |
| **Development Speed** | Fast (JS/TS is quick to iterate) | Slower (Rust compile times, but safer) |
| **Binary Distribution** | NPM packages or downloads | Platform-specific archives |
| **Update Mechanism** | Auto-update via VSCode | Extension manager in Zed |

### Key Insights:

1. **Performance**: Zed's Rust-based extension model offers significantly better performance and smaller binaries, but requires more development effort.

2. **Ecosystem Maturity**: VSCode has a much larger extension ecosystem, but Zed's is growing rapidly with focus on AI/agent integrations.

3. **Future-Proofing**: Zed's ACP protocol is becoming the standard for AI agent integration in editors, making it a strategic investment.

4. **Development Trade-offs**: VSCode extensions are faster to develop but have runtime overhead; Zed extensions require Rust expertise but deliver better performance.

---

## 9. Next Steps & Recommendations

### Immediate Actions (This Week)
1. **Set up research environment**: Install Zed nightly, explore extension system
2. **Review ACP specification**: Understand agent protocol requirements at `agentclientprotocol.com`
3. **Create proof-of-concept**: Simple MCP server extension to validate approach

### Short-Term (2-4 Weeks)
1. **Build MVP**: Basic CoDRAG MCP extension for Zed (Priority 1)
2. **Infrastructure**: Set up Cloudflare R2 + CI/CD pipeline (Priority 2)
3. **Documentation**: Write extension development guide for CoDRAG team

### Medium-Term (1-2 Months)
1. **ACP Integration**: Implement agent server protocol (Priority 3)
2. **Registry Publishing**: Submit to ACP Registry
3. **User Testing**: Gather feedback from early adopters

### Long-Term (3-6 Months)
1. **Deep Integration**: Project-aware RAG, custom UI components (Priority 4)
2. **Feature Parity**: Match VSCode extension capabilities + Zed-specific features
3. **Ecosystem**: Build community around CoDRAG for Zed

### Strategic Recommendation:

**Start with Option A (MCP Extension)** as it offers the fastest path to value while building toward deeper ACP integration. The MCP approach:
- Leverages existing CoDRAG infrastructure
- Lower barrier to entry (no ACP protocol implementation needed)
- Can be done in 2-3 weeks vs. 4-6 weeks for ACP
- Provides immediate value to Zed users

**Then progress to Option C (ACP Agent Server)** once the MCP extension is stable:
- Future-proof investment as ACP becomes the standard
- Better user experience with native agent panel integration
- Access to growing ACP ecosystem

**Ultimate goal is Option E (Deep Integration)** for maximum competitive advantage:
- Differentiated from generic MCP servers
- Leverages Zed's performance characteristics
- Can add unique features not possible with standard MCP

---

## 10. Key Takeaways

### What Makes Zed Special
1. **Performance-first**: Native Rust, minimal overhead, fast startup
2. **Modern tooling**: Custom CI/CD, sccache for compilation caching, multi-platform builds
3. **Extension ecosystem**: Growing support for MCP and ACP with focus on AI/agent integrations
4. **Developer experience**: Weekly releases, nightly builds, transparent process

### What We Can Learn from Zed
1. **Hybrid hosting**: GitHub Releases for stable + object storage (R2/Spaces) for nightlies
2. **Version management**: Both versioned and `latest` pointers enable easy rollback
3. **Security best practices**: SHA-256 hashes for all artifacts, public-read ACLs
4. **CI/CD excellence**: Multi-platform testing, automated releases, artifact validation

### Integration Strategy Summary
1. **Start with MCP**: Lowest barrier to entry, leverages existing infrastructure (2-3 weeks)
2. **Progress to ACP**: Future-proof, deeper integration (4-6 weeks)
3. **Ultimate goal**: Native Zed extension with RAG engine (8-12 weeks)

### Infrastructure Recommendations
1. **Download hosting**: Cloudflare R2 (S3-compatible, no egress fees)
2. **CI/CD**: GitHub Actions with multi-platform builds (like Zed's workflow)
3. **Version resolution**: `latest-sha` file pattern for easy version management
4. **Artifact storage**: Both stable (versioned) and nightly paths

---

## Appendix A: Useful Links

### Zed Resources
- [Zed GitHub Repository](https://github.com/zed-industries/zed)
- [Zed Documentation](https://zed.dev/docs)
- [ACP Registry](https://agentclientprotocol.com/registry)
- [Zed Extensions Directory](https://zed.dev/extensions)
- [ACP Protocol Specification](https://agentclientprotocol.com/spec)

### MCP Resources
- [Model Context Protocol Spec](https://modelcontextprotocol.io)
- [Zed MCP Extensions Docs](https://zed.dev/docs/extensions/mcp-extensions)
- [MCP Registry](https://github.com/modelcontextprotocol/registry)

### ACP Resources
- [Agent Client Protocol](https://agentclientprotocol.com)
- [ACP Registry API](https://agentclientprotocol.com/registry/api)
- [ACP Example Agents](https://github.com/zed-industries/zed/tree/main/extensions)

### Infrastructure Resources
- [Cloudflare R2 Documentation](https://developers.cloudflare.com/r2/)
- [AWS CLI with S3-Compatible APIs](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-s3-advanced.html)
- [DigitalOcean Spaces Documentation](https://www.digitalocean.com/docs/spaces/)

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **ACP** | Agent Client Protocol - standardized protocol for AI agents in editors |
| **MCP** | Model Context Protocol - protocol for connecting LLMs to external tools |
| **RAG** | Retrieval-Augmented Generation - CoDRAG's core technology for context-aware AI |
| **sccache** | Distributed compilation cache used by Zed for faster builds |
| **Context Server** | Zed's term for MCP servers (provides context to AI) |
| **Agent Server** | Zed's term for ACP-based agents (provides AI capabilities) |
| **Notarization** | macOS security process for signing and verifying apps |

---

## Appendix C: Sample Extension.toml Files

### Minimal MCP Server Extension
```toml
id = "codrag-mcp"
name = "CoDRAG MCP Server"
version = "0.1.0"
authors = ["Your Name <your@email.com>"]
description = "CoDRAG RAG integration for Zed"

[context_servers.codrag]
name = "CoDRAG"
```

### Full Agent Server Extension (ACP)
```toml
id = "codrag-agent"
name = "CoDRAG Agent"
version = "0.1.0"
authors = ["Your Name <your@email.com>"]
description = "CoDRAG AI agent for Zed"

[agent_servers.codrag]
name = "CoDRAG Assistant"
icon = "icons/codrag.svg"

[agent_servers.codrag.env]
CODRAG_API_KEY = "your-api-key-here"

[agent_servers.codrag.targets.darwin-aarch64]
archive = "https://cdn.zed.dev/codrag/darwin-aarch64.tar.gz"
cmd = "./codrag-agent"
args = ["serve"]
sha256 = "abc123def456789..."

[agent_servers.codrag.targets.darwin-x86_64]
archive = "https://cdn.zed.dev/codrag/darwin-x86_64.tar.gz"
cmd = "./codrag-agent"
args = ["serve"]
sha256 = "def456ghi789012..."

[agent_servers.codrag.targets.linux-aarch64]
archive = "https://cdn.zed.dev/codrag/linux-aarch64.tar.gz"
cmd = "./codrag-agent"
args = ["serve"]
sha256 = "ghi789jkl012345..."

[agent_servers.codrag.targets.linux-x86_64]
archive = "https://cdn.zed.dev/codrag/linux-x86_64.tar.gz"
cmd = "./codrag-agent"
args = ["serve"]
sha256 = "jkl012mno345678..."

[agent_servers.codrag.targets.windows-aarch64]
archive = "https://cdn.zed.dev/codrag/windows-aarch64.zip"
cmd = "./codrag-agent.exe"
args = ["serve"]
sha256 = "mno345pqr678901..."

[agent_servers.codrag.targets.windows-x86_64]
archive = "https://cdn.zed.dev/codrag/windows-x86_64.zip"
cmd = "./codrag-agent.exe"
args = ["serve"]
sha256 = "pqr678stu901234..."

[agent_servers.codrag.targets.windows-aarch64.env]
CODRAG_LOG_LEVEL = "debug"  # Windows-specific override
```

---

**Research Date**: March 25, 2026  
**Last Updated**: March 25, 2026  
**Status**: Initial Research Complete - Ready for Implementation

---

*This document was generated based on extensive research into Zed's infrastructure, CI/CD pipeline, download hosting, and extension system. All information is accurate as of the research date.*