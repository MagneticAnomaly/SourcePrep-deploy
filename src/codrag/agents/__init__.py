"""CoDRAG autonomous agent subsystem.

Three agents share a common AgentCore:
- Staffing Agent (hr/) — generates and audits Paperclip agent roles
- Researcher Agent (researcher/) — mines audit findings, pushes research plans
- Digital Custodian (custodian/) — identifies and cleans dead code
"""

from codrag.agents.core import AgentCore

__all__ = ["AgentCore"]
