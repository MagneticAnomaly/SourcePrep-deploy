
import asyncio
import shutil
import sys
import json
from pathlib import Path

# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from prep.mcp_direct import DirectMCPServer

async def test_end_to_end():
    repo_root = Path(__file__).parent / "fixtures" / "mini_repo"
    prep_dir = repo_root / ".prep"
    
    # Clean up previous run
    if prep_dir.exists():
        shutil.rmtree(prep_dir)
        
    print(f"Testing with repo: {repo_root}")
    
    # Initialize Server
    server = DirectMCPServer(repo_root=repo_root)
    
    # 1. Check Status (should be empty)
    print("\n--- Status (Pre-Build) ---")
    status = await server.tool_status()
    print(json.dumps(status, indent=2))
    assert status["total_documents"] == 0
    assert status["index_loaded"] == False
    
    # 2. Trigger Build
    print("\n--- Building ---")
    build_res = await server.tool_build()
    print(json.dumps(build_res, indent=2))
    
    # Wait for build to finish (polling)
    for _ in range(20):
        await asyncio.sleep(1)
        status = await server.tool_status()
        if not status["building"] and status["index_loaded"]:
            break
        print(".", end="", flush=True)
    print()
    
    status = await server.tool_status()
    print(f"Post-Build Status: {json.dumps(status, indent=2)}")
    assert status["total_documents"] > 0
    assert status["index_loaded"] == True
    
    # 3. Search
    print("\n--- Searching ---")
    search_res = await server.tool_search("hello world")
    print(json.dumps(search_res, indent=2))
    assert search_res["count"] > 0
    assert "main.py" in str(search_res["results"])
    
    # 4. Context
    print("\n--- Context ---")
    ctx_res = await server.tool_context("explain the main function")
    print(f"Context length: {len(ctx_res['context'])}")
    assert len(ctx_res["context"]) > 0
    
    print("\nSuccess! End-to-end Direct MCP test passed.")

if __name__ == "__main__":
    asyncio.run(test_end_to_end())
