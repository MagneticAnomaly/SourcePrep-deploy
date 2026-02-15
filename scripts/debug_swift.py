
import sys
import logging
from pathlib import Path
import tempfile

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codrag.core.trace import TraceBuilder, TraceNode
from codrag.core.ids import stable_file_node_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_swift")

SAMPLE_SWIFT = """
import SwiftUI
import CoreData

class UserManager {
    func createUser(name: String) {
        print("Creating user \(name)")
    }
}

struct UserView: View {
    var body: some View {
        Text("Hello")
    }
}

public protocol DataProvider {
    func fetchData()
}

extension String {
    func localized() -> String {
        return NSLocalizedString(self, comment: "")
    }
}
"""

def main():
    with tempfile.TemporaryDirectory() as tmp_dir:
        repo_root = Path(tmp_dir)
        index_dir = repo_root / ".index"
        
        # Create sample file
        src_file = repo_root / "App" / "Sources" / "Test.swift"
        src_file.parent.mkdir(parents=True)
        src_file.write_text(SAMPLE_SWIFT, encoding="utf-8")
        
        logger.info(f"Created sample Swift file at {src_file}")
        
        include_globs = ["**/*.swift"]
        exclude_globs = []
        
        builder = TraceBuilder(
            repo_root=repo_root,
            index_dir=index_dir,
            include_globs=include_globs,
            exclude_globs=exclude_globs,
        )
        
        logger.info("Building trace...")
        manifest = builder.build()
        logger.info("Build finished.")
        
        # Check output
        nodes_path = index_dir / "trace_nodes.jsonl"
        if not nodes_path.exists():
            logger.error("trace_nodes.jsonl missing!")
            return
            
        logger.info("\n--- Nodes Found ---")
        with open(nodes_path, "r") as f:
            for line in f:
                import json
                node = json.loads(line)
                print(f"[{node['kind']}] {node['name']} ({node.get('language', '')})")
                if node['kind'] == 'symbol':
                    meta = node.get('metadata', {})
                    print(f"  -> Type: {meta.get('symbol_type')}, Qualname: {meta.get('qualname')}")

if __name__ == "__main__":
    main()
