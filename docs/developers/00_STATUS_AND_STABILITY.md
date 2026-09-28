# Status, Stability and Trust

This page is the project's **truth table**.

Melodex is intentionally developing in public. Some surfaces are implemented and usable today; some are preview/experimental; some are design targets. Documentation should not blur those categories.

## Labels used in this documentation

| Label | Meaning |
| --- | --- |
| **Implemented** | Present in the current public repository and exercised by tests |
| **Preview** | Implemented, but compatibility may still change before a stable commitment |
| **Experimental** | Implemented for real use/testing, but the contract is deliberately still evolving |
| **Planned** | Design direction, not something users/developers should assume exists |
| **Historical** | Useful design/migration record, not current implementation guidance |

## Release context

Repository documentation on `main` describes current development. Tagged release binaries can lag behind `main`.

See [Releases, main, and version numbers](../RELEASES_AND_MAIN.md).

## Current ecosystem status

| Surface | Current status | Stability / important limitation |
| --- | --- | --- |
| Desktop provider manager | **Implemented** | Source-neutral runtime is in the public desktop app |
| Local files / built-in sources | **Implemented** | First-party runtime behavior |
| `.mdxprovider` installation | **Implemented** | Desktop only; package extraction rejects traversal/symlinks |
| MPP JSON-RPC subprocess transport | **Implemented** | **MPP 1.0 preview**; do not read “1.0” as a final compatibility guarantee yet |
| Provider SDK | **Implemented** | SDK package is currently **0.x** and may evolve |
| `melodex-provider init/validate/doctor/pack` | **Implemented** | Recommended fast path for provider authors |
| Capability Broker | **Implemented** | Broker runtime exists |
| `.mdxplugin` installation | **Implemented** | Desktop capability-extension runtime |
| identity / metadata / artwork / lyrics contracts | **Experimental v0.1** | Real and testable, but contract changes are still possible |
| `melodex-extension init/validate/doctor/pack` | **Implemented** | Scaffolding/tooling is usable today |
| Plugin Directory | **Implemented** | Registry-backed discovery/install in desktop Sources |
| Registry package SHA-256 + size verification | **Implemented** | Verifies bytes against registry metadata; does **not** identify the publisher cryptographically |
| Installation provenance ledger | **Implemented** | Records manual vs registry install, version, time and package hash for new installs |
| Plugin update detection | **Implemented** | Directory can identify a newer registry version; updates remain user-initiated |
| Registry status labels | **Implemented** | `example/community/reviewed/deprecated/blocked`; labels are project metadata, not cryptographic proof |
| Declared plugin permissions | **Implemented** | Visible metadata/review contract |
| OS-enforced plugin network/filesystem sandbox | **Not implemented** | Provider/extension processes still run with the current user's OS permissions |
| Child-process environment scrubbing | **Not implemented** | Current subprocesses inherit the Melodex process environment; do not launch Melodex with unrelated exported secrets |
| LLM API-key OS credential vault | **Not implemented** | GUI-entered LLM API keys are currently stored in the local SQLite preferences database |
| Publisher signatures / verified-publisher keyring | **Planned** | SHA-256 is integrity, not signing |
| Full provider health/diagnostic UI | **Planned** | CLI doctor and runtime errors exist; richer UI is future work |
| Automatic plugin updates | **Not implemented** | Deliberately no silent update mechanism |
| REST control API | **Implemented** | Authenticated local/LAN control surface |
| OpenAPI discovery | **Implemented** | `GET /openapi.json` |
| OpenAI function schemas | **Implemented** | `GET /v1/openai/tools` and `melodex-openai-tools` |
| MCP control | **Implemented** | Optional external-control path; high-level application tool names are kept in parity with OpenAI function tools |
| Android arbitrary downloaded plugins | **Not supported** | Android uses built-in functionality / Bridge model rather than executing downloaded plugin code |
| Bridge remote playback with provider-specific headers/cookies | **Partial** | Local files and ordinary remote stream redirects work; provider-specific upstream request-state is not yet fully proxied to LAN/mobile clients |
| iOS app/plugin runtime | **Planned/design only** | Architecture documentation is not a claim of a shipped iOS app |

## “Verified” can mean different things

Melodex should use precise language.

### Registry-verified package

Means:

```text
downloaded bytes
==
SHA-256 + byte size recorded in the registry

and

package-declared ID/version
==
registry ID/version
```

It does **not** mean:

- the publisher's legal identity was cryptographically proved;
- Melodex audited every line of code;
- the upstream source will remain safe/available;
- every media item returned is licensed the same way.

### Reviewed registry entry

Means the project applied its current technical/source-policy review process.

It is still not a warranty or endorsement of every result from an upstream service.

### Signed publisher

**Not implemented yet.**

That phrase should not be used for current third-party packages.

## Permission declarations are not a sandbox

Manifests/descriptors declare things such as:

```text
network hosts
local file access
offline downloads
browser authentication
LAN discovery
```

Today these declarations support transparency, UI, review and future enforcement.

They should **not** be described as universal OS-level enforcement. Desktop provider/extension processes run outside the GUI process, which improves failure isolation, but they still execute with the current user's operating-system permissions unless the OS/container environment adds stronger sandboxing.

## Compatibility language

Keep these versions distinct:

- **SDK version** — Python developer-tool package version, currently 0.x;
- **MPP protocol_version** — provider wire-contract identifier;
- **capability contract_version** — enrichment contract version such as 0.1;
- **plugin version** — extension author's release version;
- **Melodex app version** — player release version.

A matching number in two of those fields does not make them the same versioning system.

## Historical design documents

Some older files under `provider-sdk/docs/` describe the migration that produced the current source-neutral architecture.

They remain useful design records, but a historical migration document should not override this status page or current runtime documentation.

## If documentation disagrees

Treat current code/tests plus this status page as authoritative, then open a documentation issue.

Transparency is a project requirement, not a marketing extra.
