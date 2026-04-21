# QwenLM/qwen-code Research

## Overview
Qwen Code is an open-source AI agent that lives in the terminal, optimized for Qwen3-Coder models. It provides a Claude Code-like experience with agentic workflows, built-in tools, and optional IDE integrations.

## Technical Integration
- **MCP Support**: Not explicitly mentioned, but terminal-first design suggests MCP integration would be possible via HTTP proxy
- **Plugin Architecture**: TypeScript/Node.js based, mentions optional integration for VS Code, Zed, and JetBrains IDEs - likely uses extension APIs
- **Local Compatibility**: Fully local-first, works offline with local models or cloud APIs (BYOK)
- **Daemon Integration**: Could connect to Prep daemon via MCP or direct HTTP API calls

## Product Fit
- **User Base Size**: Large - Qwen models are popular in China/Asia, growing global adoption
- **Feature Overlap**: Similar to Claude Code (which Prep already mentions), but local Qwen models instead of Anthropic
- **Value Proposition**: Prep's structural context would enhance Qwen's code understanding, especially for large codebases
- **Competition**: Competing with Claude Code, but Qwen offers free tier and local models

## Development Considerations
- **Effort Estimate**: Medium (1-3 months) - Need to build MCP client or extension adapter
- **Maintenance Burden**: Low-medium - Qwen Code is actively maintained by Alibaba/Qwen team
- **Testing Complexity**: Medium - Need to test with actual Qwen models and various codebases
- **Documentation Needs**: Standard integration guide, BYOK setup for cloud APIs

## Business/Marketing
- **Pricing Impact**: Could open "Local AI" tier or expand free tier appeal
- **Brand Alignment**: Fits local-first philosophy, especially with Qwen's focus on open-source
- **Marketing Copy**: "Verified integration with Qwen Code - combine Prep's structural indexing with Qwen3-Coder's powerful reasoning"
- **Competitive Advantage**: First MCP provider to integrate with Qwen ecosystem

## Integration Feasibility Score: 8/10
- Strong technical foundation with IDE extension support
- Large, growing user base
- Clear path to MCP integration
- Marketing synergy with "local AI" positioning

## Next Steps
- Contact Qwen team about MCP integration plans
- Prototype MCP adapter for Qwen Code
- Test with Prep's existing trace index
- Prepare documentation for verified integrations page
