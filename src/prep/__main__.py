"""
Allow running codrag as a module:
    python -m codrag --repo-root /path/to/repo
"""

from .server import main

if __name__ == "__main__":
    main()
