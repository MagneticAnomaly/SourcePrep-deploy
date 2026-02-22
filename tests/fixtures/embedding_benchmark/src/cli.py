"""Command-line interface for the application."""

import argparse
import sys
from typing import List, Optional


def create_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="myapp",
        description="Example application with user management and caching",
    )
    subparsers = parser.add_subparsers(dest="command")

    # serve command
    serve = subparsers.add_parser("serve", help="Start the HTTP server")
    serve.add_argument("--host", default="0.0.0.0", help="Bind address")
    serve.add_argument("--port", type=int, default=8000, help="Port number")
    serve.add_argument("--workers", type=int, default=4, help="Number of worker processes")
    serve.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    # migrate command
    migrate = subparsers.add_parser("migrate", help="Run database migrations")
    migrate.add_argument("--direction", choices=["up", "down"], default="up")
    migrate.add_argument("--steps", type=int, default=0, help="Number of migration steps (0=all)")

    # user management
    user = subparsers.add_parser("user", help="User management commands")
    user_sub = user.add_subparsers(dest="user_command")
    user_sub.add_parser("list", help="List all users")
    create = user_sub.add_parser("create", help="Create a new user")
    create.add_argument("--email", required=True)
    create.add_argument("--role", choices=["admin", "user", "viewer"], default="user")

    # cache command
    cache = subparsers.add_parser("cache", help="Cache management")
    cache.add_argument("--clear", action="store_true", help="Clear all cached data")
    cache.add_argument("--stats", action="store_true", help="Show cache statistics")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "serve":
        print(f"Starting server on {args.host}:{args.port} with {args.workers} workers")
        return 0

    if args.command == "migrate":
        print(f"Running migrations {args.direction} (steps={args.steps})")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
