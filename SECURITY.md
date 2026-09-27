# Security

Please report security issues privately rather than opening a public issue containing exploit details.

## Provider trust

Desktop `.mdxprovider` packages contain executable third-party code. Melodex runs them out-of-process, but they still run with the operating-system permissions of the current user unless additional OS sandboxing is configured.

Install providers only from publishers you trust.

Android does not execute downloaded provider code; it accesses providers through the authenticated Provider Bridge.

## Credentials and LLM/control redaction

Do not commit API keys, provider credentials, Bridge bearer tokens, signing keys or LLM secrets.

Melodex v0.2 treats playback-only state separately from public track metadata. Control/LLM responses redact fields such as:

- request headers;
- cookies;
- refresh/access tokens;
- signed playback URLs;
- local file paths;
- internal gateway/host-permission state.

## Playback Gateway

The Playback Gateway is loopback-only, uses unpredictable registration tokens and validates provider-declared playback hosts. It supports authorised stateful/temporary media requests; it is not an access-control bypass.

## Source-integrity boundary

The public project intentionally excludes DRM/access-control circumvention, CAPTCHA bypass, private credentials and anti-bot evasion.
