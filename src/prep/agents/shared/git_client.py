"""Git client for Prep agent operations.

Wraps subprocess git calls for branch management, commits, and archive operations.
Used primarily by the Digital Custodian agent for branch creation, file archiving,
and deletion commits.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List


class GitClient:
    """Thin wrapper around subprocess git for agent branch/commit operations."""

    def __init__(self, repo_root: Path) -> None:
        self._root = repo_root

    def _run(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command in the repo root."""
        return subprocess.run(
            ["git"] + args,
            cwd=self._root,
            capture_output=True,
            text=True,
            check=check,
        )

    def current_branch(self) -> str:
        """Return the current branch name."""
        result = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        return result.stdout.strip()

    def branch_exists(self, branch_name: str) -> bool:
        """Return True if the branch exists locally."""
        result = self._run(["rev-parse", "--verify", f"refs/heads/{branch_name}"], check=False)
        return result.returncode == 0

    def create_branch(self, branch_name: str) -> None:
        """Create and switch to a new branch."""
        self._run(["checkout", "-b", branch_name])

    def switch_branch(self, branch_name: str) -> None:
        """Switch to an existing branch."""
        self._run(["checkout", branch_name])

    def add_files(self, paths: List[str]) -> None:
        """Stage files for commit."""
        self._run(["add"] + paths)

    def commit(self, message: str) -> str:
        """Commit staged changes, returning the full SHA or '' if nothing to commit."""
        result = self._run(["commit", "-m", message], check=False)
        combined = result.stdout + result.stderr
        if "nothing to commit" in combined:
            return ""
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, ["git", "commit"], result.stdout, result.stderr
            )
        sha_result = self._run(["rev-parse", "HEAD"])
        return sha_result.stdout.strip()

    def diff(self, staged: bool = False) -> str:
        """Return the current diff output."""
        args = ["diff"]
        if staged:
            args.append("--staged")
        result = self._run(args)
        return result.stdout

    def delete_files(self, paths: List[str]) -> None:
        """Stage file deletions via git rm."""
        self._run(["rm"] + paths)

    def copy_to_branch(
        self,
        source_paths: List[str],
        target_branch: str,
        target_dir: str,
        commit_message: str,
    ) -> str:
        """Copy files to a target branch, commit them there, then switch back.

        Creates the target branch if it does not exist. Returns the commit SHA.
        """
        origin_branch = self.current_branch()

        # Collect file contents before switching branches
        files_content: list[tuple[str, bytes]] = []
        for src in source_paths:
            src_path = Path(src) if Path(src).is_absolute() else self._root / src
            files_content.append((Path(src).name, src_path.read_bytes()))

        # Switch to (or create) target branch
        if self.branch_exists(target_branch):
            self.switch_branch(target_branch)
        else:
            self.create_branch(target_branch)

        # Write files into target_dir on the target branch
        dest_dir = self._root / target_dir
        dest_dir.mkdir(parents=True, exist_ok=True)

        written: List[str] = []
        for filename, content in files_content:
            dest_file = dest_dir / filename
            dest_file.write_bytes(content)
            written.append(str(dest_file.relative_to(self._root)))

        self.add_files(written)
        sha = self.commit(commit_message)

        # Return to the original branch
        self.switch_branch(origin_branch)

        return sha

    def rev_parse_head(self) -> str:
        """Return the current HEAD SHA (full, 40 chars), or '' if not a repo."""
        result = self._run(["rev-parse", "HEAD"], check=False)
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def is_shallow_repo(self) -> bool:
        """Return True if the repo is a shallow clone."""
        result = self._run(["rev-parse", "--is-shallow-repository"], check=False)
        if result.returncode != 0:
            return False
        return result.stdout.strip().lower() == "true"

    def log_numstat_since(
        self,
        *,
        since_days: int,
        max_commits: int = 2000,
    ) -> str:
        """Return raw `git log --numstat` output for the window.

        Format (streamed, newline-separated):
            COMMIT <sha>|<author>|<iso_date>|<subject_first_80_chars>
            <added>\\t<removed>\\t<path>
            <added>\\t<removed>\\t<path>
            ...

        Returns empty string on failure (not-a-repo, shallow, permission).
        Callers parse the output; this method is intentionally dumb.
        """
        result = self._run(
            [
                "log",
                f"--since={since_days} days ago",
                f"--max-count={max_commits}",
                "--numstat",
                "--no-merges",
                "--format=COMMIT %H|%an|%aI|%s",
            ],
            check=False,
        )
        if result.returncode != 0:
            return ""
        return result.stdout
