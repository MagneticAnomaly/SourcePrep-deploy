
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from prep.mcp_direct import DirectMCPServer

async def test_direct_mcp():
    print("Initializing DirectMCPServer...")
    # Use the current directory as repo root
    server = DirectMCPServer(repo_root=Path.cwd())
    
    print("Testing tool_status...")
    status = await server.tool_status()
    print(f"Status: {json.dumps(status, indent=2)}")
    
    # We won't run build/search because it might be heavy, but we check if tool works
    assert status["daemon"] == "direct_mode"
    assert "repo_root" in status
    
    print("DirectMCPServer test passed!")

if __name__ == "__main__":
    asyncio.run(test_direct_mcp())
