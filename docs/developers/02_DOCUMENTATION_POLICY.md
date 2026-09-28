# Documentation Policy

Melodex documentation is part of the product.

The goal is not to make every page short. The goal is to make the **first route obvious**, the **deep detail available**, and the **claims precise enough that a reader can tell what exists today**.

## Canonical pages

Use these pages for these questions:

| Question | Canonical page |
| --- | --- |
| What is Melodex? | root [README](../../README.md) |
| Where should a normal user start? | [Start Here](../START_HERE.md) |
| How do I navigate the docs? | [Documentation home](../README.md) |
| Where are the maintained user/developer guides? | [Documentation index](../ALL_DOCUMENTATION.md) |
| What is implemented vs experimental/planned? | [Status, stability and trust](00_STATUS_AND_STABILITY.md) |
| How does the ecosystem fit together? | [Ecosystem architecture](01_ECOSYSTEM_ARCHITECTURE.md) |
| Does `main` differ from releases? | [Releases, main, and version numbers](../RELEASES_AND_MAIN.md) |
| How do I build a plugin quickly? | [5-minute developer quickstart](../DEVELOPER_QUICKSTART.md) |
| What is the current security boundary? | [Permissions and security](07_PERMISSIONS_SECURITY.md) and [Security](../../SECURITY.md) |
| How do plugins get published? | [Registry governance](17_REGISTRY_GOVERNANCE.md) |

If another page conflicts with one of these, fix the conflict rather than inventing a third interpretation.

## Audience layers

Documentation should follow this order:

```text
friendly entry point
        ↓
short task tutorial
        ↓
reference / architecture
        ↓
specification / schema / implementation detail
```

A beginner should not have to read the protocol specification before creating a provider.

An experienced developer should not be prevented from reaching the protocol specification quickly.

## Truth labels

Use these labels consistently:

### Implemented

Present in the public repository and exercised by current code/tests.

### Preview

Implemented, but compatibility can still change before a stable commitment.

### Experimental

Implemented for real use/testing, with an explicitly evolving contract.

### Planned

A design target, not something the reader can assume exists.

### Historical

Useful context/design record, not current implementation guidance.

Do not use future-tense design text without one of these contexts when a reader could reasonably mistake it for a shipped feature.

## Release versus `main`

Repository documentation on `main` describes `main` unless stated otherwise.

Tagged releases are snapshots and can lag behind `main`.

Do not write installation/release documentation that implies every feature documented on `main` exists in the latest release binary.

## Security language

Prefer precise descriptions over reassuring adjectives.

Good:

> Provider processes run outside the GUI process, which provides failure isolation.

Bad:

> Providers are sandboxed.

unless a complete relevant sandbox is actually enforced.

Similarly:

- **declared permission** is not the same as **OS-enforced permission**;
- **registry-verified bytes** are not the same as **signed publisher identity**;
- **reviewed** is not the same as **endorsed**;
- **local-first** is not the same as **never uses the network**.

## “Verified” must have an object

Avoid bare phrases such as:

```text
verified plugin
verified provider
verified package
```

Prefer:

```text
registry hash-verified package
package SHA-256 verified against registry metadata
reviewed registry entry
cryptographically signed publisher   # only once implemented
```

The reader should know **what was verified, against what evidence**.

## Privacy claims

If a page says data is local, also state the network conditions that can send it elsewhere.

If a page discusses model context, name the categories actually sent by the current code.

If a credential is stored locally without an OS credential vault, say so.

Do not rely on “we do not intentionally send X” as a substitute for documenting where X is stored.

## UI instructions

Use the exact current visible UI wording where practical.

For example:

```text
Sources → Add local folder…
Sources → Explore plugins…
Show power tools
Play for me
Build this journey
```

If there are two valid routes, choose one as the tutorial's primary route and mention the other as an alternative instead of switching routes mid-tutorial.

## Version numbers

Keep these separate:

```text
app version
Provider SDK version
MPP protocol version
capability-contract version
plugin version
API/platform version
```

Do not say “Melodex 1.0” when the subject is actually MPP `protocol_version: "1.0"`.

Development app versions use a `.devN` suffix between tagged releases.

## External services

For external APIs/services:

- link to the official source/terms when practical;
- avoid claiming rights that the upstream project itself does not claim;
- preserve per-item rights/licence caveats;
- avoid hard-coding third-party version numbers unless the minimum version truly matters.

Examples and reference integrations are not endorsements.

## Duplication

Duplication is acceptable when it reduces navigation cost, but duplicated facts must have a canonical home.

Prefer:

> See Status, stability and trust for the current security boundary.

over copying a large, independently maintained security matrix into five tutorials.

## Automated checks

CI currently runs:

```bash
python scripts/docs_check.py
python scripts/ecosystem_check.py
python scripts/version_check.py
python scripts/release_check.py
```

These checks complement review; they do not prove documentation truth automatically.

When a documentation claim cannot be mechanically checked, reviewers should compare it with current code/tests or the relevant official upstream source.

## Documentation changes are first-class changes

A documentation-only pull request is valuable when it makes the project more accurate, navigable or understandable.

If code behavior changes, ask:

1. Does a quickstart/tutorial change?
2. Does the status/stability table change?
3. Does security/privacy wording change?
4. Does an API/tool list change?
5. Does the release/main distinction matter?
6. Does the changelog need an entry?

“Docs later” is how public architecture becomes misleading.
