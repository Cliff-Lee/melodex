# Melodex Community

Melodex should be a project where people can contribute **small useful pieces**. You do not need to become a Melodex Core developer.

## Start small

If you want to contribute to this repository and are not sure where to begin, use **[Your First Melodex Contribution](FIRST_CONTRIBUTION.md)**.

If you want to build a provider or extension immediately, use the **[5-minute developer quickstart](DEVELOPER_QUICKSTART.md)**.

You do not need to understand Melodex Core first.

## Ways to contribute

### Build a provider

Know a legal/open music API, public-domain archive, radio directory or home music server? Build an MPP provider.

Start with [Build a provider](tutorials/BUILD_A_PROVIDER.md).

### Build one capability

Know a good metadata, identity or artwork source? Build exactly that capability.

Start with [Build an enrichment plugin](tutorials/BUILD_AN_ENRICHMENT_PLUGIN.md).

### Publish to the Plugin Directory

Package your provider or capability extension, host the release in your own repository, and propose a registry entry.

Melodex verifies package SHA-256 before installation.

Start with [Publish a community plugin](tutorials/ADD_PLUGIN_TO_REGISTRY.md).

### Build on the API

Create a CLI controller, phone remote, Stream Deck integration, home-automation bridge, generated client or accessibility interface.

Start with [Control Melodex with REST](tutorials/CONTROL_MELODEX_WITH_REST.md).

### Build AI tools

Use MCP or OpenAI function calling:

- [OpenWebUI / MCP tutorial](tutorials/CONNECT_OPENWEBUI_MCP.md)
- [OpenAI function tutorial](tutorials/USE_OPENAI_FUNCTIONS.md)

### Improve documentation or testing

Documentation PRs, fixtures, source research, accessibility work, translations and platform testing are first-class contributions.

## Good first issue philosophy

A good first issue should be narrow, have a clear expected result, point to relevant files, and not require understanding the whole architecture.

Examples:

```text
Add one provider fixture test
Improve one tutorial
Add one SOURCE_POLICY.md
Generate one API client example
Improve one error message
Add one capability example
```

## Community plugin expectations

Public/community extensions should normally include:

```text
README
licence
source repository
version
capabilities
permissions
tests / fixtures
SOURCE_POLICY.md
```

The source policy should explain the upstream API, authentication, rate limits, data/media rights, caching, offline/download rules, commercial restrictions and attribution.

## Be kind to upstream services

Reference/community plugins should identify themselves with a meaningful User-Agent, obey published rate limits, cache responsibly, handle outages and prefer documented APIs over aggressive scraping.

## Security

Never post API keys, passwords, cookies, Melodex Bridge tokens, MCP tokens or private signed media URLs.

## Pull requests

Small PRs are welcome. Explain what changed, why it is useful, how it was tested, documentation impact, and source-policy implications when relevant.

See [First Contribution](FIRST_CONTRIBUTION.md), [CONTRIBUTING.md](../CONTRIBUTING.md), [Code of Conduct](../CODE_OF_CONDUCT.md), [Plugin Directory](PLUGIN_DIRECTORY.md), and [Registry governance](developers/17_REGISTRY_GOVERNANCE.md).


## Transparency matters

Community trust depends on accurate labels.

Please distinguish:

- implemented vs planned;
- preview/experimental vs stable;
- declared permissions vs OS-enforced restrictions;
- registry-verified bytes vs signed publisher identity;
- project review status vs legal/content endorsement.

See [Status, stability and trust](developers/00_STATUS_AND_STABILITY.md).
