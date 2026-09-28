# Melodex Developer Ecosystem

Melodex is a player **and** an extension platform.

The ecosystem goal is simple:

> An extension should be able to contribute one useful capability without having to become an entire music service.

## Start fast

Want a working scaffold first? Use the **[5-minute developer quickstart](../DEVELOPER_QUICKSTART.md)**.

Want the exact maturity/security picture? Read **[Status, stability and trust](00_STATUS_AND_STABILITY.md)**.

For the canonical system map, see **[Ecosystem architecture](01_ECOSYSTEM_ARCHITECTURE.md)**.

For the rules that keep public claims/navigation consistent, see **[Documentation policy](02_DOCUMENTATION_POLICY.md)**.

## Start by goal

| Goal | Read |
| --- | --- |
| Build a playback/search source | [Provider tutorial](../tutorials/BUILD_A_PROVIDER.md) |
| Add identity/metadata/artwork/lyrics | [Enrichment tutorial](../tutorials/BUILD_AN_ENRICHMENT_PLUGIN.md) |
| Understand capabilities | [Capability reference](05_CAPABILITY_REFERENCE.md) |
| Understand how extensions cooperate | [Composition and provenance](06_COMPOSITION_AND_PROVENANCE.md) |
| Test an extension | [Testing](08_TESTING.md) |
| Browse/install extensions | [Plugin Directory](../PLUGIN_DIRECTORY.md) |
| Publish/discover extensions | [Registry](10_PUBLISHING_REGISTRY.md) |
| Understand registry review/governance | [Registry governance](17_REGISTRY_GOVERNANCE.md) |
| Check source/API suitability | [Source and rights policy](11_SOURCE_AND_RIGHTS_POLICY.md) |
| Review a community plugin | [Review checklist](12_PLUGIN_REVIEW_CHECKLIST.md) |
| Study reference extensions | [Example plugins](13_EXAMPLE_PLUGINS.md) |

## Three extension levels

### 1. Declarative provider — proposed

For simple APIs/sites that can eventually be described with configuration rather than custom code.

### 2. Provider SDK — implemented

Current MPP providers can declare:

```text
search
browse
track
album
artist
playback
library
offline
recommendations
auth
```

Desktop providers communicate through JSON-RPC over stdin/stdout.

### 3. Capability extension — experimental contracts, runnable broker

Experimental contracts:

```text
identity.resolve
metadata.enrich
artwork.lookup
lyrics.lookup
```

These are deliberately versioned separately from the stable provider manifest while the model is tested with real implementations.

## Design rules

A good extension should be:

- **small** — implement only useful capabilities;
- **composable** — let other extensions fill gaps;
- **replaceable** — avoid hidden hard dependencies;
- **observable** — expose failures clearly;
- **permission-minimal** — request only needed access;
- **source-neutral** — keep service-specific logic out of Core;
- **provenance-aware** — retain where external data came from.

## You should not need Melodex internals

A provider author should not need to understand the GUI, Flow engine, player internals, taste database or LLM subsystem.

The extension boundary should reduce the problem to:

```text
What capability am I implementing?
What object do I receive?
What object do I return?
```
