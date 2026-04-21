# CoDRAG Troubleshooting Guide

Quick solutions for common issues.

## Connection Issues

### Ollama Not Available

```
Error: OLLAMA_UNAVAILABLE
```

**Causes:**
- Ollama service not running
- Wrong Ollama URL configured

**Solutions:**
```bash
# Start Ollama
ollama serve

# Check it's running
curl http://localhost:11434/api/tags

# If using non-default URL
export OLLAMA_HOST="http://localhost:11434"
codrag serve
```

### Daemon Not Running

```
Error: DAEMON_UNAVAILABLE
Connection refused
```

**Solutions:**
```bash
# Start the daemon
codrag serve

# Check health
curl http://127.0.0.1:8400/health

# Check if port is in use
lsof -i :8400
```

## Index Issues

### Index Not Built

```
Error: INDEX_NOT_BUILT
```

**Solution:**
```bash
codrag build
```

### Build Failed

```
Error: BUILD_FAILED
```

**Check logs for details:**
```bash
codrag status --verbose
```

**Common causes:**
- No files match include patterns
- All files excluded
- Ollama model not available

**Solutions:**
```bash
# Check what files would be indexed
codrag coverage

# Verify include patterns
codrag config get include_globs

# Pull missing model
ollama pull nomic-embed-text
```

### Build Takes Too Long

**Solutions:**
1. Exclude large/generated files:
   ```bash
   codrag config set exclude_globs '["**/node_modules/**", "**/dist/**", "**/*.min.js"]'
   ```

2. Reduce max file size:
   ```bash
   codrag config set max_file_bytes 200000
   ```

3. Use selective roots:
   ```bash
   codrag build --roots src,lib
   ```

### Index Corruption

**Symptoms:** Search returns errors, status shows inconsistent counts

**Solution:** Force full rebuild:
```bash
codrag build --full
```

## Search Issues

### No Results

**Causes:**
- Query too specific
- Content not indexed
- High min_score threshold

**Solutions:**
```bash
# Lower threshold
codrag search "query" --min-score 0.0

# Check what's indexed
codrag status

# Verify file is included
codrag coverage --file src/myfile.py
```

### Poor Results

**Solutions:**
1. Add primer file (`AGENTS.md`) with project context
2. Use more specific queries
3. Check if relevant files are excluded

### Search Before Build

```
Error: INDEX_NOT_BUILT
```

**Solution:** Build the index first:
```bash
codrag build
```

## Project Issues

### Project Not Found

```
Error: PROJECT_NOT_FOUND
```

**Solutions:**
```bash
# List registered projects
codrag list

# Add project
codrag add /path/to/repo

# Check project ID
codrag list --verbose
```

### Project Already Exists

```
Error: PROJECT_ALREADY_EXISTS
```

**Solutions:**
```bash
# Remove existing
codrag remove <project_id>

# Or update instead
codrag update <project_id> --name "New Name"
```

### Project Path Missing

```
Error: PROJECT_PATH_MISSING
```

The project's directory no longer exists.

**Solutions:**
```bash
# Remove stale project
codrag remove <project_id>

# Or update path
codrag update <project_id> --path /new/path
```

## MCP Issues

### Tools Not Appearing

**Check:**
1. Config file path is correct
2. `codrag` is in PATH
3. Daemon is running

**Debug:**
```bash
# Test MCP server directly
codrag mcp --help

# Check daemon
curl http://127.0.0.1:8400/health
```

### Project Selection Ambiguous

```
Error: PROJECT_SELECTION_AMBIGUOUS
```

**Solutions:**
1. Set project explicitly:
   ```bash
   export CODRAG_PROJECT_ID="proj_abc123"
   ```

2. Or in MCP config:
   ```json
   {
     "env": {
       "CODRAG_PROJECT_ID": "proj_abc123"
     }
   }
   ```

## Performance Issues

### High Memory Usage

**Solutions:**
1. Reduce indexed files
2. Lower `max_file_bytes`
3. Use incremental builds (default)

### Slow Startup

**Causes:** Loading large index

**Solutions:**
1. Keep index size reasonable
2. Exclude unnecessary files
3. Use SSD storage for `.prep/`

## File Issues

### File Not Included

```
Error: FILE_NOT_INCLUDED
```

**Solution:** Update include patterns:
```bash
codrag config set include_globs '["**/*.py", "**/*.your_ext"]'
codrag build
```

### File Excluded

```
Error: FILE_EXCLUDED
```

**Solution:** Check exclude patterns:
```bash
codrag config get exclude_globs

# Remove pattern or add exception
codrag config set exclude_globs '["**/node_modules/**"]'
```

### File Too Large

```
Error: FILE_TOO_LARGE
```

**Solutions:**
1. Increase limit:
   ```bash
   codrag config set max_file_bytes 500000
   ```

2. Or exclude the file:
   ```bash
   codrag config set exclude_globs '["**/large_file.json"]'
   ```

## Getting More Help

### Enable Debug Logging

```bash
CODRAG_LOG_LEVEL=debug codrag serve
```

### Check Version

```bash
codrag --version
```

### Report Issues

Include in bug reports:
- CoDRAG version
- Python version
- Ollama version and model
- Error message and stack trace
- Minimal reproduction steps

**GitHub Issues:** https://github.com/MagneticAnomaly/CoDRAG-MCP/issues
