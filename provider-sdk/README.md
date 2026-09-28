# Melodex Provider SDK

A source-neutral provider protocol and developer SDK for **Melodex**.

> Melodex owns playback, Flow, taste, queueing and LLM control. Providers supply
> catalog and authorized playback access.

## Status

**SDK v0.4.0 / MPP 1.0 preview.** v0.4 adds registry validation and package-integrity tooling on top of the provider and capability-extension SDK.

Melodex now has two package types:

```text
.mdxprovider   catalog/playback providers
.mdxplugin     identity/metadata/artwork/lyrics extensions
```

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
melodex-provider init my-provider
melodex-provider validate my-provider
melodex-provider doctor my-provider
melodex-provider pack my-provider
```

Capability extension:

```bash
melodex-extension init my-artwork --capability artwork
melodex-extension validate my-artwork
melodex-extension doctor my-artwork
melodex-extension pack my-artwork
```

Registry maintenance:

```bash
melodex-registry validate registry/registry.json
melodex-registry summary registry/registry.json
melodex-registry verify-packages registry/registry.json --packages registry/packages
```

## Clean core, messy edge

Providers may deal internally with JSON APIs, HTML, XML, redirects, detail pages,
sessions or temporary CDN URLs. Melodex only needs normalized catalog items and
normalized playback resources.

```text
source-specific discovery
        ↓
provider adapter
        ↓
artist / title / album / opaque track id
        ↓
playback.resolve
        ↓
URL + optional headers/cookies/expiry
        ↓
Melodex Playback Gateway
        ↓
QMediaPlayer
```

## Provider doctor

`melodex-provider doctor` checks the manifest, package shape and, for Python
entrypoints, `provider.info`, `provider.health`, `catalog.search`, and
`playback.resolve`.

## Vendored dependencies

A Python provider may ship a `vendor/` directory. Melodex adds it to the provider
process `PYTHONPATH`, so a provider can remain self-contained without installing
packages into the user's Melodex environment.

The SDK also offers a small standard-library `WebSession` helper for cookies,
redirects, retries, gzip, rate limiting, relative URLs and JSON/XML responses.
Complex HTML parsers can be vendored per provider.

## Documentation

- [Provider developer guide](docs/04_PROVIDER_DEVELOPER_GUIDE.md)
- [Messy provider playbook](docs/10_MESSY_PROVIDER_PLAYBOOK.md)
- [Playback Gateway](docs/11_PLAYBACK_GATEWAY.md)
- [Legal reference sources](docs/12_LEGAL_REFERENCE_SOURCES.md)
- [OpenAPI mapping](spec/openapi.yaml)
- [JSON-RPC mapping](spec/mpp-jsonrpc.md)
- [Experimental capability contracts](spec/extensions/v0.1/README.md)
- [Capability Broker](../docs/developers/16_CAPABILITY_BROKER.md)
- [Build an enrichment plugin](../docs/tutorials/BUILD_AN_ENRICHMENT_PLUGIN.md)
- [Plugin Directory](../docs/PLUGIN_DIRECTORY.md)
- [Registry governance](../docs/developers/17_REGISTRY_GOVERNANCE.md)

## Source neutrality

The SDK does not ship DRM/access-control circumvention, CAPTCHA bypass,
anti-bot evasion, private credentials, or connectors intended to obtain media
without authorization.

## License

MIT for SDK code and documentation unless a file states otherwise.
