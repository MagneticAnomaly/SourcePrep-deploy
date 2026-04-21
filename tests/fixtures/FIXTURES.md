# Test Fixtures Guide

This document explains how test fixtures work in CoDRAG and how to use them effectively.

## Shared Pytest Fixtures (conftest.py)

The following fixtures are automatically available to all test files:

### `mini_repo`
Creates a minimal test repository with deterministic content (main.py, utils.py, README.md).
```python
def test_something(mini_repo: Path):
    server = DirectMCPServer(repo_root=mini_repo)
```

### `fake_embedder`
Provides a FakeEmbedder for testing without Ollama dependency.
```python
def test_something(fake_embedder):
    idx = CodeIndex(index_dir=..., embedder=fake_embedder)
```

### `clean_codrag_dir`
Ensures `.codrag` directory is clean before and after test.
```python
def test_something(clean_codrag_dir):
    repo = clean_codrag_dir  # .codrag is guaranteed clean
```

## What are Test Fixtures?

Test fixtures are **deterministic, self-contained data directories** that tests use as input. They provide:

- **Reproducibility**: Same files every test run
- **Isolation**: No dependency on your real repos or machine state
- **Speed**: Small repos index quickly
- **Focus**: Only the files needed to assert specific behavior

## Directory Structure

```
tests/
├── conftest.py              # Pytest configuration and shared fixtures
├── fixtures/               # All fixture repos live here
│   └── mini_repo/          # Minimal 2-file repo for Direct MCP E2E tests
│       ├── main.py
│       └── README.md
├── test_*.py                # Test files
└── FIXTURES.md             # This file
```

## The `mini_repo` Fixture

### Purpose

`tests/fixtures/mini_repo/` is a tiny "fake repository" used by the Direct MCP end-to-end test. It contains:

- **`main.py`**: A simple Python module with a `main()` function
- **`README.md`**: A markdown file

### How It's Used

From `tests/test_mcp_direct_e2e.py`:

```python
repo_root = Path(__file__).parent / "fixtures" / "mini_repo"
server = DirectMCPServer(repo_root=repo_root)
```

The test then:

1. **Builds** an index from `mini_repo`
2. **Asserts** `total_documents > 0`
3. **Searches** for `"hello world"` and expects `"main.py"` in results
4. **Assembles** context for a query

### Why This Works

- The fixture is small (2 files), so indexing is fast
- The content is deterministic (same `main.py` every run)
- The test can assert specific behavior (e.g., "search finds main.py")

## Creating New Fixtures

### Step 1: Create the Fixture Directory

```bash
mkdir tests/fixtures/my_scenario
```

### Step 2: Add Files

Add only the files needed for your test scenario:

```python
# tests/fixtures/my_scenario/example.py
def example():
    return "test content"
```

### Step 3: Use in Tests

```python
repo_root = Path(__file__).parent / "fixtures" / "my_scenario"
server = DirectMCPServer(repo_root=repo_root)
```

### Step 4: Clean Up Build State (Optional)

If your test needs a clean slate, delete the `.codrag` directory:

```python
codrag_dir = repo_root / ".codrag"
if codrag_dir.exists():
    shutil.rmtree(codrag_dir)
```

## Best Practices

### 1. Keep Fixtures Minimal

Only include files needed for the test. Avoid:
- Large files (slow indexing)
- Unnecessary directories
- Binary files (unless testing binary handling)

### 2. Use Deterministic Content

Avoid timestamps, random data, or anything that changes between runs:

```python
# Good
def main():
    return "hello world"

# Bad (non-deterministic)
def main():
    return f"hello at {datetime.now()}"
```

### 3. Document Fixture Purpose

Add a `README.md` in the fixture directory explaining what it tests:

```markdown
# Multi-File Fixture

Tests that search works across multiple files and that
include/exclude globs are respected correctly.
```

### 4. Avoid Real Repo Dependencies

Never point tests at your actual working directory:

```python
# Bad (flaky, depends on your machine state)
repo_root = Path.cwd()

# Good (deterministic)
repo_root = Path(__file__).parent / "fixtures" / "mini_repo"
```

### 5. Test Against Fixture, Not Your Real Code

Fixtures let you test **CoDRAG's behavior** without needing a real project:

- Test indexing: Does CoDRAG index files correctly?
- Test search: Does search return expected results?
- Test context: Does context assembly work?

## Common Fixture Patterns

### Pattern 1: Minimal Single File

```python
# tests/fixtures/single_file/code.py
def func():
    return "value"
```

Use for: Basic indexing/search tests.

### Pattern 2: Multiple Files for Cross-File Search

```python
# tests/fixtures/multi_files/
├── a.py
├── b.py
└── c.py
```

Use for: Testing that search spans multiple files.

### Pattern 3: Include/Exclude Testing

```python
# tests/fixtures/globs/
├── src/
│   └── main.py
├── tests/
│   └── test_main.py
└── vendor/
    └── external.py
```

Use for: Testing that `include_globs` and `exclude_globs` work.

### Pattern 4: Large File Testing

```python
# tests/fixtures/large_file/big.py
# 500KB+ file
```

Use for: Testing `max_file_bytes` enforcement.

## Fixture State Management

### `.codrag` Directory

CoDRAG creates `.prep/` inside repos to store:
- Index files
- Manifests
- Build state

This directory is **safe to delete** in tests because it's inside the fixture repo:

```python
codrag_dir = repo_root / ".codrag"
if codrag_dir.exists():
    shutil.rmtree(codrag_dir)
```

### Clean State for Each Test

If a test needs a clean state, delete `.codrag` at the start:

```python
async def test_something():
    repo_root = Path(__file__).parent / "fixtures" / "mini_repo"
    codrag_dir = repo_root / ".codrag"
    if codrag_dir.exists():
        shutil.rmtree(codrag_dir)
    
    server = DirectMCPServer(repo_root=repo_root)
    # ... rest of test
```

## Running Tests Against Fixtures

```bash
# Run all tests
python scripts/run_tests.py

# Run specific test
pytest tests/test_mcp_direct_e2e.py::test_end_to_end -v

# Run with verbose output
pytest tests/test_mcp_direct_e2e.py -vv
```

## Troubleshooting

### Fixture Not Found

If you see `FileNotFoundError`, check:

```python
# Should be relative to test file
repo_root = Path(__file__).parent / "fixtures" / "mini_repo"
```

### No Documents Indexed

If `total_documents == 0`, check:
- Fixture directory exists and has files
- Files match `include_globs` (default: `**/*.py`, `**/*.md`, etc.)
- Files don't match `exclude_globs`
- Files are under `max_file_bytes` (default: 400KB)

### Search Returns No Results

If search returns `count == 0`, check:
- Build completed successfully (`status["index_loaded"] == True`)
- Query terms match fixture content
- Files are actually indexed (`status["total_documents"] > 0`)

## Summary

- **Fixtures** = small, deterministic repos for testing
- **`mini_repo`** = 2-file fixture for Direct MCP E2E tests
- **Create new fixtures** under `tests/fixtures/` when needed
- **Keep fixtures minimal** and deterministic
- **Clean `.prep/`** if you need a fresh state

For more on running tests, see `scripts/run_tests.py` and `pyproject.toml` for test configuration.
