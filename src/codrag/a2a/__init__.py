"""
CoDRAG A2A (Agent-to-Agent) Protocol Support — Phase 63.

Implements Google's A2A protocol (Linux Foundation governance) to make
CoDRAG discoverable and invokable by any A2A-compliant agent.

Modules:
    agent_card  — Static Agent Card served at /.well-known/agent.json
    handler     — JSON-RPC 2.0 task handler for A2A requests
"""
