#!/usr/bin/env python3
"""
Example Python client for clara-server.

Usage:
    python python_client.py
    python python_client.py --url http://your-server:8765
"""

import argparse
import json
import sys
from typing import List, Optional

import requests


class ClaraClient:
    """
    Simple client for clara-server API.
    
    Example:
        client = ClaraClient("http://localhost:8765")
        result = client.compress(
            memories=["User likes hiking.", "User has a dog."],
            query="What activities does the user enjoy?"
        )
        print(result["answer"])
    """
    
    def __init__(self, url: str = "http://localhost:8765", api_key: Optional[str] = None):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self._session = requests.Session()
        if api_key:
            self._session.headers["Authorization"] = f"Bearer {api_key}"
    
    def health(self) -> dict:
        """Check server health."""
        response = self._session.get(f"{self.url}/health", timeout=5)
        response.raise_for_status()
        return response.json()
    
    def status(self) -> dict:
        """Get server status."""
        response = self._session.get(f"{self.url}/status", timeout=5)
        response.raise_for_status()
        return response.json()
    
    def compress(
        self,
        memories: List[str],
        query: str,
        max_new_tokens: int = 128,
        timeout: int = 60,
    ) -> dict:
        """
        Compress memories and generate answer.
        
        Args:
            memories: List of memory strings to compress
            query: Question to answer from compressed memories
            max_new_tokens: Maximum tokens in response
            timeout: Request timeout in seconds
        
        Returns:
            Dict with success, answer, token counts, compression ratio, latency
        """
        response = self._session.post(
            f"{self.url}/compress",
            json={
                "memories": memories,
                "query": query,
                "max_new_tokens": max_new_tokens,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()


def main():
    parser = argparse.ArgumentParser(description="CLaRa client example")
    parser.add_argument("--url", default="http://localhost:8765", help="Server URL")
    parser.add_argument("--api-key", help="API key for authentication")
    args = parser.parse_args()
    
    client = ClaraClient(args.url, args.api_key)
    
    # Check health
    print("Checking server health...")
    try:
        health = client.health()
        print(f"✓ Server healthy: {health}")
    except Exception as e:
        print(f"✗ Server unhealthy: {e}")
        sys.exit(1)
    
    # Get status
    print("\nGetting server status...")
    status = client.status()
    print(f"Model: {status['model']}")
    print(f"Backend: {status.get('backend', 'unknown')}")
    print(f"Device: {status.get('device', 'unknown')}")
    print(f"Requests served: {status['requests_served']}")
    
    # Example compression
    print("\n" + "=" * 50)
    print("Example compression:")
    print("=" * 50)
    
    memories = [
        "User enjoys hiking in national parks and photography.",
        "User works as a software engineer and likes Python.",
        "User visited Yellowstone and Yosemite last year.",
        "User has a golden retriever named Max who loves fetch.",
        "User prefers dark mode in all applications.",
        "User drinks coffee in the morning and tea in the afternoon.",
        "User is learning about RAG systems and context compression.",
    ]
    
    query = "What are the user's hobbies and daily habits?"
    
    print(f"\nMemories ({len(memories)} items):")
    for i, m in enumerate(memories, 1):
        print(f"  {i}. {m}")
    
    print(f"\nQuery: {query}")
    print("\nCompressing...")
    
    result = client.compress(memories, query)
    
    if result["success"]:
        print(f"\n✓ Answer: {result['answer']}")
        print(f"\nStats:")
        print(f"  Original tokens: {result['original_tokens']}")
        print(f"  Compressed tokens: {result['compressed_tokens']}")
        print(f"  Compression ratio: {result['compression_ratio']}x")
        print(f"  Latency: {result['latency_ms']}ms")
    else:
        print(f"\n✗ Error: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
