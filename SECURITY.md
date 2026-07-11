# Security Policy

## Supported Versions

Use this section to tell people about which versions of your project are
currently being supported with security updates.

| Version | Supported          |
| ------- | ------------------ |
| 1.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in RemoveSamples-NZBGet, please report it responsibly by following these steps:

### How to Report
1. **DO NOT** create a public GitHub issue for security vulnerabilities
2. Send an email to anunnaki.astronaut@machinamindmeld.com with:
   - A clear description of the vulnerability
   - Steps to reproduce the issue
   - Potential impact assessment
   - Your contact information

### What to Expect
- **Response Time**: We will acknowledge receipt within 48 hours
- **Investigation**: We will investigate and provide an initial assessment within 7 days
- **Updates**: You will receive regular updates on our progress
- **Resolution**: If accepted, we will work on a fix and coordinate disclosure
- **Credit**: Security researchers will be credited in our release notes (unless you prefer to remain anonymous)

### Scope
This security policy covers:
- The main RemoveSamples extension code
- Configuration vulnerabilities that could lead to unintended file deletion
- Path traversal or directory escape issues

### Out of Scope
- Issues in NZBGet itself (report to NZBGet maintainers)
- Social engineering attacks
- Physical access attacks

## Security Best Practices for Users

When using RemoveSamples-NZBGet:
- Always test configuration on non-critical downloads first
- Regularly review debug logs to ensure expected behavior
- Keep NZBGet and Python updated to latest versions
- Use appropriate file permissions on your NZBGet installation

Thank you for helping keep RemoveSamples-NZBGet secure!
