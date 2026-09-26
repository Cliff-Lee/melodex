# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for vulnerabilities involving credential exposure, provider sandbox escape, unauthorized filesystem/network access, bridge authentication, token leakage, or remote code execution.

Until a dedicated private reporting address is configured, use GitHub's **Private vulnerability reporting** feature for this repository if it is enabled.

Include:

- affected SDK/protocol version;
- platform;
- reproduction steps or proof of concept;
- expected impact;
- suggested mitigation, if known.

## Security model

Third-party providers are untrusted. The intended architecture is:

- provider code runs outside the Melodex GUI process;
- manifests declare requested network/file/offline permissions;
- credentials are stored by Melodex using the platform credential vault;
- providers do not receive LLM keys, taste history, or other providers' secrets;
- remote Provider Bridge access is authenticated;
- diagnostic exports must redact credentials and signed playback URLs.

See `docs/05_SECURITY_AND_TRUST.md` for the full design.
