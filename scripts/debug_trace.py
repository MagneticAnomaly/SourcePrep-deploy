
import sys
import logging
import shutil
import tempfile
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codrag.core.trace import TraceBuilder
from codrag.core.ids import stable_file_node_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_trace")

def main():
    repo_root = Path(__file__).parent.parent.resolve()
    logger.info(f"Repo root: {repo_root}")

    # Create a temp dir for index
    with tempfile.TemporaryDirectory() as tmp_dir:
        index_dir = Path(tmp_dir)
        logger.info(f"Temp index dir: {index_dir}")

        # Config similar to default
        # Target ids.py only - it has minimal dependencies (std lib only)
        include_globs = ["src/codrag/core/ids.py"] 
        exclude_globs = ["**/node_modules/**", "**/.git/**"]
        max_file_bytes = 500_000
        hard_limit_bytes = 100_000_000

        builder = TraceBuilder(
            repo_root=repo_root,
            index_dir=index_dir,
            include_globs=include_globs,
            exclude_globs=exclude_globs,
            max_file_bytes=max_file_bytes,
            hard_limit_bytes=hard_limit_bytes,
        )

        def progress_cb(msg, current, total):
            logger.info(f"Progress: {msg} ({current}/{total})")

        logger.info("Starting build...")
        manifest = builder.build(progress_callback=progress_cb)
        logger.info("Build complete.")
        logger.info(f"Manifest: {manifest}")

        # Verify output
        nodes_path = index_dir / "trace_nodes.jsonl"
        edges_path = index_dir / "trace_edges.jsonl"

        if not nodes_path.exists():
            logger.error("trace_nodes.jsonl not found!")
            return

        logger.info("\n--- Nodes ---")
        with open(nodes_path, "r") as f:
            for line in f:
                print(line.strip())

        logger.info("\n--- Edges ---")
        with open(edges_path, "r") as f:
            for line in f:
                print(line.strip())

if __name__ == "__main__":
    main()
