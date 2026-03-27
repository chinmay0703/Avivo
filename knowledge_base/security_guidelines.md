# Security Guidelines

## Password Policy
- Minimum 12 characters
- Must include uppercase, lowercase, number, and special character
- Passwords expire every 90 days
- Cannot reuse the last 10 passwords
- Multi-factor authentication (MFA) is mandatory for all accounts

## Data Classification
- **Public**: Marketing materials, blog posts
- **Internal**: Company policies, internal docs
- **Confidential**: Customer data, financial reports
- **Restricted**: Security credentials, encryption keys

## Handling Sensitive Data
- Never store passwords or API keys in source code
- Use the company vault (HashiCorp Vault) for secrets management
- Encrypt all data at rest and in transit
- PII must be anonymized in non-production environments
- Log redaction is mandatory for any field containing PII

## Incident Reporting
If you discover a security vulnerability or suspect a breach:
1. Do NOT try to fix it yourself
2. Report immediately to security@company.com
3. Do not share details on public channels
4. The security team will triage within 1 hour for critical issues

## Access Control
- Principle of least privilege applies to all systems
- Access reviews are conducted quarterly
- Service accounts require documented ownership
- Production access requires just-in-time (JIT) approval

## Approved Tools
- VPN: GlobalProtect
- Password Manager: 1Password (company license)
- Communication: Slack (internal), verified email (external)
- File Sharing: Google Drive (internal), approved secure transfer for external
