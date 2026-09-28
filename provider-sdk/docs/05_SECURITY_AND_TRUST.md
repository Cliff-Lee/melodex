# 5. Security and Trust Model

> **Status note:** this document contains both current behavior and design targets. Where they differ, the **Current implementation** sections are authoritative. See also [Status, stability and trust](../../docs/developers/00_STATUS_AND_STABILITY.md).

## 5.1 Principle

A music provider should be treated like an untrusted network client, not like part of the Melodex GUI.

## 5.2 Current implementation

Desktop third-party providers:

- run outside the GUI process;
- communicate through JSON-RPC/stdin/stdout;
- are terminated independently;
- have request/protocol failure isolation;
- declare permissions in their manifests;
- can be installed manually or through the registry-backed Plugin Directory;
- receive package-integrity verification on registry installs.

But today:

- provider processes are **not** in a complete OS-level sandbox;
- declared network domains are **not** universally kernel/firewall-enforced;
- filesystem restrictions are declarations/design intent, not universal OS enforcement;
- publisher signatures are not implemented;
- current child processes inherit the Melodex process environment.

So a provider should still be treated as third-party code running with the current user's OS permissions.

## 5.3 Provider permission declarations

Manifest permissions include:

- network hosts;
- local-file access;
- offline-download permission;
- browser authentication;
- LAN discovery;
- microphone: not part of provider v1;
- arbitrary command execution: not a declared provider capability.

Declarations support transparency/review and future enforcement.

They must not be presented as proof that the operating system has enforced the boundary.

## 5.4 Credentials

Security goals:

- credentials keyed by provider/account profile;
- no credentials in manifests;
- no secrets in logs/playlists/provenance;
- no provider access to unrelated LLM/provider secrets;
- platform credential stores where practical.

**Current limitation:** a complete third-party provider credential broker is not yet implemented, and subprocesses currently inherit the Melodex environment.

Until that is fixed, do not run Melodex with unrelated secrets exported into its environment and do not document environment-variable secrets as the long-term provider-auth model.

## 5.5 Process boundary

Current benefits:

- provider crash should not crash the GUI;
- protocol corruption can be isolated;
- Python/native provider implementation stays outside Melodex imports;
- Core does not hand providers SQLite handles.

Planned strengthening:

- scrub/allowlist child-process environment;
- explicit credential/configuration broker;
- process/resource limits where practical;
- stronger platform-specific sandboxing;
- permission-policy enforcement where feasible;
- structured/redacted diagnostic export.

## 5.6 Registry/package integrity

Installable registry entries publish:

- HTTPS package URL;
- byte size;
- SHA-256.

Melodex verifies all three before registry installation.

This protects package integrity **relative to the registry metadata**.

It does not cryptographically identify the publisher.

## 5.7 Provider signing

**Not implemented today.**

Planned trust concepts may include:

- signed packages;
- verified-publisher keys;
- key rotation/revocation;
- reproducible packaging guidance.

Do not label a current package “signed” or a publisher “cryptographically verified” unless that mechanism actually exists.

## 5.8 Remote bridge

Current Bridge/control APIs use bearer-token authentication.

Longer-term trust work includes richer device pairing, fingerprints, token revocation and clearer per-device state.

Never expose provider credentials to remote clients.

## 5.9 Content/source neutrality

The public provider SDK describes generic media-source integration.

It should not ship:

- DRM/access-control circumvention;
- CAPTCHA bypass/evasion tooling;
- private credentials;
- connectors intended to obtain media without authorization.

Provider authors remain responsible for having an appropriate basis to access/expose their source.
