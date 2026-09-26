# Security

Please report security issues privately rather than opening a public issue containing exploit details.

## Provider trust

Desktop `.mdxprovider` packages contain executable third-party code. Melodex runs them out-of-process, but they still run with the operating-system permissions of the current user unless additional OS sandboxing is configured. Install providers only from publishers you trust.

Android does not execute downloaded provider code; it accesses providers through the authenticated Provider Bridge.

## Credentials

Do not commit API keys, provider credentials, bridge bearer tokens, signing keys or LLM secrets. GitHub Actions signing secrets should use repository/environment Secrets.

## Source-integrity boundary

Security reports may also cover provider packages that unexpectedly request credentials, expose tokens, access undeclared hosts, or attempt to bypass access controls. The public Melodex repository intentionally keeps source-specific provider code outside Core unless it is an approved, documented reference integration.
