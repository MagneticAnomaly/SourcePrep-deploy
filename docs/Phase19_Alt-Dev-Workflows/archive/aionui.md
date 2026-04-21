# iOfficeAI/AionUi Research

## Overview
AionUi is a free, local, open-source GUI that provides a unified interface for multiple command-line AI tools including Gemini CLI, Claude Code, Qwen Code, Goose CLI, and Auggie. Features multi-agent mode, WebUI access, scheduled tasks, and smart file management.

## Technical Integration
- **MCP Support**: Not explicitly mentioned, but designed to work with CLI tools that may support MCP
- **Plugin Architecture**: Electron/web-based (inferred from WebUI features), extensible design for CLI tool integration
- **Local Compatibility**: Fully local-first, designed for local CLI tools
- **Daemon Integration**: Could integrate Prep as additional CLI tool or via MCP if supported

## Product Fit
- **User Base Size**: Large and growing - 49 releases, 35 contributors, active community
- **Feature Overlap**: GUI frontend for multiple CLI tools, similar to Gemini CLI Desktop but supports more tools
- **Value Proposition**: Prep could enhance all supported CLI tools with superior code context
- **Competition**: Direct competitor to Gemini CLI Desktop, broader tool support

## Development Considerations
- **Effort Estimate**: Medium (1-3 months) - Need to build adapter for AionUi's CLI integration system
- **Maintenance Burden**: Medium - AionUi is actively developed, frequent updates
- **Testing Complexity**: Medium-high - Test with multiple CLI tools, ensure context flows properly
- **Documentation Needs**: Integration guide for each supported CLI tool + Prep

## Business/Marketing
- **Pricing Impact**: Could drive enterprise adoption (scheduled tasks, remote access features)
- **Brand Alignment**: Local-first, supports multiple tools = flexibility and choice
- **Marketing Copy**: "Verified integration with AionUi - the enterprise GUI for AI-assisted development with Prep context"
- **Competitive Advantage**: Prep works with more tools via AionUi than any other context provider

## Integration Feasibility Score: 7/10
- Broad CLI tool support is advantage
- Active development and community
- Integration path exists but may require custom adapter
- Good for enterprise marketing

## Next Steps
- Contact AionUi maintainers about MCP support plans
- Prototype Prep integration via CLI tool adapter
- Test with Claude Code (already supported) and Qwen Code
- Evaluate for enterprise feature set (scheduled tasks, remote access)
