# Prep Error Code Taxonomy

This document defines the standardized error codes used across Prep's HTTP API, MCP server, and CLI.

## Error Envelope Format

All API responses use a consistent envelope format:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description",
    "hint": "Optional suggestion for resolution",
    "details": {}  // Optional additional context
  }
}
```

## Error Code Categories

### Validation Errors (400)

| Code | Description | Hint |
|------|-------------|------|
| `VALIDATION_ERROR` | Generic validation failure (missing/invalid fields) | Check request body format |
| `INVALID_PATH` | File path contains invalid characters or traversal | Provide a repo-root-relative path without '..' segments |

### Not Found Errors (404)

| Code | Description | Hint |
|------|-------------|------|
| `PROJECT_NOT_FOUND` | Project ID does not exist in registry | Add the project first or select an existing project |
| `FILE_NOT_FOUND` | Requested file does not exist | Check the file path |
| `NODE_NOT_FOUND` | Trace node ID does not exist | Verify the node ID exists in the trace index |

### Conflict Errors (409)

| Code | Description | Hint |
|------|-------------|------|
| `PROJECT_ALREADY_EXISTS` | Project with same path already registered | Use a different path or remove existing project |
| `BUILD_ALREADY_RUNNING` | Index build already in progress | Wait for current build to complete |
| `TRACE_BUILD_ALREADY_RUNNING` | Trace build already in progress | Wait for current trace build to complete |
| `INDEX_NOT_BUILT` | Attempting to search/context before build | Run a build first |
| `TRACE_DISABLED` | Trace operation on project without trace enabled | Enable trace in project settings |

### Permission Errors (403)

| Code | Description | Hint |
|------|-------------|------|
| `FILE_NOT_INCLUDED` | File not matched by include_globs | Update include_globs to allow this file |
| `FILE_EXCLUDED` | File matched by exclude_globs | Update exclude_globs to allow this file |

### Payload Errors (413)

| Code | Description | Hint |
|------|-------------|------|
| `FILE_TOO_LARGE` | File exceeds max_file_bytes limit | Increase max_file_bytes in project settings |

### Server Errors (500)

| Code | Description | Hint |
|------|-------------|------|
| `FILE_READ_FAILED` | Failed to read file from disk | Check file permissions |
| `BUILD_FAILED` | Index build encountered an error | Check server logs for details |
| `INTERNAL_ERROR` | Unexpected server error | Report to maintainers |
| `IO_ERROR` | General I/O operation failed | Check disk space and permissions |
| `INSUFFICIENT_SPACE` | Not enough disk space to perform build | Free up disk space |
| `DOWNLOAD_FAILED` | Failed to download external resource | Check internet connection |
| `NATIVE_DEPS_MISSING` | Required native dependencies not found | Install missing dependencies (e.g. pip install prep[native]) |
| `NOT_IMPLEMENTED` | Feature not yet implemented | Wait for future update |

### Project Path Errors (400)

| Code | Description | Hint |
|------|-------------|------|
| `PROJECT_PATH_MISSING` | Project's repo_root no longer exists | Update project path or remove project |
| `PATH_OUTSIDE_PROJECT` | Requested path is outside project root | Ensure path is relative to project root |
| `PATH_NOT_FOUND` | Directory path does not exist | Check directory existence |
| `CHUNK_NOT_FOUND` | Document chunk ID not found | Rebuild index if chunk should exist |

## HTTP Status Code Mapping

| HTTP Status | Error Category |
|-------------|----------------|
| 400 | Validation / Bad Request |
| 403 | Forbidden / Policy Violation |
| 404 | Not Found |
| 409 | Conflict / State Error |
| 413 | Payload Too Large |
| 500 | Internal Server Error |

## MCP Error Codes

MCP uses JSON-RPC 2.0 error codes:

| Code | Name | Description |
|------|------|-------------|
| -32700 | `PARSE_ERROR` | Invalid JSON |
| -32600 | `INVALID_REQUEST` | Invalid JSON-RPC request |
| -32601 | `METHOD_NOT_FOUND` | Unknown method |
| -32602 | `INVALID_PARAMS` | Invalid method parameters |
| -32603 | `INTERNAL_ERROR` | Internal server error |

## Usage Guidelines

### When to use `hint`

Always provide a `hint` when:
- The error is recoverable by user action
- There's a clear next step the user should take
- The error relates to configuration that can be changed

### When to use `details`

Provide `details` when:
- Additional context would help debugging (e.g., file sizes, limits)
- The error involves multiple items (e.g., list of failed files)
- Programmatic consumers need structured error data

### Error Message Style

- Use sentence case (capitalize first word only)
- Be specific: "Index has not been built yet" not "Index error"
- Include relevant identifiers: "Project with ID 'abc123' not found"
- Keep messages under 100 characters

## Adding New Error Codes

1. Choose an appropriate HTTP status code
2. Create a descriptive `UPPER_SNAKE_CASE` code
3. Add to this taxonomy document
4. Use `ApiException` in Python code:

```python
raise ApiException(
    status_code=409,
    code="MY_NEW_ERROR",
    message="Clear description of what went wrong",
    hint="What the user can do to fix it",
    details={"key": "value"},  # Optional
)
```

## Cross-Layer Consistency

Error codes should be consistent across:
- **HTTP API** (`/api/*`, `/projects/*`)
- **MCP Server** (`prep_*` tools)
- **CLI** (`prep` commands)

When the same error can occur in multiple layers, use the same code.
