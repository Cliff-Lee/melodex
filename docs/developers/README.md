# Developer Reference Index

This is the **deep reference index** for the Melodex extension ecosystem.

If you are deciding what to build, use the [Developer Gateway](../DEVELOPERS.md).

If you want a working scaffold immediately, use the [5-minute developer quickstart](../DEVELOPER_QUICKSTART.md).

## Truth and architecture

| Need | Read |
| --- | --- |
| What exists today vs preview/experimental/planned | [Status, stability and trust](00_STATUS_AND_STABILITY.md) |
| Canonical system map and code locations | [Ecosystem architecture](01_ECOSYSTEM_ARCHITECTURE.md) |
| Terminology | [Glossary](15_GLOSSARY.md) |

## Capability extensions

| Need | Read |
| --- | --- |
| Capability contract shapes | [Capability reference](05_CAPABILITY_REFERENCE.md) |
| How independently sourced data combines | [Composition and provenance](06_COMPOSITION_AND_PROVENANCE.md) |
| Runtime routing/composition | [Capability Broker](16_CAPABILITY_BROKER.md) |
| Example implementations | [Reference extensions](13_EXAMPLE_PLUGINS.md) |

Current enrichment contracts are experimental v0.1:

```text
identity.resolve
metadata.enrich
artwork.lookup
lyrics.lookup
```

## Provider development

For playback/catalog providers, the primary detailed reference is the [Provider SDK](../../provider-sdk/README.md).

Provider capabilities can include:

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

Desktop providers communicate with Melodex through the MPP process boundary.

## Trust, testing and publishing

| Need | Read |
| --- | --- |
| Current permission/security boundary | [Permissions and security](07_PERMISSIONS_SECURITY.md) |
| Test an extension | [Testing](08_TESTING.md) |
| Decide whether an upstream source is suitable | [Source and rights policy](11_SOURCE_AND_RIGHTS_POLICY.md) |
| Publish/discover through the registry | [Publishing and registry](10_PUBLISHING_REGISTRY.md) |
| Registry lifecycle/review rules | [Registry governance](17_REGISTRY_GOVERNANCE.md) |
| Review a community plugin | [Plugin review checklist](12_PLUGIN_REVIEW_CHECKLIST.md) |
| Browse/install extensions as a user | [Plugin Directory](../PLUGIN_DIRECTORY.md) |

## Design rules

A good extension should be:

- **small** — implement only useful capabilities;
- **composable** — let other extensions fill gaps;
- **replaceable** — avoid hidden hard dependencies;
- **observable** — expose failures clearly;
- **permission-minimal** — request only needed access;
- **source-neutral** — keep service-specific logic out of Core;
- **provenance-aware** — retain where external data came from.

## Boundary to remember

A provider/extension author should not need to understand the GUI, Flow engine, player internals, taste database or LLM subsystem.

The extension boundary should reduce the problem to:

```text
What capability am I implementing?
What object do I receive?
What object do I return?
```

Return to the [Developer Gateway](../DEVELOPERS.md) when you want the shortest route to a tutorial rather than deeper reference.
