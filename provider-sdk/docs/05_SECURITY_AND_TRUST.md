# 5. Security and trust model

## 5.1 Principle

A music provider should be treated like an untrusted network client, not like part of the Melodex GUI.

## 5.2 Provider permissions

Manifest permissions are explicit:

- network hosts;
- local-file access;
- offline-download permission;
- browser authentication;
- LAN discovery;
- microphone: **not allowed** in provider v1;
- arbitrary command execution: **not allowed**.

A provider does not receive:

- the user's LLM API keys;
- taste database;
- Moments/Vibes database;
- other providers' credentials;
- full filesystem access by default.

## 5.3 Credentials

Credential records are keyed by `provider_id` and account profile.

Backends:

- macOS/iOS: Keychain;
- Windows: Credential Manager / DPAPI;
- Android: Keystore-backed encrypted storage;
- Linux: Secret Service/KWallet when available.

No credential should be written to `manifest.json`, logs, playlists or exported diagnostic bundles.

## 5.4 Local provider process

Desktop process transport should enforce:

- no inherited secret environment variables except an ephemeral provider session token;
- dedicated working directory;
- stdin/stdout reserved for protocol messages;
- stderr captured into provider logs;
- request timeouts;
- memory/process limits where practical;
- kill/restart on protocol corruption;
- no direct Melodex SQLite handles.

OS-level network-domain enforcement is difficult to make perfect cross-platform. The permission UI should therefore distinguish **declared** network domains from **verified/sandboxed** enforcement.

## 5.5 Remote bridge

Bridge requirements:

- HTTPS outside loopback;
- bearer tokens with revocation;
- pairing token expires quickly;
- optional device names;
- per-device access log;
- `GET /v1/health` may be public on LAN, all catalog/playback methods authenticated;
- never expose provider credentials to clients;
- bridge resolves playback on behalf of authenticated Melodex clients.

## 5.6 Provider signing

v1 should support, not require, publisher signatures.

Trust labels:

- **Built in** — shipped by Melodex;
- **Verified publisher** — signature chains to a trusted Melodex publisher key;
- **Local developer** — installed with developer mode;
- **Unverified** — user explicitly approved.

Do not imply that a signature means Melodex endorses a provider's content or legality; it only identifies the publisher/package integrity.

## 5.7 Content/source neutrality

The public provider SDK should describe generic media-source integration. It should not ship source-specific bypass logic, DRM circumvention helpers, or templates aimed at unauthorized services.

Provider authors are responsible for having permission to access and expose media from their source.
