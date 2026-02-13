# Contributing to CLaRa-Remembers-It-All

Thank you for your interest in contributing to CLaRa-Remembers-It-All! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please be respectful and constructive in all interactions. We welcome contributors of all backgrounds and experience levels.

## Getting Started

### Prerequisites

- Python 3.10+
- Git
- For CUDA: NVIDIA GPU with 14GB+ VRAM
- For Apple Silicon: Mac with 16GB+ unified memory

### Development Setup

```bash
# Clone the repository
git clone https://github.com/ericbintner/CLaRa-Remembers-It-All.git
cd CLaRa-Remembers-It-All

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check src/
black --check src/

# Start server in development mode
clara-server --reload
```

## How to Contribute

### Reporting Bugs

1. Check existing issues to avoid duplicates
2. Use the bug report template
3. Include:
   - clara-server version
   - Python version
   - Operating system
   - Backend (CUDA/MPS/CPU)
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages/logs

### Suggesting Features

1. Check existing issues and roadmap
2. Use the feature request template
3. Describe:
   - The problem you're trying to solve
   - Your proposed solution
   - Alternative approaches considered

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Add tests for new functionality
5. Run tests and linting: `pytest && ruff check src/`
6. Commit with clear messages: `git commit -m "Add feature X"`
7. Push to your fork: `git push origin feature/my-feature`
8. Open a Pull Request

#### PR Guidelines

- Keep PRs focused on a single change
- Update documentation if needed
- Add tests for new functionality
- Follow existing code style
- Ensure all tests pass
- Update CHANGELOG.md for significant changes

## Code Style

We use:
- **Black** for code formatting (line length: 100)
- **Ruff** for linting
- **MyPy** for type checking

```bash
# Format code
black src/ tests/

# Check linting
ruff check src/ tests/

# Type checking
mypy src/
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=clara_server

# Run specific test file
pytest tests/test_api.py

# Run tests matching pattern
pytest -k "test_compress"
```

## Documentation

- Update README.md for user-facing changes
- Add docstrings to all public functions/classes
- Use Google-style docstrings

## Project Structure

```
clara-server/
├── src/clara_server/
│   ├── __init__.py      # Package exports
│   ├── cli.py           # Command-line interface
│   ├── config.py        # Configuration management
│   ├── model.py         # Model loading and inference
│   └── server.py        # FastAPI application
├── tests/
│   └── test_api.py      # API tests
├── examples/
│   └── python_client.py # Example client
├── docs/                # Additional documentation
├── Dockerfile           # Container build
├── docker-compose.yml   # Container orchestration
├── pyproject.toml       # Project configuration
└── README.md            # Main documentation
```

## Areas for Contribution

### High Priority

- [ ] MLX backend implementation for native Apple Silicon
- [ ] Batching support for higher throughput
- [ ] GPTQ/AWQ quantization support
- [ ] Prometheus metrics endpoint

### Medium Priority

- [ ] Multi-GPU support
- [ ] Kubernetes Helm chart
- [ ] LangChain integration
- [ ] LlamaIndex integration

### Documentation

- [ ] Deployment guides for various platforms
- [ ] Performance tuning guide
- [ ] Troubleshooting guide

## Release Process

Releases are managed by maintainers:

1. Update version in `pyproject.toml` and `__init__.py`
2. Update CHANGELOG.md
3. Create release tag: `git tag v0.1.0`
4. Push tag: `git push origin v0.1.0`
5. GitHub Actions builds and publishes to PyPI

## Questions?

- Open a GitHub Discussion for questions
- Check existing issues and discussions first
- Be specific about your environment and use case

Thank you for contributing! 🎉
