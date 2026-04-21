"""
Allow running prep as a module:
    python -m prep --repo-root /path/to/repo
"""

from .server import main

if __name__ == "__main__":
    main()
