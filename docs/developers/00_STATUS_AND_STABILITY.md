# Status, Stability and Trust

This page is the project's **truth table**. For wording such as *registry-verified*, *reviewed*, *built into the app*, *project-maintained reference*, and *sandbox*, also use [Terminology and claim policy](02_TERMINOLOGY_AND_CLAIMS.md).

Melodex is intentionally developing in public. Some surfaces are implemented and usable today; some are preview/experimental; some are design targets. Documentation should not blur those categories.

## Labels used in this documentation

| Label | Meaning |
| --- | --- |
| **Implemented** | Present in the current public repository and exercised by tests |
| **Preview** | Implemented, but compatibility may still change before a stable commitment |
| **Experimental** | Implemented for real use/testing, but the contract is deliberately still evolving |
| **Planned** | Design direction, not something users/developers should assume exists |
| **Historical** | Useful design/migration record, not current implementation guidance |

## Current ecosystem status

| Surface | Current status | Stability / important limitation |
| --- | --- | --- |
| Desktop provider manager | **Implemented** | Source-neutral runtime is in the public desktop app |
| Local files / built-in sources | **Implemented** | First-party runtime behavior |
| Music Map | **Implemented / Preview** | Desktop local-library view using cached Flow features, deterministic 2D projection, bounded sonic/factual overlays, explainable Pathfinder routing and local semantic Journey Designer stages; layout/routing/stage heuristics may evolve |
| `.mdxprovider` installation | **Implemented** | Desktop only; package extraction rejects traversal/symlinks |
| MPP JSON-RPC subprocess transport | **Implemented** | **MPP 1.0 preview**; do not read “1.0” as a final compatibility guarantee yet |
| Provider SDK | **Implemented** | SDK package is currently **0.x** and may evolve |
| MPP `recommendations.get` | **Implemented / Preview** | Optional recommendation-only provider operation; results are discovery metadata and may require resolution through another playback provider |
| `melodex-provider init/validate/doctor/pack` | **Implemented** | Recommended fast path for provider authors |
| Capability Broker | **Implemented** | Broker runtime exists |
| `.mdxplugin` installation | **Implemented** | Desktop capability-extension runtime |
| identity / metadata / artwork / lyrics contracts | **Experimental v0.1** | Real and testable, but contract changes are still possible |
| context card contract | **Experimental v0.1** | `context.lookup` adds sourced text/list/fact cards to Rich Now Playing; deliberately host-rendered rather than plugin-specific GUI |
| local intelligence contract | **Experimental v0.1** | `library.suggest` ranks privacy-preserving local-library profiles; Core withholds paths, database keys and absolute listening timestamps |
| `melodex-extension init/validate/doctor/pack` | **Implemented** | Scaffolding/tooling is usable today |
| Plugin Directory | **Implemented** | Registry-backed discovery/install in desktop Sources |
| Registry package SHA-256 + size verification | **Implemented** | Verifies bytes against registry metadata; does **not** identify the publisher cryptographically |
| Installation provenance ledger | **Implemented** | Records manual vs registry install, version, time and package hash for new installs |
| Plugin update detection | **Implemented** | Directory can identify a newer registry version; updates remain user-initiated |
| Registry status labels | **Implemented** | `example/community/reviewed/deprecated/blocked`; labels are project metadata, not cryptographic proof |
| Registry review history | **Implemented** | Append-only per-plugin review records are tied to the current version/package SHA-256 and validated in CI; review is still not publisher signing or legal endorsement |
| Declared plugin permissions | **Implemented** | Visible metadata/review contract; not universal OS enforcement |
| Declared plugin configuration broker | **Implemented / Preview** | Schema-driven `string`/`secret`/`boolean` configuration; only declared values are brokered to the plugin |
| Plugin install/setup onboarding | **Implemented** | Registry and manual installs automatically prompt for missing required configuration; incomplete installs remain visible as `SETUP NEEDED` |
| Plugin health/testing UI | **Implemented / Preview** | Providers use bounded `provider.health`; extensions expose process/runtime health without claiming a universal upstream connectivity test |
| Optional extension health contract | **Implemented / Preview** | `.mdxplugin` may declare bounded `extension.health`; `upstream_checked` distinguishes genuine upstream connectivity from local self-checks |
| Secret configuration storage | **Implemented** | System credential store when available; otherwise session-only memory rather than plaintext JSON |
| Playback-host allowlist enforcement | **Implemented** | Playback Gateway checks external provider HTTP(S) playback URLs and redirects against declared hosts; this is not process-wide network isolation |
| OS-enforced plugin network/filesystem sandbox | **Not implemented** | Provider/extension processes still run with the current user's OS permissions |
| Child-process environment scrubbing | **Implemented** | Third-party subprocesses receive a small allowlist plus package identity/runtime paths, not the complete parent environment |
| Publisher signatures / verified-publisher keyring | **Planned** | SHA-256 is integrity, not signing |
| Redacted diagnostics export | **Implemented** | Sources can export support JSON without plugin config values, credentials, local library paths, stream/playback URLs, headers or cookies; users should still review before sharing |
| Full provider health/diagnostic UI | **Planned** | Extension health and diagnostic export exist; richer provider-level live diagnostics remain future work |
| Automatic plugin updates | **Not implemented** | Deliberately no silent update mechanism |
| REST control API | **Implemented** | Authenticated local/LAN control surface |
| OpenAPI discovery | **Implemented** | `GET /openapi.json` |
| OpenAI function schemas | **Implemented** | `GET /v1/openai/tools` and `melodex-openai-tools` |
| MCP control | **Implemented** | Optional external-control path |
| Android arbitrary downloaded plugins | **Not supported** | Android uses built-in functionality / Bridge model rather than executing downloaded plugin code |
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

Means the project applied its current technical/source-policy review process. The registry links to an append-only review record whose latest event identifies the reviewed plugin version and package SHA-256.

It is still not publisher signing, a warranty, or a legal/content endorsement of every result from an upstream service.

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

These declarations support transparency, UI and review. A narrow playback-host allowlist is enforced by the Playback Gateway for external provider HTTP(S) playback resources and redirects.

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
