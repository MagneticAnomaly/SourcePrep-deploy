# Security Policy

## Reporting a Vulnerability

We take the security of RunPrep seriously. If you discover a security vulnerability, please report it to us immediately.

**Do NOT file public GitHub issues for security vulnerabilities.**

### Contact
Please email **security@runprep.io** with a description of the issue, steps to reproduce, and any proof-of-concept code.

### Response Timeline
- **Acknowledgment**: We will acknowledge receipt of your report within 24 hours.
- **Assessment**: We will assess the impact and severity within 3 business days.
- **Resolution**: We aim to release a fix for critical vulnerabilities within 7 days.

## Supported Versions

We provide security updates for the **latest major release** of the RunPrep Desktop Application and the RunPrep MCP Server.

| Version | Supported | Notes |
| :--- | :--- | :--- |
| Latest Release | ✅ | Always upgrade to the latest version for security fixes. |
| < Latest | ❌ | Older versions are not actively patched. |

## Integrity Verification

All official releases of RunPrep are signed.
- **macOS**: Signed with our Apple Developer ID and notarized by Apple.
- **Windows**: Signed with our EV Code Signing Certificate.

Do not run RunPrep binaries that fail signature verification or originate from untrusted sources.
